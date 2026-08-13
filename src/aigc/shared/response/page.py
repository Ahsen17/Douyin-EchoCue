from typing import Annotated, Any

from msgspec import Meta, field

from aigc.base import CamelizedBaseStruct

__all__ = ("Pagination",)


class Pagination(CamelizedBaseStruct):
    """Pagination response data structure."""

    data: Annotated[Any, Meta(description="Data of page.")]
    next_offset: Annotated[int, Meta(description="Next offset of page.")]
    length: Annotated[int, Meta(description="Length of page.")]
    total: Annotated[int | None, Meta(description="Total of page.")] = field(default=None)
