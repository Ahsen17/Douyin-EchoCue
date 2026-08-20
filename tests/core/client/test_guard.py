"""User-client guard behavior tests."""

from uuid import UUID, uuid4

import anyio

from echocue.core.client import MemoryUserClientGuard


class TestMemoryUserClientGuard:
    async def test_acquires_renews_and_releases_same_client(self) -> None:
        now = 100.0
        guard = MemoryUserClientGuard(clock=lambda: now)
        user_id = uuid4()
        client_id = uuid4()

        assert await guard.acquire(user_id, client_id, expires_in=60) is True
        assert guard.expires_in(user_id) == 60

        now = 120.0
        assert await guard.renew(user_id, client_id, expires_in=60) is True
        assert guard.expires_in(user_id) == 60
        assert await guard.release(user_id, client_id) is True
        assert guard.expires_in(user_id) is None

    async def test_rejects_other_client_without_mutating_owner(self) -> None:
        guard = MemoryUserClientGuard()
        user_id = uuid4()
        owner_id = uuid4()
        other_id = uuid4()

        assert await guard.acquire(user_id, owner_id, expires_in=60) is True
        assert await guard.acquire(user_id, other_id, expires_in=60) is False
        assert await guard.renew(user_id, other_id, expires_in=60) is False
        assert await guard.release(user_id, other_id) is False
        assert await guard.renew(user_id, owner_id, expires_in=60) is True

    async def test_expired_binding_can_be_acquired_by_another_client(self) -> None:
        now = 100.0
        guard = MemoryUserClientGuard(clock=lambda: now)
        user_id = uuid4()

        assert await guard.acquire(user_id, uuid4(), expires_in=60) is True
        now = 161.0
        assert await guard.acquire(user_id, uuid4(), expires_in=60) is True

    async def test_concurrent_acquire_has_one_owner(self) -> None:
        guard = MemoryUserClientGuard()
        user_id = uuid4()
        client_ids = [uuid4(), uuid4()]
        results: list[bool] = []

        async def acquire(client_id: UUID) -> None:
            results.append(await guard.acquire(user_id, client_id, expires_in=60))

        async with anyio.create_task_group() as task_group:
            for client_id in client_ids:
                _ = task_group.start_soon(acquire, client_id)

        assert sorted(results) == [False, True]
