"""Online-only room status cache behavior tests."""

from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError

from echocue.core.live import (
    MemoryRoomOnlineStatusCache,
    RedisRoomOnlineStatusCache,
    RoomOnlineStatusStruct,
    RoomStatusCacheUnavailableError,
)
from echocue.core.live import status as status_module


class FakeRedis:
    """Minimal expiring Redis fake used by the cache adapter tests."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or (lambda: 0.0)
        self.values: dict[str, bytes] = {}
        self.deadlines: dict[str, float] = {}

    async def set(self, name: str, value: bytes, *, ex: int) -> bool:
        self.values[name] = value
        self.deadlines[name] = self._clock() + ex
        return True

    async def get(self, name: str) -> bytes | None:
        if self._is_expired(name):
            self.values.pop(name, None)
            self.deadlines.pop(name, None)

        return self.values.get(name)

    async def expire(self, name: str, time: int, *, xx: bool) -> bool:
        if self._is_expired(name):
            self.values.pop(name, None)
            self.deadlines.pop(name, None)
        if name not in self.values:
            return False

        self.deadlines[name] = self._clock() + time
        return True

    async def delete(self, name: str) -> int:
        existed = name in self.values and not self._is_expired(name)
        self.values.pop(name, None)
        self.deadlines.pop(name, None)
        return int(existed)

    def ttl(self, name: str) -> int | None:
        if name not in self.deadlines or self._is_expired(name):
            return None

        return int(self.deadlines[name] - self._clock())

    def _is_expired(self, name: str) -> bool:
        deadline = self.deadlines.get(name)
        return deadline is not None and deadline <= self._clock()


class UnavailableRedis:
    """Redis fake that exposes a secret in its internal exception only."""

    @staticmethod
    async def set(_: str, __: bytes, *, ex: int) -> bool:
        raise ConnectionError("redis://user:secret-value@private-host:6379/0")

    @staticmethod
    async def get(_: str) -> bytes | None:
        raise ConnectionError("redis://user:secret-value@private-host:6379/0")

    @staticmethod
    async def expire(_: str, __: int, *, xx: bool) -> bool:
        raise ConnectionError("redis://user:secret-value@private-host:6379/0")

    @staticmethod
    async def delete(_: str) -> int:
        raise ConnectionError("redis://user:secret-value@private-host:6379/0")


class TestMemoryRoomOnlineStatusCache:
    async def test_write_renew_clear_and_natural_expiration(self) -> None:
        now = 100.0
        cache = MemoryRoomOnlineStatusCache(clock=lambda: now)
        status = _room_status()

        assert await cache.get(status.room_id) is None

        await cache.write(status)
        assert await cache.get(status.room_id) == status
        assert cache.expires_in(status.room_id) == 7_200

        now = 200.0
        assert await cache.renew(status.room_id) is True
        assert cache.expires_in(status.room_id) == 7_200

        now = 7_401.0
        assert await cache.get(status.room_id) is None
        assert await cache.renew(status.room_id) is False
        assert await cache.clear(status.room_id) is False

        await cache.write(status)
        assert await cache.clear(status.room_id) is True
        assert await cache.get(status.room_id) is None


class TestRedisRoomOnlineStatusCache:
    async def test_persists_only_online_metadata_with_two_hour_ttl(self) -> None:
        now = 100.0
        redis = FakeRedis(clock=lambda: now)
        cache = RedisRoomOnlineStatusCache(cast(Redis, redis))
        status = _room_status()

        await cache.write(status)

        key = f"ECHOCUE_ROOM_ONLINE_STATUS:{status.room_id}"
        assert await cache.get(status.room_id) == status
        assert redis.ttl(key) == 7_200
        assert b"offline" not in redis.values[key]

        now = 200.0
        assert await cache.renew(status.room_id) is True
        assert redis.ttl(key) == 7_200

        now = 7_401.0
        assert await cache.get(status.room_id) is None
        assert await cache.renew(status.room_id) is False

    async def test_clear_deletes_key_without_writing_offline_value(self) -> None:
        redis = FakeRedis()
        cache = RedisRoomOnlineStatusCache(cast(Redis, redis))
        status = _room_status()

        await cache.write(status)
        assert await cache.clear(status.room_id) is True
        assert redis.values == {}
        assert await cache.clear(status.room_id) is False

    @pytest.mark.parametrize(
        ("operation", "logged_operation"),
        [
            ("write", "write"),
            ("renew", "renew"),
            ("get", "read"),
            ("clear", "clear"),
        ],
    )
    async def test_unavailable_redis_raises_sanitized_error_and_log(
        self,
        monkeypatch: pytest.MonkeyPatch,
        operation: str,
        logged_operation: str,
    ) -> None:
        warning_calls: list[tuple[str, dict[str, object]]] = []
        logger = SimpleNamespace(
            warning=lambda event, **kwargs: warning_calls.append((event, kwargs)),
        )
        monkeypatch.setattr(status_module, "_LOGGER", logger)
        cache = RedisRoomOnlineStatusCache(cast(Redis, UnavailableRedis()))

        with pytest.raises(RoomStatusCacheUnavailableError, match="Room status cache is unavailable") as exc_info:
            if operation == "write":
                await cache.write(_room_status())
            elif operation == "renew":
                await cache.renew("room-a")
            elif operation == "get":
                await cache.get("room-a")
            else:
                await cache.clear("room-a")

        assert exc_info.value.status_code == 503
        assert "secret-value" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert warning_calls == [
            (
                "room status cache operation failed",
                {"extra": {"operation": logged_operation, "error_type": "ConnectionError"}},
            )
        ]

    async def test_corrupt_cached_value_uses_same_failure_boundary(self) -> None:
        redis = FakeRedis()
        redis.values["ECHOCUE_ROOM_ONLINE_STATUS:room-a"] = b'{"liveStatus":"offline"}'
        redis.deadlines["ECHOCUE_ROOM_ONLINE_STATUS:room-a"] = 7_200
        cache = RedisRoomOnlineStatusCache(cast(Redis, redis))

        with pytest.raises(RoomStatusCacheUnavailableError):
            await cache.get("room-a")


def _room_status() -> RoomOnlineStatusStruct:
    return RoomOnlineStatusStruct(
        room_id="room-a",
        live_started_at=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
        last_event_at=datetime(2026, 8, 20, 10, 0, 12, tzinfo=UTC),
        room_name="Demo room",
        anchor_name="Demo anchor",
        avatar_thumb="https://example.test/avatar.jpeg",
    )
