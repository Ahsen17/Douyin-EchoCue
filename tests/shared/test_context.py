from collections.abc import Awaitable, Callable
from typing import Any, cast
from uuid import uuid4

from echocue.auth.model import UserModel
from echocue.auth.security import SESSION_USER_ID_KEY
from echocue.base import Config
from echocue.shared.context import provide_request_context


class RequestStub:
    def __init__(self, session: dict[str, Any]) -> None:
        self._session = session

    @property
    def user(self) -> None:
        return None

    @property
    def session(self) -> dict[str, Any]:
        return self._session


class TestRequestContext:
    async def test_resolves_user_from_session(
        self,
        test_config: Config,
        create_test_user: Callable[..., Awaitable[UserModel]],
    ) -> None:
        assert test_config.alchemy.url.startswith("sqlite+aiosqlite")
        user = await create_test_user(username="admin", password="admin")

        context = await provide_request_context(
            cast(Any, RequestStub({SESSION_USER_ID_KEY: str(user.id)})),
        )

        assert context.is_authenticated is True
        assert context.user_id == user.id
        assert context.user is not None
        assert context.user.username == "admin"

    async def test_ignores_invalid_session_user_id(self, test_config: Config) -> None:
        assert test_config.alchemy.url.startswith("sqlite+aiosqlite")

        context = await provide_request_context(
            cast(Any, RequestStub({SESSION_USER_ID_KEY: str(uuid4())})),
        )

        assert context.is_authenticated is False
        assert context.user is None
        assert context.user_id is None
