"""Merge-review agent execution and structured retry handling for workflow runs."""

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
from echocue.core.workflow.enum import WorkflowPushAction, WorkflowStageName, WorkflowStatus
from echocue.core.workflow.exception import WorkflowReviewInputRoomMismatchError
from echocue.core.workflow.schema import (
    ReviewAgentExecutionConfigStruct,
    ReviewAgentInputStruct,
    ReviewAgentOutput,
    WorkflowRunStruct,
    WorkflowStageAttemptStruct,
    WorkflowStageEnvelopeStruct,
)
from echocue.shared import ChatAgentLoader

__all__ = (
    "AutoGenReviewAgent",
    "AutoGenReviewAgentFactory",
    "WorkflowReviewHandler",
)


_REVIEW_AGENT_TEMPLATE_NAME = "merge_review_agent"
_INITIAL_TASK = "Review the supplied reply, safety evidence, and persona context, then return the final decision."
_RETRY_INSTRUCTION = "Correct the previous output and return only a result that conforms to the requested schema."


class ReviewAgentInvocationError(WorkflowAgentInvocationError):
    """Structured output parsing failure with the model's raw response."""


class AutoGenReviewAgent:
    """Merge-review agent adapter backed by an AutoGen AssistantAgent."""

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
            raise ReviewAgentInvocationError(raw_output, exc) from exc

        if not result.messages:
            raise RuntimeError("ReviewAgent returned no messages.")

        match result.messages[-1]:
            case StructuredMessage(content=content):
                return content
            case TextMessage(content=content):
                return content
            case _:
                raise RuntimeError("ReviewAgent returned an unsupported message type.")

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


class AutoGenReviewAgentFactory:
    """Create merge-review agent adapters from the configured Jinja template."""

    def __init__(
        self,
        agent_loader: ChatAgentLoader[ReviewAgentInputStruct],
        model_client: ChatCompletionClient,
    ) -> None:
        self._agent_loader = agent_loader
        self._model_client = model_client

    def create(self, data: ReviewAgentInputStruct) -> AutoGenReviewAgent:
        """Create a structured-output merge-review agent for the workflow input."""

        agent = self._agent_loader.load_from_template(
            _REVIEW_AGENT_TEMPLATE_NAME,
            self._model_client,
            output_content_type=ReviewAgentOutput,
            review_input=serialize_review_agent_input(data),
            output_schema=ReviewAgentOutput.model_json_schema(),
        )

        return AutoGenReviewAgent(agent)


