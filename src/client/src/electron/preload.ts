import { contextBridge, ipcRenderer } from "electron";

type OverlayPayload = {
  userName: string;
  commentDisplay: string;
  quickReply: string;
  cue: string;
  createdAt: string;
};

type OverlayTheme = "light" | "dark";
type OverlaySizeLevel = "small" | "medium" | "large";
type OverlayPreferences = {
  alwaysOnTop: boolean;
  clickThrough: boolean;
  opacity: number;
  fontScale: number;
  theme: OverlayTheme;
  sizeLevel: OverlaySizeLevel;
};
type ClientSettings = {
  overlay: OverlayPreferences;
  workspaceView: "overview" | "settings";
};
type OverlayUpdate = {
  payload: OverlayPayload;
  fontScale: number;
  theme: OverlayTheme;
  opacity: number;
};

const clientApi = {
  platform: process.platform,
  isDevelopment: process.argv.includes("--echocue-development"),
  window: {
    minimize: (): Promise<void> => ipcRenderer.invoke("window:minimize"),
    toggleMaximize: (): Promise<void> => ipcRenderer.invoke("window:toggle-maximize"),
    close: (): Promise<void> => ipcRenderer.invoke("window:close"),
  },
  overlay: {
    open: (payload: OverlayPayload): Promise<void> => ipcRenderer.invoke("overlay:open", payload),
    update: (payload: OverlayPayload): Promise<void> => ipcRenderer.invoke("overlay:update", payload),
    hide: (): Promise<void> => ipcRenderer.invoke("overlay:hide"),
    show: (): Promise<void> => ipcRenderer.invoke("overlay:show"),
    close: (): Promise<void> => ipcRenderer.invoke("overlay:close"),
    setAlwaysOnTop: (enabled: boolean): Promise<void> =>
      ipcRenderer.invoke("overlay:set-always-on-top", enabled),
    setOpacity: (opacity: number): Promise<void> => ipcRenderer.invoke("overlay:set-opacity", opacity),
    setIgnoreMouseEvents: (enabled: boolean): Promise<void> =>
      ipcRenderer.invoke("overlay:set-ignore-mouse-events", enabled),
    setFontScale: (fontScale: number): Promise<void> => ipcRenderer.invoke("overlay:set-font-scale", fontScale),
    setSizeLevel: (sizeLevel: OverlaySizeLevel): Promise<void> =>
      ipcRenderer.invoke("overlay:set-size-level", sizeLevel),
    setTheme: (theme: OverlayTheme): Promise<void> => ipcRenderer.invoke("overlay:set-theme", theme),
    onUpdate: (callback: (update: OverlayUpdate) => void): (() => void) => {
      const listener = (_event: Electron.IpcRendererEvent, update: OverlayUpdate): void => callback(update);
      ipcRenderer.on("overlay:update-content", listener);
      return () => ipcRenderer.removeListener("overlay:update-content", listener);
    },
  },
  clientSettings: {
    get: (): Promise<ClientSettings> => ipcRenderer.invoke("client-settings:get"),
    set: (settings: ClientSettings): Promise<void> => ipcRenderer.invoke("client-settings:set", settings),
  },
};

contextBridge.exposeInMainWorld("echocue", clientApi);
