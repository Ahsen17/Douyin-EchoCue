from datetime import UTC, datetime
from typing import Any, cast

import pytest
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import StructuredMessage, TextMessage
from autogen_core.models import AssistantMessage
from pydantic import ValidationError

from echocue.core.lexicon import SemanticClassificationCandidateStruct, SemanticType
from echocue.core.workflow import (
    AutoGenInterestAgent,
    AutoGenInterestAgentFactory,
    InterestAgentExecutionConfigStruct,
    InterestAgentInputStruct,
    InterestAgentOutput,
    WorkflowInterestHandler,
    WorkflowInterestInputRoomMismatchError,
    WorkflowRunStruct,
    WorkflowStageName,
)


class ScriptedInterestAgent(AutoGenInterestAgent):
    """Concrete InterestAgent test double with scripted raw outputs."""

    def __init__(self, outputs: list[Any]) -> None:
        self._outputs = iter(outputs)
        self.correction_contexts: list[dict[str, Any] | None] = []

    async def generate(self, correction_context: dict[str, Any] | None = None) -> Any:
        """Record correction context and return the next configured raw output."""

        self.correction_contexts.append(correction_context)
        return next(self._outputs)


class StaticInterestAgentFactory(AutoGenInterestAgentFactory):
    """InterestAgent factory that returns one deterministic fake agent."""

    def __init__(self, agent: ScriptedInterestAgent) -> None:
        self.agent = agent
        self.inputs: list[InterestAgentInputStruct] = []

    def create(self, data: InterestAgentInputStruct) -> ScriptedInterestAgent:
        """Record the input and return the configured fake agent."""

        self.inputs.append(data)
        return self.agent


def _interest_input(*, room_id: str = "room-a") -> InterestAgentInputStruct:
    return InterestAgentInputStruct(
        room_id=room_id,
        semantic_type=SemanticType.PERSONA_PRAISE,
        semantic_confidence=0.9,
        candidates=[
            SemanticClassificationCandidateStruct(
                comment_id="comment-1",
                text="主播今天状态太好了",
                semantic_type=SemanticType.PERSONA_PRAISE,
                score=1.2,
                confidence=0.9,
            ),
            SemanticClassificationCandidateStruct(
                comment_id="comment-2",
                text="这波操作笑死我了",
                semantic_type=SemanticType.PLAYFUL_JOKE,
                score=1,
                confidence=0.8,
            ),
        ],
    )


