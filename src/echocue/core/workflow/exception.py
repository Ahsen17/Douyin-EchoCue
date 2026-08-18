"""Workflow domain exceptions."""

from litestar.status_codes import HTTP_404_NOT_FOUND

from echocue.shared import ApplicationError

__all__ = ("WorkflowPersonaContextNotFoundError",)


class WorkflowPersonaContextNotFoundError(ApplicationError):
    """Raised when a workflow cannot resolve the current published persona context."""

    def __init__(self, room_id: str) -> None:
        """Initialize the missing persona context error."""

        super().__init__(
            f"Published persona context was not found for room {room_id}.",
            status_code=HTTP_404_NOT_FOUND,
        )
