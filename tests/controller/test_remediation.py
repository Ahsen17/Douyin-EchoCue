"""Direct remediation controller boundary tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from litestar.exceptions import NotAuthorizedException

from echocue.auth.enum import SessionClientType
from echocue.controller.client import ClientController
from echocue.controller.webui import WebuiController
from echocue.core.client import (
    RemediationContextVO,
    RemediationIssueType,
    RemediationLinkCreate,
    RemediationLinkVO,
    RemediationTokenConsumptionCreate,
    RuntimeErrorCode,
)
from echocue.shared.context import RequestContext

USER_ID = UUID("00000000-0000-7000-8000-000000000001")
CLIENT_ID = UUID("00000000-0000-7000-8000-000000000002")


class TestRemediationControllers:
    async def test_client_link_requires_client_session_and_delegates(self) -> None:
        data = RemediationLinkCreate(
            room_id="room-a",
            error_code=RuntimeErrorCode.PERSONA_NOT_PUBLISHED,
            issue_type=RemediationIssueType.PERSONA,
        )
        service = SimpleNamespace(
            create_link=AsyncMock(return_value=RemediationLinkVO(url="https://example.test?token=fake", expires_in=900))
        )
        context = RequestContext(
            user_id=USER_ID,
            client_type=SessionClientType.CLIENT,
            client_id=CLIENT_ID,
            is_authenticated=True,
        )

        response = await ClientController.create_remediation_link.fn(
            cast(ClientController, None), data, context, service
        )

        assert response.content["data"]["expiresIn"] == 900
        service.create_link.assert_awaited_once_with(USER_ID, CLIENT_ID, data)

        webui_context = RequestContext(
            user_id=USER_ID,
            client_type=SessionClientType.WEBUI,
            is_authenticated=True,
        )
        with pytest.raises(NotAuthorizedException):
            await ClientController.create_remediation_link.fn(
                cast(ClientController, None), data, webui_context, service
            )

    async def test_webui_consumption_needs_no_session_and_has_no_session_side_effect(self) -> None:
        data = RemediationTokenConsumptionCreate(token="fake-token")
        expected = RemediationContextVO(
            room_id="room-a",
            issue_type=RemediationIssueType.PERSONA,
            route="/rooms/{roomId}/persona",
            params={"roomId": "room-a"},
            expires_at=datetime(2026, 8, 20, tzinfo=UTC),
        )
        service = SimpleNamespace(consume_token=AsyncMock(return_value=expected))

        response = await WebuiController.create_remediation_token_consumption.fn(
            cast(WebuiController, None), data, service
        )

        assert response.content["data"]["roomId"] == "room-a"
        service.consume_token.assert_awaited_once_with("fake-token")
