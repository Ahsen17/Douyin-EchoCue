import {
  mockAccounts,
  mockMembers,
  mockPersonaProfiles,
  mockProviderModels,
  mockRoomsSeed,
  mockSafetyRules,
  mockSessions,
  mockTriggerConfigs,
  mockWorkflowRuns,
} from "./mock-data";
import type {
  AdapterResult,
  MockScenarioKey,
  RoomPermissionSummary,
  RoomSummary,
  WebuiSession,
  WebuiSnapshot,
} from "./types";

const EMPTY_SNAPSHOT: WebuiSnapshot = {
  sessions: mockSessions,
  activeSession: null,
  accounts: [],
  members: [],
  rooms: [],
  personaProfiles: [],
  triggerConfigs: [],
  safetyRules: [],
  workflowRuns: [],
  providerModels: [],
};

export function buildMockSnapshot(sessionId: string, scenario: MockScenarioKey): AdapterResult<WebuiSnapshot> {
  const activeSession = mockSessions.find((session) => session.sessionId === sessionId) ?? mockSessions[0] ?? null;

  if (scenario === "loading") {
    return {
      status: "loading",
      data: { ...EMPTY_SNAPSHOT, activeSession },
      message: "正在加载 mock 场景",
    };
  }

  if (scenario === "error") {
    return {
      status: "error",
      data: { ...EMPTY_SNAPSHOT, activeSession },
      message: "mock adapter 返回系统错误，用于验证错误态。",
    };
  }

  if (scenario === "empty") {
    return {
      status: "empty",
      data: { ...EMPTY_SNAPSHOT, activeSession },
      message: "当前账号暂无可管理直播间。",
    };
  }

  if (!activeSession || scenario === "forbidden" || activeSession.authStatus === "uncertified") {
    return {
      status: "forbidden",
      data: buildVisibleSnapshot(activeSession, true),
      message: "当前用户无权进入管理端主界面。",
    };
  }

  return {
    status: "success",
    data: buildVisibleSnapshot(activeSession, false),
  };
}

export function getDefaultAccountId(snapshot: WebuiSnapshot): string {
  return snapshot.activeSession?.defaultAccountId ?? snapshot.accounts[0]?.accountId ?? "";
}

export function getDefaultRoomId(snapshot: WebuiSnapshot, accountId: string): string {
  return snapshot.rooms.find((room) => room.accountId === accountId)?.roomId ?? snapshot.rooms[0]?.roomId ?? "";
}

function buildVisibleSnapshot(activeSession: WebuiSession | null, forceReadOnly: boolean): WebuiSnapshot {
  const visibleAccountIds = new Set(activeSession?.visibleAccountIds ?? []);
  const accounts = mockAccounts.filter((account) => visibleAccountIds.has(account.accountId));
  const visibleRooms = mockRoomsSeed
    .filter((room) => visibleAccountIds.has(room.accountId))
    .map<RoomSummary>((room) => ({
      ...room,
      permission: buildRoomPermission(activeSession, room.accountId, forceReadOnly),
    }));
  const visibleRoomIds = new Set(visibleRooms.map((room) => room.roomId));

  return {
    sessions: mockSessions,
    activeSession,
    accounts,
    members: mockMembers.filter((member) => visibleAccountIds.has(member.accountId)),
    rooms: visibleRooms,
    personaProfiles: mockPersonaProfiles.filter((profile) => visibleRoomIds.has(profile.roomId)),
    triggerConfigs: mockTriggerConfigs.filter((config) => visibleRoomIds.has(config.roomId)),
    safetyRules: mockSafetyRules.filter(
      (rule) => rule.scope === "global" || visibleAccountIds.has(rule.scopeId) || visibleRoomIds.has(rule.scopeId),
    ),
    workflowRuns: mockWorkflowRuns.filter((run) => visibleRoomIds.has(run.roomId)),
    providerModels: activeSession?.permissions.includes("workflow.debug") ? mockProviderModels : [],
  };
}

function buildRoomPermission(
  activeSession: WebuiSession | null,
  accountId: string,
  forceReadOnly: boolean,
): RoomPermissionSummary {
  const permissions = activeSession?.permissions ?? [];
  const canViewRoom = permissions.includes("room.read") && !forceReadOnly;
  const canViewWorkflow = permissions.includes("workflow.read") && !forceReadOnly;
  const isInvitedPersonalRoom = accountId === "acct_invited_001";
  const canWrite = !forceReadOnly && !isInvitedPersonalRoom;

  return {
    canViewRoom,
    canEditPersona: canWrite && permissions.includes("persona.write"),
    canEditTrigger: canWrite && permissions.includes("trigger.write"),
    canEditSafetyRules: canWrite && permissions.includes("safety.write"),
    canViewWorkflow,
    canViewTechnicalDetails: !forceReadOnly && permissions.includes("workflow.debug"),
    denialReason: canViewRoom ? undefined : "认证状态或授权不足",
  };
}
