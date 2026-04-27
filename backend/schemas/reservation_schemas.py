from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from models.reservation import ReservationStatus


# Shared config
class _StrictBase(BaseModel):
    """
    Shared base — mirrors auth_schemas._StrictBase.
    extra='forbid' blocks parameter pollution.
    str_strip_whitespace trims all string inputs automatically.
    """
    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
    }


# Request schemas
class CheckInRequest(_StrictBase):
    """
    POST /staff/checkin

    Transitions a reservation from PENDING → ACTIVE.
    Only requires the reservation ID — the guest is already linked
    to the reservation at booking time. No PII is accepted here.
    """

    reservation_id: Annotated[
        int,
        Field(gt=0, description="ID of the reservation to activate"),
    ]


class CheckOutRequest(_StrictBase):
    """
    POST /staff/checkout

    Transitions a reservation from ACTIVE → CHECKED_OUT
    and triggers PII purge on the linked Guest row.
    Only requires the reservation ID.
    """

    reservation_id: Annotated[
        int,
        Field(gt=0, description="ID of the reservation to close"),
    ]


class CreateReservationRequest(_StrictBase):
    """
    POST /staff/reservations

    Creates a new reservation and a linked Guest row.
    Front desk fills this out at booking time.

    Business rules enforced here (Layer 1) before any DB query:
    - check_out must be after check_in (not same day)
    - check_in cannot be in the past
    - stay length capped at 90 nights (configurable)
    - guest name and email are optional — minimal PII by design
    """

    room_id: Annotated[
        int,
        Field(gt=0, description="Room number to reserve"),
    ]

    check_in: Annotated[
        date,
        Field(description="Arrival date (YYYY-MM-DD)"),
    ]

    check_out: Annotated[
        date,
        Field(description="Departure date (YYYY-MM-DD)"),
    ]

    # Optional PII — collected only if guest consents
    # Both are purged from the DB at checkout (Guest.purge_pii)
    guest_name: Annotated[
        str | None,
        Field(
            default=None,
            min_length=2,
            max_length=120,
            description="Guest full name (optional)",
        ),
    ]

    guest_email: Annotated[
        str | None,
        Field(
            default=None,
            max_length=254,
            description="Guest email (optional)",
            pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        ),
    ]

    @field_validator("check_in")
    @classmethod
    def check_in_not_past(cls, v: date) -> date:
        """Prevent booking a room for a date that has already passed."""
        today = date.today()
        if v < today:
            raise ValueError(
                f"Check-in date {v} is in the past. "
                f"Earliest valid check-in is {today}."
            )
        return v

    @field_validator("guest_name")
    @classmethod
    def sanitise_name(cls, v: str | None) -> str | None:
        """Collapse internal whitespace in names: 'John  Smith' → 'John Smith'."""
        if v is None:
            return None
        return " ".join(v.split())

    @model_validator(mode="after")
    def validate_date_range(self) -> CreateReservationRequest:
        """
        Cross-field validation — requires both dates to be present.

        Rules:
        - check_out must be strictly after check_in (no same-day stays)
        - Maximum stay length is 90 nights
        """
        if self.check_in is None or self.check_out is None:
            return self

        if self.check_out <= self.check_in:
            raise ValueError(
                "Check-out date must be after check-in date. "
                "Same-day stays are not permitted."
            )

        nights = (self.check_out - self.check_in).days
        if nights > 90:
            raise ValueError(
                f"Stay length of {nights} nights exceeds the 90-night maximum."
            )

        return self


