from datetime import UTC, datetime
from typing import Any, Self

import pytest

from aigc.core.lexicon import (
    FakeSemanticClassificationClient,
    GrpcSemanticClassificationClient,
    SemanticClassificationRequestStruct,
    SemanticType,
)
from aigc.core.lexicon.rpc import create_live_classification_grpc_server
from aigc.core.live import CommentPayloadStruct, CommentWindowHandler, LiveCommentEventStruct


class TestSemanticClassificationGrpc:
    classification_client: FakeSemanticClassificationClient

    @pytest.fixture(autouse=True)
    def set_up(self) -> None:
        self.classification_client = FakeSemanticClassificationClient()

    def patch_fake_channel(self, mocker: Any, *, assert_method: bool = False) -> None:
        classification_client = self.classification_client

        class FakeUnaryUnaryCall:
            def __init__(self, request_serializer: Any, response_deserializer: Any) -> None:
                self._request_serializer = request_serializer
                self._response_deserializer = response_deserializer

            async def __call__(self, request: SemanticClassificationRequestStruct, *, timeout: float) -> Any:
                decoded_request = SemanticClassificationRequestStruct.from_json(
                    self._request_serializer(request).decode(),
                )
                result = await classification_client.classify(decoded_request)
                return self._response_deserializer(result.to_jsonb())

        class FakeChannel:
            async def __aenter__(self) -> Self:
                return self

            async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
                return None

            def unary_unary(
                self, method: str, *, request_serializer: Any, response_deserializer: Any
            ) -> FakeUnaryUnaryCall:
                if assert_method:
                    assert method == "/aigc.lexicon.SemanticClassification/Classify"

                return FakeUnaryUnaryCall(request_serializer, response_deserializer)

        mocker.patch("aigc.core.lexicon.rpc.grpc.aio.insecure_channel", return_value=FakeChannel())

    async def test_client_classifies_through_channel(self, mocker: Any) -> None:
        self.patch_fake_channel(mocker, assert_method=True)
        client = GrpcSemanticClassificationClient("127.0.0.1:50051")

        result = await client.classify(
            SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了", "团队也太强了"])
        )

        assert result.semantic_type is SemanticType.PERSONA_PRAISE
        assert result.confidence > 0
        assert result.candidates[0].semantic_type is SemanticType.PERSONA_PRAISE

    async def test_comment_window_handler_uses_injected_client(self, mocker: Any) -> None:
        self.patch_fake_channel(mocker)
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
            SemanticClassificationRequestStruct(room_id="room-a", text_batch=["主播今天状态太好了"])
        )

        assert result.semantic_type is SemanticType.OTHER
        assert result.confidence == 0
        assert result.candidates == []

    async def test_create_server_returns_server(self) -> None:
        server = create_live_classification_grpc_server(self.classification_client)

        assert server is not None
        await server.stop(grace=0)
