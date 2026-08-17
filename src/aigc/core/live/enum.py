"""Live domain enums."""

from enum import StrEnum, auto

__all__ = (
    "LiveRoomStatus",
    "LiveStatusCode",
)


class LiveStatusCode(StrEnum):
    """External room status codes emitted by live event sources."""

    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list[str]) -> str:
        return name

    ROOM_ONLINE = auto()
    """The room has started or resumed livestreaming."""

    ROOM_ENDED = auto()
    """The room has ended the current livestream session."""

    ROOM_OFFLINE = auto()
    """The room is offline or unavailable for comment ingestion."""

    @classmethod
    def from_external(cls, value: str) -> "LiveStatusCode | None":
        """Normalize an external room status string."""

        normalized = value.strip().upper()
        if normalized in {"ONLINE", "LIVE", "ROOM_ONLINE"}:
            return cls.ROOM_ONLINE
        if normalized in {"ENDED", "END", "ROOM_ENDED"}:
            return cls.ROOM_ENDED
        if normalized in {"OFFLINE", "ROOM_OFFLINE"}:
            return cls.ROOM_OFFLINE

        return None


class LiveRoomStatus(StrEnum):
    """Normalized room status values used inside live processing."""

    ONLINE = auto()
    """The room is currently live."""

    ENDED = auto()
    """The current livestream session has ended."""

    OFFLINE = auto()
    """The room is currently offline."""

    @classmethod
    def from_code(cls, code: LiveStatusCode) -> "LiveRoomStatus":
        """Convert an external room status code to an internal status."""

        if code is LiveStatusCode.ROOM_ONLINE:
            return cls.ONLINE
        if code is LiveStatusCode.ROOM_ENDED:
            return cls.ENDED

        return cls.OFFLINE
