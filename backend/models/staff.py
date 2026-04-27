"""
AirBnoB — Staff Model
======================
backend/models/staff.py

Represents hotel admin and front-desk employees.
Guests are NOT stored here — they use ephemeral tokens (see guest.py).
"""

from __future__ import annotations

import re
from enum import StrEnum

import bcrypt
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

_BCRYPT_ROUNDS = 12


def _parse_bcrypt_rounds(hash_value: str) -> int | None:
    match = re.match(r"^\$2[abxy]?\$(\d{2})\$", hash_value)
    if match is None:
        return None
    return int(match.group(1))


# Role enum
class StaffRole(StrEnum):
    """
    Two-tier role system per the proposal's access control design.

    ADMIN      — full access: pricing, billing, user management, all staff routes
    FRONT_DESK — operational access: reservations, check-in, check-out only
    """
    ADMIN      = "admin"
    FRONT_DESK = "front_desk"


# Staff ORM model
class Staff(Base):
    """
    Maps to the 'staff' table in PostgreSQL.

    Design decisions:
    - password_hash stores bcrypt digest only — plaintext never persists
    - role column is constrained to StaffRole values via String length + app logic
    - email is normalised to lowercase before storage (enforced in Pydantic schema)
    - No address, phone, or other PII columns — minimal data per proposal
    """

    __tablename__ = "staff"

    __table_args__ = (
        UniqueConstraint("email", name="uq_staff_email"),
    )

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identity
    email: Mapped[str] = mapped_column(
        String(254),        # RFC 5321 max email length
        nullable=False,
        index=True,         # fast lookup on login
    )

    full_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    # Auth
    password_hash: Mapped[str] = mapped_column(
        String(255),        # bcrypt output is 60 chars; 255 gives safe headroom
                            # for any future hash format without risk of truncation
        nullable=False,
    )

    # RBAC
    role: Mapped[str] = mapped_column(
        String(20),         # stores "admin" or "front_desk"
        nullable=False,
    )

    # Soft delete flag (deactivate without losing audit history)
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    # Password helpers

    @staticmethod
    def hash_password(plain: str) -> str:
        """
        Hash a plaintext password with bcrypt (cost 12).
        Call this when creating or updating a staff account — never store plain.

        Example:
            staff.password_hash = Staff.hash_password("SecurePass123!")
        """
        salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
        return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, plain: str) -> bool:
        """
        Constant-time bcrypt comparison.
        Returns True if plain matches the stored hash, False otherwise.

        Note: call pwd_ctx.dummy_verify() on a login miss BEFORE calling this
        so that timing is uniform whether or not the account exists.
        (Handled in admin_auth.py, not here.)
        """
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), self.password_hash.encode("utf-8"))
        except ValueError:
            return False

    def needs_rehash(self) -> bool:
        """
        Returns True if the stored hash was made with fewer than the current
        bcrypt rounds. Use this to transparently upgrade hashes on next login.

        Example in admin_auth.py:
            if staff.needs_rehash():
                staff.password_hash = Staff.hash_password(plain)
                session.commit()
        """
        rounds = _parse_bcrypt_rounds(self.password_hash)
        return rounds is None or rounds < _BCRYPT_ROUNDS

    # Role helpers

    def is_admin(self) -> bool:
        return self.role == StaffRole.ADMIN

    def is_front_desk(self) -> bool:
        return self.role == StaffRole.FRONT_DESK

    # Dunder

    def __repr__(self) -> str:
        return f"<Staff id={self.id} email={self.email!r} role={self.role!r}>"