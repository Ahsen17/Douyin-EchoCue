from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import StructuredMessage, TextMessage
from autogen_core.models import AssistantMessage
from pydantic import ValidationError

from echocue.core.lexicon import SemanticClassificationCandidateStruct, SemanticType
from echocue.core.workflow import (
    AutoGenReviewAgent,
    AutoGenReviewAgentFactory,
    ReplyAgentOutput,
    ReviewAgentExecutionConfigStruct,
    ReviewAgentInputStruct,
    ReviewAgentOutput,
    SafetyRuleScanConfigStruct,
    SafetyRuleScanResultStruct,
    WorkflowPersonaContextStruct,
    WorkflowPushAction,
    WorkflowReviewHandler,
    WorkflowReviewInputRoomMismatchError,
    WorkflowRunStruct,
    WorkflowSafetyRuleScanner,
    WorkflowStageName,
    WorkflowStatus,
)


class ScriptedReviewAgent(AutoGenReviewAgent):
    """Concrete ReviewAgent test double with scripted raw outputs."""

    def __init__(self, outputs: list[Any]) -> None:
        self._outputs = iter(outputs)
        self.correction_contexts: list[dict[str, Any] | None] = []

    async def generate(self, correction_context: dict[str, Any] | None = None) -> Any:
        """Record correction context and return the next configured raw output."""

        self.correction_contexts.append(correction_context)
        return next(self._outputs)


class StaticReviewAgentFactory(AutoGenReviewAgentFactory):
    """ReviewAgent factory that returns one deterministic fake agent."""

    def __init__(self, agent: ScriptedReviewAgent) -> None:
        self.agent = agent
        self.inputs: list[ReviewAgentInputStruct] = []

    def create(self, data: ReviewAgentInputStruct) -> ScriptedReviewAgent:
        """Record the input and return the configured fake agent."""

        self.inputs.append(data)
        return self.agent


def _persona_context(*, room_id: str = "room-a") -> WorkflowPersonaContextStruct:
    return WorkflowPersonaContextStruct(
        room_id=room_id,
        persona_id=UUID("00000000-0000-7000-8000-000000000010"),
        persona_version=4,
        published_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        persona_name="Host A",
        persona_summary="Warm, witty host persona.",
    )


def _selected_comment(*, room_id: str = "room-a") -> SemanticClassificationCandidateStruct:
    _ = room_id
    return SemanticClassificationCandidateStruct(
        comment_id="comment-1",
        text="主播今天状态太好了",
        semantic_type=SemanticType.PERSONA_PRAISE,
        score=1.2,
        confidence=0.9,
    )


def _review_input(
    *,
    room_id: str = "room-a",
    safety_scan: SafetyRuleScanResultStruct | None = None,
) -> ReviewAgentInputStruct:
    return ReviewAgentInputStruct(
        room_id=room_id,
        persona_context=_persona_context(room_id=room_id),
        selected_comment=_selected_comment(room_id=room_id),
        reply=ReplyAgentOutput(
            comment_display="主播今天状态太好了",
            quick_reply="谢谢夸奖,今天状态确实不错.",
            cue="顺着状态聊一下最近的安排",
            confidence=0.91,
        ),
        semantic_type=SemanticType.PERSONA_PRAISE,
        safety_scan=safety_scan
        or SafetyRuleScanResultStruct(
            global_rule_version=1,
            risk_categories=[],
        ),
    )


class TestWorkflowSafetyRuleScanner:
    def test_records_risk_evidence_without_final_push_decision(self) -> None:
        scanner = WorkflowSafetyRuleScanner(
            SafetyRuleScanConfigStruct(
                global_rule_version=7,
                prohibited_keywords={"abuse": ["垃圾主播"]},
            )
        )
        scanned_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

        workflow_run, result = scanner.scan(
            WorkflowRunStruct(room_id="room-a"),
            {
                "selected_comment": "主播今天状态太好了",
                "quick_reply": "不要说垃圾主播这种话.",
            },
            scanned_at=scanned_at,
        )

        assert result.risk_categories == ["abuse"]
        assert result.violations[0].evidence_field == "quick_reply"
        assert workflow_run.global_rule_version == 7
        assert workflow_run.risk_categories == ["abuse"]
        assert workflow_run.push_action is None
        assert workflow_run.review_stage is not None
        assert workflow_run.review_stage.stage_name is WorkflowStageName.REVIEW_STAGE
        assert workflow_run.review_stage.output["safety_scan"]["risk_categories"] == ["abuse"]


