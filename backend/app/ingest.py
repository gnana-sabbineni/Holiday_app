import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Holiday, HolidayState, HolidayStateLink

StateKey = tuple[str, str]  # (country_code, abbrev), e.g. ("US", "NV")


def get_or_create_states(db: Session, records: list[dict]) -> dict[StateKey, HolidayState]:
    """Make sure every (country, abbrev) used by `records` has exactly ONE row, and return them.

    Existing rows are reused (so a state is never duplicated, no matter how many
    holidays mention it). Only missing details (name / iso) are filled in.
    """
    wanted: dict[StateKey, dict] = {}
    for r in records:
        for s in r["states"]:
            info = wanted.setdefault((r["country_code"], s["abbrev"]), {"name": None, "iso": None})
            info["name"] = info["name"] or s.get("name")
            info["iso"] = info["iso"] or s.get("iso")
    if not wanted:
        return {}

    countries = {country for country, _ in wanted}
    existing: dict[StateKey, HolidayState] = {
        (s.country_code, s.abbrev): s
        for s in db.scalars(select(HolidayState).where(HolidayState.country_code.in_(countries)))
    }

    for key, info in wanted.items():
        state = existing.get(key)
        if state is None:
            state = HolidayState(country_code=key[0], abbrev=key[1], name=info["name"], iso=info["iso"])
            db.add(state)
            existing[key] = state
        else:
            if state.name is None and info["name"]:
                state.name = info["name"]
            if state.iso is None and info["iso"]:
                state.iso = info["iso"]

    db.flush()  # gives every new state its id, needed to build the links below
    return {key: existing[key] for key in wanted}


def _links_for(record: dict, states: dict[StateKey, HolidayState]) -> list[HolidayStateLink]:
    """The holiday -> state assignments for one record (each state at most once)."""
    links: dict[int, HolidayStateLink] = {}
    for s in record["states"]:
        state = states[(record["country_code"], s["abbrev"])]
        if state.id not in links:
            links[state.id] = HolidayStateLink(state_id=state.id, note=s.get("note"))
    return list(links.values())


def replace_holidays(db: Session, records: list[dict]) -> int:
    """Delete existing holidays for the same (country, year), then insert.
    Safe to re-run: you get the same result, not doubled rows.
    States are shared reference data: they are created once and never deleted here,
    only the holiday -> state links are rebuilt."""
    scopes = {(r["country_code"], r["date"].year) for r in records}
    for country, year in scopes:
        stale = db.scalars(
            select(Holiday).where(
                Holiday.country_code == country,
                Holiday.date >= dt.date(year, 1, 1),
                Holiday.date <= dt.date(year, 12, 31),
            )
        ).all()
        for holiday in stale:
            db.delete(holiday)  # ORM delete, so cascade also removes its links (not the states)
    db.flush()

    states = get_or_create_states(db, records)

    db.add_all(
        Holiday(
            name=r["name"], description=r["description"], country_code=r["country_code"],
            date=r["date"], primary_type=r["primary_type"], types=r["types"],
            nationwide=r["nationwide"], locations=r["locations"], url=r["url"], urlid=r["urlid"],
            state_links=_links_for(r, states),
        )
        for r in records
    )
    db.commit()
    return len(records)
