import type { Account, PushPreview, Room } from "./state";

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
    commentDisplay: "主播最近有没有推荐的入门设备？",
    quickReply: "可以先从预算和使用场景出发，我建议先看一套稳定的入门配置。",
    cue: "补充一个具体预算区间，邀请观众说说自己的设备。",
    createdAt: "刚刚",
  },
  {
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

export async function loadRooms(): Promise<Room[]> {
  await delay(650);
  return mockRooms;
}

export async function startRuntime(): Promise<void> {
  await delay(850);
}

export async function stopRuntime(): Promise<void> {
  await delay(350);
}

export function getMockPush(index: number): PushPreview {
  return mockPushes[index % mockPushes.length];
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

