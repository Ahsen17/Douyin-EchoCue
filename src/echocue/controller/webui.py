"""Webui session endpoints."""

from typing import Any

from litestar import Controller, Request, delete, get, post
from litestar.exceptions import NotAuthorizedException

from echocue.auth import LoginRequest, UserStruct
from echocue.auth.client import create_auth_permission_client
from echocue.auth.enum import SessionClientType
from echocue.auth.session import create_session_data
from echocue.base import Config
from echocue.core.client import (
    ClientSessionVO,
    ClientUserVO,
    RemediationContextVO,
    RemediationHandler,
    RemediationTokenConsumptionCreate,
    WebuiRoomListVO,
    WebuiSessionCreate,
)
from echocue.core.room import RoomAggregationHandler
from echocue.shared import GenericResponse
from echocue.shared.context import RequestContext

__all__ = ("WebuiController",)


class WebuiController(Controller):
    """Controller for webui sessions."""

    path = "/webui"
    tags = ["webui"]

    @post(
        path="/session",
        operation_id="webui:create-session",
        summary="Create webui session",
        exclude_from_auth=True,
    )
    async def create_session(
        self,
        request: Request[UserStruct, Any, Any],
        data: WebuiSessionCreate,
    ) -> GenericResponse[ClientSessionVO]:
        """Authenticate and create a webui session."""

        result = await create_auth_permission_client().authenticate(
            LoginRequest(username=data.username, password=data.password)
        )
        request.set_session(create_session_data(result.user.id, SessionClientType.WEBUI))

        return GenericResponse(
            message="ok",
            data=ClientSessionVO(
                expires_in=Config.get().auth.session_max_age_seconds,
                user=ClientUserVO.from_user(result.user),
            ),
        )

    @delete(
        path="/session",
        operation_id="webui:delete-session",
        summary="Delete webui session",
    )
    async def delete_session(
        self,
        request: Request[UserStruct, Any, Any],
        ctx: RequestContext,
    ) -> GenericResponse[None]:
        """Clear the current webui session."""

        ctx.require_webui_session()
        request.clear_session()

        return GenericResponse(message="ok", data=None)

    @get(
        path="/me",
        operation_id="webui:me",
        summary="Current webui user",
    )
    async def me(self, ctx: RequestContext) -> GenericResponse[ClientUserVO]:
        """Return the current webui user."""

        ctx.require_webui_session()
        if ctx.user is None:
            raise NotAuthorizedException(detail="Unauthorized.")

        return GenericResponse(message="ok", data=ClientUserVO.from_user(ctx.user))

    @get(
        path="/rooms",
        operation_id="webui:list-rooms",
        summary="List webui rooms",
    )
    async def list_rooms(
        self,
        ctx: RequestContext,
        room_aggregation_handler: RoomAggregationHandler,
    ) -> GenericResponse[WebuiRoomListVO]:
        """Return all visible rooms as a read-only management view."""

        ctx.require_webui_session()
        if ctx.user_id is None:
            raise NotAuthorizedException(detail="Unauthorized.")

        rooms = await room_aggregation_handler.list_rooms(ctx.user_id)
        return GenericResponse(message="ok", data=WebuiRoomListVO.from_rooms(rooms))

    @post(
        path="/remediation-token-consumptions",
        operation_id="webui:create-remediation-token-consumption",
        summary="Create remediation token consumption",
        exclude_from_auth=True,
    )
    async def create_remediation_token_consumption(
        self,
        data: RemediationTokenConsumptionCreate,
        remediation_handler: RemediationHandler,
    ) -> GenericResponse[RemediationContextVO]:
        """Create a one-time token consumption without a webui session."""

        result = await remediation_handler.consume_token(data.token)
        return GenericResponse(message="ok", data=result)
