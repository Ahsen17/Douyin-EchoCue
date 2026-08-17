from pathlib import Path

from qdrant_client import AsyncQdrantClient

from aigc.core.lexicon import (
    QdrantSemanticClassificationClient,
    SemanticClassificationRequestStruct,
    SemanticType,
)
from aigc.core.lexicon.lexicon import rebuild_lexicon_collection


async def test_qdrant_semantic_classification_client_classifies_by_sparse_lexicon(tmp_path: Path) -> None:
    samples_file = tmp_path / "lexicon_samples.jsonl"
    samples_file.write_text(
        '{"id":"persona_praise_000001","semantic_type":"persona_praise","text":"主播今天状态太好了","description":"praise"}\n'
        '{"id":"playful_joke_000001","semantic_type":"playful_joke","text":"这波操作笑死我了","description":"joke"}\n',
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
        SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了", "团队也太强了"])
    )
    await qdrant_client.close()

    assert result.semantic_type is SemanticType.PERSONA_PRAISE
    assert result.confidence > 0
    assert result.candidates[0].semantic_type is SemanticType.PERSONA_PRAISE


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
        SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了"])
    )
    await qdrant_client.close()

    assert result.semantic_type is SemanticType.OTHER
    assert result.confidence == 0
    assert result.candidates == []
