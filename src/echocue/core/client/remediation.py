"""One-time remediation capabilities for client startup failures."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

import anyio
import msgspec
from redis.asyncio import Redis
from redis.exceptions import RedisError

from echocue.base import BaseStruct

from .enum import RemediationIssueType, RuntimeErrorCode
from .exception import RemediationNotAvailableError, RemediationStoreUnavailableError, RemediationTokenInvalidError
from .schema import RemediationContextVO, RemediationLinkCreate, RemediationLinkVO

__all__ = (
    "MemoryRemediationStore",
    "RedisRemediationStore",
    "RemediationFailureStruct",
    "RemediationHandler",
    "RemediationStore",
)


class RemediationFailureStruct(BaseStruct):
    """Latest remediable runtime failure bound to a client identity."""

    user_id: UUID
    client_id: UUID
    room_id: str
    error_code: RuntimeErrorCode
    issue_type: RemediationIssueType
    route: str
    params: dict[str, str]


class _RemediationTokenStruct(BaseStruct):
    user_id: UUID
    client_id: UUID
    room_id: str
    issue_type: RemediationIssueType
    route: str
    params: dict[str, str]
    expires_at: datetime


class RemediationStore(Protocol):
    """Persistence boundary for latest failures and one-time tokens."""

    async def record_failure(self, failure: RemediationFailureStruct, *, expires_in: int) -> None:
        """Replace the client's latest remediable failure."""

    async def get_latest_failure(self, user_id: UUID, client_id: UUID) -> RemediationFailureStruct | None:
        """Return the latest active failure for an exact client identity."""

    async def store_token(self, token: str, context: _RemediationTokenStruct, *, expires_in: int) -> None:
        """Persist a token capability without storing its bearer value."""

    async def consume_token(self, token: str) -> _RemediationTokenStruct | None:
        """Atomically consume a token at most once."""


class RedisRemediationStore:
    """Redis-backed remediation store with atomic token consumption."""

    _CONSUME_SCRIPT = """
local value = redis.call('GET', KEYS[1])
if value then
    redis.call('DEL', KEYS[1])
end
return value
"""

    def __init__(self, redis: Redis, *, namespace: str = "ECHOCUE_REMEDIATION") -> None:
        self._redis = redis
        self._namespace = namespace
        self._consume_script = redis.register_script(self._CONSUME_SCRIPT)

    async def record_failure(self, failure: RemediationFailureStruct, *, expires_in: int) -> None:
        try:
            await self._redis.set(
                self._failure_key(failure.user_id, failure.client_id), msgspec.json.encode(failure), ex=expires_in
            )
        except RedisError:
            raise RemediationStoreUnavailableError from None

    async def get_latest_failure(self, user_id: UUID, client_id: UUID) -> RemediationFailureStruct | None:
        try:
            value = await self._redis.get(self._failure_key(user_id, client_id))
            return None if value is None else msgspec.json.decode(value, type=RemediationFailureStruct)
        except (RedisError, msgspec.DecodeError):
            raise RemediationStoreUnavailableError from None

    async def store_token(self, token: str, context: _RemediationTokenStruct, *, expires_in: int) -> None:
        try:
            await self._redis.set(self._token_key(token), msgspec.json.encode(context), ex=expires_in)
        except RedisError:
            raise RemediationStoreUnavailableError from None

    async def consume_token(self, token: str) -> _RemediationTokenStruct | None:
        try:
            value = await self._consume_script(keys=[self._token_key(token)])
            return None if value is None else msgspec.json.decode(value, type=_RemediationTokenStruct)
        except (RedisError, msgspec.DecodeError):
            raise RemediationStoreUnavailableError from None

    def _failure_key(self, user_id: UUID, client_id: UUID) -> str:
        return f"{self._namespace}:LATEST:{user_id}:{client_id}"

    def _token_key(self, token: str) -> str:
        return f"{self._namespace}:TOKEN:{sha256(token.encode()).hexdigest()}"


