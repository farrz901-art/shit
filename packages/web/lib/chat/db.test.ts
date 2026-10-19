/** Dexie IndexedDB schema 测试 (2026-06-19 chat spec, vitest + fake-indexeddb) */

import "fake-indexeddb/auto"; // 自动 stub indexedDB
import { beforeEach, describe, expect, it } from "vitest";
import {
  clearLocalChat,
  db,
  deleteConversation,
  loadConversations,
  loadMessages,
  saveConversations,
  saveMessages,
} from "./db";

const SINGLE_ITEM_COUNT = 1;
const ZERO_COUNT = 0;
const FIRST_ITEM_INDEX = 0;

const SAMPLE_CONV = {
  createdAt: 1_700_000_000_000,
  id: "c1",
  messageCount: 0,
  owner: "anon" as const,
  title: "测试",
  updatedAt: 1_700_000_000_000,
};

const SAMPLE_MSG = {
  content: "hello",
  conversationId: "c1",
  createdAt: 1_700_000_000_000,
  id: "m1",
  owner: "anon" as const,
  role: "user" as const,
};

beforeEach(async () => {
  await db.conversations.clear();
  await db.messages.clear();
});

describe("loadConversations", () => {
  it("空 IDB 返空数组", async () => {
    expect(await loadConversations()).toEqual([]);
  });

  it("读 anon conv, 排除 imported", async () => {
    await db.conversations.bulkPut([
      { ...SAMPLE_CONV, id: "c1", owner: "anon" },
      { ...SAMPLE_CONV, id: "c2", owner: "imported" },
    ]);
    const result = await loadConversations();
    expect(result.map((conv) => conv.id)).toEqual(["c1"]);
  });
});

describe("saveMessages + loadMessages", () => {
  it("存 + 取回一致", async () => {
    await saveMessages("c1", [SAMPLE_MSG]);
    const msgs = await loadMessages("c1");
    expect(msgs).toHaveLength(SINGLE_ITEM_COUNT);
    expect(msgs[FIRST_ITEM_INDEX].content).toBe("hello");
  });

  it("不同 conv 的消息互不干扰", async () => {
    await saveMessages("c1", [SAMPLE_MSG]);
    await saveMessages("c2", [{ ...SAMPLE_MSG, conversationId: "c2", id: "m2" }]);
    expect(await loadMessages("c1")).toHaveLength(SINGLE_ITEM_COUNT);
    expect(await loadMessages("c2")).toHaveLength(SINGLE_ITEM_COUNT);
  });
});

describe("deleteConversation", () => {
  it("删 conv 同时删关联 messages", async () => {
    await saveConversations([SAMPLE_CONV]);
    await saveMessages("c1", [SAMPLE_MSG]);
    await deleteConversation("c1");
    expect(await loadConversations()).toHaveLength(ZERO_COUNT);
    expect(await loadMessages("c1")).toHaveLength(ZERO_COUNT);
  });
});

describe("clearLocalChat", () => {
  it("只清 anon, 保留 imported (未来 C/D 模式扩展)", async () => {
    await db.conversations.bulkPut([
      { ...SAMPLE_CONV, id: "c1", owner: "anon" },
      { ...SAMPLE_CONV, id: "c2", owner: "imported" },
    ]);
    await saveMessages("c1", [SAMPLE_MSG]);
    await saveMessages("c2", [{ ...SAMPLE_MSG, conversationId: "c2", id: "m2" }]);

    await clearLocalChat();

    const convs = await db.conversations.toArray();
    expect(convs.map((conv) => conv.id)).toEqual(["c2"]); // 只保留 imported
    const msgs = await db.messages.toArray();
    expect(msgs.map((msg) => msg.conversationId)).toEqual(["c2"]);
  });
});
