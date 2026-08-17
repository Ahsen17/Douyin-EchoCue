from litestar import Controller, get

from echocue.shared import GenericResponse

__all__ = ("SystemController",)


class SystemController(Controller):
    """Controller for system-level endpoints (no domain logic)."""

    path = "/system"
    tags = ["system"]

    @get(
        path="/health",
        operation_id="system:health",
        summary="Health check",
    )
    async def health(self) -> GenericResponse:
        return GenericResponse(message="ok")