class TestWorkflowInterestHandler:
    async def test_records_validated_interest_result_in_stage(self) -> None:
        agent = ScriptedInterestAgent(
            [
                {
                    "interest_score": 0.95,
                    "interest_type": "persona_praise",
                    "selected_comment_id": "comment-1",
                    "reason": "The comment is specific and easy for the host to respond to.",
                }
            ]
        )
        factory = StaticInterestAgentFactory(agent)
        handler = WorkflowInterestHandler(
            factory,
            InterestAgentExecutionConfigStruct(provider_name="fake", model_id="fake-model"),
        )
        evaluated_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)

        evaluated = await handler.evaluate_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _interest_input(),
            evaluated_at=evaluated_at,
        )

        assert evaluated.semantic_type is SemanticType.PERSONA_PRAISE
        assert evaluated.attempt_count == 1
        assert factory.inputs == [_interest_input()]
        assert evaluated.interest_stage is not None
        assert evaluated.interest_stage.stage_name is WorkflowStageName.INTEREST_STAGE
        assert evaluated.interest_stage.output["fallback_used"] is False
        assert evaluated.interest_stage.output["agent_result"]["selected_comment_id"] == "comment-1"
        assert evaluated.interest_stage.attempts[0].input["provider_name"] == "fake"
        assert evaluated.interest_stage.attempts[0].output["raw_output"]["interest_score"] == 0.95
        assert evaluated.interest_stage.error is None

    async def test_retries_after_validation_error_with_correction_context(self) -> None:
        agent = ScriptedInterestAgent(
            [
                {
                    "interest_score": 0.8,
                    "interest_type": "persona_praise",
                    "selected_comment_id": "unknown-comment",
                    "reason": "Invalid candidate selection.",
                },
                {
                    "interest_score": 0.9,
                    "interest_type": "playful_joke",
                    "selected_comment_id": "comment-2",
                    "reason": "The joke can quickly engage the host.",
                },
            ]
        )
        handler = WorkflowInterestHandler(StaticInterestAgentFactory(agent))

        evaluated = await handler.evaluate_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _interest_input(),
            evaluated_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert evaluated.semantic_type is SemanticType.PLAYFUL_JOKE
        assert evaluated.attempt_count == 2
        assert evaluated.interest_stage is not None
        assert len(evaluated.interest_stage.attempts) == 2
        assert evaluated.interest_stage.attempts[0].error is not None
        assert evaluated.interest_stage.attempts[0].error["type"] == "ValueError"
        assert agent.correction_contexts[1] is not None
        raw_output = agent.correction_contexts[1]["raw_output"]
        assert isinstance(raw_output, dict)
        assert raw_output["selected_comment_id"] == "unknown-comment"
        validation_error = agent.correction_contexts[1]["validation_error"]
        assert isinstance(validation_error, dict)
        assert validation_error["type"] == "ValueError"

    async def test_uses_semantic_candidate_fallback_when_attempts_are_exhausted(self) -> None:
        agent = ScriptedInterestAgent(
            [
                {"interest_score": -1, "interest_type": "persona_praise", "reason": "Missing selected comment."},
                {"interest_score": -1, "interest_type": "persona_praise", "reason": "Missing selected comment."},
                {"interest_score": -1, "interest_type": "persona_praise", "reason": "Missing selected comment."},
            ]
        )
        handler = WorkflowInterestHandler(StaticInterestAgentFactory(agent))

        evaluated = await handler.evaluate_workflow_run(
            WorkflowRunStruct(room_id="room-a"),
            _interest_input(),
            evaluated_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
        )

        assert evaluated.semantic_type is SemanticType.PERSONA_PRAISE
        assert evaluated.attempt_count == 3
        assert evaluated.interest_stage is not None
        assert evaluated.interest_stage.output["fallback_used"] is True
        assert evaluated.interest_stage.output["agent_result"]["selected_comment_id"] == "comment-1"
        assert len(evaluated.interest_stage.attempts) == 3
        assert evaluated.interest_stage.error == {
            "type": "InterestAgentAttemptsExhausted",
            "message": "Interest agent attempts were exhausted; semantic classification fallback was used.",
        }

    async def test_rejects_interest_input_from_a_different_room(self) -> None:
        agent = ScriptedInterestAgent([])
        handler = WorkflowInterestHandler(StaticInterestAgentFactory(agent))

        with pytest.raises(WorkflowInterestInputRoomMismatchError) as exc_info:
            await handler.evaluate_workflow_run(
                WorkflowRunStruct(room_id="room-a"),
                _interest_input(room_id="room-b"),
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
    """Minimal AssistantAgent behavior required by AutoGenInterestAgent tests."""

    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = iter(outcomes)
        self.model_context = _FakeModelContext()
        self.tasks: list[TextMessage] = []

    async def run(self, *, task: TextMessage) -> TaskResult:
        """Record the user message and return or raise the scripted outcome."""

        self.tasks.append(task)
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            self.model_context.messages.append(AssistantMessage(content="{invalid json", source="interest_agent"))
            raise outcome

        structured_content = InterestAgentOutput.model_validate(outcome)
        return TaskResult(
            messages=[
                StructuredMessage[InterestAgentOutput](
                    content=structured_content,
                    source="interest_agent",
                )
            ]
        )


class TestAutoGenInterestAgent:
    async def test_sends_only_latest_correction_as_a_user_message(self) -> None:
        fake_agent = _FakeAssistantAgent(
            [
                {
                    "interest_score": 0.9,
                    "interest_type": "persona_praise",
                    "selected_comment_id": "comment-1",
                    "reason": "Valid result.",
                }
            ]
        )
        agent = AutoGenInterestAgent(cast("AssistantAgent", fake_agent))
        correction_context: dict[str, Any] = {
            "raw_output": {"selected_comment_id": "unknown-comment"},
            "validation_error": {"type": "ValueError", "message": "Unknown candidate."},
        }

        await agent.generate(correction_context)

        assert fake_agent.tasks[0].source == "user"
        assert "interest_input" not in fake_agent.tasks[0].content
        assert "unknown-comment" in fake_agent.tasks[0].content
        assert "Unknown candidate." in fake_agent.tasks[0].content

    async def test_recovers_raw_output_after_autogen_structured_validation_failure(self) -> None:
        validation_error = _structured_validation_error()
        fake_agent = _FakeAssistantAgent([validation_error])
        agent = AutoGenInterestAgent(cast("AssistantAgent", fake_agent))

        with pytest.raises(Exception) as exc_info:
            await agent.generate()

        assert exc_info.value.__class__.__name__ == "InterestAgentInvocationError"
        assert getattr(exc_info.value, "raw_output") == "{invalid json"


def _structured_validation_error() -> ValidationError:
    try:
        InterestAgentOutput.model_validate({"interest_score": -1, "interest_type": "persona_praise", "reason": "bad"})
    except ValidationError as exc:
        return exc

    msg = "Expected invalid InterestAgent output to produce a ValidationError."
    raise AssertionError(msg)
