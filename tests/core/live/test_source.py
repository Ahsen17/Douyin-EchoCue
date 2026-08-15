import json
from datetime import UTC, datetime

from aigc.core.live import CommentWindowHandler, DouyinLiveCommentSource


class TestDouyinLiveCommentSource:
    def test_parses_chat_message_to_comment_event(self) -> None:
        source = DouyinLiveCommentSource(ws_base_url="ws://douyin-live:1088")
        raw_message = {
            "method": "WebcastChatMessage",
            "common": {"msgId": "msg-1", "createTime": 1_786_795_200_000},
            "user": {"id": "user-1", "nickname": "用户一"},
            "content": "这个多少钱",
        }

        event = source.parse_comment(json.dumps(raw_message), room_id="room-a")

        assert event is not None
        assert event.event_id == "douyin-live:msg-1"
        assert event.platform == "douyin_live"
        assert event.room_id == "room-a"
        assert event.user_id == "user-1"
        assert event.occurred_at == datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
        assert event.payload.comment_id == "msg-1"
        assert event.payload.content == "这个多少钱"
        assert event.payload.nickname == "用户一"

    def test_ignores_non_comment_messages(self) -> None:
        source = DouyinLiveCommentSource()
        raw_message = {"type": "system", "event": "live_status", "status": True}

        event = source.parse_comment(json.dumps(raw_message), room_id="room-a")

        assert event is None

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
                    "content": "这个多少钱",
                }
            ),
            room_id="room-a",
        )

        assert event is not None
        window = await CommentWindowHandler().ingest_comment(event)

        assert window.total_count == 1
        assert window.unique_user_count == 1
        assert window.text_batch == ["这个多少钱"]
