from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from litestar.exceptions import NotAuthorizedException, ServiceUnavailableException
from litestar.middleware.session.server_side import ServerSideSessionConfig
from litestar.stores.memory import MemoryStore
from pytest import MonkeyPatch

from echocue.auth import SessionClientType
from echocue.auth.security import SESSION_EXCLUDE_PATHS, create_auth, retrieve_user_handler
from echocue.auth.session import create_session_data
from echocue.base import AuthConfig


class TestSessionAuth:
    def test_defaults_to_eight_hour_sliding_session(self) -> None:
        config = AuthConfig()
        auth = create_auth(config)
        session_config = auth.session_backend_config

        assert config.session_max_age_seconds == 28_800
        assert isinstance(session_config, ServerSideSessionConfig)
        assert session_config.max_age == 28_800
        assert session_config.renew_on_access is True

    def test_excludes_public_paths_from_auth_and_session_middleware(self) -> None:
        auth = create_auth(AuthConfig())
        expected_paths = list(SESSION_EXCLUDE_PATHS)

        assert auth.exclude == expected_paths
        assert auth.session_backend_config.exclude == expected_paths

    async def test_session_read_renews_store_ttl(self) -> None:
        auth = create_auth(AuthConfig())
        backend = auth.session_backend
        store = MemoryStore()
        await store.set("session-id", b"session-data", expires_in=60)

        session_data = await backend.get("session-id", cast(Any, store))
        renewed_ttl = await store.expires_in("session-id")

        assert session_data == b"session-data"
        assert renewed_ttl is not None
        assert renewed_ttl >= 28_790

    async def test_expired_session_is_deleted_on_read(self) -> None:
        auth = create_auth(AuthConfig())
        backend = auth.session_backend
        store = MemoryStore()
        await store.set("session-id", b"session-data", expires_in=timedelta(microseconds=-1))

        session_data = await backend.get("session-id", cast(Any, store))

        assert session_data is None
        assert await store.exists("session-id") is False

    @pytest.mark.parametrize(
        ("auth_error", "expected_release_count", "expected_clear_count"),
        [
            (NotAuthorizedException(detail="Invalid session."), 1, 1),
            (ServiceUnavailableException(detail="Auth unavailable."), 0, 0),
        ],
    )
    async def test_invalid_user_releases_client_guard_but_auth_outage_does_not(
        self,
        monkeypatch: MonkeyPatch,
        auth_error: Exception,
        expected_release_count: int,
        expected_clear_count: int,
    ) -> None:
        user_id = uuid4()
        client_id = uuid4()
        guard = SimpleNamespace(renew=AsyncMock(return_value=True), release=AsyncMock())
        connection = SimpleNamespace(
            app=SimpleNamespace(state={"user_client_guard": guard}),
            clear_session=Mock(),
        )
        auth_client = SimpleNamespace(get_permission_context=AsyncMock(side_effect=auth_error))
        monkeypatch.setattr("echocue.auth.security.create_auth_permission_client", lambda: auth_client)

        user = await retrieve_user_handler(
            create_session_data(user_id, SessionClientType.CLIENT, client_id),
            cast(Any, connection),
        )

        assert user is None
        guard.renew.assert_awaited_once_with(user_id, client_id, expires_in=28_800)
        assert guard.release.await_count == expected_release_count
        assert connection.clear_session.call_count == expected_clear_count

    async def test_missing_or_conflicting_client_guard_invalidates_session(self, monkeypatch: MonkeyPatch) -> None:
        user_id = uuid4()
        client_id = uuid4()
        guard = SimpleNamespace(renew=AsyncMock(return_value=False), release=AsyncMock())
        connection = SimpleNamespace(
            app=SimpleNamespace(state={"user_client_guard": guard}),
            clear_session=Mock(),
        )
        auth_client = SimpleNamespace(get_permission_context=AsyncMock())
        monkeypatch.setattr("echocue.auth.security.create_auth_permission_client", lambda: auth_client)

        user = await retrieve_user_handler(
            create_session_data(user_id, SessionClientType.CLIENT, client_id),
            cast(Any, connection),
        )

        assert user is None
        connection.clear_session.assert_called_once_with()
        auth_client.get_permission_context.assert_not_awaited()
