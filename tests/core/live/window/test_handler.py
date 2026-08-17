from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from msgspec.structs import fields
from qdrant_client import AsyncQdrantClient

from aigc.core.lexicon import QdrantSemanticClassificationClient, SemanticType
from aigc.core.lexicon.lexicon import rebuild_lexicon_collection
from aigc.core.live import (
    CommentPayloadStruct,
    CommentWindowHandler,
    CommentWindowWorkflowInputStruct,
    CommentWindowWorkflowInputVO,
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


class TestCommentWindowHandler:
    now: datetime

    @pytest.fixture(autouse=True)
    def set_up(self) -> None:
        self.now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

    async def test_aggregates_comment_count_users_text_batch_and_semantic_type(self) -> None:
        handler = CommentWindowHandler(window_duration=timedelta(seconds=60))

        await handler.ingest_comment(
            _comment_event(
                event_id="event-1",
                comment_id="comment-1",
                user_id="user-a",
                content="主播今天状态太好了",
                occurred_at=self.now,
            )
        )
        window = await handler.ingest_comment(
            _comment_event(
                event_id="event-2",
                comment_id="comment-2",
                user_id="user-a",
                content="团队也太强了",
                occurred_at=self.now,
            )
        )

        assert window.total_count == 2
        assert window.unique_user_count == 1
        assert window.text_batch == ["主播今天状态太好了", "团队也太强了"]
        assert window.semantic_type is SemanticType.PERSONA_PRAISE
        assert window.confidence == 1
        assert window.top_n == 5
        assert [candidate.comment_id for candidate in window.candidates] == ["comment-1", "comment-2"]
        assert [candidate.text for candidate in window.candidates] == ["主播今天状态太好了", "团队也太强了"]
        assert all(candidate.semantic_type is SemanticType.PERSONA_PRAISE for candidate in window.candidates)
        assert all(candidate.confidence == 1 for candidate in window.candidates)

    async def test_uses_ten_second_window_by_default(self) -> None:
        handler = CommentWindowHandler()

        window = await handler.ingest_comment(
            _comment_event(
                event_id="event-1",
                comment_id="comment-1",
                user_id="user-a",
                content="默认窗口",
                occurred_at=self.now,
            )
        )

        assert window.window_started_at == self.now - timedelta(seconds=10)
        assert window.window_ended_at == self.now

    async def test_ignores_duplicate_comments_and_prunes_expired_items(self) -> None:
        handler = CommentWindowHandler(window_duration=timedelta(seconds=30))

        await handler.ingest_comment(
            _comment_event(
                event_id="event-old",
                comment_id="comment-old",
                user_id="user-a",
                content="旧弹幕",
                occurred_at=self.now - timedelta(seconds=31),
            )
        )
        await handler.ingest_comment(
            _comment_event(
                event_id="event-duplicate-1",
                comment_id="comment-live",
                user_id="user-b",
                content="第一条",
                occurred_at=self.now,
            )
        )
        window = await handler.ingest_comment(
            _comment_event(
                event_id="event-duplicate-2",
                comment_id="comment-live",
                user_id="user-c",
                content="重复弹幕",
                occurred_at=self.now,
            )
        )

        assert window.total_count == 1
        assert window.unique_user_count == 1
        assert window.text_batch == ["第一条"]

    async def test_returns_other_when_classification_is_unreliable(self) -> None:
        handler = CommentWindowHandler()

        window = await handler.ingest_comment(
            _comment_event(
                event_id="event-1",
                comment_id="comment-1",
                user_id="user-a",
                content="abc",
                occurred_at=self.now,
            )
        )

        assert window.semantic_type is SemanticType.OTHER

    async def test_uses_injected_qdrant_classification_client(self, tmp_path: Path) -> None:
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

        window = await handler.ingest_comment(
            _comment_event(
                event_id="event-1",
                comment_id="comment-1",
                user_id="user-a",
                content="主播今天状态太好了",
                occurred_at=self.now,
            )
        )
        await qdrant_client.close()

        assert window.semantic_type is SemanticType.PERSONA_PRAISE
        assert window.confidence > 0
        assert window.candidates[0].comment_id == "comment-1"
        assert window.candidates[0].text == "主播今天状态太好了"
        assert window.candidates[0].semantic_type is SemanticType.PERSONA_PRAISE

    async def test_limits_top_n_candidates(self) -> None:
        handler = CommentWindowHandler(top_n=1)

        await handler.ingest_comment(
            _comment_event(
                event_id="event-1",
                comment_id="comment-1",
                user_id="user-a",
                content="主播今天状态太好了",
                occurred_at=self.now,
            )
        )
        window = await handler.ingest_comment(
            _comment_event(
                event_id="event-2",
                comment_id="comment-2",
                user_id="user-b",
                content="这波操作笑死我了",
                occurred_at=self.now,
            )
        )

        assert window.top_n == 1
        assert len(window.candidates) == 1

    async def test_builds_comment_window_workflow_input_without_persona_profile_fields(self) -> None:
        handler = CommentWindowHandler(window_duration=timedelta(seconds=60), top_n=1)

        window = await handler.ingest_comment(
            _comment_event(
                event_id="event-1",
                comment_id="comment-1",
                user_id="user-a",
                content="主播今天状态太好了",
                occurred_at=self.now,
            )
        )

        workflow_input = CommentWindowWorkflowInputStruct.from_window(window)
        workflow_input_vo = CommentWindowWorkflowInputVO.from_struct(workflow_input)
        field_names = {field.name for field in fields(CommentWindowWorkflowInputStruct)}

        assert workflow_input.room_id == "room-a"
        assert workflow_input.window_started_at == self.now - timedelta(seconds=60)
        assert workflow_input.window_ended_at == self.now
        assert workflow_input.total_count == 1
        assert workflow_input.unique_user_count == 1
        assert workflow_input.text_batch == ["主播今天状态太好了"]
        assert workflow_input.semantic_type is SemanticType.PERSONA_PRAISE
        assert workflow_input.confidence == 1
        assert workflow_input.top_n == 1
        assert workflow_input.candidates[0].comment_id == "comment-1"
        assert workflow_input.candidates[0].text == "主播今天状态太好了"
        assert workflow_input_vo.candidates[0].semantic_type is SemanticType.PERSONA_PRAISE
        assert "persona_id" not in field_names
        assert "persona_version" not in field_names
