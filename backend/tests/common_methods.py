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


def _record(name, country, date, states, nationwide=False, country_name=None):
    """A holiday in the shape app.transform.parse_record returns (what load_country takes)."""
    return {
        "name": name, "description": None,
        "country_code": country, "country_name": country_name,
        "date": dt.date.fromisoformat(date), "primary_type": "State Holiday",
        "types": ["Local holiday"], "nationwide": nationwide, "locations": None,
        "url": None, "urlid": None,
        "states": [{"abbrev": a, "name": None, "iso": None, "note": None} for a in states],
    }


def us_records():
    """US file: NV is in TWO holidays; one holiday is nationwide."""
    c = dict(country="US", country_name="United States")
    return [
        _record("Juneteenth Day", date="2026-06-19", states=["NV", "TX"], **c),
        _record("Nevada Day", date="2026-10-30", states=["NV"], **c),
        _record("Independence Day", date="2026-07-04", states=[], nationwide=True, **c),
        _record("Washington Day", date="2026-02-16", states=["WA"], **c),
    ]


def au_records():
    """AU file: its "WA" (Western Australia) must not clash with the US "WA"."""
    c = dict(country="AU", country_name="Australia")
    return [
        _record("Western Australia Day", date="2026-06-01", states=["WA"], **c),
        _record("Australia Day", date="2026-01-26", states=[], nationwide=True, **c),
    ]


def load_sample_data(db):
    """Load both sample countries the way the ingest script does: one country per call."""
    from app.ingest import load_country

    load_country(db, us_records())
    load_country(db, au_records())
