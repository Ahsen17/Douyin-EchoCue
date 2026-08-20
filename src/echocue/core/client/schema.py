"""Typed client-service protocol schemas.

These schemas freeze external HTTP and WebSocket data shapes without implementing
session, runtime, or transport behavior.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from echocue.base import CamelizedBaseStruct
from echocue.core.room import RoomStartBlockReason

from .enum import (
    ClientRuntimeStatus,
    ClientRuntimeStopReason,
    LiveStatus,
    RemediationIssueType,
    RoomKind,
    RuntimeErrorCode,
    RuntimeEventStatus,
)

if TYPE_CHECKING:
    from echocue.auth import UserStruct
    from echocue.core.room import RoomAggregateStruct

__all__ = (
    "ClientHttpResponse",
    "ClientRoomListVO",
    "ClientRoomVO",
    "ClientSessionCreate",
    "ClientSessionVO",
    "ClientUserVO",
    "ClientWebSocketMessage",
    "DisabledReasonVO",
    "RemediationContextVO",
    "RemediationLinkCreate",
    "RemediationLinkVO",
    "RemediationTokenConsumptionCreate",
    "RuntimeFailureVO",
    "RuntimeStart",
    "RuntimeStartVO",
    "RuntimeStopVO",
    "WebuiRoomListVO",
    "WebuiRoomVO",
    "WebuiSessionCreate",
)


class ClientUserVO(CamelizedBaseStruct):
    """User identity displayed by client and webui sessions."""

    id: UUID
    username: str
    display_name: str
    is_active: bool

    @classmethod
    def from_user(cls, user: "UserStruct") -> "ClientUserVO":
        """Build the client-facing identity from an authenticated user."""

        return cls(
            id=user.id,
            username=user.username,
            display_name=user.username,
            is_active=user.is_active,
        )


class ClientHttpResponse[T](CamelizedBaseStruct):
    """Parseable representation of the shared HTTP response envelope."""

    code: int
    message: str
    data: T


class ClientSessionCreate(CamelizedBaseStruct):
    """Client login payload with its persistent device identifier."""

    username: str
    password: str
    client_id: UUID


class WebuiSessionCreate(CamelizedBaseStruct):
    """Webui login payload."""

    username: str
    password: str


class ClientSessionVO(CamelizedBaseStruct):
    """Session creation result shared by client and webui views."""

    expires_in: int
    user: ClientUserVO


class DisabledReasonVO(CamelizedBaseStruct):
    """Static room gate failure displayed in the client room list."""

    error_code: RuntimeErrorCode
    message: str
    issue_type: RemediationIssueType | None = None


class ClientRoomVO(CamelizedBaseStruct):
    """Room view used by the desktop client."""

    room_id: str
    room_name: str | None
    anchor_name: str | None
    avatar_thumb: str | None
    room_kind: RoomKind
    live_status: LiveStatus
    can_start_assistant: bool
    disabled_reason: DisabledReasonVO | None

    @classmethod
    def from_room(cls, room: "RoomAggregateStruct") -> "ClientRoomVO":
        """Build a client view from a shared room aggregate."""

        if room.start_eligibility is None:
            raise ValueError("Client room aggregation requires start eligibility.")

        return cls(
            room_id=room.room_id,
            room_name=room.room_name,
            anchor_name=room.anchor_name,
            avatar_thumb=room.avatar_thumb,
            room_kind=RoomKind(room.room_kind.value),
            live_status=LiveStatus(room.live_status.value),
            can_start_assistant=room.start_eligibility.allowed,
            disabled_reason=_disabled_reason(room.start_eligibility.block_reason),
        )


class ClientRoomListVO(CamelizedBaseStruct):
    """Complete room list visible to the desktop client."""

    items: list[ClientRoomVO]

    @classmethod
    def from_rooms(cls, rooms: list["RoomAggregateStruct"]) -> "ClientRoomListVO":
        """Build a client room list from shared room aggregates."""

        return cls(items=[ClientRoomVO.from_room(room) for room in rooms])


class WebuiRoomVO(CamelizedBaseStruct):
    """Read-only room view used by the webui."""

    room_id: str
    room_name: str | None
    anchor_name: str | None
    avatar_thumb: str | None
    room_kind: RoomKind
    live_status: LiveStatus

    @classmethod
    def from_room(cls, room: "RoomAggregateStruct") -> "WebuiRoomVO":
        """Build a webui view from a shared room aggregate."""

        return cls(
            room_id=room.room_id,
            room_name=room.room_name,
            anchor_name=room.anchor_name,
            avatar_thumb=room.avatar_thumb,
            room_kind=RoomKind(room.room_kind.value),
            live_status=LiveStatus(room.live_status.value),
        )


class WebuiRoomListVO(CamelizedBaseStruct):
    """Complete room list visible to the webui."""

    items: list[WebuiRoomVO]

    @classmethod
    def from_rooms(cls, rooms: list["RoomAggregateStruct"]) -> "WebuiRoomListVO":
        """Build a webui room list from shared room aggregates."""

        return cls(items=[WebuiRoomVO.from_room(room) for room in rooms])


def _disabled_reason(block_reason: RoomStartBlockReason | None) -> DisabledReasonVO | None:
    if block_reason is None:
        return None
    if block_reason is RoomStartBlockReason.PERMISSION_DENIED:
        return DisabledReasonVO(
            error_code=RuntimeErrorCode.PERMISSION_DENIED,
            message="Current account cannot start this room assistant.",
        )
    if block_reason is RoomStartBlockReason.PERSONA_NOT_PUBLISHED:
        return DisabledReasonVO(
            error_code=RuntimeErrorCode.PERSONA_NOT_PUBLISHED,
            message="A published room persona is required.",
            issue_type=RemediationIssueType.PERSONA,
        )

    return DisabledReasonVO(
        error_code=RuntimeErrorCode.RULE_CONFLICT,
        message="Published safety rules contain a conflict.",
        issue_type=RemediationIssueType.RULE,
    )


class RuntimeStart(CamelizedBaseStruct):
    """Runtime creation payload."""

    room_id: str


class RuntimeWebSocketVO(CamelizedBaseStruct):
    """Runtime WebSocket connection parameters."""

    url: str
    heartbeat_interval_seconds: int
    heartbeat_timeout_seconds: int
    connect_retry_window_seconds: int


class RuntimeStartVO(CamelizedBaseStruct):
    """Successful runtime creation result."""

    runtime_id: str
    room_id: str
    status: ClientRuntimeStatus
    ws: RuntimeWebSocketVO


class RuntimeStopVO(CamelizedBaseStruct):
    """Successful runtime stop result."""

    runtime_id: str
    room_id: str
    status: ClientRuntimeStatus
    reason: ClientRuntimeStopReason


class RemediationVO(CamelizedBaseStruct):
    """Navigation information for resolving a runtime gate failure."""

    issue_type: RemediationIssueType
    route: str
    params: dict[str, str]
    requires_one_time_token: bool


class RuntimeFailureVO(CamelizedBaseStruct):
    """Stable failure payload returned by runtime operations."""

    error_code: RuntimeErrorCode
    message: str
    retryable: bool | None = None
    remediation: RemediationVO | None = None


class RemediationLinkCreate(CamelizedBaseStruct):
    """Request for a one-time remediation link."""

    room_id: str
    error_code: RuntimeErrorCode
    issue_type: RemediationIssueType


class RemediationLinkVO(CamelizedBaseStruct):
    """One-time remediation link returned to the client."""

    url: str
    expires_in: int


class RemediationTokenConsumptionCreate(CamelizedBaseStruct):
    """Request to create a one-time remediation token consumption."""

    token: str


class RemediationContextVO(CamelizedBaseStruct):
    """Minimal webui context authorized by a remediation token."""

    room_id: str
    issue_type: RemediationIssueType
    route: str
    params: dict[str, str]
    expires_at: datetime


class ConnectedMessage(CamelizedBaseStruct, tag="connected", tag_field="type"):
    """Server message confirming a runtime WebSocket connection."""

    message_id: str
    runtime_id: str
    room_id: str
    client_id: UUID
    heartbeat_interval_seconds: int
    heartbeat_timeout_seconds: int


class HeartbeatMessage(CamelizedBaseStruct, tag="heartbeat", tag_field="type"):
    """Client message renewing the runtime lease."""

    sent_at: datetime


class PushPayload(CamelizedBaseStruct):
    """Display content delivered to the client overlay."""

    comment_display: str
    quick_reply: str
    cue: str
    created_at: datetime


class PushMessage(CamelizedBaseStruct, tag="push", tag_field="type"):
    """Server message delivering an approved workflow result."""

    message_id: str
    runtime_id: str
    room_id: str
    payload: PushPayload


class AckMessage(CamelizedBaseStruct, tag="ack", tag_field="type"):
    """Client acknowledgement sent immediately after receiving a push."""

    message_id: str
    status: Literal["received"]
    sent_at: datetime


class RuntimeStatusReason(CamelizedBaseStruct):
    """User-facing explanation attached to a runtime status event."""

    error_code: RuntimeEventStatus
    message: str
    issue_type: RemediationIssueType


class StatusMessage(CamelizedBaseStruct, tag="status", tag_field="type"):
    """Server message reporting a user-facing runtime status change."""

    message_id: str
    runtime_id: str
    room_id: str
    status: RuntimeEventStatus
    reason: RuntimeStatusReason


type ClientWebSocketMessage = ConnectedMessage | HeartbeatMessage | PushMessage | AckMessage | StatusMessage
