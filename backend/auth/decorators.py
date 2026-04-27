"""Authorization decorators."""

from __future__ import annotations

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from database import db
from schemas.auth_schemas import error


def require_role(*roles: str):
    """
    Restrict a route to staff with one of the allowed roles.

    Re-queries the DB on every request rather than trusting the JWT role
    claim directly. This ensures that:
      - Deactivated accounts are rejected immediately (no waiting for token expiry)
      - Role changes (e.g. admin → front_desk) take effect immediately
      - Guest tokens (no role claim) are always rejected with 403

    The extra DB query is a single indexed PK lookup — negligible overhead
    for the security guarantee it provides.
    """
    allowed_roles = {str(role) for role in roles}

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            # Guest tokens carry a token_type claim but no role — reject early
            claims = get_jwt()
            if claims.get("token_type") == "guest":
                return jsonify(error("Insufficient permissions.")), 403

            # Re-query DB for live role and active status
            # Prevents a deactivated or demoted account from using a still-valid token
            from models.staff import Staff  # local import avoids circular import
            staff_id = get_jwt_identity()
            staff = db.session.get(Staff, int(staff_id))

            if staff is None or not staff.is_active:
                return jsonify(error("Authentication required.")), 401

            if staff.role not in allowed_roles:
                return jsonify(error("Insufficient permissions.")), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator