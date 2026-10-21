import datetime as dt
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    NATIONWIDE_ABBREV,
    NATIONWIDE_NAME,
    Country,
    Holiday,
    HolidayState,
    HolidayStateLink,
)


@dataclass
class LoadResult:
    country_code: str
    country_name: str
    country_created: bool
    holidays: int
    states_used: int      # real states used by this file (the "whole country" row is not counted)
    states_created: int   # how many of them were new


def resolve_country(records: list[dict], override: str | None = None) -> tuple[str, str | None]:
    """Decide which country a file belongs to -> (code, name or None).

    The country is read from the records. `override` (the --country option) is only
    needed when the file carries no country; if it disagrees with the file, we stop.
    """
    codes = {r["country_code"] for r in records if r.get("country_code")}
    if len(codes) > 1:
        raise ValueError(f"The file mixes several countries ({', '.join(sorted(codes))}); use one file per country.")

    if override is not None:
        override = override.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", override):
            raise ValueError(f"--country must be a 2-letter code like US, got '{override}'.")

    if codes:
        code = next(iter(codes))
        if override and override != code:
            raise ValueError(f"--country {override} does not match the country in the file ({code}).")
    elif override:
        code = override
    else:
        raise ValueError("The file has no country information. Pass --country XX (e.g. --country US).")

    names = sorted({r["country_name"] for r in records if r.get("country_name")})
    return code, (names[0] if names else None)


def get_or_create_country(db: Session, code: str, name: str | None) -> tuple[Country, bool]:
    """The ONE countries row for `code`; created the first time the code is seen."""
    country = db.scalar(select(Country).where(Country.code == code))
    if country is not None:
        if name and country.name == country.code:  # still the placeholder name -> use the real one
            country.name = name
        return country, False
    country = Country(code=code, name=name or code)
    db.add(country)
    db.flush()  # gives the new row its id
    return country, True


def get_or_create_states(
    db: Session, country: Country, records: list[dict]
) -> tuple[dict[str, HolidayState], HolidayState, int]:
    """Make sure each state used by `records` has exactly ONE row in this country.

    Returns (states by abbrev, the country's "whole country" row, number of new states).
    Existing rows are reused; only missing details (name / iso) are filled in.
    """
    wanted: dict[str, dict] = {}
    for r in records:
        for s in r["states"]:
            info = wanted.setdefault(s["abbrev"], {"name": None, "iso": None})
            info["name"] = info["name"] or s.get("name")
            info["iso"] = info["iso"] or s.get("iso")

    existing: dict[str, HolidayState] = {
        s.abbrev: s
        for s in db.scalars(select(HolidayState).where(HolidayState.country_id == country.id))
    }

    created = 0
    for abbrev, info in wanted.items():
        state = existing.get(abbrev)
        if state is None:
            state = HolidayState(
                country_id=country.id, abbrev=abbrev, name=info["name"], iso=info["iso"],
                is_nationwide=False,
            )
            db.add(state)
            existing[abbrev] = state
            created += 1
        else:
            if state.name is None and info["name"]:
                state.name = info["name"]
            if state.iso is None and info["iso"]:
                state.iso = info["iso"]

    nationwide = next((s for s in existing.values() if s.is_nationwide), None)
    if nationwide is None:
        nationwide = HolidayState(
            country_id=country.id, abbrev=NATIONWIDE_ABBREV, name=NATIONWIDE_NAME,
            iso=None, is_nationwide=True,
        )
        db.add(nationwide)

    db.flush()  # gives every new state its id, needed to build the links
    return {abbrev: existing[abbrev] for abbrev in wanted}, nationwide, created


def _links_for(
    record: dict, states: dict[str, HolidayState], nationwide_state: HolidayState
) -> list[HolidayStateLink]:
    """The holiday -> state assignments for one record (each state at most once)."""
    if record["nationwide"]:
        return [HolidayStateLink(state_id=nationwide_state.id)]
    if not record["states"]:
        raise ValueError(
            f"'{record['name']}' on {record['date']} lists no states and is not nationwide, "
            "so it would have no country."
        )
    links: dict[int, HolidayStateLink] = {}
    for s in record["states"]:
        state = states[s["abbrev"]]
        if state.id not in links:
            links[state.id] = HolidayStateLink(state_id=state.id, note=s.get("note"))
    return list(links.values())


def load_country(
    db: Session, records: list[dict], country_code: str | None = None, dry_run: bool = False
) -> LoadResult:
    """Load one country's holidays (one data file).

    1. find the country (from the file, or `country_code`) and get-or-create its row
    2. get-or-create its states (+ its "whole country" row)
    3. replace that country's holidays for the years present in the file
    Safe to re-run: same result, not doubled rows. All-or-nothing: on any error nothing is saved.
    With dry_run=True everything is checked (even against the database) and then rolled back.
    """
    try:
        if not records:
            raise ValueError("The file contains no holidays.")
        code, name = resolve_country(records, country_code)
        country, country_created = get_or_create_country(db, code, name)

        # Delete this country's existing holidays for the same years (ORM delete, so the
        # cascade also removes their links; states and countries are never deleted here).
        in_country = (
            select(HolidayStateLink.holiday_id)
            .join(HolidayState, HolidayState.id == HolidayStateLink.state_id)
            .where(HolidayState.country_id == country.id)
        )
        for year in {r["date"].year for r in records}:
            stale = db.scalars(
                select(Holiday).where(
                    Holiday.id.in_(in_country),
                    Holiday.date >= dt.date(year, 1, 1),
                    Holiday.date <= dt.date(year, 12, 31),
                )
            ).all()
            for holiday in stale:
                db.delete(holiday)
        db.flush()

        states, nationwide_state, states_created = get_or_create_states(db, country, records)

        db.add_all(
            Holiday(
                name=r["name"], description=r["description"], date=r["date"],
                primary_type=r["primary_type"], types=r["types"], nationwide=r["nationwide"],
                locations=r["locations"], url=r["url"], urlid=r["urlid"],
                state_links=_links_for(r, states, nationwide_state),
            )
            for r in records
        )
        db.flush()

        result = LoadResult(
            country_code=code, country_name=country.name, country_created=country_created,
            holidays=len(records), states_used=len(states), states_created=states_created,
        )
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return result
    except Exception:
        db.rollback()
        raise
