// 聊天 L0 纯函数 (2026-07-01 Phase 2 重构)
// 职责: 无 React 状态/副作用, 3 个 helper + 1 个 ID 生成器
//   - newId                     crypto.randomUUID / Date.now fallback
//   - computeEffectiveConversations  合并服务端+本地会话列表 (登录态)
//   - getNextConversationId     删除会话后的下一个 currentId
//
// setupAbortController 已删 (useChat 内置 stop); send-request.ts 整个删
// (DifyHttpChatTransport.prepareSendMessagesRequest 接管).
import type { Conversation } from "./types";
import { nowMs, toInstant } from "@/lib/date";
const RANDOM_ID_RADIX = 36;
const RANDOM_ID_START = 2;
const FIRST_INDEX = 0;

/**
 * 生成唯一 ID
 * @returns  UUID 或基于时间戳的随机 ID
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
export const newId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id-${nowMs()}-${Math.random().toString(RANDOM_ID_RADIX).slice(RANDOM_ID_START)}`;
};

/**
 * 计算有效会话列表: 登录态合并服务端+本地, 非登录态仅返回本地
 * @param conversations  本地会话列表
 * @param serverConvs    服务端会话列表
 * @param isAccount      是否为登录用户
 * @returns              合并后的会话列表
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
// 计算有效会话列表: isAccount=true 时合并服务端+本地, false 时仅返回本地
export const computeEffectiveConversations = (
  conversations: Conversation[],
  serverConvs: {
    created_at: string;
    id: string;
    message_count: number;
    title: string;
    updated_at: string;
  }[],
  isAccount: boolean,
): Conversation[] => {
  if (!isAccount) {
    return conversations;
  }
  const localIds = new Set(conversations.map((conv) => conv.id));
  const serverOnly = serverConvs
    .filter((conv) => !localIds.has(conv.id))
    .map((conv) => ({
      createdAt: toInstant(conv.created_at).epochMilliseconds,
      id: conv.id,
      messageCount: conv.message_count,
      title: conv.title,
      updatedAt: toInstant(conv.updated_at).epochMilliseconds,
    }));
  return [...conversations, ...serverOnly];
};

/**
 * 获取删除会话后的下一个 currentId
 * @param conversations  当前会话列表
 * @param deletedId      已删除的会话 ID
 * @returns              下一个会话 ID 或 null
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
// 获取删除会话后的下一个 currentId
export const getNextConversationId = (
  conversations: Conversation[],
  deletedId: string,
): string | null => {
  const remaining = conversations.filter((conv) => conv.id !== deletedId);
  return remaining[FIRST_INDEX]?.id ?? null;
};
