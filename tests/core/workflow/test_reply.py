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
    AutoGenReplyAgent,
    AutoGenReplyAgentFactory,
    ReplyAgentExecutionConfigStruct,
    ReplyAgentInputStruct,
    ReplyAgentOutput,
    WorkflowPersonaContextStruct,
    WorkflowReplyHandler,
    WorkflowReplyInputRoomMismatchError,
    WorkflowRunStruct,
    WorkflowStageName,
    WorkflowStatus,
)


class ScriptedReplyAgent(AutoGenReplyAgent):
    """Concrete ReplyAgent test double with scripted raw outputs."""

    def __init__(self, outputs: list[Any]) -> None:
        self._outputs = iter(outputs)
        self.correction_contexts: list[dict[str, Any] | None] = []

    async def generate(self, correction_context: dict[str, Any] | None = None) -> Any:
        """Record correction context and return the next configured raw output."""

        self.correction_contexts.append(correction_context)
        return next(self._outputs)


class StaticReplyAgentFactory(AutoGenReplyAgentFactory):
    """ReplyAgent factory that returns one deterministic fake agent."""

    def __init__(self, agent: ScriptedReplyAgent) -> None:
        self.agent = agent
        self.inputs: list[ReplyAgentInputStruct] = []

    def create(self, data: ReplyAgentInputStruct) -> ScriptedReplyAgent:
        """Record the input and return the configured fake agent."""

        self.inputs.append(data)
        return self.agent


def _reply_input(*, room_id: str = "room-a") -> ReplyAgentInputStruct:
    return ReplyAgentInputStruct(
        room_id=room_id,
        persona_context=WorkflowPersonaContextStruct(
            room_id=room_id,
            persona_id=UUID("00000000-0000-7000-8000-000000000010"),
            persona_version=4,
            published_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
            persona_name="Host A",
            persona_summary="Warm, witty host persona.",
        ),
        selected_comment=SemanticClassificationCandidateStruct(
            comment_id="comment-1",
            text="主播今天状态太好了",
            semantic_type=SemanticType.PERSONA_PRAISE,
            score=1.2,
            confidence=0.9,
        ),
        interest_score=0.95,
        interest_type=SemanticType.PERSONA_PRAISE,
        interest_reason="Specific praise that is easy to answer naturally.",
    )