class MemoryRemediationStore:
    """Deterministic concurrent remediation store for isolated tests."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._failures: dict[tuple[UUID, UUID], tuple[RemediationFailureStruct, datetime]] = {}
        self._tokens: dict[str, tuple[_RemediationTokenStruct, datetime]] = {}
        self._lock = anyio.Lock()

    async def record_failure(self, failure: RemediationFailureStruct, *, expires_in: int) -> None:
        async with self._lock:
            self._failures[(failure.user_id, failure.client_id)] = (
                failure,
                self._clock() + timedelta(seconds=expires_in),
            )

    async def get_latest_failure(self, user_id: UUID, client_id: UUID) -> RemediationFailureStruct | None:
        async with self._lock:
            key = (user_id, client_id)
            stored = self._failures.get(key)
            if stored is None:
                return None
            if stored[1] <= self._clock():
                del self._failures[key]
                return None
            return stored[0]

    async def store_token(self, token: str, context: _RemediationTokenStruct, *, expires_in: int) -> None:
        async with self._lock:
            self._tokens[_token_digest(token)] = (context, self._clock() + timedelta(seconds=expires_in))

    async def consume_token(self, token: str) -> _RemediationTokenStruct | None:
        async with self._lock:
            stored = self._tokens.pop(_token_digest(token), None)
            if stored is None or stored[1] <= self._clock():
                return None
            return stored[0]


class RemediationHandler:
    """Issue and consume narrowly scoped remediation capabilities."""

    def __init__(
        self,
        store: RemediationStore,
        *,
        remediation_url: str,
        token_ttl_seconds: int = 15 * 60,
        failure_ttl_seconds: int = 8 * 60 * 60,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._remediation_url = remediation_url
        self._token_ttl_seconds = token_ttl_seconds
        self._failure_ttl_seconds = failure_ttl_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_factory = token_factory or (lambda: token_urlsafe(32))

    async def record_failure(
        self,
        user_id: UUID,
        client_id: UUID,
        room_id: str,
        error_code: RuntimeErrorCode,
        issue_type: RemediationIssueType,
    ) -> None:
        """Record a remediable failure after runtime permission checks pass."""

        route = _route_for(error_code, issue_type)
        await self._store.record_failure(
            RemediationFailureStruct(
                user_id=user_id,
                client_id=client_id,
                room_id=room_id,
                error_code=error_code,
                issue_type=issue_type,
                route=route,
                params={"roomId": room_id},
            ),
            expires_in=self._failure_ttl_seconds,
        )

    async def create_link(
        self,
        user_id: UUID,
        client_id: UUID,
        data: RemediationLinkCreate,
    ) -> RemediationLinkVO:
        """Create a token only for the exact latest remediable failure."""

        latest = await self._store.get_latest_failure(user_id, client_id)
        expected = (user_id, client_id, data.room_id, data.error_code, data.issue_type)
        actual = (
            None
            if latest is None
            else (
                latest.user_id,
                latest.client_id,
                latest.room_id,
                latest.error_code,
                latest.issue_type,
            )
        )
        if actual != expected or latest is None:
            raise RemediationNotAvailableError

        token = self._token_factory()
        expires_at = self._clock() + timedelta(seconds=self._token_ttl_seconds)
        await self._store.store_token(
            token,
            _RemediationTokenStruct(
                user_id=latest.user_id,
                client_id=latest.client_id,
                room_id=latest.room_id,
                issue_type=latest.issue_type,
                route=latest.route,
                params=latest.params,
                expires_at=expires_at,
            ),
            expires_in=self._token_ttl_seconds,
        )
        return RemediationLinkVO(
            url=_url_with_token(self._remediation_url, token),
            expires_in=self._token_ttl_seconds,
        )

    async def consume_token(self, token: str) -> RemediationContextVO:
        """Consume a bearer capability and expose only its bounded page context."""

        context = await self._store.consume_token(token)
        if context is None or context.expires_at <= self._clock():
            raise RemediationTokenInvalidError

        return RemediationContextVO(
            room_id=context.room_id,
            issue_type=context.issue_type,
            route=context.route,
            params=context.params,
            expires_at=context.expires_at,
        )


def _route_for(error_code: RuntimeErrorCode, issue_type: RemediationIssueType) -> str:
    supported = {
        (RuntimeErrorCode.PERSONA_NOT_PUBLISHED, RemediationIssueType.PERSONA): "/rooms/{roomId}/persona",
        (RuntimeErrorCode.RULE_CONFLICT, RemediationIssueType.RULE): "/rooms/{roomId}/rules",
    }
    try:
        return supported[(error_code, issue_type)]
    except KeyError:
        raise ValueError("Unsupported remediation failure.") from None


def _token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def _url_with_token(url: str, token: str) -> str:
    parts = urlsplit(url)
    query = [*parse_qsl(parts.query, keep_blank_values=True), ("token", token)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
