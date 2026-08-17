"""gRPC transport for lexicon semantic classification."""

from typing import TYPE_CHECKING, Any, cast, override

import grpc  # type: ignore[import-untyped]

from .classification import (
    SemanticClassificationCandidateStruct,
    SemanticClassificationClient,
    SemanticClassificationCommentStruct,
    SemanticClassificationRequestStruct,
    SemanticClassificationResultStruct,
)
from .enum import SemanticType
from .proto import semantic_classification_pb2, semantic_classification_pb2_grpc

if TYPE_CHECKING:
    from grpc import aio

__all__ = (
    "GrpcSemanticClassificationClient",
    "SemanticClassificationGrpcService",
    "create_live_classification_grpc_server",
)


_SEMANTIC_TYPE_TO_PROTO: dict[SemanticType, int] = {
    SemanticType.PLAYFUL_JOKE: cast("int", cast("Any", semantic_classification_pb2).SEMANTIC_TYPE_PLAYFUL_JOKE),
    SemanticType.PERSONA_PRAISE: cast("int", cast("Any", semantic_classification_pb2).SEMANTIC_TYPE_PERSONA_PRAISE),
    SemanticType.INTERACTIVE_PROMPT: cast("int", cast("Any", semantic_classification_pb2).SEMANTIC_TYPE_INTERACTIVE_PROMPT),
    SemanticType.ATMOSPHERE_BOOST: cast("int", cast("Any", semantic_classification_pb2).SEMANTIC_TYPE_ATMOSPHERE_BOOST),
    SemanticType.OTHER: cast("int", cast("Any", semantic_classification_pb2).SEMANTIC_TYPE_OTHER),
}
_PROTO_TO_SEMANTIC_TYPE: dict[int, SemanticType] = {
    proto_value: semantic_type for semantic_type, proto_value in _SEMANTIC_TYPE_TO_PROTO.items()
}


class GrpcSemanticClassificationClient:
    """Semantic classification client backed by a gRPC service."""

    def __init__(self, target: str, *, timeout: float = 1.0) -> None:
        self._target = target
        self._timeout = timeout

    async def classify(self, request: SemanticClassificationRequestStruct) -> SemanticClassificationResultStruct:
        """Classify a comment window through the remote gRPC service."""

        try:
            async with grpc.aio.insecure_channel(self._target) as channel:
                stub = cast("Any", semantic_classification_pb2_grpc.SemanticClassificationStub)(channel)
                response = await stub.Classify(_request_to_proto(request), timeout=self._timeout)
        except Exception:  # noqa: BLE001
            return SemanticClassificationResultStruct.other(top_n=request.top_n)

        return _result_from_proto(response)


class SemanticClassificationGrpcService(semantic_classification_pb2_grpc.SemanticClassificationServicer):
    """gRPC service adapter for a semantic classification client."""

    def __init__(self, classification_client: SemanticClassificationClient) -> None:
        self._classification_client = classification_client

    @override
    async def Classify(
        self,
        request: Any,
        context: "grpc.aio.ServicerContext[Any, Any]",
    ) -> Any:
        """Classify a decoded gRPC request."""

        try:
            result = await self._classification_client.classify(_request_from_proto(request))
        except Exception as exc:
            await context.abort(grpc.StatusCode.INTERNAL, str(exc))
            raise RuntimeError("unreachable") from exc

        return _result_to_proto(result)


def create_live_classification_grpc_server(
    classification_client: SemanticClassificationClient,
) -> "aio.Server":
    """Create a gRPC server for live semantic classification."""

    server = grpc.aio.server()
    semantic_classification_pb2_grpc.add_SemanticClassificationServicer_to_server(  # type: ignore[no-untyped-call]
        SemanticClassificationGrpcService(classification_client),
        server,
    )
    return server


def _request_to_proto(
    request: SemanticClassificationRequestStruct,
) -> Any:
    proto = cast("Any", semantic_classification_pb2)
    return proto.SemanticClassificationRequest(
        room_id=request.room_id,
        text_batch=request.text_batch,
        top_n=request.top_n,
        comment_batch=[
            proto.SemanticClassificationComment(
                comment_id=comment.comment_id,
                text=comment.text,
            )
            for comment in request.comment_batch
        ],
    )


def _request_from_proto(
    request: Any,
) -> SemanticClassificationRequestStruct:
    return SemanticClassificationRequestStruct(
        room_id=request.room_id,
        text_batch=list(request.text_batch),
        top_n=request.top_n,
        comment_batch=[
            SemanticClassificationCommentStruct(
                comment_id=comment.comment_id,
                text=comment.text,
            )
            for comment in request.comment_batch
        ],
    )


def _result_to_proto(
    result: SemanticClassificationResultStruct,
) -> Any:
    proto = cast("Any", semantic_classification_pb2)
    return proto.SemanticClassificationResult(
        semantic_type=_SEMANTIC_TYPE_TO_PROTO[result.semantic_type],
        confidence=result.confidence,
        top_n=result.top_n,
        candidates=[
            proto.SemanticClassificationCandidate(
                semantic_type=_SEMANTIC_TYPE_TO_PROTO[candidate.semantic_type],
                score=candidate.score,
                comment_id=candidate.comment_id,
                text=candidate.text,
                confidence=candidate.confidence,
            )
            for candidate in result.candidates
        ],
    )


def _result_from_proto(
    result: Any,
) -> SemanticClassificationResultStruct:
    return SemanticClassificationResultStruct(
        semantic_type=_semantic_type_from_proto(result.semantic_type),
        confidence=result.confidence,
        top_n=result.top_n,
        candidates=[
            SemanticClassificationCandidateStruct(
                semantic_type=_semantic_type_from_proto(candidate.semantic_type),
                score=candidate.score,
                comment_id=candidate.comment_id,
                text=candidate.text,
                confidence=candidate.confidence,
            )
            for candidate in result.candidates
        ],
    )


def _semantic_type_from_proto(value: int) -> SemanticType:
    return _PROTO_TO_SEMANTIC_TYPE.get(value, SemanticType.OTHER)
