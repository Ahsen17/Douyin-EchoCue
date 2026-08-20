"""Webui session controller tests."""

from types import SimpleNamespace
from typing import NoReturn, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from litestar import Litestar, Request
from litestar.di import Provide
from litestar.exceptions import HTTPException, ServiceUnavailableException, ValidationException
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from litestar.stores.memory import MemoryStore
from litestar.testing import AsyncTestClient
from pytest import MonkeyPatch

from echocue.auth import AuthenticationResultStruct, AuthPermissionClient, PermissionContextStruct, UserStruct
from echocue.auth.security import create_auth
from echocue.base import Config
from echocue.controller.client import ClientController
from echocue.controller.webui import WebuiController
from echocue.core.client import ClientSessionHandler, MemoryUserClientGuard
from echocue.core.live import MemoryRoomOnlineStatusCache
from echocue.core.room import RoomAggregationHandler
from echocue.shared import ApplicationError
from echocue.shared.context import provide_request_context
from echocue.shared.exception import (
    app_error_handler,
    http_exception_handler,
    validation_exception_handler,
)


def raise_internal_exception(_: Request, exc: Exception) -> NoReturn:
    """Expose unexpected controller errors during tests."""

    raise exc


class TestWebuiController:
    """Verify the dedicated webui session boundary."""

    app: Litestar
    user: UserStruct
    auth_client: SimpleNamespace
    guard: MemoryUserClientGuard
    room_aggregation_handler: RoomAggregationHandler

    @pytest.fixture(autouse=True)
    def set_up(self, monkeypatch: MonkeyPatch) -> None:
        config = Config()
        self.guard = MemoryUserClientGuard()
        client_session_handler = ClientSessionHandler(
            self.guard,
            session_max_age_seconds=config.auth.session_max_age_seconds,
        )
        self.user = UserStruct(id=uuid4(), username="webui-user")
        context = PermissionContextStruct(user=self.user)
        self.auth_client = SimpleNamespace(
            authenticate=AsyncMock(return_value=AuthenticationResultStruct(user=self.user, context=context)),
            get_permission_context=AsyncMock(return_value=context),
            check_permission=AsyncMock(),
        )
        self.room_aggregation_handler = RoomAggregationHandler(
            cast(AuthPermissionClient, self.auth_client),
            MemoryRoomOnlineStatusCache(),
        )
        self.app = Litestar(
            route_handlers=[ClientController, WebuiController],
            dependencies={
                "ctx": Provide(provide_request_context),
                "client_session_handler": Provide(lambda: client_session_handler, sync_to_thread=False),
                "room_aggregation_handler": Provide(lambda: self.room_aggregation_handler, sync_to_thread=False),
            },
            exception_handlers={
                ApplicationError: app_error_handler,
                ValidationException: validation_exception_handler,
                HTTPException: http_exception_handler,
                Exception: raise_internal_exception,
            },
            on_app_init=[create_auth(config.auth).on_app_init],
            stores={config.auth.session_store_name: MemoryStore()},
        )
        monkeypatch.setattr(Config, "get", classmethod(lambda cls, filename="config.yaml": config))
        monkeypatch.setattr("echocue.controller.webui.create_auth_permission_client", lambda: self.auth_client)
        monkeypatch.setattr("echocue.core.client.handler.create_auth_permission_client", lambda: self.auth_client)
        monkeypatch.setattr("echocue.shared.context.create_auth_permission_client", lambda: self.auth_client)
        monkeypatch.setattr("echocue.auth.security.create_auth_permission_client", lambda: self.auth_client)

    async def test_login_restore_me_and_logout(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            login_response = await client.post("/webui/session", json=self._login_payload())
            me_response = await client.get("/webui/me")
            logout_response = await client.delete("/webui/session")
            expired_response = await client.get("/webui/me")

        assert login_response.status_code == HTTP_200_OK
        assert login_response.json()["data"] == {
            "expiresIn": 28_800,
            "user": {
                "id": str(self.user.id),
                "username": "webui-user",
                "displayName": "webui-user",
                "isActive": True,
            },
        }
        assert me_response.status_code == HTTP_200_OK
        assert me_response.json()["data"]["username"] == "webui-user"
        assert logout_response.status_code == HTTP_200_OK
        assert logout_response.json() == {"code": 200, "message": "ok", "data": None}
        assert expired_response.status_code == HTTP_401_UNAUTHORIZED

    async def test_rejects_invalid_login_payload(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            response = await client.post("/webui/session", json={"username": "webui-user"})

        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_auth_unavailable_is_returned_without_session(self) -> None:
        self.auth_client.authenticate.side_effect = ServiceUnavailableException(detail="Auth service unavailable.")

        async with AsyncTestClient(app=self.app) as client:
            response = await client.post("/webui/session", json=self._login_payload())
            me_response = await client.get("/webui/me")

        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert me_response.status_code == HTTP_401_UNAUTHORIZED

    async def test_client_session_cannot_enter_or_clear_webui_boundary(self) -> None:
        client_id = uuid4()

        async with AsyncTestClient(app=self.app) as client:
            login_response = await client.post(
                "/client/session",
                json={**self._login_payload(), "clientId": str(client_id)},
            )
            me_response = await client.get("/webui/me")
            logout_response = await client.delete("/webui/session")
            client_me_response = await client.get("/client/me")

        assert login_response.status_code == HTTP_200_OK
        assert me_response.status_code == HTTP_401_UNAUTHORIZED
        assert logout_response.status_code == HTTP_401_UNAUTHORIZED
        assert client_me_response.status_code == HTTP_200_OK

    async def test_webui_session_cannot_enter_client_boundary(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            login_response = await client.post("/webui/session", json=self._login_payload())
            client_me_response = await client.get("/client/me")

        assert login_response.status_code == HTTP_200_OK
        assert client_me_response.status_code == HTTP_401_UNAUTHORIZED

    async def test_lists_rooms_for_webui_session_only(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            unauthenticated_response = await client.get("/webui/rooms")
            await client.post("/webui/session", json=self._login_payload())
            response = await client.get("/webui/rooms")

        assert unauthenticated_response.status_code == HTTP_401_UNAUTHORIZED
        assert response.status_code == HTTP_200_OK
        assert response.json() == {"code": 200, "message": "ok", "data": {"items": []}}

    async def test_client_and_webui_sessions_coexist_without_sharing_guard(self) -> None:
        client_id = uuid4()

        async with (
            AsyncTestClient(app=self.app) as client,
            AsyncTestClient(app=self.app) as webui,
        ):
            client_login_response = await client.post(
                "/client/session",
                json={**self._login_payload(), "clientId": str(client_id)},
            )
            webui_login_response = await webui.post("/webui/session", json=self._login_payload())
            webui_logout_response = await webui.delete("/webui/session")
            client_me_response = await client.get("/client/me")
            guard_remains_owned = await self.guard.renew(self.user.id, client_id, expires_in=28_800)
            client_logout_response = await client.delete("/client/session")

        assert client_login_response.status_code == HTTP_200_OK
        assert webui_login_response.status_code == HTTP_200_OK
        assert webui_logout_response.status_code == HTTP_200_OK
        assert client_me_response.status_code == HTTP_200_OK
        assert guard_remains_owned is True
        assert client_logout_response.status_code == HTTP_200_OK
        assert await self.guard.renew(self.user.id, client_id, expires_in=28_800) is False

    @staticmethod
    def _login_payload() -> dict[str, str]:
        return {"username": "webui-user", "password": "fake-password"}
