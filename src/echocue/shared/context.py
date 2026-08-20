"""Request context structures and dependency providers.

This module builds request-scoped context from Litestar requests.
Context objects expose service-layer data only and never return database models.
"""

from typing import Any
from uuid import UUID

from litestar import Request
from litestar.exceptions import HTTPException, ImproperlyConfiguredException, NotAuthorizedException
from msgspec import field

from echocue.auth.client import create_auth_permission_client
from echocue.auth.enum import SessionClientType
from echocue.auth.schema import UserStruct
from echocue.auth.session import SessionIdentityStruct, parse_session_identity
from echocue.base import BaseStruct

__all__ = ("RequestContext",)


class RequestContext(BaseStruct):
    """Request-scoped context resolved from the current request."""

    user: UserStruct | None = None
    user_id: UUID | None = None
    client_type: SessionClientType | None = None
    client_id: UUID | None = None
    session: dict[str, Any] = field(default_factory=dict)
    is_authenticated: bool = False

    def require_client_id(self) -> UUID:
        """Return the client id or reject a non-client request context."""

        if not self.is_authenticated or self.client_type is not SessionClientType.CLIENT or self.client_id is None:
            raise NotAuthorizedException(detail="A client session is required.")

        return self.client_id

    def require_webui_session(self) -> None:
        """Reject a request context that does not represent a webui session."""

        if not self.is_authenticated or self.client_type is not SessionClientType.WEBUI or self.client_id is not None:
            raise NotAuthorizedException(detail="A webui session is required.")


async def provide_request_context(request: Request[Any, Any, Any]) -> RequestContext:
    """Build request context from authenticated user and session data."""

    user = _get_request_user(request)
    session = _get_request_session(request)
    identity = parse_session_identity(session)

    if identity is None:
        user = None
    elif user is None:
        user = await _get_session_user(identity)

    return RequestContext(
        user=user,
        user_id=user.id if user else None,
        client_type=identity.client_type if user and identity else None,
        client_id=identity.client_id if user and identity else None,
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


async def _get_session_user(identity: SessionIdentityStruct) -> UserStruct | None:
    """Resolve a user from session data."""

    try:
        context = await create_auth_permission_client().get_permission_context(identity.user_id)
    except HTTPException:
        return None

    user = context.user

    return user if user and user.is_active else None