class TestWorkflowReviewHandler:
    async def test_records_push_review_result_in_stage(self) -> None:
        agent = ScriptedReviewAgent(
            [
                {
                    "push_action": "push",
                    "review_category": "safe_high_confidence",
                    "risk_categories": [],
                    "skip_reason": None,
                    "review_note": "Reply matches the persona and is safe to push.",
                }
            ]
        )
        factory = StaticReviewAgentFactory(agent)
        handler = WorkflowReviewHandler(
            factory,
            ReviewAgentExecutionConfigStruct(provider_name="fake", model_id="fake-model"),
        )
        reviewed_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

        reviewed = await handler.review_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _review_input(),
            reviewed_at=reviewed_at,
        )

        assert reviewed.workflow_status is WorkflowStatus.COMPLETED
        assert reviewed.push_action is WorkflowPushAction.PUSH
        assert reviewed.review_category == "safe_high_confidence"
        assert reviewed.skip_reason is None
        assert reviewed.attempt_count == 1
        assert factory.inputs == [_review_input()]
        assert reviewed.review_stage is not None
        assert reviewed.review_stage.attempts[0].input["provider_name"] == "fake"
        assert reviewed.review_stage.output["agent_result"]["push_action"] == "push"

    async def test_records_skip_review_result_with_safety_risks(self) -> None:
        safety_scan = SafetyRuleScanResultStruct(
            global_rule_version=2,
            risk_categories=["abuse"],
        )
        agent = ScriptedReviewAgent(
            [
                {
                    "push_action": "skip",
                    "review_category": "safety_uncertain",
                    "risk_categories": ["abuse"],
                    "skip_reason": "safety_risk_detected",
                    "review_note": "Safety scan found abusive language in the generated reply.",
                }
            ]
        )
        handler = WorkflowReviewHandler(StaticReviewAgentFactory(agent))

        reviewed = await handler.review_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _review_input(safety_scan=safety_scan),
            reviewed_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert reviewed.workflow_status is WorkflowStatus.COMPLETED
        assert reviewed.push_action is WorkflowPushAction.SKIP
        assert reviewed.risk_categories == ["abuse"]
        assert reviewed.skip_reason == "safety_risk_detected"

    async def test_retries_when_review_omits_scan_risk_categories(self) -> None:
        safety_scan = SafetyRuleScanResultStruct(
            global_rule_version=2,
            risk_categories=["abuse"],
        )
        agent = ScriptedReviewAgent(
            [
                {
                    "push_action": "skip",
                    "review_category": "safety_uncertain",
                    "risk_categories": [],
                    "skip_reason": "safety_risk_detected",
                    "review_note": "Risk noted but category omitted.",
                },
                {
                    "push_action": "skip",
                    "review_category": "safety_uncertain",
                    "risk_categories": ["abuse"],
                    "skip_reason": "safety_risk_detected",
                    "review_note": "Safety scan found abusive language.",
                },
            ]
        )
        handler = WorkflowReviewHandler(StaticReviewAgentFactory(agent))

        reviewed = await handler.review_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _review_input(safety_scan=safety_scan),
            reviewed_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert reviewed.workflow_status is WorkflowStatus.COMPLETED
        assert reviewed.attempt_count == 2
        assert reviewed.review_stage is not None
        assert reviewed.review_stage.attempts[0].error is not None
        assert reviewed.review_stage.attempts[0].error["type"] == "ValueError"
        assert agent.correction_contexts[1] is not None
        correction_context = agent.correction_contexts[1]
        assert correction_context is not None
        validation_error = correction_context["validation_error"]
        assert validation_error["type"] == "ValueError"

    async def test_marks_workflow_aborted_when_review_attempts_are_exhausted(self) -> None:
        agent = ScriptedReviewAgent(
            [
                {"push_action": "skip", "review_category": "safety_uncertain", "review_note": "missing reason"},
                {"push_action": "skip", "review_category": "safety_uncertain", "review_note": "missing reason"},
                {"push_action": "skip", "review_category": "safety_uncertain", "review_note": "missing reason"},
            ]
        )
        handler = WorkflowReviewHandler(StaticReviewAgentFactory(agent))

        reviewed = await handler.review_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _review_input(),
            reviewed_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert reviewed.workflow_status is WorkflowStatus.ABORTED
        assert reviewed.push_action is WorkflowPushAction.SKIP
        assert reviewed.skip_reason == "review_agent_attempts_exhausted"
        assert reviewed.attempt_count == 3
        assert reviewed.review_stage is not None
        assert reviewed.review_stage.error == {
            "type": "ReviewAgentAttemptsExhausted",
            "message": "Review agent attempts were exhausted; workflow run was aborted.",
        }

    async def test_rejects_review_input_from_a_different_room(self) -> None:
        agent = ScriptedReviewAgent([])
        handler = WorkflowReviewHandler(StaticReviewAgentFactory(agent))

        with pytest.raises(WorkflowReviewInputRoomMismatchError) as exc_info:
            await handler.review_workflow_run(
                WorkflowRunStruct(room_id="room-a"),
                _review_input(room_id="room-b"),
            )

        assert "room-a" in exc_info.value.message
        assert "room-b" in exc_info.value.message


