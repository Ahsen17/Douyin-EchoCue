import "./styles.css";
import { getMockPush, loadRooms, signIn, startRuntime, stopRuntime } from "./mock-adapter";
import {
  initialState,
  type ClientState,
  type Room,
  type RuntimeStatus,
} from "./state";

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Renderer root element was not found.");
}

const root = app;

let state: ClientState = structuredClone(initialState);
let pushIndex = 0;

render();

function render(): void {
  root.innerHTML = state.screen === "welcome" ? renderWelcome() : renderWorkspace();
  bindEvents();
}

function renderWelcome(): string {
  const modeLabel = window.echocue.isDevelopment ? "开发模式" : "正式模式";
  const error = state.errorMessage
    ? `<div class="alert alert-error" role="alert">${escapeHtml(state.errorMessage)}</div>`
    : "";
  const loadingLabel = state.isLoading ? "正在载入 mock 账户..." : "进入主播工作台";

  return `
    <main class="welcome-page">
      <section class="welcome-copy">
        <div class="brand-lockup">
          <span class="brand-mark" aria-hidden="true">EC</span>
          <span class="brand-name">EchoCue Client</span>
        </div>
        <p class="eyebrow">主播端工作台</p>
        <h1>让每一条弹幕，<br /><em>都有下一句。</em></h1>
        <p class="welcome-description">
          在直播过程中快速浏览互动重点、回复建议和提词。当前页面使用本地 mock 数据，
          不会连接主后端服务。
        </p>
        <div class="welcome-meta">
          <span class="status-dot status-dot-green"></span>
          <span>本地 mock 环境 · ${modeLabel}</span>
        </div>
      </section>
      <section class="signin-panel" aria-labelledby="signin-title">
        <div class="panel-kicker">准备开始</div>
        <h2 id="signin-title">进入工作台</h2>
        <p>使用预置主播账号查看主窗口的运行流程。</p>
        ${error}
        <button class="button button-primary button-wide" data-action="sign-in" ${state.isLoading ? "disabled" : ""}>
          <span>${loadingLabel}</span>
          ${state.isLoading ? '<span class="spinner" aria-hidden="true"></span>' : '<span aria-hidden="true">→</span>'}
        </button>
        <div class="signin-note">
          <span class="note-icon" aria-hidden="true">i</span>
          <span>Stage 2 仅展示界面和状态切换，真实登录将在后续 adapter 阶段接入。</span>
        </div>
      </section>
    </main>
  `;
}

