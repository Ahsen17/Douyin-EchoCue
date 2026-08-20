"""Client-domain business exceptions."""

from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT, HTTP_503_SERVICE_UNAVAILABLE

from echocue.shared import ApplicationError

from .enum import RuntimeErrorCode
from .schema import RuntimeFailureVO

__all__ = (
    "ClientSessionConflictError",
    "RemediationNotAvailableError",
    "RemediationStoreUnavailableError",
    "RemediationTokenInvalidError",
)


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


class RemediationNotAvailableError(ApplicationError):
    """Raised when a request does not match the client's latest failure."""

    def __init__(self) -> None:
        super().__init__(
            message="No matching remediation is available.",
            status_code=HTTP_409_CONFLICT,
        )


class RemediationTokenInvalidError(ApplicationError):
    """Raised for unknown, expired, or already consumed tokens."""

    def __init__(self) -> None:
        super().__init__(
            message="The remediation token is invalid or expired.",
            status_code=HTTP_400_BAD_REQUEST,
        )


class RemediationStoreUnavailableError(ApplicationError):
    """Raised when remediation state cannot be accessed safely."""

    def __init__(self) -> None:
        super().__init__(
            message="Remediation service is unavailable.",
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
        )
