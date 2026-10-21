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



