"""Live event schemas for simulated livestream comments and room status.

This module defines the HTTP request, service-layer event, and API view object
boundaries for comment ingestion and room status updates. It does not perform
window aggregation.
"""

from datetime import UTC, datetime
from typing import Literal

from msgspec import field, json

from aigc.base import BaseStruct, CamelizedBaseStruct

from ._conversion import convert_struct
from .enum import LiveRoomStatus, LiveStatusCode

__all__ = (
    "CommentPayloadCreate",
    "CommentPayloadStruct",
    "CommentPayloadVO",
    "DouyinCommonMessageStruct",
    "DouyinStatusPayloadStruct",
    "DouyinUserStruct",
    "DouyinWebSocketMessageStruct",
    "LiveCommentEventCreate",
    "LiveCommentEventStruct",
    "LiveCommentEventVO",
    "LiveStatusEventCreate",
    "LiveStatusEventStruct",
    "LiveStatusEventVO",
    "LiveStatusPayloadCreate",
    "LiveStatusPayloadStruct",
    "LiveStatusPayloadVO",
)


class DouyinCommonMessageStruct(BaseStruct):
    """Common metadata carried by douyinLive WebSocket messages."""

    msg_id_camel: str = field(default="", name="msgId")
    msg_id: str = ""
    create_time_camel: int | float | str | None = field(default=None, name="createTime")
    create_time: int | float | str | None = None

    @property
    def message_id(self) -> str:
        """Return the normalized message ID."""

        return self.msg_id_camel or self.msg_id

    @property
    def occurred_at(self) -> datetime | None:
        """Return the normalized event time when present."""

        timestamp = self.create_time_camel or self.create_time
        if isinstance(timestamp, str) and timestamp.isdecimal():
            timestamp = int(timestamp)
        if isinstance(timestamp, int | float):
            seconds = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
            return datetime.fromtimestamp(seconds, tz=UTC)

        return None


class DouyinUserStruct(BaseStruct):
    """User metadata carried by douyinLive chat messages."""

    id: str = ""
    short_id: str = field(default="", name="shortId")
    sec_uid: str = field(default="", name="secUid")
    nickname: str = ""

    @property
    def user_id(self) -> str:
        """Return the normalized user ID."""

        return self.id or self.short_id or self.sec_uid or "unknown"

    @property
    def display_name(self) -> str:
        """Return the normalized user display name."""

        return self.nickname or "unknown"


class DouyinStatusPayloadStruct(BaseStruct):
    """Status payload carried by douyinLive status messages."""

    code: str = ""
    event: str = ""
    status: bool | str | None = None
    live: bool | None = None


class DouyinWebSocketMessageStruct(BaseStruct):
    """Typed douyinLive WebSocket message decoded by msgspec."""

    method: str = ""
    event: str = ""
    code: str = ""
    status: bool | str | None = None
    live: bool | None = None
    msg_id_camel: str = field(default="", name="msgId")
    msg_id: str = ""
    content: str = ""
    common: DouyinCommonMessageStruct = field(default_factory=DouyinCommonMessageStruct)
    user: DouyinUserStruct = field(default_factory=DouyinUserStruct)
    payload: DouyinStatusPayloadStruct = field(default_factory=DouyinStatusPayloadStruct)

    @classmethod
    def decode(cls, raw_message: str | bytes) -> "DouyinWebSocketMessageStruct":
        """Decode a raw douyinLive WebSocket JSON message."""

        raw_bytes = raw_message if isinstance(raw_message, bytes) else raw_message.encode()
        return json.decode(raw_bytes, type=cls)

    @property
    def message_id(self) -> str:
        """Return the normalized message ID."""

        return self.common.message_id or self.msg_id_camel or self.msg_id

    @property
    def occurred_at(self) -> datetime | None:
        """Return the normalized event time when present."""

        return self.common.occurred_at

    @property
    def status_code(self) -> LiveStatusCode | None:
        """Return the normalized live status code when this is a status message."""

        raw_code = self.code or self.payload.code
        if raw_code:
            return LiveStatusCode.from_external(raw_code)

        event = self.event or self.payload.event
        if event != "live_status":
            return None

        status = self.status if self.status is not None else self.payload.status
        if isinstance(status, bool):
            return LiveStatusCode.ROOM_ONLINE if status else LiveStatusCode.ROOM_OFFLINE
        if isinstance(status, str):
            return LiveStatusCode.from_external(status)

        live = self.live if self.live is not None else self.payload.live
        if isinstance(live, bool):
            return LiveStatusCode.ROOM_ONLINE if live else LiveStatusCode.ROOM_OFFLINE

        return None

    def comment_id(self, room_id: str) -> str:
        """Return a stable comment ID for a chat message."""

        return self.message_id or f"{room_id}:{self.user.user_id}:{self.content}"

    def status_event_id(self, room_id: str, code: LiveStatusCode, occurred_at: datetime) -> str:
        """Return a stable status event ID."""

        return self.message_id or f"{room_id}:live_status:{code.value}:{int(occurred_at.timestamp())}"


