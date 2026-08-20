"""Injectable long-lived douyinLive WebSocket gateway."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol

from msgspec import DecodeError, ValidationError

from .enum import LiveStatusCode
from .exception import (
    DouyinLiveConnectionError,
    DouyinLiveConnectTimeoutError,
    DouyinLiveDisconnectedError,
    DouyinLiveFirstStatusError,
    DouyinLiveFirstStatusTimeoutError,
    DouyinLiveProtocolError,
)
from .schema import LiveCommentEventStruct, LiveStatusEventStruct
from .source import DouyinLiveCommentSource

__all__ = (
    "DouyinLiveConnection",
    "DouyinLiveEvent",
    "DouyinLiveGateway",
    "DouyinLiveSocket",
)


type DouyinLiveEvent = LiveCommentEventStruct | LiveStatusEventStruct


class DouyinLiveSocket(Protocol):
    """Minimal upstream socket contract used by the gateway."""

    async def recv(self) -> str | bytes:
        """Receive one raw upstream message."""

    async def close(self) -> None:
        """Close the upstream socket."""


Connector = Callable[[str, float], Awaitable[DouyinLiveSocket]]


async def _default_connector(url: str, timeout: float) -> DouyinLiveSocket:
    from websockets.asyncio.client import connect  # noqa: PLC0415

    return await connect(url, open_timeout=timeout)


class DouyinLiveConnection:
    """Runtime-owned handle for one continuously consumed upstream socket."""

    def __init__(self, socket: DouyinLiveSocket, source: DouyinLiveCommentSource, room_id: str) -> None:
        self._socket = socket
        self._source = source
        self._room_id = room_id
        self._pending: DouyinLiveEvent | None = None
        self._closed = False

    async def wait_for_online(self, timeout: float) -> LiveStatusEventStruct:
        """Wait for and retain the first ROOM_ONLINE event."""

        try:
            event = await asyncio.wait_for(self._read_until_status(), timeout)
        except TimeoutError as exc:
            raise DouyinLiveFirstStatusTimeoutError from exc
        if event.payload.code is not LiveStatusCode.ROOM_ONLINE:
            await self.close()
            raise DouyinLiveFirstStatusError(event.payload.code.value)
        self._pending = event
        return event

    async def events(self) -> AsyncIterator[DouyinLiveEvent]:
        """Yield the retained first event and all subsequent valid events."""

        if self._pending is not None:
            pending, self._pending = self._pending, None
            yield pending
        while not self._closed:
            try:
                raw_message = await self._socket.recv()
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as exc:
                await self.close()
                raise DouyinLiveDisconnectedError from exc
            event = self._parse(raw_message)
            if event is not None:
                yield event

    async def close(self) -> None:
        """Close the upstream socket idempotently."""

        if self._closed:
            return
        self._closed = True
        await self._socket.close()

    async def _read_until_status(self) -> LiveStatusEventStruct:
        while True:
            try:
                raw_message = await self._socket.recv()
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as exc:
                await self.close()
                raise DouyinLiveDisconnectedError from exc
            event = self._parse(raw_message)
            if isinstance(event, LiveStatusEventStruct):
                return event

    def _parse(self, raw_message: str | bytes) -> DouyinLiveEvent | None:
        try:
            status = self._source.parse_live_status(raw_message, room_id=self._room_id)
            if status is not None:
                return status
            return self._source.parse_comment(raw_message, room_id=self._room_id)
        except (DecodeError, ValidationError, UnicodeDecodeError, TypeError, ValueError) as exc:
            raise DouyinLiveProtocolError from exc


class DouyinLiveGateway:
    """Create runtime-owned douyinLive connections without hard-coding transport."""

    def __init__(
        self,
        *,
        source: DouyinLiveCommentSource | None = None,
        connector: Connector | None = None,
        connect_timeout: float = 10.0,
        first_status_timeout: float = 10.0,
    ) -> None:
        self._source = source or DouyinLiveCommentSource()
        self._connector = connector or _default_connector
        self._connect_timeout = connect_timeout
        self._first_status_timeout = first_status_timeout

    async def connect(self, room_identifier: str) -> DouyinLiveConnection:
        """Establish a socket and verify its first live status."""

        try:
            socket = await self._connector(self._source.build_url(room_identifier), self._connect_timeout)
        except TimeoutError as exc:
            raise DouyinLiveConnectTimeoutError from exc
        except Exception as exc:
            raise DouyinLiveConnectionError from exc

        connection = DouyinLiveConnection(socket, self._source, room_identifier)
        try:
            await connection.wait_for_online(self._first_status_timeout)
        except BaseException:
            await connection.close()
            raise
        return connection