class UpdateReservationRequest(_StrictBase):
    """
    PATCH /staff/reservations/<id>

    Allows front desk to update dates on a PENDING reservation.
    All fields are optional — only provided fields are changed.
    Cannot be used on ACTIVE or CHECKED_OUT reservations (enforced in route).
    """

    check_in: Annotated[
        date | None,
        Field(default=None, description="New arrival date"),
    ]

    check_out: Annotated[
        date | None,
        Field(default=None, description="New departure date"),
    ]

    guest_name: Annotated[
        str | None,
        Field(default=None, min_length=2, max_length=120),
    ]

    guest_email: Annotated[
        str | None,
        Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    ]

    @field_validator("check_in")
    @classmethod
    def check_in_not_past(cls, v: date | None) -> date | None:
        if v is not None and v < date.today():
            raise ValueError(f"Check-in date {v} is in the past.")
        return v

    @model_validator(mode="after")
    def validate_date_range(self) -> UpdateReservationRequest:
        """Only validate date range if both dates are provided in this update."""
        if self.check_in is not None and self.check_out is not None:
            if self.check_out <= self.check_in:
                raise ValueError("Check-out must be after check-in.")
            nights = (self.check_out - self.check_in).days
            if nights > 90:
                raise ValueError(
                    f"Stay of {nights} nights exceeds the 90-night maximum."
                )
        return self


class CancelReservationRequest(_StrictBase):
    """
    POST /staff/reservations/<id>/cancel

    Cancels a PENDING reservation. Requires an explicit reason string
    so there is an audit record of why the booking was cancelled.
    """

    reason: Annotated[
        str,
        Field(
            min_length=5,
            max_length=500,
            description="Reason for cancellation (kept for audit log)",
        ),
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Response schemas
# ══════════════════════════════════════════════════════════════════════════════

class ReservationOut(_StrictBase):
    """
    Returned by GET /staff/reservations and POST /staff/reservations.

    Dates are serialized as ISO strings (YYYY-MM-DD) for JSON compatibility.
    guest_name and guest_email are included only while the stay is active —
    after checkout, both are None (purged from the Guest row).
    password_hash and token never appear here — not declared, so not possible.
    """

    model_config = {
        "extra": "forbid",
        "from_attributes": True,
    }

    id:         int
    room_id:    int
    status:     ReservationStatus
    check_in:   date
    check_out:  date
    nights:     int
    created_at: datetime
    updated_at: datetime

    # Guest identity — None after checkout (PII purged)
    guest_id:   int | None
    guest_name: str | None = None
    guest_email: str | None = None

    @classmethod
    def from_orm_with_guest(cls, reservation) -> ReservationOut:
        """
        Build a ReservationOut from an ORM Reservation object,
        pulling guest_name and guest_email from the linked Guest row
        if it exists and the stay is not yet checked out.

        Usage in route handlers:
            out = ReservationOut.from_orm_with_guest(reservation)
            return jsonify(out.model_dump(mode='json')), 200
        """
        guest = getattr(reservation, "guest", None)
        return cls(
            id=reservation.id,
            room_id=reservation.room_id,
            status=reservation.status,
            check_in=reservation.check_in,
            check_out=reservation.check_out,
            nights=reservation.nights,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            guest_id=reservation.guest_id,
            guest_name=guest.full_name if guest else None,
            guest_email=guest.email if guest else None,
        )


class GuestBookingOut(_StrictBase):
    """Response returned after a public guest booking is created."""

    message: str = "Reservation booked successfully."
    reservation: ReservationOut
    guest_token: str


class ReservationListOut(_StrictBase):
    """Paginated list wrapper for GET /staff/reservations."""

    reservations: list[ReservationOut]
    total:        int
    status_filter: ReservationStatus | None = None


class CheckInOut(_StrictBase):
    """Response returned after a successful check-in."""

    message:        str = "Guest checked in successfully."
    reservation_id: int
    room_id:        int
    check_out:      date


class CheckOutOut(_StrictBase):
    """
    Response returned after a successful checkout.
    Confirms PII purge so front desk has a record.
    """

    message:        str = "Guest checked out. PII purged."
    reservation_id: int
    room_id:        int
    checked_out_at: datetime


class AvailabilityOut(_StrictBase):
    """
    Response for a room availability check.
    Used by front desk before creating a new reservation.
    """

    room_id:   int
    available: bool
    conflicts: list[ReservationOut] = []    # overlapping reservations if not available