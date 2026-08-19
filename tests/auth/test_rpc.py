from types import TracebackType
from typing import Any, Self, cast
from uuid import uuid4

import pytest

from echocue.auth import (
    AuthenticationResultStruct,
    AuthPermissionHandler,
    GrpcAuthPermissionClient,
    LoginRequest,
    PermissionAction,
    PermissionCheckRequestStruct,
    PermissionCheckResultStruct,
    PermissionContextStruct,
    RoomAuthorizationScope,
    UserStruct,
)
from echocue.auth.proto import auth_service_pb2, auth_service_pb2_grpc
from echocue.auth.rpc import AuthGrpcService, create_auth_grpc_server


class FakeGrpcContext:
    async def abort(self, code: Any, details: str) -> None:
        raise RuntimeError(details)


class FakeAuthHandler(AuthPermissionHandler):
    user_id = uuid4()

    async def authenticate(self, request: Any) -> AuthenticationResultStruct:
        user = UserStruct(
            id=self.user_id,
            username=request.username,
            email="user@example.test",
            is_active=True,
            is_superuser=False,
        )
        context = PermissionContextStruct(user=user)

        return AuthenticationResultStruct(user=user, context=context)

    async def get_permission_context(self, user_id: Any) -> PermissionContextStruct:
        assert user_id == self.user_id

        return PermissionContextStruct(
            user=UserStruct(
                id=self.user_id,
                username="member",
                email="user@example.test",
                is_active=True,
                is_superuser=False,
            )
        )

    async def check_permission(self, request: PermissionCheckRequestStruct) -> PermissionCheckResultStruct:
        assert request.user_id == self.user_id
        assert request.room_id == "room-a"
        assert request.action is PermissionAction.START

        return PermissionCheckResultStruct(
            allowed=True,
            reason="Authorization grant allows starting the organization room assistant.",
            matched_scope=RoomAuthorizationScope.START,
        )


class FailingAuthHandler(AuthPermissionHandler):
    async def authenticate(self, request: Any) -> AuthenticationResultStruct:
        raise RuntimeError("postgresql://user:password@db/internal")


class FakeUnaryUnaryCall:
    def __init__(
        self, request_serializer: Any, response_deserializer: Any, method: str, service: AuthGrpcService
    ) -> None:
        self._request_serializer = request_serializer
        self._response_deserializer = response_deserializer
        self._method = method
        self._service = service

    async def __call__(
        self,
        request: Any,
        *,
        timeout: float | None = None,
    ) -> Any:
        proto = cast("Any", auth_service_pb2)
        decoded_request: Any
        encoded_result: Any
        if self._method == "/echocue.auth.AuthService/Authenticate":
            decoded_request = proto.AuthenticateRequest.FromString(self._request_serializer(request))
            encoded_result = await self._service.Authenticate(decoded_request, FakeGrpcContext())
        elif self._method == "/echocue.auth.AuthService/GetPermissionContext":
            decoded_request = proto.PermissionContextRequest.FromString(self._request_serializer(request))
            encoded_result = await self._service.GetPermissionContext(decoded_request, FakeGrpcContext())
        elif self._method == "/echocue.auth.AuthService/CheckPermission":
            decoded_request = proto.PermissionCheckRequest.FromString(self._request_serializer(request))
            encoded_result = await self._service.CheckPermission(decoded_request, FakeGrpcContext())
        else:
            msg = f"Unexpected method: {self._method}"
            raise AssertionError(msg)

        return self._response_deserializer(encoded_result.SerializeToString())


class FakeChannel:
    def __init__(self, service: AuthGrpcService) -> None:
        self._service = service

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def unary_unary(
        self,
        method: str,
        *,
        request_serializer: Any,
        response_deserializer: Any,
        **kwargs: Any,
    ) -> FakeUnaryUnaryCall:
        return FakeUnaryUnaryCall(request_serializer, response_deserializer, method, self._service)


class TestAuthGrpc:
    async def test_client_authenticates_through_generated_stub(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = AuthGrpcService(FakeAuthHandler())
        monkeypatch.setattr("echocue.auth.rpc.grpc.aio.insecure_channel", lambda target: FakeChannel(service))
        client = GrpcAuthPermissionClient("auth:50052", timeout=2.5)

        response = await client.authenticate(
            LoginRequest(
                username="member",
                password="member-password",
            )
        )

        assert response.user.username == "member"
        assert response.context.user.id == response.user.id

    async def test_client_gets_permission_context_through_generated_stub(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        handler = FakeAuthHandler()
        service = AuthGrpcService(handler)
        monkeypatch.setattr("echocue.auth.rpc.grpc.aio.insecure_channel", lambda target: FakeChannel(service))
        client = GrpcAuthPermissionClient("auth:50052")

        response = await client.get_permission_context(handler.user_id)

        assert response.user.id == handler.user_id
        assert response.user.email == "user@example.test"

    async def test_client_checks_permission_through_generated_stub(self, monkeypatch: pytest.MonkeyPatch) -> None:
        handler = FakeAuthHandler()
        service = AuthGrpcService(handler)
        monkeypatch.setattr("echocue.auth.rpc.grpc.aio.insecure_channel", lambda target: FakeChannel(service))
        client = GrpcAuthPermissionClient("auth:50052")

        response = await client.check_permission(
            PermissionCheckRequestStruct(
                user_id=handler.user_id,
                room_id="room-a",
                action=PermissionAction.START,
            )
        )

        assert response.allowed is True
        assert response.matched_scope is RoomAuthorizationScope.START

    async def test_generated_stub_authenticates_through_service_adapter(self) -> None:
        proto = cast("Any", auth_service_pb2)
        grpc_proto = cast("Any", auth_service_pb2_grpc)
        service = AuthGrpcService(FakeAuthHandler())
        stub = grpc_proto.AuthServiceStub(FakeChannel(service))

        response = await stub.Authenticate(
            proto.AuthenticateRequest(username="member", password="member-password"),
            timeout=1.0,
        )

        assert response.user.username == "member"
        assert response.user.email == "user@example.test"
        assert response.context.user.id == response.user.id
        assert response.context.certification.status == proto.CERTIFICATION_STATUS_UNSPECIFIED

    async def test_service_adapter_hides_internal_error_details(self) -> None:
        proto = cast("Any", auth_service_pb2)
        service = AuthGrpcService(FailingAuthHandler())

        with pytest.raises(RuntimeError, match="Auth service internal error") as exc_info:
            await service.Authenticate(
                proto.AuthenticateRequest(username="member", password="member-password"),
                FakeGrpcContext(),
            )

        assert "postgresql://" not in str(exc_info.value)

    async def test_generated_stub_checks_permission_through_service_adapter(self) -> None:
        proto = cast("Any", auth_service_pb2)
        grpc_proto = cast("Any", auth_service_pb2_grpc)
        handler = FakeAuthHandler()
        service = AuthGrpcService(handler)
        stub = grpc_proto.AuthServiceStub(FakeChannel(service))

        response = await stub.CheckPermission(
            proto.PermissionCheckRequest(
                user_id=str(handler.user_id),
                room_id="room-a",
                action=proto.PERMISSION_ACTION_START,
            ),
            timeout=1.0,
        )

        assert response.allowed is True
        assert response.matched_scope == proto.ROOM_AUTHORIZATION_SCOPE_START

    async def test_create_server_returns_generated_grpc_server(self) -> None:
        server = create_auth_grpc_server(FakeAuthHandler())

        assert server is not None
        await server.stop(grace=0)
