"""Litestar session authentication configuration.

This module resolves server-side sessions to users and configures Litestar session authentication.
Authentication only identifies users; authorization rules should be added through guards.
"""

from typing import Any
from uuid import UUID

from litestar.connection import ASGIConnection
from litestar.middleware.session.server_side import ServerSideSessionBackend, ServerSideSessionConfig
from litestar.security.session_auth import SessionAuth

from aigc.base import AuthConfig, Config

from .schema import UserStruct
from .service import UserService

SESSION_USER_ID_KEY = "user_id"
SESSION_EXCLUDE_PATHS = (
    r"^/system(?:/.*)?$",
    "/docs",
    "/openapi.json",
)


async def retrieve_user_handler(session: dict[str, Any], _: ASGIConnection) -> UserStruct | None:
    """Retrieve the authenticated user from session data."""

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
