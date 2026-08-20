"""Shared HTTP session identity handling.

This module owns the serialized session identity shared by client and webui entry points.
Runtime leases have a separate lifecycle and must not be represented here.
"""

from typing import Any
from uuid import UUID

from echocue.base import BaseStruct

from .enum import SessionClientType

SESSION_CLIENT_ID_KEY = "client_id"
SESSION_CLIENT_TYPE_KEY = "client_type"
SESSION_USER_ID_KEY = "user_id"


class SessionIdentityStruct(BaseStruct):
    """Validated identity stored in a server-side HTTP session."""

    user_id: UUID
    client_type: SessionClientType
    client_id: UUID | None = None


def create_session_data(
    user_id: UUID,
    client_type: SessionClientType,
    client_id: UUID | None = None,
) -> dict[str, str]:
    """Build a valid serialized session payload for an application surface."""

    if client_type is SessionClientType.CLIENT and client_id is None:
        msg = "Client sessions require a client id."
        raise ValueError(msg)
    if client_type is SessionClientType.WEBUI and client_id is not None:
        msg = "Webui sessions cannot contain a client id."
        raise ValueError(msg)

    data = {
        SESSION_USER_ID_KEY: str(user_id),
        SESSION_CLIENT_TYPE_KEY: client_type.value,
    }
    if client_id is not None:
        data[SESSION_CLIENT_ID_KEY] = str(client_id)

    return data


def parse_session_identity(session: dict[str, Any]) -> SessionIdentityStruct | None:
    """Parse session data, returning no identity when its shape is unsafe."""

    raw_user_id = session.get(SESSION_USER_ID_KEY)
    raw_client_type = session.get(SESSION_CLIENT_TYPE_KEY)
    if not isinstance(raw_user_id, str) or not isinstance(raw_client_type, str):
        return None

    try:
        user_id = UUID(raw_user_id)
        client_type = SessionClientType(raw_client_type)
    except ValueError:
        return None

    raw_client_id = session.get(SESSION_CLIENT_ID_KEY)
    if client_type is SessionClientType.WEBUI:
        if raw_client_id is not None:
            return None
        return SessionIdentityStruct(user_id=user_id, client_type=client_type)

    if not isinstance(raw_client_id, str):
        return None
    try:
        client_id = UUID(raw_client_id)
    except ValueError:
        return None

    return SessionIdentityStruct(user_id=user_id, client_type=client_type, client_id=client_id)
