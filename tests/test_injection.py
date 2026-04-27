"""Tests for Pydantic-layer rejection of malicious input."""

from __future__ import annotations

import pytest

from app import create_app
from database import db
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


def _create_staff(*, email: str) -> Staff:
    staff = Staff(
        email=email,
        full_name="Injection User",
        password_hash=Staff.hash_password("Password123!"),
        role=StaffRole.ADMIN,
        is_active=True,
    )
    db.session.add(staff)
    db.session.commit()
    return staff


def _assert_no_sql_leak(response) -> None:
    body = response.get_json()
    assert body is not None
    text = " ".join(str(value) for value in body.values()).lower()
    forbidden = ["traceback", "sqlalchemy", "sqlite", "postgres", "syntax error", "select "]
    for marker in forbidden:
        assert marker not in text


def test_sql_fragment_in_email_returns_422(app, client):
    response = client.post(
        "/auth/staff/login",
        json={"email": "admin@example.com' OR '1'='1", "password": "Password123!"},
    )

    assert response.status_code == 422
    assert "email" in response.get_json()["detail"].lower()
    _assert_no_sql_leak(response)


def test_script_tag_in_password_returns_422(app, client):
    response = client.post(
        "/auth/staff/login",
        json={"email": "admin@example.com", "password": "<script>alert(1)</script>"},
    )

    assert response.status_code == 422
    assert "password" in response.get_json()["detail"].lower()
    _assert_no_sql_leak(response)


def test_oversized_password_returns_422(app, client):
    response = client.post(
        "/auth/staff/login",
        json={"email": "admin@example.com", "password": "A" * 129},
    )

    assert response.status_code == 422
    assert "password" in response.get_json()["detail"].lower()
    _assert_no_sql_leak(response)


def test_missing_fields_return_422_with_detail(app, client):
    response = client.post("/auth/staff/login", json={"email": "admin@example.com"})

    assert response.status_code == 422
    detail = response.get_json()["detail"].lower()
    assert "password" in detail
    _assert_no_sql_leak(response)


def test_invalid_payloads_are_rejected_before_touching_db(app, client):
    with app.app_context():
        _create_staff(email="admin@example.com")
        before_count = db.session.query(Staff).count()

    response = client.post(
        "/auth/staff/login",
        json={"email": "bad' OR '1'='1", "password": "<script>boom</script>"},
    )

    assert response.status_code == 422
    _assert_no_sql_leak(response)

    with app.app_context():
        after_count = db.session.query(Staff).count()

    assert after_count == before_count
