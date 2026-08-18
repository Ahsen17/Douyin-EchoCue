"""Workflow domain handlers."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from echocue.core.lexicon import (
    SemanticClassificationClient,
    SemanticClassificationCommentStruct,
    SemanticClassificationRequestStruct,
    SemanticClassificationResultStruct,
)
from echocue.core.live import CommentWindowWorkflowInputStruct

from .enum import WorkflowStageName
from .exception import (
    WorkflowPersonaContextNotFoundError,
    WorkflowPersonaContextRoomMismatchError,
    WorkflowSemanticClassificationRoomMismatchError,
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
    "WorkflowSemanticClassificationHandler",
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


class WorkflowSemanticClassificationHandler:
    """Classify workflow comment-window input and record the semantic stage."""

    def __init__(self, classification_client: SemanticClassificationClient) -> None:
        self._classification_client = classification_client

    async def classify_workflow_run(
        self,
        workflow_run: WorkflowRunStruct,
        comment_window: CommentWindowWorkflowInputStruct,
        *,
        classified_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        """Classify a comment window and freeze its result into a workflow run."""

        if workflow_run.room_id != comment_window.room_id:
            raise WorkflowSemanticClassificationRoomMismatchError(workflow_run.room_id, comment_window.room_id)

        request = SemanticClassificationRequestStruct(
            room_id=comment_window.room_id,
            text_batch=list(comment_window.text_batch),
            top_n=comment_window.top_n,
            comment_batch=[
                SemanticClassificationCommentStruct(comment_id=comment.comment_id, text=comment.content)
                for comment in comment_window.comments
            ],
        )
        started_at = classified_at or datetime.now(UTC)
        result, error = await self._classify(request)
        completed_at = classified_at or datetime.now(UTC)
        latency_ms = max(round((completed_at - started_at).total_seconds() * 1000), 0)

        classified = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        classified.semantic_type = result.semantic_type
        classified.semantic_classification_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.SEMANTIC_CLASSIFICATION_STAGE,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=latency_ms,
            input=request.to_dict(),
            output=result.to_dict(),
            error=error,
        )

        return classified

    async def _classify(
        self,
        request: SemanticClassificationRequestStruct,
    ) -> tuple[SemanticClassificationResultStruct, dict[str, str] | None]:
        try:
            return await self._classification_client.classify(request), None
        # The injected client is an external service boundary; any provider failure becomes an auditable fallback.
        except Exception as exc:  # noqa: BLE001
            return (
                SemanticClassificationResultStruct.other(top_n=request.top_n),
                {
                    "type": type(exc).__name__,
                    "message": "Semantic classification service failed.",
                },
            )
