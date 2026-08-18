"""Workflow domain exceptions."""

from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from echocue.shared import ApplicationError

__all__ = (
    "WorkflowInterestInputRoomMismatchError",
    "WorkflowPersonaContextNotFoundError",
    "WorkflowPersonaContextRoomMismatchError",
    "WorkflowSemanticClassificationRoomMismatchError",
)


class WorkflowInterestInputRoomMismatchError(ApplicationError):
    """Raised when InterestAgent input does not belong to the workflow room."""

    def __init__(self, workflow_room_id: str, interest_room_id: str) -> None:
        """Initialize the InterestAgent input room mismatch error."""

        super().__init__(
            f"InterestAgent input room {interest_room_id} does not match workflow room {workflow_room_id}.",
            status_code=HTTP_400_BAD_REQUEST,
        )


class WorkflowPersonaContextNotFoundError(ApplicationError):
    """Raised when a workflow cannot resolve the current published persona context."""

    def __init__(self, room_id: str) -> None:
        """Initialize the missing persona context error."""

        super().__init__(
            f"Published persona context was not found for room {room_id}.",
            status_code=HTTP_404_NOT_FOUND,
        )


class WorkflowPersonaContextRoomMismatchError(ApplicationError):
    """Raised when a persona context does not belong to the workflow room."""

    def __init__(self, workflow_room_id: str, persona_room_id: str) -> None:
        """Initialize the room mismatch error."""

        super().__init__(
            (f"Published persona context room {persona_room_id} does not match workflow room {workflow_room_id}."),
            status_code=HTTP_400_BAD_REQUEST,
        )


class WorkflowSemanticClassificationRoomMismatchError(ApplicationError):
    """Raised when a semantic classification input does not belong to the workflow room."""

    def __init__(self, workflow_room_id: str, classification_room_id: str) -> None:
        """Initialize the semantic classification room mismatch error."""

        super().__init__(
            (f"Semantic classification room {classification_room_id} does not match workflow room {workflow_room_id}."),
            status_code=HTTP_400_BAD_REQUEST,
        )
