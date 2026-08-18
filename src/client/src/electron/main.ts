import { app, BrowserWindow, ipcMain, type IpcMainInvokeEvent } from "electron";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";

const isDevelopment = !app.isPackaged;
const rendererUrl = process.env.ECHOCUE_RENDERER_URL ?? "http://127.0.0.1:5173";
const clientSettingsFileName = "client-settings.json";

type OverlayTheme = "light" | "dark";
const overlayAlwaysOnTopLevel = "screen-saver" as const;
const overlayConstraintIntervalMs = 300;
const overlayTopmostResetIntervalMs = 1800;

type OverlayPayload = {
  commentDisplay: string;
  quickReply: string;
  cue: string;
  createdAt: string;
};

type ClientSettings = {
  overlay: {
    alwaysOnTop: boolean;
    clickThrough: boolean;
    opacity: number;
    fontScale: number;
    theme: OverlayTheme;
  };
  workspaceView: "overview" | "settings";
};

let mainWindow: BrowserWindow | null = null;
let overlayWindow: BrowserWindow | null = null;
let overlayPayload: OverlayPayload | null = null;
let overlayAlwaysOnTop = true;
let overlayOpacity = 0.94;
let overlayClickThrough = false;
let overlayFontScale = 1;
let overlayTheme: OverlayTheme = "dark";
let overlayConstraintTimer: NodeJS.Timeout | null = null;
let overlayLastTopmostResetAt = 0;
let clientSettings: ClientSettings = {
  overlay: {
    alwaysOnTop: overlayAlwaysOnTop,
    clickThrough: overlayClickThrough,
    opacity: overlayOpacity,
    fontScale: overlayFontScale,
    theme: overlayTheme,
  },
  workspaceView: "overview",
};

function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1180,
    height: 760,
    minWidth: 960,
    minHeight: 640,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: join(__dirname, "preload.js"),
      additionalArguments: [isDevelopment ? "--echocue-development" : "--echocue-production"],
    },
  });

  mainWindow = window;
  window.once("ready-to-show", () => {
    window.show();
  });
  window.on("closed", () => {
    mainWindow = null;
    closeOverlayWindow();
  });

  if (isDevelopment) {
    void window.loadURL(rendererUrl);
  } else {
    void window.loadFile(join(__dirname, "../dist/index.html"));
  }

  return window;
}

function createOverlayWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 440,
    height: 260,
    minWidth: 320,
    minHeight: 180,
    frame: false,
    transparent: true,
    resizable: true,
    focusable: false,
    show: false,
    skipTaskbar: true,
    alwaysOnTop: overlayAlwaysOnTop,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: join(__dirname, "preload.js"),
      additionalArguments: [isDevelopment ? "--echocue-development" : "--echocue-production"],
    },
  });

  overlayWindow = window;
  applyOverlayWindowSettings(window);
  window.on("closed", () => {
    stopOverlayConstraintTimer();
    overlayWindow = null;
  });
  window.on("show", () => {
    applyOverlayWindowSettings(window);
    startOverlayConstraintTimer();
  });
  window.on("hide", () => {
    stopOverlayConstraintTimer();
  });
  window.webContents.on("did-finish-load", () => {
    sendOverlayState();
    if (!window.isDestroyed()) {
      showOverlayWindow(window);
    }
  });

  if (isDevelopment) {
    void window.loadURL(`${rendererUrl}/overlay.html`);
  } else {
    void window.loadFile(join(__dirname, "../dist/overlay.html"));
  }

  return window;
}

function getClientSettingsPath(): string {
  return join(app.getPath("userData"), clientSettingsFileName);
}

