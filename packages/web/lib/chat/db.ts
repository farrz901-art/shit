// Dexie IndexedDB schema 替原 localStorage (2026-06-19 chat spec §4)

import type { Conversation, Message } from "./types";

import Dexie, { type Table } from "dexie";

/**
 * 本地会话 (扩展 Conversation, 加 owner / deletedAt)
 * @shared
 */
export interface LocalConversation extends Conversation {
  // 跟 Conversation 相同, 但加 owner 标记 (防止 anon/login 切换串)
  owner: "anon" | "imported";
  // 软删 (本地, 跟服务端对齐)
  deletedAt?: number;
}

/**
 * 本地消息 (扩展 Message, 加 owner)
 * @shared
 */
export interface LocalMessage extends Message {
  // 跟 Message 相同
  owner: "anon" | "imported";
}

const DB_VERSION = 1; // 数据库版本号

class ChatDB extends Dexie {
  conversations!: Table<LocalConversation, string>;
  messages!: Table<LocalMessage, string>;

  constructor() {
    super("rag-chat");
    this.version(DB_VERSION).stores({
      // Primary key + 索引
      // 字段名 conversationId 跟现有 types.Message.conversationId 对齐
      conversations: "id, owner, updatedAt, deletedAt",
      messages: "id, conversationId, createdAt, owner, [conversationId+createdAt]",
    });
  }
}

/**
 * Dexie IndexedDB 数据库实例 (rag-chat)
 * 供 chat store / service 读写会话和消息
 */
export const db = new ChatDB();

const MIN_TIMESTAMP = 0; // 时间戳最小值

// ── 跟旧 storage.ts 兼容的 facade ──

/**
 * 读取 anon 用户的会话列表 (排除 imported 和软删)
 * 跟服务端 conversations 列表对齐: 按 updatedAt 倒序由调用方排序
 */
export const loadConversations = async (): Promise<LocalConversation[]> =>
  db.conversations
    .where("owner")
    .equals("anon")
    .and((conv) => !conv.deletedAt)
    .toArray();

/**
 * 批量保存会话, 强制 owner="anon" (防止 imported 串到 anon)
 */
export const saveConversations = async (items: LocalConversation[]): Promise<void> => {
  await db.conversations.bulkPut(items.map((conv) => ({ ...conv, owner: "anon" as const })));
};

/**
 * 删会话 + 关联 messages (事务保证级联)
 */
export const deleteConversation = async (id: string): Promise<void> => {
  await db.transaction("rw", db.conversations, db.messages, async () => {
    await db.conversations.delete(id);
    await db.messages.where("conversationId").equals(id).delete();
  });
};

/**
 * 读单 conv 消息, 按 createdAt 升序
 * 走复合索引 [conversationId+createdAt]
 */
export const loadMessages = async (convId: string): Promise<LocalMessage[]> =>
  db.messages
    .where("[conversationId+createdAt]")
    .between([convId, MIN_TIMESTAMP], [convId, Number.MAX_SAFE_INTEGER])
    .toArray();

/**
 * 保存消息, 强制 owner="anon" + conversationId=convId
 */
export const saveMessages = async (convId: string, messages: LocalMessage[]): Promise<void> => {
  await db.messages.bulkPut(
    messages.map((msg) => ({ ...msg, conversationId: convId, owner: "anon" as const })),
  );
};

/**
 * 登录后清 anon 数据 (保留 imported, 留好未来 C/D 模式扩展)
 * 消息的归属由 conv 决定: 先查删哪些 conv, 再删对应 messages (cascade 语义)
 */
export const clearLocalChat = async (): Promise<void> => {
  await db.transaction("rw", db.conversations, db.messages, async () => {
    // 1) 找到所有 anon 会话 id
    const anonConvIds = await db.conversations.where("owner").equals("anon").primaryKeys();
    // 2) 删 anon 会话
    if (anonConvIds.length) {
      await db.conversations.bulkDelete(anonConvIds);
    }
    // 3) 删这些会话的所有消息 (cascade)
    if (anonConvIds.length) {
      const msgs = await db.messages
        .where("conversationId")
        .anyOf(anonConvIds as string[])
        .primaryKeys();
      if (msgs.length) {
        await db.messages.bulkDelete(msgs);
      }
    }
  });
};
