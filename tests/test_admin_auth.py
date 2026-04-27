"""Tests for admin authentication flows and guest token verification."""

from __future__ import annotations

from datetime import date, timedelta
from http.cookies import SimpleCookie

import pytest
from flask_jwt_extended import create_access_token, decode_token

from app import create_app
from database import db
from models.guest import Guest
from models.staff import Staff, StaffRole


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr(Staff, "hash_password", staticmethod(lambda plain: f"stub-hash::{plain}"))
    monkeypatch.setattr(
        Staff,
        "verify_password",
        lambda self, plain: self.password_hash == f"stub-hash::{plain}",
    )
    monkeypatch.setattr(Staff, "needs_rehash", lambda self: False)

    app = create_app("testing")
    app.config["TESTING"] = True

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _create_staff(*, email: str, password: str = "Password123!", role: StaffRole = StaffRole.ADMIN) -> Staff:
    staff = Staff(
        email=email,
        full_name="Test Staff",
        password_hash=Staff.hash_password(password),
        role=role,
        is_active=True,
    )
    db.session.add(staff)
    db.session.commit()
    return staff


def _create_guest(*, token: str, check_in: date, check_out: date) -> dict[str, object]:
    guest = Guest(
        token=token,
        room_id=101,
        check_in=check_in,
        check_out=check_out,
        full_name="Guest Name",
        email="guest@example.com",
    )
    db.session.add(guest)
    db.session.commit()
    return {
        "id": guest.id,
        "token": guest.token,
        "room_id": guest.room_id,
        "check_in": guest.check_in,
        "check_out": guest.check_out,
    }


def _cookie_value(response, key: str) -> str | None:
    cookie = SimpleCookie()
    for header in response.headers.getlist("Set-Cookie"):
        cookie.load(header)
    morsel = cookie.get(key)
    return morsel.value if morsel is not None else None


def _set_access_cookie(client, token: str) -> None:
    client.set_cookie("access_token_cookie", token)


def test_login_happy_path_returns_200_and_cookie(app, client):
    with app.app_context():
        _create_staff(email="admin@example.com")

    response = client.post(
        "/auth/staff/login",
        json={"email": "admin@example.com", "password": "Password123!"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Login successful.",
        "role": "admin",
        "full_name": "Test Staff",
    }
    assert _cookie_value(response, "access_token_cookie")


def test_login_wrong_password_returns_401_without_field_detail(app, client):
    with app.app_context():
        _create_staff(email="admin@example.com")

    response = client.post(
        "/auth/staff/login",
        json={"email": "admin@example.com", "password": "WrongPassword123!"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"detail": "Invalid credentials."}
    body = response.get_json()["detail"].lower()
    assert "email" not in body
    assert "password" not in body


def test_login_invalid_email_format_returns_422(app, client):
    response = client.post(
        "/auth/staff/login",
        json={"email": "not-an-email", "password": "Password123!"},
    )

    assert response.status_code == 422
    assert "email" in response.get_json()["detail"].lower()


def test_login_rate_limit_11th_request_in_one_minute_returns_429(app, client):
    with app.app_context():
        _create_staff(email="admin@example.com")

    for _ in range(10):
        response = client.post(
            "/auth/staff/login",
            json={"email": "admin@example.com", "password": "WrongPassword123!"},
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/staff/login",
        json={"email": "admin@example.com", "password": "WrongPassword123!"},
    )

    assert response.status_code == 429
    assert response.get_json() == {"detail": "Too many requests. Try again later."}


def test_expired_jwt_returns_401_on_me(app, client):
    with app.app_context():
        staff = _create_staff(email="admin@example.com")
        expired_token = create_access_token(
            identity=str(staff.id),
            additional_claims={"role": staff.role, "email": staff.email},
            expires_delta=timedelta(seconds=-1),
        )

    _set_access_cookie(client, expired_token)
    response = client.get("/auth/staff/me")

    assert response.status_code == 401
    assert response.get_json() == {"detail": "Token has expired."}


def test_guest_verify_issues_session_without_role_claim(app, client):
    with app.app_context():
        guest = _create_guest(
            token="123e4567-e89b-42d3-a456-426614174000",
            check_in=date.today() - timedelta(days=1),
            check_out=date.today() + timedelta(days=1),
        )

    response = client.post("/auth/guest/verify", json={"token": guest["token"]})

    assert response.status_code == 200
    assert response.get_json() == {
        "room_id": 101,
        "check_in": guest["check_in"].isoformat(),
        "check_out": guest["check_out"].isoformat(),
        "message": "Token verified.",
    }

    with app.app_context():
        claims = decode_token(_cookie_value(response, "access_token_cookie"))

    assert claims["sub"] == str(guest["id"])
    assert claims["token_type"] == "guest"
    assert claims["room_id"] == 101
    assert "role" not in claims


def test_guest_verify_rejects_expired_token(app, client):
    with app.app_context():
        guest = _create_guest(
            token="123e4567-e89b-42d3-a456-426614174001",
            check_in=date.today() - timedelta(days=4),
            check_out=date.today() - timedelta(days=1),
        )

    response = client.post("/auth/guest/verify", json={"token": guest["token"]})

    assert response.status_code == 401
    assert response.get_json() == {"detail": "Invalid or expired token."}
