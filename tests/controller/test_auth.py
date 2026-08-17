from collections.abc import Awaitable, Callable

import pytest
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK
from litestar.testing import AsyncTestClient

from echocue.auth.model import UserModel


class TestAuthController:
    app: Litestar
    create_test_user: Callable[..., Awaitable[UserModel]]

    @pytest.fixture(autouse=True)
    def set_up(
        self,
        app: Litestar,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        self.app = app
        self.create_test_user = create_test_user

    async def test_auth_session_login_and_me(self) -> None:
        await self.create_test_user(username="admin", password="admin", is_superuser=True)

        async with AsyncTestClient(app=self.app) as client:
            login_response = await client.post("/auth/session", json={"username": "admin", "password": "admin"})

            assert login_response.status_code == HTTP_200_OK
            assert login_response.json()["data"]["user"]["username"] == "admin"

            me_response = await client.get("/auth/me")

            assert me_response.status_code == HTTP_200_OK
            assert me_response.json()["data"]["username"] == "admin"
            assert me_response.json()["data"]["isSuperuser"] is True
