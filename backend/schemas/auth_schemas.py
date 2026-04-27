from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from models.staff import StaffRole


# Shared config
class _StrictBase(BaseModel):
    """
    Base for all AirBnoB schemas.

    extra='forbid' rejects any fields not declared in the schema.
    This prevents parameter pollution attacks where a client sends
    extra keys hoping one of them gets forwarded to the DB layer.
    """
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


def _reject_unsafe_password_input(value: str) -> str:
    """
    Reject password inputs containing control characters or HTML/script payloads.

    Passwords are not rendered back to the browser, but we still treat obvious
    markup payloads as invalid input at the API boundary for defense in depth.
    """
    lowered = value.lower()
    if "\x00" in value:
        raise ValueError("Password contains invalid characters.")
    if "<script" in lowered or "</script" in lowered or "<" in value or ">" in value:
        raise ValueError("Password contains invalid characters.")
    return value


# Request schemas  (incoming — validate strictly)
class AdminLoginRequest(_StrictBase):
    """
    POST /auth/staff/login

    Validates admin and front-desk login credentials before they reach
    the DB layer. Email is normalised to lowercase so lookups are
    case-insensitive without a DB-level ILIKE query.
    """

    email: Annotated[
        EmailStr,
        Field(description="Staff email address"),
    ]

    password: Annotated[
        str,
        Field(
            min_length=8,
            max_length=128,     # prevents bcrypt DoS via very long inputs
            description="Staff password",
        ),
    ]

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        """Lowercase + strip so 'Admin@Hotel.com' matches 'admin@hotel.com'."""
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        """
        Null bytes in passwords can truncate bcrypt input silently.
        Reject them explicitly rather than letting bcrypt see a shorter string.
        """
        return _reject_unsafe_password_input(v)


class GuestTokenRequest(_StrictBase):
    """
    POST /auth/guest/verify

    Validates a guest QR token before the DB lookup.
    UUID4 format is enforced so malformed strings are rejected at Layer 1.
    """

    token: Annotated[
        str,
        Field(
            min_length=36,
            max_length=36,
            description="UUID4 token from the guest's QR code",
            pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        ),
    ]


class CreateStaffRequest(_StrictBase):
    """
    POST /admin/staff  (admin only)

    Used by an admin to create a new staff account.
    Password strength is validated here before hashing.
    """

    email: Annotated[EmailStr, Field(description="New staff member's email")]

    full_name: Annotated[
        str,
        Field(min_length=2, max_length=120, description="Full display name"),
    ]

    password: Annotated[
        str,
        Field(min_length=10, max_length=128, description="Initial password"),
    ]

    role: Annotated[
        StaffRole,
        Field(description="'admin' or 'front_desk'"),
    ]

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return " ".join(v.split())      # collapse internal whitespace

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Enforce a basic strength policy for staff accounts:
        at least one uppercase letter, one digit, one special character.
        Guests have no passwords so this only applies to staff creation.
        """
        v = _reject_unsafe_password_input(v)
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
            raise ValueError("Password must contain at least one special character.")
        return v


class ChangePasswordRequest(_StrictBase):
    """
    POST /auth/staff/change-password

    Requires the current password before accepting a new one.
    The model_validator checks that old and new passwords differ.
    """

    current_password: Annotated[
        str,
        Field(min_length=8, max_length=128),
    ]

    new_password: Annotated[
        str,
        Field(min_length=10, max_length=128),
    ]

    @field_validator("current_password", "new_password")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        return _reject_unsafe_password_input(v)

    @model_validator(mode="after")
    def passwords_must_differ(self) -> ChangePasswordRequest:
        if self.current_password == self.new_password:
            raise ValueError("New password must differ from current password.")
        return self


# ══════════════════════════════════════════════════════════════════════════════
# Response schemas  (outgoing — control exactly what is exposed)
# ══════════════════════════════════════════════════════════════════════════════

class StaffOut(_StrictBase):
    """
    Returned on successful login and from GET /auth/staff/me.

    password_hash is explicitly absent — it must never appear in any
    API response. from_attributes=True allows model_validate(staff_orm_obj).
    """

    model_config = {"extra": "forbid", "from_attributes": True}

    id:        int
    email:     str
    full_name: str
    role:      StaffRole
    is_active: bool


class TokenResponse(_StrictBase):
    """
    Returned alongside the HttpOnly cookie on successful login.
    The actual JWT value travels in the cookie — this body confirms
    auth succeeded and provides role context to the frontend.
    """

    message:   str = "Login successful."
    role:      StaffRole
    full_name: str


class GuestSessionOut(_StrictBase):
    """
    Returned when a guest token is verified successfully.
    Provides the room number and stay window — nothing else.
    """

    room_id:    int
    check_in:   str     # ISO date string: "2025-09-01"
    check_out:  str     # ISO date string: "2025-09-05"
    message:    str = "Token verified."


class ErrorResponse(_StrictBase):
    """
    Consistent error shape across all 4xx and 5xx responses.
    The 'detail' key mirrors FastAPI convention so the frontend
    always knows where to read the error message.
    """

    model_config = {"extra": "forbid"}

    detail: str


# ══════════════════════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════════════════════

def error(message: str) -> dict:
    """
    Shorthand for building an error response dict in route handlers.

    Usage:
        from schemas.auth_schemas import error
        return jsonify(error("Invalid credentials.")), 401
    """
    return ErrorResponse(detail=message).model_dump()
