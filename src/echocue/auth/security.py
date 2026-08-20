"""Litestar session authentication configuration.

This module resolves server-side sessions to users and configures Litestar session authentication.
Authentication only identifies users; authorization rules should be added through guards.
"""

from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException, ServiceUnavailableException
from litestar.middleware.session.server_side import ServerSideSessionBackend, ServerSideSessionConfig
from litestar.security.session_auth import SessionAuth

from echocue.auth.client import create_auth_permission_client
from echocue.base import AuthConfig, Config

from .enum import SessionClientType
from .schema import UserStruct
from .session import parse_session_identity

if TYPE_CHECKING:
    from echocue.core.client import UserClientGuard

SESSION_EXCLUDE_PATHS = (
    r"^/system(?:/.*)?$",
    "/docs",
    "/openapi.json",
)
USER_CLIENT_GUARD_STATE_KEY = "user_client_guard"


async def retrieve_user_handler(session: dict[str, Any], connection: ASGIConnection) -> UserStruct | None:
    """Retrieve the authenticated user from session data."""

    identity = parse_session_identity(session)
    if identity is None:
        return None

    if not await _renew_client_binding(connection, identity.user_id, identity.client_type, identity.client_id):
        connection.clear_session()
        return None

    try:
        permission_context = await create_auth_permission_client().get_permission_context(identity.user_id)
    except NotAuthorizedException:
        await _release_invalid_client_binding(connection, identity.user_id, identity.client_type, identity.client_id)
        connection.clear_session()
        return None
    except ServiceUnavailableException:
        return None

    user = permission_context.user

    if user and user.is_active:
        return user

    await _release_invalid_client_binding(connection, identity.user_id, identity.client_type, identity.client_id)
    connection.clear_session()
    return None


async def _renew_client_binding(
    connection: ASGIConnection,
    user_id: UUID,
    client_type: SessionClientType,
    client_id: UUID | None,
) -> bool:
    if client_type is not SessionClientType.CLIENT or client_id is None:
        return True

    guard = cast("UserClientGuard | None", connection.app.state.get(USER_CLIENT_GUARD_STATE_KEY))
    if guard is None:
        return True

    return await guard.renew(user_id, client_id, expires_in=Config.get().auth.session_max_age_seconds)


async def _release_invalid_client_binding(
    connection: ASGIConnection,
    user_id: UUID,
    client_type: SessionClientType,
    client_id: UUID | None,
) -> None:
    if client_type is not SessionClientType.CLIENT or client_id is None:
        return

    guard = cast("UserClientGuard | None", connection.app.state.get(USER_CLIENT_GUARD_STATE_KEY))
    if guard is not None:
        await guard.release(user_id, client_id)


def create_auth(config: AuthConfig | None = None) -> SessionAuth[UserStruct, ServerSideSessionBackend]:
    """Create the Litestar server-side session authentication config."""

    auth_config = config or Config.get().auth
    session_backend_config = ServerSideSessionConfig(
        key=auth_config.session_cookie_key,
        max_age=auth_config.session_max_age_seconds,
        renew_on_access=auth_config.session_renew_on_access,
        secure=auth_config.session_cookie_secure,
        httponly=auth_config.session_cookie_httponly,
        samesite=auth_config.session_cookie_samesite,
        exclude=list(SESSION_EXCLUDE_PATHS),
        store=auth_config.session_store_name,
    )

    return SessionAuth[UserStruct, ServerSideSessionBackend](
        session_backend_config=session_backend_config,
        retrieve_user_handler=retrieve_user_handler,
        exclude=list(SESSION_EXCLUDE_PATHS),
    )
