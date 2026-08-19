"""Authentication domain orchestration.

This module combines account lookup, certification, organization membership, room ownership,
and room authorization into reusable permission context and decision objects.
"""

from datetime import UTC, datetime
from uuid import UUID

from litestar.exceptions import NotAuthorizedException

from .enum import (
    OrganizationMemberRole,
    PermissionAction,
    RoomAuthorizationScope,
    RoomAuthorizationStatus,
    RoomOwnershipKind,
)
from .schema import (
    AccountCertificationStruct,
    AuthenticationResultStruct,
    LoginRequest,
    OrganizationMemberStruct,
    OrganizationStruct,
    PermissionCheckRequestStruct,
    PermissionCheckResultStruct,
    PermissionContextStruct,
    RoomAuthorizationStruct,
    RoomStruct,
    UserStruct,
)
from .service import (
    AccountCertificationService,
    OrganizationMemberService,
    OrganizationService,
    RoomAuthorizationService,
    RoomService,
    UserService,
)

__all__ = ("AuthPermissionHandler",)


class AuthPermissionHandler:
    """Compose auth services into authentication and authorization operations."""

    async def authenticate(self, request: LoginRequest) -> AuthenticationResultStruct:
        """Authenticate credentials and return the full permission context."""

        async with UserService.provide() as user_service:
            user = await user_service.authenticate(request)

        context = await self.get_permission_context(user.id)

        return AuthenticationResultStruct(user=user, context=context)

    async def get_permission_context(self, user_id: UUID) -> PermissionContextStruct:
        """Build the full permission context for a user."""

        user = await self._get_user(user_id)
        certification = await self._get_certification(user_id)

        memberships = await self._collect_memberships(user_id)
        organizations = await self._collect_organizations(user_id, certification, memberships)
        rooms = await self._collect_rooms(user_id, organizations, memberships)
        grants = await self._collect_grants(user_id, organizations, memberships)

        return PermissionContextStruct(
            user=user,
            certification=certification,
            organizations=organizations,
            memberships=memberships,
            rooms=rooms,
            room_authorizations=grants,
        )

    async def check_permission(self, request: PermissionCheckRequestStruct) -> PermissionCheckResultStruct:
        """Check whether a user can perform an action on a room."""

        context = await self.get_permission_context(request.user_id)
        room = next((item for item in context.rooms if item.room_id == request.room_id), None)
        if room is None:
            return PermissionCheckResultStruct(
                allowed=False,
                reason="Room not found or unavailable.",
            )

        if not room.is_active:
            return PermissionCheckResultStruct(
                allowed=False,
                reason="Room is inactive.",
            )

        if room.owner_user_id == request.user_id and request.action in {
            PermissionAction.VIEW,
            PermissionAction.EDIT,
            PermissionAction.REPLAY,
            PermissionAction.START,
        }:
            return PermissionCheckResultStruct(allowed=True, reason="Room is owned by the user.")

        if room.room_kind is RoomOwnershipKind.ORGANIZATION:
            return self._check_organization_room_permission(context, room.room_id, request.action)

        return self._check_granted_personal_room_permission(context, room.room_id, request.action)

    async def _get_user(self, user_id: UUID) -> UserStruct:
        async with UserService.provide() as user_service:
            user = await user_service.get_by_id(user_id)

        if user is None:
            raise NotAuthorizedException(detail="User not found.")

        return user

    async def _get_certification(self, user_id: UUID) -> AccountCertificationStruct | None:
        async with AccountCertificationService.provide() as certification_service:
            return await certification_service.get_by_user_id(user_id)

    async def _collect_organizations(
        self,
        user_id: UUID,
        certification: AccountCertificationStruct | None,
        memberships: list[OrganizationMemberStruct],
    ) -> list[OrganizationStruct]:
        organizations: list[OrganizationStruct] = []
        seen_ids: set[UUID] = set()

        async with OrganizationService.provide() as organization_service:
            owner_organization = await organization_service.get_by_owner_user_id(user_id)
            if owner_organization is not None and owner_organization.id is not None:
                organizations.append(owner_organization)
                seen_ids.add(owner_organization.id)

            if certification is not None and certification.organization_id is not None:
                organization = await organization_service.get_by_id(certification.organization_id)
                if organization is not None and organization.id is not None and organization.id not in seen_ids:
                    organizations.append(organization)
                    seen_ids.add(organization.id)

            for membership in memberships:
                if membership.organization_id in seen_ids:
                    continue
                organization = await organization_service.get_by_id(membership.organization_id)
                if organization is not None and organization.id is not None:
                    organizations.append(organization)
                    seen_ids.add(organization.id)

        return organizations

    async def _collect_memberships(self, user_id: UUID) -> list[OrganizationMemberStruct]:
        async with OrganizationMemberService.provide() as membership_service:
            memberships = await membership_service.list_by_user_id(user_id)

        return [membership for membership in memberships if membership.is_active]

    async def _collect_rooms(
        self,
        user_id: UUID,
        organizations: list[OrganizationStruct],
        memberships: list[OrganizationMemberStruct],
    ) -> list[RoomStruct]:
        organization_ids = {organization.id for organization in organizations if organization.id is not None}
        organization_ids.update(membership.organization_id for membership in memberships if membership.is_active)

        rooms: list[RoomStruct] = []
        seen_room_ids: set[str] = set()

        async with RoomService.provide() as room_service:
            for room in await room_service.list_by_owner_user_id(user_id):
                if room.room_id not in seen_room_ids:
                    rooms.append(room)
                    seen_room_ids.add(room.room_id)

            for organization_id in organization_ids:
                for room in await room_service.list_by_organization_id(organization_id):
                    if room.room_id not in seen_room_ids:
                        rooms.append(room)
                        seen_room_ids.add(room.room_id)

        async with RoomAuthorizationService.provide() as authorization_service:
            grants = await authorization_service.list_by_user_id(user_id)
            for grant in grants:
                if grant.room_id in seen_room_ids:
                    continue
                if not self._is_grant_active(grant):
                    continue

                async with RoomService.provide() as room_service:
                    granted_room = await room_service.get_by_room_id(grant.room_id)
                if granted_room is None or not granted_room.is_active:
                    continue

                rooms.append(granted_room)
                seen_room_ids.add(granted_room.room_id)

        return rooms

    async def _collect_grants(
        self,
        user_id: UUID,
        organizations: list[OrganizationStruct],
        memberships: list[OrganizationMemberStruct],
    ) -> list[RoomAuthorizationStruct]:
        organization_ids = [
            organization.id
            for organization in organizations
            if organization.id is not None and organization.owner_user_id == user_id
        ]
        organization_ids.extend(
            membership.organization_id
            for membership in memberships
            if membership.role in {OrganizationMemberRole.OWNER, OrganizationMemberRole.ADMIN}
        )

        async with RoomAuthorizationService.provide() as authorization_service:
            grants = await authorization_service.list_by_user_id(user_id)
            grants.extend(await authorization_service.list_by_organization_ids(organization_ids))

        unique_grants: list[RoomAuthorizationStruct] = []
        seen_keys: set[tuple[str, UUID, UUID, str]] = set()
        for grant in grants:
            if not self._is_grant_active(grant):
                continue
            key = (grant.room_id, grant.organization_id, grant.user_id, grant.access_scope.value)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_grants.append(grant)

        return unique_grants

    def _check_organization_room_permission(
        self,
        context: PermissionContextStruct,
        room_id: str,
        action: PermissionAction,
    ) -> PermissionCheckResultStruct:
        room = next((item for item in context.rooms if item.room_id == room_id), None)
        if room is None or room.organization_id is None:
            return PermissionCheckResultStruct(allowed=False, reason="Organization room not found.")

        if any(
            organization.id == room.organization_id and organization.owner_user_id == context.user.id
            for organization in context.organizations
        ):
            return PermissionCheckResultStruct(
                allowed=True,
                reason="Organization owner can access the room.",
            )

        membership = next(
            (item for item in context.memberships if item.organization_id == room.organization_id and item.is_active),
            None,
        )
        if membership is None:
            return PermissionCheckResultStruct(
                allowed=False,
                reason="No active organization membership for the room.",
            )

        if membership.role in {OrganizationMemberRole.OWNER, OrganizationMemberRole.ADMIN}:
            return PermissionCheckResultStruct(
                allowed=True,
                reason="Organization owner or admin can access the room.",
            )

        grant = next(
            (
                item
                for item in context.room_authorizations
                if item.room_id == room_id
                and item.organization_id == room.organization_id
                and item.user_id == context.user.id
            ),
            None,
        )
        if grant is None:
            return PermissionCheckResultStruct(
                allowed=False,
                reason="No room authorization grant found.",
            )

        if action is PermissionAction.VIEW and grant.access_scope in {
            RoomAuthorizationScope.VIEW,
            RoomAuthorizationScope.REPLAY,
            RoomAuthorizationScope.CONFIGURE,
            RoomAuthorizationScope.START,
        }:
            return PermissionCheckResultStruct(
                allowed=True,
                reason="Authorization grant allows viewing the organization room.",
                matched_scope=grant.access_scope,
            )

        if action is PermissionAction.REPLAY and grant.access_scope in {
            RoomAuthorizationScope.REPLAY,
            RoomAuthorizationScope.CONFIGURE,
            RoomAuthorizationScope.START,
        }:
            return PermissionCheckResultStruct(
                allowed=True,
                reason="Authorization grant allows replay access.",
                matched_scope=grant.access_scope,
            )

        if action is PermissionAction.EDIT and grant.access_scope in {
            RoomAuthorizationScope.CONFIGURE,
            RoomAuthorizationScope.START,
        }:
            return PermissionCheckResultStruct(
                allowed=True,
                reason="Authorization grant allows editing the organization room.",
                matched_scope=grant.access_scope,
            )

        if action is PermissionAction.START and grant.access_scope == RoomAuthorizationScope.START:
            return PermissionCheckResultStruct(
                allowed=True,
                reason="Authorization grant allows starting the organization room assistant.",
                matched_scope=grant.access_scope,
            )

        return PermissionCheckResultStruct(
            allowed=False,
            reason="The authorization grant does not cover the requested action.",
            matched_scope=grant.access_scope,
        )

    def _check_granted_personal_room_permission(
        self,
        context: PermissionContextStruct,
        room_id: str,
        action: PermissionAction,
    ) -> PermissionCheckResultStruct:
        room = next((item for item in context.rooms if item.room_id == room_id), None)
        if room is None:
            return PermissionCheckResultStruct(allowed=False, reason="Personal room not found.")

        if room.owner_user_id == context.user.id:
            return PermissionCheckResultStruct(allowed=True, reason="Room is owned by the user.")

        grant = next(
            (
                item
                for item in context.room_authorizations
                if item.room_id == room_id and item.user_id == context.user.id
            ),
            None,
        )
        if grant is None:
            return PermissionCheckResultStruct(
                allowed=False,
                reason="No personal room authorization grant found.",
            )

        if action is PermissionAction.VIEW and grant.access_scope in {
            RoomAuthorizationScope.VIEW,
            RoomAuthorizationScope.REPLAY,
        }:
            return PermissionCheckResultStruct(
                allowed=True,
                reason="Authorization grant allows viewing the personal room.",
                matched_scope=grant.access_scope,
            )

        if action is PermissionAction.REPLAY and grant.access_scope == RoomAuthorizationScope.REPLAY:
            return PermissionCheckResultStruct(
                allowed=True,
                reason="Authorization grant allows replay access.",
                matched_scope=grant.access_scope,
            )

        return PermissionCheckResultStruct(
            allowed=False,
            reason="Personal room authorization does not cover the requested action.",
            matched_scope=grant.access_scope,
        )

    @staticmethod
    def _is_grant_active(grant: RoomAuthorizationStruct) -> bool:
        if grant.status != RoomAuthorizationStatus.ACTIVE:
            return False
        if grant.expires_at is None:
            return True

        return grant.expires_at > datetime.now(tz=UTC)