class WorkflowReviewHandler:
    """Run merge-review attempts and record the final review stage."""

    def __init__(
        self,
        agent_factory: AutoGenReviewAgentFactory,
        config: ReviewAgentExecutionConfigStruct | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._config = config or ReviewAgentExecutionConfigStruct()
        self._attempt_runner = WorkflowAgentAttemptRunner[ReviewAgentOutput](
            stage_name=WorkflowStageName.REVIEW_STAGE,
            provider_name=self._config.provider_name,
            model_id=self._config.model_id,
            invocation_failure_message="Review agent invocation failed.",
        )

    async def review_workflow_run(
        self,
        workflow_run: WorkflowRunStruct,
        data: ReviewAgentInputStruct,
        *,
        reviewed_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        """Review the generated reply and record final push or skip decision."""

        if workflow_run.room_id != data.room_id:
            raise WorkflowReviewInputRoomMismatchError(workflow_run.room_id, data.room_id)

        if data.persona_context.room_id != workflow_run.room_id:
            raise WorkflowReviewInputRoomMismatchError(workflow_run.room_id, data.persona_context.room_id)

        started_at = self._get_stage_started_at(workflow_run, reviewed_at)
        agent = self._agent_factory.create(data)
        result, attempts = await self._attempt_runner.run(
            agent.generate,
            lambda raw_output: self._validate_output(raw_output, data),
            max_attempts=self._config.max_attempts,
            occurred_at=reviewed_at,
        )
        if result is not None:
            return self._record_result(
                workflow_run,
                data,
                result,
                attempts=attempts,
                started_at=started_at,
                completed_at=reviewed_at or datetime.now(UTC),
            )

        return self._record_attempts_exhausted(
            workflow_run,
            data,
            attempts=attempts,
            started_at=started_at,
            completed_at=reviewed_at or datetime.now(UTC),
        )

    def _validate_output(self, raw_output: Any, data: ReviewAgentInputStruct) -> ReviewAgentOutput:
        if isinstance(raw_output, str):
            result = ReviewAgentOutput.model_validate_json(raw_output)
        elif isinstance(raw_output, BaseModel):
            result = ReviewAgentOutput.model_validate(raw_output.model_dump())
        else:
            result = ReviewAgentOutput.model_validate(raw_output)

        if result.push_action is WorkflowPushAction.SKIP and not result.skip_reason:
            msg = "ReviewAgent skip decision must include skip_reason."
            raise ValueError(msg)

        if result.push_action is WorkflowPushAction.PUSH and result.skip_reason is not None:
            msg = "ReviewAgent push decision must not include skip_reason."
            raise ValueError(msg)

        missing_risks = set(data.safety_scan.risk_categories) - set(result.risk_categories)
        if missing_risks:
            msg = f"ReviewAgent output omitted safety scan risk categories: {sorted(missing_risks)}."
            raise ValueError(msg)

        return result

    def _record_result(
        self,
        workflow_run: WorkflowRunStruct,
        data: ReviewAgentInputStruct,
        result: ReviewAgentOutput,
        *,
        attempts: list[WorkflowStageAttemptStruct],
        started_at: datetime,
        completed_at: datetime,
    ) -> WorkflowRunStruct:
        reviewed = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        result_data = result.model_dump(mode="json")
        reviewed.workflow_status = WorkflowStatus.COMPLETED
        reviewed.push_action = result.push_action
        reviewed.review_category = result.review_category
        reviewed.review_note = result.review_note
        reviewed.risk_categories = list(result.risk_categories)
        reviewed.skip_reason = result.skip_reason
        reviewed.attempt_count += len(attempts)
        reviewed.review_stage = self._build_stage(
            workflow_run,
            data,
            attempts=attempts,
            started_at=started_at,
            completed_at=completed_at,
            output={
                "safety_scan": data.safety_scan.to_dict(),
                "agent_name": self._config.agent_name,
                "agent_result": result_data,
                "fallback_used": False,
            },
        )
        return reviewed

    def _record_attempts_exhausted(
        self,
        workflow_run: WorkflowRunStruct,
        data: ReviewAgentInputStruct,
        *,
        attempts: list[WorkflowStageAttemptStruct],
        started_at: datetime,
        completed_at: datetime,
    ) -> WorkflowRunStruct:
        reviewed = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        reviewed.workflow_status = WorkflowStatus.ABORTED
        reviewed.push_action = WorkflowPushAction.SKIP
        reviewed.review_category = "review_agent_unavailable"
        reviewed.review_note = "Review agent attempts were exhausted; workflow run was aborted."
        reviewed.risk_categories = list(data.safety_scan.risk_categories)
        reviewed.skip_reason = "review_agent_attempts_exhausted"
        reviewed.attempt_count += len(attempts)
        reviewed.review_stage = self._build_stage(
            workflow_run,
            data,
            attempts=attempts,
            started_at=started_at,
            completed_at=completed_at,
            output={
                "safety_scan": data.safety_scan.to_dict(),
                "agent_name": self._config.agent_name,
                "fallback_used": False,
            },
            error={
                "type": "ReviewAgentAttemptsExhausted",
                "message": "Review agent attempts were exhausted; workflow run was aborted.",
            },
        )
        return reviewed

    def _build_stage(
        self,
        workflow_run: WorkflowRunStruct,
        data: ReviewAgentInputStruct,
        *,
        attempts: list[WorkflowStageAttemptStruct],
        started_at: datetime,
        completed_at: datetime,
        output: dict[str, Any],
        error: dict[str, str] | None = None,
    ) -> WorkflowStageEnvelopeStruct:
        existing_input = workflow_run.review_stage.input if workflow_run.review_stage is not None else {}
        return WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REVIEW_STAGE,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=max(round((completed_at - started_at).total_seconds() * 1000), 0),
            input={
                **existing_input,
            "review_input": serialize_review_agent_input(data),
            },
            output=output,
            error=error,
            attempts=attempts,
        )

    def _get_stage_started_at(self, workflow_run: WorkflowRunStruct, reviewed_at: datetime | None) -> datetime:
        if workflow_run.review_stage is not None:
            return workflow_run.review_stage.started_at

        return reviewed_at or datetime.now(UTC)



def serialize_review_agent_input(data: ReviewAgentInputStruct) -> dict[str, Any]:
    """Serialize review input into a JSON-compatible payload for templates and audit logs."""

    return {
        "room_id": data.room_id,
        "persona_context": data.persona_context.to_dict(),
        "selected_comment": data.selected_comment.to_dict(),
        "reply": data.reply.model_dump(mode="json"),
        "semantic_type": data.semantic_type.value,
        "safety_scan": data.safety_scan.to_dict(),
        "recent_push_records": data.recent_push_records,
    }
