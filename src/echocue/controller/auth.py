"""Authentication RESTful endpoints.

This module exposes session and current-user endpoints.
Controllers handle HTTP input, response construction, and service calls without accessing database models directly.
"""

from typing import Any

from litestar import Controller, Request, delete, get, post
from litestar.exceptions import NotAuthorizedException

from echocue.auth import AuthSessionVO, LoginRequest, UserService, UserStruct, UserVO
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

        async with UserService.provide() as service:
            user = await service.authenticate(data)

        config = Config.get().auth
        request.set_session({SESSION_USER_ID_KEY: str(user.id)})

        return GenericResponse(
            message="ok",
            data=AuthSessionVO(
                expires_in=config.session_max_age_seconds,
                user=UserVO.from_struct(user),
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
