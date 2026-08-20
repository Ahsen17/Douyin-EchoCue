"""Desktop client session endpoints."""

from typing import Any

from litestar import Controller, Request, delete, get, post
from litestar.exceptions import NotAuthorizedException

from echocue.auth import UserStruct
from echocue.auth.enum import SessionClientType
from echocue.auth.session import create_session_data
from echocue.base import Config
from echocue.core.client import ClientSessionCreate, ClientSessionVO, ClientUserVO
from echocue.core.client.handler import ClientSessionHandler
from echocue.shared import GenericResponse
from echocue.shared.context import RequestContext

__all__ = ("ClientController",)


class ClientController(Controller):
    """Controller for desktop client sessions."""

    path = "/client"
    tags = ["client"]

    @post(
        path="/session",
        operation_id="client:create-session",
        summary="Create client session",
        exclude_from_auth=True,
    )
    async def create_session(
        self,
        request: Request[UserStruct, Any, Any],
        data: ClientSessionCreate,
        client_session_handler: ClientSessionHandler,
    ) -> GenericResponse[ClientSessionVO]:
        """Authenticate and create or restore a client session."""

        user = await client_session_handler.create(data)
        request.set_session(create_session_data(user.id, SessionClientType.CLIENT, data.client_id))

        return GenericResponse(
            message="ok",
            data=ClientSessionVO(
                expires_in=Config.get().auth.session_max_age_seconds,
                user=ClientUserVO.from_user(user),
            ),
        )

    @delete(
        path="/session",
        operation_id="client:delete-session",
        summary="Delete client session",
    )
    async def delete_session(
        self,
        request: Request[UserStruct, Any, Any],
        ctx: RequestContext,
        client_session_handler: ClientSessionHandler,
    ) -> GenericResponse[None]:
        """Release the client binding and clear the server-side session."""

        client_id = ctx.require_client_id()
        if ctx.user_id is None:
            raise NotAuthorizedException(detail="Unauthorized.")

        await client_session_handler.release(ctx.user_id, client_id)
        request.clear_session()

        return GenericResponse(message="ok", data=None)

    @get(
        path="/me",
        operation_id="client:me",
        summary="Current client user",
    )
    async def me(
        self,
        ctx: RequestContext,
    ) -> GenericResponse[ClientUserVO]:
        """Return the current client user and renew its binding."""

        ctx.require_client_id()
        if ctx.user is None or ctx.user_id is None:
            raise NotAuthorizedException(detail="Unauthorized.")

        return GenericResponse(message="ok", data=ClientUserVO.from_user(ctx.user))
