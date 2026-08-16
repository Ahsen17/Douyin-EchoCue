"""gRPC transport for live semantic classification."""

from typing import TYPE_CHECKING, cast

import grpc  # type: ignore[import-untyped]
from msgspec import DecodeError, ValidationError, json

from .classification import (
    SemanticClassificationClient,
    SemanticClassificationRequestStruct,
    SemanticClassificationResultStruct,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from grpc import aio

__all__ = (
    "GrpcSemanticClassificationClient",
    "SemanticClassificationGrpcService",
)


LIVE_CLASSIFICATION_GRPC_SERVICE = "aigc.live.SemanticClassification"
LIVE_CLASSIFICATION_GRPC_METHOD = f"/{LIVE_CLASSIFICATION_GRPC_SERVICE}/Classify"


class GrpcSemanticClassificationClient:
    """Semantic classification client backed by a gRPC service."""

    def __init__(self, target: str, *, timeout: float = 1.0) -> None:
        self._target = target
        self._timeout = timeout

    async def classify(self, request: SemanticClassificationRequestStruct) -> SemanticClassificationResultStruct:
        """Classify a comment window through the remote gRPC service."""

        try:
            async with grpc.aio.insecure_channel(self._target) as channel:
                classify = channel.unary_unary(
                    LIVE_CLASSIFICATION_GRPC_METHOD,
                    request_serializer=_serialize_classification_request,
                    response_deserializer=_deserialize_classification_result,
                )
                return cast("SemanticClassificationResultStruct", await classify(request, timeout=self._timeout))
        except Exception:  # noqa: BLE001
            return SemanticClassificationResultStruct.other()


class SemanticClassificationGrpcService:
    """gRPC service adapter for a semantic classification client."""

    def __init__(self, classification_client: SemanticClassificationClient) -> None:
        self._classification_client = classification_client

    async def classify(
        self,
        request: SemanticClassificationRequestStruct,
        context: "grpc.aio.ServicerContext[bytes, bytes]",
    ) -> SemanticClassificationResultStruct:
        """Classify a decoded gRPC request."""

        try:
            return await self._classification_client.classify(request)
        except Exception as exc:
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))
            raise RuntimeError("unreachable") from exc


def create_live_classification_grpc_server(
    classification_client: SemanticClassificationClient,
) -> "aio.Server":
    """Create a gRPC server for live semantic classification."""

    server = grpc.aio.server()
    service = SemanticClassificationGrpcService(classification_client)
    handler = grpc.unary_unary_rpc_method_handler(
        _wrap_rpc_method(service.classify),
        request_deserializer=_deserialize_classification_request,
        response_serializer=_serialize_classification_result,
    )
    generic_handler = grpc.method_handlers_generic_handler(
        LIVE_CLASSIFICATION_GRPC_SERVICE,
        {"Classify": handler},
    )
    server.add_generic_rpc_handlers((generic_handler,))
    return server


def _wrap_rpc_method(
    method: "Callable[[SemanticClassificationRequestStruct, grpc.aio.ServicerContext[bytes, bytes]], Awaitable[SemanticClassificationResultStruct]]",
) -> "Callable[[SemanticClassificationRequestStruct, grpc.aio.ServicerContext[bytes, bytes]], Awaitable[SemanticClassificationResultStruct]]":
    return method


def _serialize_classification_request(request: SemanticClassificationRequestStruct) -> bytes:
    return request.to_jsonb()


def _deserialize_classification_request(data: bytes) -> SemanticClassificationRequestStruct:
    try:
        return json.decode(data, type=SemanticClassificationRequestStruct)
    except (DecodeError, ValidationError) as exc:
        msg = "Invalid semantic classification request"
        raise ValueError(msg) from exc


def _serialize_classification_result(result: SemanticClassificationResultStruct) -> bytes:
    return result.to_jsonb()


def _deserialize_classification_result(data: bytes) -> SemanticClassificationResultStruct:
    try:
        return json.decode(data, type=SemanticClassificationResultStruct)
    except (DecodeError, ValidationError) as exc:
        msg = "Invalid semantic classification result"
        raise ValueError(msg) from exc
