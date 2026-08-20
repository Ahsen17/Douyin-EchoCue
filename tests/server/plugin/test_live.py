"""Live plugin dependency registration tests."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

import msgspec.yaml
from litestar import Litestar
from litestar.config.app import AppConfig
from pytest import MonkeyPatch
from redis.asyncio import Redis

from echocue.base import Config, LiveConfig
from echocue.core.live import RedisRoomOnlineStatusCache
from echocue.server.plugin.live import LivePlugin


class ClosableRedis:
    """Redis resource fake used to verify plugin ownership."""

    closed: bool = False

    async def aclose(self) -> None:
        self.closed = True


class TestLivePlugin:
    async def test_registers_room_status_cache_and_closes_redis(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        redis = ClosableRedis()
        config = Config(live=LiveConfig(room_status_cache_ttl_seconds=3_600))
        monkeypatch.setattr(Config, "get", classmethod(lambda cls, filename="config.yaml": config))
        monkeypatch.setattr("echocue.server.plugin.live.Redis.from_url", lambda *args, **kwargs: cast(Redis, redis))

        app_config = LivePlugin().on_app_init(AppConfig())

        cache = app_config.state.get("room_online_status_cache")
        assert isinstance(cache, RedisRoomOnlineStatusCache)
        assert app_config.state.get("room_online_status_redis") is redis
        assert "room_status_cache" in app_config.dependencies
        assert "RoomOnlineStatusCache" in app_config.signature_namespace

        shutdown_hook = cast("Callable[[Litestar], Awaitable[None]]", app_config.on_shutdown[-1])
        await shutdown_hook(cast(Litestar, None))
        assert redis.closed is True

    def test_deploy_config_declares_room_status_ttl(self) -> None:
        app_config = msgspec.yaml.decode(Path("config/app.config.yaml").read_text(encoding="utf-8"))

        assert app_config["live"]["room_status_cache_ttl_seconds"] == 7_200
