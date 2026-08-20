"""Room aggregation domain schemas."""

from echocue.auth import RoomOwnershipKind
from echocue.base import BaseStruct

from .enum import RoomLiveStatus, RoomStartBlockReason

__all__ = ("RoomAggregateStruct", "RoomStartEligibilityStruct", "RoomStaticGateStruct")


class RoomStaticGateStruct(BaseStruct):
    """Static configuration readiness for a room assistant."""

    persona_published: bool = True
    rule_conflict: bool = False


class RoomStartEligibilityStruct(BaseStruct):
    """Static room start decision independent of current live status."""

    allowed: bool
    block_reason: RoomStartBlockReason | None = None


class RoomAggregateStruct(BaseStruct):
    """Shared room data used to build client and webui views."""

    room_id: str
    room_kind: RoomOwnershipKind
    live_status: RoomLiveStatus
    room_name: str | None = None
    anchor_name: str | None = None
    avatar_thumb: str | None = None
    start_eligibility: RoomStartEligibilityStruct | None = None
