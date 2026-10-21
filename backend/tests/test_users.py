import datetime as dt

import pytest

from app.security import create_access_token

from .common_methods import USER,REGISTER_URL,ME_URL,register,login


# ---------- register ----------

def test_register_success(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == USER["email"]
    assert body["username"] == USER["username"]
    assert "password" not in body             # response_model must not leak secrets
    assert "password_hash" not in body


def test_register_duplicate_email_returns_409(client):
    register(client)
    response = register(client, username="someone_else")   # only the email collides
    assert response.status_code == 409


def test_register_duplicate_username_returns_409(client):
    register(client)
    response = register(client, email="other@example.com")  # only the username collides
    assert response.status_code == 409


@pytest.mark.parametrize("missing_field", ["email", "username", "password"])
def test_register_missing_field_returns_422(client, missing_field):
    payload = {k: v for k, v in USER.items() if k != missing_field}
    response = client.post(REGISTER_URL, json=payload)      # raw post: we need a field OMITTED
    assert response.status_code == 422                      # Pydantic validation error


@pytest.mark.parametrize(
    "field, value, expected_status",
    [
        pytest.param("username", "ab",           422, id="username-2-chars-too-short"),
        pytest.param("username", "abc",          201, id="username-3-chars-minimum"),
        pytest.param("username", "a" * 50,       201, id="username-50-chars-maximum"),
        pytest.param("username", "a" * 51,       422, id="username-51-chars-too-long"),
        pytest.param("email",    "not-an-email", 422, id="email-invalid-format"),
        pytest.param("password", "1234567",      422, id="password-7-chars-too-short"),
        pytest.param("password", "12345678",     201, id="password-8-chars-minimum"),
        pytest.param("password", "a" * 72,       201, id="password-72-chars-maximum"),
        pytest.param("password", "a" * 73,       422, id="password-73-chars-too-long"),
    ],
)
def test_register_field_rules(client, field, value, expected_status):
    response = register(client, **{field: value})   # {"username": "ab"} becomes username="ab"
    assert response.status_code == expected_status


# ---------- login ----------

def test_login_success_returns_token(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_wrong_password_returns_401(client):
    register(client)
    assert login(client, password="wrong-password").status_code == 401


def test_login_unknown_email_gives_same_error_as_wrong_password(client):
    register(client)
    wrong_password = login(client, password="wrong-password")
    unknown_email = login(client, email="nobody@example.com")
    assert unknown_email.status_code == 401
    assert unknown_email.json() == wrong_password.json()   # don't reveal which emails exist


# ---------- /user/me (a protected route) ----------

def test_me_without_token_returns_401(client):
    assert client.get(ME_URL).status_code == 401


def test_me_with_garbage_token_returns_401(client):
    response = client.get(ME_URL, headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_me_with_expired_token_returns_401(client):
    register(client)
    expired = create_access_token(
        {"sub": USER["email"]}, expires_delta=dt.timedelta(minutes=-1)   # already expired
    )
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


def test_me_with_valid_token_returns_current_user(client):
    register(client)
    token = login(client).json()["access_token"]
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == USER["email"]