class CommentPayloadStruct(BaseStruct):
    """Normalized comment payload extracted from a livestream event."""

    comment_id: str
    content: str
    nickname: str


class CommentPayloadCreate(CamelizedBaseStruct):
    """Comment payload request body accepted from the simulator."""

    comment_id: str
    content: str
    nickname: str

    def to_struct(self) -> CommentPayloadStruct:
        """Convert the request payload to a service-layer payload."""

        return convert_struct(self, CommentPayloadStruct)


class CommentPayloadVO(CamelizedBaseStruct):
    """Comment payload view object returned by API endpoints."""

    comment_id: str
    content: str
    nickname: str

    @classmethod
    def from_struct(cls, data: CommentPayloadStruct) -> "CommentPayloadVO":
        """Build a view object from a service-layer payload."""

        return convert_struct(data, cls)


class LiveCommentEventStruct(BaseStruct):
    """Service-layer livestream comment event."""

    event_id: str
    platform: str
    event_type: Literal["comment"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: CommentPayloadStruct


class LiveCommentEventCreate(CamelizedBaseStruct):
    """Comment event request body accepted from the simulator."""

    event_id: str
    platform: str
    event_type: Literal["comment"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: CommentPayloadCreate

    def to_struct(self) -> LiveCommentEventStruct:
        """Convert the request body to a service-layer event."""

        return convert_struct(self, LiveCommentEventStruct)


class LiveCommentEventVO(CamelizedBaseStruct):
    """Comment event view object returned by API endpoints."""

    event_id: str
    platform: str
    event_type: Literal["comment"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: CommentPayloadVO

    @classmethod
    def from_struct(cls, data: LiveCommentEventStruct) -> "LiveCommentEventVO":
        """Build a view object from a service-layer event."""

        return convert_struct(data, cls)


class LiveStatusPayloadStruct(BaseStruct):
    """Normalized room status payload extracted from a livestream event."""

    code: LiveStatusCode
    live: bool
    status: LiveRoomStatus


class LiveStatusPayloadCreate(CamelizedBaseStruct):
    """Room status payload request body accepted from live event sources."""

    code: LiveStatusCode
    live: bool
    status: LiveRoomStatus

    def to_struct(self) -> LiveStatusPayloadStruct:
        """Convert the request payload to a service-layer payload."""

        return convert_struct(self, LiveStatusPayloadStruct)


class LiveStatusPayloadVO(CamelizedBaseStruct):
    """Room status payload view object returned by API endpoints."""

    code: LiveStatusCode
    live: bool
    status: LiveRoomStatus

    @classmethod
    def from_struct(cls, data: LiveStatusPayloadStruct) -> "LiveStatusPayloadVO":
        """Build a view object from a service-layer payload."""

        return convert_struct(data, cls)


class LiveStatusEventStruct(BaseStruct):
    """Service-layer livestream room status event."""

    event_id: str
    platform: str
    event_type: Literal["live_status"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: LiveStatusPayloadStruct


class LiveStatusEventCreate(CamelizedBaseStruct):
    """Room status event request body accepted from live event sources."""

    event_id: str
    platform: str
    event_type: Literal["live_status"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: LiveStatusPayloadCreate

    def to_struct(self) -> LiveStatusEventStruct:
        """Convert the request body to a service-layer event."""

        return convert_struct(self, LiveStatusEventStruct)


class LiveStatusEventVO(CamelizedBaseStruct):
    """Room status event view object returned by API endpoints."""

    event_id: str
    platform: str
    event_type: Literal["live_status"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: LiveStatusPayloadVO

    @classmethod
    def from_struct(cls, data: LiveStatusEventStruct) -> "LiveStatusEventVO":
        """Build a view object from a service-layer event."""

        return convert_struct(data, cls)
