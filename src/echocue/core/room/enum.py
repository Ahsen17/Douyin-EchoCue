"""Room aggregation domain enums."""

from enum import StrEnum, auto

__all__ = ("RoomLiveStatus", "RoomStartBlockReason")


class RoomLiveStatus(StrEnum):
    """Cached display status for a room."""

    LIVE = auto()
    """The room has a current online cache entry."""

    OFFLINE = auto()
    """The room has no current online cache entry."""


class RoomStartBlockReason(StrEnum):
    """Static reasons that prevent starting a room assistant."""

    PERMISSION_DENIED = auto()
    """The user lacks START permission for the room."""

    PERSONA_NOT_PUBLISHED = auto()
    """The room has no published persona."""

    RULE_CONFLICT = auto()
    """The room safety rules contain a conflict."""
