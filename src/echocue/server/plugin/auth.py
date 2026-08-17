"""Authentication plugin for Litestar.

This module registers Redis-backed session storage and installs session authentication.
Authentication configuration stays in the server layer and does not leak into controllers.
"""

from typing import TYPE_CHECKING

from litestar.plugins import InitPluginProtocol
from litestar.stores.redis import RedisStore
from litestar.stores.registry import StoreRegistry

from echocue.auth.security import create_auth
from echocue.base import Config

if TYPE_CHECKING:
    from litestar.config.app import AppConfig

__all__ = ("AuthPlugin",)


class AuthPlugin(InitPluginProtocol):
    """Redis session authentication plugin."""

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        """Register session storage and authentication middleware."""

        config = Config.get()
        session_store = RedisStore.with_client(
            url=config.redis.dsn,
            namespace=config.auth.session_store_namespace,
        )

        if app_config.stores is None:
            app_config.stores = {config.auth.session_store_name: session_store}
        elif isinstance(app_config.stores, StoreRegistry):
            app_config.stores.register(config.auth.session_store_name, session_store, allow_override=True)
        else:
            app_config.stores[config.auth.session_store_name] = session_store

        create_auth(config.auth).on_app_init(app_config)

        return app_config
