export type ClientScreen = "welcome" | "workspace";

export type RuntimeStatus = "idle" | "starting" | "running" | "paused" | "error";

export type RoomStatus = "live" | "offline";

export type OverlayTheme = "light" | "dark";
export type OverlaySizeLevel = "small" | "medium" | "large";
export type WorkspaceView = "overview" | "settings";

export interface Account {
  displayName: string;
  accountType: "主播" | "运营";
}

export interface Room {
  id: string;
  name: string;
  anchorName: string;
  status: RoomStatus;
  viewerCount: number;
  lastActiveLabel: string;
}

export interface PushPreview {
  userName: string;
  commentDisplay: string;
  quickReply: string;
  cue: string;
  createdAt: string;
}

export interface OverlayConfig {
  isVisible: boolean;
  alwaysOnTop: boolean;
  clickThrough: boolean;
  opacity: number;
  fontScale: number;
  theme: OverlayTheme;
  sizeLevel: OverlaySizeLevel;
}

export interface OverlayPreferences {
  alwaysOnTop: boolean;
  clickThrough: boolean;
  opacity: number;
  fontScale: number;
  theme: OverlayTheme;
  sizeLevel: OverlaySizeLevel;
}

export interface ClientSettings {
  overlay: OverlayPreferences;
  workspaceView: WorkspaceView;
}

export interface ClientState {
  screen: ClientScreen;
  isLoading: boolean;
  errorMessage: string | null;
  account: Account | null;
  rooms: Room[];
  selectedRoomId: string | null;
  runtimeStatus: RuntimeStatus;
  runtimeMessage: string;
  lastPush: PushPreview | null;
  overlay: OverlayConfig;
  workspaceView: WorkspaceView;
}

export const initialState: ClientState = {
  screen: "welcome",
  isLoading: false,
  errorMessage: null,
  account: null,
  rooms: [],
  selectedRoomId: null,
  runtimeStatus: "idle",
  runtimeMessage: "尚未启动",
  lastPush: null,
  overlay: {
    isVisible: false,
    alwaysOnTop: true,
    clickThrough: false,
    opacity: 0.94,
    fontScale: 1.15,
    theme: "dark",
    sizeLevel: "medium",
  },
  workspaceView: "overview",
};

export const initialClientSettings: ClientSettings = {
  overlay: {
    alwaysOnTop: true,
    clickThrough: false,
    opacity: 0.94,
    fontScale: 1.15,
    theme: "dark",
    sizeLevel: "medium",
  },
  workspaceView: "overview",
};
