from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from echocue.core.lexicon import SemanticClassificationCandidateStruct, SemanticClassificationResultStruct, SemanticType
from echocue.core.live import CommentWindowCandidateStruct, CommentWindowItemStruct, CommentWindowWorkflowInputStruct
from echocue.core.workflow import (
    SafetyRuleScanConfigStruct,
    StaticWorkflowPersonaContextResolver,
    WorkflowExecutionHandler,
    WorkflowInterestHandler,
    WorkflowPersonaContextHandler,
    WorkflowPersonaContextStruct,
    WorkflowPushAction,
    WorkflowReplyHandler,
    WorkflowReviewHandler,
    WorkflowRunStruct,
    WorkflowSafetyRuleScanner,
    WorkflowSemanticClassificationHandler,
    WorkflowStageEnvelopeStruct,
    WorkflowStageName,
    WorkflowStatus,
)
from echocue.core.workflow.schema import ReviewAgentInputStruct
from echocue.core.workflow.service import WorkflowRunService


class RecordingWorkflowRunService(WorkflowRunService):
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def create(self, data: Any, *args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        self.created.append(data)
        return data


class StaticSemanticClassificationClient:
    def __init__(self, result: SemanticClassificationResultStruct) -> None:
        self.result = result

    async def classify(self, request: Any) -> SemanticClassificationResultStruct:
        del request
        return self.result


class StubInterestHandler(WorkflowInterestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def evaluate_workflow_run(
        self,
        workflow_run: WorkflowRunStruct,
        data: Any,
        *,
        evaluated_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        started_at = evaluated_at or datetime.now(UTC)
        evaluated = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        selected_comment = data.candidates[0]
        evaluated.semantic_type = data.semantic_type
        evaluated.attempt_count += 1
        evaluated.interest_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.INTEREST_STAGE,
            started_at=started_at,
            completed_at=started_at,
            latency_ms=0,
            input=data.to_dict(),
            output={
                "agent_name": "interest_agent",
                "agent_result": {
                    "interest_score": selected_comment.score,
                    "interest_type": selected_comment.semantic_type.value,
                    "selected_comment_id": selected_comment.comment_id,
                    "reason": "Selected the strongest candidate.",
                },
                "fallback_used": False,
            },
            attempts=[],
        )
        return evaluated


class StubReplyHandler(WorkflowReplyHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def generate_workflow_run(
        self,
        workflow_run: WorkflowRunStruct,
        data: Any,
        *,
        generated_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        started_at = generated_at or datetime.now(UTC)
        evaluated = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        evaluated.attempt_count += 1
        evaluated.reply_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REPLY_STAGE,
            started_at=started_at,
            completed_at=started_at,
            latency_ms=0,
            input=data.to_dict(),
            output={
                "agent_name": "reply_agent",
                "agent_result": {
                    "comment_display": "主播今天状态太好了",
                    "quick_reply": "谢谢夸奖,今天状态确实不错.",
                    "cue": "顺着状态聊一下最近的安排",
                    "confidence": 0.91,
                },
                "fallback_used": False,
            },
            attempts=[],
        )
        return evaluated


class StubReviewHandler(WorkflowReviewHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def review_workflow_run(
        self,
        workflow_run: WorkflowRunStruct,
        data: ReviewAgentInputStruct,
        *,
        reviewed_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        started_at = reviewed_at or datetime.now(UTC)
        reviewed = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        reviewed.workflow_status = WorkflowStatus.COMPLETED
        reviewed.push_action = WorkflowPushAction.PUSH
        reviewed.review_category = "safe_high_confidence"
        reviewed.review_note = "Safe to push."
        reviewed.skip_reason = None
        reviewed.risk_categories = list(data.safety_scan.risk_categories)
        reviewed.review_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REVIEW_STAGE,
            started_at=started_at,
            completed_at=started_at,
            latency_ms=0,
            input={
                **(workflow_run.review_stage.input if workflow_run.review_stage is not None else {}),
                "review_input": {
                    "room_id": data.room_id,
                    "persona_context": data.persona_context.to_dict(),
                    "selected_comment": data.selected_comment.to_dict(),
                    "reply": data.reply.model_dump(mode="json"),
                    "semantic_type": data.semantic_type.value,
                    "safety_scan": data.safety_scan.to_dict(),
                    "recent_push_records": data.recent_push_records,
                },
            },
            output={
                "safety_scan": data.safety_scan.to_dict(),
                "agent_name": "merge_review_agent",
                "agent_result": {
                    "push_action": "push",
                    "review_category": "safe_high_confidence",
                    "risk_categories": [],
                    "skip_reason": None,
                    "review_note": "Safe to push.",
                },
                "fallback_used": False,
            },
            attempts=[],
        )
        return reviewed


def _workflow_input() -> CommentWindowWorkflowInputStruct:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
    comments = [
        CommentWindowItemStruct(
            comment_id="comment-1",
            user_id="user-a",
            nickname="nick-a",
            content="主播今天状态太好了",
            occurred_at=now,
        )
    ]
    return CommentWindowWorkflowInputStruct(
        room_id="room-a",
        window_started_at=now - timedelta(seconds=10),
        window_ended_at=now,
        total_count=1,
        unique_user_count=1,
        comments=comments,
        text_batch=[comment.content for comment in comments],
        semantic_type=SemanticType.PERSONA_PRAISE,
        confidence=0.95,
        top_n=1,
        candidates=[
            CommentWindowCandidateStruct(
                comment_id="comment-1",
                text="主播今天状态太好了",
                semantic_type=SemanticType.PERSONA_PRAISE,
                score=1.2,
                confidence=0.9,
            )
        ],
    )


def _build_handler(
    *,
    semantic_result: SemanticClassificationResultStruct | None = None,
) -> tuple[WorkflowExecutionHandler, RecordingWorkflowRunService]:
    persona_context = WorkflowPersonaContextStruct(
        room_id="room-a",
        persona_id=UUID("00000000-0000-7000-8000-000000000010"),
        persona_version=4,
        published_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        persona_name="Host A",
        persona_summary="Warm, witty host persona.",
    )
    persona_handler = WorkflowPersonaContextHandler(
        StaticWorkflowPersonaContextResolver({"room-a": persona_context})
    )
    classification_handler = WorkflowSemanticClassificationHandler(
        StaticSemanticClassificationClient(
            semantic_result
            or SemanticClassificationResultStruct(
                semantic_type=SemanticType.PERSONA_PRAISE,
                confidence=0.9,
                top_n=1,
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
        )
    )
    service = RecordingWorkflowRunService()
    handler = WorkflowExecutionHandler(
        persona_context_handler=persona_handler,
        semantic_classification_handler=classification_handler,
        interest_handler=StubInterestHandler(),
        reply_handler=StubReplyHandler(),
        review_handler=StubReviewHandler(),
        safety_rule_scanner=WorkflowSafetyRuleScanner(SafetyRuleScanConfigStruct()),
        workflow_run_service=service,
    )
    return handler, service


class TestWorkflowExecutionHandler:
    async def test_runs_full_workflow_to_completed_snapshot(self) -> None:
        handler, service = _build_handler()

        workflow_run = await handler.run_comment_window_workflow(_workflow_input())

        assert workflow_run.workflow_status is WorkflowStatus.COMPLETED
        assert workflow_run.push_action is WorkflowPushAction.PUSH
        assert workflow_run.review_stage is not None
        assert workflow_run.review_stage.stage_name is WorkflowStageName.REVIEW_STAGE
        assert workflow_run.client_delivery_stage is not None
        assert workflow_run.client_delivery_stage.stage_name is WorkflowStageName.CLIENT_DELIVERY_STAGE
        assert workflow_run.completed_at is not None
        assert len(service.created) == 1
        assert service.created[0]["workflow_status"] == "completed"
        assert service.created[0]["client_delivery_stage"]["stage_name"] == "client_delivery_stage"

    async def test_persists_aborted_snapshot_when_trigger_is_blocked(self) -> None:
        handler, service = _build_handler()
        input_data = _workflow_input()
        blocked_at = input_data.window_ended_at - timedelta(seconds=10)

        workflow_run = await handler.run_comment_window_workflow(
            input_data,
            last_pushed_at=blocked_at,
        )

        assert workflow_run.workflow_status is WorkflowStatus.ABORTED
        assert workflow_run.skip_reason == "cooldown_active"
        assert workflow_run.completed_at == input_data.window_ended_at
        assert len(service.created) == 1
        assert service.created[0]["workflow_status"] == "aborted"

    async def test_marks_workflow_failed_when_a_runtime_error_surfaces(self) -> None:
        handler, service = _build_handler()

        class FailingSemanticHandler(WorkflowSemanticClassificationHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                del args, kwargs

            async def classify_workflow_run(
                self,
                workflow_run: WorkflowRunStruct,
                data: Any,
                *,
                classified_at: datetime | None = None,
            ) -> WorkflowRunStruct:
                del workflow_run, data, classified_at
                raise RuntimeError("semantic backend failed")

        handler._semantic_classification_handler = FailingSemanticHandler()

        workflow_run = await handler.run_comment_window_workflow(_workflow_input())

        assert workflow_run.workflow_status is WorkflowStatus.FAILED
        assert workflow_run.skip_reason == "RuntimeError"
        assert workflow_run.review_stage is not None
        assert workflow_run.review_stage.error == {
            "type": "RuntimeError",
            "message": "Workflow execution failed.",
        }
        assert len(service.created) == 1
        assert service.created[0]["workflow_status"] == "failed"
