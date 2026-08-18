"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const node_path_1 = require("node:path");
const isDevelopment = !electron_1.app.isPackaged;
const rendererUrl = process.env.ECHOCUE_RENDERER_URL ?? "http://127.0.0.1:5173";
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
    window.once("ready-to-show", () => {
        window.show();
    });
    if (isDevelopment) {
        void window.loadURL(rendererUrl);
    }
    else {
        void window.loadFile((0, node_path_1.join)(__dirname, "../dist/index.html"));
    }
    return window;
}
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