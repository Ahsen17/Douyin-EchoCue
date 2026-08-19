"""Authentication data schemas.

This module defines service-layer structs, request schemas, and API view objects.
Schemas describe authentication data boundaries and do not perform database I/O or response construction.
"""

from datetime import datetime
from uuid import UUID

from msgspec import field

from echocue.base import BaseStruct, CamelizedBaseStruct

from .enum import (
    AccountCertificationStatus,
    OrganizationMemberRole,
    PermissionAction,
    RoomAuthorizationScope,
    RoomAuthorizationStatus,
    RoomOwnershipKind,
)

__all__ = (
    "AccountCertificationStatus",
    "AccountCertificationStruct",
    "AccountCertificationVO",
    "AuthSessionVO",
    "AuthenticationResultStruct",
    "LoginRequest",
    "OrganizationMemberRole",
    "OrganizationMemberStruct",
    "OrganizationMemberVO",
    "OrganizationStruct",
    "OrganizationVO",
    "PermissionAction",
    "PermissionCheckRequest",
    "PermissionCheckRequestStruct",
    "PermissionCheckResultStruct",
    "PermissionCheckVO",
    "PermissionContextStruct",
    "PermissionContextVO",
    "RoomAuthorizationScope",
    "RoomAuthorizationStatus",
    "RoomAuthorizationStruct",
    "RoomAuthorizationVO",
    "RoomOwnershipKind",
    "RoomStruct",
    "RoomVO",
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
    id: UUID | None = None
    status: AccountCertificationStatus = AccountCertificationStatus.UNCERTIFIED
    organization_id: UUID | None = None
    certified_at: datetime | None = None
    revoked_at: datetime | None = None
    note: str | None = None


class OrganizationStruct(BaseStruct):
    """Organization data visible to auth services."""

    name: str
    owner_user_id: UUID
    id: UUID | None = None
    description: str | None = None
    is_active: bool = True


class OrganizationMemberStruct(BaseStruct):
    """Organization membership record."""

    organization_id: UUID
    user_id: UUID
    id: UUID | None = None
    role: OrganizationMemberRole = OrganizationMemberRole.MEMBER
    is_active: bool = True


class RoomStruct(BaseStruct):
    """Live room ownership record."""

    room_id: str
    id: UUID | None = None
    room_kind: RoomOwnershipKind = RoomOwnershipKind.PERSONAL
    owner_user_id: UUID | None = None
    organization_id: UUID | None = None
    is_active: bool = True


class RoomAuthorizationStruct(BaseStruct):
    """Room authorization record for organization members."""

    room_id: str
    organization_id: UUID
    user_id: UUID
    id: UUID | None = None
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


class PermissionContextStruct(BaseStruct):
    """Permission context returned by auth services."""

    user: UserStruct
    certification: AccountCertificationStruct | None = None
    organizations: list[OrganizationStruct] = field(default_factory=list)
    memberships: list[OrganizationMemberStruct] = field(default_factory=list)
    rooms: list[RoomStruct] = field(default_factory=list)
    room_authorizations: list[RoomAuthorizationStruct] = field(default_factory=list)


class AccountCertificationVO(CamelizedBaseStruct):
    """Certification state returned by API endpoints."""

    user_id: UUID
    id: UUID | None = None
    status: AccountCertificationStatus = AccountCertificationStatus.UNCERTIFIED
    organization_id: UUID | None = None
    certified_at: datetime | None = None
    revoked_at: datetime | None = None
    note: str | None = None

    @classmethod
    def from_struct(cls, data: AccountCertificationStruct) -> "AccountCertificationVO":
        """Build a certification view object from service-layer data."""

        return cls(**data.to_dict())


class OrganizationVO(CamelizedBaseStruct):
    """Organization data returned by API endpoints."""

    name: str
    owner_user_id: UUID
    id: UUID | None = None
    description: str | None = None
    is_active: bool = True

    @classmethod
    def from_struct(cls, data: OrganizationStruct) -> "OrganizationVO":
        """Build an organization view object from service-layer data."""

        return cls(**data.to_dict())


class OrganizationMemberVO(CamelizedBaseStruct):
    """Organization membership returned by API endpoints."""

    organization_id: UUID
    user_id: UUID
    id: UUID | None = None
    role: OrganizationMemberRole = OrganizationMemberRole.MEMBER
    is_active: bool = True

    @classmethod
    def from_struct(cls, data: OrganizationMemberStruct) -> "OrganizationMemberVO":
        """Build an organization member view object from service-layer data."""

        return cls(**data.to_dict())


class RoomVO(CamelizedBaseStruct):
    """Live room ownership returned by API endpoints."""

    room_id: str
    id: UUID | None = None
    room_kind: RoomOwnershipKind = RoomOwnershipKind.PERSONAL
    owner_user_id: UUID | None = None
    organization_id: UUID | None = None
    is_active: bool = True

    @classmethod
    def from_struct(cls, data: RoomStruct) -> "RoomVO":
        """Build a room view object from service-layer data."""

        return cls(**data.to_dict())


class RoomAuthorizationVO(CamelizedBaseStruct):
    """Room authorization returned by API endpoints."""

    room_id: str
    organization_id: UUID
    user_id: UUID
    id: UUID | None = None
    access_scope: RoomAuthorizationScope = RoomAuthorizationScope.VIEW
    status: RoomAuthorizationStatus = RoomAuthorizationStatus.ACTIVE
    granted_by_user_id: UUID | None = None
    expires_at: datetime | None = None
    note: str | None = None

    @classmethod
    def from_struct(cls, data: RoomAuthorizationStruct) -> "RoomAuthorizationVO":
        """Build a room authorization view object from service-layer data."""

        return cls(**data.to_dict())


class PermissionContextVO(CamelizedBaseStruct):
    """Permission context returned by API endpoints."""

    user: UserVO
    certification: AccountCertificationVO | None = None
    organizations: list[OrganizationVO] = field(default_factory=list)
    memberships: list[OrganizationMemberVO] = field(default_factory=list)
    rooms: list[RoomVO] = field(default_factory=list)
    room_authorizations: list[RoomAuthorizationVO] = field(default_factory=list)

    @classmethod
    def from_struct(cls, data: PermissionContextStruct) -> "PermissionContextVO":
        """Build a permission context view object from service-layer data."""

        return cls(
            user=UserVO.from_struct(data.user),
            certification=AccountCertificationVO.from_struct(data.certification)
            if data.certification is not None
            else None,
            organizations=[OrganizationVO.from_struct(item) for item in data.organizations],
            memberships=[OrganizationMemberVO.from_struct(item) for item in data.memberships],
            rooms=[RoomVO.from_struct(item) for item in data.rooms],
            room_authorizations=[RoomAuthorizationVO.from_struct(item) for item in data.room_authorizations],
        )


class AuthenticationResultStruct(BaseStruct):
    """Authentication result with full permission context."""

    user: UserStruct
    context: PermissionContextStruct


class PermissionCheckRequestStruct(BaseStruct):
    """Room permission check request."""

    user_id: UUID
    room_id: str
    action: PermissionAction


class PermissionCheckRequest(CamelizedBaseStruct):
    """Room permission check request body."""

    room_id: str
    action: PermissionAction


class PermissionCheckResultStruct(BaseStruct):
    """Room permission check result."""

    allowed: bool
    reason: str
    matched_scope: RoomAuthorizationScope | None = None


class PermissionCheckVO(CamelizedBaseStruct):
    """Room permission check result returned by API endpoints."""

    allowed: bool
    reason: str
    matched_scope: RoomAuthorizationScope | None = None

    @classmethod
    def from_struct(cls, data: PermissionCheckResultStruct) -> "PermissionCheckVO":
        """Build a permission check view object from service-layer data."""

        return cls(**data.to_dict())
