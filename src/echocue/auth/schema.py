"""Authentication data schemas.

This module defines service-layer structs, request schemas, and API view objects.
Schemas describe authentication data boundaries and do not perform database I/O or response construction.
"""

from datetime import datetime
from uuid import UUID

from echocue.base import BaseStruct, CamelizedBaseStruct

from .enum import (
    AccountCertificationStatus,
    OrganizationMemberRole,
    RoomAuthorizationScope,
    RoomAuthorizationStatus,
    RoomOwnershipKind,
)

__all__ = (
    "AccountCertificationStatus",
    "AccountCertificationStruct",
    "AuthSessionVO",
    "LoginRequest",
    "OrganizationMemberRole",
    "OrganizationMemberStruct",
    "OrganizationStruct",
    "RoomAuthorizationScope",
    "RoomAuthorizationStatus",
    "RoomAuthorizationStruct",
    "RoomOwnershipKind",
    "RoomStruct",
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


class AccountCertificationStruct(BaseStruct):
    """Certification state bound to a platform account."""

    user_id: UUID
    status: AccountCertificationStatus = AccountCertificationStatus.UNCERTIFIED
    organization_id: UUID | None = None
    certified_at: datetime | None = None
    revoked_at: datetime | None = None
    note: str | None = None


class OrganizationStruct(BaseStruct):
    """Organization data visible to auth services."""

    name: str
    owner_user_id: UUID
    description: str | None = None
    is_active: bool = True


class OrganizationMemberStruct(BaseStruct):
    """Organization membership record."""

    organization_id: UUID
    user_id: UUID
    role: OrganizationMemberRole = OrganizationMemberRole.MEMBER
    is_active: bool = True


class RoomStruct(BaseStruct):
    """Live room ownership record."""

    room_id: str
    room_kind: RoomOwnershipKind = RoomOwnershipKind.PERSONAL
    owner_user_id: UUID | None = None
    organization_id: UUID | None = None
    is_active: bool = True


class RoomAuthorizationStruct(BaseStruct):
    """Room authorization record for organization members."""

    room_id: str
    organization_id: UUID
    user_id: UUID
    access_scope: RoomAuthorizationScope = RoomAuthorizationScope.VIEW
    status: RoomAuthorizationStatus = RoomAuthorizationStatus.ACTIVE
    granted_by_user_id: UUID | None = None
    expires_at: datetime | None = None
    note: str | None = None


class LoginRequest(CamelizedBaseStruct):
    """Login request body."""

    username: str
    password: str


class AuthSessionVO(CamelizedBaseStruct):
    """Authentication session response data."""

    expires_in: int
    user: UserVO
