import type { ClientAdapters, RuntimeSnapshot } from "./adapter";
import type { Account, PushPreview, Room } from "./state";

export type MockScenario = "normal" | "emptyRooms" | "roomError" | "runtimeError" | "emptyPush";

let mockScenario: MockScenario = "normal";

const mockAccount: Account = {
  displayName: "EchoCue 主播账号",
  accountType: "主播",
};

const mockRooms: Room[] = [
  {
    id: "room-main",
    name: "晚间聊天与游戏直播",
    anchorName: "EchoCue 主播",
    status: "live",
    viewerCount: 12840,
    lastActiveLabel: "刚刚更新",
  },
  {
    id: "room-test",
    name: "工作日测试直播间",
    anchorName: "EchoCue 测试账号",
    status: "offline",
    viewerCount: 0,
    lastActiveLabel: "今天 14:20",
  },
];

const mockPushes: PushPreview[] = [
  {
    userName: "小林在看",
    commentDisplay: "主播最近有没有推荐的入门设备？",
    quickReply: "可以先从预算和使用场景出发，我建议先看一套稳定的入门配置。",
    cue: "补充一个具体预算区间，邀请观众说说自己的设备。",
    createdAt: "刚刚",
  },
  {
    userName: "夜色调音台",
    commentDisplay: "这首歌的情绪很适合今晚的直播间。",
    quickReply: "确实，今晚就沿着这个氛围聊下去。",
    cue: "可以顺势问观众今晚最喜欢哪一首。",
    createdAt: "1 分钟前",
  },
];

export async function signIn(): Promise<Account> {
  await delay(500);
  return mockAccount;
}

export async function signOut(): Promise<void> {
  await delay(180);
}

export async function getSession(): Promise<Account | null> {
  await delay(220);
  return null;
}

export async function loadRooms(): Promise<Room[]> {
  await delay(650);
  if (mockScenario === "roomError") {
    throw new Error("Mock room adapter failure.");
  }
  if (mockScenario === "emptyRooms") {
    return [];
  }
  return mockRooms;
}

export async function selectRoom(roomId: string): Promise<Room | null> {
  await delay(160);
  return mockRooms.find((room) => room.id === roomId) ?? null;
}

export async function startRuntime(roomId: string): Promise<RuntimeSnapshot> {
  await delay(850);
  if (mockScenario === "runtimeError") {
    throw new Error("Mock runtime adapter failure.");
  }
  const room = mockRooms.find((item) => item.id === roomId);
  return {
    status: "running",
    message: room ? `辅助服务运行中：${room.name}` : "辅助服务运行中",
  };
}

export async function stopRuntime(): Promise<RuntimeSnapshot> {
  await delay(350);
  return {
    status: "idle",
    message: "已停止，等待下一次启动。",
  };
}

export async function getRuntimeStatus(): Promise<RuntimeSnapshot> {
  await delay(160);
  return {
    status: "idle",
    message: "尚未启动",
  };
}

let pushIndex = 0;

export async function getLatestPush(): Promise<PushPreview | null> {
  await delay(120);
  if (mockScenario === "emptyPush") {
    return null;
  }
  return mockPushes[0] ?? null;
}

export async function getNextPreview(): Promise<PushPreview | null> {
  await delay(160);
  if (mockScenario === "emptyPush") {
    return null;
  }
  const push = mockPushes[pushIndex % mockPushes.length] ?? null;
  pushIndex += 1;
  return push;
}

export const mockAdapters: ClientAdapters = {
  auth: {
    signIn,
    signOut,
    getSession,
  },
  room: {
    loadRooms,
    selectRoom,
  },
  runtime: {
    start: startRuntime,
    stop: stopRuntime,
    getStatus: getRuntimeStatus,
  },
  push: {
    getLatest: getLatestPush,
    getNextPreview,
  },
};

export function setMockScenario(scenario: MockScenario): void {
  mockScenario = scenario;
  pushIndex = 0;
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}
