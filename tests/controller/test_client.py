"""Desktop client session controller tests."""

from types import SimpleNamespace
from typing import NoReturn, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from litestar import Litestar, Request
from litestar.di import Provide
from litestar.exceptions import HTTPException, ServiceUnavailableException, ValidationException
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_409_CONFLICT,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from litestar.stores.memory import MemoryStore
from litestar.testing import AsyncTestClient
from pytest import MonkeyPatch

from echocue.auth import (
    AuthenticationResultStruct,
    AuthPermissionClient,
    LoginRequest,
    PermissionContextStruct,
    UserStruct,
)
from echocue.auth.security import create_auth
from echocue.base import Config
from echocue.controller.auth import AuthController
from echocue.controller.client import ClientController
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


class TestClientController:
    app: Litestar
    user: UserStruct
    auth_client: SimpleNamespace
    room_aggregation_handler: RoomAggregationHandler

    @pytest.fixture(autouse=True)
    def set_up(self, monkeypatch: MonkeyPatch) -> None:
        config = Config()
        client_session_handler = ClientSessionHandler(
            MemoryUserClientGuard(),
            session_max_age_seconds=config.auth.session_max_age_seconds,
        )
        self.user = UserStruct(id=uuid4(), username="client-user")
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
            route_handlers=[AuthController, ClientController],
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
        monkeypatch.setattr(
            "echocue.core.client.handler.create_auth_permission_client",
            lambda: self.auth_client,
        )
        monkeypatch.setattr("echocue.controller.auth.create_auth_permission_client", lambda: self.auth_client)
        monkeypatch.setattr("echocue.shared.context.create_auth_permission_client", lambda: self.auth_client)
        monkeypatch.setattr("echocue.auth.security.create_auth_permission_client", lambda: self.auth_client)

    async def test_login_restore_me_and_logout(self) -> None:
        client_id = str(uuid4())
        login_payload = {"username": "client-user", "password": "fake-password", "clientId": client_id}

        async with AsyncTestClient(app=self.app) as client:
            login_response = await client.post("/client/session", json=login_payload)
            restore_response = await client.post("/client/session", json=login_payload)
            me_response = await client.get("/client/me")
            logout_response = await client.delete("/client/session")
            expired_response = await client.get("/client/me")

        assert login_response.status_code == HTTP_200_OK
        assert login_response.json()["data"] == {
            "expiresIn": 28_800,
            "user": {
                "id": str(self.user.id),
                "username": "client-user",
                "displayName": "client-user",
                "isActive": True,
            },
        }
        assert restore_response.status_code == HTTP_200_OK
        assert me_response.status_code == HTTP_200_OK
        assert me_response.json()["data"]["displayName"] == "client-user"
        assert logout_response.status_code == HTTP_200_OK
        assert logout_response.json() == {"code": 200, "message": "ok", "data": None}
        assert expired_response.status_code == HTTP_401_UNAUTHORIZED

    async def test_different_client_is_rejected_with_stable_error(self) -> None:
        first_payload = self._login_payload(uuid4())
        second_payload = self._login_payload(uuid4())

        async with (
            AsyncTestClient(app=self.app) as first_client,
            AsyncTestClient(app=self.app) as second_client,
        ):
            first_response = await first_client.post("/client/session", json=first_payload)
            conflict_response = await second_client.post("/client/session", json=second_payload)

        assert first_response.status_code == HTTP_200_OK
        assert conflict_response.status_code == HTTP_409_CONFLICT
        assert conflict_response.json()["data"]["errorCode"] == "clientSessionConflict"

    async def test_different_users_can_login_independently(self) -> None:
        second_user = UserStruct(id=uuid4(), username="second-user")

        async def authenticate(request: LoginRequest) -> AuthenticationResultStruct:
            user = second_user if request.username == "second-user" else self.user
            return AuthenticationResultStruct(user=user, context=PermissionContextStruct(user=user))

        self.auth_client.authenticate.side_effect = authenticate

        async with (
            AsyncTestClient(app=self.app) as first_client,
            AsyncTestClient(app=self.app) as second_client,
        ):
            first_response = await first_client.post("/client/session", json=self._login_payload(uuid4()))
            second_response = await second_client.post(
                "/client/session",
                json=self._login_payload(uuid4(), username="second-user"),
            )

        assert first_response.status_code == HTTP_200_OK
        assert second_response.status_code == HTTP_200_OK

    async def test_rejects_missing_and_invalid_client_id(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            missing_response = await client.post(
                "/client/session",
                json={"username": "client-user", "password": "fake-password"},
            )
            invalid_response = await client.post(
                "/client/session",
                json={"username": "client-user", "password": "fake-password", "clientId": "invalid"},
            )

        assert missing_response.status_code == HTTP_400_BAD_REQUEST
        assert invalid_response.status_code == HTTP_400_BAD_REQUEST

    async def test_webui_session_cannot_enter_client_endpoint(self) -> None:
        async with AsyncTestClient(app=self.app) as client:
            login_response = await client.post(
                "/auth/session",
                json={"username": "client-user", "password": "fake-password"},
            )
            me_response = await client.get("/client/me")

        assert login_response.status_code == HTTP_200_OK
        assert me_response.status_code == HTTP_401_UNAUTHORIZED

    async def test_lists_rooms_for_client_session_only(self) -> None:
        client_id = uuid4()

        async with AsyncTestClient(app=self.app) as client:
            unauthenticated_response = await client.get("/client/rooms")
            await client.post("/client/session", json=self._login_payload(client_id))
            response = await client.get("/client/rooms")

        assert unauthenticated_response.status_code == HTTP_401_UNAUTHORIZED
        assert response.status_code == HTTP_200_OK
        assert response.json() == {"code": 200, "message": "ok", "data": {"items": []}}

    async def test_auth_unavailable_is_returned_without_session(self) -> None:
        self.auth_client.authenticate.side_effect = ServiceUnavailableException(detail="Auth service unavailable.")

        async with AsyncTestClient(app=self.app) as client:
            response = await client.post("/client/session", json=self._login_payload(uuid4()))
            me_response = await client.get("/client/me")

        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert me_response.status_code == HTTP_401_UNAUTHORIZED

    @staticmethod
    def _login_payload(client_id: UUID, *, username: str = "client-user") -> dict[str, str]:
        return {
            "username": username,
            "password": "fake-password",
            "clientId": str(client_id),
        }
