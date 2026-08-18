import "./styles.css";
import { mockAdapters } from "./mock-adapter";
import {
  initialClientSettings,
  initialState,
  type ClientState,
  type ClientSettings,
  type OverlayTheme,
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
let clientSettingsSaveChain: Promise<void> = Promise.resolve();
let clientSettingsReady = false;

render();
void bootstrapClientSettings();

async function bootstrapClientSettings(): Promise<void> {
  try {
    const settings = await window.echocue.clientSettings.get();
    state = {
      ...state,
      overlay: {
        ...state.overlay,
        ...settings.overlay,
      },
      workspaceView: settings.workspaceView,
    };
  } catch {
    state = {
      ...state,
      overlay: {
        ...state.overlay,
        ...initialClientSettings.overlay,
      },
      workspaceView: initialClientSettings.workspaceView,
    };
  }

  clientSettingsReady = true;
  render();
}

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
  const account = state.account ?? { displayName: "未登录", accountType: "主播" };
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
            <button class="side-nav-item ${state.workspaceView === "overview" ? "is-active" : ""}" type="button" data-action="show-overview"><span class="nav-icon">⌂</span>运行概览</button>
            <button class="side-nav-item ${state.workspaceView === "settings" ? "is-active" : ""}" type="button" data-action="show-settings"><span class="nav-icon">⚙</span>展示设置</button>
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
          ${state.workspaceView === "settings" ? renderSettingsPage(account, runtimeLabel, runtimeTone) : renderOverviewPage(account, selectedRoom, runtimeLabel, runtimeTone, error)}
        </section>
      </div>
    </main>
  `;
}

function renderOverviewPage(
  account: NonNullable<ClientState["account"]>,
  selectedRoom: Room | null,
  runtimeLabel: string,
  runtimeTone: string,
  error: string,
): string {
  return `
    <div class="content-heading">
      <div>
        <p class="eyebrow">运行概览</p>
        <h1>晚上好，${escapeHtml(account.displayName.split(" ")[0] ?? "主播")}</h1>
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
  `;
}

function renderSettingsPage(account: NonNullable<ClientState["account"]>, runtimeLabel: string, runtimeTone: string): string {
  const overlayStatusLabel = state.overlay.isVisible ? "已显示" : "已隐藏";
  const topOn = state.overlay.alwaysOnTop ? "已开启" : "已关闭";
  const clickThroughLabel = state.overlay.clickThrough ? "已开启" : "已关闭";

  return `
    <div class="content-heading">
      <div>
        <p class="eyebrow">展示设置</p>
        <h1>${escapeHtml(account.displayName)} 的展示配置</h1>
        <p>这里调整浮窗显示、交互和视觉参数，所有变更会保存在本地。</p>
      </div>
      <div class="heading-status ${runtimeTone}">
        <span class="status-dot ${runtimeTone === "tone-green" ? "status-dot-green" : runtimeTone === "tone-red" ? "status-dot-red" : "status-dot-amber"}"></span>
        <span>${runtimeLabel}</span>
      </div>
    </div>
    <section class="surface settings-surface">
      <div class="surface-heading">
        <div>
          <h2>浮窗显示</h2>
          <p>控制浮窗的可见性、置顶、穿透和外观。</p>
        </div>
        <span class="status-badge ${state.overlay.isVisible ? "tone-green" : "tone-neutral"}">${overlayStatusLabel}</span>
      </div>
      <div class="overlay-controls">
        <button class="button button-primary" data-action="toggle-overlay" ${!state.lastPush ? "disabled" : ""}>
          <span>${state.overlay.isVisible ? "隐藏浮窗" : "显示浮窗"}</span>
          <span aria-hidden="true">${state.overlay.isVisible ? "□" : "▣"}</span>
        </button>
        <button class="button button-secondary" data-action="toggle-overlay-top" ${!state.overlay.isVisible ? "disabled" : ""}>
          <span>${state.overlay.alwaysOnTop ? "取消置顶" : "保持置顶"}</span>
        </button>
        <button class="button button-secondary" data-action="toggle-overlay-click" ${!state.overlay.isVisible ? "disabled" : ""}>
          <span>${state.overlay.clickThrough ? "恢复点击" : "点击穿透"}</span>
        </button>
        <button class="button button-secondary" data-action="toggle-overlay-theme" ${!state.overlay.isVisible ? "disabled" : ""}>
          <span>${state.overlay.theme === "dark" ? "浅色主题" : "深色主题"}</span>
        </button>
      </div>
      <div class="overlay-sliders">
        <label>
          <span>透明度</span>
          <input type="range" min="0.35" max="1" step="0.005" value="${state.overlay.opacity}" data-action="set-overlay-opacity" ${!state.overlay.isVisible ? "disabled" : ""} />
          <strong data-value="overlay-opacity">${Math.round(state.overlay.opacity * 100)}%</strong>
        </label>
        <label>
          <span>字号</span>
          <input type="range" min="0.85" max="1.35" step="0.01" value="${state.overlay.fontScale}" data-action="set-overlay-font" ${!state.overlay.isVisible ? "disabled" : ""} />
          <strong data-value="overlay-font">${Math.round(state.overlay.fontScale * 100)}%</strong>
        </label>
      </div>
      <div class="settings-summary">
        <div class="metric-row"><span>置顶</span><strong>${topOn}</strong></div>
        <div class="metric-row"><span>点击穿透</span><strong>${clickThroughLabel}</strong></div>
        <div class="metric-row"><span>页面状态</span><strong>${state.workspaceView === "settings" ? "展示设置" : "运行概览"}</strong></div>
      </div>
      <p class="overlay-hint">这里直接承载浮窗设置，作为独立页面保留。</p>
    </section>
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
    if (element instanceof HTMLInputElement && element.type === "range") {
      element.addEventListener("input", () => {
        void handleSliderInput(element.dataset.action ?? "", element.value, element);
      });
      element.addEventListener("change", () => {
        render();
      });
      return;
    }

    element.addEventListener("click", () => {
      void handleAction(element.dataset.action ?? "", element.dataset.roomId);
    });
  });
}

