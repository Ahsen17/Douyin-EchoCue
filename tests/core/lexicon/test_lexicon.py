from pathlib import Path
from uuid import UUID

import pytest
from qdrant_client import AsyncQdrantClient

from echocue.core.lexicon import SemanticType
from echocue.core.lexicon.lexicon import load_lexicon_samples, rebuild_lexicon_collection


class TestLexiconCollection:
    sample_lines: str

    @pytest.fixture(autouse=True)
    def set_up(self) -> None:
        self.sample_lines = (
            '{"id":"persona_praise_000001","semantic_type":"persona_praise","text":"主播今天状态太好了","description":"praise"}\n'
            '{"id":"interactive_prompt_000001","semantic_type":"interactive_prompt","text":"主播能聊聊这个吗","description":"prompt"}\n'
        )

    def test_load_samples_decodes_jsonl(self, tmp_path: Path) -> None:
        samples_file = tmp_path / "lexicon_samples.jsonl"
        samples_file.write_text(self.sample_lines, encoding="utf-8")

        samples = load_lexicon_samples(samples_file)

        assert [sample.semantic_type for sample in samples] == [
            SemanticType.PERSONA_PRAISE,
            SemanticType.INTERACTIVE_PROMPT,
        ]
        assert [sample.text for sample in samples] == ["主播今天状态太好了", "主播能聊聊这个吗"]

    def test_project_samples_cover_interaction_semantic_types(self) -> None:
        samples = load_lexicon_samples(Path("assets/live/lexicon_samples.jsonl"))

        assert {sample.semantic_type for sample in samples} == {
            SemanticType.PLAYFUL_JOKE,
            SemanticType.PERSONA_PRAISE,
            SemanticType.INTERACTIVE_PROMPT,
            SemanticType.ATMOSPHERE_BOOST,
            SemanticType.OTHER,
        }
        assert all(sample.id for sample in samples)
        assert all(sample.text for sample in samples)

    async def test_rebuild_collection_recreates_sparse_collection(self, tmp_path: Path) -> None:
        samples_file = tmp_path / "lexicon_samples.jsonl"
        samples_file.write_text(self.sample_lines, encoding="utf-8")
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
            "persona_praise_000001",
            "interactive_prompt_000001",
        ]
        assert [point.payload["semantic_type"] for point in points if point.payload is not None] == [
            "persona_praise",
            "interactive_prompt",
        ]
