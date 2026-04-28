"""
AirBnoB - Guest Authentication Blueprint
========================================
backend/auth/guest_auth.py

Guests never create accounts. This blueprint validates the QR token issued at
check-in and returns a short-lived JWT stored in an HttpOnly cookie.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, set_access_cookies
from pydantic import ValidationError

from app import limiter
from database import db
from models.guest import Guest
from schemas.auth_schemas import GuestSessionOut, GuestTokenRequest, error


guest_auth_bp = Blueprint("guest_auth", __name__)


@guest_auth_bp.post("/verify")
@limiter.limit("30 per minute")     # OWASP A07 — prevent token scanning / amplification
def verify_guest_token():
    """
    Validate a guest QR token and issue a short-lived guest session.

    The guest JWT deliberately carries no role claim, so staff-only routes
    cannot be accessed through guest authentication.
    """
    raw = request.get_json(silent=True)
    if not raw:
        _log_attempt("invalid_json")
        return jsonify(error("Request body must be JSON.")), 400

    try:
        body = GuestTokenRequest.model_validate(raw)
    except ValidationError as exc:
        messages = "; ".join(
            f"{'.'.join(str(loc) for loc in item['loc'])}: {item['msg']}"
            for item in exc.errors()
        )
        _log_attempt("validation_failed")
        return jsonify(error(messages)), 422

    guest = Guest.get_by_token(db.session, body.token)
    if guest is None:
        _log_attempt("token_not_found")
        return jsonify(error("Invalid or expired token.")), 401

    if not guest.is_viewable_token():
        _log_attempt("token_checked_out", guest)
        return jsonify(error("This booking has been checked out and is no longer accessible.")), 401

    token = create_access_token(
        identity=str(guest.id),
        expires_delta=current_app.config["GUEST_JWT_ACCESS_EXPIRES"],
        additional_claims={
            "token_type": "guest",
            "room_id": guest.room_id,
        },
    )

    response = jsonify(
        GuestSessionOut(
            room_id=guest.room_id,
            check_in=guest.check_in.isoformat(),
            check_out=guest.check_out.isoformat(),
        ).model_dump()
    )
    set_access_cookies(response, token)
    _log_attempt("verified", guest)
    return response, 200


def _log_attempt(outcome: str, guest: Guest | None = None) -> None:
    """Log the verification attempt without token values or guest PII."""
    guest_id = guest.id if guest is not None else None
    room_id = guest.room_id if guest is not None else None
    current_app.logger.info(
        "guest_token_verify outcome=%s guest_id=%s room_id=%s",
        outcome,
        guest_id,
        room_id,
    )