from __future__ import annotations

import re
from enum import Enum

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass

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
   
    ADMIN      = "admin"
    FRONT_DESK = "front_desk"


# Staff ORM model
class Staff(Base):
  
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
     
        salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
        return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, plain: str) -> bool:
        
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), self.password_hash.encode("utf-8"))
        except ValueError:
            return False

    def needs_rehash(self) -> bool:
        
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