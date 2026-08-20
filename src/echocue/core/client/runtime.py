"""Runtime lifecycle state, lease storage, and distributed ownership guards."""

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from time import monotonic
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

import anyio
from msgspec import field, json
from msgspec.structs import replace
from redis.asyncio import Redis

from echocue.base import BaseStruct

if TYPE_CHECKING:
    from redis.commands.core import AsyncScript

__all__ = (
    "ClientRuntimeGuard",
    "ClientRuntimeState",
    "MemoryClientRuntimeGuard",
    "MemoryRuntimeStore",
    "RedisClientRuntimeGuard",
    "RedisRuntimeStore",
    "RuntimeContextStruct",
    "RuntimeStore",
)


class ClientRuntimeState(StrEnum):
    """States used by the internal runtime lifecycle state machine."""

    STARTING = "starting"
    ACTIVE = "active"
    RECONNECTING = "reconnecting"
    STOPPING = "stopping"
    STOPPED = "stopped"


class RuntimeContextStruct(BaseStruct):
    """Runtime ownership and lifecycle context retained by the main service."""

    runtime_id: UUID
    user_id: UUID
    session_id: str
    client_id: UUID
    room_id: str
    persona_id: str | None = None
    persona_version: str | None = None
    rule_version: str | None = None
    status: str = ClientRuntimeState.STARTING
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    stop_reason: str | None = None


class ClientRuntimeGuard(Protocol):
    """Atomic ownership boundary for one client and one active room."""

    async def acquire(self, runtime_id: UUID, client_id: UUID, room_id: str, *, expires_in: int) -> bool:
        """Acquire both ownership keys or leave them unchanged."""

    async def renew(self, runtime_id: UUID, client_id: UUID, room_id: str, *, expires_in: int) -> bool:
        """Renew both keys only when they still belong to this runtime."""

    async def release(self, runtime_id: UUID, client_id: UUID, room_id: str) -> bool:
        """Release only keys still owned by this runtime."""


class RedisClientRuntimeGuard:
    """Redis-backed atomic client-runtime and active-room guard."""

    _ACQUIRE = """
local client = redis.call('GET', KEYS[1])
local room = redis.call('GET', KEYS[2])
if (not client or client == ARGV[1]) and (not room or room == ARGV[1]) then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
    redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[2])
    return 1
end
return 0
"""
    _RENEW = """
if redis.call('GET', KEYS[1]) == ARGV[1] and redis.call('GET', KEYS[2]) == ARGV[1] then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    redis.call('EXPIRE', KEYS[2], ARGV[2])
    return 1
end
return 0
"""
    _RELEASE = """
local released = 0
if redis.call('GET', KEYS[1]) == ARGV[1] then redis.call('DEL', KEYS[1]); released = 1 end
if redis.call('GET', KEYS[2]) == ARGV[1] then redis.call('DEL', KEYS[2]); released = 1 end
return released
"""

    def __init__(self, redis: Redis, *, namespace: str = "ECHOCUE_RUNTIME_GUARDS") -> None:
        self._redis = redis
        self._namespace = namespace
        self._acquire_script: AsyncScript = redis.register_script(self._ACQUIRE)
        self._renew_script: AsyncScript = redis.register_script(self._RENEW)
        self._release_script: AsyncScript = redis.register_script(self._RELEASE)

    async def acquire(self, runtime_id: UUID, client_id: UUID, room_id: str, *, expires_in: int) -> bool:
        """Acquire both guard keys atomically."""

        result = await self._acquire_script(
            keys=[self._client_key(client_id), self._room_key(room_id)], args=[str(runtime_id), expires_in]
        )
        return bool(result)

    async def renew(self, runtime_id: UUID, client_id: UUID, room_id: str, *, expires_in: int) -> bool:
        """Renew both guard keys when owned by this runtime."""

        result = await self._renew_script(
            keys=[self._client_key(client_id), self._room_key(room_id)], args=[str(runtime_id), expires_in]
        )
        return bool(result)

    async def release(self, runtime_id: UUID, client_id: UUID, room_id: str) -> bool:
        """Release stale-safe guard keys."""

        result = await self._release_script(
            keys=[self._client_key(client_id), self._room_key(room_id)], args=[str(runtime_id)]
        )
        return bool(result)

    def _client_key(self, client_id: UUID) -> str:
        return f"{self._namespace}:client:{client_id}"

    def _room_key(self, room_id: str) -> str:
        return f"{self._namespace}:room:{room_id}"


