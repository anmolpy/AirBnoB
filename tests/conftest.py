"""
Shared pytest fixtures for AirBnoB backend tests.

Place this file in the tests/ directory alongside the test files.
The app fixture creates a fresh in-memory SQLite DB for every test,
so tests are fully isolated and never touch the dev database.
"""

from __future__ import annotations

import pytest

from app import create_app, limiter
from database import db as _db
from models.staff import Staff, StaffRole


@pytest.fixture(scope="session")
def app():
    """
    Create a testing app instance once per session.
    Uses TestingConfig: in-memory SQLite, CSRF disabled, no secure cookies.
    """
    application = create_app("testing")
    # Disable rate limiting entirely in tests — we test logic, not limits
    application.config["RATELIMIT_ENABLED"] = False
    limiter.enabled = False
    return application


@pytest.fixture(scope="function")
def db(app):
    """
    Provide a clean database for each test.
    Creates all tables before the test, drops them after.
    """
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app, db):
    """Flask test client with cookie support enabled."""
    with app.test_client() as c:
        c.allow_redirects = True
        yield c


@pytest.fixture
def admin_user(db, app):
    """Create and return an active admin staff member."""
    with app.app_context():
        staff = Staff(
            email="admin@hotel.com",
            full_name="Test Admin",
            password_hash=Staff.hash_password("AdminPass1!"),
            role=StaffRole.ADMIN,
            is_active=True,
        )
        db.session.add(staff)
        db.session.commit()
        db.session.refresh(staff)
        return {"id": staff.id, "email": staff.email, "password": "AdminPass1!"}


@pytest.fixture
def front_desk_user(db, app):
    """Create and return an active front-desk staff member."""
    with app.app_context():
        staff = Staff(
            email="desk@hotel.com",
            full_name="Test Front Desk",
            password_hash=Staff.hash_password("DeskPass1!"),
            role=StaffRole.FRONT_DESK,
            is_active=True,
        )
        db.session.add(staff)
        db.session.commit()
        db.session.refresh(staff)
        return {"id": staff.id, "email": staff.email, "password": "DeskPass1!"}


def login(client, email: str, password: str):
    """Helper: log in and return the response. Cookie is set automatically."""
    return client.post(
        "/auth/staff/login",
        json={"email": email, "password": password},
    )