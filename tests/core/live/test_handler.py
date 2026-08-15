from datetime import UTC, datetime, timedelta

from aigc.core.live import CommentPayloadStruct, CommentWindowHandler, LiveCommentEventStruct, SemanticType


def _comment_event(
    *,
    event_id: str,
    comment_id: str,
    user_id: str,
    content: str,
    occurred_at: datetime,
) -> LiveCommentEventStruct:
    return LiveCommentEventStruct(
        event_id=event_id,
        platform="douyin_mock",
        event_type="comment",
        room_id="room-a",
        user_id=user_id,
        occurred_at=occurred_at,
        payload=CommentPayloadStruct(
            comment_id=comment_id,
            content=content,
            nickname=f"nick-{user_id}",
        ),
    )


def test_comment_window_aggregates_comment_count_users_and_text_batch() -> None:
    handler = CommentWindowHandler(window_duration=timedelta(seconds=60))
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    handler.ingest_comment(
        _comment_event(event_id="event-1", comment_id="comment-1", user_id="user-a", content="多少钱", occurred_at=now)
    )
    window = handler.ingest_comment(
        _comment_event(
            event_id="event-2", comment_id="comment-2", user_id="user-a", content="有优惠吗", occurred_at=now
        )
    )

    assert window.total_count == 2
    assert window.unique_user_count == 1
    assert window.text_batch == ["多少钱", "有优惠吗"]
    assert window.semantic_type is SemanticType.OTHER


def test_comment_window_uses_thirty_second_window_by_default() -> None:
    handler = CommentWindowHandler()
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    window = handler.ingest_comment(
        _comment_event(
            event_id="event-1",
            comment_id="comment-1",
            user_id="user-a",
            content="默认窗口",
            occurred_at=now,
        )
    )

    assert window.window_started_at == now - timedelta(seconds=30)
    assert window.window_ended_at == now


def test_comment_window_ignores_duplicate_comments_and_prunes_expired_items() -> None:
    handler = CommentWindowHandler(window_duration=timedelta(seconds=30))
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    handler.ingest_comment(
        _comment_event(
            event_id="event-old",
            comment_id="comment-old",
            user_id="user-a",
            content="旧弹幕",
            occurred_at=now - timedelta(seconds=31),
        )
    )
    handler.ingest_comment(
        _comment_event(
            event_id="event-duplicate-1",
            comment_id="comment-live",
            user_id="user-b",
            content="第一条",
            occurred_at=now,
        )
    )
    window = handler.ingest_comment(
        _comment_event(
            event_id="event-duplicate-2",
            comment_id="comment-live",
            user_id="user-c",
            content="重复弹幕",
            occurred_at=now,
        )
    )

    assert window.total_count == 1
    assert window.unique_user_count == 1
    assert window.text_batch == ["第一条"]
