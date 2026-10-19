// Chat share API 客户端 (2026-06-16)
// 创建 / 拉取 / 撤销 chat 对话分享 (公开只读链接).
// GET 端点公开 (anon 可读), POST / DELETE 需鉴权 (cookie 自动带).
import { apiFetch } from "./config";

/**
 * 分享对话响应
 */
export interface ShareResponse {
  share_id: string;
  url: string;
  title: string;
  expires_at: string | null;
  created_at: string;
}

/**
 * 分享对话中的消息
 */
export interface SharedMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

/**
 * 分享对话完整响应
 */
export interface SharedConversationResponse {
  share_id: string;
  title: string;
  messages: SharedMessage[];
  model: string | null;
  created_at: string;
}

/**
 * 创建分享输入参数
 */
export interface CreateShareInput {
  convId: string;
  title?: string | null;
  messages: { role: "user" | "assistant"; content: string; timestamp?: string | null }[];
}

/**
 * 创建对话分享链接
 * @param req    创建分享请求
 * @returns      分享响应
 *
 * @client-bff
 */
export const createShare = (req: CreateShareInput): Promise<ShareResponse> =>
  apiFetch("/api/chat/shares", {
    body: {
      conv_id: req.convId,
      title: req.title ?? null,
      messages: req.messages,
    },
    method: "POST",
  });

/**
 * 列出对话的分享链接
 * @param convId  对话 ID
 * @returns       分享列表
 *
 * @client-bff
 */
export const listShares = (convId: string): Promise<ShareResponse[]> =>
  apiFetch(`/api/chat/shares?conv_id=${encodeURIComponent(convId)}`, { method: "GET" });

/**
 * 获取单个分享详情
 * @param shareId  分享 ID
 * @returns        分享对话响应
 *
 * @client-bff
 */
export const getShare = (shareId: string): Promise<SharedConversationResponse> =>
  apiFetch(`/api/chat/shares/${shareId}`, { method: "GET" });

/**
 * 撤销对话分享
 * @param shareId  分享 ID
 *
 * @client-bff
 */
export const revokeShare = (shareId: string): Promise<void> =>
  apiFetch(`/api/chat/shares/${shareId}`, { method: "DELETE" });
