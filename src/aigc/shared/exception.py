from typing import Any

from litestar import Request, Response
from litestar.exceptions import HTTPException, ValidationException
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from .response import GenericResponse

__all__ = ("ApplicationError",)


class ApplicationError(Exception):
    """Application business exception."""

    def __init__(
        self,
        message: str,
        status_code: int = HTTP_400_BAD_REQUEST,
        data: Any | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(message)


def app_error_handler(_: Request, exc: ApplicationError) -> Response:
    """Handle application business exceptions."""

    return GenericResponse(
        status_code=exc.status_code,
        message=exc.message,
        data=exc.data,
    )


def validation_exception_handler(_: Request, exc: ValidationException) -> Response:
    """Handle request validation exceptions."""

    return GenericResponse(
        status_code=exc.status_code,
        message=_get_exception_message(exc),
        data=exc.extra,
    )


def http_exception_handler(_: Request, exc: HTTPException) -> Response:
    """Handle Litestar HTTP exceptions."""

    return GenericResponse(
        status_code=exc.status_code,
        message=_get_exception_message(exc),
        data=exc.extra,
        headers=exc.headers,
    )


def internal_exception_handler(_: Request, __: Exception) -> Response:
    """Handle unhandled exceptions."""

    return GenericResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error.",
    )


def _get_exception_message(exc: HTTPException) -> str:
    return exc.detail or exc.__class__.__name__
