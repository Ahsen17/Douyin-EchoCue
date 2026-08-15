from typing import TYPE_CHECKING, ClassVar, cast

from litestar.di import Provide
from litestar.plugins import InitPluginProtocol
from qdrant_client import AsyncQdrantClient

from aigc.base import Config
from aigc.lib.qdrant import QdrantClientFactory

if TYPE_CHECKING:
    from litestar.config.app import AppConfig
    from litestar.datastructures import State


__all__ = ("QdrantPlugin",)


class QdrantPlugin(InitPluginProtocol):
    """Qdrant application initialize Plugin."""

    state_key: ClassVar[str] = "qdrant_factory"

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        self.setup_signature_namespaces(app_config)
        self.setup_states(app_config)
        self.setup_dependencies(app_config)

        return app_config

    def provide_qdrant_client(self, state: "State") -> "AsyncQdrantClient":
        return cast("QdrantClientFactory", state.get(self.state_key)).new()

    def setup_signature_namespaces(self, app_config: "AppConfig") -> None:
        app_config.signature_namespace.update(
            {
                "AsyncQdrantClient": AsyncQdrantClient,
                "QdrantClientFactory": QdrantClientFactory,
            }
        )

    def setup_states(self, app_config: "AppConfig") -> None:
        if self.state_key not in app_config.state:
            config = Config.get().qdrant

            app_config.state.update({self.state_key: QdrantClientFactory(config)})

    def setup_dependencies(self, app_config: "AppConfig") -> None:
        app_config.dependencies.update(
            {
                "qdrant_client": Provide(
                    self.provide_qdrant_client,
                    sync_to_thread=True,
                )
            },
        )