class TestWorkflowReplyHandler:
    async def test_records_validated_reply_result_in_stage(self) -> None:
        agent = ScriptedReplyAgent(
            [
                {
                    "comment_display": "主播今天状态太好了",
                    "quick_reply": "谢谢夸奖,今天状态确实不错.",
                    "cue": "顺着状态聊一下最近的安排",
                    "confidence": 0.91,
                }
            ]
        )
        factory = StaticReplyAgentFactory(agent)
        handler = WorkflowReplyHandler(
            factory,
            ReplyAgentExecutionConfigStruct(provider_name="fake", model_id="fake-model"),
        )
        generated_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

        evaluated = await handler.generate_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _reply_input(),
            generated_at=generated_at,
        )

        assert evaluated.workflow_status is WorkflowStatus.PENDING
        assert evaluated.attempt_count == 1
        assert factory.inputs == [_reply_input()]
        assert evaluated.reply_stage is not None
        assert evaluated.reply_stage.stage_name is WorkflowStageName.REPLY_STAGE
        assert evaluated.reply_stage.output["agent_result"]["quick_reply"] == "谢谢夸奖,今天状态确实不错."
        assert evaluated.reply_stage.attempts[0].input["provider_name"] == "fake"
        assert evaluated.reply_stage.attempts[0].output["raw_output"]["confidence"] == 0.91
        assert evaluated.reply_stage.error is None

    async def test_retries_after_validation_error_with_correction_context(self) -> None:
        agent = ScriptedReplyAgent(
            [
                {
                    "comment_display": "主播今天状态太好了",
                    "quick_reply": "谢谢夸奖",
                    "confidence": 1.2,
                },
                {
                    "comment_display": "主播今天状态太好了",
                    "quick_reply": "谢谢夸奖,今天状态确实不错.",
                    "cue": "顺着状态聊一下最近的安排",
                    "confidence": 0.9,
                },
            ]
        )
        handler = WorkflowReplyHandler(StaticReplyAgentFactory(agent))

        evaluated = await handler.generate_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _reply_input(),
            generated_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert evaluated.workflow_status is WorkflowStatus.PENDING
        assert evaluated.attempt_count == 2
        assert evaluated.reply_stage is not None
        assert len(evaluated.reply_stage.attempts) == 2
        assert evaluated.reply_stage.attempts[0].error is not None
        assert evaluated.reply_stage.attempts[0].error["type"] == "ValidationError"
        assert agent.correction_contexts[1] is not None
        raw_output = agent.correction_contexts[1]["raw_output"]
        assert isinstance(raw_output, dict)
        assert raw_output["confidence"] == 1.2
        validation_error = agent.correction_contexts[1]["validation_error"]
        assert isinstance(validation_error, dict)
        assert validation_error["type"] == "ValidationError"

    async def test_marks_workflow_aborted_when_attempts_are_exhausted(self) -> None:
        agent = ScriptedReplyAgent(
            [
                {"comment_display": "主播今天状态太好了", "quick_reply": "谢谢夸奖", "confidence": 1.2},
                {"comment_display": "主播今天状态太好了", "quick_reply": "谢谢夸奖", "confidence": 1.2},
                {"comment_display": "主播今天状态太好了", "quick_reply": "谢谢夸奖", "confidence": 1.2},
            ]
        )
        handler = WorkflowReplyHandler(StaticReplyAgentFactory(agent))

        evaluated = await handler.generate_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _reply_input(),
            generated_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert evaluated.workflow_status is WorkflowStatus.ABORTED
        assert evaluated.skip_reason == "reply_agent_attempts_exhausted"
        assert evaluated.attempt_count == 3
        assert evaluated.reply_stage is not None
        assert evaluated.reply_stage.error == {
            "type": "ReplyAgentAttemptsExhausted",
            "message": "Reply agent attempts were exhausted; workflow run was aborted.",
        }

    async def test_rejects_reply_input_from_a_different_room(self) -> None:
        agent = ScriptedReplyAgent([])
        handler = WorkflowReplyHandler(StaticReplyAgentFactory(agent))

        with pytest.raises(WorkflowReplyInputRoomMismatchError) as exc_info:
            await handler.generate_workflow_run(
                WorkflowRunStruct(room_id="room-a"),
                _reply_input(room_id="room-b"),
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
    """Minimal AssistantAgent behavior required by AutoGenReplyAgent tests."""

    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = iter(outcomes)
        self.model_context = _FakeModelContext()
        self.tasks: list[TextMessage] = []

    async def run(self, *, task: TextMessage) -> TaskResult:
        """Record the user message and return or raise the scripted outcome."""

        self.tasks.append(task)
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            self.model_context.messages.append(AssistantMessage(content="{invalid json", source="reply_agent"))
            raise outcome

        structured_content = ReplyAgentOutput.model_validate(outcome)
        return TaskResult(
            messages=[
                StructuredMessage[ReplyAgentOutput](
                    content=structured_content,
                    source="reply_agent",
                )
            ]
        )


class TestAutoGenReplyAgent:
    async def test_sends_only_latest_correction_as_a_user_message(self) -> None:
        fake_agent = _FakeAssistantAgent(
            [
                {
                    "comment_display": "主播今天状态太好了",
                    "quick_reply": "谢谢夸奖,今天状态确实不错.",
                    "cue": "顺着状态聊一下最近的安排",
                    "confidence": 0.91,
                }
            ]
        )
        agent = AutoGenReplyAgent(cast("AssistantAgent", fake_agent))
        correction_context: dict[str, Any] = {
            "raw_output": {"comment_display": "主播今天状态太好了", "confidence": 1.2},
            "validation_error": {"type": "ValidationError", "message": "Invalid reply output."},
        }

        await agent.generate(correction_context)

        assert fake_agent.tasks[0].source == "user"
        assert "validation_error" in fake_agent.tasks[0].content
        assert "Invalid reply output." in fake_agent.tasks[0].content
        assert "confidence" in fake_agent.tasks[0].content

    async def test_recovers_raw_output_after_autogen_structured_validation_failure(self) -> None:
        validation_error = _structured_validation_error()
        fake_agent = _FakeAssistantAgent([validation_error])
        agent = AutoGenReplyAgent(cast("AssistantAgent", fake_agent))

        with pytest.raises(Exception) as exc_info:
            await agent.generate()

        assert exc_info.value.__class__.__name__ == "ReplyAgentInvocationError"
        assert getattr(exc_info.value, "raw_output") == "{invalid json"


def _structured_validation_error() -> ValidationError:
    try:
        ReplyAgentOutput.model_validate(
            {
                "comment_display": "主播今天状态太好了",
                "quick_reply": "谢谢夸奖,今天状态确实不错.",
                "confidence": 2,
            }
        )
    except ValidationError as exc:
        return exc

    msg = "Expected invalid ReplyAgent output to produce a ValidationError."
    raise AssertionError(msg)
