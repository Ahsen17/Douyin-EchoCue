"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const node_path_1 = require("node:path");
const isDevelopment = !electron_1.app.isPackaged;
const rendererUrl = process.env.ECHOCUE_RENDERER_URL ?? "http://127.0.0.1:5173";
const overlayAlwaysOnTopLevel = "screen-saver";
const overlayConstraintIntervalMs = 300;
const overlayTopmostResetIntervalMs = 1800;
let mainWindow = null;
let overlayWindow = null;
let overlayPayload = null;
let overlayAlwaysOnTop = true;
let overlayOpacity = 0.94;
let overlayClickThrough = false;
let overlayFontScale = 1;
let overlayTheme = "dark";
let overlayConstraintTimer = null;
let overlayLastTopmostResetAt = 0;
function createMainWindow() {
    const window = new electron_1.BrowserWindow({
        width: 1180,
        height: 760,
        minWidth: 960,
        minHeight: 640,
        show: false,
        webPreferences: {
            contextIsolation: true,
            nodeIntegration: false,
            preload: (0, node_path_1.join)(__dirname, "preload.js"),
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
    }
    else {
        void window.loadFile((0, node_path_1.join)(__dirname, "../dist/index.html"));
    }
    return window;
}
function createOverlayWindow() {
    const window = new electron_1.BrowserWindow({
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
            preload: (0, node_path_1.join)(__dirname, "preload.js"),
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
    }
    else {
        void window.loadFile((0, node_path_1.join)(__dirname, "../dist/overlay.html"));
    }
    return window;
}
function getOverlayWindow() {
    return overlayWindow ?? createOverlayWindow();
}
function sendOverlayState() {
    if (overlayWindow && !overlayWindow.isDestroyed() && overlayPayload) {
        overlayWindow.webContents.send("overlay:update-content", {
            payload: overlayPayload,
            fontScale: overlayFontScale,
            theme: overlayTheme,
            opacity: overlayOpacity,
        });
    }
}
function applyOverlayClickThrough(window) {
    window.setIgnoreMouseEvents(overlayClickThrough);
}
function applyOverlayTopmost(window, forceReset = false) {
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
function applyOverlayWindowSettings(window) {
    window.setOpacity(overlayOpacity);
    window.setFocusable(false);
    window.setSkipTaskbar(true);
    applyOverlayClickThrough(window);
    window.setFullScreenable(false);
    applyOverlayTopmost(window);
}
function showOverlayWindow(window) {
    window.showInactive();
    applyOverlayWindowSettings(window);
    applyOverlayTopmost(window, true);
    startOverlayConstraintTimer();
}
function startOverlayConstraintTimer() {
    if (overlayConstraintTimer) {
        return;
    }
    overlayConstraintTimer = setInterval(() => {
        if (overlayWindow && !overlayWindow.isDestroyed() && overlayWindow.isVisible()) {
            applyOverlayWindowSettings(overlayWindow);
        }
    }, overlayConstraintIntervalMs);
}
function stopOverlayConstraintTimer() {
    if (overlayConstraintTimer) {
        clearInterval(overlayConstraintTimer);
        overlayConstraintTimer = null;
    }
}
function closeOverlayWindow() {
    if (overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.close();
    }
    stopOverlayConstraintTimer();
    overlayLastTopmostResetAt = 0;
    overlayWindow = null;
}
function requirePayload(value) {
    if (!value || typeof value !== "object") {
        throw new TypeError("Invalid overlay payload.");
    }
    const payload = value;
    const fields = ["commentDisplay", "quickReply", "cue", "createdAt"];
    if (fields.some((field) => typeof payload[field] !== "string")) {
        throw new TypeError("Invalid overlay payload.");
    }
    return {
        commentDisplay: payload.commentDisplay,
        quickReply: payload.quickReply,
        cue: payload.cue,
        createdAt: payload.createdAt,
    };
}
function isMainWindowSender(event) {
    return electron_1.BrowserWindow.fromWebContents(event.sender) === mainWindow;
}
function registerOverlayHandlers() {
    electron_1.ipcMain.handle("overlay:open", (event, value) => {
        if (!isMainWindowSender(event)) {
            return;
        }
        overlayPayload = requirePayload(value);
        const window = getOverlayWindow();
        showOverlayWindow(window);
        sendOverlayState();
    });
    electron_1.ipcMain.handle("overlay:update", (event, value) => {
        if (!isMainWindowSender(event)) {
            return;
        }
        overlayPayload = requirePayload(value);
        if (overlayWindow) {
            sendOverlayState();
        }
    });
    electron_1.ipcMain.handle("overlay:hide", (event) => {
        if (isMainWindowSender(event)) {
            overlayWindow?.hide();
            stopOverlayConstraintTimer();
        }
    });
    electron_1.ipcMain.handle("overlay:show", (event) => {
        if (isMainWindowSender(event)) {
            if (overlayWindow) {
                showOverlayWindow(overlayWindow);
            }
        }
    });
    electron_1.ipcMain.handle("overlay:close", (event) => {
        if (isMainWindowSender(event)) {
            closeOverlayWindow();
        }
    });
    electron_1.ipcMain.handle("overlay:set-always-on-top", (event, enabled) => {
        if (!isMainWindowSender(event) || typeof enabled !== "boolean") {
            return;
        }
        overlayAlwaysOnTop = enabled;
        if (overlayWindow) {
            applyOverlayWindowSettings(overlayWindow);
            applyOverlayTopmost(overlayWindow, true);
        }
    });
    electron_1.ipcMain.handle("overlay:set-opacity", (event, opacity) => {
        if (!isMainWindowSender(event) || typeof opacity !== "number") {
            return;
        }
        overlayOpacity = Math.min(1, Math.max(0.35, opacity));
        if (overlayWindow) {
            applyOverlayWindowSettings(overlayWindow);
            sendOverlayState();
        }
    });
    electron_1.ipcMain.handle("overlay:set-ignore-mouse-events", (event, enabled) => {
        if (!isMainWindowSender(event) || typeof enabled !== "boolean") {
            return;
        }
        overlayClickThrough = enabled;
        if (overlayWindow) {
            applyOverlayWindowSettings(overlayWindow);
        }
    });
    electron_1.ipcMain.handle("overlay:set-font-scale", (event, fontScale) => {
        if (!isMainWindowSender(event) || typeof fontScale !== "number") {
            return;
        }
        overlayFontScale = Math.min(1.35, Math.max(0.85, fontScale));
        sendOverlayState();
    });
    electron_1.ipcMain.handle("overlay:set-theme", (event, theme) => {
        if (!isMainWindowSender(event) || (theme !== "light" && theme !== "dark")) {
            return;
        }
        overlayTheme = theme;
        sendOverlayState();
    });
}
registerOverlayHandlers();
electron_1.app.whenReady().then(() => {
    createMainWindow();
    electron_1.app.on("activate", () => {
        if (electron_1.BrowserWindow.getAllWindows().length === 0) {
            createMainWindow();
        }
    });
});
electron_1.app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
        electron_1.app.quit();
    }
});
//# sourceMappingURL=main.js.map