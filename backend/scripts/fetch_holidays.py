"""Download one country's holidays from the holiday API into data/holidays_<CC>_<year>.json.

Run from the backend/ folder:
    python -m scripts.fetch_holidays IN 2026

Then load that file into the database:
    python -m scripts.ingest_data ../data/holidays_IN_2026.json --dry-run
    python -m scripts.ingest_data ../data/holidays_IN_2026.json

Needs API_KEY and BASE_URL in backend/.env.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()  # reads backend/.env

DATA_DIR = Path(__file__).resolve().parents[2] / "data"   # <repo>/data, next to backend/


def call_api(country: str, year: int) -> list[dict]:
    api_key = os.getenv("API_KEY")
    base_url = os.getenv("BASE_URL")
    if not api_key or not base_url:
        raise RuntimeError("Add API_KEY and BASE_URL to backend/.env")
    response = requests.get(
        f"{base_url.rstrip('/')}/holidays",
        params={"api_key": api_key, "country": country, "year": year},
        timeout=10,
    )
    response.raise_for_status()
    body = response.json()
    try:
        return body["response"]["holidays"]
    except (KeyError, TypeError):
        raise RuntimeError("Unexpected reply from the API (no response.holidays in it)") from None


def save_to_file(data: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def country_code(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z]{2}", value):
        raise argparse.ArgumentTypeError("use a 2-letter country code like IN")
    return value.upper()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download one country's holidays into the data folder.")
    parser.add_argument("country", type=country_code, help="2-letter country code, e.g. IN")
    parser.add_argument("year", type=int, help="year, e.g. 2026")
    args = parser.parse_args()

    try:
        holidays = call_api(args.country, args.year)
    except requests.HTTPError as error:
        # not str(error): it contains the full URL, and the URL contains your API key
        sys.exit(f"The API refused the request: HTTP {error.response.status_code}")
    except requests.RequestException as error:
        sys.exit(f"Could not reach the API ({type(error).__name__}). Check BASE_URL and your connection.")
    except RuntimeError as error:
        sys.exit(str(error))

    if not holidays:
        sys.exit(f"The API returned no holidays for {args.country} {args.year}; nothing saved.")

    path = DATA_DIR / f"holidays_{args.country}_{args.year}.json"
    save_to_file(holidays, path)
    print(f"Saved {len(holidays)} holidays to {path}")


if __name__ == "__main__":
    main()