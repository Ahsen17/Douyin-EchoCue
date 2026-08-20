"""Room-domain plugin tests."""

from litestar.config.app import AppConfig
from pytest import MonkeyPatch

from echocue.core.live import MemoryRoomOnlineStatusCache
from echocue.core.room import RoomAggregationHandler
from echocue.server.plugin.room import RoomPlugin


class TestRoomPlugin:
    """Verify room-domain dependency registration."""

    def test_registers_room_aggregation_handler(self, monkeypatch: MonkeyPatch) -> None:
        auth_client = object()
        monkeypatch.setattr("echocue.server.plugin.room.create_auth_permission_client", lambda: auth_client)
        plugin = RoomPlugin()

        app_config = plugin.on_app_init(AppConfig())
        handler = plugin.provide_room_aggregation_handler(MemoryRoomOnlineStatusCache())

        assert "room_aggregation_handler" in app_config.dependencies
        assert "RoomAggregationHandler" in app_config.signature_namespace
        assert isinstance(handler, RoomAggregationHandler)
