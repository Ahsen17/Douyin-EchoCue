"""Shared workflow agent attempt handling."""

import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime

from autogen_core.models import AssistantMessage, LLMMessage
from pydantic import ValidationError

from echocue.base import BaseModel
from echocue.core.workflow.enum import WorkflowStageName
from echocue.core.workflow.schema import WorkflowStageAttemptStruct
from echocue.shared import ApplicationError

__all__ = (
    "WorkflowAgentAttemptRunner",
    "WorkflowAgentInvocationError",
)


class WorkflowAgentInvocationError(ApplicationError):
    """Structured output parsing failure with the model's raw response."""

    def __init__(self, raw_output: object | None, cause: ValidationError) -> None:
        """Initialize the parsing failure details."""

        self.raw_output = raw_output
        self.cause = cause
        super().__init__(str(cause))


class WorkflowAgentAttemptRunner[OutputT: BaseModel]:
    """Run structured workflow agent attempts and build auditable attempt records."""

    def __init__(
        self,
        *,
        stage_name: WorkflowStageName,
        provider_name: str | None,
        model_id: str | None,
        invocation_failure_message: str,
    ) -> None:
        self._stage_name = stage_name
        self._provider_name = provider_name
        self._model_id = model_id
        self._invocation_failure_message = invocation_failure_message

    async def run(
        self,
        generate: Callable[[dict[str, object] | None], Awaitable[object]],
        validate_output: Callable[[object], OutputT],
        *,
        max_attempts: int,
        occurred_at: datetime | None,
    ) -> tuple[OutputT | None, list[WorkflowStageAttemptStruct]]:
        """Run attempts until a validated result is produced or attempts are exhausted."""

        attempts: list[WorkflowStageAttemptStruct] = []
        correction_context: dict[str, object] | None = None

        for attempt_index in range(1, max(max_attempts, 1) + 1):
            result, attempt = await self._run_attempt(
                generate,
                validate_output,
                attempt_index=attempt_index,
                correction_context=correction_context,
                occurred_at=occurred_at,
            )
            attempts.append(attempt)
            if result is not None:
                return result, attempts

            correction_context = {
                "raw_output": attempt.output.get("raw_output"),
                "validation_error": attempt.error,
            }

        return None, attempts

    async def _run_attempt(
        self,
        generate: Callable[[dict[str, object] | None], Awaitable[object]],
        validate_output: Callable[[object], OutputT],
        *,
        attempt_index: int,
        correction_context: dict[str, object] | None,
        occurred_at: datetime | None,
    ) -> tuple[OutputT | None, WorkflowStageAttemptStruct]:
        started_at = occurred_at or datetime.now(UTC)
        raw_output: object | None = None

        try:
            raw_output = await generate(correction_context)
            result = validate_output(raw_output)
        except WorkflowAgentInvocationError as exc:
            completed_at = occurred_at or datetime.now(UTC)
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
            completed_at = occurred_at or datetime.now(UTC)
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
        # Agent execution is an external model boundary; provider failures are recorded before retry handling.
        except Exception as exc:  # noqa: BLE001
            completed_at = occurred_at or datetime.now(UTC)
            return None, self._build_attempt(
                attempt_index,
                started_at=started_at,
                completed_at=completed_at,
                correction_context=correction_context,
                raw_output=raw_output,
                error={
                    "type": type(exc).__name__,
                    "message": self._invocation_failure_message,
                },
            )

        completed_at = occurred_at or datetime.now(UTC)
        return result, self._build_attempt(
            attempt_index,
            started_at=started_at,
            completed_at=completed_at,
            correction_context=correction_context,
            raw_output=raw_output,
        )

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
            stage_name=self._stage_name,
            attempt_index=attempt_index,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=max(round((completed_at - started_at).total_seconds() * 1000), 0),
            input={
                "provider_name": self._provider_name,
                "model_id": self._model_id,
                "correction_context": correction_context,
            },
            output={"raw_output": serialize_agent_raw_output(raw_output)},
            error=error,
        )


def find_latest_assistant_output(messages: Sequence[LLMMessage]) -> object | None:
    """Return the latest assistant raw content from an AutoGen model context slice."""

    for message in reversed(messages):
        if isinstance(message, AssistantMessage):
            return message.content

    return None


def serialize_agent_raw_output(raw_output: object | None) -> object:
    """Convert arbitrary agent output into a JSON-compatible value for stage attempts."""

    if isinstance(raw_output, BaseModel):
        return raw_output.model_dump(mode="json")

    return json.loads(json.dumps(raw_output, default=str, ensure_ascii=True))
