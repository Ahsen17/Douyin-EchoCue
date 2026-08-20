import asyncio
import json
from datetime import UTC, datetime

import pytest

from echocue.core.live import (
    CommentWindowHandler,
    DouyinLiveCommentSource,
    DouyinLiveDisconnectedError,
    DouyinLiveFirstStatusError,
    DouyinLiveFirstStatusTimeoutError,
    DouyinLiveGateway,
    DouyinLiveProtocolError,
    LiveRoomStatus,
    LiveStatusCode,
)


class FakeSocket:
    def __init__(self, messages: list[str | bytes | Exception]) -> None:
        self._messages = iter(messages)
        self.close_count = 0

    async def recv(self) -> str | bytes:
        message = next(self._messages)
        if isinstance(message, Exception):
            raise message
        return message

    async def close(self) -> None:
        self.close_count += 1


class HangingSocket(FakeSocket):
    async def recv(self) -> str | bytes:
        await asyncio.sleep(10)
        return "{}"


def _status(code: str) -> str:
    return json.dumps({"event": "live_status", "payload": {"code": code}})


def _comment() -> str:
    return json.dumps(
        {
            "method": "WebcastChatMessage",
            "common": {"msgId": "comment-1"},
            "user": {"id": "user-1", "nickname": "用户一"},
            "content": "你好",
        }
    )


class TestDouyinLiveCommentSource:
    def test_parses_chat_message_to_comment_event(self) -> None:
        source = DouyinLiveCommentSource(ws_base_url="ws://douyin-live:1088")
        raw_message = {
            "method": "WebcastChatMessage",
            "common": {"msgId": "msg-1", "createTime": 1_786_795_200_000},
            "user": {"id": "user-1", "nickname": "用户一"},
            "content": "主播今天状态太好了",
        }

        event = source.parse_comment(json.dumps(raw_message), room_id="room-a")

        assert event is not None
        assert event.event_id == "douyin-live:msg-1"
        assert event.platform == "douyin_live"
        assert event.room_id == "room-a"
        assert event.user_id == "user-1"
        assert event.occurred_at == datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
        assert event.payload.comment_id == "msg-1"
        assert event.payload.content == "主播今天状态太好了"
        assert event.payload.nickname == "用户一"

    def test_ignores_non_comment_messages(self) -> None:
        source = DouyinLiveCommentSource()
        raw_message = {"type": "system", "event": "live_status", "status": True}

        event = source.parse_comment(json.dumps(raw_message), room_id="room-a")

        assert event is None

    def test_parses_live_status_event_and_maintains_latest_room_status(self) -> None:
        source = DouyinLiveCommentSource()
        raw_message = {
            "event": "live_status",
            "common": {"msgId": "status-1", "createTime": 1_786_795_200_000},
            "payload": {"code": "ROOM_ONLINE"},
        }

        event = source.parse_live_status(json.dumps(raw_message), room_id="room-a")

        assert event is not None
        assert event.event_id == "douyin-live:status-1"
        assert event.platform == "douyin_live"
        assert event.event_type == "live_status"
        assert event.room_id == "room-a"
        assert event.user_id == ""
        assert event.occurred_at == datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
        assert event.payload.code is LiveStatusCode.ROOM_ONLINE
        assert event.payload.live is True
        assert event.payload.status is LiveRoomStatus.ONLINE
        assert source.get_live_status("room-a") == event

    def test_parses_live_status_boolean_compatibility_message(self) -> None:
        source = DouyinLiveCommentSource()
        raw_message = {"event": "live_status", "status": False}

        event = source.parse_live_status(json.dumps(raw_message), room_id="room-a")

        assert event is not None
        assert event.payload.code is LiveStatusCode.ROOM_OFFLINE
        assert event.payload.live is False
        assert event.payload.status is LiveRoomStatus.OFFLINE

    def test_parses_room_ended_status_event(self) -> None:
        source = DouyinLiveCommentSource()
        raw_message = {"event": "live_status", "status": "ended"}

        event = source.parse_live_status(json.dumps(raw_message), room_id="room-a")

        assert event is not None
        assert event.payload.code is LiveStatusCode.ROOM_ENDED
        assert event.payload.live is False
        assert event.payload.status is LiveRoomStatus.ENDED

    def test_builds_room_websocket_url(self) -> None:
        source = DouyinLiveCommentSource(ws_base_url="ws://douyin-live:1088/")

        assert source.build_url("516466932480") == "ws://douyin-live:1088/ws/516466932480"

    async def test_pushes_comment_event_to_comment_window(self) -> None:
        source = DouyinLiveCommentSource()
        event = source.parse_comment(
            json.dumps(
                {
                    "method": "WebcastChatMessage",
                    "common": {"msgId": "msg-1", "createTime": 1_786_800_000_000},
                    "user": {"id": "user-1", "nickname": "用户一"},
                    "content": "主播今天状态太好了",
                }
            ),
            room_id="room-a",
        )

        assert event is not None
        window = await CommentWindowHandler().ingest_comment(event)

        assert window.total_count == 1
        assert window.unique_user_count == 1
        assert window.text_batch == ["主播今天状态太好了"]

    async def test_live_status_event_does_not_enter_comment_window(self) -> None:
        source = DouyinLiveCommentSource()
        status_event = source.parse_live_status(
            json.dumps({"event": "live_status", "payload": {"code": "ROOM_ONLINE"}}),
            room_id="room-a",
        )

        assert status_event is not None
        window = await CommentWindowHandler().get_window("room-a", now=status_event.occurred_at)

        assert window.total_count == 0
        assert window.unique_user_count == 0
        assert window.text_batch == []


