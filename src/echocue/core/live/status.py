"""Online-only room status cache boundaries.

Cache presence represents a live room and cache absence represents an offline room.
No offline sentinel is persisted by either implementation.
"""

from collections.abc import Callable
from datetime import datetime
from time import monotonic
from typing import NoReturn, Protocol

import anyio
import structlog
from msgspec import DecodeError, ValidationError, json
from redis.asyncio import Redis
from redis.exceptions import RedisError

from echocue.base import BaseStruct

from .exception import RoomStatusCacheUnavailableError

__all__ = (
    "MemoryRoomOnlineStatusCache",
    "RedisRoomOnlineStatusCache",
    "RoomOnlineStatusCache",
    "RoomOnlineStatusStruct",
)


_LOGGER = structlog.stdlib.get_logger(__name__)


class RoomOnlineStatusStruct(BaseStruct):
    """Display metadata retained while a room is known to be live."""

    room_id: str
    live_started_at: datetime
    last_event_at: datetime
    room_name: str | None = None
    anchor_name: str | None = None
    avatar_thumb: str | None = None


class RoomOnlineStatusCache(Protocol):
    """Storage boundary for online-only room display status."""

    async def write(self, status: RoomOnlineStatusStruct) -> None:
        """Write live room metadata and start or refresh its cache lifetime."""

    async def renew(self, room_id: str) -> bool:
        """Refresh an existing live room entry without creating one."""

    async def get(self, room_id: str) -> RoomOnlineStatusStruct | None:
        """Return live room metadata, or no entry when the room is offline."""

    async def clear(self, room_id: str) -> bool:
        """Delete an online entry without writing an offline sentinel."""


class RedisRoomOnlineStatusCache:
    """Redis-backed online room cache with sanitized failure handling."""

    def __init__(
        self,
        redis: Redis,
        *,
        ttl_seconds: int = 7_200,
        namespace: str = "ECHOCUE_ROOM_ONLINE_STATUS",
    ) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds
        self._namespace = namespace

    async def write(self, status: RoomOnlineStatusStruct) -> None:
        """Write live room metadata with the configured lifetime."""

        try:
            await self._redis.set(self._key(status.room_id), status.to_jsonb(), ex=self._ttl_seconds)
        except RedisError as exc:
            self._raise_unavailable("write", exc)

    async def renew(self, room_id: str) -> bool:
        """Refresh the lifetime only when the room still has an online entry."""

        try:
            return bool(await self._redis.expire(self._key(room_id), self._ttl_seconds, xx=True))
        except RedisError as exc:
            self._raise_unavailable("renew", exc)

    async def get(self, room_id: str) -> RoomOnlineStatusStruct | None:
        """Read live metadata, treating an absent key as offline."""

        try:
            raw_status = await self._redis.get(self._key(room_id))
        except RedisError as exc:
            self._raise_unavailable("read", exc)

        if raw_status is None:
            return None

        try:
            return json.decode(raw_status, type=RoomOnlineStatusStruct)
        except (DecodeError, ValidationError) as exc:
            self._raise_unavailable("decode", exc)

    async def clear(self, room_id: str) -> bool:
        """Delete the online entry and never persist an offline value."""

        try:
            return bool(await self._redis.delete(self._key(room_id)))
        except RedisError as exc:
            self._raise_unavailable("clear", exc)

    def _key(self, room_id: str) -> str:
        return f"{self._namespace}:{room_id}"

    @staticmethod
    def _raise_unavailable(operation: str, exc: Exception) -> NoReturn:
        _LOGGER.warning(
            "room status cache operation failed",
            extra={"operation": operation, "error_type": type(exc).__name__},
        )
        raise RoomStatusCacheUnavailableError from None


class MemoryRoomOnlineStatusCache:
    """Concurrent deterministic room status cache for isolated tests."""

    def __init__(self, *, ttl_seconds: int = 7_200, clock: Callable[[], float] = monotonic) -> None:
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[str, tuple[RoomOnlineStatusStruct, float]] = {}
        self._lock = anyio.Lock()

    async def write(self, status: RoomOnlineStatusStruct) -> None:
        """Write live room metadata under an in-process lock."""

        async with self._lock:
            self._entries[status.room_id] = (status, self._clock() + self._ttl_seconds)

    async def renew(self, room_id: str) -> bool:
        """Refresh an existing entry under an in-process lock."""

        async with self._lock:
            status = self._active_status(room_id)
            if status is None:
                return False

            self._entries[room_id] = (status, self._clock() + self._ttl_seconds)
            return True

    async def get(self, room_id: str) -> RoomOnlineStatusStruct | None:
        """Return active live metadata or no value for an offline room."""

        async with self._lock:
            return self._active_status(room_id)

    async def clear(self, room_id: str) -> bool:
        """Delete an active online entry without creating a replacement."""

        async with self._lock:
            if self._active_status(room_id) is None:
                return False

            del self._entries[room_id]
            return True

    def expires_in(self, room_id: str) -> int | None:
        """Return the remaining entry lifetime for deterministic assertions."""

        status = self._active_status(room_id)
        if status is None:
            return None

        return max(0, int(self._entries[room_id][1] - self._clock()))

    def _active_status(self, room_id: str) -> RoomOnlineStatusStruct | None:
        entry = self._entries.get(room_id)
        if entry is None:
            return None
        if entry[1] <= self._clock():
            del self._entries[room_id]
            return None

        return entry[0]
