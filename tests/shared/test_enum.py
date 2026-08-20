"""Shared enum serialization tests."""

from enum import auto

from echocue.base import CamelizedBaseStruct
from echocue.shared import CamelizedStrEnum


class ExampleStatus(CamelizedStrEnum):
    """Example external status values."""

    ROOM_OFFLINE = auto()
    """The example room is offline."""

    LIVE = auto()
    """The example room is live."""


class ExamplePayload(CamelizedBaseStruct):
    """Example camelized response payload."""

    live_status: ExampleStatus


class TestCamelizedStrEnum:
    """Verify camelized enum serialization behavior."""

    def test_serializes_multiword_and_singleword_values(self) -> None:
        payload = ExamplePayload(live_status=ExampleStatus.ROOM_OFFLINE)

        assert ExampleStatus.ROOM_OFFLINE.value == "roomOffline"
        assert ExampleStatus.LIVE.value == "live"
        assert payload.to_dict() == {"liveStatus": "roomOffline"}
