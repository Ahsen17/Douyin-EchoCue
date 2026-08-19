"""Authentication persistence models.

This module defines database mappings for account, certification, organization, room, and authorization data.
Models are used only for persistence and are not returned directly from controllers.
"""

from datetime import datetime
from uuid import UUID

from advanced_alchemy.types.password_hash.base import PasswordHash
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from echocue.shared import CustomModel

from .enum import (
    AccountCertificationStatus,
    OrganizationMemberRole,
    RoomAuthorizationScope,
    RoomAuthorizationStatus,
    RoomOwnershipKind,
)
from .password import password_hasher
from .schema import (
    AccountCertificationStruct,
    OrganizationMemberStruct,
    OrganizationStruct,
    RoomAuthorizationStruct,
    RoomStruct,
    UserStruct,
)

__all__ = (
    "AccountCertificationModel",
    "OrganizationMemberModel",
    "OrganizationModel",
    "RoomAuthorizationModel",
    "RoomModel",
    "UserModel",
)


class UserModel(CustomModel[UserStruct]):
    """User persistence model."""

    __struct_type__ = UserStruct

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(PasswordHash(password_hasher))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)


class AccountCertificationModel(CustomModel[AccountCertificationStruct]):
    """Account certification persistence model."""

    __struct_type__ = AccountCertificationStruct

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_model.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=AccountCertificationStatus.UNCERTIFIED.value,
        index=True,
    )
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_model.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    certified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class OrganizationModel(CustomModel[OrganizationStruct]):
    """Organization persistence model."""

    __struct_type__ = OrganizationStruct

    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_model.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OrganizationMemberModel(CustomModel[OrganizationMemberStruct]):
    """Organization membership persistence model."""

    __struct_type__ = OrganizationMemberStruct

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_model.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_model.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(32),
        default=OrganizationMemberRole.MEMBER.value,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_organization_member_user"),)


class RoomModel(CustomModel[RoomStruct]):
    """Live room ownership persistence model."""

    __struct_type__ = RoomStruct

    room_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    room_kind: Mapped[str] = mapped_column(
        String(32),
        default=RoomOwnershipKind.PERSONAL.value,
        index=True,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_model.id", ondelete="CASCADE"),
        unique=True,
        nullable=True,
        index=True,
    )
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_model.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint(
            "(room_kind = 'personal' AND owner_user_id IS NOT NULL AND organization_id IS NULL) "
            "OR (room_kind = 'organization' AND organization_id IS NOT NULL AND owner_user_id IS NULL)",
            name="ck_room_owner_kind",
        ),
    )


class RoomAuthorizationModel(CustomModel[RoomAuthorizationStruct]):
    """Room authorization persistence model."""

    __struct_type__ = RoomAuthorizationStruct

    room_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("room_model.room_id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization_model.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_model.id", ondelete="CASCADE"),
        index=True,
    )
    access_scope: Mapped[str] = mapped_column(
        String(32),
        default=RoomAuthorizationScope.VIEW.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=RoomAuthorizationStatus.ACTIVE.value,
        index=True,
    )
    granted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_model.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "room_id",
            "organization_id",
            "user_id",
            "access_scope",
            name="uq_room_authorization_grant",
        ),
    )
