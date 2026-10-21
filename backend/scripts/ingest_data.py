"""Load holiday JSON files into the database: one file per country, any country.

Run from the backend/ folder:
    python -m scripts.ingest_data ../data/holidays_2026.json                 # one file
    python -m scripts.ingest_data ../data/us.json ../data/in.json            # several files
    python -m scripts.ingest_data ../data/us.json --country US               # static country code
    python -m scripts.ingest_data ../data/*.json --dry-run                   # check only, saves nothing

The country is read from the records themselves ({"country": {"id": "us", "name": ...}}).
--country is only needed when a file carries no country, and it must match the file if it does.
Each file is its own all-or-nothing transaction: a bad file changes nothing and the others still load.
Re-running is safe: a country's holidays are replaced per year, countries and states are stored once.
With no file given it loads ../data/holidays_2026.json (the old default).
"""
import argparse
import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.ingest import load_country
from app.transform import parse_records


def load_raw(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):  # full API response instead of just the list
        inner = data.get("response")
        data = (inner if isinstance(inner, dict) else data).get("holidays")
    if not isinstance(data, list):
        raise ValueError("expected a list of holidays (or a response containing 'holidays')")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Load holiday data files (one file per country).")
    parser.add_argument("files", nargs="*", type=Path, help="JSON file(s) to load")
    parser.add_argument("--country", help="2-letter country code, only for a single file")
    parser.add_argument("--dry-run", action="store_true", help="validate everything, save nothing")
    args = parser.parse_args()

    paths = args.files or [Path("../data/holidays_2026.json")]
    if args.country and len(paths) != 1:
        parser.error("--country can only be used with exactly one file")

    failures = 0
    for path in paths:
        with SessionLocal() as db:
            try:
                records = parse_records(load_raw(path))
                result = load_country(db, records, country_code=args.country, dry_run=args.dry_run)
            except (ValueError, KeyError, OSError) as error:  # JSON errors are ValueErrors
                reason = f"a record is missing the field {error}" if isinstance(error, KeyError) else error
                print(f"{path}: FAILED, nothing saved - {reason}")
                failures += 1
                continue
        print(
            f"{path}: {result.country_code} ({result.country_name}"
            f"{', new country' if result.country_created else ''}) - "
            f"{result.holidays} holidays, {result.states_used} states ({result.states_created} new)"
            f"{'  [dry run, nothing saved]' if args.dry_run else ''}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
