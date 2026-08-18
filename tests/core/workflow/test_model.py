from datetime import UTC, datetime

from echocue.core.lexicon import SemanticType
from echocue.core.workflow import (
    WorkflowPushAction,
    WorkflowRuns,
    WorkflowRunService,
    WorkflowRunStruct,
    WorkflowStageEnvelopeStruct,
    WorkflowStageName,
    WorkflowStatus,
    WorkflowTriggerType,
)


class TestWorkflowRunsModel:
    def test_workflow_runs_table_name_matches_plan(self) -> None:
        assert WorkflowRuns.__tablename__ == "workflow_runs"

    def test_workflow_run_service_uses_workflow_runs_repository(self) -> None:
        assert WorkflowRunService.repository_type.model_type is WorkflowRuns

    def test_model_roundtrip_uses_domain_structs(self) -> None:
        started_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        workflow_run = WorkflowRunStruct(
            room_id="room-a",
            workflow_status=WorkflowStatus.RUNNING,
            trigger_type=WorkflowTriggerType.SCHEDULED_COMMENT_WINDOW,
            semantic_type=SemanticType.PLAYFUL_JOKE,
            push_action=WorkflowPushAction.SKIP,
            attempt_count=1,
            started_at=started_at,
            comment_window_stage=WorkflowStageEnvelopeStruct(
                stage_name=WorkflowStageName.COMMENT_WINDOW_STAGE,
                started_at=started_at,
            ),
        )

        model = WorkflowRuns.from_struct(workflow_run)
        clone = model.to_struct()

        assert model.__tablename__ == "workflow_runs"
        assert model.room_id == "room-a"
        assert model.workflow_status == "running"
        assert model.trigger_type == "scheduled_comment_window"
        assert model.semantic_type == "playful_joke"
        assert model.push_action == "skip"
        assert model.attempt_count == 1
        assert model.risk_categories == []
        assert clone.workflow_status is WorkflowStatus.RUNNING
        assert clone.trigger_type is WorkflowTriggerType.SCHEDULED_COMMENT_WINDOW
        assert clone.semantic_type is SemanticType.PLAYFUL_JOKE
        assert clone.push_action is WorkflowPushAction.SKIP
        assert clone.comment_window_stage is not None
        assert clone.comment_window_stage.stage_name is WorkflowStageName.COMMENT_WINDOW_STAGE
