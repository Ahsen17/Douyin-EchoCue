"""Workflow trigger evaluation for comment-window inputs."""

from datetime import datetime, timedelta

from echocue.core.lexicon import SemanticType
from echocue.core.live import CommentWindowCandidateStruct, CommentWindowWorkflowInputStruct

from .enum import WorkflowStageName, WorkflowStatus, WorkflowTriggerType
from .schema import (
    WorkflowRunStruct,
    WorkflowStageEnvelopeStruct,
    WorkflowTriggerEvaluationStruct,
    WorkflowTriggerParametersStruct,
)

__all__ = (
    "WorkflowTriggerEvaluator",
)


class WorkflowTriggerEvaluator:
    """Evaluate whether a comment window should start a workflow run."""

    def __init__(self, parameters: WorkflowTriggerParametersStruct | None = None) -> None:
        self._parameters = parameters or WorkflowTriggerParametersStruct()

    def evaluate(
        self,
        data: CommentWindowWorkflowInputStruct,
        *,
        last_pushed_at: datetime | None = None,
        evaluated_at: datetime | None = None,
    ) -> WorkflowTriggerEvaluationStruct:
        """Evaluate trigger rules and return a structured decision."""

        now = evaluated_at or data.window_ended_at
        cooldown_until = self._get_cooldown_until(last_pushed_at)
        if cooldown_until is not None and now < cooldown_until:
            return WorkflowTriggerEvaluationStruct(
                should_trigger=False,
                trigger_type=None,
                parameters=self._parameters,
                evaluated_at=now,
                last_pushed_at=last_pushed_at,
                blocked_reason="cooldown_active",
                cooldown_until=cooldown_until,
            )

        candidate = self._select_high_value_candidate(data.candidates)
        if candidate is not None:
            return WorkflowTriggerEvaluationStruct(
                should_trigger=True,
                trigger_type=WorkflowTriggerType.HIGH_VALUE_COMMENT,
                parameters=self._parameters,
                evaluated_at=now,
                last_pushed_at=last_pushed_at,
                selected_candidate_id=candidate.comment_id,
                selected_candidate_text=candidate.text,
                selected_candidate_semantic_type=candidate.semantic_type,
                selected_candidate_score=candidate.score,
                selected_candidate_confidence=candidate.confidence,
            )

        if self._can_trigger_scheduled_window(data):
            return WorkflowTriggerEvaluationStruct(
                should_trigger=True,
                trigger_type=WorkflowTriggerType.SCHEDULED_COMMENT_WINDOW,
                parameters=self._parameters,
                evaluated_at=now,
                last_pushed_at=last_pushed_at,
            )

        return WorkflowTriggerEvaluationStruct(
            should_trigger=False,
            trigger_type=None,
            parameters=self._parameters,
            evaluated_at=now,
            last_pushed_at=last_pushed_at,
            blocked_reason="comment_window_below_threshold",
        )

    def _get_cooldown_until(self, last_pushed_at: datetime | None) -> datetime | None:
        if last_pushed_at is None:
            return None

        return last_pushed_at + timedelta(seconds=self._parameters.cooldown_seconds)

    def _select_high_value_candidate(
        self,
        candidates: list[CommentWindowCandidateStruct],
    ) -> CommentWindowCandidateStruct | None:
        qualified = [
            candidate
            for candidate in candidates
            if candidate.semantic_type in self._parameters.high_value_semantic_types
            and candidate.semantic_type is not SemanticType.OTHER
            and candidate.confidence >= self._parameters.high_value_confidence_threshold
            and candidate.score >= self._parameters.high_value_score_threshold
        ]
        if not qualified:
            return None

        return max(qualified, key=lambda candidate: (candidate.confidence, candidate.score))

    def _can_trigger_scheduled_window(self, data: CommentWindowWorkflowInputStruct) -> bool:
        return (
            data.total_count >= self._parameters.minimum_comment_count
            and data.confidence >= self._parameters.minimum_window_confidence
        )


def build_workflow_run_from_comment_window(
    data: CommentWindowWorkflowInputStruct,
    evaluation: WorkflowTriggerEvaluationStruct,
) -> WorkflowRunStruct:
    """Build the initial workflow run snapshot from comment-window trigger evaluation."""

    workflow_status = WorkflowStatus.PENDING if evaluation.should_trigger else WorkflowStatus.ABORTED
    completed_at = None if evaluation.should_trigger else evaluation.evaluated_at

    return WorkflowRunStruct(
        room_id=data.room_id,
        workflow_status=workflow_status,
        semantic_type=data.semantic_type,
        trigger_type=evaluation.trigger_type,
        skip_reason=evaluation.blocked_reason,
        completed_at=completed_at,
        comment_window_stage=WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.COMMENT_WINDOW_STAGE,
            started_at=data.window_started_at,
            completed_at=data.window_ended_at,
            latency_ms=0,
            input={"room_id": data.room_id},
            output=data.to_dict(),
        ),
        trigger_evaluation_stage=WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.TRIGGER_EVALUATION_STAGE,
            started_at=evaluation.evaluated_at,
            completed_at=evaluation.evaluated_at,
            latency_ms=0,
            input={
                "last_pushed_at": evaluation.last_pushed_at,
                "parameters": evaluation.parameters.to_dict(),
            },
            output=evaluation.to_dict(),
        ),
    )