class MemoryClientRuntimeGuard:
    """Concurrent in-memory implementation used by tests and local fixtures."""

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._entries: dict[tuple[str, str], tuple[UUID, float]] = {}
        self._lock = anyio.Lock()

    async def acquire(self, runtime_id: UUID, client_id: UUID, room_id: str, *, expires_in: int) -> bool:
        """Acquire client and room ownership under one lock."""

        async with self._lock:
            self._purge()
            if any(
                (entry := self._entries.get(key)) is not None and entry[0] != runtime_id
                for key in (("client", str(client_id)), ("room", room_id))
            ):
                return False
            expiry = self._clock() + expires_in
            self._entries["client", str(client_id)] = runtime_id, expiry
            self._entries["room", room_id] = runtime_id, expiry
            return True

    async def renew(self, runtime_id: UUID, client_id: UUID, room_id: str, *, expires_in: int) -> bool:
        """Renew both ownership entries when still owned by this runtime."""

        async with self._lock:
            self._purge()
            if any(self._entries.get(key, (None, 0))[0] != runtime_id for key in (("client", str(client_id)), ("room", room_id))):
                return False
            expiry = self._clock() + expires_in
            self._entries["client", str(client_id)] = runtime_id, expiry
            self._entries["room", room_id] = runtime_id, expiry
            return True

    async def release(self, runtime_id: UUID, client_id: UUID, room_id: str) -> bool:
        """Release entries only when they still belong to this runtime."""

        async with self._lock:
            released = False
            for key in (("client", str(client_id)), ("room", room_id)):
                if self._entries.get(key, (None, 0))[0] == runtime_id:
                    del self._entries[key]
                    released = True
            return released

    def expires_in(self, client_id: UUID, room_id: str) -> int | None:
        """Return the remaining lease for assertions and diagnostics."""

        self._purge()
        entry = self._entries.get(("client", str(client_id)))
        room_entry = self._entries.get(("room", room_id))
        if entry is None or room_entry is None or entry[0] != room_entry[0]:
            return None
        return max(0, int(entry[1] - self._clock()))

    def _purge(self) -> None:
        now = self._clock()
        for key, (_, expiry) in list(self._entries.items()):
            if expiry <= now:
                del self._entries[key]


class RuntimeStore(Protocol):
    """Storage boundary for runtime contexts."""

    async def create(self, context: RuntimeContextStruct, *, expires_in: int) -> bool:
        """Create a runtime context if its identifier is unused."""

    async def get(self, runtime_id: UUID) -> RuntimeContextStruct | None:
        """Read a runtime context."""

    async def transition(self, runtime_id: UUID, expected: str, target: str) -> RuntimeContextStruct | None:
        """Apply one legal state transition, returning the updated context."""

    async def heartbeat(self, runtime_id: UUID, *, at: datetime | None = None) -> RuntimeContextStruct | None:
        """Update the heartbeat timestamp for a non-stopped runtime."""

    async def stop(self, runtime_id: UUID, reason: str) -> RuntimeContextStruct | None:
        """Stop a runtime idempotently and preserve its stop reason."""


_TRANSITIONS: dict[str, set[str]] = {
    ClientRuntimeState.STARTING: {ClientRuntimeState.ACTIVE, ClientRuntimeState.STOPPING, ClientRuntimeState.STOPPED},
    ClientRuntimeState.ACTIVE: {ClientRuntimeState.RECONNECTING, ClientRuntimeState.STOPPING},
    ClientRuntimeState.RECONNECTING: {ClientRuntimeState.ACTIVE, ClientRuntimeState.STOPPING},
    ClientRuntimeState.STOPPING: {ClientRuntimeState.STOPPED},
    ClientRuntimeState.STOPPED: set(),
}


