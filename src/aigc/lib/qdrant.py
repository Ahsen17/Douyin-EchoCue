from typing import TYPE_CHECKING, Literal, overload

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    SparseVectorParams,
    VectorParams,
)

if TYPE_CHECKING:
    from aigc.base import QdrantConfig


__all__ = (
    "QdrantClientFactory",
    "QdrantCollectionCreator",
)


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


class QdrantCollectionCreator:
    """Creator for managing AsyncQdrantClient instances."""

    def __init__(self, client: AsyncQdrantClient) -> None:

        self._client = client

    @overload
    async def create(
        self,
        collection_name: str,
        *,
        vector_type: Literal["default"] = "default",
    ) -> bool: ...

    @overload
    async def create(
        self,
        collection_name: str,
        *,
        vector_type: Literal["sparse"] = "sparse",
    ) -> bool: ...

    @overload
    async def create(
        self,
        collection_name: str,
        *,
        vector_type: Literal["hybrid"] = "hybrid",
        dense_size: int,
    ) -> bool: ...

    @overload
    async def create(
        self,
        collection_name: str,
        *,
        vector_type: Literal["multi"] = "multi",
        dense_size: int,
        mrl_dense_size: int,
        sparse: bool | None = None,
    ) -> bool: ...

    async def create(
        self,
        collection_name: str,
        *,
        vector_type: Literal["default", "sparse", "hybrid", "multi"] = "default",
        dense_size: int | None = None,
        mrl_dense_size: int | None = None,
        sparse: bool | None = None,
    ) -> bool:

        config_cache = {
            "dense": VectorParams(
                size=dense_size,  # type: ignore
                distance=Distance.COSINE,
                on_disk=True,
            ),
            "dense_mrl": VectorParams(
                size=mrl_dense_size,  # type: ignore
                distance=Distance.COSINE,
                quantization_config=ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        quantile=0.99,
                    )
                ),
                on_disk=True,
            ),
            "sparse": SparseVectorParams(modifier=Modifier.IDF),
        }

        match vector_type:
            case "default":
                if dense_size is None:
                    raise ValueError("dense_size must be specified for dense collections")

                return await self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=config_cache["dense"],
                )

            case "sparse":
                return await self._client.create_collection(
                    collection_name=collection_name,
                    sparse_vectors_config={"sparse": config_cache["sparse"]},
                )

            case "hybrid":
                if dense_size is None:
                    raise ValueError("dense_size must be specified for hybrid collections")

                return await self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=config_cache["dense"],
                    sparse_vectors_config={"sparse": config_cache["sparse"]},
                )

            case "multi":
                if not all((dense_size, mrl_dense_size, sparse is not None)):
                    raise ValueError(
                        "dense_size, mrl_dense_size, and sparse must be specified for multi collections",
                    )

                if mrl_dense_size >= dense_size:
                    raise ValueError("`mrl_dense_size` illegal.")

                return await self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "dense_full": config_cache["dense"],
                        "dense_mrl": config_cache["dense_mrl"],
                    },
                    sparse_vectors_config={"sparse": config_cache["sparse"]} if sparse else None,
                )
