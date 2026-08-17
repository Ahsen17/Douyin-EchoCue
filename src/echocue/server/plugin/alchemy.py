from typing import TYPE_CHECKING

from litestar.plugins import InitPluginProtocol
from litestar.plugins.sqlalchemy import SQLAlchemyPlugin, SQLAlchemySerializationPlugin

from echocue.base import Config
from echocue.shared import AlchemySetup

if TYPE_CHECKING:
    from litestar.config.app import AppConfig


__all__ = ("AlchemyPlugin",)


class AlchemyPlugin(InitPluginProtocol):
    """Alchemy plugin for Litestar."""

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        app_config.plugins.extend(
            [
                SQLAlchemyPlugin(
                    AlchemySetup(
                        Config.get().alchemy,
                    ).create_config()
                ),
                SQLAlchemySerializationPlugin(),
            ]
        )

        return app_config
