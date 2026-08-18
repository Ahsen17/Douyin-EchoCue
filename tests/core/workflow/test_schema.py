from datetime import UTC, datetime
from uuid import UUID

import pytest

from echocue.core.lexicon import SemanticType
from echocue.core.workflow import (
    WorkflowPushAction,
    WorkflowRunStruct,
    WorkflowStageAttemptStruct,
    WorkflowStageEnvelopeStruct,
    WorkflowStageName,
    WorkflowStatus,
    WorkflowTriggerType,
)
from echocue.core.workflow.enum import (
    ensure_workflow_status_transition,
    is_valid_workflow_status_transition,
)


class TestWorkflowSchema:
    def test_workflow_enums_use_canonical_values(self) -> None:
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowTriggerType.SCHEDULED_COMMENT_WINDOW.value == "scheduled_comment_window"
        assert WorkflowPushAction.PUSH.value == "push"
        assert WorkflowStageName.COMMENT_WINDOW_STAGE.value == "comment_window_stage"

    def test_workflow_status_transition_rules(self) -> None:
        assert is_valid_workflow_status_transition(WorkflowStatus.PENDING, WorkflowStatus.RUNNING) is True
        assert is_valid_workflow_status_transition(WorkflowStatus.PENDING, WorkflowStatus.FAILED) is True
        assert is_valid_workflow_status_transition(WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED) is True
        assert is_valid_workflow_status_transition(WorkflowStatus.RUNNING, WorkflowStatus.ABORTED) is True
        assert is_valid_workflow_status_transition(WorkflowStatus.RUNNING, WorkflowStatus.FAILED) is True
        assert is_valid_workflow_status_transition(WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING) is False
        assert is_valid_workflow_status_transition(WorkflowStatus.ABORTED, WorkflowStatus.RUNNING) is False
        assert is_valid_workflow_status_transition(WorkflowStatus.FAILED, WorkflowStatus.RUNNING) is False

        ensure_workflow_status_transition(WorkflowStatus.PENDING, WorkflowStatus.RUNNING)

        with pytest.raises(ValueError, match="completed -> running"):
            ensure_workflow_status_transition(WorkflowStatus.COMPLETED, WorkflowStatus.RUNNING)

    def test_stage_envelope_defaults_are_isolated(self) -> None:
        started_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        envelope = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REPLY_STAGE,
            started_at=started_at,
        )

        envelope.attempts.append(
            WorkflowStageAttemptStruct(
                stage_name=WorkflowStageName.REPLY_STAGE,
                attempt_index=1,
                started_at=started_at,
            )
        )

        other_envelope = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REPLY_STAGE,
            started_at=started_at,
        )

        assert envelope.completed_at is None
        assert envelope.latency_ms is None
        assert envelope.input == {}
        assert envelope.output == {}
        assert envelope.error is None
        assert len(envelope.attempts) == 1
        assert other_envelope.attempts == []

    def test_workflow_run_struct_defaults_cover_stage1_fields(self) -> None:
        workflow_run = WorkflowRunStruct(room_id="room-a")

        assert workflow_run.tenant_id is None
        assert workflow_run.room_id == "room-a"
        assert workflow_run.persona_id is None
        assert workflow_run.persona_version is None
        assert workflow_run.workflow_status is WorkflowStatus.PENDING
        assert workflow_run.trigger_type is None
        assert workflow_run.semantic_type is SemanticType.OTHER
        assert workflow_run.push_action is None
        assert workflow_run.review_category is None
        assert workflow_run.review_note is None
        assert workflow_run.risk_categories == []
        assert workflow_run.skip_reason is None
        assert workflow_run.attempt_count == 0
        assert workflow_run.started_at is None
        assert workflow_run.completed_at is None
        assert workflow_run.latency_ms is None
        assert workflow_run.pushed_to_client is False
        assert workflow_run.delivered_to_client is False
        assert workflow_run.global_rule_version is None
        assert workflow_run.organization_rule_version is None
        assert workflow_run.room_rule_version is None
        assert workflow_run.comment_window_stage is None

    def test_workflow_run_struct_roundtrip_keeps_nested_envelope(self) -> None:
        started_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        workflow_run = WorkflowRunStruct(
            tenant_id=UUID("00000000-0000-7000-8000-000000000001"),
            room_id="room-a",
            persona_id=UUID("00000000-0000-7000-8000-000000000002"),
            persona_version=3,
            workflow_status=WorkflowStatus.RUNNING,
            trigger_type=WorkflowTriggerType.HIGH_VALUE_COMMENT,
            semantic_type=SemanticType.PERSONA_PRAISE,
            push_action=WorkflowPushAction.PUSH,
            review_category="safe_high_confidence",
            review_note="ok",
            risk_categories=["none"],
            skip_reason=None,
            attempt_count=2,
            started_at=started_at,
            completed_at=started_at,
            latency_ms=1200,
            pushed_to_client=True,
            delivered_to_client=False,
            global_rule_version=11,
            organization_rule_version=12,
            room_rule_version=13,
            comment_window_stage=WorkflowStageEnvelopeStruct(
                stage_name=WorkflowStageName.COMMENT_WINDOW_STAGE,
                started_at=started_at,
                completed_at=started_at,
                latency_ms=100,
                input={"room_id": "room-a"},
                output={"total_count": 2},
                attempts=[
                    WorkflowStageAttemptStruct(
                        stage_name=WorkflowStageName.COMMENT_WINDOW_STAGE,
                        attempt_index=1,
                        started_at=started_at,
                        completed_at=started_at,
                        latency_ms=100,
                    )
                ],
            ),
        )

        clone = WorkflowRunStruct.from_dict(workflow_run.to_dict())

        assert clone.room_id == "room-a"
        assert clone.workflow_status is WorkflowStatus.RUNNING
        assert clone.trigger_type is WorkflowTriggerType.HIGH_VALUE_COMMENT
        assert clone.semantic_type is SemanticType.PERSONA_PRAISE
        assert clone.push_action is WorkflowPushAction.PUSH
        assert clone.comment_window_stage is not None
        assert clone.comment_window_stage.stage_name is WorkflowStageName.COMMENT_WINDOW_STAGE
        assert clone.comment_window_stage.attempts[0].attempt_index == 1
