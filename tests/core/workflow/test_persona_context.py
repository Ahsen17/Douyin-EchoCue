from datetime import UTC, datetime
from uuid import UUID

import pytest
from litestar.status_codes import HTTP_404_NOT_FOUND

from echocue.core.workflow import (
    StaticWorkflowPersonaContextResolver,
    WorkflowPersonaContextHandler,
    WorkflowPersonaContextNotFoundError,
    WorkflowPersonaContextStruct,
    WorkflowRunStruct,
    WorkflowStageName,
)


class TestWorkflowPersonaContextHandler:
    async def test_resolves_current_published_persona_context_for_room(self) -> None:
        published_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        persona_context = WorkflowPersonaContextStruct(
            room_id="room-a",
            persona_id=UUID("00000000-0000-7000-8000-000000000001"),
            persona_version=3,
            published_at=published_at,
            persona_name="Echo host",
            persona_summary="Warm and concise.",
        )
        handler = WorkflowPersonaContextHandler(
            StaticWorkflowPersonaContextResolver({"room-a": persona_context})
        )

        result = await handler.resolve_current_published("room-a")

        assert result.persona_id == UUID("00000000-0000-7000-8000-000000000001")
        assert result.persona_version == 3
        assert result.published_at == published_at
        assert result.persona_name == "Echo host"
        assert result.persona_summary == "Warm and concise."

    async def test_raises_domain_error_when_published_persona_context_is_missing(self) -> None:
        handler = WorkflowPersonaContextHandler(StaticWorkflowPersonaContextResolver({}))

        with pytest.raises(WorkflowPersonaContextNotFoundError) as exc_info:
            await handler.resolve_current_published("room-missing")

        assert exc_info.value.status_code == HTTP_404_NOT_FOUND
        assert "room-missing" in exc_info.value.message

    def test_freezes_persona_identity_version_and_stage_output(self) -> None:
        frozen_at = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)
        persona_context = WorkflowPersonaContextStruct(
            room_id="room-a",
            persona_id=UUID("00000000-0000-7000-8000-000000000001"),
            persona_version=3,
            published_at=frozen_at,
            persona_name="Echo host",
            persona_summary="Warm and concise.",
        )
        workflow_run = WorkflowRunStruct(room_id="room-a")
        handler = WorkflowPersonaContextHandler(
            StaticWorkflowPersonaContextResolver({"room-a": persona_context})
        )

        frozen = handler.freeze_workflow_run(workflow_run, persona_context, frozen_at=frozen_at)

        assert frozen is not workflow_run
        assert workflow_run.persona_id is None
        assert workflow_run.persona_version is None
        assert frozen.persona_id == UUID("00000000-0000-7000-8000-000000000001")
        assert frozen.persona_version == 3
        assert frozen.persona_context_stage is not None
        assert frozen.persona_context_stage.stage_name is WorkflowStageName.PERSONA_CONTEXT_STAGE
        assert frozen.persona_context_stage.started_at == frozen_at
        assert frozen.persona_context_stage.completed_at == frozen_at
        assert frozen.persona_context_stage.input == {"room_id": "room-a"}
        assert frozen.persona_context_stage.output["persona_id"] == str(
            UUID("00000000-0000-7000-8000-000000000001")
        )
        assert frozen.persona_context_stage.output["persona_version"] == 3
