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
)

__all__ = (
    "WorkflowPersonaContextStruct",
    "WorkflowPushAction",
    "WorkflowRunStruct",
    "WorkflowRunVO",
    "WorkflowStageAttemptStruct",
    "WorkflowStageAttemptVO",
    "WorkflowStageEnvelopeStruct",
    "WorkflowStageEnvelopeVO",
    "WorkflowStageName",
    "WorkflowStatus",
    "WorkflowTriggerEvaluationStruct",
    "WorkflowTriggerParametersStruct",
    "WorkflowTriggerType",
)


class WorkflowPersonaContextStruct(BaseStruct):
    """Frozen published persona context for a workflow run."""

    room_id: str
    persona_id: UUID
    persona_version: int
    published_at: datetime | None = None
    persona_name: str | None = None
    persona_summary: str | None = None
    source: str = "current_published"


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


class WorkflowTriggerParametersStruct(BaseStruct):
    """Trigger thresholds and cooldown parameters used by workflow evaluation."""

    minimum_comment_count: int = 1
    minimum_window_confidence: float = 0
    high_value_confidence_threshold: float = 0.8
    high_value_score_threshold: float = 1
    cooldown_seconds: int = 30
    high_value_semantic_types: list[SemanticType] = field(
        default_factory=lambda: [
            SemanticType.PERSONA_PRAISE,
            SemanticType.INTERACTIVE_PROMPT,
            SemanticType.PLAYFUL_JOKE,
            SemanticType.ATMOSPHERE_BOOST,
        ]
    )


class WorkflowTriggerEvaluationStruct(BaseStruct):
    """Result of evaluating whether a comment window should start workflow execution."""

    should_trigger: bool
    trigger_type: WorkflowTriggerType | None
    parameters: WorkflowTriggerParametersStruct
    evaluated_at: datetime
    last_pushed_at: datetime | None = None
    blocked_reason: str | None = None
    cooldown_until: datetime | None = None
    selected_candidate_id: str | None = None
    selected_candidate_text: str | None = None
    selected_candidate_semantic_type: SemanticType | None = None
    selected_candidate_score: float | None = None
    selected_candidate_confidence: float | None = None


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