function sanitizeClientSettings(value: unknown): ClientSettings {
  if (!value || typeof value !== "object") {
    return structuredClone(clientSettings);
  }

  const candidate = value as Partial<ClientSettings> & {
    overlay?: Partial<ClientSettings["overlay"]>;
  };
  const overlay = (candidate.overlay ?? {}) as Record<string, unknown>;

  return {
    overlay: {
      alwaysOnTop:
        typeof overlay.alwaysOnTop === "boolean" ? overlay.alwaysOnTop : clientSettings.overlay.alwaysOnTop,
      clickThrough:
        typeof overlay.clickThrough === "boolean" ? overlay.clickThrough : clientSettings.overlay.clickThrough,
      opacity:
        typeof overlay.opacity === "number"
          ? Math.min(1, Math.max(0.35, overlay.opacity))
          : clientSettings.overlay.opacity,
      fontScale:
        typeof overlay.fontScale === "number"
          ? Math.min(1.35, Math.max(0.85, overlay.fontScale))
          : clientSettings.overlay.fontScale,
      theme: overlay.theme === "light" || overlay.theme === "dark" ? overlay.theme : clientSettings.overlay.theme,
    },
    workspaceView:
      candidate.workspaceView === "settings" || candidate.workspaceView === "overview"
        ? candidate.workspaceView
        : clientSettings.workspaceView,
  };
}

function applyClientSettings(settings: ClientSettings): void {
  clientSettings = settings;
  overlayAlwaysOnTop = settings.overlay.alwaysOnTop;
  overlayClickThrough = settings.overlay.clickThrough;
  overlayOpacity = settings.overlay.opacity;
  overlayFontScale = settings.overlay.fontScale;
  overlayTheme = settings.overlay.theme;
}

async function loadClientSettings(): Promise<void> {
  try {
    const raw = await readFile(getClientSettingsPath(), "utf8");
    applyClientSettings(sanitizeClientSettings(JSON.parse(raw) as unknown));
  } catch {
    applyClientSettings(structuredClone(clientSettings));
  }
}

async function saveClientSettings(): Promise<void> {
  const settingsPath = getClientSettingsPath();
  await mkdir(dirname(settingsPath), { recursive: true });
  await writeFile(settingsPath, `${JSON.stringify(clientSettings, null, 2)}\n`, "utf8");
}

function getOverlayWindow(): BrowserWindow {
  return overlayWindow ?? createOverlayWindow();
}

function sendClientSettings(): ClientSettings {
  return structuredClone(clientSettings);
}

function sendOverlayState(): void {
  if (overlayWindow && !overlayWindow.isDestroyed() && overlayPayload) {
    overlayWindow.webContents.send("overlay:update-content", {
      payload: overlayPayload,
      fontScale: overlayFontScale,
      theme: overlayTheme,
      opacity: overlayOpacity,
    });
  }
}

function applyOverlayClickThrough(window: BrowserWindow): void {
  window.setIgnoreMouseEvents(overlayClickThrough);
}

function applyOverlayTopmost(window: BrowserWindow, forceReset = false): void {
  if (!overlayAlwaysOnTop) {
    window.setAlwaysOnTop(false);
    return;
  }

  const now = Date.now();
  const shouldReset = forceReset || now - overlayLastTopmostResetAt > overlayTopmostResetIntervalMs;

  window.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  if (shouldReset) {
    window.setAlwaysOnTop(false);
    overlayLastTopmostResetAt = now;
  }

  window.setAlwaysOnTop(true, overlayAlwaysOnTopLevel);
  if (window.isVisible()) {
    window.moveTop();
  }
}

function applyOverlayWindowSettings(window: BrowserWindow): void {
  window.setOpacity(overlayOpacity);
  window.setFocusable(false);
  window.setSkipTaskbar(true);
  applyOverlayClickThrough(window);
  window.setFullScreenable(false);
  applyOverlayTopmost(window);
}

function showOverlayWindow(window: BrowserWindow): void {
  window.showInactive();
  applyOverlayWindowSettings(window);
  applyOverlayTopmost(window, true);
  startOverlayConstraintTimer();
}

function startOverlayConstraintTimer(): void {
  if (overlayConstraintTimer) {
    return;
  }

  overlayConstraintTimer = setInterval(() => {
    if (overlayWindow && !overlayWindow.isDestroyed() && overlayWindow.isVisible()) {
      applyOverlayWindowSettings(overlayWindow);
    }
  }, overlayConstraintIntervalMs);
}

function stopOverlayConstraintTimer(): void {
  if (overlayConstraintTimer) {
    clearInterval(overlayConstraintTimer);
    overlayConstraintTimer = null;
  }
}

function closeOverlayWindow(): void {
  if (overlayWindow && !overlayWindow.isDestroyed()) {
    overlayWindow.close();
  }
  stopOverlayConstraintTimer();
  overlayLastTopmostResetAt = 0;
  overlayWindow = null;
}

