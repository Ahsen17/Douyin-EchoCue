"""Authentication RESTful endpoints.

This module exposes session and current-user endpoints.
Controllers handle HTTP input, response construction, and service calls without accessing database models directly.
"""

from typing import Any
from uuid import UUID

from litestar import Controller, Request, delete, get, post
from litestar.exceptions import HTTPException, ImproperlyConfiguredException, NotAuthorizedException
from litestar.status_codes import HTTP_409_CONFLICT

from echocue.auth import (
    AuthSessionVO,
    LoginRequest,
    PermissionCheckRequest,
    PermissionCheckRequestStruct,
    PermissionCheckVO,
    PermissionContextVO,
    UserStruct,
    UserVO,
)
from echocue.auth.client import create_auth_permission_client
from echocue.auth.security import SESSION_USER_ID_KEY
from echocue.base import Config
from echocue.shared import GenericResponse
from echocue.shared.context import RequestContext

__all__ = ("AuthController",)


class AuthController(Controller):
    """Controller for authentication endpoints."""

    path = "/auth"
    tags = ["auth"]

    @post(
        path="/session",
        operation_id="auth:create-session",
        summary="Create session",
        exclude_from_auth=True,
    )
    async def create_session(
        self,
        request: Request[UserStruct, Any, Any],
        data: LoginRequest,
    ) -> GenericResponse[AuthSessionVO]:
        """Authenticate credentials and create a server-side session."""

        await _reject_existing_session(request)

        auth_client = create_auth_permission_client()
        result = await auth_client.authenticate(data)
        config = Config.get().auth
        request.set_session({SESSION_USER_ID_KEY: str(result.user.id)})

        return GenericResponse(
            message="ok",
            data=AuthSessionVO(
                expires_in=config.session_max_age_seconds,
                user=UserVO.from_struct(result.user),
            ),
        )

    @delete(
        path="/session",
        operation_id="auth:delete-session",
        summary="Delete session",
    )
    async def delete_session(self, request: Request[UserStruct, Any, Any]) -> GenericResponse[None]:
        """Clear the current server-side session."""

        request.clear_session()

        return GenericResponse(message="ok", data=None)

    @get(
        path="/me",
        operation_id="auth:me",
        summary="Current user",
    )
    async def me(self, ctx: RequestContext) -> GenericResponse[UserVO]:
        """Return the current authenticated user."""

        if ctx.user is None:
            raise NotAuthorizedException(detail="Unauthorized.")

        return GenericResponse(message="ok", data=UserVO.from_struct(ctx.user))

    @get(
        path="/permission/context",
        operation_id="auth:permission-context",
        summary="Current permission context",
    )
    async def permission_context(self, ctx: RequestContext) -> GenericResponse[PermissionContextVO]:
        """Return the current authenticated user's permission context."""

        if ctx.user_id is None:
            raise NotAuthorizedException(detail="Unauthorized.")

        permission_context = await create_auth_permission_client().get_permission_context(ctx.user_id)

        return GenericResponse(message="ok", data=PermissionContextVO.from_struct(permission_context))

    @post(
        path="/room/permissions/checks",
        operation_id="auth:check-room-permission",
        summary="Check room permission",
    )
    async def check_room_permission(
        self,
        ctx: RequestContext,
        data: PermissionCheckRequest,
    ) -> GenericResponse[PermissionCheckVO]:
        """Check whether the current authenticated user may perform a room action."""

        if ctx.user_id is None:
            raise NotAuthorizedException(detail="Unauthorized.")

        result = await create_auth_permission_client().check_permission(
            PermissionCheckRequestStruct(
                user_id=ctx.user_id,
                room_id=data.room_id,
                action=data.action,
            )
        )

        return GenericResponse(message="ok", data=PermissionCheckVO.from_struct(result))


async def _reject_existing_session(request: Request[UserStruct, Any, Any]) -> None:
    raw_user_id = _get_session_user_id(request)
    if raw_user_id is None:
        return

    try:
        user_id = UUID(raw_user_id)
    except ValueError:
        request.clear_session()
        return

    try:
        permission_context = await create_auth_permission_client().get_permission_context(user_id)
    except NotAuthorizedException:
        request.clear_session()
        return

    if permission_context.user.is_active:
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail="Session already exists.",
        )

    request.clear_session()


def _get_session_user_id(request: Request[UserStruct, Any, Any]) -> str | None:
    try:
        raw_user_id = request.session.get(SESSION_USER_ID_KEY)
    except ImproperlyConfiguredException:
        return None

    return raw_user_id if isinstance(raw_user_id, str) else None
