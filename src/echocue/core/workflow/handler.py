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
    SafetyRuleScanConfigStruct,
    SafetyRuleScanResultStruct,
    SafetyRuleViolationStruct,
    WorkflowPersonaContextStruct,
    WorkflowRunStruct,
    WorkflowStageEnvelopeStruct,
)

__all__ = (
    "StaticWorkflowPersonaContextResolver",
    "WorkflowPersonaContextHandler",
    "WorkflowPersonaContextResolver",
    "WorkflowSafetyRuleScanner",
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


class WorkflowSafetyRuleScanner:
    """Run deterministic safety rule scans and record risk evidence."""

    def __init__(self, config: SafetyRuleScanConfigStruct | None = None) -> None:
        self._config = config or SafetyRuleScanConfigStruct()

    def scan(
        self,
        workflow_run: WorkflowRunStruct,
        evidence: Mapping[str, str],
        *,
        scanned_at: datetime | None = None,
    ) -> tuple[WorkflowRunStruct, SafetyRuleScanResultStruct]:
        """Scan textual evidence and record the programmatic safety evidence stage input."""

        now = scanned_at or datetime.now(UTC)
        result = self._scan_evidence(evidence)

        scanned = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        scanned.global_rule_version = result.global_rule_version
        scanned.organization_rule_version = result.organization_rule_version
        scanned.room_rule_version = result.room_rule_version
        scanned.risk_categories = list(result.risk_categories)
        scanned.review_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REVIEW_STAGE,
            started_at=now,
            completed_at=None,
            input={
                "safety_scan_evidence": dict(evidence),
                "rule_versions": {
                    "global_rule_version": result.global_rule_version,
                    "organization_rule_version": result.organization_rule_version,
                    "room_rule_version": result.room_rule_version,
                },
            },
            output={"safety_scan": result.to_dict()},
        )

        return scanned, result

    def _scan_evidence(self, evidence: Mapping[str, str]) -> SafetyRuleScanResultStruct:
        violations: list[SafetyRuleViolationStruct] = []
        for risk_category, keywords in self._config.prohibited_keywords.items():
            for keyword in keywords:
                violation = self._find_violation(evidence, risk_category, keyword)
                if violation is not None:
                    violations.append(violation)

        risk_categories = sorted({violation.risk_category for violation in violations})
        return SafetyRuleScanResultStruct(
            global_rule_version=self._config.global_rule_version,
            organization_rule_version=self._config.organization_rule_version,
            room_rule_version=self._config.room_rule_version,
            risk_categories=risk_categories,
            violations=violations,
        )

    def _find_violation(
        self,
        evidence: Mapping[str, str],
        risk_category: str,
        keyword: str,
    ) -> SafetyRuleViolationStruct | None:
        normalized_keyword = keyword.casefold()
        for field_name, text in evidence.items():
            if normalized_keyword not in text.casefold():
                continue

            return SafetyRuleViolationStruct(
                risk_category=risk_category,
                rule_id=f"keyword:{risk_category}:{keyword}",
                matched_text=keyword,
                evidence_field=field_name,
            )

        return None
