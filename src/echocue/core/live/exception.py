"""Live-domain business exceptions."""

from litestar.status_codes import HTTP_503_SERVICE_UNAVAILABLE

from echocue.shared import ApplicationError

__all__ = (
    "DouyinLiveConnectTimeoutError",
    "DouyinLiveConnectionError",
    "DouyinLiveDisconnectedError",
    "DouyinLiveFirstStatusError",
    "DouyinLiveFirstStatusTimeoutError",
    "DouyinLiveGatewayError",
    "DouyinLiveProtocolError",
    "RoomStatusCacheUnavailableError",
)


class DouyinLiveGatewayError(Exception):
    """Base class for failures owned by the douyinLive gateway."""


class DouyinLiveConnectionError(DouyinLiveGatewayError):
    """The upstream WebSocket could not be established."""


class DouyinLiveConnectTimeoutError(DouyinLiveConnectionError):
    """The upstream WebSocket did not establish before its deadline."""


class DouyinLiveProtocolError(DouyinLiveGatewayError):
    """The upstream sent malformed JSON or an invalid message payload."""


class DouyinLiveFirstStatusTimeoutError(DouyinLiveGatewayError):
    """No usable first room status arrived before its deadline."""


class DouyinLiveFirstStatusError(DouyinLiveGatewayError):
    """The first usable room status was not ROOM_ONLINE."""


class DouyinLiveDisconnectedError(DouyinLiveGatewayError):
    """The upstream closed before the runtime explicitly stopped it."""


class RoomStatusCacheUnavailableError(ApplicationError):
    """Raised when the room online-status cache cannot serve an operation."""

    def __init__(self) -> None:
        """Initialize a sanitized service-unavailable error."""

        super().__init__(
            message="Room status cache is unavailable.",
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
        )