function requirePayload(value: unknown): OverlayPayload {
  if (!value || typeof value !== "object") {
    throw new TypeError("Invalid overlay payload.");
  }

  const payload = value as Record<string, unknown>;
  const fields = ["commentDisplay", "quickReply", "cue", "createdAt"];
  if (fields.some((field) => typeof payload[field] !== "string")) {
    throw new TypeError("Invalid overlay payload.");
  }

  return {
    commentDisplay: payload.commentDisplay as string,
    quickReply: payload.quickReply as string,
    cue: payload.cue as string,
    createdAt: payload.createdAt as string,
  };
}

function isMainWindowSender(event: IpcMainInvokeEvent): boolean {
  return BrowserWindow.fromWebContents(event.sender) === mainWindow;
}

function registerOverlayHandlers(): void {
  ipcMain.handle("overlay:open", (event, value: unknown) => {
    if (!isMainWindowSender(event)) {
      return;
    }
    overlayPayload = requirePayload(value);
    const window = getOverlayWindow();
    showOverlayWindow(window);
    sendOverlayState();
  });
  ipcMain.handle("overlay:update", (event, value: unknown) => {
    if (!isMainWindowSender(event)) {
      return;
    }
    overlayPayload = requirePayload(value);
    if (overlayWindow) {
      sendOverlayState();
    }
  });
  ipcMain.handle("overlay:hide", (event) => {
    if (isMainWindowSender(event)) {
      overlayWindow?.hide();
      stopOverlayConstraintTimer();
    }
  });
  ipcMain.handle("overlay:show", (event) => {
    if (isMainWindowSender(event)) {
      if (overlayWindow) {
        showOverlayWindow(overlayWindow);
      }
    }
  });
  ipcMain.handle("overlay:close", (event) => {
    if (isMainWindowSender(event)) {
      closeOverlayWindow();
    }
  });
  ipcMain.handle("overlay:set-always-on-top", (event, enabled: unknown) => {
    if (!isMainWindowSender(event) || typeof enabled !== "boolean") {
      return;
    }
    overlayAlwaysOnTop = enabled;
    if (overlayWindow) {
      applyOverlayWindowSettings(overlayWindow);
      applyOverlayTopmost(overlayWindow, true);
    }
  });
  ipcMain.handle("overlay:set-opacity", (event, opacity: unknown) => {
    if (!isMainWindowSender(event) || typeof opacity !== "number") {
      return;
    }
    overlayOpacity = Math.min(1, Math.max(0.35, opacity));
    if (overlayWindow) {
      applyOverlayWindowSettings(overlayWindow);
      sendOverlayState();
    }
  });
  ipcMain.handle("overlay:set-ignore-mouse-events", (event, enabled: unknown) => {
    if (!isMainWindowSender(event) || typeof enabled !== "boolean") {
      return;
    }
    overlayClickThrough = enabled;
    if (overlayWindow) {
      applyOverlayWindowSettings(overlayWindow);
    }
  });
  ipcMain.handle("overlay:set-font-scale", (event, fontScale: unknown) => {
    if (!isMainWindowSender(event) || typeof fontScale !== "number") {
      return;
    }
    overlayFontScale = Math.min(1.35, Math.max(0.85, fontScale));
    sendOverlayState();
  });
  ipcMain.handle("overlay:set-theme", (event, theme: unknown) => {
    if (!isMainWindowSender(event) || (theme !== "light" && theme !== "dark")) {
      return;
    }
    overlayTheme = theme;
    sendOverlayState();
  });
  ipcMain.handle("client-settings:get", (event) => {
    if (!isMainWindowSender(event)) {
      return sendClientSettings();
    }
    return sendClientSettings();
  });
  ipcMain.handle("client-settings:set", async (event, value: unknown) => {
    if (!isMainWindowSender(event)) {
      return;
    }
    applyClientSettings(sanitizeClientSettings(value));
    try {
      await saveClientSettings();
    } catch (error: unknown) {
      console.error("Failed to persist client settings:", error);
    }
    if (overlayWindow && !overlayWindow.isDestroyed()) {
      applyOverlayWindowSettings(overlayWindow);
      sendOverlayState();
    }
  });
}

registerOverlayHandlers();

app.whenReady().then(async () => {
  await loadClientSettings();
  createMainWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
