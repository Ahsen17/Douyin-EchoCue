"""Direct room-view controller tests independent of application lifespan."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from litestar.exceptions import NotAuthorizedException

from echocue.auth.enum import SessionClientType
from echocue.controller.client import ClientController
from echocue.controller.webui import WebuiController
from echocue.shared.context import RequestContext

USER_ID = UUID("00000000-0000-7000-8000-000000000001")
CLIENT_ID = UUID("00000000-0000-7000-8000-000000000002")


class TestRoomViewControllers:
    """Verify controllers delegate through typed session boundaries."""

    async def test_client_room_view_delegates_for_client_session(self) -> None:
        service = SimpleNamespace(list_rooms=AsyncMock(return_value=[]))
        context = RequestContext(
            user_id=USER_ID,
            client_type=SessionClientType.CLIENT,
            client_id=CLIENT_ID,
            is_authenticated=True,
        )

        response = await ClientController.list_rooms.fn(
            cast(ClientController, None),
            context,
            service,
        )

        assert response.content == {"code": 200, "message": "ok", "data": {"items": []}}
        service.list_rooms.assert_awaited_once_with(USER_ID, include_start_eligibility=True)

    async def test_webui_room_view_delegates_for_webui_session(self) -> None:
        service = SimpleNamespace(list_rooms=AsyncMock(return_value=[]))
        context = RequestContext(
            user_id=USER_ID,
            client_type=SessionClientType.WEBUI,
            is_authenticated=True,
        )

        response = await WebuiController.list_rooms.fn(
            cast(WebuiController, None),
            context,
            service,
        )

        assert response.content == {"code": 200, "message": "ok", "data": {"items": []}}
        service.list_rooms.assert_awaited_once_with(USER_ID)

    async def test_room_views_reject_cross_surface_sessions(self) -> None:
        service = SimpleNamespace(
            list_rooms=AsyncMock(return_value=[]),
        )
        client_context = RequestContext(
            user_id=USER_ID,
            client_type=SessionClientType.CLIENT,
            client_id=CLIENT_ID,
            is_authenticated=True,
        )
        webui_context = RequestContext(
            user_id=USER_ID,
            client_type=SessionClientType.WEBUI,
            is_authenticated=True,
        )

        with pytest.raises(NotAuthorizedException):
            await ClientController.list_rooms.fn(cast(ClientController, None), webui_context, service)
        with pytest.raises(NotAuthorizedException):
            await WebuiController.list_rooms.fn(cast(WebuiController, None), client_context, service)

        service.list_rooms.assert_not_awaited()
