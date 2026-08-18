"""Workflow domain handlers."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from .enum import WorkflowStageName
from .exception import (
    WorkflowPersonaContextNotFoundError,
    WorkflowPersonaContextRoomMismatchError,
)
from .schema import (
    WorkflowPersonaContextStruct,
    WorkflowRunStruct,
    WorkflowStageEnvelopeStruct,
)

__all__ = (
    "StaticWorkflowPersonaContextResolver",
    "WorkflowPersonaContextHandler",
    "WorkflowPersonaContextResolver",
)


class WorkflowPersonaContextResolver(Protocol):
    """Resolve the current published persona context for a room."""

    async def resolve_current_published(self, room_id: str) -> WorkflowPersonaContextStruct | None:
        """Return the current published persona context for a room."""


class StaticWorkflowPersonaContextResolver:
    """Deterministic in-memory persona context resolver for local adapters and tests."""

    def __init__(self, contexts: Mapping[str, WorkflowPersonaContextStruct]) -> None:
        self._contexts = dict(contexts)

    async def resolve_current_published(self, room_id: str) -> WorkflowPersonaContextStruct | None:
        """Return the configured persona context for a room."""

        return self._contexts.get(room_id)


class WorkflowPersonaContextHandler:
    """Resolve and freeze persona context into a workflow run."""

    def __init__(self, resolver: WorkflowPersonaContextResolver) -> None:
        self._resolver = resolver

    async def resolve_current_published(self, room_id: str) -> WorkflowPersonaContextStruct:
        """Resolve the current published persona context or raise a business error."""

        persona_context = await self._resolver.resolve_current_published(room_id)
        if persona_context is None:
            raise WorkflowPersonaContextNotFoundError(room_id)

        return persona_context

    def freeze_workflow_run(
        self,
        workflow_run: WorkflowRunStruct,
        persona_context: WorkflowPersonaContextStruct,
        *,
        frozen_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        """Freeze persona identity and version into a workflow run snapshot."""

        if workflow_run.room_id != persona_context.room_id:
            raise WorkflowPersonaContextRoomMismatchError(workflow_run.room_id, persona_context.room_id)

        frozen = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        resolved_at = frozen_at or persona_context.published_at or datetime.now(UTC)

        frozen.persona_id = persona_context.persona_id
        frozen.persona_version = persona_context.persona_version
        frozen.persona_context_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.PERSONA_CONTEXT_STAGE,
            started_at=resolved_at,
            completed_at=resolved_at,
            latency_ms=0,
            input={"room_id": persona_context.room_id},
            output=persona_context.to_dict(),
        )

        return frozen
