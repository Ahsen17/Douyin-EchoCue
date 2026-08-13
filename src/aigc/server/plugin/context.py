"""Request context dependency plugin.

This module registers request-scoped context dependencies through Litestar's application config.
Controllers should consume the dependency instead of parsing cookies or sessions directly.
"""

from typing import TYPE_CHECKING

from litestar.di import Provide
from litestar.plugins import InitPluginProtocol

from aigc.shared.context import provide_request_context

if TYPE_CHECKING:
    from litestar.config.app import AppConfig

__all__ = ("ContextPlugin",)


class ContextPlugin(InitPluginProtocol):
    """Request context dependency plugin."""

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        """Register request-scoped context dependencies."""

        app_config.dependencies["ctx"] = Provide(provide_request_context)

        return app_config
