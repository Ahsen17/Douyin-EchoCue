"""InterestAgent execution and structured retry handling for workflow runs."""

import json
from datetime import UTC, datetime
from typing import Any

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import StructuredMessage, TextMessage
from autogen_core.models import ChatCompletionClient
from pydantic import ValidationError

from echocue.base import BaseModel
from echocue.core.lexicon import SemanticType
from echocue.core.workflow.agent.handler import (
    WorkflowAgentAttemptRunner,
    WorkflowAgentInvocationError,
    find_latest_assistant_output,
)
from echocue.core.workflow.enum import WorkflowStageName
from echocue.core.workflow.exception import WorkflowInterestInputRoomMismatchError
from echocue.core.workflow.schema import (
    InterestAgentExecutionConfigStruct,
    InterestAgentInputStruct,
    InterestAgentOutput,
    WorkflowRunStruct,
    WorkflowStageAttemptStruct,
    WorkflowStageEnvelopeStruct,
)
from echocue.shared import ChatAgentLoader

__all__ = (
    "AutoGenInterestAgent",
    "AutoGenInterestAgentFactory",
    "WorkflowInterestHandler",
)


_INTEREST_AGENT_TEMPLATE_NAME = "interest_agent"
_INITIAL_TASK = "Evaluate the supplied semantic classification input and return the requested structured result."
_RETRY_INSTRUCTION = "Correct the previous output and return only a result that conforms to the requested schema."


class InterestAgentInvocationError(WorkflowAgentInvocationError):
    """Structured output parsing failure with the model's raw response."""


class AutoGenInterestAgent:
    """InterestAgent adapter backed by an AutoGen AssistantAgent."""

    def __init__(self, agent: AssistantAgent) -> None:
        self._agent = agent

    async def generate(self, correction_context: dict[str, Any] | None = None) -> Any:
        """Run the agent with either the initial task or the latest correction request."""

        messages_before_run = await self._agent.model_context.get_messages()
        task = self._build_task(correction_context)

        try:
            result = await self._agent.run(task=TextMessage(content=task, source="user"))
        except ValidationError as exc:
            messages_after_failure = await self._agent.model_context.get_messages()
            raw_output = find_latest_assistant_output(messages_after_failure[len(messages_before_run) :])
            raise InterestAgentInvocationError(raw_output, exc) from exc

        if not result.messages:
            raise RuntimeError("InterestAgent returned no messages.")

        match result.messages[-1]:
            case StructuredMessage(content=content):
                return content
            case TextMessage(content=content):
                return content
            case _:
                raise RuntimeError("InterestAgent returned an unsupported message type.")

    def _build_task(self, correction_context: dict[str, Any] | None) -> str:
        if correction_context is None:
            return _INITIAL_TASK

        return json.dumps(
            {
                "previous_output": correction_context["raw_output"],
                "validation_error": correction_context["validation_error"],
                "instruction": _RETRY_INSTRUCTION,
            },
            ensure_ascii=True,
        )


class AutoGenInterestAgentFactory:
    """Create InterestAgent adapters from the configured Jinja template."""

    def __init__(
        self,
        agent_loader: ChatAgentLoader[InterestAgentInputStruct],
        model_client: ChatCompletionClient,
    ) -> None:
        self._agent_loader = agent_loader
        self._model_client = model_client

    def create(self, data: InterestAgentInputStruct) -> AutoGenInterestAgent:
        """Create a structured-output InterestAgent for the workflow input."""

        agent = self._agent_loader.load_from_template(
            _INTEREST_AGENT_TEMPLATE_NAME,
            self._model_client,
            output_content_type=InterestAgentOutput,
            interest_input=data,
            output_schema=InterestAgentOutput.model_json_schema(),
        )

        return AutoGenInterestAgent(agent)


