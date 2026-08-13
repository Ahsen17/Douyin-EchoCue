"""Request context structures and dependency providers.

This module builds request-scoped context from Litestar requests.
Context objects expose service-layer data only and never return database models.
"""

from typing import Any
from uuid import UUID

from litestar import Request
from litestar.exceptions import ImproperlyConfiguredException
from msgspec import field

from aigc.auth.schema import UserStruct
from aigc.auth.security import SESSION_USER_ID_KEY
from aigc.auth.service import UserService
from aigc.base import BaseStruct

__all__ = ("RequestContext",)


class RequestContext(BaseStruct):
    """Request-scoped context resolved from the current request."""

    user: UserStruct | None = None
    user_id: UUID | None = None
    session: dict[str, Any] = field(default_factory=dict)
    is_authenticated: bool = False


async def provide_request_context(request: Request[Any, Any, Any]) -> RequestContext:
    """Build request context from authenticated user and session data."""

    user = _get_request_user(request)
    session = _get_request_session(request)

    if user is None:
        user = await _get_session_user(session)

    return RequestContext(
        user=user,
        user_id=user.id if user else None,
        session=session,
        is_authenticated=user is not None,
    )


def _get_request_user(request: Request[Any, Any, Any]) -> UserStruct | None:
    """Return the authenticated request user when available."""

    try:
        user = request.user
    except ImproperlyConfiguredException:
        return None

    return user if isinstance(user, UserStruct) else None


def _get_request_session(request: Request[Any, Any, Any]) -> dict[str, Any]:
    """Return the request session when session middleware is available."""

    try:
        return dict(request.session)
    except ImproperlyConfiguredException:
        return {}


async def _get_session_user(session: dict[str, Any]) -> UserStruct | None:
    """Resolve a user from session data."""

    raw_user_id = session.get(SESSION_USER_ID_KEY)
    if not isinstance(raw_user_id, str):
        return None

    try:
        user_id = UUID(raw_user_id)
    except ValueError:
        return None

    async with UserService.provide() as service:
        user = await service.get_by_id(user_id)

    return user if user and user.is_active else None
