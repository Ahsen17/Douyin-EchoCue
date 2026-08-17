"""Live comment sources for external realtime event streams."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from urllib.parse import quote

from .enum import LiveRoomStatus
from .schema import (
    CommentPayloadStruct,
    DouyinWebSocketMessageStruct,
    LiveCommentEventStruct,
    LiveStatusEventStruct,
    LiveStatusPayloadStruct,
)
from .window import CommentWindowHandler, CommentWindowStruct

__all__ = ("DouyinLiveCommentSource",)


DOUYIN_CHAT_METHOD = "WebcastChatMessage"


class DouyinLiveCommentSource:
    """Adapt douyinLive WebSocket messages into live comment events."""

    def __init__(
        self,
        *,
        ws_base_url: str = "ws://127.0.0.1:1088",
        platform: str = "douyin_live",
    ) -> None:
        self._ws_base_url = ws_base_url.rstrip("/")
        self._platform = platform
        self._live_status_by_room: dict[str, LiveStatusEventStruct] = {}

    def build_url(self, room_identifier: str) -> str:
        """Build the douyinLive WebSocket URL for a room identifier."""

        return f"{self._ws_base_url}/ws/{quote(room_identifier, safe='')}"

    def parse_comment(self, raw_message: str | bytes, *, room_id: str) -> LiveCommentEventStruct | None:
        """Parse a douyinLive WebSocket message into a comment event."""

        message = DouyinWebSocketMessageStruct.decode(raw_message)
        if message.method != DOUYIN_CHAT_METHOD:
            return None

        if not message.content:
            return None

        comment_id = message.comment_id(room_id)

        return LiveCommentEventStruct(
            event_id=f"douyin-live:{comment_id}",
            platform=self._platform,
            event_type="comment",
            room_id=room_id,
            user_id=message.user.user_id,
            occurred_at=message.occurred_at or datetime.now(UTC),
            payload=CommentPayloadStruct(
                comment_id=comment_id,
                content=message.content,
                nickname=message.user.display_name,
            ),
        )

    def parse_live_status(self, raw_message: str | bytes, *, room_id: str) -> LiveStatusEventStruct | None:
        """Parse a douyinLive WebSocket message into a room status event."""

        message = DouyinWebSocketMessageStruct.decode(raw_message)
        status_code = message.status_code
        if status_code is None:
            return None

        occurred_at = message.occurred_at or datetime.now(UTC)
        status = LiveRoomStatus.from_code(status_code)
        event_id = message.status_event_id(room_id, status_code, occurred_at)
        event = LiveStatusEventStruct(
            event_id=f"douyin-live:{event_id}",
            platform=self._platform,
            event_type="live_status",
            room_id=room_id,
            user_id="",
            occurred_at=occurred_at,
            payload=LiveStatusPayloadStruct(
                code=status_code,
                live=status is LiveRoomStatus.ONLINE,
                status=status,
            ),
        )
        self._live_status_by_room[room_id] = event

        return event

    def get_live_status(self, room_id: str) -> LiveStatusEventStruct | None:
        """Return the latest parsed room status event."""

        return self._live_status_by_room.get(room_id)

    async def stream_comments(self, room_identifier: str) -> AsyncIterator[LiveCommentEventStruct]:
        """Stream comment events from a douyinLive WebSocket room."""

        from websockets.asyncio.client import connect  # noqa: PLC0415

        async with connect(self.build_url(room_identifier)) as websocket:
            async for raw_message in websocket:
                if self.parse_live_status(raw_message, room_id=room_identifier) is not None:
                    continue

                event = self.parse_comment(raw_message, room_id=room_identifier)
                if event is not None:
                    yield event

    async def stream_windows(
        self,
        room_identifier: str,
        *,
        window_handler: CommentWindowHandler | None = None,
    ) -> AsyncIterator[CommentWindowStruct]:
        """Stream comment window snapshots from douyinLive comment events."""

        handler = window_handler or CommentWindowHandler()
        async for event in self.stream_comments(room_identifier):
            yield await handler.ingest_comment(event)