function renderWorkspace(): string {
  const account = state.account;
  const selectedRoom = getSelectedRoom();
  const runtimeLabel = getRuntimeLabel(state.runtimeStatus);
  const runtimeTone = getRuntimeTone(state.runtimeStatus);
  const error = state.errorMessage
    ? `<div class="alert alert-error workspace-alert" role="alert">${escapeHtml(state.errorMessage)}</div>`
    : "";

  return `
    <main class="workspace">
      <header class="topbar">
        <div class="brand-lockup">
          <span class="brand-mark brand-mark-small" aria-hidden="true">EC</span>
          <span class="brand-name">EchoCue Client</span>
        </div>
        <div class="topbar-actions">
          <span class="environment-label"><span class="status-dot status-dot-green"></span>Mock 环境</span>
          <button class="icon-button" data-action="sign-out" title="退出当前账号" aria-label="退出当前账号">↪</button>
          <div class="account-chip">
            <span class="avatar" aria-hidden="true">${escapeHtml(account?.displayName.slice(0, 1) ?? "E")}</span>
            <span>
              <strong>${escapeHtml(account?.displayName ?? "未登录")}</strong>
              <small>${escapeHtml(account?.accountType ?? "")}</small>
            </span>
          </div>
        </div>
      </header>
      <div class="workspace-body">
        <aside class="sidebar">
          <div class="sidebar-heading">
            <div>
              <p class="panel-kicker">工作区</p>
              <h2>直播控制台</h2>
            </div>
            <span class="live-pill"><span class="status-dot status-dot-green"></span>在线</span>
          </div>
          <nav class="side-nav" aria-label="主导航">
            <button class="side-nav-item is-active" type="button"><span class="nav-icon">⌂</span>运行概览</button>
            <button class="side-nav-item" type="button" data-action="show-settings"><span class="nav-icon">⚙</span>展示设置</button>
          </nav>
          <div class="sidebar-footer">
            <div class="connection-card">
              <div class="connection-icon">↗</div>
              <div>
                <strong>服务连接</strong>
                <span>当前使用本地 mock</span>
              </div>
              <span class="status-dot status-dot-amber"></span>
            </div>
            <p class="version-label">EchoCue Client · M6</p>
          </div>
        </aside>
        <section class="content">
          <div class="content-heading">
            <div>
              <p class="eyebrow">运行概览</p>
              <h1>晚上好，${escapeHtml(account?.displayName.split(" ")[0] ?? "主播")}</h1>
              <p>准备好后启动本地辅助服务，开始接收直播间互动。</p>
            </div>
            <div class="heading-status ${runtimeTone}">
              <span class="status-dot ${runtimeTone === "tone-green" ? "status-dot-green" : runtimeTone === "tone-red" ? "status-dot-red" : "status-dot-amber"}"></span>
              <span>${runtimeLabel}</span>
            </div>
          </div>
          ${error}
          <div class="content-grid">
            <section class="surface room-surface">
              <div class="surface-heading">
                <div>
                  <h2>直播间</h2>
                  <p>选择本次需要辅助的直播间</p>
                </div>
                <span class="surface-count">${state.rooms.length} 个直播间</span>
              </div>
              <div class="room-list">
                ${state.isLoading ? renderRoomLoading() : state.rooms.length ? state.rooms.map(renderRoom).join("") : renderRoomEmpty()}
              </div>
              <div class="room-actions">
                <button class="button button-primary" data-action="toggle-runtime" ${state.isLoading || !selectedRoom ? "disabled" : ""}>
                  <span>${state.runtimeStatus === "running" || state.runtimeStatus === "starting" ? "停止辅助服务" : "启动辅助服务"}</span>
                  <span aria-hidden="true">${state.runtimeStatus === "running" || state.runtimeStatus === "starting" ? "■" : "▶"}</span>
                </button>
                <button class="button button-secondary" data-action="refresh-rooms" ${state.isLoading ? "disabled" : ""}>
                  <span aria-hidden="true">↻</span><span>刷新直播间</span>
                </button>
              </div>
            </section>
            <section class="surface runtime-surface">
              <div class="surface-heading">
                <div>
                  <h2>运行状态</h2>
                  <p>本地辅助服务当前状态</p>
                </div>
                <span class="status-badge ${runtimeTone}">${runtimeLabel}</span>
              </div>
              <div class="runtime-overview">
                <div class="runtime-ring ${runtimeTone}"><span>${state.runtimeStatus === "running" ? "ON" : "—"}</span></div>
                <div>
                  <strong>${escapeHtml(state.runtimeMessage)}</strong>
                  <p>${selectedRoom ? escapeHtml(selectedRoom.name) : "尚未选择直播间"}</p>
                </div>
              </div>
              <div class="metric-list">
                <div class="metric-row"><span>直播状态</span><strong class="${selectedRoom?.status === "live" ? "value-green" : ""}">${selectedRoom ? (selectedRoom.status === "live" ? "直播中" : "未开播") : "—"}</strong></div>
                <div class="metric-row"><span>当前在线观众</span><strong>${selectedRoom ? formatNumber(selectedRoom.viewerCount) : "—"}</strong></div>
                <div class="metric-row"><span>最近推送</span><strong>${state.lastPush?.createdAt ?? "暂无"}</strong></div>
              </div>
            </section>
          </div>
          <section class="surface push-surface">
            <div class="surface-heading">
              <div>
                <h2>最近互动预览</h2>
                <p>展示将出现在后续浮窗中的内容</p>
              </div>
              <button class="text-button" data-action="next-push" ${state.runtimeStatus !== "running" ? "disabled" : ""}>模拟新消息 <span aria-hidden="true">→</span></button>
            </div>
            ${state.lastPush ? renderPush(state.lastPush) : renderPushEmpty()}
          </section>
        </section>
      </div>
    </main>
  `;
}

function renderRoom(room: Room): string {
  const selected = room.id === state.selectedRoomId;
  return `
    <button class="room-item ${selected ? "is-selected" : ""}" data-action="select-room" data-room-id="${escapeHtml(room.id)}">
      <span class="room-status ${room.status === "live" ? "room-status-live" : "room-status-offline"}"></span>
      <span class="room-details">
        <strong>${escapeHtml(room.name)}</strong>
        <span>${escapeHtml(room.anchorName)} · ${room.status === "live" ? `${formatNumber(room.viewerCount)} 人观看` : "未开播"}</span>
      </span>
      <span class="room-last-active">${escapeHtml(room.lastActiveLabel)}</span>
      <span class="room-check" aria-hidden="true">${selected ? "✓" : ""}</span>
    </button>
  `;
}

function renderRoomLoading(): string {
  return `<div class="empty-state"><span class="spinner spinner-dark"></span><strong>正在读取直播间</strong><span>mock adapter 正在准备数据</span></div>`;
}

function renderRoomEmpty(): string {
  return `<div class="empty-state"><span class="empty-icon">—</span><strong>暂无可用直播间</strong><span>刷新后将再次尝试读取 mock 数据。</span></div>`;
}

