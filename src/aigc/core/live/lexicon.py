"""Lexicon rebuilding for live comment classification."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from msgspec import DecodeError, ValidationError, json
from qdrant_client.models import Modifier, PointStruct, SparseVector, SparseVectorParams
from uuid_utils.compat import uuid7

from aigc.base import BaseStruct
from aigc.shared.embedder import Bm25SparseEmbedder

from .enum import SemanticType

__all__ = (
    "LexiconRebuildResultStruct",
    "LexiconSampleStruct",
    "SemanticQdrantClient",
)


DEFAULT_LEXICON_COLLECTION_NAME = "live_lexicon"


class LexiconSampleStruct(BaseStruct):
    """Single lexicon seed sample."""

    id: str
    semantic_type: SemanticType
    text: str
    description: str = ""


class LexiconRebuildResultStruct(BaseStruct):
    """Result returned after rebuilding the lexicon collection."""

    collection_name: str
    sample_count: int


class SemanticQdrantClient(Protocol):
    """Qdrant operations required by lexicon rebuilding."""

    async def collection_exists(self, collection_name: str, **kwargs: object) -> bool:
        """Return whether a collection exists."""

    async def delete_collection(self, collection_name: str, **kwargs: object) -> bool:
        """Delete an existing collection."""

    async def create_collection(
        self,
        collection_name: str,
        sparse_vectors_config: Mapping[str, SparseVectorParams] | None = None,
        **kwargs: object,
    ) -> bool:
        """Create a collection."""

    async def upsert(self, collection_name: str, points: Sequence[PointStruct], **kwargs: object) -> object:
        """Upsert points into a collection."""


def load_lexicon_samples(samples_file: Path) -> list[LexiconSampleStruct]:
    """Load lexicon samples from a JSONL file."""

    samples: list[LexiconSampleStruct] = []
    for line_number, line in enumerate(samples_file.read_text(encoding="utf-8").splitlines(), start=1):
        content = line.strip()
        if not content:
            continue

        try:
            samples.append(json.decode(content.encode(), type=LexiconSampleStruct))
        except (DecodeError, ValidationError) as exc:
            msg = f"Invalid lexicon sample at {samples_file}:{line_number}"
            raise ValueError(msg) from exc

    return samples


async def rebuild_lexicon_collection(
    client: SemanticQdrantClient,
    *,
    samples_file: Path,
    collection_name: str = DEFAULT_LEXICON_COLLECTION_NAME,
    embedder: Bm25SparseEmbedder | None = None,
) -> LexiconRebuildResultStruct:
    """Rebuild the Qdrant sparse collection from lexicon sample JSONL."""

    samples = load_lexicon_samples(samples_file)
    embedder = embedder or Bm25SparseEmbedder(avg_len=_average_text_length(samples))
    vectors = embedder.embed([sample.text for sample in samples])
    points = [
        _sample_to_point(sample, vector, index)
        for index, (sample, vector) in enumerate(zip(samples, vectors, strict=True))
    ]

    if await client.collection_exists(collection_name):
        await client.delete_collection(collection_name=collection_name)

    await client.create_collection(
        collection_name=collection_name,
        sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
    )
    if points:
        await client.upsert(collection_name=collection_name, points=points, wait=True)

    return LexiconRebuildResultStruct(collection_name=collection_name, sample_count=len(samples))


def _sample_to_point(sample: LexiconSampleStruct, vector: SparseVector, index: int) -> PointStruct:
    return PointStruct(
        id=uuid7(),
        vector={"sparse": vector},
        payload={
            "sample_id": sample.id,
            "semantic_type": sample.semantic_type.value,
            "text": sample.text,
            "description": sample.description,
        },
    )


def _average_text_length(samples: list[LexiconSampleStruct]) -> float:
    if not samples:
        return 1

    return max(sum(len(sample.text) for sample in samples) / len(samples), 1)
