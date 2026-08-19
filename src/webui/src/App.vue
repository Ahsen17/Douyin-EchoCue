<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { buildMockSnapshot, getDefaultAccountId, getDefaultRoomId } from "./mock-adapter";
import type {
  AccountSummary,
  MockScenarioKey,
  PersonaStatus,
  PushAction,
  ReviewCategory,
  RoomSummary,
  WebuiRole,
  WorkflowRunSummary,
} from "./types";

type PanelKey = "overview" | "accounts" | "rooms" | "workflow";

interface PanelItem {
  key: PanelKey;
  label: string;
  hint: string;
}

interface ScenarioItem {
  key: MockScenarioKey;
  label: string;
  description: string;
}

const panels: PanelItem[] = [
  { key: "overview", label: "总览", hint: "上下文" },
  { key: "accounts", label: "账号", hint: "认证 / 成员" },
  { key: "rooms", label: "直播间", hint: "配置权限" },
  { key: "workflow", label: "Workflow", hint: "业务摘要" },
];

const scenarios: ScenarioItem[] = [
  { key: "success", label: "成功态", description: "完整 mock 数据" },
  { key: "loading", label: "加载态", description: "请求进行中" },
  { key: "empty", label: "空态", description: "无直播间" },
  { key: "forbidden", label: "无权限", description: "认证或授权不足" },
  { key: "error", label: "错误态", description: "adapter 异常" },
];

const currentPanel = ref<PanelKey>("overview");
const scenarioKey = ref<MockScenarioKey>("success");
const activeSessionId = ref("session_org_admin");
const activeAccountId = ref("");
const activeRoomId = ref("");
const loggedOut = ref(false);

const adapterResult = computed(() =>
  loggedOut.value ? buildMockSnapshot("session_uncertified", "forbidden") : buildMockSnapshot(activeSessionId.value, scenarioKey.value),
);
const snapshot = computed(() => adapterResult.value.data);
const activeSession = computed(() => snapshot.value.activeSession);

const activeAccount = computed<AccountSummary | undefined>(() =>
  snapshot.value.accounts.find((account) => account.accountId === activeAccountId.value),
);

const visibleRooms = computed<RoomSummary[]>(() =>
  snapshot.value.rooms.filter((room) => room.accountId === activeAccountId.value),
);

const activeRoom = computed<RoomSummary | undefined>(() =>
  snapshot.value.rooms.find((room) => room.roomId === activeRoomId.value),
);

const activePersona = computed(() =>
  snapshot.value.personaProfiles.find((profile) => profile.roomId === activeRoom.value?.roomId),
);

const activeTrigger = computed(() =>
  snapshot.value.triggerConfigs.find((config) => config.roomId === activeRoom.value?.roomId),
);

const activeRules = computed(() =>
  snapshot.value.safetyRules.filter(
    (rule) =>
      rule.scope === "global" ||
      rule.scopeId === activeAccountId.value ||
      rule.scopeId === activeRoom.value?.roomId,
  ),
);

const accountMembers = computed(() =>
  snapshot.value.members.filter((member) => member.accountId === activeAccountId.value),
);

const workflowRuns = computed<WorkflowRunSummary[]>(() =>
  snapshot.value.workflowRuns.filter((run) => run.roomId === activeRoom.value?.roomId),
);

const canShowTechnicalDetails = computed(() => activeRoom.value?.permission.canViewTechnicalDetails ?? false);

const permissionSummary = computed(() => {
  const permission = activeRoom.value?.permission;
  if (!permission) {
    return ["未选择直播间"];
  }

  return [
    permission.canViewRoom ? "可查看直播间" : "不可查看直播间",
    permission.canEditPersona ? "可编辑主体档案" : "主体档案只读",
    permission.canEditTrigger ? "可编辑触发配置" : "触发配置只读",
    permission.canEditSafetyRules ? "可编辑安全规则" : "安全规则只读",
    permission.canViewWorkflow ? "可查看回放" : "不可查看回放",
    permission.canViewTechnicalDetails ? "可查看技术详情" : "隐藏技术详情",
  ];
});