async function handleAction(action: string, roomId?: string, value?: string): Promise<void> {
  if (action === "sign-in") {
    state = { ...state, isLoading: true, errorMessage: null };
    render();
    try {
      const [account, rooms] = await Promise.all([mockAdapters.auth.signIn(), mockAdapters.room.loadRooms()]);
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
    await window.echocue.overlay.close();
    const resetState = structuredClone(initialState);
    state = {
      ...resetState,
      overlay: { ...state.overlay, isVisible: false },
      workspaceView: state.workspaceView,
    };
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
    state = { ...state, lastPush: mockAdapters.push.getPreview(pushIndex++) };
    await syncOverlayContent();
    render();
    return;
  }

  if (action === "toggle-overlay") {
    await toggleOverlay();
    return;
  }

  if (action === "toggle-overlay-top") {
    await setOverlayAlwaysOnTop(!state.overlay.alwaysOnTop);
    return;
  }

  if (action === "toggle-overlay-click") {
    await setOverlayClickThrough(!state.overlay.clickThrough);
    return;
  }

  if (action === "toggle-overlay-theme") {
    await setOverlayTheme(state.overlay.theme === "dark" ? "light" : "dark");
    return;
  }

  if (action === "show-overview" || action === "show-settings") {
    state = {
      ...state,
      workspaceView: action === "show-settings" ? "settings" : "overview",
      errorMessage: null,
    };
    void persistClientSettings();
    render();
  }
}

async function refreshRooms(): Promise<void> {
  state = { ...state, isLoading: true, errorMessage: null };
  render();
  try {
    const rooms = await mockAdapters.room.loadRooms();
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
    await mockAdapters.runtime.start();
    state = {
      ...state,
      runtimeStatus: "running",
      runtimeMessage: "辅助服务运行中",
      lastPush: mockAdapters.push.getPreview(pushIndex++),
    };
    await openOverlayIfNeeded();
    await syncOverlayContent();
  } catch {
    state = { ...state, runtimeStatus: "error", runtimeMessage: "启动失败，请重试。", errorMessage: "mock 运行服务启动失败。" };
  }
  render();
}

async function stopRuntimeFlow(): Promise<void> {
  state = { ...state, runtimeStatus: "paused", runtimeMessage: "正在停止本地辅助服务..." };
  render();
  await mockAdapters.runtime.stop();
  await window.echocue.overlay.close();
  state = {
    ...state,
    runtimeStatus: "idle",
    runtimeMessage: "已停止，等待下一次启动。",
    overlay: { ...state.overlay, isVisible: false },
  };
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

async function toggleOverlay(): Promise<void> {
  if (!state.lastPush) {
    state = { ...state, errorMessage: "暂无可展示的浮窗内容，请先启动辅助服务或模拟新消息。" };
    render();
    return;
  }

  if (state.overlay.isVisible) {
    await window.echocue.overlay.hide();
    state = { ...state, overlay: { ...state.overlay, isVisible: false } };
  } else {
    await window.echocue.overlay.open(state.lastPush);
    await syncOverlaySettings();
    state = { ...state, overlay: { ...state.overlay, isVisible: true }, errorMessage: null };
  }
  await persistClientSettings();
  render();
}

async function syncOverlayContent(): Promise<void> {
  if (state.overlay.isVisible && state.lastPush) {
    await window.echocue.overlay.update(state.lastPush);
  }
}

async function openOverlayIfNeeded(): Promise<void> {
  if (state.overlay.isVisible || !state.lastPush) {
    return;
  }

  await window.echocue.overlay.open(state.lastPush);
  await syncOverlaySettings();
  state = { ...state, overlay: { ...state.overlay, isVisible: true }, errorMessage: null };
  await persistClientSettings();
}

async function syncOverlaySettings(): Promise<void> {
  await Promise.all([
    window.echocue.overlay.setAlwaysOnTop(state.overlay.alwaysOnTop),
    window.echocue.overlay.setOpacity(state.overlay.opacity),
    window.echocue.overlay.setIgnoreMouseEvents(state.overlay.clickThrough),
    window.echocue.overlay.setFontScale(state.overlay.fontScale),
    window.echocue.overlay.setTheme(state.overlay.theme),
  ]);
}

async function setOverlayAlwaysOnTop(alwaysOnTop: boolean): Promise<void> {
  await window.echocue.overlay.setAlwaysOnTop(alwaysOnTop);
  state = { ...state, overlay: { ...state.overlay, alwaysOnTop } };
  await persistClientSettings();
  render();
}

async function setOverlayClickThrough(clickThrough: boolean): Promise<void> {
  await window.echocue.overlay.setIgnoreMouseEvents(clickThrough);
  state = { ...state, overlay: { ...state.overlay, clickThrough } };
  await persistClientSettings();
  render();
}

async function setOverlayTheme(theme: OverlayTheme): Promise<void> {
  await window.echocue.overlay.setTheme(theme);
  state = { ...state, overlay: { ...state.overlay, theme } };
  await persistClientSettings();
  render();
}

async function setOverlayOpacity(opacity: number): Promise<void> {
  if (Number.isNaN(opacity)) {
    return;
  }
  await window.echocue.overlay.setOpacity(opacity);
  state = { ...state, overlay: { ...state.overlay, opacity } };
  await persistClientSettings();
  render();
}

async function setOverlayFontScale(fontScale: number): Promise<void> {
  if (Number.isNaN(fontScale)) {
    return;
  }
  await window.echocue.overlay.setFontScale(fontScale);
  state = { ...state, overlay: { ...state.overlay, fontScale } };
  await persistClientSettings();
  render();
}

async function handleSliderInput(action: string, value: string, element: HTMLInputElement): Promise<void> {
  if (action === "set-overlay-opacity") {
    const opacity = Number.parseFloat(value);
    if (Number.isNaN(opacity)) {
      return;
    }
    void window.echocue.overlay.setOpacity(opacity);
    state = { ...state, overlay: { ...state.overlay, opacity } };
    updateSliderValue(element, `${Math.round(opacity * 100)}%`);
    void persistClientSettings();
    return;
  }

  if (action === "set-overlay-font") {
    const fontScale = Number.parseFloat(value);
    if (Number.isNaN(fontScale)) {
      return;
    }
    void window.echocue.overlay.setFontScale(fontScale);
    state = { ...state, overlay: { ...state.overlay, fontScale } };
    updateSliderValue(element, `${Math.round(fontScale * 100)}%`);
    void persistClientSettings();
  }
}

function snapshotClientSettings(): ClientSettings {
  return {
    overlay: {
      alwaysOnTop: state.overlay.alwaysOnTop,
      clickThrough: state.overlay.clickThrough,
      opacity: state.overlay.opacity,
      fontScale: state.overlay.fontScale,
      theme: state.overlay.theme,
    },
    workspaceView: state.workspaceView,
  };
}

async function persistClientSettings(): Promise<void> {
  if (!clientSettingsReady) {
    return;
  }

  const settings = snapshotClientSettings();
  clientSettingsSaveChain = clientSettingsSaveChain
    .catch(() => undefined)
    .then(() => window.echocue.clientSettings.set(settings))
    .catch((error: unknown) => {
      console.error("Failed to persist client settings:", error);
    });
  await clientSettingsSaveChain;
}

function updateSliderValue(element: HTMLInputElement, text: string): void {
  const label = element.parentElement?.querySelector<HTMLElement>("[data-value]");
  if (label) {
    label.textContent = text;
  }
}
