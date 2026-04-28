"""Tests for admin, staff, and guest route blueprints."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import create_app
from database import db
from models.guest import Guest
from models.reservation import Reservation, ReservationStatus
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


def test_public_health_endpoint_returns_200(app, client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"message": "ok"}


def _create_staff(*, email: str, role: StaffRole) -> Staff:
    staff = Staff(
        email=email,
        full_name="Route User",
        password_hash=Staff.hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    db.session.add(staff)
    db.session.commit()
    return staff


def _login_staff(client, *, email: str):
    response = client.post(
        "/auth/staff/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200


def test_admin_can_create_and_list_staff(app, client):
    with app.app_context():
        _create_staff(email="admin@example.com", role=StaffRole.ADMIN)

    _login_staff(client, email="admin@example.com")

    create_response = client.post(
        "/admin/staff",
        json={
            "email": "desk@example.com",
            "full_name": "Front Desk",
            "password": "Welcome123!",
            "role": "front_desk",
        },
    )
    assert create_response.status_code == 201
    assert create_response.get_json()["email"] == "desk@example.com"
    assert "password_hash" not in create_response.get_json()

    list_response = client.get("/admin/staff")
    assert list_response.status_code == 200
    assert list_response.get_json()["total"] == 2


def test_staff_can_create_check_in_and_check_out_reservation(app, client):
    with app.app_context():
        _create_staff(email="desk@example.com", role=StaffRole.FRONT_DESK)

    _login_staff(client, email="desk@example.com")

    create_response = client.post(
        "/staff/reservations",
        json={
            "room_id": 301,
            "check_in": date.today().isoformat(),
            "check_out": (date.today() + timedelta(days=2)).isoformat(),
            "guest_name": "Taylor Guest",
            "guest_email": "taylor@example.com",
        },
    )
    assert create_response.status_code == 201
    reservation_id = create_response.get_json()["id"]

    check_in_response = client.post(
        "/staff/checkin",
        json={"reservation_id": reservation_id},
    )
    assert check_in_response.status_code == 200
    assert check_in_response.get_json()["reservation_id"] == reservation_id

    check_out_response = client.post(
        "/staff/checkout",
        json={"reservation_id": reservation_id},
    )
    assert check_out_response.status_code == 200
    assert check_out_response.get_json()["reservation_id"] == reservation_id

    with app.app_context():
        reservation = db.session.get(Reservation, reservation_id)
        assert reservation is not None
        guest = db.session.get(Guest, reservation.guest_id)
        assert guest is not None
        assert reservation.status == ReservationStatus.CHECKED_OUT
        assert guest.full_name is None
        assert guest.email is None


def test_guest_can_view_own_session_and_reservation(app, client):
    with app.app_context():
        guest = Guest(
            token="123e4567-e89b-42d3-a456-426614174111",
            room_id=404,
            check_in=date.today() - timedelta(days=1),
            check_out=date.today() + timedelta(days=2),
            full_name="Guest Session",
            email="guestsession@example.com",
        )
        db.session.add(guest)
        db.session.flush()

        reservation = Reservation(
            guest_id=guest.id,
            room_id=guest.room_id,
            check_in=guest.check_in,
            check_out=guest.check_out,
            status=ReservationStatus.ACTIVE,
        )
        db.session.add(reservation)
        db.session.commit()

    verify_response = client.post(
        "/auth/guest/verify",
        json={"token": "123e4567-e89b-42d3-a456-426614174111"},
    )
    assert verify_response.status_code == 200

    me_response = client.get("/guest/me")
    assert me_response.status_code == 200
    assert me_response.get_json()["room_id"] == 404

    reservation_response = client.get("/guest/reservation")
    assert reservation_response.status_code == 200
    assert reservation_response.get_json()["room_id"] == 404


def test_guest_can_book_room_publicly(app, client):
    response = client.post(
        "/guest/book",
        json={
            "room_id": 808,
            "check_in": (date.today() + timedelta(days=1)).isoformat(),
            "check_out": (date.today() + timedelta(days=4)).isoformat(),
            "guest_name": "Guest Booker",
            "guest_email": "guest.booker@example.com",
        },
    )

    assert response.status_code == 201

    body = response.get_json()
    assert body["message"] == "Reservation booked successfully."
    assert body["guest_token"]
    assert body["reservation"]["room_id"] == 808
    assert body["reservation"]["status"] == "pending"

    with app.app_context():
        guest = db.session.scalar(db.select(Guest).where(Guest.token == body["guest_token"]))
        assert guest is not None
        assert guest.full_name == "Guest Booker"


def test_availability_reports_conflicts(app, client):
    with app.app_context():
        _create_staff(email="admin@example.com", role=StaffRole.ADMIN)
        guest = Guest(
            token="123e4567-e89b-42d3-a456-426614174112",
            room_id=505,
            check_in=date.today() + timedelta(days=1),
            check_out=date.today() + timedelta(days=3),
            full_name="Conflict Guest",
            email="conflict@example.com",
        )
        db.session.add(guest)
        db.session.flush()
        reservation = Reservation(
            guest_id=guest.id,
            room_id=505,
            check_in=guest.check_in,
            check_out=guest.check_out,
            status=ReservationStatus.PENDING,
        )
        db.session.add(reservation)
        db.session.commit()

    _login_staff(client, email="admin@example.com")

    response = client.get(
        "/staff/availability",
        query_string={
            "room_id": 505,
            "check_in": (date.today() + timedelta(days=2)).isoformat(),
            "check_out": (date.today() + timedelta(days=4)).isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.get_json()["available"] is False
    assert len(response.get_json()["conflicts"]) == 1
