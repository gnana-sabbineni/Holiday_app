import datetime as dt

import pytest

HOLIDAYS_URL = "/holidays"
TYPES_URL = f"{HOLIDAYS_URL}/types"
HOLIDAY_URL = f"{HOLIDAYS_URL}/1"

@pytest.mark.parametrize("route", [HOLIDAYS_URL, TYPES_URL, HOLIDAY_URL])
def test_holidays_routes_require_token(client, route):
    assert client.get(route).status_code == 401


@pytest.mark.parametrize(
    "route, expected_status",
    [
        (HOLIDAYS_URL, 200),
        (TYPES_URL, 200),
        (HOLIDAY_URL, 404),     # authenticated, but no holiday with id 1 exists yet
    ],
)
def test_holidays_routes_accept_valid_token(client, auth_headers, route, expected_status):
    assert client.get(route, headers=auth_headers).status_code == expected_status

def test_holidays_empty_db_returns_empty_page(client, auth_headers):
    response = client.get(HOLIDAYS_URL , headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0





# ---- filters and output once holidays map to states and states to countries ----

from .common_methods import load_sample_data


def _names(client, auth_headers, **params):
    response = client.get(HOLIDAYS_URL, params=params, headers=auth_headers)
    assert response.status_code == 200
    return {h["name"] for h in response.json()["items"]}


def test_state_filter_includes_nationwide_holidays_of_that_country(client, auth_headers, db_session):
    load_sample_data(db_session)

    names = _names(client, auth_headers, state="NV", country="US")
    assert names == {"Juneteenth Day", "Nevada Day", "Independence Day"}   # 2 linked + 1 nationwide


def test_state_filter_skips_nationwide_holidays_of_countries_without_that_state(client, auth_headers, db_session):
    load_sample_data(db_session)

    # no country given: Australia has no "NV", so "Australia Day" must not appear
    assert _names(client, auth_headers, state="NV") == {"Juneteenth Day", "Nevada Day", "Independence Day"}


def test_country_filter_separates_equal_abbreviations(client, auth_headers, db_session):
    load_sample_data(db_session)

    assert _names(client, auth_headers, state="WA", country="AU") == {"Western Australia Day", "Australia Day"}
    assert _names(client, auth_headers, state="WA", country="US") == {"Washington Day", "Independence Day"}


def test_state_filter_without_country_matches_every_country_that_has_it(client, auth_headers, db_session):
    load_sample_data(db_session)

    assert _names(client, auth_headers, state="WA") == {
        "Washington Day", "Western Australia Day", "Independence Day", "Australia Day",
    }


def test_country_filter_alone(client, auth_headers, db_session):
    load_sample_data(db_session)

    assert _names(client, auth_headers, country="AU") == {"Western Australia Day", "Australia Day"}


def test_output_shows_country_code_and_states(client, auth_headers, db_session):
    load_sample_data(db_session)

    items = {h["name"]: h for h in client.get(HOLIDAYS_URL, headers=auth_headers).json()["items"]}
    assert items["Juneteenth Day"]["country_code"] == "US"
    assert items["Juneteenth Day"]["states"] == ["NV", "TX"]
    assert items["Independence Day"]["states"] == [] and items["Independence Day"]["nationwide"] is True
    assert items["Australia Day"]["country_code"] == "AU"
