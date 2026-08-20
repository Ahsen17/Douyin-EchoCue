"""Live-domain business exceptions."""

from litestar.status_codes import HTTP_503_SERVICE_UNAVAILABLE

from echocue.shared import ApplicationError

__all__ = ("RoomStatusCacheUnavailableError",)


class RoomStatusCacheUnavailableError(ApplicationError):
    """Raised when the room online-status cache cannot serve an operation."""

    def __init__(self) -> None:
        """Initialize a sanitized service-unavailable error."""

        super().__init__(
            message="Room status cache is unavailable.",
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
        )
