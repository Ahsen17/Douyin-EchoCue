from uuid import uuid4

import pytest

from echocue.auth import SessionClientType
from echocue.auth.session import (
    SESSION_CLIENT_ID_KEY,
    SESSION_CLIENT_TYPE_KEY,
    SESSION_USER_ID_KEY,
    create_session_data,
    parse_session_identity,
)


class TestSessionIdentity:
    def test_round_trips_client_identity(self) -> None:
        user_id = uuid4()
        client_id = uuid4()

        session = create_session_data(user_id, SessionClientType.CLIENT, client_id)
        identity = parse_session_identity(session)

        assert session == {
            SESSION_USER_ID_KEY: str(user_id),
            SESSION_CLIENT_TYPE_KEY: "client",
            SESSION_CLIENT_ID_KEY: str(client_id),
        }
        assert identity is not None
        assert identity.user_id == user_id
        assert identity.client_type is SessionClientType.CLIENT
        assert identity.client_id == client_id

    def test_round_trips_webui_identity_without_client_id(self) -> None:
        user_id = uuid4()

        session = create_session_data(user_id, SessionClientType.WEBUI)
        identity = parse_session_identity(session)

        assert session == {
            SESSION_USER_ID_KEY: str(user_id),
            SESSION_CLIENT_TYPE_KEY: "webui",
        }
        assert identity is not None
        assert identity.client_type is SessionClientType.WEBUI
        assert identity.client_id is None

    @pytest.mark.parametrize(
        "session",
        [
            {},
            {SESSION_USER_ID_KEY: "not-a-uuid", SESSION_CLIENT_TYPE_KEY: "client"},
            {SESSION_USER_ID_KEY: str(uuid4())},
            {SESSION_USER_ID_KEY: str(uuid4()), SESSION_CLIENT_TYPE_KEY: "unknown"},
            {SESSION_USER_ID_KEY: str(uuid4()), SESSION_CLIENT_TYPE_KEY: "client"},
            {
                SESSION_USER_ID_KEY: str(uuid4()),
                SESSION_CLIENT_TYPE_KEY: "client",
                SESSION_CLIENT_ID_KEY: "not-a-uuid",
            },
            {
                SESSION_USER_ID_KEY: str(uuid4()),
                SESSION_CLIENT_TYPE_KEY: "webui",
                SESSION_CLIENT_ID_KEY: str(uuid4()),
            },
        ],
    )
    def test_rejects_unsafe_session_shapes(self, session: dict[str, str]) -> None:
        assert parse_session_identity(session) is None

    def test_requires_client_id_when_creating_client_session(self) -> None:
        with pytest.raises(ValueError, match="require a client id"):
            create_session_data(uuid4(), SessionClientType.CLIENT)

    def test_rejects_client_id_when_creating_webui_session(self) -> None:
        with pytest.raises(ValueError, match="cannot contain a client id"):
            create_session_data(uuid4(), SessionClientType.WEBUI, uuid4())
