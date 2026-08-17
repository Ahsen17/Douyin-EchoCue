"""Semantic classification boundaries for live interaction lexicons."""

from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol

from msgspec import field

from aigc.base import BaseStruct
from aigc.shared.embedder import Bm25SparseEmbedder

from .enum import SemanticType
from .lexicon import DEFAULT_LEXICON_COLLECTION_NAME

__all__ = (
    "FakeSemanticClassificationClient",
    "QdrantSemanticClassificationClient",
    "SemanticClassificationCandidateStruct",
    "SemanticClassificationClient",
    "SemanticClassificationRequestStruct",
    "SemanticClassificationResultStruct",
)

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import ScoredPoint


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
    """Local deterministic classifier used when the remote lexicon service is unavailable."""

    _KEYWORDS: dict[SemanticType, tuple[str, ...]] = {
        SemanticType.PERSONA_PRAISE: ("厉害", "好帅", "好美", "太强", "太好", "状态", "喜欢你", "像你", "人设", "团队"),
        SemanticType.INTERACTIVE_PROMPT: ("为什么", "怎么做到", "能不能", "聊聊", "说说", "回应", "选哪个"),
        SemanticType.PLAYFUL_JOKE: ("笑死", "哈哈", "绷不住", "有梗", "整活", "反差", "名场面"),
        SemanticType.ATMOSPHERE_BOOST: ("冲", "起来", "刷起来", "气氛", "排面", "一起", "666", "上头"),
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


class QdrantSemanticClassificationClient:
    """Classify comment windows by retrieving sparse lexicon samples from Qdrant."""

    def __init__(
        self,
        client: "AsyncQdrantClient",
        *,
        collection_name: str = DEFAULT_LEXICON_COLLECTION_NAME,
        embedder: Bm25SparseEmbedder | None = None,
        limit: int = 8,
        score_threshold: float | None = None,
    ) -> None:
        self._client = client
        self._collection_name = collection_name
        self._embedder = embedder or Bm25SparseEmbedder(avg_len=1)
        self._limit = limit
        self._score_threshold = score_threshold

    async def classify(self, request: SemanticClassificationRequestStruct) -> SemanticClassificationResultStruct:
        """Classify a comment window through Qdrant sparse retrieval."""

        query_text = "\n".join(text for text in request.text_batch if text.strip())
        if not query_text:
            return SemanticClassificationResultStruct.other()

        query_vectors = self._embedder.query_embed(query_text)
        if not query_vectors:
            return SemanticClassificationResultStruct.other()

        try:
            response = await self._client.query_points(
                collection_name=self._collection_name,
                query=query_vectors[0],
                using="sparse",
                limit=self._limit,
                with_payload=["semantic_type"],
                score_threshold=self._score_threshold,
            )
        except Exception:  # noqa: BLE001
            return SemanticClassificationResultStruct.other()

        scores = _score_points_by_semantic_type(response.points)
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


def _score_points_by_semantic_type(points: Iterable["ScoredPoint"]) -> dict[SemanticType, float]:
    scores: dict[SemanticType, float] = {}
    for point in points:
        payload = point.payload
        if not isinstance(payload, dict):
            continue

        raw_semantic_type = payload.get("semantic_type")
        if not isinstance(raw_semantic_type, str):
            continue

        try:
            semantic_type = SemanticType(raw_semantic_type)
        except ValueError:
            continue

        scores[semantic_type] = scores.get(semantic_type, 0) + float(point.score)

    return scores
