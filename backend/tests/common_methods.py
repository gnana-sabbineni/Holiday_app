import datetime as dt

REGISTER_URL = "/user/register"
LOGIN_URL = "/user/login"
ME_URL = "/user/me"

USER = {"email": "asha@example.com", "username": "asha", "password": "S3cret-pass!"}


def register(client, email=USER["email"], username=USER["username"], password=USER["password"]):
    """Register a user. Every field defaults to the standard valid USER."""
    return client.post(
        REGISTER_URL,
        json={"email": email, "username": username, "password": password},
    )


def login(client, email=USER["email"], password=USER["password"]):
    # Your login uses OAuth2PasswordRequestForm: FORM data (data=), not JSON,
    # and the field is called "username" even though we put the email in it.
    return client.post(LOGIN_URL, data={"username": email, "password": password})


def _record(name, country, date, states, nationwide=False):
    """A holiday in the shape app.transform.parse_record returns (what replace_holidays takes)."""
    return {
        "name": name, "description": None, "country_code": country,
        "date": dt.date.fromisoformat(date), "primary_type": "State Holiday",
        "types": ["Local holiday"], "nationwide": nationwide, "locations": None,
        "url": None, "urlid": None,
        "states": [{"abbrev": a, "name": None, "iso": None, "note": None} for a in states],
    }


def holidays_sample_data():
    """Sample records: NV appears in TWO holidays, and "WA" exists in two countries."""
    return [
        _record("Juneteenth Day", "US", "2026-06-19", ["NV", "TX"]),
        _record("Nevada Day", "US", "2026-10-30", ["NV"]),
        _record("Independence Day", "US", "2026-07-04", [], nationwide=True),
        _record("Western Australia Day", "AU", "2026-06-01", ["WA"]),
        _record("Washington Day", "US", "2026-02-16", ["WA"]),
    ]
