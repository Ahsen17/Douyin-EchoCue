"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const clientApi = {
    platform: process.platform,
    isDevelopment: process.argv.includes("--echocue-development"),
};
electron_1.contextBridge.exposeInMainWorld("echocue", clientApi);
//# sourceMappingURL=preload.js.map