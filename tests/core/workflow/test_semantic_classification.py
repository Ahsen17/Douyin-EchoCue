from datetime import UTC, datetime

import pytest

from echocue.core.lexicon import (
    SemanticClassificationCandidateStruct,
    SemanticClassificationRequestStruct,
    SemanticClassificationResultStruct,
    SemanticType,
)
from echocue.core.live import (
    CommentWindowItemStruct,
    CommentWindowWorkflowInputStruct,
)
from echocue.core.workflow import (
    WorkflowRunStruct,
    WorkflowSemanticClassificationHandler,
    WorkflowSemanticClassificationRoomMismatchError,
    WorkflowStageName,
)


class StaticSemanticClassificationClient:
    """Deterministic semantic classification client for workflow tests."""

    def __init__(self, result: SemanticClassificationResultStruct) -> None:
        self.result = result
        self.requests: list[SemanticClassificationRequestStruct] = []

    async def classify(self, request: SemanticClassificationRequestStruct) -> SemanticClassificationResultStruct:
        """Record a request and return the configured classification result."""

        self.requests.append(request)
        return self.result


class FailingSemanticClassificationClient:
    """Semantic classification client that simulates a remote service failure."""

    async def classify(self, request: SemanticClassificationRequestStruct) -> SemanticClassificationResultStruct:
        """Raise the configured infrastructure failure."""

        del request
        raise RuntimeError("qdrant unavailable")


def _comment_window_input(*, room_id: str = "room-a") -> CommentWindowWorkflowInputStruct:
    occurred_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    comments = [
        CommentWindowItemStruct(
            comment_id="comment-1",
            user_id="user-a",
            nickname="nick-a",
            content="主播今天状态太好了",
            occurred_at=occurred_at,
        ),
        CommentWindowItemStruct(
            comment_id="comment-2",
            user_id="user-b",
            nickname="nick-b",
            content="这波操作笑死我了",
            occurred_at=occurred_at,
        ),
    ]
    return CommentWindowWorkflowInputStruct(
        room_id=room_id,
        window_started_at=occurred_at,
        window_ended_at=occurred_at,
        total_count=len(comments),
        unique_user_count=len(comments),
        comments=comments,
        text_batch=[comment.content for comment in comments],
        semantic_type=SemanticType.OTHER,
        confidence=0,
        top_n=2,
        candidates=[],
    )


class TestWorkflowSemanticClassificationHandler:
    async def test_records_lexicon_request_and_successful_result(self) -> None:
        classified_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        result = SemanticClassificationResultStruct(
            semantic_type=SemanticType.PERSONA_PRAISE,
            confidence=0.9,
            top_n=2,
            candidates=[
                SemanticClassificationCandidateStruct(
                    comment_id="comment-1",
                    text="主播今天状态太好了",
                    semantic_type=SemanticType.PERSONA_PRAISE,
                    score=1.2,
                    confidence=0.9,
                )
            ],
        )
        classification_client = StaticSemanticClassificationClient(result)
        handler = WorkflowSemanticClassificationHandler(classification_client)
        workflow_run = WorkflowRunStruct(room_id="room-a")

        classified = await handler.classify_workflow_run(
            workflow_run,
            _comment_window_input(),
            classified_at=classified_at,
        )

        assert workflow_run.semantic_type is SemanticType.OTHER
        assert classified.semantic_type is SemanticType.PERSONA_PRAISE
        assert classification_client.requests[0].room_id == "room-a"
        assert classification_client.requests[0].text_batch == ["主播今天状态太好了", "这波操作笑死我了"]
        assert [comment.comment_id for comment in classification_client.requests[0].comment_batch] == [
            "comment-1",
            "comment-2",
        ]
        assert classified.semantic_classification_stage is not None
        assert classified.semantic_classification_stage.stage_name is WorkflowStageName.SEMANTIC_CLASSIFICATION_STAGE
        assert classified.semantic_classification_stage.started_at == classified_at
        assert classified.semantic_classification_stage.completed_at == classified_at
        assert classified.semantic_classification_stage.latency_ms == 0
        assert classified.semantic_classification_stage.input["top_n"] == 2
        assert classified.semantic_classification_stage.output["semantic_type"] == "persona_praise"
        assert classified.semantic_classification_stage.error is None

    async def test_preserves_low_confidence_other_result(self) -> None:
        result = SemanticClassificationResultStruct(
            semantic_type=SemanticType.OTHER,
            confidence=0.5,
            top_n=2,
            candidates=[
                SemanticClassificationCandidateStruct(
                    comment_id="comment-1",
                    text="主播今天状态太好了",
                    semantic_type=SemanticType.PERSONA_PRAISE,
                    score=1,
                    confidence=1,
                ),
                SemanticClassificationCandidateStruct(
                    comment_id="comment-2",
                    text="这波操作笑死我了",
                    semantic_type=SemanticType.PLAYFUL_JOKE,
                    score=1,
                    confidence=1,
                ),
            ],
        )
        classification_client = StaticSemanticClassificationClient(result)
        handler = WorkflowSemanticClassificationHandler(classification_client)

        classified = await handler.classify_workflow_run(
            WorkflowRunStruct(room_id="room-a", semantic_type=SemanticType.PERSONA_PRAISE),
            _comment_window_input(),
            classified_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert classified.semantic_type is SemanticType.OTHER
        assert classified.semantic_classification_stage is not None
        assert classified.semantic_classification_stage.output["semantic_type"] == "other"
        assert classified.semantic_classification_stage.output["confidence"] == 0.5
        assert len(classified.semantic_classification_stage.output["candidates"]) == 2
        assert classified.semantic_classification_stage.error is None

    async def test_falls_back_to_other_and_records_client_failure(self) -> None:
        handler = WorkflowSemanticClassificationHandler(FailingSemanticClassificationClient())

        classified = await handler.classify_workflow_run(
            WorkflowRunStruct(room_id="room-a", semantic_type=SemanticType.PERSONA_PRAISE),
            _comment_window_input(),
            classified_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert classified.semantic_type is SemanticType.OTHER
        assert classified.semantic_classification_stage is not None
        assert classified.semantic_classification_stage.output["semantic_type"] == "other"
        assert classified.semantic_classification_stage.output["top_n"] == 2
        assert classified.semantic_classification_stage.error == {
            "type": "RuntimeError",
            "message": "Semantic classification service failed.",
        }

    async def test_rejects_comment_window_from_a_different_room(self) -> None:
        handler = WorkflowSemanticClassificationHandler(
            StaticSemanticClassificationClient(SemanticClassificationResultStruct.other())
        )

        with pytest.raises(WorkflowSemanticClassificationRoomMismatchError) as exc_info:
            await handler.classify_workflow_run(
                WorkflowRunStruct(room_id="room-a"),
                _comment_window_input(room_id="room-b"),
            )

        assert "room-a" in exc_info.value.message
        assert "room-b" in exc_info.value.message
