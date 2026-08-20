"""Live-domain runtime dependency registration."""

from typing import TYPE_CHECKING, ClassVar, cast

from litestar.di import Provide
from litestar.plugins import InitPluginProtocol
from redis.asyncio import Redis

from echocue.base import Config
from echocue.core.live import RedisRoomOnlineStatusCache, RoomOnlineStatusCache

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.config.app import AppConfig
    from litestar.datastructures import State

__all__ = ("LivePlugin",)


class LivePlugin(InitPluginProtocol):
    """Register the shared room online-status cache."""

    cache_state_key: ClassVar[str] = "room_online_status_cache"
    redis_state_key: ClassVar[str] = "room_online_status_redis"

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        """Configure the Redis-backed room status dependency."""

        config = Config.get()
        redis = Redis.from_url(
            config.redis.dsn,
            socket_connect_timeout=config.redis.connection_timeout,
        )
        cache = RedisRoomOnlineStatusCache(
            redis,
            ttl_seconds=config.live.room_status_cache_ttl_seconds,
        )
        app_config.state.update(
            {
                self.cache_state_key: cache,
                self.redis_state_key: redis,
            }
        )
        app_config.signature_namespace.update(
            {
                "RedisRoomOnlineStatusCache": RedisRoomOnlineStatusCache,
                "RoomOnlineStatusCache": RoomOnlineStatusCache,
            }
        )
        app_config.dependencies["room_status_cache"] = Provide(
            self.provide_room_status_cache,
            sync_to_thread=True,
        )

        async def close_redis(_: "Litestar") -> None:
            await redis.aclose()

        app_config.on_shutdown.append(close_redis)

        return app_config

    def provide_room_status_cache(self, state: "State") -> RoomOnlineStatusCache:
        """Return the shared room online-status cache."""

        return cast("RoomOnlineStatusCache", state.get(self.cache_state_key))
