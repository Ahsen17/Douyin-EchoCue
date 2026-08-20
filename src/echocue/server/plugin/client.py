"""Client-domain runtime dependency registration."""

from typing import TYPE_CHECKING, ClassVar, cast

from litestar.di import Provide
from litestar.plugins import InitPluginProtocol
from redis.asyncio import Redis

from echocue.base import Config
from echocue.core.client import RedisRemediationStore, RemediationHandler

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.config.app import AppConfig
    from litestar.datastructures import State

__all__ = ("ClientPlugin",)


class ClientPlugin(InitPluginProtocol):
    """Register shared remediation state and orchestration."""

    handler_state_key: ClassVar[str] = "remediation_handler"
    redis_state_key: ClassVar[str] = "remediation_redis"

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
        app_config.state.update(
            {
                self.handler_state_key: handler,
                self.redis_state_key: redis,
            }
        )
        app_config.signature_namespace.update({"RemediationHandler": RemediationHandler})
        app_config.dependencies["remediation_handler"] = Provide(
            self.provide_remediation_handler,
            sync_to_thread=True,
        )

        async def close_redis(_: "Litestar") -> None:
            await redis.aclose()

        app_config.on_shutdown.append(close_redis)
        return app_config

    def provide_remediation_handler(self, state: "State") -> RemediationHandler:
        """Return the shared remediation handler."""

        return cast("RemediationHandler", state.get(self.handler_state_key))
