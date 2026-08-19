export type WebuiRole = "platform_admin" | "org_admin" | "operator" | "viewer";

export type AuthStatus = "uncertified" | "personal_certified" | "organization_certified";

export type AccountType = "personal" | "organization";

export type LiveStatus = "offline" | "live" | "paused";

export type PersonaStatus = "draft" | "published" | "missing";

export type RuleScope = "global" | "organization" | "room";

export type PushAction = "push" | "skip" | "failed";

export type ReviewCategory = "safe_high_confidence" | "low_reply_quality" | "persona_mismatch" | "safety_uncertain";

export type MockScenarioKey = "success" | "loading" | "empty" | "error" | "forbidden";

export type AdapterStatus = "success" | "loading" | "empty" | "error" | "forbidden";

export type PermissionKey =
  | "account.read"
  | "member.read"
  | "room.read"
  | "persona.write"
  | "trigger.write"
  | "safety.write"
  | "workflow.read"
  | "workflow.debug";

export interface WebuiSession {
  sessionId: string;
  userId: string;
  username: string;
  displayName: string;
  role: WebuiRole;
  authStatus: AuthStatus;
  permissions: PermissionKey[];
  defaultAccountId?: string;
  visibleAccountIds: string[];
}

export interface AccountSummary {
  accountId: string;
  accountType: AccountType;
  authStatus: AuthStatus;
  displayName: string;
  organizationName?: string;
  memberCount: number;
  roomCount: number;
}

export interface MemberSummary {
  memberId: string;
  accountId: string;
  displayName: string;
  role: WebuiRole;
  roomIds: string[];
  active: boolean;
}

export interface RoomPermissionSummary {
  canViewRoom: boolean;
  canEditPersona: boolean;
  canEditTrigger: boolean;
  canEditSafetyRules: boolean;
  canViewWorkflow: boolean;
  canViewTechnicalDetails: boolean;
  denialReason?: string;
}

export interface RoomSummary {
  roomId: string;
  accountId: string;
  displayName: string;
  ownerLabel: string;
  liveStatus: LiveStatus;
  authorizationLabel: string;
  permission: RoomPermissionSummary;
}

export interface PersonaProfileSummary {
  profileId: string;
  roomId: string;
  title: string;
  version: number;
  status: PersonaStatus;
  updatedAt: string;
}

export interface TriggerConfigSummary {
  roomId: string;
  enabled: boolean;
  windowSeconds: number;
  cooldownSeconds: number;
  minCommentCount: number;
  highValueThreshold: number;
  semanticTags: string[];
}

export interface SafetyRuleSummary {
  ruleId: string;
  scope: RuleScope;
  scopeId: string;
  enabled: boolean;
  blockedTerms: string[];
  reviewRequired: boolean;
}

export interface WorkflowRunSummary {
  runId: string;
  roomId: string;
  commentDisplay: string;
  quickReply: string;
  cue: string;
  pushAction: PushAction;
  skipReason: string;
  reviewCategory: ReviewCategory;
  createdAt: string;
}

export interface ProviderModelStatus {
  provider: string;
  modelId: string;
  available: boolean;
  failureCount: number;
  cooldownUntil?: string;
}

export interface WebuiSnapshot {
  sessions: WebuiSession[];
  activeSession: WebuiSession | null;
  accounts: AccountSummary[];
  members: MemberSummary[];
  rooms: RoomSummary[];
  personaProfiles: PersonaProfileSummary[];
  triggerConfigs: TriggerConfigSummary[];
  safetyRules: SafetyRuleSummary[];
  workflowRuns: WorkflowRunSummary[];
  providerModels: ProviderModelStatus[];
}

export interface AdapterResult<T> {
  status: AdapterStatus;
  data: T;
  message?: string;
}
