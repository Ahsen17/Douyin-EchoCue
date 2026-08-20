"""Client-domain runtime dependency registration."""

from typing import TYPE_CHECKING, ClassVar, cast

from litestar.di import Provide
from litestar.plugins import InitPluginProtocol
from redis.asyncio import Redis

from echocue.base import Config
from echocue.core.client import (
    RedisClientRuntimeGuard,
    RedisRemediationStore,
    RedisRuntimeStore,
    RemediationHandler,
)

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.config.app import AppConfig
    from litestar.datastructures import State

__all__ = ("ClientPlugin",)


class ClientPlugin(InitPluginProtocol):
    """Register shared remediation state and orchestration."""

    handler_state_key: ClassVar[str] = "remediation_handler"
    redis_state_key: ClassVar[str] = "remediation_redis"
    runtime_guard_state_key: ClassVar[str] = "client_runtime_guard"
    runtime_store_state_key: ClassVar[str] = "runtime_store"

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        """Configure the Redis-backed remediation dependency."""

        config = Config.get()
        redis = Redis.from_url(
            config.redis.dsn,
            socket_connect_timeout=config.redis.connection_timeout,
        )
        handler = RemediationHandler(
            RedisRemediationStore(redis),
            remediation_url=config.client.remediation_url,
            token_ttl_seconds=config.client.remediation_token_ttl_seconds,
            failure_ttl_seconds=config.auth.session_max_age_seconds,
        )
        runtime_guard = RedisClientRuntimeGuard(redis)
        runtime_store = RedisRuntimeStore(redis)
        app_config.state.update(
            {
                self.handler_state_key: handler,
                self.redis_state_key: redis,
                self.runtime_guard_state_key: runtime_guard,
                self.runtime_store_state_key: runtime_store,
            }
        )
        app_config.signature_namespace.update({
            "RemediationHandler": RemediationHandler,
            "ClientRuntimeGuard": RedisClientRuntimeGuard,
            "RuntimeStore": RedisRuntimeStore,
        })
        app_config.dependencies["remediation_handler"] = Provide(
            self.provide_remediation_handler,
            sync_to_thread=True,
        )
        app_config.dependencies["client_runtime_guard"] = Provide(
            self.provide_runtime_guard,
            sync_to_thread=True,
        )
        app_config.dependencies["runtime_store"] = Provide(
            self.provide_runtime_store,
            sync_to_thread=True,
        )

        async def close_redis(_: "Litestar") -> None:
            await redis.aclose()

        app_config.on_shutdown.append(close_redis)
        return app_config

    def provide_remediation_handler(self, state: "State") -> RemediationHandler:
        """Return the shared remediation handler."""

        return cast("RemediationHandler", state.get(self.handler_state_key))

    def provide_runtime_guard(self, state: "State") -> RedisClientRuntimeGuard:
        """Return the atomic client and room runtime guard."""

        return cast("RedisClientRuntimeGuard", state.get(self.runtime_guard_state_key))

    def provide_runtime_store(self, state: "State") -> RedisRuntimeStore:
        """Return the runtime context store."""

        return cast("RedisRuntimeStore", state.get(self.runtime_store_state_key))
