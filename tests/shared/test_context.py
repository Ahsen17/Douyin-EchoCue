from typing import Any, cast
from uuid import uuid4

import pytest
from litestar.exceptions import NotAuthorizedException

from echocue.auth import PermissionContextStruct, SessionClientType, UserStruct
from echocue.auth.session import create_session_data
from echocue.shared.context import RequestContext, provide_request_context


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
            cast(Any, RequestStub(create_session_data(user.id, SessionClientType.WEBUI))),
        )

        assert context.is_authenticated is True
        assert context.user_id == user.id
        assert context.user is not None
        assert context.user.username == "admin"
        assert context.client_type is SessionClientType.WEBUI
        assert context.client_id is None

    async def test_ignores_invalid_session_user_id(self) -> None:
        context = await provide_request_context(
            cast(Any, RequestStub({"user_id": "not-a-uuid", "client_type": "webui"})),
        )

        assert context.is_authenticated is False
        assert context.user is None
        assert context.user_id is None

    async def test_rejects_client_session_without_client_id(self) -> None:
        context = await provide_request_context(
            cast(Any, RequestStub({"user_id": str(uuid4()), "client_type": "client"})),
        )

        assert context.is_authenticated is False
        assert context.client_type is None

    def test_client_context_cannot_enter_webui_boundary(self) -> None:
        client_id = uuid4()
        context = RequestContext(
            user_id=uuid4(),
            client_type=SessionClientType.CLIENT,
            client_id=client_id,
            is_authenticated=True,
        )

        assert context.require_client_id() == client_id
        with pytest.raises(NotAuthorizedException, match="webui session"):
            context.require_webui_session()

    def test_webui_context_cannot_enter_client_boundary(self) -> None:
        context = RequestContext(
            user_id=uuid4(),
            client_type=SessionClientType.WEBUI,
            is_authenticated=True,
        )

        context.require_webui_session()
        with pytest.raises(NotAuthorizedException, match="client session"):
            context.require_client_id()