watch(
  snapshot,
  (nextSnapshot) => {
    const nextAccountId = nextSnapshot.accounts.some((account) => account.accountId === activeAccountId.value)
      ? activeAccountId.value
      : getDefaultAccountId(nextSnapshot);
    activeAccountId.value = nextAccountId;

    const nextRoomId = nextSnapshot.rooms.some((room) => room.roomId === activeRoomId.value)
      ? activeRoomId.value
      : getDefaultRoomId(nextSnapshot, nextAccountId);
    activeRoomId.value = nextRoomId;
  },
  { immediate: true },
);

function selectAccount(accountId: string): void {
  activeAccountId.value = accountId;
  activeRoomId.value = getDefaultRoomId(snapshot.value, accountId);
}

function selectRoom(roomId: string): void {
  activeRoomId.value = roomId;
}

function loginAs(sessionId: string): void {
  loggedOut.value = false;
  activeSessionId.value = sessionId;
  scenarioKey.value = "success";
}

function logout(): void {
  loggedOut.value = true;
  currentPanel.value = "overview";
}

function roleLabel(role: WebuiRole): string {
  const labels: Record<WebuiRole, string> = {
    platform_admin: "平台管理员",
    org_admin: "机构管理员",
    operator: "运营成员",
    viewer: "只读成员",
  };

  return labels[role];
}

function scenarioLabel(scenario: MockScenarioKey): string {
  return scenarios.find((item) => item.key === scenario)?.label ?? scenario;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    live: "直播中",
    offline: "未开播",
    paused: "暂停",
    published: "已发布",
    draft: "草稿",
    missing: "缺失",
    push: "已推送",
    skip: "未推送",
    failed: "失败",
    safe_high_confidence: "安全高置信",
    low_reply_quality: "回复质量低",
    persona_mismatch: "人设不匹配",
    safety_uncertain: "安全不确定",
    personal: "个人",
    organization: "机构",
    uncertified: "未认证",
    personal_certified: "个人认证",
    organization_certified: "机构认证",
    loading: "加载态",
    empty: "空态",
    error: "错误态",
    forbidden: "无权限",
  };

  return labels[status] ?? status;
}

function personaTone(status: PersonaStatus | undefined): string {
  if (status === "published") {
    return "good";
  }

  if (!status || status === "missing") {
    return "warn";
  }

  return "neutral";
}

function actionTone(action: PushAction): string {
  if (action === "push") {
    return "good";
  }

  if (action === "failed") {
    return "danger";
  }

  return "warn";
}

