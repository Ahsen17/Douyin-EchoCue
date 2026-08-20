"""Client session orchestration tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from litestar.exceptions import ServiceUnavailableException
from pytest import MonkeyPatch

from echocue.auth import AuthenticationResultStruct, PermissionContextStruct, UserStruct
from echocue.core.client import ClientSessionCreate, ClientSessionHandler, MemoryUserClientGuard
from echocue.core.client.exception import ClientSessionConflictError
from echocue.core.client.schema import RuntimeFailureVO


class TestClientSessionHandler:
    user: UserStruct
    guard: MemoryUserClientGuard
    handler: ClientSessionHandler
    auth_client: SimpleNamespace

    @pytest.fixture(autouse=True)
    def set_up(self, monkeypatch: MonkeyPatch) -> None:
        self.user = UserStruct(id=uuid4(), username="client-user")
        context = PermissionContextStruct(user=self.user)
        self.auth_client = SimpleNamespace(
            authenticate=AsyncMock(return_value=AuthenticationResultStruct(user=self.user, context=context))
        )
        self.guard = MemoryUserClientGuard()
        self.handler = ClientSessionHandler(self.guard, session_max_age_seconds=28_800)
        monkeypatch.setattr(
            "echocue.core.client.handler.create_auth_permission_client",
            lambda: self.auth_client,
        )

    async def test_authenticates_and_allows_same_client_recovery(self) -> None:
        client_id = uuid4()
        request = ClientSessionCreate(username="client-user", password="fake-password", client_id=client_id)

        first_user = await self.handler.create(request)
        recovered_user = await self.handler.create(request)

        assert first_user == self.user
        assert recovered_user == self.user
        assert self.auth_client.authenticate.await_count == 2
        remaining_ttl = self.guard.expires_in(self.user.id)
        assert remaining_ttl is not None
        assert remaining_ttl >= 28_798

    async def test_rejects_different_client_for_same_user(self) -> None:
        await self.handler.create(
            ClientSessionCreate(username="client-user", password="fake-password", client_id=uuid4())
        )

        with pytest.raises(ClientSessionConflictError) as exc_info:
            await self.handler.create(
                ClientSessionCreate(username="client-user", password="fake-password", client_id=uuid4())
            )

        assert isinstance(exc_info.value.data, RuntimeFailureVO)
        assert exc_info.value.data.error_code.value == "clientSessionConflict"

    async def test_propagates_auth_unavailability_without_acquiring_guard(self) -> None:
        self.auth_client.authenticate.side_effect = ServiceUnavailableException(detail="Auth service unavailable.")

        with pytest.raises(ServiceUnavailableException):
            await self.handler.create(
                ClientSessionCreate(username="client-user", password="fake-password", client_id=uuid4())
            )

        assert self.guard.expires_in(self.user.id) is None
