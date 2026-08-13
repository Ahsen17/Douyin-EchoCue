from collections.abc import Callable
from functools import partial
from typing import Any

from litestar import Response
from litestar.background_tasks import BackgroundTask
from litestar.status_codes import HTTP_200_OK

from aigc.base import CamelizedBaseStruct

__all__ = ("GenericResponse",)


type _DataType = CamelizedBaseStruct | Any


class _response(CamelizedBaseStruct):  # noqa: N801
    """Inner response body for generic response."""

    code: int = HTTP_200_OK
    message: str | None = None
    data: _DataType = None


class GenericResponse[T: _DataType](Response):
    """Generic response class for application."""

    def __init__(
        self,
        status_code: int = HTTP_200_OK,
        message: str | None = None,
        data: T | None = None,
        background: Callable[..., Any] | partial | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            status_code=status_code,
            content=None,
            background=BackgroundTask(fn=background) if background else None,
            **kwargs,
        )

        self.content = _response(
            code=status_code,
            message=message,
            data=data or None,
        ).to_dict()
