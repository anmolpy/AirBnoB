"""
Tests for injection resistance and input validation.

Covers:
- SQL injection attempts in login fields
- Script injection in password fields
- Null bytes in passwords
- Oversized inputs (bcrypt DoS prevention)
- UUID format enforcement on guest tokens
- Parameter pollution (extra fields rejected)
- Invalid JSON handling
- Guest token expiry and validity window
- Reservation date validation
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from conftest import login


class TestLoginInjection:
    """Login endpoint must reject malicious inputs before hitting the DB."""

    SQL_PAYLOADS = [
        "' OR '1'='1",
        "' OR 1=1--",
        "admin'--",
        "' UNION SELECT * FROM staff--",
        "'; DROP TABLE staff;--",
    ]

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_sql_injection_in_email(self, client, payload):
        res = client.post(
            "/auth/staff/login",
            json={"email": payload, "password": "SomePass1!"},
        )
        # Must be 422 (invalid email format) or 401 (not found) — never 200 or 500
        assert res.status_code in (401, 422)

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_sql_injection_in_password(self, client, admin_user, payload):
        res = client.post(
            "/auth/staff/login",
            json={"email": admin_user["email"], "password": payload},
        )
        assert res.status_code in (401, 422)

    def test_script_tag_in_password_rejected(self, client):
        res = client.post(
            "/auth/staff/login",
            json={"email": "admin@hotel.com", "password": "<script>alert(1)</script>"},
        )
        assert res.status_code == 422

    def test_null_byte_in_password_rejected(self, client):
        res = client.post(
            "/auth/staff/login",
            json={"email": "admin@hotel.com", "password": "Valid\x00Pass1!"},
        )
        assert res.status_code == 422

    def test_oversized_password_rejected(self, client):
        """Passwords over 128 chars must be rejected to prevent bcrypt DoS."""
        long_password = "A" * 129
        res = client.post(
            "/auth/staff/login",
            json={"email": "admin@hotel.com", "password": long_password},
        )
        assert res.status_code == 422

    def test_oversized_email_rejected(self, client):
        long_email = "a" * 250 + "@test.com"
        res = client.post(
            "/auth/staff/login",
            json={"email": long_email, "password": "ValidPass1!"},
        )
        assert res.status_code == 422


class TestGuestTokenValidation:
    """Guest token endpoint must enforce UUID4 format strictly."""

    def test_valid_uuid4_accepted(self, client, app, db):
        from models.guest import Guest
        with app.app_context():
            token = Guest.generate_token()
            guest = Guest(
                token=token,
                room_id=1,
                check_in=date.today(),
                check_out=date.today() + timedelta(days=1),
            )
            db.session.add(guest)
            db.session.commit()

        res = client.post("/auth/guest/verify", json={"token": token})
        assert res.status_code == 200

    def test_random_string_rejected(self, client):
        res = client.post("/auth/guest/verify", json={"token": "not-a-uuid"})
        assert res.status_code == 422

    def test_sql_injection_as_token(self, client):
        res = client.post(
            "/auth/guest/verify",
            json={"token": "' OR '1'='1' --xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"},
        )
        assert res.status_code == 422

    def test_uuid1_rejected(self, client):
        """UUID1 format must be rejected — only UUID4 is valid."""
        uuid1 = str(uuid.uuid1())
        res = client.post("/auth/guest/verify", json={"token": uuid1})
        assert res.status_code == 422

    def test_expired_token_rejected(self, client, app, db):
        """A guest whose check_out is in the past must be rejected."""
        from models.guest import Guest
        with app.app_context():
            token = Guest.generate_token()
            guest = Guest(
                token=token,
                room_id=1,
                check_in=date.today() - timedelta(days=3),
                check_out=date.today() - timedelta(days=1),
            )
            db.session.add(guest)
            db.session.commit()

        res = client.post("/auth/guest/verify", json={"token": token})
        assert res.status_code == 401

    def test_checked_out_guest_rejected(self, client, app, db):
        """A guest who has already checked out must be rejected."""
        from datetime import datetime, timezone
        from models.guest import Guest
        with app.app_context():
            token = Guest.generate_token()
            guest = Guest(
                token=token,
                room_id=1,
                check_in=date.today(),
                check_out=date.today() + timedelta(days=1),
                checked_out_at=datetime.now(tz=timezone.utc),
            )
            db.session.add(guest)
            db.session.commit()

        res = client.post("/auth/guest/verify", json={"token": token})
        assert res.status_code == 401

    def test_nonexistent_token_rejected(self, client):
        fake_token = str(uuid.uuid4())
        res = client.post("/auth/guest/verify", json={"token": fake_token})
        assert res.status_code == 401


class TestParameterPollution:
    """Extra fields must be rejected on all endpoints (extra='forbid')."""

    def test_extra_field_on_login(self, client):
        res = client.post(
            "/auth/staff/login",
            json={
                "email": "admin@hotel.com",
                "password": "AdminPass1!",
                "is_admin": True,
            },
        )
        assert res.status_code == 422

    def test_extra_field_on_guest_verify(self, client):
        res = client.post(
            "/auth/guest/verify",
            json={
                "token": str(uuid.uuid4()),
                "room_id": 999,
            },
        )
        assert res.status_code == 422

    def test_extra_field_on_create_staff(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/admin/staff",
            json={
                "email": "new@hotel.com",
                "full_name": "New Staff",
                "password": "NewStaff1!",
                "role": "front_desk",
                "is_active": False,     # should not be settable at creation
            },
        )
        assert res.status_code == 422


class TestReservationValidation:
    """Reservation inputs must be validated before hitting the DB."""

    def test_past_check_in_rejected(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/staff/reservations",
            json={
                "room_id": 1,
                "check_in": str(date.today() - timedelta(days=1)),
                "check_out": str(date.today() + timedelta(days=1)),
            },
        )
        assert res.status_code == 422

    def test_checkout_before_checkin_rejected(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/staff/reservations",
            json={
                "room_id": 1,
                "check_in": str(date.today() + timedelta(days=3)),
                "check_out": str(date.today() + timedelta(days=1)),
            },
        )
        assert res.status_code == 422

    def test_same_day_checkout_rejected(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        today = str(date.today())
        res = client.post(
            "/staff/reservations",
            json={
                "room_id": 1,
                "check_in": today,
                "check_out": today,
            },
        )
        assert res.status_code == 422

    def test_stay_over_90_nights_rejected(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/staff/reservations",
            json={
                "room_id": 1,
                "check_in": str(date.today()),
                "check_out": str(date.today() + timedelta(days=91)),
            },
        )
        assert res.status_code == 422

    def test_valid_reservation_accepted(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/staff/reservations",
            json={
                "room_id": 1,
                "check_in": str(date.today()),
                "check_out": str(date.today() + timedelta(days=3)),
            },
        )
        assert res.status_code == 201

    def test_negative_room_id_rejected(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/staff/reservations",
            json={
                "room_id": -1,
                "check_in": str(date.today()),
                "check_out": str(date.today() + timedelta(days=1)),
            },
        )
        assert res.status_code == 422