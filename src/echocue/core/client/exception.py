"""Client-domain business exceptions."""

from litestar.status_codes import HTTP_409_CONFLICT

from echocue.shared import ApplicationError

from .enum import RuntimeErrorCode
from .schema import RuntimeFailureVO

__all__ = ("ClientSessionConflictError",)


class ClientSessionConflictError(ApplicationError):
    """Raised when a user is already bound to another client."""

    def __init__(self) -> None:
        super().__init__(
            message="Current account is already signed in on another client.",
            status_code=HTTP_409_CONFLICT,
            data=RuntimeFailureVO(
                error_code=RuntimeErrorCode.CLIENT_SESSION_CONFLICT,
                message="Current account is already signed in on another client.",
            ),
        )
