from typing import Any

from aigc.base.schema import BaseStruct

__all__ = ("QdrantConfig",)


class QdrantConfig(BaseStruct):
    """Configuration for Qdrant vector database."""

    host: str = "localhost"
    location: str | None = None
    path: str | None = None
    url: str | None = None

    port: int = 6333
    grpc_port: int = 6334
    prefer_grpc: bool = False

    https: bool | None = None
    api_key: str | None = None
    prefix: str | None = None
    timeout: int | None = None
    grpc_options: dict[str, Any] | None = None
    pool_size: int | None = None
    headers: dict[str, str] | None = None
