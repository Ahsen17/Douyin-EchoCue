"""Semantic classification boundaries for live comment windows.

This module defines request and result structures shared by the main backend,
local fallback classifiers, and remote semantic classification clients.
"""

from collections.abc import Iterable
from typing import Protocol

from msgspec import field

from aigc.base import BaseStruct

from .enum import SemanticType

__all__ = (
    "FakeSemanticClassificationClient",
    "SemanticClassificationCandidateStruct",
    "SemanticClassificationClient",
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


class SemanticClassificationClient(Protocol):
    """Client boundary used to classify live comment windows."""

    async def classify(self, request: SemanticClassificationRequestStruct) -> SemanticClassificationResultStruct:
        """Classify a comment window."""


class FakeSemanticClassificationClient:
    """Local deterministic classifier used when the remote classifier is unavailable."""

    _KEYWORDS: dict[SemanticType, tuple[str, ...]] = {
        SemanticType.PRICE_PROMOTION: ("价格", "多少钱", "优惠", "券", "便宜", "到手价"),
        SemanticType.SPECIFICATION: ("尺码", "颜色", "规格", "容量", "型号", "尺寸"),
        SemanticType.STOCK: ("库存", "还有吗", "补货", "卖完", "缺货", "现货"),
        SemanticType.LOGISTICS: ("发货", "包邮", "运费", "几天到", "快递", "物流"),
        SemanticType.AFTER_SALE: ("退", "换", "保修", "售后", "质保", "质量"),
        SemanticType.SELLING_POINT: ("好用", "效果", "材质", "成分", "卖点", "优势"),
        SemanticType.AUDIENCE_SCENARIO: ("适合", "孕妇", "学生", "老人", "小孩", "敏感肌"),
        SemanticType.GENERAL_INTERACTION: ("主播", "看看", "来了", "喜欢", "关注", "下单"),
    }

    async def classify(self, request: SemanticClassificationRequestStruct) -> SemanticClassificationResultStruct:
        """Classify comments by deterministic keyword voting."""

        scores = self._score(request.text_batch)
        if not scores:
            return SemanticClassificationResultStruct.other()

        semantic_type, score = max(scores.items(), key=lambda item: item[1])
        total_score = sum(scores.values())
        candidates = [
            SemanticClassificationCandidateStruct(semantic_type=item_type, score=item_score)
            for item_type, item_score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ]
        return SemanticClassificationResultStruct(
            semantic_type=semantic_type,
            confidence=score / total_score,
            candidates=candidates,
        )

    def _score(self, text_batch: Iterable[str]) -> dict[SemanticType, float]:
        scores: dict[SemanticType, float] = {}
        for text in text_batch:
            normalized = text.lower()
            for semantic_type, keywords in self._KEYWORDS.items():
                matches = sum(1 for keyword in keywords if keyword.lower() in normalized)
                if matches:
                    scores[semantic_type] = scores.get(semantic_type, 0) + matches

        return scores
