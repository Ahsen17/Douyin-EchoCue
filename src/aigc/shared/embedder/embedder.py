from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Literal

from openai import AsyncOpenAI

from aigc.lib import Bm25Chinese

from .vector import DenseVector, SparseVector

if TYPE_CHECKING:
    from aigc.base import EmbeddingConfig


__all__ = (
    "Bm25SparseEmbedder",
    "OpenAIDenseEmbedder",
)


class OpenAIDenseEmbedder:
    """OpenAI-compatible dense embedder."""

    def __init__(self, config: "EmbeddingConfig") -> None:

        self._config = config

    @property
    def aclient(self) -> "AsyncOpenAI":

        return AsyncOpenAI(
            base_url=self._config.base_url,
            api_key=self._config.api_key,
            timeout=self._config.timeout,
            max_retries=self._config.max_retries or 1,
        )

    async def aembed(
        self,
        content: str | list[str],
        *,
        dimensions: int = 2048,
        chunk_size: int = 32,
        encoding_format: Literal["base64", "float"] = "float",
    ) -> list[DenseVector]:
        """Asynchronously embeds the given content into a vector space."""

        content = [content] if isinstance(content, str) else content

        if not content:
            return []

        async def _aembed_generator(
            documents: str | list[str],
            chunk_size: int,
        ) -> AsyncGenerator[list[DenseVector], None]:
            for i in range(0, len(documents), chunk_size):
                response = await self.aclient.embeddings.create(
                    input=documents[i : i + chunk_size],
                    model=self._config.model,
                    dimensions=dimensions,
                    encoding_format=encoding_format,
                )
                yield [
                    DenseVector(
                        index=embeddings.index,
                        values=embeddings.embedding,
                    )
                    for embeddings in response.data
                ]

        embeddings: list[DenseVector] = []

        async for chunk in _aembed_generator(content, chunk_size):
            embeddings.extend(chunk)

        return embeddings


class Bm25SparseEmbedder:
    """Bm25 sparse embedder."""

    def __init__(self, avg_len: float) -> None:

        self._bm25 = Bm25Chinese(model_name="", avg_len=avg_len)

    def embed(self, content: str | list[str]) -> list[SparseVector]:
        """Embed documents into sparse vectors."""

        return [
            SparseVector(
                indices=embedding.indices,
                values=embedding.values,
            )
            for embedding in self._bm25.embed(documents=content)
        ]

    def query_embed(self, query: str | list[str]) -> list[SparseVector]:
        """Embed queries into sparse vectors with binary weighting."""

        return [
            SparseVector(
                index=embedding.index,
                values=embedding.values,
            )
            for embedding in self._bm25.query_embed(query=query)
        ]
