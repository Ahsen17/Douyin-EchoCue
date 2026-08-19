import type {
  AccountSummary,
  MemberSummary,
  ProviderModelStatus,
  SafetyRuleSummary,
  TriggerConfigSummary,
  WebuiSession,
  WorkflowRunSummary,
} from "./types";

export const mockSessions: WebuiSession[] = [
  {
    sessionId: "session_platform_admin",
    userId: "user_platform_001",
    username: "platform.admin",
    displayName: "平台管理员",
    role: "platform_admin",
    authStatus: "organization_certified",
    defaultAccountId: "acct_org_001",
    visibleAccountIds: ["acct_org_001", "acct_personal_001", "acct_invited_001"],
    permissions: [
      "account.read",
      "member.read",
      "room.read",
      "persona.write",
      "trigger.write",
      "safety.write",
      "workflow.read",
      "workflow.debug",
    ],
  },
  {
    sessionId: "session_org_admin",
    userId: "user_org_001",
    username: "brand.admin",
    displayName: "机构运营主管",
    role: "org_admin",
    authStatus: "organization_certified",
    defaultAccountId: "acct_org_001",
    visibleAccountIds: ["acct_org_001", "acct_invited_001"],
    permissions: [
      "account.read",
      "member.read",
      "room.read",
      "persona.write",
      "trigger.write",
      "safety.write",
      "workflow.read",
    ],
  },
  {
    sessionId: "session_personal_owner",
    userId: "user_personal_001",
    username: "personal.owner",
    displayName: "个人主播",
    role: "operator",
    authStatus: "personal_certified",
    defaultAccountId: "acct_personal_001",
    visibleAccountIds: ["acct_personal_001"],
    permissions: ["account.read", "room.read", "persona.write", "trigger.write", "workflow.read"],
  },
  {
    sessionId: "session_viewer",
    userId: "user_viewer_001",
    username: "room.viewer",
    displayName: "只读成员",
    role: "viewer",
    authStatus: "organization_certified",
    defaultAccountId: "acct_org_001",
    visibleAccountIds: ["acct_org_001"],
    permissions: ["account.read", "room.read", "workflow.read"],
  },
  {
    sessionId: "session_uncertified",
    userId: "user_guest_001",
    username: "guest",
    displayName: "未认证用户",
    role: "viewer",
    authStatus: "uncertified",
    visibleAccountIds: [],
    permissions: [],
  },
];

export const mockAccounts: AccountSummary[] = [
  {
    accountId: "acct_org_001",
    accountType: "organization",
    authStatus: "organization_certified",
    displayName: "品牌旗舰运营号",
    organizationName: "EchoCue 演示机构",
    memberCount: 3,
    roomCount: 2,
  },
  {
    accountId: "acct_personal_001",
    accountType: "personal",
    authStatus: "personal_certified",
    displayName: "阿森直播助手",
    memberCount: 1,
    roomCount: 1,
  },
  {
    accountId: "acct_invited_001",
    accountType: "personal",
    authStatus: "personal_certified",
    displayName: "受邀个人直播间",
    organizationName: "EchoCue 演示机构",
    memberCount: 1,
    roomCount: 1,
  },
];

export const mockMembers: MemberSummary[] = [
  {
    memberId: "member_org_admin",
    accountId: "acct_org_001",
    displayName: "机构运营主管",
    role: "org_admin",
    roomIds: ["room_001", "room_003"],
    active: true,
  },
  {
    memberId: "member_operator",
    accountId: "acct_org_001",
    displayName: "直播运营",
    role: "operator",
    roomIds: ["room_001"],
    active: true,
  },
  {
    memberId: "member_viewer",
    accountId: "acct_org_001",
    displayName: "只读成员",
    role: "viewer",
    roomIds: ["room_003"],
    active: true,
  },
];

