"""Admin-only staff management routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from auth.decorators import require_role
from database import db
from models.staff import Staff, StaffRole
from schemas.auth_schemas import CreateStaffRequest, StaffOut, error


admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/health")
@require_role(StaffRole.ADMIN)
def admin_health():
    """Minimal protected endpoint used by tests and app wiring."""
    return jsonify({"message": "admin ok"}), 200


@admin_bp.get("/staff")
@require_role(StaffRole.ADMIN)
def list_staff():
    """List all staff accounts without exposing password hashes."""
    stmt = select(Staff).order_by(Staff.role, Staff.full_name, Staff.email)
    staff_rows = db.session.scalars(stmt).all()

    payload = [StaffOut.model_validate(staff).model_dump() for staff in staff_rows]
    return jsonify({"staff": payload, "total": len(payload)}), 200


@admin_bp.post("/staff")
@require_role(StaffRole.ADMIN)
def create_staff():
    """Create a new admin or front-desk account."""
    body = _validate_json(CreateStaffRequest)
    if body is None:
        return _validation_error_response()

    existing = db.session.scalars(
        select(Staff).where(Staff.email == body.email)
    ).first()
    if existing is not None:
        return jsonify(error("A staff account with that email already exists.")), 409

    staff = Staff(
        email=body.email,
        full_name=body.full_name,
        password_hash=Staff.hash_password(body.password),
        role=str(body.role),
        is_active=True,
    )
    db.session.add(staff)
    db.session.commit()

    return jsonify(StaffOut.model_validate(staff).model_dump()), 201


@admin_bp.patch("/staff/<int:staff_id>/deactivate")
@require_role(StaffRole.ADMIN)
def deactivate_staff(staff_id: int):
    """Soft-delete a staff account while preserving audit history."""
    staff = db.session.get(Staff, staff_id)
    if staff is None:
        return jsonify(error("Staff account not found.")), 404

    if not staff.is_active:
        return jsonify(error("Staff account is already inactive.")), 409

    staff.is_active = False
    db.session.commit()
    return jsonify(StaffOut.model_validate(staff).model_dump()), 200


@admin_bp.patch("/staff/<int:staff_id>/reactivate")
@require_role(StaffRole.ADMIN)
def reactivate_staff(staff_id: int):
    """Re-enable a previously deactivated staff account."""
    staff = db.session.get(Staff, staff_id)
    if staff is None:
        return jsonify(error("Staff account not found.")), 404

    if staff.is_active:
        return jsonify(error("Staff account is already active.")), 409

    staff.is_active = True
    db.session.commit()
    return jsonify(StaffOut.model_validate(staff).model_dump()), 200


_LAST_VALIDATION_ERROR: str | None = None


def _validate_json(schema_cls):
    """Validate request JSON through a Pydantic schema."""
    global _LAST_VALIDATION_ERROR

    raw = request.get_json(silent=True)
    if not raw:
        _LAST_VALIDATION_ERROR = "Request body must be JSON."
        return None

    try:
        _LAST_VALIDATION_ERROR = None
        return schema_cls.model_validate(raw)
    except ValidationError as exc:
        _LAST_VALIDATION_ERROR = "; ".join(
            f"{'.'.join(str(loc) for loc in item['loc'])}: {item['msg']}"
            for item in exc.errors()
        )
        return None


def _validation_error_response():
    """Return the most recent request validation error."""
    message = _LAST_VALIDATION_ERROR or "Validation error."
    status = 400 if message == "Request body must be JSON." else 422
    return jsonify(error(message)), status
