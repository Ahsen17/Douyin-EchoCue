from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import anyio
import anyio.lowlevel
import pytest
from qdrant_client import AsyncQdrantClient

from echocue.core.lexicon import (
    FakeSemanticClassificationClient,
    QdrantSemanticClassificationClient,
    SemanticClassificationCommentStruct,
    SemanticClassificationRequestStruct,
    SemanticType,
)
from echocue.core.lexicon.lexicon import rebuild_lexicon_collection
from echocue.shared.embedder import SparseVector

if TYPE_CHECKING:
    from collections.abc import Sequence


class FakeScoredPoint:
    score: float
    payload: dict[str, str]

    def __init__(self, *, score: float, semantic_type: SemanticType) -> None:
        self.score = score
        self.payload = {"semantic_type": semantic_type.value}


class FakeQueryResponse:
    points: "Sequence[FakeScoredPoint]"

    def __init__(self, points: "Sequence[FakeScoredPoint]") -> None:
        self.points = points


class DelayedQdrantClient:
    active_queries: int
    max_active_queries: int

    def __init__(self) -> None:
        self.active_queries = 0
        self.max_active_queries = 0

    async def query_points(
        self,
        *,
        collection_name: str,
        query: SparseVector,
        using: str,
        limit: int,
        with_payload: list[str],
        score_threshold: float | None,
    ) -> FakeQueryResponse:
        self.active_queries += 1
        self.max_active_queries = max(self.max_active_queries, self.active_queries)
        await anyio.lowlevel.checkpoint()
        self.active_queries -= 1
        return FakeQueryResponse([FakeScoredPoint(score=1.0, semantic_type=SemanticType.PERSONA_PRAISE)])


class FailingQdrantClient:
    async def query_points(
        self,
        *,
        collection_name: str,
        query: SparseVector,
        using: str,
        limit: int,
        with_payload: list[str],
        score_threshold: float | None,
    ) -> FakeQueryResponse:
        raise RuntimeError("qdrant unavailable")


class SlowCollectionQdrantClient:
    async def get_collection(self, collection_name: str) -> Any:
        await anyio.sleep(1)
        return object()


class TestQdrantSemanticClassificationClient:
    qdrant_client: AsyncQdrantClient

    @pytest.fixture(autouse=True)
    def set_up(self) -> None:
        self.qdrant_client = AsyncQdrantClient(location=":memory:")

    async def test_classifies_by_sparse_lexicon(self, tmp_path: Path) -> None:
        samples_file = tmp_path / "lexicon_samples.jsonl"
        samples_file.write_text(
            '{"id":"persona_praise_000001","semantic_type":"persona_praise","text":"主播今天状态太好了","description":"praise"}\n'
            '{"id":"playful_joke_000001","semantic_type":"playful_joke","text":"这波操作笑死我了","description":"joke"}\n',
            encoding="utf-8",
        )
        await rebuild_lexicon_collection(
            self.qdrant_client,
            samples_file=samples_file,
            collection_name="test_lexicon",
        )
        classification_client = QdrantSemanticClassificationClient(
            self.qdrant_client,
            collection_name="test_lexicon",
            limit=2,
        )

        result = await classification_client.classify(
            SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了", "团队也太强了"])
        )
        await self.qdrant_client.close()

        assert result.semantic_type is SemanticType.PERSONA_PRAISE
        assert result.confidence > 0
        assert result.candidates[0].semantic_type is SemanticType.PERSONA_PRAISE

    async def test_returns_other_for_empty_text_batch(self) -> None:
        classification_client = QdrantSemanticClassificationClient(
            self.qdrant_client,
            collection_name="test_lexicon",
        )

        result = await classification_client.classify(
            SemanticClassificationRequestStruct(room_id="room-a", text_batch=["", "   "])
        )
        await self.qdrant_client.close()

        assert result.semantic_type is SemanticType.OTHER
        assert result.confidence == 0
        assert result.candidates == []

    async def test_returns_other_when_window_confidence_is_below_threshold(self) -> None:
        classification_client = FakeSemanticClassificationClient()

        result = await classification_client.classify(
            SemanticClassificationRequestStruct(
                room_id="room-a",
                text_batch=["主播好帅", "这波操作笑死我了"],
            )
        )

        assert result.semantic_type is SemanticType.OTHER
        assert result.confidence == 0.5
        assert {candidate.semantic_type for candidate in result.candidates} == {
            SemanticType.PERSONA_PRAISE,
            SemanticType.PLAYFUL_JOKE,
        }

    async def test_returns_other_when_collection_is_unavailable(self) -> None:
        classification_client = QdrantSemanticClassificationClient(
            self.qdrant_client,
            collection_name="missing_lexicon",
        )

        result = await classification_client.classify(
            SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了"])
        )
        await self.qdrant_client.close()

        assert result.semantic_type is SemanticType.OTHER
        assert result.confidence == 0
        assert result.candidates == []

    async def test_queries_comment_batch_in_batches_of_five(self) -> None:
        qdrant_client = DelayedQdrantClient()
        classification_client = QdrantSemanticClassificationClient(
            cast("AsyncQdrantClient", qdrant_client),
            collection_name="test_lexicon",
        )

        result = await classification_client.classify(
            SemanticClassificationRequestStruct(
                room_id="room-a",
                text_batch=["主播今天状态太好了", "团队也太强了"],
                comment_batch=[
                    SemanticClassificationCommentStruct(comment_id="comment-1", text="主播今天状态太好了"),
                    SemanticClassificationCommentStruct(comment_id="comment-2", text="团队也太强了"),
                    SemanticClassificationCommentStruct(comment_id="comment-3", text="主播今天状态太好了"),
                    SemanticClassificationCommentStruct(comment_id="comment-4", text="团队也太强了"),
                    SemanticClassificationCommentStruct(comment_id="comment-5", text="主播今天状态太好了"),
                    SemanticClassificationCommentStruct(comment_id="comment-6", text="团队也太强了"),
                ],
            )
        )

        assert qdrant_client.max_active_queries == 5
        assert result.semantic_type is SemanticType.PERSONA_PRAISE
        assert len(result.candidates) == 5

    async def test_logs_qdrant_query_failure(self, capfd: pytest.CaptureFixture[str]) -> None:
        classification_client = QdrantSemanticClassificationClient(
            cast("AsyncQdrantClient", FailingQdrantClient()),
            collection_name="test_lexicon",
        )

        result = await classification_client.classify(
            SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了"])
        )

        assert result.semantic_type is SemanticType.OTHER
        assert "qdrant semantic classification query failed" in capfd.readouterr().out

    async def test_collection_check_uses_bounded_timeout(self, capfd: pytest.CaptureFixture[str]) -> None:
        classification_client = QdrantSemanticClassificationClient(
            cast("AsyncQdrantClient", SlowCollectionQdrantClient()),
            collection_name="test_lexicon",
        )

        await classification_client.check_collection(timeout=0.01)

        assert "qdrant semantic classification collection check timed out" in capfd.readouterr().out
