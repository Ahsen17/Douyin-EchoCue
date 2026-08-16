from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from qdrant_client.models import PointStruct, SparseVectorParams

from aigc.core.live import SemanticType
from aigc.core.live.lexicon import load_lexicon_samples, rebuild_lexicon_collection


class FakeQdrantClient:
    def __init__(self, *, exists: bool) -> None:
        self.exists = exists
        self.deleted_collections: list[str] = []
        self.created_kwargs: dict[str, Any] | None = None
        self.upserted_points: list[PointStruct] = []

    async def collection_exists(self, collection_name: str, **kwargs: object) -> bool:
        return self.exists

    async def delete_collection(self, collection_name: str, **kwargs: object) -> bool:
        self.deleted_collections.append(collection_name)

        return True

    async def create_collection(
        self,
        collection_name: str,
        sparse_vectors_config: Mapping[str, SparseVectorParams] | None = None,
        **kwargs: object,
    ) -> bool:
        self.created_kwargs = {
            "collection_name": collection_name,
            "sparse_vectors_config": sparse_vectors_config,
            **kwargs,
        }

        return True

    async def upsert(self, collection_name: str, points: Sequence[PointStruct], **kwargs: object) -> object:
        self.upserted_points.extend(points)

        return object()


def test_load_lexicon_samples_decodes_jsonl(tmp_path: Path) -> None:
    samples_file = tmp_path / "semantic_samples.jsonl"
    samples_file.write_text(
        '{"id":"price_promotion_000001","semantic_type":"price_promotion","text":"多少钱","description":"price"}\n'
        '{"id":"stock_000001","semantic_type":"stock","text":"还有库存吗","description":"stock"}\n',
        encoding="utf-8",
    )

    samples = load_lexicon_samples(samples_file)

    assert [sample.semantic_type for sample in samples] == [SemanticType.PRICE_PROMOTION, SemanticType.STOCK]
    assert [sample.text for sample in samples] == ["多少钱", "还有库存吗"]


async def test_rebuild_lexicon_collection_recreates_sparse_collection(tmp_path: Path) -> None:
    samples_file = tmp_path / "semantic_samples.jsonl"
    samples_file.write_text(
        '{"id":"price_promotion_000001","semantic_type":"price_promotion","text":"多少钱","description":"price"}\n'
        '{"id":"stock_000001","semantic_type":"stock","text":"还有库存吗","description":"stock"}\n',
        encoding="utf-8",
    )
    client = FakeQdrantClient(exists=True)

    result = await rebuild_lexicon_collection(
        client,
        samples_file=samples_file,
        collection_name="test_lexicon",
    )

    assert result.collection_name == "test_lexicon"
    assert result.sample_count == 2
    assert client.deleted_collections == ["test_lexicon"]
    assert client.created_kwargs is not None
    assert client.created_kwargs["collection_name"] == "test_lexicon"
    assert "sparse" in client.created_kwargs["sparse_vectors_config"]
    assert all(UUID(str(point.id)) for point in client.upserted_points)
    assert [point.payload["sample_id"] for point in client.upserted_points if point.payload is not None] == [
        "price_promotion_000001",
        "stock_000001",
    ]
    assert [point.payload["semantic_type"] for point in client.upserted_points if point.payload is not None] == [
        "price_promotion",
        "stock",
    ]
