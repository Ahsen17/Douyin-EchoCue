export const runtimeErrorCodes = [
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
] as const;

export type RuntimeErrorCode = (typeof runtimeErrorCodes)[number];
export type RemediationIssueType = "persona" | "rule" | "liveStatus";

export interface HttpResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface SessionData {
  expiresIn: number;
  user: {
    id: string;
    username: string;
    displayName: string;
    isActive: boolean;
  };
}

export interface ClientRoomListData {
  items: Array<{
    roomId: string;
    roomName: string | null;
    anchorName: string | null;
    avatarThumb: string | null;
    roomKind: "personal" | "organization";
    liveStatus: "live" | "offline";
    canStartAssistant: boolean;
    disabledReason: {
      errorCode: RuntimeErrorCode;
      message: string;
      issueType: RemediationIssueType;
    } | null;
  }>;
}

export interface WebuiRoomListData {
  items: Array<Omit<ClientRoomListData["items"][number], "canStartAssistant" | "disabledReason">>;
}

export interface RuntimeStartData {
  runtimeId: string;
  roomId: string;
  status: "starting";
  ws: {
    url: string;
    heartbeatIntervalSeconds: number;
    heartbeatTimeoutSeconds: number;
    connectRetryWindowSeconds: number;
  };
}

export interface RuntimeStopData {
  runtimeId: string;
  roomId: string;
  status: "stopped";
  reason: "clientStopped";
}

export interface RuntimeFailureData {
  errorCode: RuntimeErrorCode;
  message: string;
  retryable?: boolean;
  remediation?: {
    issueType: RemediationIssueType;
    route: string;
    params: Record<string, string>;
    requiresOneTimeToken: boolean;
  };
}

export interface RemediationLinkData {
  url: string;
  expiresIn: number;
}

export interface RemediationContextData {
  roomId: string;
  issueType: RemediationIssueType;
  route: string;
  params: Record<string, string>;
  expiresAt: string;
}

export type ClientWebSocketMessage =
  | {
      type: "connected";
      messageId: string;
      runtimeId: string;
      roomId: string;
      clientId: string;
      heartbeatIntervalSeconds: number;
      heartbeatTimeoutSeconds: number;
    }
  | { type: "heartbeat"; sentAt: string }
  | {
      type: "push";
      messageId: string;
      runtimeId: string;
      roomId: string;
      payload: {
        commentDisplay: string;
        quickReply: string;
        cue: string;
        createdAt: string;
      };
    }
  | { type: "ack"; messageId: string; status: "received"; sentAt: string }
  | {
      type: "status";
      messageId: string;
      runtimeId: string;
      roomId: string;
      status: "roomEnded" | "runtimeStopped" | "connectionTimeout";
      reason: {
        errorCode: "roomEnded" | "runtimeStopped" | "connectionTimeout";
        message: string;
        issueType: RemediationIssueType;
      };
    };

type JsonObject = Record<string, unknown>;

