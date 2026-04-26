"""
AirBnoB — Admin / Staff Authentication Blueprint
=================================================
backend/auth/admin_auth.py

Registered in app.py as:
    app.register_blueprint(admin_auth_bp, url_prefix="/auth/staff")

Endpoints:
    POST   /auth/staff/login            — issue JWT cookie
    POST   /auth/staff/logout           — clear JWT cookie
    GET    /auth/staff/me               — current staff info
    POST   /auth/staff/change-password  — update own password

OWASP coverage in this file:
    A01 — role claim embedded in JWT; route guards in decorators.py
    A02 — bcrypt cost 12, dummy_verify on miss, needs_rehash upgrade
    A03 — all input through Pydantic before DB touch
    A05 — no sensitive data logged, no stack traces in responses
    A07 — Flask-Limiter 10 req/min on login route
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
    create_access_token,
)
import bcrypt
from pydantic import ValidationError
from sqlalchemy import select

from database import db
from app import limiter
from models.staff import Staff, StaffRole
from schemas.auth_schemas import (
    AdminLoginRequest,
    ChangePasswordRequest,
    StaffOut,
    TokenResponse,
    error,
)


admin_auth_bp = Blueprint("admin_auth", __name__)

_DUMMY_BCRYPT_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(rounds=12))


# POST /auth/staff/login
@admin_auth_bp.post("/login")
@limiter.limit("10 per minute")         # OWASP A07 — brute-force cap
def login():
    """
    Authenticate a staff member and issue a JWT in an HttpOnly cookie.

    Flow:
        1. Parse + validate body with Pydantic (Layer 1 — OWASP A03)
        2. Query Staff via ORM — no raw SQL (Layers 2 & 3)
        3. dummy_verify on miss to prevent timing-based user enumeration
        4. bcrypt verify on hit
        5. Check is_active — deactivated accounts silently return 401
        6. Transparent hash upgrade if bcrypt rounds have increased
        7. Issue JWT with role + email claims via HttpOnly cookie
    """
    raw = request.get_json(silent=True)
    if not raw:
        return jsonify(error("Request body must be JSON.")), 400

    # Pydantic validation
    try:
        body = AdminLoginRequest.model_validate(raw)
    except ValidationError as exc:
        messages = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        return jsonify(error(messages)), 422

    # ORM query (psycopg3 parameterises automatically)
    stmt = select(Staff).where(Staff.email == body.email)
    staff = db.session.scalars(stmt).first()

    # Timing-safe miss path
    # dummy_verify burns ~same time as a real bcrypt check so an attacker
    # cannot enumerate valid emails by measuring response latency.
    if staff is None:
        bcrypt.checkpw(b"dummy-password", _DUMMY_BCRYPT_HASH)
        return jsonify(error("Invalid credentials.")), 401

    # Password verification
    if not staff.verify_password(body.password):
        return jsonify(error("Invalid credentials.")), 401

    # Deactivated account — same vague message (OWASP A02)
    if not staff.is_active:
        return jsonify(error("Invalid credentials.")), 401

    # Transparent hash upgrade (cost factor may have increased)
    if staff.needs_rehash():
        staff.password_hash = Staff.hash_password(body.password)
        db.session.commit()

    # Issue JWT with role claim
    token = create_access_token(
        identity=str(staff.id),
        additional_claims={
            "role":  staff.role,
            "email": staff.email,
        },
    )

    response = jsonify(
        TokenResponse(
            role=StaffRole(staff.role),
            full_name=staff.full_name,
        ).model_dump()
    )

    # HttpOnly cookie — JS cannot read this value (OWASP A02)
    set_access_cookies(response, token)
    return response, 200


# POST /auth/staff/logout
@admin_auth_bp.post("/logout")
@jwt_required()
def logout():
    """
    Clear the JWT cookie server-side.
    The client has nothing to clean up — the cookie is HttpOnly.
    """
    response = jsonify({"message": "Logged out successfully."})
    unset_jwt_cookies(response)
    return response, 200


# GET /auth/staff/me
@admin_auth_bp.get("/me")
@jwt_required()
def me():
    """
    Return the current authenticated staff member's profile.

    Re-queries the DB from the JWT identity (staff.id) rather than
    reading the JWT claims directly — this ensures deactivated accounts
    are caught even if their token hasn't expired yet.
    """
    staff_id = int(get_jwt_identity())
    staff = db.session.get(Staff, staff_id)

    if staff is None or not staff.is_active:
        return jsonify(error("Account not found or deactivated.")), 401

    return jsonify(StaffOut.model_validate(staff).model_dump()), 200


# POST /auth/staff/change-password
@admin_auth_bp.post("/change-password")
@jwt_required()
@limiter.limit("5 per minute")          # tighter limit — sensitive operation
def change_password():
    """
    Allow a staff member to update their own password.

    Requires the current password before accepting the new one.
    The ChangePasswordRequest model_validator ensures old != new.
    On success the existing JWT cookie remains valid — no forced
    re-login unless you want to add that UX (swap token here if so).
    """
    raw = request.get_json(silent=True)
    if not raw:
        return jsonify(error("Request body must be JSON.")), 400

    try:
        body = ChangePasswordRequest.model_validate(raw)
    except ValidationError as exc:
        messages = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        return jsonify(error(messages)), 422

    staff_id = int(get_jwt_identity())
    staff = db.session.get(Staff, staff_id)

    if staff is None or not staff.is_active:
        return jsonify(error("Account not found.")), 401

    # Verify current password before allowing any change
    if not staff.verify_password(body.current_password):
        return jsonify(error("Current password is incorrect.")), 401

    staff.password_hash = Staff.hash_password(body.new_password)
    db.session.commit()

    return jsonify({"message": "Password updated successfully."}), 200
