from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_409_CONFLICT
from litestar.testing import AsyncTestClient
from pytest import MonkeyPatch

from echocue.auth import (
    AuthenticationResultStruct,
    PermissionCheckResultStruct,
    PermissionContextStruct,
    RoomAuthorizationScope,
    RoomStruct,
    UserStruct,
)


class TestAuthController:
    app: Litestar

    @pytest.fixture(autouse=True)
    def set_up(
        self,
        app: Litestar,
        monkeypatch: MonkeyPatch,
    ) -> None:
        self.app = app

        user = UserStruct(id=uuid4(), username="grpc-user", email=None, is_active=True, is_superuser=False)
        context = PermissionContextStruct(
            user=user,
            rooms=[RoomStruct(room_id="room-a", owner_user_id=user.id)],
        )
        auth_client = SimpleNamespace(
            authenticate=AsyncMock(return_value=AuthenticationResultStruct(user=user, context=context)),
            get_permission_context=AsyncMock(return_value=context),
            check_permission=AsyncMock(
                return_value=PermissionCheckResultStruct(
                    allowed=True,
                    reason="Authorization grant allows starting the organization room assistant.",
                    matched_scope=RoomAuthorizationScope.START,
                )
            ),
        )

        monkeypatch.setattr("echocue.controller.auth.create_auth_permission_client", lambda: auth_client)
        monkeypatch.setattr("echocue.shared.context.create_auth_permission_client", lambda: auth_client)
        monkeypatch.setattr("echocue.auth.security.create_auth_permission_client", lambda: auth_client)

    async def test_auth_session_login_and_me(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            login_response = await client.post(
                "/auth/session",
                json={"username": "grpc-user", "password": "password"},
            )

            assert login_response.status_code == HTTP_200_OK
            assert login_response.json()["data"]["user"]["username"] == "grpc-user"

            me_response = await client.get("/auth/me")

            assert me_response.status_code == HTTP_200_OK
            assert me_response.json()["data"]["username"] == "grpc-user"
            assert me_response.json()["data"]["isSuperuser"] is False

    async def test_auth_permission_context_and_room_permission_check(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            login_response = await client.post(
                "/auth/session",
                json={"username": "grpc-user", "password": "password"},
            )
            context_response = await client.get("/auth/permission/context")
            check_response = await client.post(
                "/auth/room/permissions/checks",
                json={"roomId": "room-a", "action": "start"},
            )

        assert login_response.status_code == HTTP_200_OK
        assert context_response.status_code == HTTP_200_OK
        assert context_response.json()["data"]["rooms"][0]["roomId"] == "room-a"
        assert check_response.status_code == HTTP_200_OK
        assert check_response.json()["data"]["allowed"] is True
        assert check_response.json()["data"]["matchedScope"] == "start"

    async def test_auth_session_rejects_duplicate_session_creation(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            first_response = await client.post(
                "/auth/session",
                json={"username": "grpc-user", "password": "password"},
            )
            second_response = await client.post(
                "/auth/session",
                json={"username": "grpc-user", "password": "password"},
            )

        assert first_response.status_code == HTTP_200_OK
        assert second_response.status_code == HTTP_409_CONFLICT
