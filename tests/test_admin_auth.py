"""
Tests for admin / staff authentication.

Covers:
- Successful login returns 200 + role info
- Wrong password returns 401
- Unknown email returns 401 (same message — no enumeration)
- Inactive account returns 401
- Missing fields return 422
- Logout clears the cookie
- /me returns current user when authenticated
- /me returns 401 when not authenticated
- Change password happy path
- Change password wrong current password
- Change password same as old password
"""

from __future__ import annotations

import pytest
from conftest import login


class TestLogin:
    def test_successful_login(self, client, admin_user):
        res = login(client, admin_user["email"], admin_user["password"])
        assert res.status_code == 200
        data = res.get_json()
        assert data["role"] == "admin"
        assert data["full_name"] == "Test Admin"
        assert "access_token_cookie" in res.headers.get("Set-Cookie", "")

    def test_wrong_password(self, client, admin_user):
        res = login(client, admin_user["email"], "WrongPass1!")
        assert res.status_code == 401
        assert res.get_json()["detail"] == "Invalid credentials."

    def test_unknown_email(self, client):
        res = login(client, "nobody@hotel.com", "SomePass1!")
        assert res.status_code == 401
        assert res.get_json()["detail"] == "Invalid credentials."

    def test_wrong_and_unknown_same_message(self, client, admin_user):
        """Both wrong password and unknown email must return identical messages
        to prevent user enumeration."""
        wrong_pass = login(client, admin_user["email"], "WrongPass1!")
        unknown = login(client, "nobody@hotel.com", "SomePass1!")
        assert wrong_pass.get_json()["detail"] == unknown.get_json()["detail"]

    def test_inactive_account(self, client, db, app, admin_user):
        from models.staff import Staff
        with app.app_context():
            staff = db.session.get(Staff, admin_user["id"])
            staff.is_active = False
            db.session.commit()

        res = login(client, admin_user["email"], admin_user["password"])
        assert res.status_code == 401
        assert res.get_json()["detail"] == "Invalid credentials."

    def test_missing_password_field(self, client):
        res = client.post("/auth/staff/login", json={"email": "admin@hotel.com"})
        assert res.status_code == 422

    def test_missing_email_field(self, client):
        res = client.post("/auth/staff/login", json={"password": "AdminPass1!"})
        assert res.status_code == 422

    def test_empty_body(self, client):
        res = client.post("/auth/staff/login", json={})
        assert res.status_code == 400

    def test_non_json_body(self, client):
        res = client.post(
            "/auth/staff/login",
            data="not json",
            content_type="text/plain",
        )
        assert res.status_code == 400

    def test_extra_fields_rejected(self, client):
        """extra='forbid' on the schema must block unknown keys."""
        res = client.post(
            "/auth/staff/login",
            json={"email": "admin@hotel.com", "password": "AdminPass1!", "role": "admin"},
        )
        assert res.status_code == 422

    def test_password_too_short(self, client):
        res = client.post(
            "/auth/staff/login",
            json={"email": "admin@hotel.com", "password": "short"},
        )
        assert res.status_code == 422

    def test_email_case_insensitive(self, client, admin_user):
        """Email normalisation means ADMIN@HOTEL.COM should match admin@hotel.com."""
        res = login(client, "ADMIN@HOTEL.COM", admin_user["password"])
        assert res.status_code == 200


class TestLogout:
    def test_logout_clears_cookie(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post("/auth/staff/logout")
        assert res.status_code == 200
        # Cookie should be cleared (empty or expired)
        cookie_header = res.headers.get("Set-Cookie", "")
        assert "access_token_cookie" in cookie_header

    def test_logout_without_login(self, client):
        res = client.post("/auth/staff/logout")
        assert res.status_code == 401


class TestMe:
    def test_me_authenticated(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.get("/auth/staff/me")
        assert res.status_code == 200
        data = res.get_json()
        assert data["email"] == admin_user["email"]
        assert "password_hash" not in data

    def test_me_unauthenticated(self, client):
        res = client.get("/auth/staff/me")
        assert res.status_code == 401

    def test_me_deactivated_mid_session(self, client, db, app, admin_user):
        """Even with a valid token, a deactivated account must be rejected."""
        login(client, admin_user["email"], admin_user["password"])

        from models.staff import Staff
        with app.app_context():
            staff = db.session.get(Staff, admin_user["id"])
            staff.is_active = False
            db.session.commit()

        res = client.get("/auth/staff/me")
        assert res.status_code == 401


class TestChangePassword:
    def test_change_password_success(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/auth/staff/change-password",
            json={
                "current_password": admin_user["password"],
                "new_password": "NewAdminPass1!",
            },
        )
        assert res.status_code == 200

        # Old password must no longer work
        client2 = client.application.test_client()
        res2 = login(client2, admin_user["email"], admin_user["password"])
        assert res2.status_code == 401

        # New password must work
        res3 = login(client2, admin_user["email"], "NewAdminPass1!")
        assert res3.status_code == 200

    def test_wrong_current_password(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/auth/staff/change-password",
            json={
                "current_password": "WrongPass1!",
                "new_password": "NewAdminPass1!",
            },
        )
        assert res.status_code == 401

    def test_same_password_rejected(self, client, admin_user):
        login(client, admin_user["email"], admin_user["password"])
        res = client.post(
            "/auth/staff/change-password",
            json={
                "current_password": admin_user["password"],
                "new_password": admin_user["password"],
            },
        )
        assert res.status_code == 422

    def test_change_password_unauthenticated(self, client):
        res = client.post(
            "/auth/staff/change-password",
            json={
                "current_password": "AdminPass1!",
                "new_password": "NewAdminPass1!",
            },
        )
        assert res.status_code == 401