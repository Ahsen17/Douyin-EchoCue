"""Room-domain dependency registration."""

from typing import TYPE_CHECKING

from litestar.di import Provide
from litestar.plugins import InitPluginProtocol

from echocue.auth.client import create_auth_permission_client
from echocue.core.live import RoomOnlineStatusCache
from echocue.core.room import RoomAggregationHandler

if TYPE_CHECKING:
    from litestar.config.app import AppConfig

__all__ = ("RoomPlugin",)


class RoomPlugin(InitPluginProtocol):
    """Register shared room-domain orchestration dependencies."""

    def on_app_init(self, app_config: "AppConfig") -> "AppConfig":
        """Register the room aggregation service provider."""

        app_config.signature_namespace.update({"RoomAggregationHandler": RoomAggregationHandler})
        app_config.dependencies["room_aggregation_handler"] = Provide(
            self.provide_room_aggregation_handler,
            sync_to_thread=False,
        )

        return app_config

    def provide_room_aggregation_handler(
        self,
        room_status_cache: RoomOnlineStatusCache,
    ) -> RoomAggregationHandler:
        """Build a room aggregator using the configured auth and cache adapters."""

        return RoomAggregationHandler(create_auth_permission_client(), room_status_cache)
