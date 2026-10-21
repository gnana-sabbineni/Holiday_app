import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Holiday, HolidayState


def replace_holidays(db: Session, records: list[dict]) -> int:
    """Delete existing rows for the same (country, year), then insert.
    Safe to re-run: you get the same result, not doubled rows."""
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
            db.delete(holiday)  # ORM delete, so cascade also removes child rows
    db.flush()

    db.add_all(
        Holiday(
            name=r["name"], description=r["description"], country_code=r["country_code"],
            date=r["date"], primary_type=r["primary_type"], types=r["types"],
            nationwide=r["nationwide"], locations=r["locations"], url=r["url"], urlid=r["urlid"],
            state_rows=[HolidayState(abbrev=s["abbrev"], note=s["note"]) for s in r["states"]],
        )
        for r in records
    )
    db.commit()
    return len(records)