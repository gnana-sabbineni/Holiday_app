"""ONE-TIME migration to the countries layout:
  countries            : id, name, code            (one row per country)
  holiday_states       : one row per (country, abbrev) + one "ALL" row per country
  holiday_state_links  : which holiday applies to which state
  holidays             : the country_code column is removed (country comes via states)

Works from either earlier layout:
  - original      : holiday_states(holiday_id, abbrev, note) and holidays.country_code
  - first revision: holiday_states(country_code, abbrev, ...) + holiday_state_links

Why a script? `init_db.py` only creates MISSING tables; it never alters an existing one.

Run from the backend/ folder:
    python -m scripts.migrate_unique_states                    # dry run: prints the plan, changes nothing
    python -m scripts.migrate_unique_states --apply            # does it, inside ONE transaction
    python -m scripts.migrate_unique_states --apply --drop-orphans

BACK UP FIRST (e.g. pg_dump). Old state rows are dropped and rebuilt.
Country names are set to the code (e.g. "US") and state names are left empty:
run ingest_data.py on your data files afterwards and it fills in the real names.
"Orphans" are holidays that are not nationwide and have no state, so they would have no
country; --drop-orphans deletes them (ingest_data.py re-creates real holidays anyway).
"""
import sys

from sqlalchemy import bindparam, inspect, select, text

from app import models  # noqa: F401  (registers the tables on Base)
from app.database import Base, engine
from app.models import NATIONWIDE_ABBREV, NATIONWIDE_NAME, Country, HolidayState, HolidayStateLink


def detect_layout() -> str | None:
    """'original', 'first-revision', 'done', or None when there is nothing to migrate."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "holidays" not in tables or "holiday_states" not in tables:
        return None
    state_cols = {c["name"] for c in inspector.get_columns("holiday_states")}
    if "country_id" in state_cols:
        return "done"
    if "holiday_id" in state_cols:
        return "original"
    if "country_code" in state_cols:
        return "first-revision"
    raise RuntimeError(f"holiday_states has unexpected columns: {sorted(state_cols)}")


def main(apply: bool, drop_orphans: bool) -> None:
    layout = detect_layout()
    if layout is None:
        print("No old holiday_states table found. Run scripts/init_db.py to create the new tables.")
        return
    if layout == "done":
        print("holiday_states already has the new layout. Nothing to do.")
        return
    print(f"Detected the '{layout}' layout.")

    # 1. Read the old data.
    with engine.connect() as conn:
        holidays = conn.execute(text("SELECT id, country_code, nationwide FROM holidays")).all()
        if layout == "original":
            old_links = conn.execute(text(
                "SELECT hs.holiday_id, h.country_code, hs.abbrev, hs.note, NULL AS name, NULL AS iso "
                "FROM holiday_states hs JOIN holidays h ON h.id = hs.holiday_id ORDER BY hs.id"
            )).all()
        else:
            old_links = conn.execute(text(
                "SELECT l.holiday_id, s.country_code, s.abbrev, l.note, s.name, s.iso "
                "FROM holiday_state_links l JOIN holiday_states s ON s.id = l.state_id ORDER BY s.id"
            )).all()

    # 2. Work out the new layout in memory (the data is small).
    country_codes = sorted({code for _, code, _ in holidays})
    states: dict[tuple[str, str], dict] = {}   # (country, abbrev) -> details
    for code in country_codes:                 # every country gets its "whole country" row
        states[(code, NATIONWIDE_ABBREV)] = {"name": NATIONWIDE_NAME, "iso": None, "is_nationwide": True}
    links: dict[tuple[int, str, str], str | None] = {}   # (holiday_id, country, abbrev) -> note
    for holiday_id, code, abbrev, note, name, iso in old_links:
        abbrev = abbrev.strip()
        states.setdefault((code, abbrev), {"name": name, "iso": iso, "is_nationwide": False})
        if links.get((holiday_id, code, abbrev)) is None:   # keep the first non-empty note
            links[(holiday_id, code, abbrev)] = note
    for holiday_id, code, nationwide in holidays:
        if nationwide:
            links[(holiday_id, code, NATIONWIDE_ABBREV)] = None

    linked_ids = {holiday_id for holiday_id, _, _ in links}
    orphans = sorted(hid for hid, _, nationwide in holidays if not nationwide and hid not in linked_ids)

    real_states = sum(1 for s in states.values() if not s["is_nationwide"])
    print(f"Countries to create     : {len(country_codes)} ({', '.join(country_codes)})")
    print(f"States to create        : {real_states} real + {len(country_codes)} 'ALL' rows")
    print(f"Links to create         : {len(links)}")
    print(f"Holidays without a state and not nationwide (orphans): {len(orphans)}")
    if orphans:
        print(f"  ids: {orphans[:20]}{' ...' if len(orphans) > 20 else ''}")

    if not apply:
        print("\nDry run only. Re-run with --apply to perform the migration.")
        return
    if orphans and not drop_orphans:
        print("\nStopped: orphan holidays would have no country. Fix them, or re-run with --drop-orphans.")
        sys.exit(1)

    # 3. Swap the tables inside ONE transaction: any error rolls everything back.
    with engine.begin() as conn:
        if orphans:
            conn.execute(
                text("DELETE FROM holidays WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
                {"ids": orphans},
            )
        conn.execute(text("DROP TABLE IF EXISTS holiday_state_links"))
        conn.execute(text("DROP TABLE holiday_states"))
        conn.execute(text("ALTER TABLE holidays DROP COLUMN country_code"))
        Base.metadata.create_all(
            conn, tables=[Country.__table__, HolidayState.__table__, HolidayStateLink.__table__]
        )

        conn.execute(Country.__table__.insert(), [{"code": c, "name": c} for c in country_codes])
        country_ids = {row.code: row.id for row in conn.execute(select(Country.__table__))}

        conn.execute(
            HolidayState.__table__.insert(),
            [
                {"country_id": country_ids[code], "abbrev": abbrev, "name": info["name"],
                 "iso": info["iso"], "is_nationwide": info["is_nationwide"]}
                for (code, abbrev), info in sorted(states.items())
            ],
        )
        state_ids = {
            (row.country_id, row.abbrev): row.id
            for row in conn.execute(select(HolidayState.__table__))
        }
        conn.execute(
            HolidayStateLink.__table__.insert(),
            [
                {"holiday_id": holiday_id, "state_id": state_ids[(country_ids[code], abbrev)], "note": note}
                for (holiday_id, code, abbrev), note in links.items()
            ],
        )

        # 4. Sanity check before committing.
        counts = tuple(
            conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            for table in ("countries", "holiday_states", "holiday_state_links")
        )
        if counts != (len(country_codes), len(states), len(links)):
            raise RuntimeError(f"Row counts {counts} do not match the plan; rolled back.")

    print(f"\nMigrated: {len(country_codes)} countries, {len(states)} states, {len(links)} links.")
    print("Next: run scripts/ingest_data.py on your data files to fill in the real names.")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(apply="--apply" in args, drop_orphans="--drop-orphans" in args)
