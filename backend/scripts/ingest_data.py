"""Load holiday JSON files (one or more, any country) into the database.

Run from the backend/ folder:
    python -m scripts.ingest_data ../data/holidays_us_2026.json ../data/holidays_in_2026.json

With no arguments it loads ../data/holidays_2026.json (the old default).
Each file may be a plain list of holidays or the full API response
({"response": {"holidays": [...]}}). Re-running is safe: holidays are replaced
per (country, year) and every state is stored once.
"""
import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.ingest import replace_holidays
from app.transform import parse_records


def load_raw(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):  # full API response instead of just the list
        inner = data.get("response")
        data = (inner if isinstance(inner, dict) else data).get("holidays")
    if not isinstance(data, list):
        raise SystemExit(f"{path}: expected a list of holidays (or a response containing 'holidays')")
    return data


paths = [Path(p) for p in sys.argv[1:]] or [Path("../data/holidays_2026.json")]

with SessionLocal() as db:
    for path in paths:
        records = parse_records(load_raw(path))
        print(f"Loaded {replace_holidays(db, records)} holidays from {path}")
