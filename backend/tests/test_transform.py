from app.transform import parse_record


def _raw(states, country="us"):
    return {
        "name": "Test Day",
        "country": {"id": country, "name": country.upper() + " Land"},
        "date": {"iso": "2026-06-19"},
        "primary_type": "State Holiday",
        "states": states,
    }


def test_all_means_nationwide_with_no_states():
    record = parse_record(_raw("All"))
    assert record["nationwide"] is True
    assert record["states"] == []


def test_state_list_keeps_abbrev_name_iso_and_note():
    record = parse_record(_raw([{"abbrev": "NV", "name": "Nevada", "iso": "us-nv", "exception": "partly"}]))
    assert record["nationwide"] is False
    assert record["states"] == [{"abbrev": "NV", "name": "Nevada", "iso": "us-nv", "note": "partly"}]


def test_duplicate_state_inside_one_record_is_dropped():
    record = parse_record(_raw([{"abbrev": "NV"}, {"abbrev": "NV"}, {"abbrev": "TX"}]))
    assert [s["abbrev"] for s in record["states"]] == ["NV", "TX"]


def test_abbrev_falls_back_to_iso_for_other_countries():
    record = parse_record(_raw([{"iso": "au-nsw", "name": "New South Wales"}], country="au"))
    assert record["country_code"] == "AU"
    assert record["states"][0]["abbrev"] == "NSW"


def test_state_without_abbrev_or_iso_is_skipped():
    assert parse_record(_raw([{"name": "Nowhere"}]))["states"] == []


def test_country_code_and_name_come_from_the_record():
    record = parse_record(_raw("All", country="in"))
    assert record["country_code"] == "IN"
    assert record["country_name"] == "IN Land"


def test_record_without_country_gives_none():
    raw = _raw("All")
    del raw["country"]
    record = parse_record(raw)
    assert record["country_code"] is None and record["country_name"] is None


def test_a_state_called_all_is_ignored_because_the_name_is_reserved():
    record = parse_record(_raw([{"abbrev": "ALL"}, {"abbrev": "NV"}]))
    assert [s["abbrev"] for s in record["states"]] == ["NV"]