function reviewTone(category: ReviewCategory): string {
  return category === "safe_high_confidence" ? "good" : "warn";
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">E</div>
        <div>
          <strong>EchoCue</strong>
          <span>Web 管理端</span>
        </div>
      </div>

      <nav class="nav" aria-label="主导航">
        <button
          v-for="panel in panels"
          :key="panel.key"
          class="nav-item"
          :class="{ active: currentPanel === panel.key }"
          type="button"
          @click="currentPanel = panel.key"
        >
          <span>{{ panel.label }}</span>
          <small>{{ panel.hint }}</small>
        </button>
      </nav>

      <div class="side-section">
        <span class="sidebar-label">Mock 场景</span>
        <button
          v-for="scenario in scenarios"
          :key="scenario.key"
          class="scenario-button"
          :class="{ active: scenarioKey === scenario.key && !loggedOut }"
          type="button"
          @click="
            loggedOut = false;
            scenarioKey = scenario.key;
          "
        >
          <span>{{ scenario.label }}</span>
          <small>{{ scenario.description }}</small>
        </button>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div class="title-group">
          <p class="eyebrow">{{ scenarioLabel(scenarioKey) }} · mock-first adapter</p>
          <h1>Web 管理端主界面</h1>
        </div>
        <div class="topbar-actions">
          <label class="select-field">
            <span>登录身份</span>
            <select v-model="activeSessionId" :disabled="loggedOut">
              <option v-for="session in snapshot.sessions" :key="session.sessionId" :value="session.sessionId">
                {{ session.displayName }}
              </option>
            </select>
          </label>
          <button class="ghost-button" type="button" @click="loggedOut ? loginAs(activeSessionId) : logout()">
            {{ loggedOut ? "登录" : "退出" }}
          </button>
          <div class="user-summary" aria-label="当前用户">
            <div class="user-avatar" aria-hidden="true">{{ activeSession?.displayName.slice(0, 1) ?? "-" }}</div>
            <div class="user-meta">
              <strong>{{ activeSession?.displayName ?? "未登录" }}</strong>
              <span>{{ activeSession ? roleLabel(activeSession.role) : "无会话" }}</span>
            </div>
          </div>
        </div>
      </header>

      <section v-if="adapterResult.status !== 'success'" class="state-panel" :class="adapterResult.status">
        <strong>{{ statusLabel(adapterResult.status) }}</strong>
        <span>{{ adapterResult.message }}</span>
      </section>

      <section class="stats">
        <article class="stat">
          <span>账号</span>
          <strong>{{ snapshot.accounts.length }}</strong>
        </article>
        <article class="stat">
          <span>成员</span>
          <strong>{{ snapshot.members.length }}</strong>
        </article>
        <article class="stat">
          <span>直播间</span>
          <strong>{{ snapshot.rooms.length }}</strong>
        </article>
        <article class="stat">
          <span>Workflow</span>
          <strong>{{ snapshot.workflowRuns.length }}</strong>
        </article>
      </section>

      <section v-if="currentPanel === 'overview'" class="layout">
        <article class="panel wide">
          <div class="panel-head">
            <h2>当前上下文</h2>
            <span class="badge" :class="activeRoom?.liveStatus">{{ statusLabel(activeRoom?.liveStatus ?? "offline") }}</span>
          </div>
          <div class="context-grid">
            <div>
              <span class="field-label">账户</span>
              <strong>{{ activeAccount?.displayName ?? "未选择" }}</strong>
              <p>{{ activeAccount ? statusLabel(activeAccount.authStatus) : "-" }}</p>
            </div>
            <div>
              <span class="field-label">直播间</span>
              <strong>{{ activeRoom?.displayName ?? "未选择" }}</strong>
              <p>{{ activeRoom?.authorizationLabel ?? "-" }}</p>
            </div>
            <div>
              <span class="field-label">主体档案</span>
              <strong>{{ activePersona?.title ?? "未配置主体档案" }}</strong>
              <p>v{{ activePersona?.version ?? 0 }} · {{ statusLabel(activePersona?.status ?? "missing") }}</p>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <h2>权限摘要</h2>
            <span class="hint">adapter 返回</span>
          </div>
          <div class="tag-list">
            <span v-for="item in permissionSummary" :key="item" class="tag">{{ item }}</span>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head">
            <h2>上下文切换</h2>
            <span class="hint">账号 / 直播间</span>
          </div>
          <div class="split-controls">
            <label class="select-field">
              <span>当前账号</span>
              <select v-model="activeAccountId" @change="selectAccount(activeAccountId)">
                <option value="">无账号</option>
                <option v-for="account in snapshot.accounts" :key="account.accountId" :value="account.accountId">
                  {{ account.displayName }}
                </option>
              </select>
            </label>
            <label class="select-field">
              <span>当前直播间</span>
              <select v-model="activeRoomId" @change="selectRoom(activeRoomId)">
                <option value="">无直播间</option>
                <option v-for="room in visibleRooms" :key="room.roomId" :value="room.roomId">
                  {{ room.displayName }}
                </option>
              </select>
            </label>
          </div>
        </article>
      </section>

      <section v-else-if="currentPanel === 'accounts'" class="layout">
        <article class="panel wide">
          <div class="panel-head">
            <h2>账号与成员</h2>
            <span class="hint">个人 / 机构 / 受邀个人</span>
          </div>
          <div class="table">
            <div v-for="account in snapshot.accounts" :key="account.accountId" class="table-row">
              <div>
                <strong>{{ account.displayName }}</strong>
                <span>{{ account.organizationName ?? statusLabel(account.accountType) }}</span>
              </div>
              <div class="row-meta">
                <span class="badge">{{ statusLabel(account.authStatus) }}</span>
                <span>{{ account.memberCount }} 成员</span>
                <span>{{ account.roomCount }} 直播间</span>
              </div>
            </div>
          </div>
        </article>

        <article class="panel wide">
          <div class="panel-head">
            <h2>当前账号成员</h2>
            <span class="hint">{{ activeAccount?.displayName ?? "无账号" }}</span>
          </div>
          <div v-if="accountMembers.length > 0" class="member-grid">
            <article v-for="member in accountMembers" :key="member.memberId" class="compact-card">
              <strong>{{ member.displayName }}</strong>
              <span>{{ roleLabel(member.role) }}</span>
              <p>{{ member.roomIds.length }} 个直播间授权</p>
            </article>
          </div>
          <p v-else class="empty-text">当前账号没有机构成员数据。</p>
        </article>
      </section>

      <section v-else-if="currentPanel === 'rooms'" class="layout">
        <article class="panel wide">
          <div class="panel-head">
            <h2>直播间与配置入口</h2>
            <span class="hint">权限差异直接来自 adapter</span>
          </div>
          <div class="room-grid">
            <button
              v-for="room in snapshot.rooms"
              :key="room.roomId"
              class="room-card"
              :class="{ active: room.roomId === activeRoomId }"
              type="button"
              @click="
                activeAccountId = room.accountId;
                selectRoom(room.roomId);
              "
            >
              <span class="badge" :class="room.liveStatus">{{ statusLabel(room.liveStatus) }}</span>
              <strong>{{ room.displayName }}</strong>
              <span>{{ room.ownerLabel }} · {{ room.authorizationLabel }}</span>
            </button>
          </div>
        </article>

        <article class="panel wide">
          <div class="config-grid">
            <div class="config-card">
              <span class="field-label">主体档案</span>
              <strong>{{ activePersona?.title ?? "未配置" }}</strong>
              <p>v{{ activePersona?.version ?? 0 }} · {{ statusLabel(activePersona?.status ?? "missing") }}</p>
              <span class="badge" :class="personaTone(activePersona?.status)">
                {{ activeRoom?.permission.canEditPersona ? "可编辑" : "只读" }}
              </span>
            </div>
            <div class="config-card">
              <span class="field-label">触发配置</span>
              <strong>{{ activeTrigger?.enabled ? "启用" : "未启用" }}</strong>
              <p>
                {{ activeTrigger?.windowSeconds ?? "-" }}s 窗口 · 冷静期
                {{ activeTrigger?.cooldownSeconds ?? "-" }}s
              </p>
              <span class="badge">{{ activeRoom?.permission.canEditTrigger ? "可编辑" : "只读" }}</span>
            </div>
            <div class="config-card">
              <span class="field-label">安全规则</span>
              <strong>{{ activeRules.length }}</strong>
              <p>{{ activeRules[0]?.blockedTerms.join("、") ?? "无适用规则" }}</p>
              <span class="badge">{{ activeRoom?.permission.canEditSafetyRules ? "可编辑" : "只读" }}</span>
            </div>
          </div>
        </article>
      </section>

      <section v-else class="layout">
        <article class="panel wide">
          <div class="panel-head">
            <h2>Workflow 最近记录</h2>
            <span class="hint">{{ activeRoom?.displayName ?? "无直播间" }}</span>
          </div>
          <div v-if="workflowRuns.length > 0 && activeRoom?.permission.canViewWorkflow" class="stack">
            <article v-for="run in workflowRuns" :key="run.runId" class="workflow-item">
              <div>
                <strong>{{ run.commentDisplay }}</strong>
                <span>{{ run.quickReply || run.skipReason }}</span>
                <p>{{ run.cue }}</p>
              </div>
              <div class="workflow-meta">
                <span class="badge" :class="actionTone(run.pushAction)">{{ statusLabel(run.pushAction) }}</span>
                <span class="badge" :class="reviewTone(run.reviewCategory)">{{ statusLabel(run.reviewCategory) }}</span>
              </div>
            </article>
          </div>
          <p v-else class="empty-text">当前没有可展示的 Workflow 业务摘要。</p>
        </article>

        <article v-if="canShowTechnicalDetails" class="panel wide">
          <div class="panel-head">
            <h2>平台模型状态</h2>
            <span class="hint">仅平台管理员可见</span>
          </div>
          <div class="table">
            <div v-for="model in snapshot.providerModels" :key="`${model.provider}:${model.modelId}`" class="table-row">
              <div>
                <strong>{{ model.provider }}</strong>
                <span>{{ model.modelId }}</span>
              </div>
              <div class="row-meta">
                <span class="badge" :class="model.available ? 'good' : 'warn'">
                  {{ model.available ? "可用" : "冷却中" }}
                </span>
                <span>{{ model.failureCount }} 次失败</span>
              </div>
            </div>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>
