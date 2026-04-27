"""Staff routes shared by admin and front desk."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from auth.decorators import require_role
from database import db
from models.guest import Guest
from models.reservation import Reservation, ReservationStatus
from models.staff import StaffRole
from schemas.auth_schemas import error
from schemas.reservation_schemas import (
    AvailabilityOut,
    CancelReservationRequest,
    CheckInOut,
    CheckInRequest,
    CheckOutOut,
    CheckOutRequest,
    CreateReservationRequest,
    ReservationListOut,
    ReservationOut,
    UpdateReservationRequest,
)


staff_bp = Blueprint("staff", __name__)


@staff_bp.get("/health")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def staff_health():
    """Minimal protected endpoint used by tests and app wiring."""
    return jsonify({"message": "staff ok"}), 200


@staff_bp.get("/reservations")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def list_reservations():
    """List reservations, optionally filtered by status or room."""
    stmt = select(Reservation).options(selectinload(Reservation.guest))

    status = request.args.get("status")
    if status:
        try:
            status_enum = ReservationStatus(status)
        except ValueError:
            return jsonify(error("Invalid reservation status filter.")), 422
        stmt = stmt.where(Reservation.status == status_enum)
    else:
        status_enum = None

    room_id = request.args.get("room_id", type=int)
    if room_id is not None:
        if room_id <= 0:
            return jsonify(error("room_id must be a positive integer.")), 422
        stmt = stmt.where(Reservation.room_id == room_id)

    stmt = stmt.order_by(Reservation.check_in, Reservation.id)
    reservations = db.session.scalars(stmt).all()
    payload = [ReservationOut.from_orm_with_guest(item).model_dump(mode="json") for item in reservations]

    return jsonify(
        ReservationListOut(
            reservations=payload,
            total=len(payload),
            status_filter=status_enum,
        ).model_dump(mode="json")
    ), 200


@staff_bp.get("/reservations/<int:reservation_id>")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def get_reservation(reservation_id: int):
    """Return one reservation with guest details if still present."""
    reservation = _reservation_by_id(reservation_id)
    if reservation is None:
        return jsonify(error("Reservation not found.")), 404

    return jsonify(ReservationOut.from_orm_with_guest(reservation).model_dump(mode="json")), 200


@staff_bp.post("/reservations")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def create_reservation():
    """Create a reservation and linked guest record."""
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
    return jsonify(ReservationOut.from_orm_with_guest(reservation).model_dump(mode="json")), 201


@staff_bp.patch("/reservations/<int:reservation_id>")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def update_reservation(reservation_id: int):
    """Update a pending reservation without touching active or closed stays."""
    reservation = _reservation_by_id(reservation_id)
    if reservation is None:
        return jsonify(error("Reservation not found.")), 404

    if reservation.status != ReservationStatus.PENDING:
        return jsonify(error("Only pending reservations can be updated.")), 409

    body, err = _validate_json(UpdateReservationRequest)
    if body is None:
        return _validation_error_response(err)

    new_check_in = body.check_in if body.check_in is not None else reservation.check_in
    new_check_out = body.check_out if body.check_out is not None else reservation.check_out
    if new_check_out <= new_check_in:
        return jsonify(error("Check-out must be after check-in.")), 422

    conflicts = _find_conflicts(
        reservation.room_id,
        new_check_in,
        new_check_out,
        exclude_reservation_id=reservation.id,
    )
    if conflicts:
        return jsonify(error("Room is not available for the requested date range.")), 409

    reservation.check_in = new_check_in
    reservation.check_out = new_check_out
    if reservation.guest is not None:
        if body.guest_name is not None:
            reservation.guest.full_name = body.guest_name
        if body.guest_email is not None:
            reservation.guest.email = body.guest_email
        reservation.guest.check_in = new_check_in
        reservation.guest.check_out = new_check_out

    db.session.commit()
    reservation = _reservation_by_id(reservation.id)
    return jsonify(ReservationOut.from_orm_with_guest(reservation).model_dump(mode="json")), 200


@staff_bp.post("/reservations/<int:reservation_id>/cancel")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def cancel_reservation(reservation_id: int):
    """Cancel a pending reservation and retain the row for audit history."""
    reservation = _reservation_by_id(reservation_id)
    if reservation is None:
        return jsonify(error("Reservation not found.")), 404

    body, err = _validate_json(CancelReservationRequest)
    if body is None:
        return _validation_error_response(err)

    try:
        reservation.cancel(db.session)
    except ValueError as exc:
        return jsonify(error(str(exc))), 409

    reservation = _reservation_by_id(reservation.id)
    return jsonify(
        {
            "message": "Reservation cancelled successfully.",
            "reason": body.reason,
            "reservation": ReservationOut.from_orm_with_guest(reservation).model_dump(mode="json"),
        }
    ), 200


@staff_bp.post("/checkin")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def check_in_guest():
    """Activate a pending reservation."""
    body, err = _validate_json(CheckInRequest)
    if body is None:
        return _validation_error_response(err)

    reservation = _reservation_by_id(body.reservation_id)
    if reservation is None:
        return jsonify(error("Reservation not found.")), 404

    try:
        reservation.check_in_guest(db.session)
    except ValueError as exc:
        return jsonify(error(str(exc))), 409

    return jsonify(
        CheckInOut(
            reservation_id=reservation.id,
            room_id=reservation.room_id,
            check_out=reservation.check_out,
        ).model_dump(mode="json")
    ), 200


@staff_bp.post("/checkout")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def check_out_guest():
    """Check out an active guest and purge their PII."""
    body, err = _validate_json(CheckOutRequest)
    if body is None:
        return _validation_error_response(err)

    reservation = _reservation_by_id(body.reservation_id)
    if reservation is None:
        return jsonify(error("Reservation not found.")), 404

    try:
        reservation.check_out_guest(db.session)
    except ValueError as exc:
        return jsonify(error(str(exc))), 409

    reservation = _reservation_by_id(reservation.id)
    checked_out_at = (
        reservation.guest.checked_out_at
        if reservation.guest and reservation.guest.checked_out_at is not None
        else reservation.updated_at
    )
    return jsonify(
        CheckOutOut(
            reservation_id=reservation.id,
            room_id=reservation.room_id,
            checked_out_at=checked_out_at,
        ).model_dump(mode="json")
    ), 200


@staff_bp.get("/availability")
@require_role(StaffRole.ADMIN, StaffRole.FRONT_DESK)
def check_availability():
    """Check whether a room is available for a requested date range."""
    room_id = request.args.get("room_id", type=int)
    if room_id is None or room_id <= 0:
        return jsonify(error("room_id must be a positive integer.")), 422

    check_in_raw = request.args.get("check_in")
    check_out_raw = request.args.get("check_out")
    if not check_in_raw or not check_out_raw:
        return jsonify(error("check_in and check_out query parameters are required.")), 422

    try:
        check_in = date.fromisoformat(check_in_raw)
        check_out = date.fromisoformat(check_out_raw)
    except ValueError:
        return jsonify(error("check_in and check_out must be valid ISO dates.")), 422

    if check_out <= check_in:
        return jsonify(error("check_out must be after check_in.")), 422

    conflicts = _find_conflicts(room_id, check_in, check_out)
    conflict_payload = [
        ReservationOut.from_orm_with_guest(item).model_dump(mode="json")
        for item in conflicts
    ]

    return jsonify(
        AvailabilityOut(
            room_id=room_id,
            available=not conflicts,
            conflicts=conflict_payload,
        ).model_dump(mode="json")
    ), 200


def _validate_json(schema_cls) -> tuple:
    """
    Validate request JSON through a Pydantic schema.

    Returns:
        (parsed_body, None)  on success
        (None, error_msg)    on failure

    No global state — safe under multi-threaded WSGI servers.
    """
    raw = request.get_json(silent=True)
    if not raw:
        return None, "Request body must be JSON."

    try:
        return schema_cls.model_validate(raw), None
    except ValidationError as exc:
        msg = "; ".join(
            f"{'.'.join(str(loc) for loc in item['loc'])}: {item['msg']}"
            for item in exc.errors()
        )
        return None, msg


def _validation_error_response(message: str):
    """Return a validation error response for the given message."""
    status = 400 if message == "Request body must be JSON." else 422
    return jsonify(error(message)), status


def _reservation_by_id(reservation_id: int) -> Reservation | None:
    """Load a reservation with its guest relationship."""
    stmt = (
        select(Reservation)
        .options(selectinload(Reservation.guest))
        .where(Reservation.id == reservation_id)
    )
    return db.session.scalars(stmt).first()


def _find_conflicts(
    room_id: int,
    check_in: date,
    check_out: date,
    exclude_reservation_id: int | None = None,
) -> list[Reservation]:
    """Find overlapping non-cancelled reservations for the same room."""
    stmt = (
        select(Reservation)
        .options(selectinload(Reservation.guest))
        .where(
            Reservation.room_id == room_id,
            Reservation.status != ReservationStatus.CANCELLED,
            Reservation.check_in < check_out,
            Reservation.check_out > check_in,
        )
        .order_by(Reservation.check_in, Reservation.id)
    )

    if exclude_reservation_id is not None:
        stmt = stmt.where(Reservation.id != exclude_reservation_id)

    return list(db.session.scalars(stmt).all())