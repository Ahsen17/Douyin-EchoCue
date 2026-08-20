"""One-time remediation capability behavior tests."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import anyio
import pytest
from redis.asyncio import Redis

from echocue.core.client import (
    MemoryRemediationStore,
    RedisRemediationStore,
    RemediationHandler,
    RemediationIssueType,
    RemediationLinkCreate,
    RuntimeErrorCode,
)
from echocue.core.client.exception import RemediationNotAvailableError, RemediationTokenInvalidError

USER_ID = UUID("00000000-0000-7000-8000-000000000001")
OTHER_USER_ID = UUID("00000000-0000-7000-8000-000000000002")
CLIENT_ID = UUID("00000000-0000-7000-8000-000000000003")
OTHER_CLIENT_ID = UUID("00000000-0000-7000-8000-000000000004")


class FakeRedis:
    """Minimal Redis fake for persistence and consume-script behavior."""

    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    async def set(self, name: str, value: bytes, *, ex: int) -> bool:
        self.values[name] = value
        return ex > 0

    async def get(self, name: str) -> bytes | None:
        return self.values.get(name)

    def register_script(self, _: str) -> Callable[..., Awaitable[bytes | None]]:
        async def consume(*, keys: list[str]) -> bytes | None:
            return self.values.pop(keys[0], None)

        return consume


class TestRemediationHandler:
    async def test_creates_and_consumes_exact_failure_once(self) -> None:
        now = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)
        handler = RemediationHandler(
            MemoryRemediationStore(clock=lambda: now),
            remediation_url="https://webui.example.test/remediation?source=client",
            clock=lambda: now,
            token_factory=lambda: "secret-token",
        )
        await handler.record_failure(
            USER_ID,
            CLIENT_ID,
            "room-a",
            RuntimeErrorCode.PERSONA_NOT_PUBLISHED,
            RemediationIssueType.PERSONA,
        )

        link = await handler.create_link(USER_ID, CLIENT_ID, _persona_request())
        query = parse_qs(urlsplit(link.url).query)
        assert link.expires_in == 900
        assert query == {"source": ["client"], "token": ["secret-token"]}

        context = await handler.consume_token("secret-token")
        assert context.room_id == "room-a"
        assert context.issue_type is RemediationIssueType.PERSONA
        assert context.route == "/rooms/{roomId}/persona"
        assert context.params == {"roomId": "room-a"}
        assert context.expires_at == now + timedelta(minutes=15)

        with pytest.raises(RemediationTokenInvalidError):
            await handler.consume_token("secret-token")

    @pytest.mark.parametrize(
        ("user_id", "client_id", "payload"),
        [
            (OTHER_USER_ID, CLIENT_ID, None),
            (USER_ID, OTHER_CLIENT_ID, None),
            (
                USER_ID,
                CLIENT_ID,
                RemediationLinkCreate(
                    room_id="room-b",
                    error_code=RuntimeErrorCode.PERSONA_NOT_PUBLISHED,
                    issue_type=RemediationIssueType.PERSONA,
                ),
            ),
            (
                USER_ID,
                CLIENT_ID,
                RemediationLinkCreate(
                    room_id="room-a",
                    error_code=RuntimeErrorCode.RULE_CONFLICT,
                    issue_type=RemediationIssueType.RULE,
                ),
            ),
        ],
    )
    async def test_rejects_cross_identity_room_and_issue_mismatches(
        self,
        user_id: UUID,
        client_id: UUID,
        payload: RemediationLinkCreate | None,
    ) -> None:
        handler = RemediationHandler(MemoryRemediationStore(), remediation_url="https://webui.example.test/remediation")
        await handler.record_failure(
            USER_ID,
            CLIENT_ID,
            "room-a",
            RuntimeErrorCode.PERSONA_NOT_PUBLISHED,
            RemediationIssueType.PERSONA,
        )

        with pytest.raises(RemediationNotAvailableError):
            await handler.create_link(user_id, client_id, payload or _persona_request())

    async def test_expired_and_forged_tokens_are_rejected(self) -> None:
        now = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)
        handler = RemediationHandler(
            MemoryRemediationStore(clock=lambda: now),
            remediation_url="https://webui.example.test/remediation",
            clock=lambda: now,
            token_factory=lambda: "expiring-token",
        )
        await handler.record_failure(
            USER_ID,
            CLIENT_ID,
            "room-a",
            RuntimeErrorCode.PERSONA_NOT_PUBLISHED,
            RemediationIssueType.PERSONA,
        )
        await handler.create_link(USER_ID, CLIENT_ID, _persona_request())

        with pytest.raises(RemediationTokenInvalidError):
            await handler.consume_token("forged-token")

        now += timedelta(minutes=16)
        with pytest.raises(RemediationTokenInvalidError):
            await handler.consume_token("expiring-token")

    async def test_concurrent_double_consume_has_one_success(self) -> None:
        handler = RemediationHandler(
            MemoryRemediationStore(),
            remediation_url="https://webui.example.test/remediation",
            token_factory=lambda: "single-use-token",
        )
        await handler.record_failure(
            USER_ID,
            CLIENT_ID,
            "room-a",
            RuntimeErrorCode.PERSONA_NOT_PUBLISHED,
            RemediationIssueType.PERSONA,
        )
        await handler.create_link(USER_ID, CLIENT_ID, _persona_request())
        outcomes: list[str] = []

        async def consume() -> None:
            try:
                await handler.consume_token("single-use-token")
            except RemediationTokenInvalidError:
                outcomes.append("rejected")
            else:
                outcomes.append("consumed")

        async with anyio.create_task_group() as task_group:
            _ = task_group.start_soon(consume)
            _ = task_group.start_soon(consume)

        assert sorted(outcomes) == ["consumed", "rejected"]

    async def test_permission_failure_cannot_be_recorded_as_remediation(self) -> None:
        handler = RemediationHandler(MemoryRemediationStore(), remediation_url="https://webui.example.test/remediation")

        with pytest.raises(ValueError, match="Unsupported remediation failure"):
            await handler.record_failure(
                USER_ID,
                CLIENT_ID,
                "room-a",
                RuntimeErrorCode.PERMISSION_DENIED,
                RemediationIssueType.PERSONA,
            )


class TestRedisRemediationStore:
    async def test_hashes_bearer_token_and_consumes_it_atomically(self) -> None:
        redis = FakeRedis()
        handler = RemediationHandler(
            RedisRemediationStore(cast(Redis, redis)),
            remediation_url="https://webui.example.test/remediation",
            token_factory=lambda: "raw-bearer-secret",
        )
        await handler.record_failure(
            USER_ID,
            CLIENT_ID,
            "room-a",
            RuntimeErrorCode.RULE_CONFLICT,
            RemediationIssueType.RULE,
        )
        await handler.create_link(
            USER_ID,
            CLIENT_ID,
            RemediationLinkCreate(
                room_id="room-a",
                error_code=RuntimeErrorCode.RULE_CONFLICT,
                issue_type=RemediationIssueType.RULE,
            ),
        )

        stored_material = " ".join([*redis.values, *(value.decode() for value in redis.values.values())])
        assert "raw-bearer-secret" not in stored_material

        context = await handler.consume_token("raw-bearer-secret")
        assert context.issue_type is RemediationIssueType.RULE
        with pytest.raises(RemediationTokenInvalidError):
            await handler.consume_token("raw-bearer-secret")


def _persona_request() -> RemediationLinkCreate:
    return RemediationLinkCreate(
        room_id="room-a",
        error_code=RuntimeErrorCode.PERSONA_NOT_PUBLISHED,
        issue_type=RemediationIssueType.PERSONA,
    )
