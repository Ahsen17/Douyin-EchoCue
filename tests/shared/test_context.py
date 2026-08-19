from typing import Any, cast
from uuid import uuid4

import pytest

from echocue.auth import PermissionContextStruct, UserStruct
from echocue.auth.security import SESSION_USER_ID_KEY
from echocue.shared.context import provide_request_context


class FakeAuthPermissionClient:
    def __init__(self, user: UserStruct | None) -> None:
        self._user = user

    async def get_permission_context(self, user_id: object) -> PermissionContextStruct:
        if self._user is None or user_id != self._user.id:
            raise AssertionError("Unexpected user id.")

        return PermissionContextStruct(user=self._user)


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
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        user = UserStruct(id=uuid4(), username="admin")
        fake_client = FakeAuthPermissionClient(user)
        monkeypatch.setattr("echocue.shared.context.create_auth_permission_client", lambda: fake_client)

        context = await provide_request_context(
            cast(Any, RequestStub({SESSION_USER_ID_KEY: str(user.id)})),
        )

        assert context.is_authenticated is True
        assert context.user_id == user.id
        assert context.user is not None
        assert context.user.username == "admin"

    async def test_ignores_invalid_session_user_id(self) -> None:
        context = await provide_request_context(
            cast(Any, RequestStub({SESSION_USER_ID_KEY: "not-a-uuid"})),
        )

        assert context.is_authenticated is False
        assert context.user is None
        assert context.user_id is None
