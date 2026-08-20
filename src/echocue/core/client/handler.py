"""Client HTTP session orchestration."""

from uuid import UUID

from echocue.auth.client import create_auth_permission_client
from echocue.auth.schema import LoginRequest, UserStruct

from .exception import ClientSessionConflictError
from .guard import UserClientGuard
from .schema import ClientSessionCreate

__all__ = ("ClientSessionHandler",)


class ClientSessionHandler:
    """Coordinate client authentication with the user-client guard."""

    def __init__(self, guard: UserClientGuard, *, session_max_age_seconds: int) -> None:
        self._guard = guard
        self._session_max_age_seconds = session_max_age_seconds

    async def create(self, data: ClientSessionCreate) -> UserStruct:
        """Authenticate credentials and acquire the user's client binding."""

        result = await create_auth_permission_client().authenticate(
            LoginRequest(username=data.username, password=data.password)
        )
        acquired = await self._guard.acquire(
            result.user.id,
            data.client_id,
            expires_in=self._session_max_age_seconds,
        )
        if not acquired:
            raise ClientSessionConflictError

        return result.user

    async def renew(self, user_id: UUID, client_id: UUID) -> bool:
        """Synchronize the guard lifetime with an authenticated HTTP access."""

        return await self._guard.renew(
            user_id,
            client_id,
            expires_in=self._session_max_age_seconds,
        )

    async def release(self, user_id: UUID, client_id: UUID) -> bool:
        """Release the current client binding without touching runtime state."""

        return await self._guard.release(user_id, client_id)
