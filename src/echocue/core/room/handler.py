"""Room aggregation business handler.

The service combines auth visibility, optional static start eligibility, and
online-only display cache without depending on client or webui protocols.
"""

from typing import Protocol
from uuid import UUID

from echocue.auth import (
    OrganizationMemberRole,
    PermissionContextStruct,
    RoomAuthorizationScope,
    RoomAuthorizationStatus,
    RoomOwnershipKind,
    RoomStruct,
)
from echocue.auth.client import AuthPermissionClient
from echocue.core.live import RoomOnlineStatusCache

from .enum import RoomLiveStatus, RoomStartBlockReason
from .schema import RoomAggregateStruct, RoomStartEligibilityStruct, RoomStaticGateStruct

__all__ = ("DefaultRoomStaticGateProvider", "RoomAggregationHandler", "RoomStaticGateProvider")


class RoomStaticGateProvider(Protocol):
    """Resolve static persona and rule readiness for a room."""

    async def get(self, room_id: str) -> RoomStaticGateStruct:
        """Return the current static readiness summary for a room."""


class DefaultRoomStaticGateProvider:
    """Fail-closed readiness adapter until persistent gate sources exist."""

    async def get(self, room_id: str) -> RoomStaticGateStruct:
        """Prevent starts when published persona readiness cannot be verified."""

        return RoomStaticGateStruct(persona_published=False)


class RoomAggregationHandler:
    """Build shared room aggregates from domain inputs."""

    def __init__(
        self,
        auth_client: AuthPermissionClient,
        room_status_cache: RoomOnlineStatusCache,
        static_gate_provider: RoomStaticGateProvider | None = None,
    ) -> None:
        self._auth_client = auth_client
        self._room_status_cache = room_status_cache
        self._static_gate_provider = static_gate_provider or DefaultRoomStaticGateProvider()

    async def list_rooms(
        self,
        user_id: UUID,
        *,
        include_start_eligibility: bool = False,
    ) -> list[RoomAggregateStruct]:
        """Return visible room aggregates for a user."""

        context = await self._auth_client.get_permission_context(user_id)
        items: list[RoomAggregateStruct] = []
        for room in self._visible_rooms(context):
            online = await self._room_status_cache.get(room.room_id)
            eligibility = (
                await self._start_eligibility(context, room) if include_start_eligibility else None
            )
            items.append(
                RoomAggregateStruct(
                    room_id=room.room_id,
                    room_kind=room.room_kind,
                    live_status=RoomLiveStatus.LIVE if online is not None else RoomLiveStatus.OFFLINE,
                    room_name=online.room_name if online is not None else None,
                    anchor_name=online.anchor_name if online is not None else None,
                    avatar_thumb=online.avatar_thumb if online is not None else None,
                    start_eligibility=eligibility,
                )
            )

        return items

    @staticmethod
    def _visible_rooms(context: PermissionContextStruct) -> list[RoomStruct]:
        rooms: list[RoomStruct] = []
        seen_room_ids: set[str] = set()
        for room in context.rooms:
            if not room.is_active or room.room_id in seen_room_ids:
                continue
            rooms.append(room)
            seen_room_ids.add(room.room_id)

        return rooms

    async def _start_eligibility(
        self,
        context: PermissionContextStruct,
        room: RoomStruct,
    ) -> RoomStartEligibilityStruct:
        if not self._can_start(context, room):
            return RoomStartEligibilityStruct(
                allowed=False,
                block_reason=RoomStartBlockReason.PERMISSION_DENIED,
            )

        gate = await self._static_gate_provider.get(room.room_id)
        if not gate.persona_published:
            return RoomStartEligibilityStruct(
                allowed=False,
                block_reason=RoomStartBlockReason.PERSONA_NOT_PUBLISHED,
            )
        if gate.rule_conflict:
            return RoomStartEligibilityStruct(
                allowed=False,
                block_reason=RoomStartBlockReason.RULE_CONFLICT,
            )

        return RoomStartEligibilityStruct(allowed=True)

    @staticmethod
    def _can_start(context: PermissionContextStruct, room: RoomStruct) -> bool:
        user_id = context.user.id
        if room.owner_user_id == user_id:
            return True

        if room.room_kind is RoomOwnershipKind.ORGANIZATION and room.organization_id is not None:
            if any(
                organization.id == room.organization_id and organization.owner_user_id == user_id
                for organization in context.organizations
            ):
                return True
            membership = next(
                (
                    membership
                    for membership in context.memberships
                    if membership.organization_id == room.organization_id and membership.is_active
                ),
                None,
            )
            if membership is not None and membership.role in {OrganizationMemberRole.OWNER, OrganizationMemberRole.ADMIN}:
                return True
            if membership is None:
                return False

            return any(
                grant.room_id == room.room_id
                and grant.organization_id == room.organization_id
                and grant.user_id == user_id
                and grant.status is RoomAuthorizationStatus.ACTIVE
                and grant.access_scope is RoomAuthorizationScope.START
                for grant in context.room_authorizations
            )

        return any(
            grant.room_id == room.room_id
            and grant.user_id == user_id
            and grant.status is RoomAuthorizationStatus.ACTIVE
            and grant.access_scope is RoomAuthorizationScope.START
            for grant in context.room_authorizations
        )
