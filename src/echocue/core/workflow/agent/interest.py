"""InterestAgent execution and structured retry handling for workflow runs."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import StructuredMessage, TextMessage
from autogen_core.models import AssistantMessage, ChatCompletionClient, LLMMessage
from pydantic import BaseModel, ValidationError

from echocue.core.lexicon import SemanticType
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


class InterestAgentInvocationError(Exception):
    """Structured output parsing failure with the model's raw response."""

    def __init__(self, raw_output: object | None, cause: ValidationError) -> None:
        """Initialize the parsing failure details."""

        self.raw_output = raw_output
        self.cause = cause
        super().__init__(str(cause))


class AutoGenInterestAgent:
    """InterestAgent adapter backed by an AutoGen AssistantAgent."""

    def __init__(self, agent: AssistantAgent) -> None:
        self._agent = agent

    async def generate(self, correction_context: dict[str, object] | None = None) -> object:
        """Run the agent with either the initial task or the latest correction request."""

        messages_before_run = await self._agent.model_context.get_messages()
        task = self._build_task(correction_context)

        try:
            result = await self._agent.run(task=TextMessage(content=task, source="user"))
        except ValidationError as exc:
            messages_after_failure = await self._agent.model_context.get_messages()
            raw_output = _find_latest_assistant_output(messages_after_failure[len(messages_before_run) :])
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

    def _build_task(self, correction_context: dict[str, object] | None) -> str:
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
        attempts: list[WorkflowStageAttemptStruct] = []
        correction_context: dict[str, object] | None = None

        for attempt_index in range(1, max(self._config.max_attempts, 1) + 1):
            result, attempt = await self._run_attempt(
                agent,
                data,
                attempt_index=attempt_index,
                correction_context=correction_context,
                evaluated_at=evaluated_at,
            )
            attempts.append(attempt)
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

            correction_context = {
                "raw_output": attempt.output.get("raw_output"),
                "validation_error": attempt.error,
            }

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

    async def _run_attempt(
        self,
        agent: AutoGenInterestAgent,
        data: InterestAgentInputStruct,
        *,
        attempt_index: int,
        correction_context: dict[str, object] | None,
        evaluated_at: datetime | None,
    ) -> tuple[InterestAgentOutput | None, WorkflowStageAttemptStruct]:
        started_at = evaluated_at or datetime.now(UTC)
        raw_output: object | None = None

        try:
            raw_output = await agent.generate(correction_context)
            result = self._validate_output(raw_output, data)
        except InterestAgentInvocationError as exc:
            completed_at = evaluated_at or datetime.now(UTC)
            return None, self._build_attempt(
                attempt_index,
                started_at=started_at,
                completed_at=completed_at,
                correction_context=correction_context,
                raw_output=exc.raw_output,
                error={
                    "type": type(exc.cause).__name__,
                    "message": str(exc.cause),
                },
            )
        except (TypeError, ValidationError, ValueError) as exc:
            completed_at = evaluated_at or datetime.now(UTC)
            return None, self._build_attempt(
                attempt_index,
                started_at=started_at,
                completed_at=completed_at,
                correction_context=correction_context,
                raw_output=raw_output,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
        # The agent is an external model boundary; failures are recorded and retried before fallback.
        except Exception as exc:  # noqa: BLE001
            completed_at = evaluated_at or datetime.now(UTC)
            return None, self._build_attempt(
                attempt_index,
                started_at=started_at,
                completed_at=completed_at,
                correction_context=correction_context,
                raw_output=raw_output,
                error={
                    "type": type(exc).__name__,
                    "message": "Interest agent invocation failed.",
                },
            )

        completed_at = evaluated_at or datetime.now(UTC)
        return result, self._build_attempt(
            attempt_index,
            started_at=started_at,
            completed_at=completed_at,
            correction_context=correction_context,
            raw_output=raw_output,
        )

    def _validate_output(self, raw_output: object, data: InterestAgentInputStruct) -> InterestAgentOutput:
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

    def _build_attempt(
        self,
        attempt_index: int,
        *,
        started_at: datetime,
        completed_at: datetime,
        correction_context: dict[str, object] | None,
        raw_output: object | None,
        error: dict[str, str] | None = None,
    ) -> WorkflowStageAttemptStruct:
        return WorkflowStageAttemptStruct(
            stage_name=WorkflowStageName.INTEREST_STAGE,
            attempt_index=attempt_index,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=max(round((completed_at - started_at).total_seconds() * 1000), 0),
            input={
                "provider_name": self._config.provider_name,
                "model_id": self._config.model_id,
                "correction_context": correction_context,
            },
            output={"raw_output": _serialize_raw_output(raw_output)},
            error=error,
        )

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


def _find_latest_assistant_output(messages: Sequence[LLMMessage]) -> object | None:
    for message in reversed(messages):
        if isinstance(message, AssistantMessage):
            return message.content

    return None


def _serialize_raw_output(raw_output: object | None) -> object:
    if isinstance(raw_output, BaseModel):
        return raw_output.model_dump(mode="json")

    return json.loads(json.dumps(raw_output, default=str, ensure_ascii=True))
