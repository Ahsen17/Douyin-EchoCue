"""Runtime state, lease, and ownership guard behavior tests."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import anyio

from echocue.core.client import (
    ClientRuntimeState,
    MemoryClientRuntimeGuard,
    MemoryRuntimeStore,
    RuntimeContextStruct,
)


def _context() -> RuntimeContextStruct:
    now = datetime.now(UTC)
    return RuntimeContextStruct(
        runtime_id=uuid4(),
        user_id=uuid4(),
        session_id="session",
        client_id=uuid4(),
        room_id="room-1",
        started_at=now,
        last_heartbeat_at=now,
    )


class TestMemoryClientRuntimeGuard:
    async def test_acquires_renews_and_releases_both_dimensions(self) -> None:
        guard = MemoryClientRuntimeGuard()
        runtime = uuid4()
        client = uuid4()

        assert await guard.acquire(runtime, client, "room", expires_in=60)
        assert await guard.renew(runtime, client, "room", expires_in=60)
        assert await guard.release(runtime, client, "room")
        assert guard.expires_in(client, "room") is None

    async def test_stale_release_does_not_delete_new_runtime(self) -> None:
        guard = MemoryClientRuntimeGuard()
        runtime = uuid4()
        client = uuid4()
        assert await guard.acquire(runtime, client, "room", expires_in=60)
        assert await guard.release(uuid4(), client, "room") is False
        assert await guard.renew(runtime, client, "room", expires_in=60)

    async def test_concurrent_client_and_room_acquire_has_one_winner(self) -> None:
        guard = MemoryClientRuntimeGuard()
        client = uuid4()
        results: list[bool] = []

        async def acquire(runtime: UUID, room: str) -> None:
            results.append(await guard.acquire(runtime, client, room, expires_in=60))

        async with anyio.create_task_group() as group:
            _ = group.start_soon(acquire, uuid4(), "room")
            _ = group.start_soon(acquire, uuid4(), "room")

        assert sorted(results) == [False, True]


class TestMemoryRuntimeStore:
    async def test_state_machine_and_idempotent_stop(self) -> None:
        store = MemoryRuntimeStore()
        context = _context()
        assert await store.create(context, expires_in=60)
        assert await store.transition(context.runtime_id, ClientRuntimeState.STARTING, ClientRuntimeState.ACTIVE)
        assert await store.transition(context.runtime_id, ClientRuntimeState.ACTIVE, ClientRuntimeState.RECONNECTING)
        assert await store.transition(context.runtime_id, ClientRuntimeState.RECONNECTING, ClientRuntimeState.ACTIVE)
        assert await store.transition(context.runtime_id, ClientRuntimeState.ACTIVE, ClientRuntimeState.STOPPED) is None
        stopped = await store.stop(context.runtime_id, "client_stopped")
        assert stopped is not None and stopped.status == ClientRuntimeState.STOPPED
        assert await store.stop(context.runtime_id, "second_stop") == stopped

    async def test_expired_runtime_is_not_returned(self) -> None:
        now = 100.0
        store = MemoryRuntimeStore(clock=lambda: now)
        context = _context()
        assert await store.create(context, expires_in=10)
        now = 111.0
        assert await store.get(context.runtime_id) is None
