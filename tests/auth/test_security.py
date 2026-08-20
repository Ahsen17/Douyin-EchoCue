from datetime import timedelta
from typing import Any, cast

from litestar.middleware.session.server_side import ServerSideSessionConfig
from litestar.stores.memory import MemoryStore

from echocue.auth.security import SESSION_EXCLUDE_PATHS, create_auth
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
