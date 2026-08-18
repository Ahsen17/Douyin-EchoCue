"""Workflow domain enums."""

from enum import StrEnum, auto

__all__ = (
    "WorkflowPushAction",
    "WorkflowStageName",
    "WorkflowStatus",
    "WorkflowTriggerType",
)


class WorkflowStatus(StrEnum):
    """Lifecycle states for a workflow run."""

    PENDING = auto()
    """The workflow run has been created but has not started executing."""

    RUNNING = auto()
    """The workflow run is executing one or more stages."""

    COMPLETED = auto()
    """The workflow run finished normally, regardless of push or skip result."""

    ABORTED = auto()
    """The workflow run stopped because required business conditions were not met."""

    FAILED = auto()
    """The workflow run failed because of a system, dependency, or infrastructure error."""


class WorkflowTriggerType(StrEnum):
    """Workflow trigger sources."""

    SCHEDULED_COMMENT_WINDOW = auto()
    """Periodic comment-window scan used as the default workflow trigger."""

    HIGH_VALUE_COMMENT = auto()
    """Early workflow trigger caused by a high-value comment candidate."""


class WorkflowPushAction(StrEnum):
    """Workflow review decisions."""

    PUSH = auto()
    """The reviewed result is safe and useful enough to push to the active client."""

    SKIP = auto()
    """The reviewed result should not be pushed to the active client."""


class WorkflowStageName(StrEnum):
    """Named workflow stage envelopes."""

    COMMENT_WINDOW_STAGE = auto()
    """Stage that records the M2 comment-window input snapshot."""

    TRIGGER_EVALUATION_STAGE = auto()
    """Stage that records trigger-source, threshold, and cooldown evaluation."""

    PERSONA_CONTEXT_STAGE = auto()
    """Stage that records the frozen persona profile identity and version."""

    SEMANTIC_CLASSIFICATION_STAGE = auto()
    """Stage that records lexicon semantic classification request and result."""

    INTEREST_STAGE = auto()
    """Stage that records InterestAgent candidate scoring and selection."""

    REPLY_STAGE = auto()
    """Stage that records ReplyAgent generated display text, reply, and cue."""

    REVIEW_STAGE = auto()
    """Stage that records safety scan inputs and final review decision."""

    CLIENT_DELIVERY_STAGE = auto()
    """Stage reserved for client push, ACK, and retry records in M6."""


_ALLOWED_WORKFLOW_STATUS_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.PENDING: frozenset({WorkflowStatus.RUNNING, WorkflowStatus.FAILED}),
    WorkflowStatus.RUNNING: frozenset(
        {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.ABORTED,
            WorkflowStatus.FAILED,
        }
    ),
    WorkflowStatus.COMPLETED: frozenset(),
    WorkflowStatus.ABORTED: frozenset(),
    WorkflowStatus.FAILED: frozenset(),
}


def is_valid_workflow_status_transition(current: WorkflowStatus, target: WorkflowStatus) -> bool:
    """Return whether a workflow status transition is allowed."""

    return target in _ALLOWED_WORKFLOW_STATUS_TRANSITIONS[current]


def ensure_workflow_status_transition(current: WorkflowStatus, target: WorkflowStatus) -> None:
    """Raise when a workflow status transition is not allowed."""

    if is_valid_workflow_status_transition(current, target):
        return

    msg = f"Invalid workflow status transition: {current.value} -> {target.value}"
    raise ValueError(msg)
