"""Authentication domain services.

This module handles user lookup, password verification, and login state checks.
Services return service-layer structs and do not expose database models to controllers.
"""

from collections.abc import Sequence
from uuid import UUID

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.types.password_hash.base import HashedPassword
from litestar.exceptions import NotAuthorizedException

from echocue.shared import CustomService

from .exception import UserDisabledError
from .model import (
    AccountCertificationModel,
    OrganizationMemberModel,
    OrganizationModel,
    RoomAuthorizationModel,
    RoomModel,
    UserModel,
)
from .password import password_hasher
from .schema import (
    AccountCertificationStruct,
    LoginRequest,
    OrganizationMemberStruct,
    OrganizationStruct,
    RoomAuthorizationStruct,
    RoomStruct,
    UserStruct,
)

__all__ = (
    "AccountCertificationService",
    "OrganizationMemberService",
    "OrganizationService",
    "RoomAuthorizationService",
    "RoomService",
    "UserService",
)


class UserService(CustomService[UserModel]):
    """User database service."""

    class _Repository(SQLAlchemyAsyncRepository[UserModel]):
        """User model repository."""

        model_type: type[UserModel] = UserModel

    repository_type = _Repository

    async def get_by_id(self, user_id: UUID) -> UserStruct | None:
        """Get active or inactive user data by primary key."""

        user = await self.get_one_or_none(id=user_id)

        return user.to_struct() if user else None

    async def get_by_username(self, username: str) -> UserModel | None:
        """Get a user model by username."""

        return await self.get_one_or_none(username=username)

    async def authenticate(self, data: LoginRequest) -> UserStruct:
        """Authenticate a login request and return service-layer user data."""

        user = await self.get_by_username(data.username)

        if user is None:
            raise NotAuthorizedException(detail="Invalid username or password.")

        stored_password = user.password_hash
        password_valid = (
            stored_password.verify(data.password)
            if isinstance(stored_password, HashedPassword)
            else password_hasher.verify(data.password, stored_password)
        )

        if not password_valid:
            raise NotAuthorizedException(detail="Invalid username or password.")

        if not user.is_active:
            raise UserDisabledError()

        return user.to_struct()


class AccountCertificationService(CustomService[AccountCertificationModel]):
    """Account certification database service."""

    class _Repository(SQLAlchemyAsyncRepository[AccountCertificationModel]):
        """Account certification repository."""

        model_type: type[AccountCertificationModel] = AccountCertificationModel

    repository_type = _Repository

    async def get_by_user_id(self, user_id: UUID) -> AccountCertificationStruct | None:
        """Get a certification record by user ID."""

        certification = await self.get_one_or_none(user_id=user_id)

        return certification.to_struct() if certification else None


class OrganizationService(CustomService[OrganizationModel]):
    """Organization database service."""

    class _Repository(SQLAlchemyAsyncRepository[OrganizationModel]):
        """Organization repository."""

        model_type: type[OrganizationModel] = OrganizationModel

    repository_type = _Repository

    async def get_by_id(self, organization_id: UUID) -> OrganizationStruct | None:
        """Get an organization by primary key."""

        organization = await self.get_one_or_none(id=organization_id)

        return organization.to_struct() if organization else None

    async def get_by_owner_user_id(self, user_id: UUID) -> OrganizationStruct | None:
        """Get an organization by owner user ID."""

        organization = await self.get_one_or_none(owner_user_id=user_id)

        return organization.to_struct() if organization else None

    async def list_by_owner_user_id(self, user_id: UUID) -> list[OrganizationStruct]:
        """List organizations owned by a user."""

        organizations = await self.list(owner_user_id=user_id)

        return [organization.to_struct() for organization in organizations]


class OrganizationMemberService(CustomService[OrganizationMemberModel]):
    """Organization member database service."""

    class _Repository(SQLAlchemyAsyncRepository[OrganizationMemberModel]):
        """Organization member repository."""

        model_type: type[OrganizationMemberModel] = OrganizationMemberModel

    repository_type = _Repository

    async def list_by_user_id(self, user_id: UUID) -> list[OrganizationMemberStruct]:
        """List memberships for a user."""

        memberships = await self.list(user_id=user_id)

        return [membership.to_struct() for membership in memberships]

    async def get_by_organization_and_user(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> OrganizationMemberStruct | None:
        """Get a membership record by organization and user."""

        member = await self.get_one_or_none(organization_id=organization_id, user_id=user_id)

        return member.to_struct() if member else None

    async def list_by_organization_ids(self, organization_ids: Sequence[UUID]) -> list[OrganizationMemberStruct]:
        """List memberships for a collection of organizations."""

        memberships: list[OrganizationMemberModel] = []
        for organization_id in organization_ids:
            memberships.extend(await self.list(organization_id=organization_id))

        return [membership.to_struct() for membership in memberships]


class RoomService(CustomService[RoomModel]):
    """Room database service."""

    class _Repository(SQLAlchemyAsyncRepository[RoomModel]):
        """Room repository."""

        model_type: type[RoomModel] = RoomModel

    repository_type = _Repository

    async def list_by_owner_user_id(self, user_id: UUID) -> list[RoomStruct]:
        """List rooms owned by a user."""

        rooms = await self.list(owner_user_id=user_id)

        return [room.to_struct() for room in rooms]

    async def list_by_organization_id(self, organization_id: UUID) -> list[RoomStruct]:
        """List rooms owned by an organization."""

        rooms = await self.list(organization_id=organization_id)

        return [room.to_struct() for room in rooms]

    async def get_by_room_id(self, room_id: str) -> RoomStruct | None:
        """Get a room by its business room ID."""

        room = await self.get_one_or_none(room_id=room_id)

        return room.to_struct() if room else None


class RoomAuthorizationService(CustomService[RoomAuthorizationModel]):
    """Room authorization database service."""

    class _Repository(SQLAlchemyAsyncRepository[RoomAuthorizationModel]):
        """Room authorization repository."""

        model_type: type[RoomAuthorizationModel] = RoomAuthorizationModel

    repository_type = _Repository

    async def list_by_room_id(self, room_id: str) -> list[RoomAuthorizationStruct]:
        """List room authorization grants for a room."""

        grants = await self.list(room_id=room_id)

        return [grant.to_struct() for grant in grants]

    async def list_by_user_id(self, user_id: UUID) -> list[RoomAuthorizationStruct]:
        """List room authorization grants for a user."""

        grants = await self.list(user_id=user_id)

        return [grant.to_struct() for grant in grants]

    async def list_by_organization_ids(self, organization_ids: Sequence[UUID]) -> list[RoomAuthorizationStruct]:
        """List room authorization grants for multiple organizations."""

        grants: list[RoomAuthorizationModel] = []
        for organization_id in organization_ids:
            grants.extend(await self.list(organization_id=organization_id))

        return [grant.to_struct() for grant in grants]
