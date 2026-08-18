"""Workflow domain schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from msgspec import field

from echocue.base import BaseStruct, CamelizedBaseStruct
from echocue.core.lexicon import SemanticType

from .enum import (
    WorkflowPushAction,
    WorkflowStageName,
    WorkflowStatus,
    WorkflowTriggerType,
    ensure_workflow_status_transition,
    is_valid_workflow_status_transition,
)

__all__ = (
    "WorkflowPushAction",
    "WorkflowRunStruct",
    "WorkflowRunVO",
    "WorkflowStageAttemptStruct",
    "WorkflowStageAttemptVO",
    "WorkflowStageEnvelopeStruct",
    "WorkflowStageEnvelopeVO",
    "WorkflowStageName",
    "WorkflowStatus",
    "WorkflowTriggerType",
    "ensure_workflow_status_transition",
    "is_valid_workflow_status_transition",
)


class WorkflowStageAttemptStruct(BaseStruct):
    """Single workflow stage attempt record."""

    stage_name: WorkflowStageName
    attempt_index: int
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None


class WorkflowStageAttemptVO(CamelizedBaseStruct):
    """API-facing workflow stage attempt view object."""

    stage_name: WorkflowStageName
    attempt_index: int
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None

    @classmethod
    def from_struct(cls, data: WorkflowStageAttemptStruct) -> "WorkflowStageAttemptVO":
        """Build a view object from a workflow stage attempt."""

        return cls(**data.to_dict())


class WorkflowStageEnvelopeStruct(BaseStruct):
    """Single workflow stage envelope."""

    stage_name: WorkflowStageName
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    attempts: list[WorkflowStageAttemptStruct] = field(default_factory=list)


class WorkflowStageEnvelopeVO(CamelizedBaseStruct):
    """API-facing workflow stage envelope view object."""

    stage_name: WorkflowStageName
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int | None = None
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    attempts: list[WorkflowStageAttemptVO] = field(default_factory=list)

    @classmethod
    def from_struct(cls, data: WorkflowStageEnvelopeStruct) -> "WorkflowStageEnvelopeVO":
        """Build a view object from a workflow stage envelope."""

        return cls(**data.to_dict())


class WorkflowRunStruct(BaseStruct):
    """Service-layer workflow run snapshot."""

    room_id: str
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    semantic_type: SemanticType = SemanticType.OTHER
    attempt_count: int = 0
    pushed_to_client: bool = False
    delivered_to_client: bool = False
    tenant_id: UUID | None = None
    persona_id: UUID | None = None
    persona_version: int | None = None
    trigger_type: WorkflowTriggerType | None = None
    push_action: WorkflowPushAction | None = None
    review_category: str | None = None
    review_note: str | None = None
    risk_categories: list[str] = field(default_factory=list)
    skip_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latency_ms: int | None = None
    global_rule_version: int | None = None
    organization_rule_version: int | None = None
    room_rule_version: int | None = None
    comment_window_stage: WorkflowStageEnvelopeStruct | None = None
    trigger_evaluation_stage: WorkflowStageEnvelopeStruct | None = None
    persona_context_stage: WorkflowStageEnvelopeStruct | None = None
    semantic_classification_stage: WorkflowStageEnvelopeStruct | None = None
    interest_stage: WorkflowStageEnvelopeStruct | None = None
    reply_stage: WorkflowStageEnvelopeStruct | None = None
    review_stage: WorkflowStageEnvelopeStruct | None = None
    client_delivery_stage: WorkflowStageEnvelopeStruct | None = None


class WorkflowRunVO(CamelizedBaseStruct):
    """API-facing workflow run snapshot."""

    room_id: str
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    semantic_type: SemanticType = SemanticType.OTHER
    attempt_count: int = 0
    pushed_to_client: bool = False
    delivered_to_client: bool = False
    tenant_id: UUID | None = None
    persona_id: UUID | None = None
    persona_version: int | None = None
    trigger_type: WorkflowTriggerType | None = None
    push_action: WorkflowPushAction | None = None
    review_category: str | None = None
    review_note: str | None = None
    risk_categories: list[str] = field(default_factory=list)
    skip_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    latency_ms: int | None = None
    global_rule_version: int | None = None
    organization_rule_version: int | None = None
    room_rule_version: int | None = None
    comment_window_stage: WorkflowStageEnvelopeVO | None = None
    trigger_evaluation_stage: WorkflowStageEnvelopeVO | None = None
    persona_context_stage: WorkflowStageEnvelopeVO | None = None
    semantic_classification_stage: WorkflowStageEnvelopeVO | None = None
    interest_stage: WorkflowStageEnvelopeVO | None = None
    reply_stage: WorkflowStageEnvelopeVO | None = None
    review_stage: WorkflowStageEnvelopeVO | None = None
    client_delivery_stage: WorkflowStageEnvelopeVO | None = None

    @classmethod
    def from_struct(cls, data: WorkflowRunStruct) -> "WorkflowRunVO":
        """Build a view object from a workflow run snapshot."""

        return cls(**data.to_dict())
