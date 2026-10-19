"use client";

// REST API facade (2026-06-19 chat spec §6)
// 7 endpoints + TanStack Query hooks, integrated with existing lib/api/config.ts apiFetch.
// StaleTime 60s aligned with backend Redis cache; refetchOnWindowFocus for tab switching.
//
// NOTE: All paths start with /api/ — this is intentional.
// ApiFetch's resolveUrl() in lib/api/config.ts checks path.startsWith("/api/")
// To route through the BFF proxy (app/api/[...path]) in browser, or to the
// Backend API_BASE on server. Without /api/, browser requests would go
// Directly to the backend causing CORS errors.
//
// NOTE: lib/api/chat.ts's sendMessage() is for streaming Dify BFF chat
// Messages (POST /api/chat/messages, apiProxy, ReadableStream return).
// It cannot replace these conversation CRUD endpoints (different backend
// Routes, response types, and HTTP methods).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/config";
import { toast } from "sonner";
import { useTranslations } from "next-intl";

// ── Types ──

/**
 * 服务端会话摘要 (对应 chat_router GET /api/chat/conversations 单条)
 * @shared
 */
export interface ServerConversation {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

/**
 * 服务端单条消息
 * @shared
 */
export interface ServerMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta?: Record<string, unknown> | null;
  created_at: string;
}

/**
 * 会话详情 = 摘要 + messages 列表 (对应 GET /api/chat/conversations/:id)
 * @shared
 */
export interface ServerConversationDetail extends ServerConversation {
  messages: ServerMessage[];
}

// ── Query Keys ──

const KEYS = {
  conversation: (id: string) => ["chat", "conversations", id] as const,
  conversations: () => ["chat", "conversations"] as const,
};

// ── Hooks ──

/** 列出当前用户的全部会话.
 *  (2026-06-24) Bug 2 修: 加 `enabled` — anon 状态不该调 /api/chat/conversations
 *  (会被后端 401 + 污染日志). 调用方传 `isAccount`, anon 时 hook 返 `data=[]` 不发请求.
 */
export const useConversations = (enabled = true) =>
  useQuery({
    enabled,
    queryFn: () => apiFetch<ServerConversation[]>("/api/chat/conversations"),
    queryKey: KEYS.conversations(),
    refetchOnWindowFocus: true,
    staleTime: 60_000,
  });

/** 单会话详情, 含 messages. null id 时不发请求.
 *  (2026-06-23) 404 / 410 等"语义性"错误不重试: 切到已删/不存在 conv 时,
 *  TanStack 默认 retry 3 次会刷屏 + 浪费 backend 资源. retry 0 让它优雅失败,
 *  useEffect 上层根据 error 走 fallback (e.g. setCurrentId(null)).
 */
export const useConversation = (id: string | null) => {
  const emptyKey: readonly ["chat", string, string] = ["chat", "conversation", "none"];
  const activeKey: readonly ["chat", string, string] = KEYS.conversation(id ?? "");
  const conversationKey = id ? activeKey : emptyKey;
  return useQuery({
    enabled: Boolean(id),
    queryFn: () => apiFetch<ServerConversationDetail>(`/api/chat/conversations/${id}`),
    queryKey: conversationKey,
    retry: false,
    staleTime: 60_000,
  });
};

/** 创建会话 (POST); 成功后 invalidate 列表让侧栏刷新.
 *  (2026-06-24) Bug 3 修: 不要手动 JSON.stringify body. apiFetch 对 string body 会跳过
 *  Content-Type: application/json 自动注入 (见 lib/api/config.ts:107-114), 浏览器 fetch
 *  默认就给 string body 加 text/plain 头, BFF 透传给 FastAPI → Pydantic 拿不到 JSON → 500.
 *  正确用法跟 lib/api/account.ts:6 / approvals.ts:64 一致: 传 object body.
 */
export const useCreateConversation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ title }: { title?: string } = {}) =>
      apiFetch<ServerConversation>("/api/chat/conversations", {
        body: { title },
        method: "POST",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.conversations() }),
  });
};

/** 重命名会话 (PATCH); 同时 invalidate 列表 + 详情.
 *  (2026-06-24) Bug 3 修: 同 useCreateConversation, body 改 object 让 apiFetch 自动序列化.
 */
export const useRenameConversation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      apiFetch<ServerConversation>(`/api/chat/conversations/${id}`, {
        body: { title },
        method: "PATCH",
      }),
    onSuccess: (unused, vars) => {
      qc.invalidateQueries({ queryKey: KEYS.conversations() });
      qc.invalidateQueries({ queryKey: KEYS.conversation(vars.id) });
    },
  });
};

/** 软删会话 (DELETE); invalidate 列表让软删条目淡出 */
export const useDeleteConversation = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/api/chat/conversations/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.conversations() }),
  });
};

/** 备份全部会话 (GET /api/chat/backup, 返 JSON dump) */
export const useBackup = () =>
  useMutation({
    mutationFn: () => apiFetch<unknown>("/api/chat/backup"),
  });

// ---- 单条消息追加 (2026-06-24 chat-message-persistence) ----

interface AppendMessageArgs {
  convId: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta?: Record<string, unknown>;
}

/** 追加单条消息到指定 conv (POST /conversations/{id}/messages).
 *
 * (2026-06-24 chat-message-persistence)
 * - onSuccess: invalidate list + detail 2 keys, 让侧栏数字 + 详情自动刷
 * - onError: 弹 toast "消息保存失败, 刷新后可能丢失"; 不阻塞 UI (UI 已乐观更新)
 * - meta 透传 JSON: finish_reason / error_code / citations / tokens 等
 */
export const useAppendMessage = () => {
  const qc = useQueryClient();
  const translate = useTranslations();
  return useMutation({
    mutationFn: ({ convId, role, content, meta }: AppendMessageArgs) =>
      apiFetch<ServerMessage>(`/api/chat/conversations/${convId}/messages`, {
        body: { role, content, meta },
        method: "POST",
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: KEYS.conversations() });
      qc.invalidateQueries({ queryKey: KEYS.conversation(vars.convId) });
    },
    onError: () => {
      // (2026-06-24) 单例 id: 连续触发保存失败时,新 toast 替换旧 toast,
      // 避免屏幕上堆 3-5 条相同红条. 固定 id 让 sonner 复用同一 slot.
      toast.error(translate("消息保存失败, 刷新后可能丢失"), {
        id: "chat-append-message-failed",
      });
    },
  });
};
