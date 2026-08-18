"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const clientApi = {
    platform: process.platform,
    isDevelopment: process.argv.includes("--echocue-development"),
    overlay: {
        open: (payload) => electron_1.ipcRenderer.invoke("overlay:open", payload),
        update: (payload) => electron_1.ipcRenderer.invoke("overlay:update", payload),
        hide: () => electron_1.ipcRenderer.invoke("overlay:hide"),
        show: () => electron_1.ipcRenderer.invoke("overlay:show"),
        close: () => electron_1.ipcRenderer.invoke("overlay:close"),
        setAlwaysOnTop: (enabled) => electron_1.ipcRenderer.invoke("overlay:set-always-on-top", enabled),
        setOpacity: (opacity) => electron_1.ipcRenderer.invoke("overlay:set-opacity", opacity),
        setIgnoreMouseEvents: (enabled) => electron_1.ipcRenderer.invoke("overlay:set-ignore-mouse-events", enabled),
        setFontScale: (fontScale) => electron_1.ipcRenderer.invoke("overlay:set-font-scale", fontScale),
        setTheme: (theme) => electron_1.ipcRenderer.invoke("overlay:set-theme", theme),
        onUpdate: (callback) => {
            const listener = (_event, update) => callback(update);
            electron_1.ipcRenderer.on("overlay:update-content", listener);
            return () => electron_1.ipcRenderer.removeListener("overlay:update-content", listener);
        },
    },
    clientSettings: {
        get: () => electron_1.ipcRenderer.invoke("client-settings:get"),
        set: (settings) => electron_1.ipcRenderer.invoke("client-settings:set", settings),
    },
};
electron_1.contextBridge.exposeInMainWorld("echocue", clientApi);
//# sourceMappingURL=preload.js.map