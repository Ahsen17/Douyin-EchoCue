import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  parseClientRoomListResponse,
  parseCurrentUserResponse,
  parseEmptyResponse,
  parseRemediationContextResponse,
  parseRemediationLinkResponse,
  parseRuntimeFailureResponse,
  parseRuntimeStartResponse,
  parseRuntimeStopResponse,
  parseSessionResponse,
  parseWebSocketMessage,
  parseWebuiRoomListResponse,
  runtimeErrorCodes,
} from "../src/renderer/protocol.ts";

interface ContractFixture {
  errorCodes: Record<"retryable" | "remediation" | "blocked", string[]>;
  httpExamples: Record<string, { response: unknown }>;
  websocketExamples: Record<string, unknown>;
}

const contractPath = new URL("../../../contracts/m6/client-service.json", import.meta.url);
const contract = JSON.parse(await readFile(contractPath, "utf8")) as ContractFixture;

test("HTTP examples parse through the client protocol boundary", () => {
  const examples = contract.httpExamples;

  assert.equal(parseSessionResponse(examples.clientSessionSuccess.response).data.expiresIn, 28800);
  assert.equal(parseSessionResponse(examples.webuiSessionSuccess.response).data.user.username, "admin");
  assert.equal(parseCurrentUserResponse(examples.clientMeSuccess.response).data.username, "demo_anchor");
  assert.equal(parseCurrentUserResponse(examples.webuiMeSuccess.response).data.username, "admin");
  assert.equal(parseEmptyResponse(examples.clientSessionDeleteSuccess.response).data, null);
  assert.equal(parseEmptyResponse(examples.webuiSessionDeleteSuccess.response).data, null);
  assert.equal(parseClientRoomListResponse(examples.clientRoomsSuccess.response).data.items.length, 2);
  assert.equal(parseWebuiRoomListResponse(examples.webuiRoomsSuccess.response).data.items.length, 1);
  const permissionDeniedRoom = parseClientRoomListResponse({
    code: 200,
    message: "ok",
    data: {
      items: [
        {
          roomId: "view-only-room",
          roomName: null,
          anchorName: null,
          avatarThumb: null,
          roomKind: "personal",
          liveStatus: "offline",
          canStartAssistant: false,
          disabledReason: {
            errorCode: "permissionDenied",
            message: "Current account cannot start this room assistant.",
          },
        },
      ],
    },
  });
  assert.equal(permissionDeniedRoom.data.items[0]?.disabledReason?.issueType, undefined);
  assert.equal(parseRuntimeStartResponse(examples.runtimeStartSuccess.response).data.status, "starting");
  assert.equal(parseRuntimeStopResponse(examples.runtimeStopSuccess.response).data.status, "stopped");
  assert.equal(parseRemediationLinkResponse(examples.remediationLinkSuccess.response).data.expiresIn, 900);
  assert.equal(
    parseRemediationContextResponse(examples.remediationTokenConsumptionSuccess.response).data.issueType,
    "persona",
  );

  for (const exampleName of ["blockedFailure", "retryableFailure", "remediationFailure"]) {
    assert.ok(parseRuntimeFailureResponse(examples[exampleName].response).data.errorCode);
  }
});

test("WebSocket examples parse as the complete discriminated message union", () => {
  const parsedTypes = Object.values(contract.websocketExamples).map(
    (example) => parseWebSocketMessage(example).type,
  );

  assert.deepEqual(new Set(parsedTypes), new Set(["connected", "heartbeat", "push", "ack", "status"]));
});

test("client error parser accepts exactly the frozen error catalog", () => {
  const fixtureCodes = Object.values(contract.errorCodes).flat().sort();
  assert.deepEqual(fixtureCodes, [...runtimeErrorCodes].sort());

  const invalidResponse = structuredClone(contract.httpExamples.blockedFailure.response) as {
    data: { errorCode: string };
  };
  invalidResponse.data.errorCode = "roomNotLive";
  assert.throws(() => parseRuntimeFailureResponse(invalidResponse), /unsupported value/);
});
