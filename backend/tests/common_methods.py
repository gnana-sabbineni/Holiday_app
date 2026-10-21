from models import Holiday , HolidayState

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


def holidays_sample_data():
    """Sample data for the holidays table."""
    state1 = HolidayState("")