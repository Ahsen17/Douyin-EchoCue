"""Semantic classification schemas for live comment windows.

This module defines request and result structures shared by the main backend
and semantic classification clients.
"""

from msgspec import field

from aigc.base import BaseStruct

from .enum import SemanticType

__all__ = (
    "SemanticClassificationCandidateStruct",
    "SemanticClassificationRequestStruct",
    "SemanticClassificationResultStruct",
)


class SemanticClassificationRequestStruct(BaseStruct):
    """Window-level semantic classification request."""

    room_id: str
    text_batch: list[str]


class SemanticClassificationCandidateStruct(BaseStruct):
    """Single semantic classification candidate returned by retrieval."""

    semantic_type: SemanticType
    score: float


class SemanticClassificationResultStruct(BaseStruct):
    """Window-level semantic classification result."""

    semantic_type: SemanticType = SemanticType.OTHER
    confidence: float = 0
    candidates: list[SemanticClassificationCandidateStruct] = field(default_factory=list)

    @classmethod
    def other(cls) -> "SemanticClassificationResultStruct":
        """Return the fallback classification result."""

        return cls()
