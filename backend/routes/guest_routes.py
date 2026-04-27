"""Guest routes."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required, unset_jwt_cookies
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import limiter
from database import db
from models.guest import Guest
from models.reservation import Reservation, ReservationStatus
from schemas.auth_schemas import GuestSessionOut, error
from schemas.reservation_schemas import CreateReservationRequest, GuestBookingOut, ReservationOut
from routes.staff_routes import _find_conflicts, _reservation_by_id, _validate_json, _validation_error_response


guest_bp = Blueprint("guest", __name__)


@guest_bp.post("/book")
@limiter.limit("20 per hour")       # OWASP A07 — prevent reservation flooding and room enumeration
def book_guest_room():
    """Create a public reservation and issue a guest token for later check-in."""
    body, err = _validate_json(CreateReservationRequest)
    if body is None:
        return _validation_error_response(err)

    conflicts = _find_conflicts(body.room_id, body.check_in, body.check_out)
    if conflicts:
        return jsonify(error("Room is not available for the requested date range.")), 409

    guest = Guest(
        token=Guest.generate_token(),
        room_id=body.room_id,
        check_in=body.check_in,
        check_out=body.check_out,
        full_name=body.guest_name,
        email=body.guest_email,
    )
    db.session.add(guest)
    db.session.flush()

    reservation = Reservation(
        guest_id=guest.id,
        room_id=body.room_id,
        check_in=body.check_in,
        check_out=body.check_out,
        status=ReservationStatus.PENDING,
    )
    db.session.add(reservation)
    db.session.commit()

    reservation = _reservation_by_id(reservation.id)
    return jsonify(
        GuestBookingOut(
            reservation=ReservationOut.from_orm_with_guest(reservation),
            guest_token=guest.token,
        ).model_dump(mode="json")
    ), 201


@guest_bp.get("/health")
@jwt_required()
def guest_health():
    """Minimal authenticated endpoint reserved for guest flows."""
    if not _is_guest_session():
        return jsonify(error("Insufficient permissions.")), 403
    return jsonify({"message": "guest ok"}), 200


@guest_bp.get("/me")
@jwt_required()
def guest_me():
    """Return the current guest session without exposing token or extra PII."""
    if not _is_guest_session():
        return jsonify(error("Insufficient permissions.")), 403

    guest = _current_guest()
    if guest is None or not guest.is_valid_token():
        return jsonify(error("Guest session is no longer valid.")), 401

    return jsonify(
        GuestSessionOut(
            room_id=guest.room_id,
            check_in=guest.check_in.isoformat(),
            check_out=guest.check_out.isoformat(),
        ).model_dump()
    ), 200


@guest_bp.get("/reservation")
@jwt_required()
def guest_reservation():
    """Return the reservation linked to the current guest token."""
    if not _is_guest_session():
        return jsonify(error("Insufficient permissions.")), 403

    guest = _current_guest()
    if guest is None or not guest.is_valid_token():
        return jsonify(error("Guest session is no longer valid.")), 401

    stmt = (
        select(Reservation)
        .options(selectinload(Reservation.guest))
        .where(Reservation.guest_id == guest.id)
        .order_by(Reservation.created_at.desc(), Reservation.id.desc())
    )
    reservation = db.session.scalars(stmt).first()
    if reservation is None:
        return jsonify(error("Reservation not found.")), 404

    return jsonify(ReservationOut.from_orm_with_guest(reservation).model_dump(mode="json")), 200


@guest_bp.post("/logout")
@jwt_required()
def guest_logout():
    """Clear the guest JWT cookie."""
    if not _is_guest_session():
        return jsonify(error("Insufficient permissions.")), 403

    response = jsonify({"message": "Guest session ended."})
    unset_jwt_cookies(response)
    return response, 200


def _is_guest_session() -> bool:
    """Identify a guest JWT by the absence of a role claim."""
    claims = get_jwt()
    return claims.get("token_type") == "guest" and claims.get("role") is None


def _current_guest() -> Guest | None:
    """Load the current guest from the JWT identity."""
    guest_id = get_jwt_identity()
    if guest_id is None:
        return None
    return db.session.get(Guest, int(guest_id))