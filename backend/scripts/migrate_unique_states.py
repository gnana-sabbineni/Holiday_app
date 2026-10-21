"""ONE-TIME migration: turn the old duplicated `holiday_states` table into
  - holiday_states       : one row per (country_code, abbrev)
  - holiday_state_links  : which holiday applies to which state

Why a script? `init_db.py` only creates MISSING tables; it never alters an existing one.

Run from the backend/ folder:
    python -m scripts.migrate_unique_states            # dry run: prints the plan, changes nothing
    python -m scripts.migrate_unique_states --apply    # does it, inside ONE transaction

BACK UP FIRST (e.g. pg_dump). The old holiday_states table is dropped and rebuilt.
The old table has no state names; they are filled in the next time you run ingest_data.
"""
import sys

from sqlalchemy import inspect, select, text

from app import models  # noqa: F401  (registers the tables on Base)
from app.database import Base, engine
from app.models import HolidayState, HolidayStateLink


def main(apply: bool) -> None:
    inspector = inspect(engine)
    if "holiday_states" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("holiday_states")}
        if "country_code" in columns:
            print("holiday_states already has the new layout. Nothing to do.")
            return

    # 1. Read the old rows. The country comes from the holiday each row belonged to.
    with engine.connect() as conn:
        old_rows = conn.execute(text(
            "SELECT hs.holiday_id, hs.abbrev, hs.note, h.country_code "
            "FROM holiday_states hs JOIN holidays h ON h.id = hs.holiday_id "
            "ORDER BY hs.id"
        )).all()
        total_old = conn.execute(text("SELECT COUNT(*) FROM holiday_states")).scalar_one()

    # 2. Work out the new layout in memory (the data is small).
    states: set[tuple[str, str]] = set()                      # (country_code, abbrev)
    links: dict[tuple[int, tuple[str, str]], str | None] = {}  # (holiday_id, state) -> note
    for holiday_id, abbrev, note, country_code in old_rows:
        key = (country_code, abbrev.strip())
        states.add(key)
        link_key = (holiday_id, key)
        if links.get(link_key) is None:       # keep the first non-empty note
            links[link_key] = note

    print(f"Old holiday_states rows : {total_old}")
    print(f"  without a matching holiday (dropped): {total_old - len(old_rows)}")
    print(f"New holiday_states rows : {len(states)}  (one per country + abbrev)")
    print(f"New holiday_state_links : {len(links)}")

    if not apply:
        print("\nDry run only. Re-run with --apply to perform the migration.")
        return

    # 3. Swap the tables inside ONE transaction: any error rolls everything back.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE holiday_states"))
        Base.metadata.create_all(conn, tables=[HolidayState.__table__, HolidayStateLink.__table__])

        conn.execute(
            HolidayState.__table__.insert(),
            [{"country_code": c, "abbrev": a} for c, a in sorted(states)],
        )
        state_ids = {
            (row.country_code, row.abbrev): row.id
            for row in conn.execute(select(HolidayState.__table__))
        }
        conn.execute(
            HolidayStateLink.__table__.insert(),
            [
                {"holiday_id": holiday_id, "state_id": state_ids[key], "note": note}
                for (holiday_id, key), note in links.items()
            ],
        )

        # 4. Sanity check before committing.
        n_states = conn.execute(text("SELECT COUNT(*) FROM holiday_states")).scalar_one()
        n_links = conn.execute(text("SELECT COUNT(*) FROM holiday_state_links")).scalar_one()
        if (n_states, n_links) != (len(states), len(links)):
            raise RuntimeError(f"Row counts do not match the plan ({n_states}, {n_links}); rolled back.")

    print(f"\nMigrated: {len(states)} states, {len(links)} links.")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv[1:])
