"""Room aggregation handler tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from echocue.auth import (
    OrganizationMemberRole,
    OrganizationMemberStruct,
    OrganizationStruct,
    PermissionContextStruct,
    RoomAuthorizationScope,
    RoomAuthorizationStruct,
    RoomOwnershipKind,
    RoomStruct,
    UserStruct,
)
from echocue.core.live import MemoryRoomOnlineStatusCache, RoomOnlineStatusStruct
from echocue.core.room import (
    RoomAggregationHandler,
    RoomStartBlockReason,
    RoomStaticGateStruct,
)

USER_ID = UUID("00000000-0000-7000-8000-000000000001")
ORGANIZATION_ID = UUID("00000000-0000-7000-8000-000000000002")
OTHER_USER_ID = UUID("00000000-0000-7000-8000-000000000003")


class StaticGateProvider:
    """Deterministic static gate provider for room aggregation tests."""

    def __init__(self, gates: dict[str, RoomStaticGateStruct]) -> None:
        self._gates = gates

    async def get(self, room_id: str) -> RoomStaticGateStruct:
        """Return a configured gate or an unblocked default."""

        return self._gates.get(room_id, RoomStaticGateStruct())


class TestRoomAggregationHandler:
    """Verify shared room aggregation behavior."""

    async def test_lists_visible_rooms_with_deduplication_and_static_start_reasons(self) -> None:
        context = self._permission_context()
        auth_client = SimpleNamespace(get_permission_context=AsyncMock(return_value=context))
        cache = MemoryRoomOnlineStatusCache()
        await cache.write(
            RoomOnlineStatusStruct(
                room_id="personal-room",
                live_started_at=datetime(2026, 8, 20, tzinfo=UTC),
                last_event_at=datetime(2026, 8, 20, 0, 1, tzinfo=UTC),
                room_name="Cached title",
                anchor_name="Cached anchor",
                avatar_thumb="https://example.com/avatar.jpeg",
            )
        )
        gates = StaticGateProvider(
            {
                "org-admin-room": RoomStaticGateStruct(persona_published=False),
                "granted-room": RoomStaticGateStruct(rule_conflict=True),
            }
        )
        handler = RoomAggregationHandler(auth_client, cache, gates)

        result = await handler.list_rooms(USER_ID, include_start_eligibility=True)

        assert [item.room_id for item in result] == [
            "personal-room",
            "org-admin-room",
            "granted-room",
            "view-only-room",
        ]
        personal = result[0]
        assert personal.live_status.value == "live"
        assert personal.room_name == "Cached title"
        assert personal.start_eligibility is not None
        assert personal.start_eligibility.allowed is True
        assert personal.start_eligibility.block_reason is None

        persona_blocked = result[1]
        assert persona_blocked.live_status.value == "offline"
        assert persona_blocked.start_eligibility is not None
        assert persona_blocked.start_eligibility.block_reason is RoomStartBlockReason.PERSONA_NOT_PUBLISHED

        rule_blocked = result[2]
        assert rule_blocked.start_eligibility is not None
        assert rule_blocked.start_eligibility.block_reason is RoomStartBlockReason.RULE_CONFLICT

        permission_blocked = result[3]
        assert permission_blocked.start_eligibility is not None
        assert permission_blocked.start_eligibility.block_reason is RoomStartBlockReason.PERMISSION_DENIED
        auth_client.get_permission_context.assert_awaited_once_with(USER_ID)

    async def test_can_start_while_room_is_offline(self) -> None:
        context = PermissionContextStruct(
            user=UserStruct(id=USER_ID, username="owner"),
            rooms=[RoomStruct(room_id="offline-room", owner_user_id=USER_ID)],
        )
        auth_client = SimpleNamespace(get_permission_context=AsyncMock(return_value=context))
        handler = RoomAggregationHandler(
            auth_client,
            MemoryRoomOnlineStatusCache(),
            StaticGateProvider({}),
        )

        result = await handler.list_rooms(USER_ID, include_start_eligibility=True)

        assert result[0].live_status.value == "offline"
        assert result[0].start_eligibility is not None
        assert result[0].start_eligibility.allowed is True

    async def test_default_static_gate_fails_closed_without_published_persona_source(self) -> None:
        context = PermissionContextStruct(
            user=UserStruct(id=USER_ID, username="owner"),
            rooms=[RoomStruct(room_id="unverified-room", owner_user_id=USER_ID)],
        )
        auth_client = SimpleNamespace(get_permission_context=AsyncMock(return_value=context))
        handler = RoomAggregationHandler(auth_client, MemoryRoomOnlineStatusCache())

        result = await handler.list_rooms(USER_ID, include_start_eligibility=True)

        assert result[0].start_eligibility is not None
        assert result[0].start_eligibility.allowed is False
        assert result[0].start_eligibility.block_reason is RoomStartBlockReason.PERSONA_NOT_PUBLISHED

    async def test_skips_start_gate_for_read_only_room_aggregation(self) -> None:
        context = self._permission_context()
        auth_client = SimpleNamespace(get_permission_context=AsyncMock(return_value=context))
        handler = RoomAggregationHandler(auth_client, MemoryRoomOnlineStatusCache())

        result = await handler.list_rooms(USER_ID)

        assert len(result) == 4
        assert all(item.start_eligibility is None for item in result)

    @staticmethod
    def _permission_context() -> PermissionContextStruct:
        user = UserStruct(id=USER_ID, username="room-user")
        organization = OrganizationStruct(
            id=ORGANIZATION_ID,
            name="Studio",
            owner_user_id=OTHER_USER_ID,
        )
        return PermissionContextStruct(
            user=user,
            organizations=[organization],
            memberships=[
                OrganizationMemberStruct(
                    organization_id=ORGANIZATION_ID,
                    user_id=USER_ID,
                    role=OrganizationMemberRole.ADMIN,
                )
            ],
            rooms=[
                RoomStruct(room_id="personal-room", owner_user_id=USER_ID),
                RoomStruct(
                    room_id="org-admin-room",
                    room_kind=RoomOwnershipKind.ORGANIZATION,
                    organization_id=ORGANIZATION_ID,
                ),
                RoomStruct(room_id="granted-room", owner_user_id=OTHER_USER_ID),
                RoomStruct(room_id="view-only-room", owner_user_id=OTHER_USER_ID),
                RoomStruct(room_id="personal-room", owner_user_id=USER_ID),
                RoomStruct(room_id="inactive-room", owner_user_id=USER_ID, is_active=False),
            ],
            room_authorizations=[
                RoomAuthorizationStruct(
                    room_id="granted-room",
                    organization_id=ORGANIZATION_ID,
                    user_id=USER_ID,
                    access_scope=RoomAuthorizationScope.START,
                ),
                RoomAuthorizationStruct(
                    room_id="view-only-room",
                    organization_id=ORGANIZATION_ID,
                    user_id=USER_ID,
                    access_scope=RoomAuthorizationScope.VIEW,
                ),
            ],
        )
