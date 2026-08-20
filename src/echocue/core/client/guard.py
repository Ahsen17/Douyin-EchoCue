"""User-to-client binding guards.

The Redis implementation keeps acquire, renewal, and release compare-and-act operations
atomic so stale sessions cannot mutate a newer client binding.
"""

from collections.abc import Callable
from time import monotonic
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import anyio
from redis.asyncio import Redis

if TYPE_CHECKING:
    from redis.commands.core import AsyncScript

__all__ = (
    "MemoryUserClientGuard",
    "RedisUserClientGuard",
    "UserClientGuard",
)


class UserClientGuard(Protocol):
    """Storage boundary for the single-client-per-user constraint."""

    async def acquire(self, user_id: UUID, client_id: UUID, *, expires_in: int) -> bool:
        """Acquire or renew a binding when it is free or owned by the same client."""

    async def renew(self, user_id: UUID, client_id: UUID, *, expires_in: int) -> bool:
        """Renew a binding only when it is still owned by the client."""

    async def release(self, user_id: UUID, client_id: UUID) -> bool:
        """Release a binding only when it is still owned by the client."""


class RedisUserClientGuard:
    """Redis-backed user-client guard with atomic ownership checks."""

    _ACQUIRE_SCRIPT = """
local current = redis.call('GET', KEYS[1])
if not current then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
    return 1
end
if current == ARGV[1] then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return 1
end
return 0
"""
    _RENEW_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    return 1
end
return 0
"""
    _RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    redis.call('DEL', KEYS[1])
    return 1
end
return 0
"""

    def __init__(self, redis: Redis, *, namespace: str = "ECHOCUE_USER_CLIENT_GUARDS") -> None:
        self._namespace = namespace
        self._acquire_script: AsyncScript = redis.register_script(self._ACQUIRE_SCRIPT)
        self._renew_script: AsyncScript = redis.register_script(self._RENEW_SCRIPT)
        self._release_script: AsyncScript = redis.register_script(self._RELEASE_SCRIPT)

    async def acquire(self, user_id: UUID, client_id: UUID, *, expires_in: int) -> bool:
        """Acquire or renew the user's binding atomically."""

        result = await self._acquire_script(keys=[self._key(user_id)], args=[str(client_id), expires_in])
        return bool(result)

    async def renew(self, user_id: UUID, client_id: UUID, *, expires_in: int) -> bool:
        """Renew the binding when its owner still matches."""

        result = await self._renew_script(keys=[self._key(user_id)], args=[str(client_id), expires_in])
        return bool(result)

    async def release(self, user_id: UUID, client_id: UUID) -> bool:
        """Release the binding when its owner still matches."""

        result = await self._release_script(keys=[self._key(user_id)], args=[str(client_id)])
        return bool(result)

    def _key(self, user_id: UUID) -> str:
        return f"{self._namespace}:{user_id}"


class MemoryUserClientGuard:
    """Concurrent in-memory guard for isolated tests and local fixtures."""

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._bindings: dict[UUID, tuple[UUID, float]] = {}
        self._lock = anyio.Lock()

    async def acquire(self, user_id: UUID, client_id: UUID, *, expires_in: int) -> bool:
        """Acquire or renew a binding under an in-process lock."""

        async with self._lock:
            binding = self._active_binding(user_id)
            if binding is not None and binding[0] != client_id:
                return False

            self._bindings[user_id] = (client_id, self._clock() + expires_in)
            return True

    async def renew(self, user_id: UUID, client_id: UUID, *, expires_in: int) -> bool:
        """Renew a binding under an in-process lock when ownership matches."""

        async with self._lock:
            binding = self._active_binding(user_id)
            if binding is None or binding[0] != client_id:
                return False

            self._bindings[user_id] = (client_id, self._clock() + expires_in)
            return True

    async def release(self, user_id: UUID, client_id: UUID) -> bool:
        """Release a binding under an in-process lock when ownership matches."""

        async with self._lock:
            binding = self._active_binding(user_id)
            if binding is None or binding[0] != client_id:
                return False

            del self._bindings[user_id]
            return True

    def expires_in(self, user_id: UUID) -> int | None:
        """Return the remaining binding lifetime for test assertions."""

        binding = self._active_binding(user_id)
        if binding is None:
            return None
        return max(0, int(binding[1] - self._clock()))

    def _active_binding(self, user_id: UUID) -> tuple[UUID, float] | None:
        binding = self._bindings.get(user_id)
        if binding is None:
            return None
        if binding[1] <= self._clock():
            del self._bindings[user_id]
            return None
        return binding