class _FakeModelContext:
    """In-memory AutoGen model context used to verify retry message handling."""

    def __init__(self) -> None:
        self.messages: list[Any] = []

    async def get_messages(self) -> list[Any]:
        """Return the current model message history."""

        return list(self.messages)


class _FakeAssistantAgent:
    """Minimal AssistantAgent behavior required by AutoGenReviewAgent tests."""

    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = iter(outcomes)
        self.model_context = _FakeModelContext()
        self.tasks: list[TextMessage] = []

    async def run(self, *, task: TextMessage) -> TaskResult:
        """Record the user message and return or raise the scripted outcome."""

        self.tasks.append(task)
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            self.model_context.messages.append(AssistantMessage(content="{invalid json", source="review_agent"))
            raise outcome

        structured_content = ReviewAgentOutput.model_validate(outcome)
        return TaskResult(
            messages=[
                StructuredMessage[ReviewAgentOutput](
                    content=structured_content,
                    source="review_agent",
                )
            ]
        )


class TestAutoGenReviewAgent:
    async def test_sends_only_latest_correction_as_a_user_message(self) -> None:
        fake_agent = _FakeAssistantAgent(
            [
                {
                    "push_action": "push",
                    "review_category": "safe_high_confidence",
                    "risk_categories": [],
                    "skip_reason": None,
                    "review_note": "Valid result.",
                }
            ]
        )
        agent = AutoGenReviewAgent(cast("AssistantAgent", fake_agent))
        correction_context: dict[str, Any] = {
            "raw_output": {"push_action": "skip", "review_category": "safety_uncertain"},
            "validation_error": {"type": "ValueError", "message": "Skip decision needs skip_reason."},
        }

        await agent.generate(correction_context)

        assert fake_agent.tasks[0].source == "user"
        assert "review_input" not in fake_agent.tasks[0].content
        assert "Skip decision needs skip_reason." in fake_agent.tasks[0].content
        assert "safety_uncertain" in fake_agent.tasks[0].content

    async def test_recovers_raw_output_after_autogen_structured_validation_failure(self) -> None:
        validation_error = _structured_validation_error()
        fake_agent = _FakeAssistantAgent([validation_error])
        agent = AutoGenReviewAgent(cast("AssistantAgent", fake_agent))

        with pytest.raises(Exception) as exc_info:
            await agent.generate()

        assert type(exc_info.value).__name__ == "ReviewAgentInvocationError"
        assert getattr(exc_info.value, "raw_output") == "{invalid json"


def _structured_validation_error() -> ValidationError:
    try:
        ReviewAgentOutput.model_validate(
            {
                "push_action": "push",
                "review_category": "safe_high_confidence",
                "review_note": "",
            }
        )
    except ValidationError as exc:
        return exc

    raise AssertionError("Expected a validation error.")
