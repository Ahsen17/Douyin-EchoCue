import type { Account, PushPreview, Room, RuntimeStatus } from "./state";

export interface AuthAdapter {
  signIn: () => Promise<Account>;
  signOut: () => Promise<void>;
  getSession: () => Promise<Account | null>;
}

export interface RoomAdapter {
  loadRooms: () => Promise<Room[]>;
  selectRoom: (roomId: string) => Promise<Room | null>;
}

export interface RuntimeSnapshot {
  status: RuntimeStatus;
  message: string;
}

export interface RuntimeAdapter {
  start: (roomId: string) => Promise<RuntimeSnapshot>;
  stop: () => Promise<RuntimeSnapshot>;
  getStatus: () => Promise<RuntimeSnapshot>;
}

export interface PushMessageAdapter {
  getLatest: () => Promise<PushPreview | null>;
  getNextPreview: () => Promise<PushPreview | null>;
}

export interface ClientAdapters {
  auth: AuthAdapter;
  room: RoomAdapter;
  runtime: RuntimeAdapter;
  push: PushMessageAdapter;
}
