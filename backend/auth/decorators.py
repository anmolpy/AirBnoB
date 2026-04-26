"""Authorization decorators."""

from __future__ import annotations

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, jwt_required

from schemas.auth_schemas import error


def require_role(*roles: str):
    """
    Restrict a route to staff JWTs with one of the allowed roles.

    Guest tokens carry no role claim, so they are rejected with 403 before the
    wrapped handler runs.
    """
    allowed_roles = {str(role) for role in roles}

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            role = claims.get("role")

            if role not in allowed_roles:
                return jsonify(error("Insufficient permissions.")), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator
