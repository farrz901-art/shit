// 会话元数据 CRUD 测试 (2026-06-19 改 Dexie IndexedDB 替原 localStorage)
import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it } from "vitest";
import {
  deleteConversation,
  loadConversations,
  saveConversations,
  upsertConversation,
} from "./storage";
import type { Conversation } from "./types";
import { db } from "./db";

const SAMPLE: Conversation = {
  createdAt: 1_700_000_000_000,
  id: "c1",
  messageCount: 0,
  title: "测试会话",
  updatedAt: 1_700_000_000_000,
};

const SINGLE = 1;
const PAIR = 2;
const FIRST = 0;

beforeEach(async () => {
  await db.conversations.clear();
  await db.messages.clear();
});

describe("loadConversations", () => {
  it("空 IDB 返空数组", async () => {
    expect(await loadConversations()).toEqual([]);
  });

  it("写后读回一致", async () => {
    await saveConversations([SAMPLE]);
    expect(await loadConversations()).toEqual([SAMPLE]);
  });
});

describe("saveConversations", () => {
  it("批量写后能读回", async () => {
    await saveConversations([SAMPLE]);
    expect(await loadConversations()).toEqual([SAMPLE]);
  });

  it("二次写覆盖前次", async () => {
    await saveConversations([SAMPLE]);
    await saveConversations([{ ...SAMPLE, title: "替换", updatedAt: 1_700_000_001_000 }]);
    const all = await loadConversations();
    expect(all).toHaveLength(SINGLE);
    expect(all[FIRST].title).toBe("替换");
  });
});

describe("upsertConversation", () => {
  it("空列表时插入新 conv", async () => {
    await upsertConversation(SAMPLE);
    expect(await loadConversations()).toEqual([SAMPLE]);
  });

  it("同 id 已存在 → 替换 (不重复)", async () => {
    await upsertConversation(SAMPLE);
    await upsertConversation({ ...SAMPLE, title: "更新后", updatedAt: 1_700_000_001_000 });
    const all = await loadConversations();
    expect(all).toHaveLength(SINGLE);
    expect(all[FIRST].title).toBe("更新后");
  });

  it("不同 id 都插入", async () => {
    await upsertConversation(SAMPLE);
    await upsertConversation({ ...SAMPLE, id: "c2", title: "第二个" });
    expect(await loadConversations()).toHaveLength(PAIR);
  });
});

describe("deleteConversation", () => {
  it("删存在的 id", async () => {
    await upsertConversation(SAMPLE);
    await upsertConversation({ ...SAMPLE, id: "c2", title: "B" });
    await deleteConversation("c1");
    const all = await loadConversations();
    expect(all.map((conv) => conv.id)).toEqual(["c2"]);
  });

  it("删不存在的 id 是 no-op", async () => {
    await upsertConversation(SAMPLE);
    await deleteConversation("ghost");
    expect(await loadConversations()).toHaveLength(SINGLE);
  });
});
