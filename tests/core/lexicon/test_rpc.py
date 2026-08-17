from datetime import UTC, datetime
from typing import Any, Self, cast

import pytest

from echocue.core.lexicon import (
    FakeSemanticClassificationClient,
    GrpcSemanticClassificationClient,
    SemanticClassificationCommentStruct,
    SemanticClassificationRequestStruct,
    SemanticType,
)
from echocue.core.lexicon.proto import semantic_classification_pb2
from echocue.core.lexicon.rpc import SemanticClassificationGrpcService, create_live_classification_grpc_server
from echocue.core.live import CommentPayloadStruct, CommentWindowHandler, LiveCommentEventStruct


class FakeGrpcContext:
    async def abort(self, code: object, details: str) -> None:
        raise RuntimeError(details)


class TestSemanticClassificationGrpc:
    classification_client: FakeSemanticClassificationClient

    @pytest.fixture(autouse=True)
    def set_up(self) -> None:
        self.classification_client = FakeSemanticClassificationClient()

    def patch_generated_stub_channel(self, mocker: Any, *, assert_method: bool = False) -> None:
        classification_client = self.classification_client

        class FakeUnaryUnaryCall:
            def __init__(self, request_serializer: Any, response_deserializer: Any) -> None:
                self._request_serializer = request_serializer
                self._response_deserializer = response_deserializer

            async def __call__(
                self,
                request: Any,
                *,
                timeout: float,
            ) -> Any:
                proto = cast("Any", semantic_classification_pb2)
                decoded_request = proto.SemanticClassificationRequest.FromString(
                    self._request_serializer(request),
                )
                service = SemanticClassificationGrpcService(classification_client)
                encoded_result = await service.Classify(decoded_request, FakeGrpcContext())
                return self._response_deserializer(encoded_result.SerializeToString())

        class FakeChannel:
            async def __aenter__(self) -> Self:
                return self

            async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
                return None

            def unary_unary(
                self,
                method: str,
                *,
                request_serializer: Any,
                response_deserializer: Any,
                **kwargs: Any,
            ) -> FakeUnaryUnaryCall:
                if assert_method:
                    assert method == "/echocue.lexicon.SemanticClassification/Classify"

                return FakeUnaryUnaryCall(request_serializer, response_deserializer)

        mocker.patch("echocue.core.lexicon.rpc.grpc.aio.insecure_channel", return_value=FakeChannel())

    async def test_client_classifies_through_generated_stub(self, mocker: Any) -> None:
        self.patch_generated_stub_channel(mocker, assert_method=True)
        client = GrpcSemanticClassificationClient("127.0.0.1:50051")

        result = await client.classify(
            SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了", "团队也太强了"])
        )

        assert result.semantic_type is SemanticType.PERSONA_PRAISE
        assert result.confidence > 0
        assert result.candidates[0].semantic_type is SemanticType.PERSONA_PRAISE

    async def test_client_preserves_comment_candidates_through_proto(self, mocker: Any) -> None:
        self.patch_generated_stub_channel(mocker)
        client = GrpcSemanticClassificationClient("127.0.0.1:50051")

        result = await client.classify(
            SemanticClassificationRequestStruct(
                room_id="room-a",
                text_batch=["主播今天状态太好了", "笑死这个反差太有梗了"],
                top_n=2,
                comment_batch=[
                    SemanticClassificationCommentStruct(comment_id="comment-1", text="主播今天状态太好了"),
                    SemanticClassificationCommentStruct(comment_id="comment-2", text="笑死这个反差太有梗了"),
                ],
            )
        )

        assert result.top_n == 2
        assert {candidate.comment_id for candidate in result.candidates} == {"comment-1", "comment-2"}
        assert {candidate.semantic_type for candidate in result.candidates} == {
            SemanticType.PERSONA_PRAISE,
            SemanticType.PLAYFUL_JOKE,
        }

    async def test_comment_window_handler_uses_injected_client(self, mocker: Any) -> None:
        self.patch_generated_stub_channel(mocker)
        handler = CommentWindowHandler(classification_client=GrpcSemanticClassificationClient("127.0.0.1:50051"))

        window = await handler.ingest_comment(
            LiveCommentEventStruct(
                event_id="event-1",
                platform="douyin_mock",
                event_type="comment",
                room_id="room-a",
                user_id="user-a",
                occurred_at=datetime(2026, 8, 15, 12, 0, tzinfo=UTC),
                payload=CommentPayloadStruct(
                    comment_id="comment-1",
                    content="主播今天状态太好了",
                    nickname="nick-a",
                ),
            )
        )

        assert window.semantic_type is SemanticType.PERSONA_PRAISE

    async def test_client_returns_other_when_service_is_unavailable(self) -> None:
        client = GrpcSemanticClassificationClient("127.0.0.1:1", timeout=0.1)

        result = await client.classify(
            SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了"], top_n=3)
        )

        assert result.semantic_type is SemanticType.OTHER
        assert result.confidence == 0
        assert result.top_n == 3
        assert result.candidates == []

    async def test_create_server_returns_generated_grpc_server(self) -> None:
        server = create_live_classification_grpc_server(self.classification_client)

        assert server is not None
        await server.stop(grace=0)
