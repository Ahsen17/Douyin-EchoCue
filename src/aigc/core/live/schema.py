"""Live event schemas for simulated livestream comments.

This module defines the HTTP request, service-layer event, and API view object
boundaries for comment ingestion. It does not perform window aggregation.
"""

from datetime import datetime
from typing import Literal

from aigc.base import BaseStruct, CamelizedBaseStruct

from ._conversion import convert_struct

__all__ = (
    "CommentPayloadCreate",
    "CommentPayloadStruct",
    "CommentPayloadVO",
    "LiveCommentEventCreate",
    "LiveCommentEventStruct",
    "LiveCommentEventVO",
)


class CommentPayloadStruct(BaseStruct):
    """Normalized comment payload extracted from a livestream event."""

    comment_id: str
    content: str
    nickname: str


class CommentPayloadCreate(CamelizedBaseStruct):
    """Comment payload request body accepted from the simulator."""

    comment_id: str
    content: str
    nickname: str

    def to_struct(self) -> CommentPayloadStruct:
        """Convert the request payload to a service-layer payload."""

        return convert_struct(self, CommentPayloadStruct)


class CommentPayloadVO(CamelizedBaseStruct):
    """Comment payload view object returned by API endpoints."""

    comment_id: str
    content: str
    nickname: str

    @classmethod
    def from_struct(cls, data: CommentPayloadStruct) -> "CommentPayloadVO":
        """Build a view object from a service-layer payload."""

        return convert_struct(data, cls)


class LiveCommentEventStruct(BaseStruct):
    """Service-layer livestream comment event."""

    event_id: str
    platform: str
    event_type: Literal["comment"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: CommentPayloadStruct


class LiveCommentEventCreate(CamelizedBaseStruct):
    """Comment event request body accepted from the simulator."""

    event_id: str
    platform: str
    event_type: Literal["comment"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: CommentPayloadCreate

    def to_struct(self) -> LiveCommentEventStruct:
        """Convert the request body to a service-layer event."""

        return convert_struct(self, LiveCommentEventStruct)


class LiveCommentEventVO(CamelizedBaseStruct):
    """Comment event view object returned by API endpoints."""

    event_id: str
    platform: str
    event_type: Literal["comment"]
    room_id: str
    user_id: str
    occurred_at: datetime
    payload: CommentPayloadVO

    @classmethod
    def from_struct(cls, data: LiveCommentEventStruct) -> "LiveCommentEventVO":
        """Build a view object from a service-layer event."""

        return convert_struct(data, cls)
