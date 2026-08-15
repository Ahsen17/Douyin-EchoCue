"""Live comment sources for external realtime event streams."""

from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from urllib.parse import quote

from msgspec import json

from .handler import CommentWindowHandler
from .schema import CommentPayloadStruct, LiveCommentEventStruct
from .window import CommentWindowStruct

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

    def build_url(self, room_identifier: str) -> str:
        """Build the douyinLive WebSocket URL for a room identifier."""

        return f"{self._ws_base_url}/ws/{quote(room_identifier, safe='')}"

    def parse_comment(self, raw_message: str | bytes, *, room_id: str) -> LiveCommentEventStruct | None:
        """Parse a douyinLive WebSocket message into a comment event."""

        raw_bytes = raw_message if isinstance(raw_message, bytes) else raw_message.encode()
        message = json.decode(raw_bytes, type=dict[str, object])
        if message.get("method") != DOUYIN_CHAT_METHOD:
            return None

        content = _get_string(message, "content")
        if not content:
            return None

        user = _get_mapping(message, "user")
        common = _get_mapping(message, "common")
        comment_id = (
            _get_string(common, "msgId")
            or _get_string(common, "msg_id")
            or _get_string(message, "msgId")
            or _get_string(message, "msg_id")
            or f"{room_id}:{_get_string(user, 'id') or 'unknown'}:{content}"
        )
        user_id = _get_string(user, "id") or _get_string(user, "shortId") or _get_string(user, "secUid") or "unknown"
        nickname = _get_string(user, "nickname") or "unknown"

        return LiveCommentEventStruct(
            event_id=f"douyin-live:{comment_id}",
            platform=self._platform,
            event_type="comment",
            room_id=room_id,
            user_id=user_id,
            occurred_at=_parse_occurred_at(common) or datetime.now(UTC),
            payload=CommentPayloadStruct(
                comment_id=comment_id,
                content=content,
                nickname=nickname,
            ),
        )

    async def stream_comments(self, room_identifier: str) -> AsyncIterator[LiveCommentEventStruct]:
        """Stream comment events from a douyinLive WebSocket room."""

        from websockets.asyncio.client import connect  # noqa: PLC0415

        async with connect(self.build_url(room_identifier)) as websocket:
            async for raw_message in websocket:
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
            yield handler.ingest_comment(event)


def _get_mapping(data: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _get_string(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else ""


def _parse_occurred_at(common: Mapping[str, object]) -> datetime | None:
    timestamp = common.get("createTime") or common.get("create_time")
    if isinstance(timestamp, str) and timestamp.isdecimal():
        return _datetime_from_timestamp(int(timestamp))
    if isinstance(timestamp, int | float):
        return _datetime_from_timestamp(timestamp)

    return None


def _datetime_from_timestamp(timestamp: float) -> datetime:
    seconds = timestamp / 1000 if timestamp > 10_000_000_000 else timestamp
    return datetime.fromtimestamp(seconds, tz=UTC)
