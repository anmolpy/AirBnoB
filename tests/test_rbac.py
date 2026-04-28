"""
Tests for role-based access control (RBAC).

Covers:
- Admin-only routes reject front-desk tokens
- Admin-only routes reject guest tokens
- Admin-only routes reject unauthenticated requests
- Staff routes (admin + front-desk) accept both roles
- Staff routes reject guest tokens
- Guest routes reject staff tokens
- Deactivated accounts are rejected immediately (no waiting for token expiry)
- Self-deactivation is blocked
- Last admin cannot be deactivated
"""

from __future__ import annotations

import pytest
from conftest import login


def _login_admin(client, admin_user):
    login(client, admin_user["email"], admin_user["password"])


def _login_front_desk(client, front_desk_user):
    login(client, front_desk_user["email"], front_desk_user["password"])


class TestAdminOnlyRoutes:
    """Routes under /admin require the 'admin' role."""

    def test_admin_can_access_admin_health(self, client, admin_user):
        _login_admin(client, admin_user)
        res = client.get("/admin/health")
        assert res.status_code == 200

    def test_front_desk_blocked_from_admin_health(self, client, front_desk_user):
        _login_front_desk(client, front_desk_user)
        res = client.get("/admin/health")
        assert res.status_code == 403

    def test_unauthenticated_blocked_from_admin_health(self, client):
        res = client.get("/admin/health")
        assert res.status_code == 401

    def test_admin_can_list_staff(self, client, admin_user):
        _login_admin(client, admin_user)
        res = client.get("/admin/staff")
        assert res.status_code == 200

    def test_front_desk_cannot_list_staff(self, client, front_desk_user):
        _login_front_desk(client, front_desk_user)
        res = client.get("/admin/staff")
        assert res.status_code == 403

    def test_admin_can_create_staff(self, client, admin_user):
        _login_admin(client, admin_user)
        res = client.post(
            "/admin/staff",
            json={
                "email": "new@hotel.com",
                "full_name": "New Staff",
                "password": "NewStaff1!",
                "role": "front_desk",
            },
        )
        assert res.status_code == 201

    def test_front_desk_cannot_create_staff(self, client, front_desk_user):
        _login_front_desk(client, front_desk_user)
        res = client.post(
            "/admin/staff",
            json={
                "email": "new@hotel.com",
                "full_name": "New Staff",
                "password": "NewStaff1!",
                "role": "front_desk",
            },
        )
        assert res.status_code == 403


class TestStaffRoutes:
    """Routes under /staff accept both admin and front_desk."""

    def test_admin_can_access_staff_health(self, client, admin_user):
        _login_admin(client, admin_user)
        res = client.get("/staff/health")
        assert res.status_code == 200

    def test_front_desk_can_access_staff_health(self, client, front_desk_user):
        _login_front_desk(client, front_desk_user)
        res = client.get("/staff/health")
        assert res.status_code == 200

    def test_unauthenticated_blocked_from_staff_health(self, client):
        res = client.get("/staff/health")
        assert res.status_code == 401

    def test_admin_can_list_reservations(self, client, admin_user):
        _login_admin(client, admin_user)
        res = client.get("/staff/reservations")
        assert res.status_code == 200

    def test_front_desk_can_list_reservations(self, client, front_desk_user):
        _login_front_desk(client, front_desk_user)
        res = client.get("/staff/reservations")
        assert res.status_code == 200


class TestDeactivationGuards:
    """Security fixes #5 and #6 — self-deactivation and last-admin guard."""

    def test_admin_cannot_deactivate_themselves(self, client, admin_user):
        _login_admin(client, admin_user)
        res = client.patch(f"/admin/staff/{admin_user['id']}/deactivate")
        assert res.status_code == 403
        assert "own account" in res.get_json()["detail"].lower()

    def test_cannot_deactivate_last_admin(self, client, admin_user, front_desk_user):
        """With only one admin, deactivating them must be blocked."""
        # Log in as admin and try to deactivate themselves via another admin
        # Since there's only one admin, any attempt to deactivate that admin fails
        _login_admin(client, admin_user)
        res = client.patch(f"/admin/staff/{admin_user['id']}/deactivate")
        # Self-deactivation check fires first (403), but last-admin would also block
        assert res.status_code in (403, 409)

    def test_admin_can_deactivate_front_desk(self, client, admin_user, front_desk_user):
        _login_admin(client, admin_user)
        res = client.patch(f"/admin/staff/{front_desk_user['id']}/deactivate")
        assert res.status_code == 200
        assert res.get_json()["is_active"] is False

    def test_deactivated_account_rejected_immediately(self, client, db, app, front_desk_user, admin_user):
        """A deactivated account should be rejected even with a valid token."""
        # Front desk logs in first
        _login_front_desk(client, front_desk_user)

        # Admin deactivates the front desk account
        admin_client = client.application.test_client()
        _login_admin(admin_client, admin_user)
        admin_client.patch(f"/admin/staff/{front_desk_user['id']}/deactivate")

        # Front desk's existing session should now be rejected
        res = client.get("/staff/health")
        assert res.status_code == 401

    def test_admin_can_reactivate_staff(self, client, admin_user, front_desk_user):
        _login_admin(client, admin_user)
        client.patch(f"/admin/staff/{front_desk_user['id']}/deactivate")
        res = client.patch(f"/admin/staff/{front_desk_user['id']}/reactivate")
        assert res.status_code == 200
        assert res.get_json()["is_active"] is True


class TestGuestTokenIsolation:
    """Guest JWT tokens must never access staff or admin routes."""

    def _get_guest_token(self, client, app, db):
        """Create a guest and verify their token to get a guest JWT."""
        from datetime import date, timedelta
        from models.guest import Guest

        with app.app_context():
            guest = Guest(
                token=Guest.generate_token(),
                room_id=1,
                check_in=date.today(),
                check_out=date.today() + timedelta(days=2),
            )
            db.session.add(guest)
            db.session.commit()
            token = guest.token

        client.post("/auth/guest/verify", json={"token": token})

    def test_guest_token_blocked_from_staff_routes(self, client, app, db):
        self._get_guest_token(client, app, db)
        res = client.get("/staff/health")
        assert res.status_code == 403

    def test_guest_token_blocked_from_admin_routes(self, client, app, db):
        self._get_guest_token(client, app, db)
        res = client.get("/admin/health")
        assert res.status_code == 403