import { ONE, TWO, ZERO } from "@/const";
// Storage facade 额外单测 (loadAllMessages + upsertConversation + saveMessages 截断)
import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it } from "vitest";
import { db } from "./db";
import {
  loadAllMessages,
  loadConversations,
  saveConversations,
  saveMessages,
  upsertConversation,
} from "./storage";

describe("storage facade 额外", () => {
  beforeEach(async () => {
    await db.conversations.clear();
    await db.messages.clear();
  });

  it("upsertConversation 新增", async () => {
    await upsertConversation({
      id: "c1",
      title: "新",
      createdAt: 1,
      updatedAt: 2,
      messageCount: 0,
    });
    const convs = await loadConversations();
    expect(convs).toHaveLength(ONE);
    expect(convs[ZERO].title).toBe("新");
  });

  it("upsertConversation 更新", async () => {
    await saveConversations([
      { id: "c1", title: "旧", createdAt: 1, updatedAt: 2, messageCount: 0 },
    ]);
    await upsertConversation({
      id: "c1",
      title: "新",
      createdAt: 1,
      updatedAt: 3,
      messageCount: 0,
    });
    const convs = await loadConversations();
    expect(convs[ZERO].title).toBe("新");
  });

  it("loadAllMessages 分组", async () => {
    await saveMessages("c1", [
      { id: "m1", role: "user", content: "a", createdAt: 1, conversationId: "c1" },
    ]);
    await saveMessages("c2", [
      { id: "m2", role: "user", content: "b", createdAt: 2, conversationId: "c2" },
    ]);
    const all = await loadAllMessages();
    expect(Object.keys(all)).toHaveLength(TWO);
  });
});