function renderPush(push: NonNullable<ClientState["lastPush"]>): string {
  return `
    <div class="push-content">
      <div class="push-comment">
        <span class="push-label">观众弹幕</span>
        <p>“${escapeHtml(push.commentDisplay)}”</p>
        <span class="push-time">${escapeHtml(push.createdAt)}</span>
      </div>
      <div class="push-divider"></div>
      <div class="push-suggestion">
        <div class="suggestion-block"><span class="push-label">建议回复</span><p>${escapeHtml(push.quickReply)}</p></div>
        <div class="suggestion-block"><span class="push-label">提词</span><p>${escapeHtml(push.cue)}</p></div>
      </div>
    </div>
  `;
}

function renderPushEmpty(): string {
  return `<div class="push-empty"><span class="empty-icon">✦</span><div><strong>启动辅助服务后，这里会出现互动预览</strong><span>你可以先选择一个直播间，再开始运行。</span></div></div>`;
}

function bindEvents(): void {
  root.querySelectorAll<HTMLElement>("[data-action]").forEach((element) => {
    element.addEventListener("click", () => {
      void handleAction(element.dataset.action ?? "", element.dataset.roomId);
    });
  });
}

async function handleAction(action: string, roomId?: string): Promise<void> {
  if (action === "sign-in") {
    state = { ...state, isLoading: true, errorMessage: null };
    render();
    try {
      const [account, rooms] = await Promise.all([signIn(), loadRooms()]);
      state = {
        ...state,
        screen: "workspace",
        isLoading: false,
        account,
        rooms,
        selectedRoomId: rooms[0]?.id ?? null,
      };
    } catch {
      state = { ...state, isLoading: false, errorMessage: "mock 账户暂时不可用，请稍后重试。" };
    }
    render();
    return;
  }

  if (action === "sign-out") {
    state = structuredClone(initialState);
    pushIndex = 0;
    render();
    return;
  }

  if (action === "select-room" && roomId && state.runtimeStatus !== "running") {
    state = { ...state, selectedRoomId: roomId, errorMessage: null };
    render();
    return;
  }

  if (action === "refresh-rooms") {
    await refreshRooms();
    return;
  }

  if (action === "toggle-runtime") {
    if (state.runtimeStatus === "running" || state.runtimeStatus === "starting") {
      await stopRuntimeFlow();
    } else {
      await startRuntimeFlow();
    }
    return;
  }

  if (action === "next-push" && state.runtimeStatus === "running") {
    state = { ...state, lastPush: getMockPush(pushIndex++) };
    render();
  }

  if (action === "show-settings") {
    state = { ...state, errorMessage: "展示设置将在 M6 Stage 4 提供，本阶段保留主窗口流程。" };
    render();
  }
}

async function refreshRooms(): Promise<void> {
  state = { ...state, isLoading: true, errorMessage: null };
  render();
  try {
    const rooms = await loadRooms();
    state = {
      ...state,
      isLoading: false,
      rooms,
      selectedRoomId: rooms.some((room) => room.id === state.selectedRoomId)
        ? state.selectedRoomId
        : rooms[0]?.id ?? null,
    };
  } catch {
    state = { ...state, isLoading: false, errorMessage: "直播间列表读取失败，请重试。" };
  }
  render();
}

async function startRuntimeFlow(): Promise<void> {
  if (!state.selectedRoomId) {
    state = { ...state, errorMessage: "请先选择一个直播间。" };
    render();
    return;
  }

  state = {
    ...state,
    runtimeStatus: "starting",
    runtimeMessage: "正在启动本地辅助服务...",
    errorMessage: null,
  };
  render();
  try {
    await startRuntime();
    state = {
      ...state,
      runtimeStatus: "running",
      runtimeMessage: "辅助服务运行中",
      lastPush: getMockPush(pushIndex++),
    };
  } catch {
    state = { ...state, runtimeStatus: "error", runtimeMessage: "启动失败，请重试。", errorMessage: "mock 运行服务启动失败。" };
  }
  render();
}

async function stopRuntimeFlow(): Promise<void> {
  state = { ...state, runtimeStatus: "paused", runtimeMessage: "正在停止本地辅助服务..." };
  render();
  await stopRuntime();
  state = { ...state, runtimeStatus: "idle", runtimeMessage: "已停止，等待下一次启动。" };
  render();
}

function getSelectedRoom(): Room | null {
  return state.rooms.find((room) => room.id === state.selectedRoomId) ?? null;
}

function getRuntimeLabel(status: RuntimeStatus): string {
  return { idle: "未启动", starting: "启动中", running: "运行中", paused: "停止中", error: "异常" }[status];
}

function getRuntimeTone(status: RuntimeStatus): string {
  return { idle: "tone-neutral", starting: "tone-amber", running: "tone-green", paused: "tone-amber", error: "tone-red" }[status];
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character] ?? character);
}
