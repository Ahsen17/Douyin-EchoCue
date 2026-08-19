from typing import Any, cast
from uuid import uuid4

import pytest
from litestar.exceptions import HTTPException
from pytest import MonkeyPatch

from echocue.auth import (
    AuthenticationResultStruct,
    LoginRequest,
    PermissionAction,
    PermissionCheckRequestStruct,
    PermissionCheckResultStruct,
    PermissionContextStruct,
    RoomAuthorizationScope,
    RoomStruct,
    UserStruct,
)
from echocue.controller.auth import AuthController
from echocue.shared.context import RequestContext


class FakeSessionRequest:
    session: dict[str, str]

    def __init__(self, session: dict[str, str] | None = None) -> None:
        self.session = session or {}

    def set_session(self, session: dict[str, str]) -> None:
        self.session = session

    def clear_session(self) -> None:
        self.session = {}


class FakeAuthPermissionClient:
    user = UserStruct(id=uuid4(), username="grpc-user", email=None, is_active=True, is_superuser=False)

    async def authenticate(self, request: LoginRequest) -> AuthenticationResultStruct:
        assert request.username == "grpc-user"

        context = PermissionContextStruct(
            user=self.user,
            rooms=[RoomStruct(room_id="room-a", owner_user_id=self.user.id)],
        )
        return AuthenticationResultStruct(user=self.user, context=context)

    async def get_permission_context(self, user_id: object) -> PermissionContextStruct:
        assert user_id == self.user.id

        return PermissionContextStruct(
            user=self.user,
            rooms=[RoomStruct(room_id="room-a", owner_user_id=self.user.id)],
        )

    async def check_permission(self, request: PermissionCheckRequestStruct) -> PermissionCheckResultStruct:
        assert request.user_id == self.user.id
        assert request.room_id == "room-a"
        assert request.action is PermissionAction.START

        return PermissionCheckResultStruct(
            allowed=True,
            reason="Authorization grant allows starting the organization room assistant.",
            matched_scope=RoomAuthorizationScope.START,
        )


class TestAuthController:
    @pytest.fixture(autouse=True)
    def set_up(self, monkeypatch: MonkeyPatch) -> None:
        fake_client = FakeAuthPermissionClient()
        monkeypatch.setattr("echocue.controller.auth.create_auth_permission_client", lambda: fake_client)
        monkeypatch.setattr("echocue.shared.context.create_auth_permission_client", lambda: fake_client)
        monkeypatch.setattr("echocue.auth.security.create_auth_permission_client", lambda: fake_client)

    async def test_auth_session_login_and_me(self) -> None:
        controller = AuthController(owner=cast(Any, object()))
        request = FakeSessionRequest()
        ctx = RequestContext(user=FakeAuthPermissionClient.user, user_id=FakeAuthPermissionClient.user.id, is_authenticated=True)

        login_response = await controller.create_session.fn(
            controller,
            request,
            LoginRequest(username="grpc-user", password="password"),
        )
        me_response = await controller.me.fn(
            controller,
            ctx=ctx,
        )

        assert login_response.content["data"]["user"]["username"] == "grpc-user"
        assert request.session["user_id"] == str(FakeAuthPermissionClient.user.id)
        assert me_response.content["data"]["username"] == "grpc-user"

    async def test_auth_controller_uses_auth_client_for_session_context_and_permission_checks(self) -> None:
        controller = AuthController(owner=cast(Any, object()))
        request = FakeSessionRequest()
        ctx = RequestContext(user=FakeAuthPermissionClient.user, user_id=FakeAuthPermissionClient.user.id, is_authenticated=True)

        login_response = await controller.create_session.fn(
            controller,
            request,
            LoginRequest(username="grpc-user", password="password"),
        )
        context_response = await controller.permission_context.fn(controller, ctx=ctx)
        check_response = await controller.check_room_permission.fn(
            controller,
            ctx=ctx,
            data=PermissionCheckRequestStruct(
                user_id=FakeAuthPermissionClient.user.id,
                room_id="room-a",
                action=PermissionAction.START,
            ),
        )

        assert login_response.content["data"]["user"]["username"] == "grpc-user"
        assert context_response.content["data"]["rooms"][0]["roomId"] == "room-a"
        assert check_response.content["data"]["allowed"] is True
        assert check_response.content["data"]["matchedScope"] == "start"

    async def test_auth_controller_rejects_duplicate_session_creation(self) -> None:
        controller = AuthController(owner=cast(Any, object()))
        request = FakeSessionRequest({"user_id": str(FakeAuthPermissionClient.user.id)})

        with pytest.raises(HTTPException) as exc_info:
            await controller.create_session.fn(
                controller,
                request,
                LoginRequest(username="grpc-user", password="password"),
            )

        assert exc_info.value.status_code == 409
