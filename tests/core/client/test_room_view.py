"""Client and webui room view conversion tests."""

from echocue.auth import RoomOwnershipKind
from echocue.core.client import ClientRoomListVO, RuntimeErrorCode, WebuiRoomListVO
from echocue.core.room import (
    RoomAggregateStruct,
    RoomLiveStatus,
    RoomStartBlockReason,
    RoomStartEligibilityStruct,
)


class TestRoomViewConversion:
    """Verify room-domain aggregates map to frozen external views."""

    def test_maps_start_eligibility_to_client_error_contract(self) -> None:
        rooms = [
            RoomAggregateStruct(
                room_id="ready-room",
                room_kind=RoomOwnershipKind.PERSONAL,
                live_status=RoomLiveStatus.OFFLINE,
                start_eligibility=RoomStartEligibilityStruct(allowed=True),
            ),
            RoomAggregateStruct(
                room_id="view-only-room",
                room_kind=RoomOwnershipKind.ORGANIZATION,
                live_status=RoomLiveStatus.LIVE,
                start_eligibility=RoomStartEligibilityStruct(
                    allowed=False,
                    block_reason=RoomStartBlockReason.PERMISSION_DENIED,
                ),
            ),
        ]

        result = ClientRoomListVO.from_rooms(rooms)

        assert result.items[0].can_start_assistant is True
        assert result.items[0].live_status.value == "offline"
        assert result.items[1].disabled_reason is not None
        assert result.items[1].disabled_reason.error_code is RuntimeErrorCode.PERMISSION_DENIED
        assert result.items[1].disabled_reason.issue_type is None

    def test_webui_view_omits_start_eligibility(self) -> None:
        room = RoomAggregateStruct(
            room_id="managed-room",
            room_kind=RoomOwnershipKind.ORGANIZATION,
            live_status=RoomLiveStatus.LIVE,
            start_eligibility=RoomStartEligibilityStruct(
                allowed=False,
                block_reason=RoomStartBlockReason.RULE_CONFLICT,
            ),
        )

        result = WebuiRoomListVO.from_rooms([room]).to_dict()

        assert "canStartAssistant" not in result["items"][0]
        assert "disabledReason" not in result["items"][0]
