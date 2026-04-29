from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass

from sqlalchemy import Date, DateTime, ForeignKey, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
from sqlalchemy.orm import scoped_session

from database import Base


# Status enum
class ReservationStatus(StrEnum):
    PENDING     = "pending"
    ACTIVE      = "active"
    CHECKED_OUT = "checked_out"
    CANCELLED   = "cancelled"


# Reservation ORM model
class Reservation(Base):
    

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

    def check_in_guest(self, session: Any) -> None:
       
        if self.status != ReservationStatus.PENDING:
            raise ValueError(
                f"Cannot check in: reservation is '{self.status}', expected 'pending'."
            )
        self.status     = ReservationStatus.ACTIVE
        self.updated_at = datetime.now(tz=timezone.utc)
        session.add(self)
        session.commit()

    def check_out_guest(self, session: Any) -> None:
       
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
            session.commit()
        else:
            session.commit()

    def cancel(self, session: Any) -> None:
        
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
    def get_active(cls, session: Any) -> list[Reservation]:
       
        stmt = (
            select(cls)
            .where(cls.status == ReservationStatus.ACTIVE)
            .order_by(cls.check_out)   # soonest departures first
        )
        return list(session.scalars(stmt).all())

    @classmethod
    def get_pending(cls, session: Any) -> list[Reservation]:
        
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
    def get_by_room(cls, session: Any, room_id: int) -> list[Reservation]:
        
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
    def get_by_guest(cls, session: Any, guest_id: int) -> list[Reservation]:
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