function asObject(value: unknown, context: string): JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${context} must be an object`);
  }
  return value as JsonObject;
}

function asString(value: unknown, context: string): string {
  if (typeof value !== "string") {
    throw new TypeError(`${context} must be a string`);
  }
  return value;
}

function asNullableString(value: unknown, context: string): string | null {
  return value === null ? null : asString(value, context);
}

function asNumber(value: unknown, context: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`${context} must be a finite number`);
  }
  return value;
}

function asBoolean(value: unknown, context: string): boolean {
  if (typeof value !== "boolean") {
    throw new TypeError(`${context} must be a boolean`);
  }
  return value;
}

function asLiteral<T extends string>(value: unknown, allowed: readonly T[], context: string): T {
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    throw new TypeError(`${context} has an unsupported value`);
  }
  return value as T;
}

function asStringRecord(value: unknown, context: string): Record<string, string> {
  const record = asObject(value, context);
  return Object.fromEntries(
    Object.entries(record).map(([key, item]) => [key, asString(item, `${context}.${key}`)]),
  );
}

function parseResponse<T>(value: unknown, parseData: (data: unknown) => T): HttpResponse<T> {
  const response = asObject(value, "response");
  return {
    code: asNumber(response.code, "response.code"),
    message: asString(response.message, "response.message"),
    data: parseData(response.data),
  };
}

function parseIssueType(value: unknown, context: string): RemediationIssueType {
  return asLiteral(value, ["persona", "rule", "liveStatus"], context);
}

function parseRuntimeErrorCode(value: unknown, context: string): RuntimeErrorCode {
  return asLiteral(value, runtimeErrorCodes, context);
}

function parseRoomBase(value: unknown, context: string) {
  const room = asObject(value, context);
  return {
    roomId: asString(room.roomId, `${context}.roomId`),
    roomName: asNullableString(room.roomName, `${context}.roomName`),
    anchorName: asNullableString(room.anchorName, `${context}.anchorName`),
    avatarThumb: asNullableString(room.avatarThumb, `${context}.avatarThumb`),
    roomKind: asLiteral(room.roomKind, ["personal", "organization"], `${context}.roomKind`),
    liveStatus: asLiteral(room.liveStatus, ["live", "offline"], `${context}.liveStatus`),
  } as const;
}

export function parseSessionResponse(value: unknown): HttpResponse<SessionData> {
  return parseResponse(value, (data) => {
    const session = asObject(data, "response.data");
    const user = asObject(session.user, "response.data.user");
    return {
      expiresIn: asNumber(session.expiresIn, "response.data.expiresIn"),
      user: {
        id: asString(user.id, "response.data.user.id"),
        username: asString(user.username, "response.data.user.username"),
        displayName: asString(user.displayName, "response.data.user.displayName"),
        isActive: asBoolean(user.isActive, "response.data.user.isActive"),
      },
    };
  });
}

export function parseCurrentUserResponse(value: unknown): HttpResponse<SessionData["user"]> {
  return parseResponse(value, (data) => {
    const user = asObject(data, "response.data");
    return {
      id: asString(user.id, "response.data.id"),
      username: asString(user.username, "response.data.username"),
      displayName: asString(user.displayName, "response.data.displayName"),
      isActive: asBoolean(user.isActive, "response.data.isActive"),
    };
  });
}

export function parseEmptyResponse(value: unknown): HttpResponse<null> {
  return parseResponse(value, (data) => {
    if (data !== null) {
      throw new TypeError("response.data must be null");
    }
    return null;
  });
}

export function parseClientRoomListResponse(value: unknown): HttpResponse<ClientRoomListData> {
  return parseResponse(value, (data) => {
    const roomList = asObject(data, "response.data");
    if (!Array.isArray(roomList.items)) {
      throw new TypeError("response.data.items must be an array");
    }
    return {
      items: roomList.items.map((value, index) => {
        const context = `response.data.items[${index}]`;
        const room = asObject(value, context);
        const disabledReason =
          room.disabledReason === null
            ? null
            : (() => {
                const reason = asObject(room.disabledReason, `${context}.disabledReason`);
                return {
                  errorCode: parseRuntimeErrorCode(reason.errorCode, `${context}.disabledReason.errorCode`),
                  message: asString(reason.message, `${context}.disabledReason.message`),
                  issueType: parseIssueType(reason.issueType, `${context}.disabledReason.issueType`),
                };
              })();
        return {
          ...parseRoomBase(value, context),
          canStartAssistant: asBoolean(room.canStartAssistant, `${context}.canStartAssistant`),
          disabledReason,
        };
      }),
    };
  });
}

export function parseWebuiRoomListResponse(value: unknown): HttpResponse<WebuiRoomListData> {
  return parseResponse(value, (data) => {
    const roomList = asObject(data, "response.data");
    if (!Array.isArray(roomList.items)) {
      throw new TypeError("response.data.items must be an array");
    }
    return {
      items: roomList.items.map((room, index) => parseRoomBase(room, `response.data.items[${index}]`)),
    };
  });
}

export function parseRuntimeStartResponse(value: unknown): HttpResponse<RuntimeStartData> {
  return parseResponse(value, (data) => {
    const runtime = asObject(data, "response.data");
    const ws = asObject(runtime.ws, "response.data.ws");
    return {
      runtimeId: asString(runtime.runtimeId, "response.data.runtimeId"),
      roomId: asString(runtime.roomId, "response.data.roomId"),
      status: asLiteral(runtime.status, ["starting"], "response.data.status"),
      ws: {
        url: asString(ws.url, "response.data.ws.url"),
        heartbeatIntervalSeconds: asNumber(
          ws.heartbeatIntervalSeconds,
          "response.data.ws.heartbeatIntervalSeconds",
        ),
        heartbeatTimeoutSeconds: asNumber(
          ws.heartbeatTimeoutSeconds,
          "response.data.ws.heartbeatTimeoutSeconds",
        ),
        connectRetryWindowSeconds: asNumber(
          ws.connectRetryWindowSeconds,
          "response.data.ws.connectRetryWindowSeconds",
        ),
      },
    };
  });
}

export function parseRuntimeStopResponse(value: unknown): HttpResponse<RuntimeStopData> {
  return parseResponse(value, (data) => {
    const runtime = asObject(data, "response.data");
    return {
      runtimeId: asString(runtime.runtimeId, "response.data.runtimeId"),
      roomId: asString(runtime.roomId, "response.data.roomId"),
      status: asLiteral(runtime.status, ["stopped"], "response.data.status"),
      reason: asLiteral(runtime.reason, ["clientStopped"], "response.data.reason"),
    };
  });
}

export function parseRuntimeFailureResponse(value: unknown): HttpResponse<RuntimeFailureData> {
  return parseResponse(value, (data) => {
    const failure = asObject(data, "response.data");
    const result: RuntimeFailureData = {
      errorCode: parseRuntimeErrorCode(failure.errorCode, "response.data.errorCode"),
      message: asString(failure.message, "response.data.message"),
    };
    if (failure.retryable !== undefined) {
      result.retryable = asBoolean(failure.retryable, "response.data.retryable");
    }
    if (failure.remediation !== undefined) {
      const remediation = asObject(failure.remediation, "response.data.remediation");
      result.remediation = {
        issueType: parseIssueType(remediation.issueType, "response.data.remediation.issueType"),
        route: asString(remediation.route, "response.data.remediation.route"),
        params: asStringRecord(remediation.params, "response.data.remediation.params"),
        requiresOneTimeToken: asBoolean(
          remediation.requiresOneTimeToken,
          "response.data.remediation.requiresOneTimeToken",
        ),
      };
    }
    return result;
  });
}

export function parseRemediationLinkResponse(value: unknown): HttpResponse<RemediationLinkData> {
  return parseResponse(value, (data) => {
    const link = asObject(data, "response.data");
    return {
      url: asString(link.url, "response.data.url"),
      expiresIn: asNumber(link.expiresIn, "response.data.expiresIn"),
    };
  });
}

export function parseRemediationContextResponse(value: unknown): HttpResponse<RemediationContextData> {
  return parseResponse(value, (data) => {
    const context = asObject(data, "response.data");
    return {
      roomId: asString(context.roomId, "response.data.roomId"),
      issueType: parseIssueType(context.issueType, "response.data.issueType"),
      route: asString(context.route, "response.data.route"),
      params: asStringRecord(context.params, "response.data.params"),
      expiresAt: asString(context.expiresAt, "response.data.expiresAt"),
    };
  });
}

export function parseWebSocketMessage(value: unknown): ClientWebSocketMessage {
  const message = asObject(value, "message");
  const type = asLiteral(message.type, ["connected", "heartbeat", "push", "ack", "status"], "message.type");
  if (type === "heartbeat") {
    return { type, sentAt: asString(message.sentAt, "message.sentAt") };
  }
  if (type === "ack") {
    return {
      type,
      messageId: asString(message.messageId, "message.messageId"),
      status: asLiteral(message.status, ["received"], "message.status"),
      sentAt: asString(message.sentAt, "message.sentAt"),
    };
  }

  const envelope = {
    messageId: asString(message.messageId, "message.messageId"),
    runtimeId: asString(message.runtimeId, "message.runtimeId"),
    roomId: asString(message.roomId, "message.roomId"),
  };
  if (type === "connected") {
    return {
      type,
      ...envelope,
      clientId: asString(message.clientId, "message.clientId"),
      heartbeatIntervalSeconds: asNumber(
        message.heartbeatIntervalSeconds,
        "message.heartbeatIntervalSeconds",
      ),
      heartbeatTimeoutSeconds: asNumber(
        message.heartbeatTimeoutSeconds,
        "message.heartbeatTimeoutSeconds",
      ),
    };
  }
  if (type === "push") {
    const payload = asObject(message.payload, "message.payload");
    return {
      type,
      ...envelope,
      payload: {
        commentDisplay: asString(payload.commentDisplay, "message.payload.commentDisplay"),
        quickReply: asString(payload.quickReply, "message.payload.quickReply"),
        cue: asString(payload.cue, "message.payload.cue"),
        createdAt: asString(payload.createdAt, "message.payload.createdAt"),
      },
    };
  }

  const reason = asObject(message.reason, "message.reason");
  const status = asLiteral(
    message.status,
    ["roomEnded", "runtimeStopped", "connectionTimeout"],
    "message.status",
  );
  return {
    type,
    ...envelope,
    status,
    reason: {
      errorCode: asLiteral(
        reason.errorCode,
        ["roomEnded", "runtimeStopped", "connectionTimeout"],
        "message.reason.errorCode",
      ),
      message: asString(reason.message, "message.reason.message"),
      issueType: parseIssueType(reason.issueType, "message.reason.issueType"),
    },
  };
}
