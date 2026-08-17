from datetime import UTC, datetime, timedelta
from pathlib import Path

from qdrant_client import AsyncQdrantClient

from aigc.core.lexicon import QdrantSemanticClassificationClient, SemanticType
from aigc.core.lexicon.lexicon import rebuild_lexicon_collection
from aigc.core.live import (
    CommentPayloadStruct,
    CommentWindowHandler,
    LiveCommentEventStruct,
)


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


async def test_comment_window_aggregates_comment_count_users_text_batch_and_semantic_type() -> None:
    handler = CommentWindowHandler(window_duration=timedelta(seconds=60))
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    await handler.ingest_comment(
        _comment_event(
            event_id="event-1",
            comment_id="comment-1",
            user_id="user-a",
            content="主播今天状态太好了",
            occurred_at=now,
        )
    )
    window = await handler.ingest_comment(
        _comment_event(
            event_id="event-2",
            comment_id="comment-2",
            user_id="user-a",
            content="团队也太强了",
            occurred_at=now,
        )
    )

    assert window.total_count == 2
    assert window.unique_user_count == 1
    assert window.text_batch == ["主播今天状态太好了", "团队也太强了"]
    assert window.semantic_type is SemanticType.PERSONA_PRAISE


async def test_comment_window_uses_thirty_second_window_by_default() -> None:
    handler = CommentWindowHandler()
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    window = await handler.ingest_comment(
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


async def test_comment_window_ignores_duplicate_comments_and_prunes_expired_items() -> None:
    handler = CommentWindowHandler(window_duration=timedelta(seconds=30))
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    await handler.ingest_comment(
        _comment_event(
            event_id="event-old",
            comment_id="comment-old",
            user_id="user-a",
            content="旧弹幕",
            occurred_at=now - timedelta(seconds=31),
        )
    )
    await handler.ingest_comment(
        _comment_event(
            event_id="event-duplicate-1",
            comment_id="comment-live",
            user_id="user-b",
            content="第一条",
            occurred_at=now,
        )
    )
    window = await handler.ingest_comment(
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


async def test_comment_window_returns_other_when_classification_is_unreliable() -> None:
    handler = CommentWindowHandler()
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    window = await handler.ingest_comment(
        _comment_event(
            event_id="event-1",
            comment_id="comment-1",
            user_id="user-a",
            content="abc",
            occurred_at=now,
        )
    )

    assert window.semantic_type is SemanticType.OTHER


async def test_comment_window_uses_injected_qdrant_classification_client(tmp_path: Path) -> None:
    samples_file = tmp_path / "lexicon_samples.jsonl"
    samples_file.write_text(
        '{"id":"persona_praise_000001","semantic_type":"persona_praise","text":"主播今天状态太好了","description":"praise"}\n'
        '{"id":"playful_joke_000001","semantic_type":"playful_joke","text":"这波操作笑死我了","description":"joke"}\n',
        encoding="utf-8",
    )
    qdrant_client = AsyncQdrantClient(location=":memory:")
    await rebuild_lexicon_collection(qdrant_client, samples_file=samples_file, collection_name="test_lexicon")
    classification_client = QdrantSemanticClassificationClient(qdrant_client, collection_name="test_lexicon")
    handler = CommentWindowHandler(classification_client=classification_client)
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    window = await handler.ingest_comment(
        _comment_event(
            event_id="event-1",
            comment_id="comment-1",
            user_id="user-a",
            content="主播今天状态太好了",
            occurred_at=now,
        )
    )
    await qdrant_client.close()

    assert window.semantic_type is SemanticType.PERSONA_PRAISE
