"""Workflow domain handlers."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from echocue.core.lexicon import (
    SemanticClassificationCandidateStruct,
    SemanticClassificationClient,
    SemanticClassificationCommentStruct,
    SemanticClassificationRequestStruct,
    SemanticClassificationResultStruct,
)
from echocue.core.live import CommentWindowWorkflowInputStruct
from echocue.shared import ApplicationError

from .agent import WorkflowInterestHandler, WorkflowReplyHandler, WorkflowReviewHandler
from .enum import WorkflowStageName, WorkflowStatus
from .exception import (
    WorkflowPersonaContextNotFoundError,
    WorkflowPersonaContextRoomMismatchError,
    WorkflowSemanticClassificationRoomMismatchError,
)
from .schema import (
    InterestAgentInputStruct,
    ReplyAgentInputStruct,
    ReplyAgentOutput,
    ReviewAgentInputStruct,
    SafetyRuleScanConfigStruct,
    SafetyRuleScanResultStruct,
    SafetyRuleViolationStruct,
    WorkflowPersonaContextStruct,
    WorkflowRunStruct,
    WorkflowStageEnvelopeStruct,
)
from .service import WorkflowRunService
from .trigger import WorkflowTriggerEvaluator, build_workflow_run_from_comment_window

__all__ = (
    "StaticWorkflowPersonaContextResolver",
    "WorkflowExecutionHandler",
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


class WorkflowExecutionHandler:
    """Run the full workflow from a comment-window input."""

    def __init__(
        self,
        *,
        persona_context_handler: WorkflowPersonaContextHandler,
        semantic_classification_handler: WorkflowSemanticClassificationHandler,
        interest_handler: WorkflowInterestHandler,
        reply_handler: WorkflowReplyHandler,
        review_handler: WorkflowReviewHandler,
        trigger_evaluator: WorkflowTriggerEvaluator | None = None,
        safety_rule_scanner: WorkflowSafetyRuleScanner | None = None,
        workflow_run_service: WorkflowRunService | None = None,
    ) -> None:
        self._trigger_evaluator = trigger_evaluator or WorkflowTriggerEvaluator()
        self._persona_context_handler = persona_context_handler
        self._semantic_classification_handler = semantic_classification_handler
        self._interest_handler = interest_handler
        self._reply_handler = reply_handler
        self._safety_rule_scanner = safety_rule_scanner or WorkflowSafetyRuleScanner(SafetyRuleScanConfigStruct())
        self._review_handler = review_handler
        self._workflow_run_service = workflow_run_service

    async def run_comment_window_workflow(
        self,
        data: CommentWindowWorkflowInputStruct,
        *,
        last_pushed_at: datetime | None = None,
        recent_push_records: Sequence[dict[str, Any]] | None = None,
        evaluated_at: datetime | None = None,
    ) -> WorkflowRunStruct:
        """Run the workflow end to end."""

        workflow_run = build_workflow_run_from_comment_window(
            data,
            self._trigger_evaluator.evaluate(
                data,
                last_pushed_at=last_pushed_at,
                evaluated_at=evaluated_at,
            ),
        )
        if workflow_run.workflow_status is WorkflowStatus.ABORTED:
            return await self._persist(workflow_run)

        stage_at = evaluated_at or data.window_ended_at
        workflow_run.workflow_status = WorkflowStatus.RUNNING
        workflow_run.started_at = stage_at
        workflow_run.completed_at = None
        workflow_run.latency_ms = None

        try:
            persona_context = await self._persona_context_handler.resolve_current_published(data.room_id)
            workflow_run = self._persona_context_handler.freeze_workflow_run(
                workflow_run,
                persona_context,
                frozen_at=stage_at,
            )
            workflow_run.workflow_status = WorkflowStatus.RUNNING
            workflow_run.started_at = workflow_run.started_at or stage_at

            workflow_run = await self._semantic_classification_handler.classify_workflow_run(
                workflow_run,
                data,
                classified_at=stage_at,
            )

            interest_input = self._build_interest_input(workflow_run)
            workflow_run = await self._interest_handler.evaluate_workflow_run(
                workflow_run,
                interest_input,
                evaluated_at=stage_at,
            )
            if workflow_run.workflow_status is WorkflowStatus.ABORTED:
                workflow_run = self._finalize_now(workflow_run, completed_at=stage_at)
                return await self._persist(workflow_run)

            reply_input = self._build_reply_input(workflow_run, interest_input)
            workflow_run = await self._reply_handler.generate_workflow_run(
                workflow_run,
                reply_input,
                generated_at=stage_at,
            )
            if workflow_run.workflow_status is WorkflowStatus.ABORTED:
                workflow_run = self._finalize_now(workflow_run, completed_at=stage_at)
                return await self._persist(workflow_run)

            workflow_run, safety_scan = self._safety_rule_scanner.scan(
                workflow_run,
                self._build_review_evidence(workflow_run, reply_input),
                scanned_at=stage_at,
            )
            workflow_run = self._attach_safety_scan(workflow_run, safety_scan)
            review_input = self._build_review_input(
                workflow_run,
                reply_input,
                safety_scan=safety_scan,
                recent_push_records=recent_push_records,
            )

            workflow_run = await self._review_handler.review_workflow_run(
                workflow_run,
                review_input,
                reviewed_at=stage_at,
            )
            workflow_run = self._attach_client_delivery_stage(workflow_run, stage_at)
            workflow_run = self._finalize_now(workflow_run, completed_at=stage_at)
            return await self._persist(workflow_run)
        except ApplicationError as exc:
            workflow_run = self._mark_aborted(workflow_run, reason=exc.message, completed_at=stage_at)
            return await self._persist(workflow_run)
        except Exception as exc:  # noqa: BLE001
            workflow_run = self._mark_failed(workflow_run, exc, completed_at=stage_at)
            return await self._persist(workflow_run)

    def _build_interest_input(self, workflow_run: WorkflowRunStruct) -> InterestAgentInputStruct:
        semantic_stage = workflow_run.semantic_classification_stage
        if semantic_stage is None:
            raise RuntimeError("Semantic classification stage is missing from workflow run.")

        return InterestAgentInputStruct(
            room_id=workflow_run.room_id,
            semantic_type=workflow_run.semantic_type,
            semantic_confidence=float(semantic_stage.output.get("confidence", 0)),
            candidates=self._load_candidates(semantic_stage.output.get("candidates", [])),
        )

    def _build_reply_input(
        self,
        workflow_run: WorkflowRunStruct,
        interest_input: InterestAgentInputStruct,
    ) -> ReplyAgentInputStruct:
        if workflow_run.persona_id is None or workflow_run.persona_version is None:
            raise RuntimeError("Persona context was not frozen before reply generation.")

        interest_stage = workflow_run.interest_stage
        if interest_stage is None:
            raise RuntimeError("Workflow run is missing interest stage data.")

        selected_comment = self._find_selected_candidate(
            interest_stage.output.get("agent_result", {}),
            interest_input.candidates,
        )
        if selected_comment is None:
            raise RuntimeError("Interest stage did not produce a usable selected comment.")

        return ReplyAgentInputStruct(
            room_id=workflow_run.room_id,
            persona_context=self._build_persona_context(workflow_run),
            selected_comment=selected_comment,
            interest_score=float(interest_stage.output["agent_result"]["interest_score"]),
            interest_type=workflow_run.semantic_type,
            interest_reason=str(interest_stage.output["agent_result"]["reason"]),
        )

    def _build_review_input(
        self,
        workflow_run: WorkflowRunStruct,
        reply_input: ReplyAgentInputStruct,
        *,
        safety_scan: SafetyRuleScanResultStruct,
        recent_push_records: Sequence[dict[str, Any]] | None,
    ) -> ReviewAgentInputStruct:
        reply_stage = workflow_run.reply_stage
        if reply_stage is None:
            raise RuntimeError("Reply stage is missing from workflow run.")

        return ReviewAgentInputStruct(
            room_id=workflow_run.room_id,
            persona_context=reply_input.persona_context,
            selected_comment=reply_input.selected_comment,
            reply=ReplyAgentOutput.model_validate(dict(reply_stage.output["agent_result"])),
            semantic_type=workflow_run.semantic_type,
            safety_scan=safety_scan,
            recent_push_records=list(recent_push_records or []),
        )

    def _build_review_evidence(
        self,
        workflow_run: WorkflowRunStruct,
        reply_input: ReplyAgentInputStruct,
    ) -> dict[str, str]:
        reply_stage = workflow_run.reply_stage
        if reply_stage is None:
            raise RuntimeError("Reply stage is missing from workflow run.")

        return {
            "selected_comment": reply_input.selected_comment.text,
            "quick_reply": str(reply_stage.output["agent_result"]["quick_reply"]),
            "cue": str(reply_stage.output["agent_result"]["cue"]),
            "persona_summary": reply_input.persona_context.persona_summary or "",
        }

    def _attach_safety_scan(
        self,
        workflow_run: WorkflowRunStruct,
        safety_scan: SafetyRuleScanResultStruct,
    ) -> WorkflowRunStruct:
        scanned = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        scanned.global_rule_version = safety_scan.global_rule_version
        scanned.organization_rule_version = safety_scan.organization_rule_version
        scanned.room_rule_version = safety_scan.room_rule_version
        scanned.risk_categories = list(safety_scan.risk_categories)
        scanned.review_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.REVIEW_STAGE,
            started_at=workflow_run.review_stage.started_at
            if workflow_run.review_stage is not None
            else datetime.now(UTC),
            completed_at=None,
            input=workflow_run.review_stage.input if workflow_run.review_stage is not None else {},
            output={"safety_scan": safety_scan.to_dict()},
            error=workflow_run.review_stage.error if workflow_run.review_stage is not None else None,
            attempts=workflow_run.review_stage.attempts if workflow_run.review_stage is not None else [],
        )
        return scanned

    def _attach_client_delivery_stage(
        self,
        workflow_run: WorkflowRunStruct,
        completed_at: datetime,
    ) -> WorkflowRunStruct:
        delivered = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        delivered.pushed_to_client = False
        delivered.delivered_to_client = False
        delivered.client_delivery_stage = WorkflowStageEnvelopeStruct(
            stage_name=WorkflowStageName.CLIENT_DELIVERY_STAGE,
            started_at=completed_at,
            completed_at=completed_at,
            latency_ms=0,
            input={
                "push_action": workflow_run.push_action.value if workflow_run.push_action is not None else None,
            },
            output={
                "pushed_to_client": False,
                "delivered_to_client": False,
            },
        )
        return delivered

    def _mark_aborted(
        self,
        workflow_run: WorkflowRunStruct,
        *,
        reason: str,
        completed_at: datetime,
    ) -> WorkflowRunStruct:
        aborted = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        aborted.workflow_status = WorkflowStatus.ABORTED
        aborted.skip_reason = reason
        return self._finalize_now(aborted, completed_at=completed_at)

    def _mark_failed(
        self,
        workflow_run: WorkflowRunStruct,
        exc: Exception,
        *,
        completed_at: datetime,
    ) -> WorkflowRunStruct:
        failed = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        failed.workflow_status = WorkflowStatus.FAILED
        failed.skip_reason = type(exc).__name__
        if failed.review_stage is None:
            failed.review_stage = WorkflowStageEnvelopeStruct(
                stage_name=WorkflowStageName.REVIEW_STAGE,
                started_at=completed_at,
                completed_at=completed_at,
                error={
                    "type": type(exc).__name__,
                    "message": "Workflow execution failed.",
                },
            )
        else:
            failed.review_stage.error = {
                "type": type(exc).__name__,
                "message": "Workflow execution failed.",
            }
        return self._finalize_now(failed, completed_at=completed_at)

    def _finalize_now(
        self,
        workflow_run: WorkflowRunStruct,
        *,
        completed_at: datetime,
    ) -> WorkflowRunStruct:
        finalized = WorkflowRunStruct.from_dict(workflow_run.to_dict())
        finalized.completed_at = completed_at
        if finalized.started_at is not None:
            finalized.latency_ms = max(round((completed_at - finalized.started_at).total_seconds() * 1000), 0)
        if finalized.workflow_status is WorkflowStatus.RUNNING:
            finalized.workflow_status = WorkflowStatus.COMPLETED
        if finalized.workflow_status is WorkflowStatus.COMPLETED and finalized.client_delivery_stage is None:
            finalized = self._attach_client_delivery_stage(finalized, completed_at)
        return finalized

    async def _persist(self, workflow_run: WorkflowRunStruct) -> WorkflowRunStruct:
        if self._workflow_run_service is None:
            return workflow_run

        await self._workflow_run_service.create(workflow_run.to_dict())
        return workflow_run

    def _build_persona_context(self, workflow_run: WorkflowRunStruct) -> WorkflowPersonaContextStruct:
        if workflow_run.persona_id is None or workflow_run.persona_version is None:
            raise RuntimeError("Persona context is missing from workflow run.")

        if workflow_run.persona_context_stage is None:
            raise RuntimeError("Persona context stage is missing from workflow run.")

        return WorkflowPersonaContextStruct.from_dict(dict(workflow_run.persona_context_stage.output))

    def _load_candidates(
        self,
        candidates: Sequence[dict[str, Any]],
    ) -> list[SemanticClassificationCandidateStruct]:
        return [SemanticClassificationCandidateStruct.from_dict(dict(candidate)) for candidate in candidates]

    def _find_selected_candidate(
        self,
        agent_result: dict[str, Any],
        candidates: Sequence[SemanticClassificationCandidateStruct],
    ) -> SemanticClassificationCandidateStruct | None:
        selected_comment_id = agent_result.get("selected_comment_id")
        if selected_comment_id is None:
            return None

        for candidate in candidates:
            if candidate.comment_id == selected_comment_id:
                return candidate

        return None

    def _current_safety_scan_result(self, workflow_run: WorkflowRunStruct) -> SafetyRuleScanResultStruct | None:
        review_stage = workflow_run.review_stage
        if review_stage is None:
            return None

        safety_scan = review_stage.output.get("safety_scan")
        if safety_scan is None:
            return None

        return SafetyRuleScanResultStruct.from_dict(dict(safety_scan))
