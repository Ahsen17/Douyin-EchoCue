"""Authentication domain exceptions.

This module defines business exceptions for authentication domain rules.
Framework authentication errors should keep using Litestar exceptions.
"""

from litestar.status_codes import HTTP_403_FORBIDDEN

from echocue.shared.exception import ApplicationError

__all__ = ("UserDisabledError",)


class UserDisabledError(ApplicationError):
    """Raised when an inactive user attempts to authenticate."""

    def __init__(self) -> None:
        """Initialize the disabled user error."""

        super().__init__("User is disabled.", status_code=HTTP_403_FORBIDDEN)