class MemoryRuntimeStore:
    """Concurrent runtime context store with deterministic expiration."""

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._entries: dict[UUID, tuple[RuntimeContextStruct, float]] = {}
        self._lock = anyio.Lock()

    async def create(self, context: RuntimeContextStruct, *, expires_in: int) -> bool:
        """Create a runtime context once."""

        async with self._lock:
            self._purge()
            if context.runtime_id in self._entries:
                return False
            self._entries[context.runtime_id] = context, self._clock() + expires_in
            return True

    async def get(self, runtime_id: UUID) -> RuntimeContextStruct | None:
        """Read a non-expired runtime context."""

        async with self._lock:
            self._purge()
            entry = self._entries.get(runtime_id)
            return None if entry is None else entry[0]

    async def transition(self, runtime_id: UUID, expected: str, target: str) -> RuntimeContextStruct | None:
        """Apply a validated lifecycle transition."""

        async with self._lock:
            self._purge()
            entry = self._entries.get(runtime_id)
            if entry is None or entry[0].status != expected or target not in _TRANSITIONS.get(expected, set()):
                return None
            updated = replace(entry[0], status=target)
            self._entries[runtime_id] = updated, entry[1]
            return updated

    async def heartbeat(self, runtime_id: UUID, *, at: datetime | None = None) -> RuntimeContextStruct | None:
        """Update heartbeat time and retain the existing lease."""

        async with self._lock:
            self._purge()
            entry = self._entries.get(runtime_id)
            if entry is None or entry[0].status == ClientRuntimeState.STOPPED:
                return None
            updated = replace(entry[0], last_heartbeat_at=at or datetime.now(UTC))
            self._entries[runtime_id] = updated, entry[1]
            return updated

    async def stop(self, runtime_id: UUID, reason: str) -> RuntimeContextStruct | None:
        """Stop a runtime and make repeated stop calls harmless."""

        async with self._lock:
            self._purge()
            entry = self._entries.get(runtime_id)
            if entry is None:
                return None
            if entry[0].status == ClientRuntimeState.STOPPED:
                return entry[0]
            updated = replace(entry[0], status=ClientRuntimeState.STOPPED, stop_reason=reason)
            self._entries[runtime_id] = updated, entry[1]
            return updated

    def _purge(self) -> None:
        now = self._clock()
        for runtime_id, (_, expiry) in list(self._entries.items()):
            if expiry <= now:
                del self._entries[runtime_id]


class RedisRuntimeStore:
    """Redis-backed runtime context store."""

    def __init__(self, redis: Redis, *, namespace: str = "ECHOCUE_RUNTIMES") -> None:
        self._redis = redis
        self._namespace = namespace

    async def create(self, context: RuntimeContextStruct, *, expires_in: int) -> bool:
        """Create a context only when the runtime key is absent."""

        return bool(await self._redis.set(self._key(context.runtime_id), context.to_jsonb(), ex=expires_in, nx=True))

    async def get(self, runtime_id: UUID) -> RuntimeContextStruct | None:
        """Read a context from Redis."""

        value = await self._redis.get(self._key(runtime_id))
        return None if value is None else json.decode(value, type=RuntimeContextStruct)

    async def transition(self, runtime_id: UUID, expected: str, target: str) -> RuntimeContextStruct | None:
        """Apply a lifecycle transition with a compare-and-set transaction."""

        if target not in _TRANSITIONS.get(expected, set()):
            return None
        context = await self.get(runtime_id)
        if context is None or context.status != expected:
            return None
        updated = replace(context, status=target)
        await self._redis.set(self._key(runtime_id), updated.to_jsonb(), keepttl=True)
        return updated

    async def heartbeat(self, runtime_id: UUID, *, at: datetime | None = None) -> RuntimeContextStruct | None:
        """Refresh the heartbeat timestamp while retaining the Redis TTL."""

        context = await self.get(runtime_id)
        if context is None or context.status == ClientRuntimeState.STOPPED:
            return None
        updated = replace(context, last_heartbeat_at=at or datetime.now(UTC))
        await self._redis.set(self._key(runtime_id), updated.to_jsonb(), keepttl=True)
        return updated

    async def stop(self, runtime_id: UUID, reason: str) -> RuntimeContextStruct | None:
        """Mark a runtime stopped without deleting its audit context immediately."""

        context = await self.get(runtime_id)
        if context is None or context.status == ClientRuntimeState.STOPPED:
            return context
        updated = replace(context, status=ClientRuntimeState.STOPPED, stop_reason=reason)
        await self._redis.set(self._key(runtime_id), updated.to_jsonb(), keepttl=True)
        return updated

    def _key(self, runtime_id: UUID) -> str:
        return f"{self._namespace}:{runtime_id}"
