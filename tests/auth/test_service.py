from collections.abc import Awaitable, Callable

import pytest
from litestar.exceptions import NotAuthorizedException

from aigc.auth.model import UserModel
from aigc.auth.schema import LoginRequest
from aigc.auth.service import UserService


class TestUserService:
    async def test_authenticate_returns_user_for_valid_credentials(
        self,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        user = await create_test_user(username="admin", password="admin", is_superuser=True)

        async with UserService.provide() as service:
            result = await service.authenticate(LoginRequest(username="admin", password="admin"))

        assert result.id == user.id
        assert result.username == "admin"
        assert result.is_superuser is True

    async def test_authenticate_rejects_invalid_credentials(
        self,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        await create_test_user(username="admin", password="admin")

        async with UserService.provide() as service:
            with pytest.raises(NotAuthorizedException):
                await service.authenticate(LoginRequest(username="admin", password="wrong-password"))