export const mockRoomsSeed = [
  {
    roomId: "room_001",
    accountId: "acct_org_001",
    displayName: "晚间福利直播间",
    ownerLabel: "机构自有",
    liveStatus: "live",
    authorizationLabel: "可配置与回放",
  },
  {
    roomId: "room_003",
    accountId: "acct_org_001",
    displayName: "新品讲解直播间",
    ownerLabel: "机构自有",
    liveStatus: "paused",
    authorizationLabel: "只读回放",
  },
  {
    roomId: "room_002",
    accountId: "acct_personal_001",
    displayName: "个人答疑直播间",
    ownerLabel: "个人自有",
    liveStatus: "offline",
    authorizationLabel: "个人可配置",
  },
  {
    roomId: "room_004",
    accountId: "acct_invited_001",
    displayName: "受邀联播直播间",
    ownerLabel: "受邀个人",
    liveStatus: "offline",
    authorizationLabel: "机构只读",
  },
] as const;

export const mockPersonaProfiles = [
  {
    profileId: "persona_001",
    roomId: "room_001",
    title: "高频答疑导购型主播",
    version: 3,
    status: "published",
    updatedAt: "2026-08-18T20:30:00+08:00",
  },
  {
    profileId: "persona_002",
    roomId: "room_002",
    title: "轻松闲聊型主播",
    version: 1,
    status: "draft",
    updatedAt: "2026-08-17T13:12:00+08:00",
  },
] as const;

export const mockTriggerConfigs: TriggerConfigSummary[] = [
  {
    roomId: "room_001",
    enabled: true,
    windowSeconds: 10,
    cooldownSeconds: 10,
    minCommentCount: 1,
    highValueThreshold: 0.7,
    semanticTags: ["playful_joke", "persona_praise", "interactive_prompt"],
  },
  {
    roomId: "room_002",
    enabled: true,
    windowSeconds: 12,
    cooldownSeconds: 15,
    minCommentCount: 2,
    highValueThreshold: 0.75,
    semanticTags: ["interactive_prompt", "atmosphere_boost"],
  },
];

export const mockSafetyRules: SafetyRuleSummary[] = [
  {
    ruleId: "rule_global_001",
    scope: "global",
    scopeId: "global",
    enabled: true,
    blockedTerms: ["站外交易", "私下转账"],
    reviewRequired: true,
  },
  {
    ruleId: "rule_org_001",
    scope: "organization",
    scopeId: "acct_org_001",
    enabled: true,
    blockedTerms: ["绝对最低价", "包治"],
    reviewRequired: true,
  },
  {
    ruleId: "rule_room_001",
    scope: "room",
    scopeId: "room_001",
    enabled: true,
    blockedTerms: ["全网第一"],
    reviewRequired: false,
  },
];

export const mockWorkflowRuns: WorkflowRunSummary[] = [
  {
    runId: "run_20260818_001",
    roomId: "room_001",
    commentDisplay: "这件衣服 165 能穿吗？",
    quickReply: "可以，建议先看肩宽。",
    cue: "尺码建议 / 肩宽 / 宽松感",
    pushAction: "push",
    skipReason: "",
    reviewCategory: "safe_high_confidence",
    createdAt: "2026-08-18T21:01:14+08:00",
  },
  {
    runId: "run_20260818_002",
    roomId: "room_001",
    commentDisplay: "能不能私下给我更低价？",
    quickReply: "",
    cue: "命中安全规则，跳过推送。",
    pushAction: "skip",
    skipReason: "命中站外交易风险",
    reviewCategory: "safety_uncertain",
    createdAt: "2026-08-18T21:04:52+08:00",
  },
  {
    runId: "run_20260818_003",
    roomId: "room_003",
    commentDisplay: "主播这波讲得像脱口秀",
    quickReply: "那我继续加点料。",
    cue: "接梗 / 轻松回应 / 回到商品",
    pushAction: "push",
    skipReason: "",
    reviewCategory: "safe_high_confidence",
    createdAt: "2026-08-18T21:12:09+08:00",
  },
];

export const mockProviderModels: ProviderModelStatus[] = [
  {
    provider: "openai-compatible-primary",
    modelId: "gpt-main",
    available: true,
    failureCount: 0,
  },
  {
    provider: "openai-compatible-backup",
    modelId: "gpt-fallback",
    available: false,
    failureCount: 5,
    cooldownUntil: "2026-08-18T21:18:00+08:00",
  },
];
