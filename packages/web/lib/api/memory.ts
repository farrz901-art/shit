// 长期记忆 API 客户端 (2026-06-16)
// 走 apiFetch 直连后端 (/api/memory/* 不在 BFF_PATTERNS 名单里, 浏览器拼 host)
// 服务端 (RSC / server action) 也用同一个 apiFetch, cookie 透传
import { FIVE } from "@/const";
import { apiFetch } from "./config";

/**
 * 记忆命中结果
 */
export interface MemoryHit {
  id: string;
  text: string;
  score?: number;
  metadata?: Record<string, unknown>;
}

/**
 * 对话轮次消息
 */
export interface TurnMessage {
  role: "user" | "assistant";
  content: string;
}

/**
 * 搜索记忆输入
 */
export interface SearchInput {
  query: string;
  limit?: number;
}

/**
 * 添加记忆输入
 */
export interface AddInput {
  messages: TurnMessage[];
  conversationId?: string;
}

/**
 * 添加长期记忆
 * @param req  添加请求 (messages, conversationId)
 *
 * @shared
 */
export const add = async (req: AddInput): Promise<void> => {
  // 后端 Pydantic 字段是 snake_case conversation_id, 前端 camelCase 转
  const body: Record<string, unknown> = {
    messages: req.messages,
  };
  if (req.conversationId) {
    body.conversation_id = req.conversationId;
  }
  await apiFetch("/api/memory/add", { body, method: "POST" });
};

/**
 * 删除单条记忆
 * @param memoryId  记忆 ID
 *
 * @shared
 */
// Delete 是 JS 关键字，用 deleteMemory 导出避免冲突
export const deleteMemory = (memoryId: string): Promise<void> =>
  apiFetch(`/api/memory/${memoryId}`, { method: "DELETE" });

/**
 * 删除所有记忆
 * @returns  删除数量
 *
 * @shared
 */
export const deleteAll = (): Promise<{ deleted_count: number }> =>
  apiFetch("/api/memory/all", { method: "DELETE" });

/**
 * 列出所有记忆
 * @returns  记忆列表
 *
 * @shared
 */
export const list = (): Promise<{ memories: MemoryHit[] }> =>
  apiFetch("/api/memory/list", { method: "GET" });

/**
 * 搜索匹配的记忆
 * @param req  搜索请求 (query, limit)
 * @returns    匹配的记忆列表
 *
 * @shared
 */
export const search = (req: SearchInput): Promise<{ memories: MemoryHit[] }> =>
  apiFetch("/api/memory/search", {
    body: { limit: req.limit ?? FIVE, query: req.query },
    method: "POST",
  });

/**
 * 更新记忆内容
 * @param memoryId  记忆 ID
 * @param text      新记忆文本
 *
 * @shared
 */
export const update = (memoryId: string, text: string): Promise<void> =>
  apiFetch(`/api/memory/${memoryId}`, {
    body: { text },
    method: "PATCH",
  });