class TestDouyinLiveGateway:
    async def test_waits_for_online_and_keeps_connection_for_following_events(self) -> None:
        socket = FakeSocket([_status("ROOM_ONLINE"), _comment(), _status("ROOM_ENDED")])

        async def connector(url: str, timeout: float) -> FakeSocket:
            assert url.endswith("/ws/room-a")
            assert timeout == 1
            return socket

        connection = await DouyinLiveGateway(
            connector=connector,
            connect_timeout=1,
            first_status_timeout=1,
        ).connect("room-a")
        events = []
        async for event in connection.events():
            events.append(event)
            if len(events) == 3:
                break

        assert [event.event_type for event in events] == ["live_status", "comment", "live_status"]
        assert socket.close_count == 0
        await connection.close()
        await connection.close()
        assert socket.close_count == 1

    async def test_rejects_first_non_online_status_and_closes_socket(self) -> None:
        socket = FakeSocket([_status("ROOM_OFFLINE")])

        async def connector(url: str, timeout: float) -> FakeSocket:
            return socket

        with pytest.raises(DouyinLiveFirstStatusError):
            await DouyinLiveGateway(connector=connector).connect("room-a")

        assert socket.close_count == 1

    async def test_first_status_timeout_closes_socket(self) -> None:
        socket = HangingSocket([])

        async def connector(url: str, timeout: float) -> FakeSocket:
            return socket

        with pytest.raises(DouyinLiveFirstStatusTimeoutError):
            await DouyinLiveGateway(connector=connector, first_status_timeout=0).connect("room-a")

        assert socket.close_count == 1

    async def test_invalid_payload_is_protocol_error(self) -> None:
        socket = FakeSocket(["{"])

        async def connector(url: str, timeout: float) -> FakeSocket:
            return socket

        with pytest.raises(DouyinLiveProtocolError):
            await DouyinLiveGateway(connector=connector).connect("room-a")

        assert socket.close_count == 1

    async def test_remote_disconnect_is_classified_and_closes_socket(self) -> None:
        socket = FakeSocket([_status("ROOM_ONLINE"), EOFError()])

        async def connector(url: str, timeout: float) -> FakeSocket:
            return socket

        connection = await DouyinLiveGateway(connector=connector).connect("room-a")
        with pytest.raises(DouyinLiveDisconnectedError):
            _ = [event async for event in connection.events()]

        assert socket.close_count == 1
