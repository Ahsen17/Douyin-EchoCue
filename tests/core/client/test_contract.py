"""M6 client-service contract regression tests."""

import json
import re
from pathlib import Path
from typing import Any, cast

from msgspec import convert

from echocue.core.client import (
    ClientHttpResponse,
    ClientRoomListVO,
    ClientSessionCreate,
    ClientSessionVO,
    ClientUserVO,
    ClientWebSocketMessage,
    RemediationContextVO,
    RemediationLinkCreate,
    RemediationLinkVO,
    RemediationTokenConsumptionCreate,
    RuntimeErrorCode,
    RuntimeFailureVO,
    RuntimeStart,
    RuntimeStartVO,
    RuntimeStopVO,
    WebuiRoomListVO,
    WebuiSessionCreate,
)

CONTRACT_PATH = Path(__file__).parents[3] / "contracts" / "m6" / "client-service.json"

EXPECTED_HTTP_ENDPOINTS = {
    ("POST", "/client/session", "client:create-session"),
    ("DELETE", "/client/session", "client:delete-session"),
    ("GET", "/client/me", "client:me"),
    ("GET", "/client/rooms", "client:list-rooms"),
    ("POST", "/client/runtimes", "client:create-runtime"),
    ("DELETE", "/client/runtimes/{runtime_id}", "client:delete-runtime"),
    ("POST", "/client/remediation-links", "client:create-remediation-link"),
    ("POST", "/webui/session", "webui:create-session"),
    ("DELETE", "/webui/session", "webui:delete-session"),
    ("GET", "/webui/me", "webui:me"),
    ("GET", "/webui/rooms", "webui:list-rooms"),
    (
        "POST",
        "/webui/remediation-token-consumptions",
        "webui:create-remediation-token-consumption",
    ),
}
EXPECTED_ERROR_CODES = {
    "roomOffline",
    "douyinliveUnavailable",
    "runtimeStartFailed",
    "personaNotPublished",
    "ruleConflict",
    "unauthenticated",
    "clientSessionConflict",
    "permissionDenied",
    "clientRuntimeActive",
    "roomActiveByOtherClient",
}
RPC_PATH_SEGMENTS = {"consume", "create", "delete", "login", "logout", "start", "stop", "update"}


def load_contract() -> dict[str, Any]:
    """Load the shared M6 contract fixture."""

    with CONTRACT_PATH.open(encoding="utf-8") as contract_file:
        return cast("dict[str, Any]", json.load(contract_file))


class TestClientContract:
    """Verify the shared M6 client-service contract."""

    def test_endpoint_manifest_matches_frozen_controller_contract(self) -> None:
        contract = load_contract()
        endpoints = {
            (endpoint["method"], endpoint["path"], endpoint["operationId"]) for endpoint in contract["httpEndpoints"]
        }

        assert endpoints == EXPECTED_HTTP_ENDPOINTS
        assert contract["websocketEndpoint"]["path"] == ("/client/runtime/ws/{client_id}/{room_id}/{runtime_id}")

        for method, path, operation_id in endpoints:
            assert method in {"GET", "POST", "DELETE"}
            assert re.fullmatch(r"/(?:[a-z]+(?:-[a-z]+)*|\{[a-z]+(?:_[a-z]+)*\})(?:/[^/]+)*", path)
            assert re.fullmatch(r"(?:client|webui):[a-z]+(?:-[a-z]+)*", operation_id)
            path_words = {
                word
                for segment in path.split("/")
                if segment and not segment.startswith("{")
                for word in segment.split("-")
            }
            assert path_words.isdisjoint(RPC_PATH_SEGMENTS)

    def test_error_code_catalog_matches_runtime_error_enum(self) -> None:
        contract = load_contract()
        error_codes = {
            error_code
            for category in ("retryable", "remediation", "blocked")
            for error_code in contract["errorCodes"][category]
        }

        assert error_codes == EXPECTED_ERROR_CODES
        assert error_codes == {error_code.value for error_code in RuntimeErrorCode}

    def test_http_examples_parse_with_typed_backend_schemas(self) -> None:
        examples = load_contract()["httpExamples"]

        convert(examples["clientSessionSuccess"]["request"], type=ClientSessionCreate)
        convert(
            examples["clientSessionSuccess"]["response"],
            type=ClientHttpResponse[ClientSessionVO],
        )
        convert(examples["webuiSessionSuccess"]["request"], type=WebuiSessionCreate)
        convert(
            examples["webuiSessionSuccess"]["response"],
            type=ClientHttpResponse[ClientSessionVO],
        )
        convert(
            examples["clientMeSuccess"]["response"],
            type=ClientHttpResponse[ClientUserVO],
        )
        convert(
            examples["webuiMeSuccess"]["response"],
            type=ClientHttpResponse[ClientUserVO],
        )
        convert(
            examples["clientSessionDeleteSuccess"]["response"],
            type=ClientHttpResponse[None],
        )
        convert(
            examples["webuiSessionDeleteSuccess"]["response"],
            type=ClientHttpResponse[None],
        )
        convert(
            examples["clientRoomsSuccess"]["response"],
            type=ClientHttpResponse[ClientRoomListVO],
        )
        convert(
            examples["webuiRoomsSuccess"]["response"],
            type=ClientHttpResponse[WebuiRoomListVO],
        )
        convert(examples["runtimeStartSuccess"]["request"], type=RuntimeStart)
        runtime_start = convert(
            examples["runtimeStartSuccess"]["response"],
            type=ClientHttpResponse[RuntimeStartVO],
        )
        assert runtime_start.data.status.value == "starting"

        runtime_stop = convert(
            examples["runtimeStopSuccess"]["response"],
            type=ClientHttpResponse[RuntimeStopVO],
        )
        assert runtime_stop.data.status.value == "stopped"
        convert(examples["remediationLinkSuccess"]["request"], type=RemediationLinkCreate)
        convert(
            examples["remediationLinkSuccess"]["response"],
            type=ClientHttpResponse[RemediationLinkVO],
        )
        convert(
            examples["remediationTokenConsumptionSuccess"]["request"],
            type=RemediationTokenConsumptionCreate,
        )
        convert(
            examples["remediationTokenConsumptionSuccess"]["response"],
            type=ClientHttpResponse[RemediationContextVO],
        )

        for example_name in ("blockedFailure", "retryableFailure", "remediationFailure"):
            convert(
                examples[example_name]["response"],
                type=ClientHttpResponse[RuntimeFailureVO],
            )

    def test_websocket_examples_parse_as_discriminated_union(self) -> None:
        examples = load_contract()["websocketExamples"]

        messages = [convert(example, type=ClientWebSocketMessage) for example in examples.values()]

        assert {message.__struct_config__.tag for message in messages} == {
            "connected",
            "heartbeat",
            "push",
            "ack",
            "status",
        }
