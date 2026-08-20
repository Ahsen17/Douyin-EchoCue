"""Client protocol enums shared by HTTP and WebSocket boundaries."""

from enum import StrEnum, auto

from echocue.shared import CamelizedStrEnum

__all__ = (
    "ClientRuntimeStatus",
    "ClientRuntimeStopReason",
    "LiveStatus",
    "RemediationIssueType",
    "RoomKind",
    "RuntimeErrorCode",
    "RuntimeEventStatus",
)


class RuntimeErrorCode(CamelizedStrEnum):
    """Stable runtime error codes exposed to clients."""

    ROOM_OFFLINE = auto()
    """The selected room is not live."""

    DOUYINLIVE_UNAVAILABLE = auto()
    """The upstream live status service is unavailable."""

    RUNTIME_START_FAILED = auto()
    """The runtime could not be initialized."""

    PERSONA_NOT_PUBLISHED = auto()
    """The room has no published persona."""

    RULE_CONFLICT = auto()
    """Published safety rules contain a conflict."""

    UNAUTHENTICATED = auto()
    """The client session is missing or expired."""

    CLIENT_SESSION_CONFLICT = auto()
    """The user is bound to another client."""

    PERMISSION_DENIED = auto()
    """The user cannot start the selected room."""

    CLIENT_RUNTIME_ACTIVE = auto()
    """The client already owns an active runtime."""

    ROOM_ACTIVE_BY_OTHER_CLIENT = auto()
    """Another client owns the selected room runtime."""


class RoomKind(StrEnum):
    """Room ownership kinds exposed by room lists."""

    PERSONAL = auto()
    """A room owned by an individual user."""

    ORGANIZATION = auto()
    """A room owned by an organization."""


class LiveStatus(StrEnum):
    """Cached live-status values exposed by room lists."""

    LIVE = auto()
    """The room has a current online cache entry."""

    OFFLINE = auto()
    """The room has no current online cache entry."""


class RemediationIssueType(CamelizedStrEnum):
    """Issue categories supported by remediation links."""

    PERSONA = auto()
    """The room persona requires remediation."""

    RULE = auto()
    """The room safety rules require remediation."""

    LIVE_STATUS = auto()
    """The runtime stopped because the room status changed."""


class ClientRuntimeStatus(StrEnum):
    """Runtime states returned by lifecycle HTTP endpoints."""

    STARTING = auto()
    """The runtime was created and awaits a client WebSocket."""

    STOPPED = auto()
    """The runtime has stopped and released its resources."""


class ClientRuntimeStopReason(CamelizedStrEnum):
    """Stable reasons returned after runtime cleanup."""

    CLIENT_STOPPED = auto()
    """The client explicitly stopped the runtime."""


class RuntimeEventStatus(CamelizedStrEnum):
    """Business status events sent over the runtime WebSocket."""

    ROOM_ENDED = auto()
    """The live room ended and the runtime stopped."""

    RUNTIME_STOPPED = auto()
    """The server stopped the runtime."""

    CONNECTION_TIMEOUT = auto()
    """The heartbeat window expired and the runtime stopped."""
