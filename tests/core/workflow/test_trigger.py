from datetime import UTC, datetime, timedelta

from echocue.core.lexicon import SemanticType
from echocue.core.live import (
    CommentWindowCandidateStruct,
    CommentWindowItemStruct,
    CommentWindowWorkflowInputStruct,
)
from echocue.core.workflow import (
    WorkflowStageName,
    WorkflowStatus,
    WorkflowTriggerEvaluator,
    WorkflowTriggerParametersStruct,
    WorkflowTriggerType,
)
from echocue.core.workflow.trigger import build_workflow_run_from_comment_window


def _workflow_input(
    *,
    total_count: int = 1,
    confidence: float = 0,
    candidates: list[CommentWindowCandidateStruct] | None = None,
) -> CommentWindowWorkflowInputStruct:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    comments = [
        CommentWindowItemStruct(
            comment_id="comment-1",
            user_id="user-a",
            nickname="nick-a",
            content="主播今天状态太好了",
            occurred_at=now,
        )
    ][:total_count]

    return CommentWindowWorkflowInputStruct(
        room_id="room-a",
        window_started_at=now - timedelta(seconds=10),
        window_ended_at=now,
        total_count=total_count,
        unique_user_count=len({comment.user_id for comment in comments}),
        comments=comments,
        text_batch=[comment.content for comment in comments],
        semantic_type=SemanticType.PERSONA_PRAISE if total_count else SemanticType.OTHER,
        confidence=confidence,
        top_n=5,
        candidates=candidates or [],
    )


def _candidate(
    *,
    comment_id: str = "comment-1",
    semantic_type: SemanticType = SemanticType.PERSONA_PRAISE,
    score: float = 1,
    confidence: float = 1,
) -> CommentWindowCandidateStruct:
    return CommentWindowCandidateStruct(
        comment_id=comment_id,
        text="主播今天状态太好了",
        semantic_type=semantic_type,
        score=score,
        confidence=confidence,
    )


class TestWorkflowTriggerEvaluator:
    def test_scheduled_comment_window_triggers_with_default_parameters(self) -> None:
        data = _workflow_input()

        result = WorkflowTriggerEvaluator().evaluate(data)

        assert result.should_trigger is True
        assert result.trigger_type is WorkflowTriggerType.SCHEDULED_COMMENT_WINDOW
        assert result.parameters.minimum_comment_count == 1
        assert result.parameters.cooldown_seconds == 30
        assert result.blocked_reason is None

    def test_high_value_comment_candidate_has_priority_over_scheduled_window(self) -> None:
        data = _workflow_input(candidates=[_candidate(score=1.2, confidence=0.9)])

        result = WorkflowTriggerEvaluator().evaluate(data)

        assert result.should_trigger is True
        assert result.trigger_type is WorkflowTriggerType.HIGH_VALUE_COMMENT
        assert result.selected_candidate_id == "comment-1"
        assert result.selected_candidate_semantic_type is SemanticType.PERSONA_PRAISE
        assert result.selected_candidate_score == 1.2
        assert result.selected_candidate_confidence == 0.9

    def test_cooldown_blocks_window_and_high_value_triggers(self) -> None:
        data = _workflow_input(candidates=[_candidate(score=1.2, confidence=0.9)])
        last_pushed_at = data.window_ended_at - timedelta(seconds=10)

        result = WorkflowTriggerEvaluator().evaluate(data, last_pushed_at=last_pushed_at)

        assert result.should_trigger is False
        assert result.trigger_type is None
        assert result.last_pushed_at == last_pushed_at
        assert result.blocked_reason == "cooldown_active"
        assert result.cooldown_until == last_pushed_at + timedelta(seconds=30)
        assert result.selected_candidate_id is None

    def test_comment_window_below_threshold_does_not_trigger(self) -> None:
        data = _workflow_input(total_count=0)
        parameters = WorkflowTriggerParametersStruct(minimum_comment_count=1)

        result = WorkflowTriggerEvaluator(parameters).evaluate(data)

        assert result.should_trigger is False
        assert result.trigger_type is None
        assert result.blocked_reason == "comment_window_below_threshold"

    def test_builds_initial_workflow_run_with_comment_and_trigger_stages(self) -> None:
        data = _workflow_input(candidates=[_candidate(score=1.2, confidence=0.9)])
        evaluation = WorkflowTriggerEvaluator().evaluate(data)

        workflow_run = build_workflow_run_from_comment_window(data, evaluation)

        assert workflow_run.room_id == "room-a"
        assert workflow_run.workflow_status is WorkflowStatus.PENDING
        assert workflow_run.trigger_type is WorkflowTriggerType.HIGH_VALUE_COMMENT
        assert workflow_run.skip_reason is None
        assert workflow_run.comment_window_stage is not None
        assert workflow_run.comment_window_stage.stage_name is WorkflowStageName.COMMENT_WINDOW_STAGE
        assert workflow_run.comment_window_stage.output["room_id"] == "room-a"
        assert workflow_run.trigger_evaluation_stage is not None
        assert workflow_run.trigger_evaluation_stage.stage_name is WorkflowStageName.TRIGGER_EVALUATION_STAGE
        assert workflow_run.trigger_evaluation_stage.output["should_trigger"] is True

    def test_builds_aborted_workflow_run_when_trigger_is_blocked(self) -> None:
        data = _workflow_input()
        last_pushed_at = data.window_ended_at - timedelta(seconds=10)
        evaluation = WorkflowTriggerEvaluator().evaluate(data, last_pushed_at=last_pushed_at)

        workflow_run = build_workflow_run_from_comment_window(data, evaluation)

        assert workflow_run.workflow_status is WorkflowStatus.ABORTED
        assert workflow_run.trigger_type is None
        assert workflow_run.skip_reason == "cooldown_active"
        assert workflow_run.completed_at == evaluation.evaluated_at
        assert workflow_run.trigger_evaluation_stage is not None
        assert workflow_run.trigger_evaluation_stage.input["last_pushed_at"] == last_pushed_at
