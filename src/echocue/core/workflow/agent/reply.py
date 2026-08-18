"""ReplyAgent execution and structured retry handling for workflow runs."""

import json
from datetime import UTC, datetime
from typing import Any

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import StructuredMessage, TextMessage
from autogen_core.models import ChatCompletionClient
from pydantic import ValidationError

from echocue.base import BaseModel
from echocue.core.workflow.agent.handler import (
    WorkflowAgentAttemptRunner,
    WorkflowAgentInvocationError,
    find_latest_assistant_output,
)
from echocue.core.workflow.enum import WorkflowStageName, WorkflowStatus
from echocue.core.workflow.exception import WorkflowReplyInputRoomMismatchError
from echocue.core.workflow.schema import (
    ReplyAgentExecutionConfigStruct,
    ReplyAgentInputStruct,
    ReplyAgentOutput,
    WorkflowRunStruct,
    WorkflowStageAttemptStruct,
    WorkflowStageEnvelopeStruct,
)
from echocue.shared import ChatAgentLoader

__all__ = (
    "AutoGenReplyAgent",
    "AutoGenReplyAgentFactory",
    "WorkflowReplyHandler",
)


_REPLY_AGENT_TEMPLATE_NAME = "reply_agent"
_INITIAL_TASK = "Generate the requested livestream reply and return the requested structured result."
_RETRY_INSTRUCTION = "Correct the previous output and return only a result that conforms to the requested schema."


class ReplyAgentInvocationError(WorkflowAgentInvocationError):
    """Structured output parsing failure with the model's raw response."""


class AutoGenReplyAgent:
    """ReplyAgent adapter backed by an AutoGen AssistantAgent."""

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
            raise ReplyAgentInvocationError(raw_output, exc) from exc

        if not result.messages:
            raise RuntimeError("ReplyAgent returned no messages.")

        match result.messages[-1]:
            case StructuredMessage(content=content):
                return content
            case TextMessage(content=content):
                return content
            case _:
                raise RuntimeError("ReplyAgent returned an unsupported message type.")

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


class AutoGenReplyAgentFactory:
    """Create ReplyAgent adapters from the configured Jinja template."""

    def __init__(
        self,
        agent_loader: ChatAgentLoader[ReplyAgentInputStruct],
        model_client: ChatCompletionClient,
    ) -> None:
        self._agent_loader = agent_loader
        self._model_client = model_client

    def create(self, data: ReplyAgentInputStruct) -> AutoGenReplyAgent:
        """Create a structured-output ReplyAgent for the workflow input."""

        agent = self._agent_loader.load_from_template(
            _REPLY_AGENT_TEMPLATE_NAME,
            self._model_client,
            output_content_type=ReplyAgentOutput,
            reply_input=data,
            output_schema=ReplyAgentOutput.model_json_schema(),
        )

        return AutoGenReplyAgent(agent)


class WorkflowReplyHandler:
    """Run ReplyAgent attempts and record an auditable reply stage."""

    def __init__(
        self,
        agent_factory: AutoGenReplyAgentFactory,
        config: ReplyAgentExecutionConfigStruct | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._config = config or ReplyAgentExecutionConfigStruct()
        self._attempt_runner = WorkflowAgentAttemptRunner[ReplyAgentOutput](
            stage_name=WorkflowStageName.REPLY_STAGE,
            provider_name=self._config.provider_name,
            model_id=self._config.model_id,
            invocation_failure_message="Reply agent invocation failed.",
        )

    async def generate_workflow_run(
        self,
        workflow_run: WorkflowRunStruct,
        data: ReplyAgentInputStruct,
        *,
        generated_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        """Generate a reply and record attempts in the workflow run."""

        if workflow_run.room_id != data.room_id:
            raise WorkflowReplyInputRoomMismatchError(workflow_run.room_id, data.room_id)

        if data.persona_context.room_id != workflow_run.room_id:
            raise WorkflowReplyInputRoomMismatchError(workflow_run.room_id, data.persona_context.room_id)

        started_at = generated_at or datetime.now(UTC)
        agent = self._agent_factory.create(data)
        result, attempts = await self._attempt_runner.run(
            agent.generate,
            self._validate_output,
            max_attempts=self._config.max_attempts,
            occurred_at=generated_at,
        )
        if result is not None:
            return self._record_result(
                workflow_run,
                data,
                result,
                attempts=attempts,
                started_at=started_at,
                completed_at=generated_at or datetime.now(UTC),
            )

        return self._record_attempts_exhausted(
            workflow_run,
            data,
            attempts=attempts,
            started_at=started_at,
            completed_at=generated_at or datetime.now(UTC),
        )

    def _validate_output(self, raw_output: Any) -> ReplyAgentOutput:
        if isinstance(raw_output, str):
            return ReplyAgentOutput.model_validate_json(raw_output)
        if isinstance(raw_output, BaseModel):
            return ReplyAgentOutput.model_validate(raw_output.model_dump())
        return ReplyAgentOutput.model_validate(raw_output)

    def _record_result(
        self,
        workflow_run: WorkflowRunStruct,
        data: ReplyAgentInputStruct,
        result: ReplyAgentOutput,
        *,
        attempts: list[WorkflowStageAttemptStruct],
        started_at: datetime,
        completed_at: datetime,
    ) -> WorkflowRunStruct:
        evaluated = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        evaluated.attempt_count += len(attempts)
        evaluated.reply_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REPLY_STAGE,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=max(round((completed_at - started_at).total_seconds() * 1000), 0),
            input=data.to_dict(),
            output={
                "agent_name": self._config.agent_name,
                "agent_result": result.model_dump(mode="json"),
                "fallback_used": False,
            },
            attempts=attempts,
        )
        return evaluated

    def _record_attempts_exhausted(
        self,
        workflow_run: WorkflowRunStruct,
        data: ReplyAgentInputStruct,
        *,
        attempts: list[WorkflowStageAttemptStruct],
        started_at: datetime,
        completed_at: datetime,
    ) -> WorkflowRunStruct:
        evaluated = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        evaluated.workflow_status = WorkflowStatus.ABORTED
        evaluated.attempt_count += len(attempts)
        evaluated.skip_reason = "reply_agent_attempts_exhausted"
        evaluated.reply_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REPLY_STAGE,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=max(round((completed_at - started_at).total_seconds() * 1000), 0),
            input=data.to_dict(),
            output={
                "agent_name": self._config.agent_name,
                "fallback_used": False,
            },
            error={
                "type": "ReplyAgentAttemptsExhausted",
                "message": "Reply agent attempts were exhausted; workflow run was aborted.",
            },
            attempts=attempts,
        )
        return evaluated
