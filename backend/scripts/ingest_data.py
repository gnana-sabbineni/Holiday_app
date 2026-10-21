import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.ingest import replace_holidays
from app.transform import parse_records

path = Path(sys.argv[1] if len(sys.argv) > 1 else "../data/holidays_2026.json")
records = parse_records(json.loads(path.read_text(encoding="utf-8")))

with SessionLocal() as db:
    print(f"Loaded {replace_holidays(db, records)} holidays from {path}")