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
    "SemanticClassificationCommentStruct",
    "SemanticClassificationRequestStruct",
    "SemanticClassificationResultStruct",
)

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import ScoredPoint


DEFAULT_SEMANTIC_CLASSIFICATION_TOP_N = 5
MIN_SEMANTIC_CLASSIFICATION_TOP_N = 1
MAX_SEMANTIC_CLASSIFICATION_TOP_N = 10
_SEMANTIC_TYPE_PRIORITY: dict[SemanticType, int] = {
    SemanticType.PERSONA_PRAISE: 4,
    SemanticType.INTERACTIVE_PROMPT: 3,
    SemanticType.PLAYFUL_JOKE: 2,
    SemanticType.ATMOSPHERE_BOOST: 1,
    SemanticType.OTHER: 0,
}


class SemanticClassificationCommentStruct(BaseStruct):
    """Single comment input for semantic classification candidates."""

    comment_id: str
    text: str


class SemanticClassificationRequestStruct(BaseStruct):
    """Window-level semantic classification request."""

    room_id: str
    text_batch: list[str]
    top_n: int = DEFAULT_SEMANTIC_CLASSIFICATION_TOP_N
    comment_batch: list[SemanticClassificationCommentStruct] = field(default_factory=list)


class SemanticClassificationCandidateStruct(BaseStruct):
    """Single semantic classification candidate returned by retrieval."""

    semantic_type: SemanticType
    score: float
    comment_id: str = ""
    text: str = ""
    confidence: float = 0


class SemanticClassificationResultStruct(BaseStruct):
    """Window-level semantic classification result."""

    semantic_type: SemanticType = SemanticType.OTHER
    confidence: float = 0
    top_n: int = DEFAULT_SEMANTIC_CLASSIFICATION_TOP_N
    candidates: list[SemanticClassificationCandidateStruct] = field(default_factory=list)

    @classmethod
    def other(cls, *, top_n: int = DEFAULT_SEMANTIC_CLASSIFICATION_TOP_N) -> "SemanticClassificationResultStruct":
        """Return the fallback classification result."""

        return cls(top_n=top_n)


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

        top_n = clamp_semantic_classification_top_n(request.top_n)
        if request.comment_batch:
            candidates = self._classify_comments(request.comment_batch, top_n=top_n)
            if not candidates:
                return SemanticClassificationResultStruct.other(top_n=top_n)

            scores = _score_candidates_by_semantic_type(candidates)
            semantic_type, score = _select_semantic_type(scores)
            total_score = sum(scores.values())
            return SemanticClassificationResultStruct(
                semantic_type=semantic_type,
                confidence=score / total_score,
                top_n=top_n,
                candidates=candidates,
            )

        scores = self._score(request.text_batch)
        if not scores:
            return SemanticClassificationResultStruct.other(top_n=top_n)

        semantic_type, score = _select_semantic_type(scores)
        total_score = sum(scores.values())
        candidates = [
            SemanticClassificationCandidateStruct(
                semantic_type=item_type,
                score=item_score,
                confidence=item_score / total_score,
            )
            for item_type, item_score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ]
        return SemanticClassificationResultStruct(
            semantic_type=semantic_type,
            confidence=score / total_score,
            top_n=top_n,
            candidates=candidates,
        )

    def _classify_comments(
        self,
        comments: Iterable[SemanticClassificationCommentStruct],
        *,
        top_n: int,
    ) -> list[SemanticClassificationCandidateStruct]:
        candidates: list[SemanticClassificationCandidateStruct] = []
        for comment in comments:
            scores = self._score((comment.text,))
            if not scores:
                continue

            semantic_type, score = _select_semantic_type(scores)
            total_score = sum(scores.values())
            candidates.append(
                SemanticClassificationCandidateStruct(
                    comment_id=comment.comment_id,
                    text=comment.text,
                    semantic_type=semantic_type,
                    score=score,
                    confidence=score / total_score,
                )
            )

        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:top_n]

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

        top_n = clamp_semantic_classification_top_n(request.top_n)
        if request.comment_batch:
            return await self._classify_comment_batch(request.comment_batch, top_n=top_n)

        query_text = "\n".join(text for text in request.text_batch if text.strip())
        if not query_text:
            return SemanticClassificationResultStruct.other(top_n=top_n)

        query_vectors = self._embedder.query_embed(query_text)
        if not query_vectors:
            return SemanticClassificationResultStruct.other(top_n=top_n)

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
            return SemanticClassificationResultStruct.other(top_n=top_n)

        scores = _score_points_by_semantic_type(response.points)
        if not scores:
            return SemanticClassificationResultStruct.other(top_n=top_n)

        semantic_type, score = _select_semantic_type(scores)
        total_score = sum(scores.values())
        candidates = [
            SemanticClassificationCandidateStruct(
                semantic_type=item_type,
                score=item_score,
                confidence=item_score / total_score,
            )
            for item_type, item_score in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ]
        return SemanticClassificationResultStruct(
            semantic_type=semantic_type,
            confidence=score / total_score,
            top_n=top_n,
            candidates=candidates,
        )

    async def _classify_comment_batch(
        self,
        comments: Iterable[SemanticClassificationCommentStruct],
        *,
        top_n: int,
    ) -> SemanticClassificationResultStruct:
        candidates: list[SemanticClassificationCandidateStruct] = []
        for comment in comments:
            scores = await self._query_scores(comment.text)
            if not scores:
                continue

            semantic_type, score = _select_semantic_type(scores)
            total_score = sum(scores.values())
            candidates.append(
                SemanticClassificationCandidateStruct(
                    comment_id=comment.comment_id,
                    text=comment.text,
                    semantic_type=semantic_type,
                    score=score,
                    confidence=score / total_score,
                )
            )

        if not candidates:
            return SemanticClassificationResultStruct.other(top_n=top_n)

        candidates = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:top_n]
        scores = _score_candidates_by_semantic_type(candidates)
        semantic_type, score = _select_semantic_type(scores)
        total_score = sum(scores.values())
        return SemanticClassificationResultStruct(
            semantic_type=semantic_type,
            confidence=score / total_score,
            top_n=top_n,
            candidates=candidates,
        )

    async def _query_scores(self, text: str) -> dict[SemanticType, float]:
        query_text = text.strip()
        if not query_text:
            return {}

        query_vectors = self._embedder.query_embed(query_text)
        if not query_vectors:
            return {}

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
            return {}

        return _score_points_by_semantic_type(response.points)


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


def _score_candidates_by_semantic_type(
    candidates: Iterable[SemanticClassificationCandidateStruct],
) -> dict[SemanticType, float]:
    scores: dict[SemanticType, float] = {}
    for candidate in candidates:
        scores[candidate.semantic_type] = scores.get(candidate.semantic_type, 0) + candidate.score

    return scores


def _select_semantic_type(scores: dict[SemanticType, float]) -> tuple[SemanticType, float]:
    return max(scores.items(), key=lambda item: (item[1], _SEMANTIC_TYPE_PRIORITY[item[0]]))


def clamp_semantic_classification_top_n(top_n: int) -> int:
    """Clamp candidate count to the MVP-supported range."""

    return max(MIN_SEMANTIC_CLASSIFICATION_TOP_N, min(top_n, MAX_SEMANTIC_CLASSIFICATION_TOP_N))
