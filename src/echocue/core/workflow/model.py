"""Workflow persistence models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from advanced_alchemy.types import GUID, DateTimeUTC, JsonB
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from echocue.core.lexicon import SemanticType
from echocue.shared import CustomModel

from .enum import WorkflowStatus
from .schema import WorkflowRunStruct

__all__ = ("WorkflowRuns",)


class WorkflowRuns(CustomModel[WorkflowRunStruct]):
    """Workflow run persistence model."""

    __struct_type__ = WorkflowRunStruct

    tenant_id: Mapped[UUID | None] = mapped_column(GUID(), index=True, nullable=True)
    room_id: Mapped[str] = mapped_column(String(64), index=True)
    persona_id: Mapped[UUID | None] = mapped_column(GUID(), index=True, nullable=True)
    persona_version: Mapped[int | None] = mapped_column(index=True, nullable=True)
    workflow_status: Mapped[str] = mapped_column(
        String(16),
        default=WorkflowStatus.PENDING.value,
        index=True,
    )
    trigger_type: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    semantic_type: Mapped[str] = mapped_column(
        String(32),
        default=SemanticType.OTHER.value,
        index=True,
    )
    push_action: Mapped[str | None] = mapped_column(String(8), index=True, nullable=True)
    review_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    risk_categories: Mapped[list[str]] = mapped_column(JsonB, default=list)
    skip_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    attempt_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTimeUTC(timezone=True), index=True, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTimeUTC(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    pushed_to_client: Mapped[bool] = mapped_column(default=False)
    delivered_to_client: Mapped[bool] = mapped_column(default=False)
    global_rule_version: Mapped[int | None] = mapped_column(nullable=True)
    organization_rule_version: Mapped[int | None] = mapped_column(nullable=True)
    room_rule_version: Mapped[int | None] = mapped_column(nullable=True)
    comment_window_stage: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    trigger_evaluation_stage: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    persona_context_stage: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    semantic_classification_stage: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    interest_stage: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    reply_stage: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    review_stage: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    client_delivery_stage: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
