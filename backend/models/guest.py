from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from database import Base


# Guest ORM model
class Guest(Base):
 

    __tablename__ = "guests"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # QR token \u2014 the guest's only credential
    token: Mapped[str] = mapped_column(
        String(36),             # UUID4 canonical form: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        unique=True,
        nullable=False,
        index=True,             # fast lookup on every door/kiosk scan
        default=lambda: str(uuid.uuid4()),
    )

    # Stay details
    room_id: Mapped[int] = mapped_column(nullable=False)

    check_in: Mapped[date] = mapped_column(Date, nullable=False)

    check_out: Mapped[date] = mapped_column(Date, nullable=False)

    # Minimal PII (purged at checkout)
    # Stored only so front desk can identify the guest during their stay.
    # Both fields are set to None by purge_pii() on checkout.
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email:     Mapped[str | None] = mapped_column(String(254), nullable=True)

    # Lifecycle timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    checked_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,          # None until checkout is processed
    )

    # Token helpers

    def is_valid_token(self) -> bool:
        """
        A token is valid if:
          1. The guest has not yet checked out
          2. Today's date is within the booked stay window

        Call this on every QR scan in guest_auth.py before issuing a session.
        """
        today = date.today()
        not_checked_out = self.checked_out_at is None
        within_window   = self.check_in <= today <= self.check_out
        return not_checked_out and within_window

    def is_expired(self) -> bool:
        """Token is expired if today is past the check_out date."""
        return date.today() > self.check_out

    # PII helpers

    def purge_pii(self, session: Session) -> None:
        
        self.full_name      = None
        self.email          = None
        self.checked_out_at = datetime.now(tz=timezone.utc)
        session.add(self)

    # Class-level helpers

    @classmethod
    def get_by_token(cls, session: Session, token: str) -> Guest | None:
        
        stmt = select(cls).where(cls.token == token)
        return session.scalars(stmt).first()

    @classmethod
    def purge_expired(cls, session: Session) -> int:
        
        today = date.today()
        stmt = select(cls).where(
            cls.check_out < today,
            cls.checked_out_at.is_(None),       # not yet cleaned
            (cls.full_name.is_not(None)) | (cls.email.is_not(None)),
        )
        expired = session.scalars(stmt).all()

        for guest in expired:
            guest.full_name      = None
            guest.email          = None
            guest.checked_out_at = datetime.now(tz=timezone.utc)

        session.commit()
        return len(expired)

    @classmethod
    def generate_token(cls) -> str:
        """Generate a fresh UUID4 token. Use when creating a new guest row."""
        return str(uuid.uuid4())

    # Dunder

    def __repr__(self) -> str:
        return (
            f"<Guest id={self.id} room={self.room_id} "
            f"check_in={self.check_in} check_out={self.check_out} "
            f"checked_out_at={self.checked_out_at!r}>"
        )