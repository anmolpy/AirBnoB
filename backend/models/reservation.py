"""
AirBnoB — Reservation Model
=============================
backend/models/reservation.py

Links a guest token to a room and a date range.
A reservation is created by front desk at booking time and transitions
through three states: pending → active → checked_out.

No PII beyond what is strictly required to manage the booking is stored here.
Guest identity is referenced via guest_id FK — personal details live (briefly)
on the Guest row and are purged at checkout.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from database import Base


# Status enum
class ReservationStatus(StrEnum):
    """
    Lifecycle states of a reservation.

    PENDING     — booked but guest has not yet arrived
    ACTIVE      — guest has checked in, QR token is live
    CHECKED_OUT — stay complete, guest PII has been purged
    CANCELLED   — reservation cancelled before check-in
    """
    PENDING     = "pending"
    ACTIVE      = "active"
    CHECKED_OUT = "checked_out"
    CANCELLED   = "cancelled"


# Reservation ORM model
class Reservation(Base):
    """
    Maps to the 'reservations' table in PostgreSQL.

    Design decisions:
    - guest_id FK links to guests.id — no name/email duplicated here
    - room_id is a plain integer (Room model lives in Sushil's schema work)
    - status drives the checkout flow and determines token validity
    - No payment data stored — out of scope per proposal
    """

    __tablename__ = "reservations"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to Guest
    # ON DELETE SET NULL: if a guest row is hard-deleted, reservation history
    # is preserved with guest_id = NULL rather than cascade-deleting records.
    guest_id: Mapped[int | None] = mapped_column(
        ForeignKey("guests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Room reference
    # Integer FK \u2014 Room model is part of Sushil's schema work.
    # No ForeignKey constraint here yet; add once Room model exists.
    room_id: Mapped[int] = mapped_column(nullable=False, index=True)

    # Stay window
    check_in: Mapped[date]  = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReservationStatus.PENDING,
        index=True,             # frequently filtered by status in staff views
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),    # auto-updates on every row change
        nullable=False,
    )

    # Relationship back to Guest
    # lazy="select" (default) — Guest is loaded only when accessed.
    # Use .guest to read check_in/check_out or call guest.purge_pii().
    guest: Mapped["Guest | None"] = relationship(   # type: ignore[name-defined]
        "Guest",
        lazy="select",
        foreign_keys=[guest_id],
    )

    # State transition helpers

    def check_in_guest(self, session: Session) -> None:
        """
        Transition: PENDING → ACTIVE.

        Called by the staff check-in route when the guest arrives.
        Validates the current status before transitioning so a reservation
        can't be activated twice or after cancellation.

        Raises:
            ValueError if the reservation is not in PENDING status.
        """
        if self.status != ReservationStatus.PENDING:
            raise ValueError(
                f"Cannot check in: reservation is '{self.status}', expected 'pending'."
            )
        self.status     = ReservationStatus.ACTIVE
        self.updated_at = datetime.now(tz=timezone.utc)
        session.add(self)
        session.commit()

    def check_out_guest(self, session: Session) -> None:
        """
        Transition: ACTIVE → CHECKED_OUT.

        Called by the staff checkout route. Transitions the reservation status
        then immediately purges PII from the linked Guest row.
        Both changes happen in the same commit — no window where status is
        checked_out but PII still exists.

        Raises:
            ValueError if the reservation is not in ACTIVE status.
        """
        if self.status != ReservationStatus.ACTIVE:
            raise ValueError(
                f"Cannot check out: reservation is '{self.status}', expected 'active'."
            )

        self.status     = ReservationStatus.CHECKED_OUT
        self.updated_at = datetime.now(tz=timezone.utc)
        session.add(self)

        # Purge guest PII atomically in the same transaction
        if self.guest is not None:
            self.guest.purge_pii(session)
        else:
            session.commit()

    def cancel(self, session: Session) -> None:
        """
        Transition: PENDING → CANCELLED.

        Only pending reservations can be cancelled. Active stays must be
        checked out through the normal flow first.

        Raises:
            ValueError if the reservation is not in PENDING status.
        """
        if self.status != ReservationStatus.PENDING:
            raise ValueError(
                f"Cannot cancel: reservation is '{self.status}', expected 'pending'."
            )
        self.status     = ReservationStatus.CANCELLED
        self.updated_at = datetime.now(tz=timezone.utc)
        session.add(self)
        session.commit()

    # Query helpers

    @classmethod
    def get_active(cls, session: Session) -> list[Reservation]:
        """
        Return all currently active reservations.
        Used by the staff dashboard to show who is currently checked in.
        """
        stmt = (
            select(cls)
            .where(cls.status == ReservationStatus.ACTIVE)
            .order_by(cls.check_out)   # soonest departures first
        )
        return list(session.scalars(stmt).all())

    @classmethod
    def get_pending(cls, session: Session) -> list[Reservation]:
        """
        Return all pending reservations (arriving guests).
        Filtered to check_in >= today so historical pending records
        from cancelled stays don't surface.
        """
        stmt = (
            select(cls)
            .where(
                cls.status == ReservationStatus.PENDING,
                cls.check_in >= date.today(),
            )
            .order_by(cls.check_in)     # soonest arrivals first
        )
        return list(session.scalars(stmt).all())

    @classmethod
    def get_by_room(cls, session: Session, room_id: int) -> list[Reservation]:
        """
        Return all non-cancelled reservations for a specific room.
        Used by front desk to check room availability before booking.
        """
        stmt = (
            select(cls)
            .where(
                cls.room_id == room_id,
                cls.status != ReservationStatus.CANCELLED,
            )
            .order_by(cls.check_in)
        )
        return list(session.scalars(stmt).all())

    @classmethod
    def get_by_guest(cls, session: Session, guest_id: int) -> list[Reservation]:
        """Return all reservations linked to a specific guest row."""
        stmt = select(cls).where(cls.guest_id == guest_id).order_by(cls.check_in)
        return list(session.scalars(stmt).all())

    # Properties

    @property
    def nights(self) -> int:
        """Number of nights booked."""
        return (self.check_out - self.check_in).days

    @property
    def is_current(self) -> bool:
        """True if today falls within the booked window."""
        return self.check_in <= date.today() <= self.check_out

    # Dunder

    def __repr__(self) -> str:
        return (
            f"<Reservation id={self.id} room={self.room_id} "
            f"guest_id={self.guest_id} status={self.status!r} "
            f"{self.check_in} → {self.check_out}>"
        )