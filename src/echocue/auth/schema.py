"""Authentication data schemas.

This module defines service-layer structs, request schemas, and API view objects.
Schemas describe authentication data boundaries and do not perform database I/O or response construction.
"""

from uuid import UUID

from echocue.base import BaseStruct, CamelizedBaseStruct

__all__ = (
    "AuthSessionVO",
    "LoginRequest",
    "UserStruct",
    "UserVO",
)


class UserStruct(BaseStruct):
    """Service-layer user data."""

    id: UUID
    username: str
    email: str | None = None
    is_active: bool = True
    is_superuser: bool = False


class UserVO(CamelizedBaseStruct):
    """User view object returned by API endpoints."""

    id: UUID
    username: str
    is_active: bool
    is_superuser: bool
    email: str | None = None

    @classmethod
    def from_struct(cls, data: UserStruct) -> "UserVO":
        """Build a user view object from service-layer data."""

        return cls(**data.to_dict())


class LoginRequest(CamelizedBaseStruct):
    """Login request body."""

    username: str
    password: str


class AuthSessionVO(CamelizedBaseStruct):
    """Authentication session response data."""

    expires_in: int
    user: UserVO
