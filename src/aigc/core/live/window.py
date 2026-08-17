"""Comment window schemas and aggregation boundaries for live comments.

This module defines service-layer and API-facing structures for comment window
snapshots.
"""

from datetime import datetime

from aigc.base import BaseStruct, CamelizedBaseStruct
from aigc.core.lexicon import SemanticType

from ._conversion import convert_struct

__all__ = (
    "CommentWindowItemStruct",
    "CommentWindowItemVO",
    "CommentWindowStruct",
    "CommentWindowVO",
)


class CommentWindowItemStruct(BaseStruct):
    """Single normalized comment inside a window snapshot."""

    comment_id: str
    user_id: str
    nickname: str
    content: str
    occurred_at: datetime


class CommentWindowItemVO(CamelizedBaseStruct):
    """Comment item view object returned by API endpoints."""

    comment_id: str
    user_id: str
    nickname: str
    content: str
    occurred_at: datetime

    @classmethod
    def from_struct(cls, data: CommentWindowItemStruct) -> "CommentWindowItemVO":
        """Build a view object from a service-layer comment item."""

        return convert_struct(data, cls)


class CommentWindowStruct(BaseStruct):
    """Service-layer comment window snapshot."""

    room_id: str
    window_started_at: datetime
    window_ended_at: datetime
    total_count: int
    unique_user_count: int
    comments: list[CommentWindowItemStruct]
    text_batch: list[str]
    semantic_type: SemanticType = SemanticType.OTHER


class CommentWindowVO(CamelizedBaseStruct):
    """Comment window view object returned by API endpoints."""

    room_id: str
    window_started_at: datetime
    window_ended_at: datetime
    total_count: int
    unique_user_count: int
    comments: list[CommentWindowItemVO]
    text_batch: list[str]
    semantic_type: SemanticType

    @classmethod
    def from_struct(cls, data: CommentWindowStruct) -> "CommentWindowVO":
        """Build a view object from a service-layer window snapshot."""

        return convert_struct(data, cls)
