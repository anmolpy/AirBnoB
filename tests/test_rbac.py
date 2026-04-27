"""Tests for role-based access control boundaries."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from flask_jwt_extended import create_access_token

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


def _create_staff(*, email: str, role: StaffRole) -> Staff:
    staff = Staff(
        email=email,
        full_name="RBAC User",
        password_hash=Staff.hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    db.session.add(staff)
    db.session.commit()
    return staff


def _create_guest() -> dict[str, object]:
    guest = Guest(
        token="123e4567-e89b-42d3-a456-426614174099",
        room_id=202,
        check_in=date.today() - timedelta(days=1),
        check_out=date.today() + timedelta(days=1),
        full_name="Guest Name",
        email="guest@example.com",
    )
    db.session.add(guest)
    db.session.commit()
    return {"id": guest.id, "token": guest.token}


def _login_staff(client, *, email: str) -> None:
    response = client.post(
        "/auth/staff/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200


def _set_access_cookie(client, token: str) -> None:
    client.set_cookie("access_token_cookie", token)


def test_front_desk_jwt_on_admin_route_returns_403(app, client):
    with app.app_context():
        _create_staff(email="desk@example.com", role=StaffRole.FRONT_DESK)

    _login_staff(client, email="desk@example.com")
    response = client.get("/admin/health")

    assert response.status_code == 403
    assert response.get_json() == {"detail": "Insufficient permissions."}


def test_guest_jwt_without_role_on_staff_route_returns_403(app, client):
    with app.app_context():
        guest = _create_guest()

    verify_response = client.post("/auth/guest/verify", json={"token": guest["token"]})
    assert verify_response.status_code == 200

    response = client.get("/staff/health")

    assert response.status_code == 403
    assert response.get_json() == {"detail": "Insufficient permissions."}


def test_admin_jwt_on_staff_route_returns_200(app, client):
    with app.app_context():
        _create_staff(email="admin@example.com", role=StaffRole.ADMIN)

    _login_staff(client, email="admin@example.com")
    response = client.get("/staff/health")

    assert response.status_code == 200
    assert response.get_json() == {"message": "staff ok"}


def test_missing_auth_credentials_returns_401(app, client):
    response = client.get("/staff/health")

    assert response.status_code == 401
    assert response.get_json() == {"detail": "Authentication required."}


def test_token_with_forged_role_claim_returns_403(app, client):
    with app.app_context():
        staff = _create_staff(email="desk@example.com", role=StaffRole.FRONT_DESK)
        forged_token = create_access_token(
            identity=str(staff.id),
            additional_claims={"role": "super_admin", "email": staff.email},
        )

    _set_access_cookie(client, forged_token)
    response = client.get("/admin/health")

    assert response.status_code == 403
    assert response.get_json() == {"detail": "Insufficient permissions."}
