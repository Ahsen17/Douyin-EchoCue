import { contextBridge } from "electron";

const clientApi = {
  platform: process.platform,
  isDevelopment: process.argv.includes("--echocue-development"),
};

contextBridge.exposeInMainWorld("echocue", clientApi);