class WorkflowInterestHandler:
    """Run InterestAgent attempts and record an auditable interest stage."""

    def __init__(
        self,
        agent_factory: AutoGenInterestAgentFactory,
        config: InterestAgentExecutionConfigStruct | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._config = config or InterestAgentExecutionConfigStruct()
        self._attempt_runner = WorkflowAgentAttemptRunner[InterestAgentOutput](
            stage_name=WorkflowStageName.INTEREST_STAGE,
            provider_name=self._config.provider_name,
            model_id=self._config.model_id,
            invocation_failure_message="Interest agent invocation failed.",
        )

    async def evaluate_workflow_run(
        self,
        workflow_run: WorkflowRunStruct,
        data: InterestAgentInputStruct,
        *,
        evaluated_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        """Evaluate candidate interest and record attempts in the workflow run."""

        if workflow_run.room_id != data.room_id:
            raise WorkflowInterestInputRoomMismatchError(workflow_run.room_id, data.room_id)

        started_at = evaluated_at or datetime.now(UTC)
        agent = self._agent_factory.create(data)
        result, attempts = await self._attempt_runner.run(
            agent.generate,
            lambda raw_output: self._validate_output(raw_output, data),
            max_attempts=self._config.max_attempts,
            occurred_at=evaluated_at,
        )
        if result is not None:
            return self._record_result(
                workflow_run,
                data,
                result,
                attempts=attempts,
                started_at=started_at,
                completed_at=evaluated_at or datetime.now(UTC),
                fallback_used=False,
            )

        fallback = self._build_fallback(data)
        return self._record_result(
            workflow_run,
            data,
            fallback,
            attempts=attempts,
            started_at=started_at,
            completed_at=evaluated_at or datetime.now(UTC),
            fallback_used=True,
            error={
                "type": "InterestAgentAttemptsExhausted",
                "message": "Interest agent attempts were exhausted; semantic classification fallback was used.",
            },
        )

    def _validate_output(self, raw_output: Any, data: InterestAgentInputStruct) -> InterestAgentOutput:
        if isinstance(raw_output, str):
            result = InterestAgentOutput.model_validate_json(raw_output)
        elif isinstance(raw_output, BaseModel):
            result = InterestAgentOutput.model_validate(raw_output.model_dump())
        else:
            result = InterestAgentOutput.model_validate(raw_output)

        candidate_ids = {candidate.comment_id for candidate in data.candidates}
        if result.selected_comment_id not in candidate_ids:
            msg = f"InterestAgent selected comment {result.selected_comment_id!r} outside the semantic candidates."
            raise ValueError(msg)

        return result

    def _record_result(
        self,
        workflow_run: WorkflowRunStruct,
        data: InterestAgentInputStruct,
        result: InterestAgentOutput,
        *,
        attempts: list[WorkflowStageAttemptStruct],
        started_at: datetime,
        completed_at: datetime,
        fallback_used: bool,
        error: dict[str, str] | None = None,
    ) -> WorkflowRunStruct:
        evaluated = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        result_data = result.model_dump(mode="json")
        evaluated.semantic_type = result.interest_type
        evaluated.attempt_count += len(attempts)
        evaluated.interest_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.INTEREST_STAGE,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=max(round((completed_at - started_at).total_seconds() * 1000), 0),
            input=data.to_dict(),
            output={
                "agent_name": self._config.agent_name,
                "agent_result": result_data,
                "fallback_used": fallback_used,
            },
            error=error,
            attempts=attempts,
        )

        return evaluated

    def _build_fallback(self, data: InterestAgentInputStruct) -> InterestAgentOutput:
        if not data.candidates:
            return InterestAgentOutput(
                interest_score=0,
                interest_type=SemanticType.OTHER,
                selected_comment_id=None,
                reason="No semantic classification candidates were available for InterestAgent fallback.",
            )

        candidate = max(data.candidates, key=lambda item: (item.confidence, item.score))
        return InterestAgentOutput(
            interest_score=candidate.score,
            interest_type=candidate.semantic_type,
            selected_comment_id=candidate.comment_id,
            reason="Semantic classification fallback selected the highest-confidence candidate.",
        )
