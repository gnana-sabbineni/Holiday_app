import datetime as dt
from typing import Any

NATIONWIDE_ABBREV = "ALL"  # reserved: the per-country "whole country" row (see models.py)


def _parse_state(raw_state: dict[str, Any]) -> dict[str, Any] | None:
    """One raw state/province entry -> {"abbrev", "name", "iso", "note"}, or None if unusable.

    Calendarific gives US states as {"abbrev": "NV", "name": "Nevada", "iso": "us-nv", ...}.
    Some other countries may omit `abbrev`; the part after the dash in `iso`
    ("au-nsw" -> "NSW") is used instead, so the same code works for any country.
    """
    iso = raw_state.get("iso")
    abbrev = (raw_state.get("abbrev") or "").strip()
    if not abbrev and iso:
        abbrev = iso.rsplit("-", 1)[-1].strip().upper()
    if not abbrev or abbrev.upper() == NATIONWIDE_ABBREV:
        return None
    return {
        "abbrev": abbrev,
        "name": raw_state.get("name"),
        "iso": iso,
        "note": raw_state.get("exception"),
    }


def parse_record(raw: dict[str, Any]) -> dict[str, Any]:
    """One raw Calendarific record -> flat dict.

    Quirk: `states` is EITHER the string "All" OR a list of dicts. Only the string
    means "observed everywhere". A list can still be long ("All except MA, MS..."
    arrives as 45 listed states).

    The country comes from the record itself ({"country": {"id": "us", "name": "United States"}});
    it is None when the record has no country information (the loader then needs --country).
    Each state is returned once (duplicates inside one record are dropped).
    """
    raw_states = raw.get("states")
    nationwide = raw_states == "All"

    states: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(raw_states, list):
        for s in raw_states:
            parsed = _parse_state(s)
            if parsed and parsed["abbrev"] not in seen:
                seen.add(parsed["abbrev"])
                states.append(parsed)

    country = raw.get("country") or {}
    country_code = (country.get("id") or "").strip().upper() or None

    return {
        "name": raw["name"],
        "description": raw.get("description"),
        "country_code": country_code,
        "country_name": country.get("name"),
        "date": dt.date.fromisoformat(raw["date"]["iso"][:10]),
        "primary_type": raw["primary_type"],
        "types": list(raw.get("type", [])),
        "nationwide": nationwide,
        "locations": raw.get("locations"),
        "url": raw.get("canonical_url"),
        "urlid": raw.get("urlid"),
        "states": states,
    }


def parse_records(raws: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [parse_record(r) for r in raws]
