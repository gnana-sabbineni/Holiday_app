import datetime as dt
from typing import Any


def parse_record(raw: dict[str, Any]) -> dict[str, Any]:
    """One raw Calendarific record -> flat dict.

    Quirk: `states` is EITHER the string "All" OR a list of dicts. Only the string
    means "observed everywhere". A list can still be long ("All except MA, MS..."
    arrives as 45 listed states).
    """
    raw_states = raw.get("states")
    nationwide = raw_states == "All"

    states = []
    if isinstance(raw_states, list):
        for s in raw_states:
            if s.get("abbrev"):
                states.append({"abbrev": s["abbrev"], "note": s.get("exception")})

    return {
        "name": raw["name"],
        "description": raw.get("description"),
        "country_code": raw["country"]["id"].upper(),
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