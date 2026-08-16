from pathlib import Path

from qdrant_client import AsyncQdrantClient

from aigc.core.live.classifier import (
    QdrantSemanticClassificationClient,
    SemanticClassificationRequestStruct,
    SemanticType,
)
from aigc.core.live.classifier.lexicon import rebuild_lexicon_collection


async def test_qdrant_semantic_classification_client_classifies_by_sparse_lexicon(tmp_path: Path) -> None:
    samples_file = tmp_path / "lexicon_samples.jsonl"
    samples_file.write_text(
        '{"id":"price_promotion_000001","semantic_type":"price_promotion","text":"多少钱 优惠券","description":"price"}\n'
        '{"id":"stock_000001","semantic_type":"stock","text":"库存 补货","description":"stock"}\n',
        encoding="utf-8",
    )
    qdrant_client = AsyncQdrantClient(location=":memory:")
    await rebuild_lexicon_collection(qdrant_client, samples_file=samples_file, collection_name="test_lexicon")
    classification_client = QdrantSemanticClassificationClient(
        qdrant_client,
        collection_name="test_lexicon",
        limit=2,
    )

    result = await classification_client.classify(
        SemanticClassificationRequestStruct(room_id="room-a", text_batch=["这个多少钱", "有没有优惠券"])
    )
    await qdrant_client.close()

    assert result.semantic_type is SemanticType.PRICE_PROMOTION
    assert result.confidence > 0
    assert result.candidates[0].semantic_type is SemanticType.PRICE_PROMOTION


async def test_qdrant_semantic_classification_client_returns_other_for_empty_text_batch() -> None:
    qdrant_client = AsyncQdrantClient(location=":memory:")
    classification_client = QdrantSemanticClassificationClient(qdrant_client, collection_name="test_lexicon")

    result = await classification_client.classify(
        SemanticClassificationRequestStruct(room_id="room-a", text_batch=["", "   "])
    )
    await qdrant_client.close()

    assert result.semantic_type is SemanticType.OTHER
    assert result.confidence == 0
    assert result.candidates == []


async def test_qdrant_semantic_classification_client_returns_other_when_collection_is_unavailable() -> None:
    qdrant_client = AsyncQdrantClient(location=":memory:")
    classification_client = QdrantSemanticClassificationClient(qdrant_client, collection_name="missing_lexicon")

    result = await classification_client.classify(
        SemanticClassificationRequestStruct(room_id="room-a", text_batch=["这个多少钱"])
    )
    await qdrant_client.close()

    assert result.semantic_type is SemanticType.OTHER
    assert result.confidence == 0
    assert result.candidates == []
