from pathlib import Path
from uuid import UUID

from qdrant_client import AsyncQdrantClient

from aigc.core.live import SemanticType
from aigc.core.live.lexicon import load_lexicon_samples, rebuild_lexicon_collection


def test_load_lexicon_samples_decodes_jsonl(tmp_path: Path) -> None:
    samples_file = tmp_path / "lexicon_samples.jsonl"
    samples_file.write_text(
        '{"id":"price_promotion_000001","semantic_type":"price_promotion","text":"多少钱","description":"price"}\n'
        '{"id":"stock_000001","semantic_type":"stock","text":"还有库存吗","description":"stock"}\n',
        encoding="utf-8",
    )

    samples = load_lexicon_samples(samples_file)

    assert [sample.semantic_type for sample in samples] == [SemanticType.PRICE_PROMOTION, SemanticType.STOCK]
    assert [sample.text for sample in samples] == ["多少钱", "还有库存吗"]


async def test_rebuild_lexicon_collection_recreates_sparse_collection(tmp_path: Path) -> None:
    samples_file = tmp_path / "lexicon_samples.jsonl"
    samples_file.write_text(
        '{"id":"price_promotion_000001","semantic_type":"price_promotion","text":"多少钱","description":"price"}\n'
        '{"id":"stock_000001","semantic_type":"stock","text":"还有库存吗","description":"stock"}\n',
        encoding="utf-8",
    )
    client = AsyncQdrantClient(location=":memory:")

    result = await rebuild_lexicon_collection(
        client,
        samples_file=samples_file,
        collection_name="test_lexicon",
    )

    assert result.collection_name == "test_lexicon"
    assert result.sample_count == 2
    collection = await client.get_collection("test_lexicon")
    points, _ = await client.scroll(collection_name="test_lexicon", with_payload=True)
    await client.close()

    assert collection.config.params.sparse_vectors is not None
    assert "sparse" in collection.config.params.sparse_vectors
    assert all(UUID(str(point.id)) for point in points)
    assert [point.payload["sample_id"] for point in points if point.payload is not None] == [
        "price_promotion_000001",
        "stock_000001",
    ]
    assert [point.payload["semantic_type"] for point in points if point.payload is not None] == [
        "price_promotion",
        "stock",
    ]
