export type ClientScreen = "welcome" | "workspace";

export type RuntimeStatus = "idle" | "starting" | "running" | "paused" | "error";

export type RoomStatus = "live" | "offline";

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
  commentDisplay: string;
  quickReply: string;
  cue: string;
  createdAt: string;
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
};

