from typing import TYPE_CHECKING

from qdrant_client import AsyncQdrantClient

if TYPE_CHECKING:
    from aigc.base import QdrantConfig


class QdrantClientFactory:
    """Factory for creating AsyncQdrantClient instances."""

    def __init__(self, config: "QdrantConfig") -> None:
        self._config = config
        self._client: AsyncQdrantClient | None = None

    def new(self) -> "AsyncQdrantClient":
        if self._client is None:
            self._client = AsyncQdrantClient(
                check_compatibility=False,
                **self._config.to_dict(),
            )

        return self._client
