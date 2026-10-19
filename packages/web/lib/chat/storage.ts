// LocalStorage → IndexedDB via Dexie (2026-06-19 chat spec §4)
// 保留旧 API 兼容 ChatShell (loadConversations / saveMessages / deleteConversation)

import type { Conversation, Message } from "./types";
import {
  type LocalConversation,
  type LocalMessage,
  deleteConversation as _idbDeleteConversation,
  loadConversations as _idbLoadConversations,
  loadMessages as _idbLoadMessages,
  saveConversations as _idbSaveConversations,
  saveMessages as _idbSaveMessages,
  db,
} from "./db";

const MAX_MESSAGES_PER_CONV = 100;
const IDX_NOT_FOUND = -1; // 未找到索引

// ── Conversations (跟旧 storage.ts 同名 export, ChatShell 调用) ──

/**
 * 读取 anon 用户的会话列表
 * 跟旧 localStorage 行为兼容, 但底层走 IndexedDB
 * 返 Conversation[] (不暴露 LocalConversation 的 owner 字段, 跟旧 API 兼容)
 */
export const loadConversations = async (): Promise<Conversation[]> => {
  const items = await _idbLoadConversations();
  // 抹掉 LocalConversation 的 owner 字段, 返纯 Conversation (兼容 ChatShell)
  return items.map(({ owner: _owner, deletedAt: _deletedAt, ...rest }) => rest);
};

/**
 * 批量保存会话, owner 强制 anon (facade 不让 caller 传 imported)
 */
export const saveConversations = async (items: Conversation[]): Promise<void> => {
  await _idbSaveConversations(items as LocalConversation[]);
};

/**
 * 插入或更新单条会话, 保留原 id 不变
 */
export const upsertConversation = async (conv: Conversation): Promise<void> => {
  const all = await _idbLoadConversations();
  const index = all.findIndex((convItem) => convItem.id === conv.id);
  if (index !== IDX_NOT_FOUND) {
    all[index] = { ...all[index], ...conv };
  } else {
    all.push({ ...conv, owner: "anon" });
  }
  await _idbSaveConversations(all);
};

/**
 * 删会话 (级联删 messages)
 */
export const deleteConversation = async (id: string): Promise<void> => {
  await _idbDeleteConversation(id);
};

// ── Messages ──

/**
 * 读单 conv 消息, 按 createdAt 升序
 * 返 Message[] (不暴露 LocalMessage 的 owner 字段, 跟旧 API 兼容)
 */
export const loadMessages = async (convId: string): Promise<Message[]> => {
  const items = await _idbLoadMessages(convId);
  return items.map(({ owner: _owner, ...rest }) => rest);
};

/**
 * 读全量消息, 按 convId 分组 (返 Record 兼容旧 API)
 * 抹掉 LocalMessage 的 owner 字段
 */
export const loadAllMessages = async (): Promise<Record<string, Message[]>> => {
  const all = await db.messages.toArray();
  const grouped: Record<string, Message[]> = {};
  for (const msg of all) {
    const { owner: _owner, ...msgData } = msg;
    const convId = msgData.conversationId;
    if (convId) {
      (grouped[convId] ??= []).push(msgData);
    }
  }
  return grouped;
};

/**
 * 保存消息, 只保留最近 MAX_MESSAGES_PER_CONV 条
 */
export const saveMessages = async (convId: string, messages: Message[]): Promise<void> => {
  // 只保留最近 N 条, 避免 IDB 膨胀
  const trimmed = messages.slice(-MAX_MESSAGES_PER_CONV);
  await _idbSaveMessages(convId, trimmed as LocalMessage[]);
};

// Re-export 新加的
export { clearLocalChat } from "./db";
