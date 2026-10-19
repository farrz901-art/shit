/**
 * ui-message-adapter (2026-07-01 chat AI SDK 协议层 Phase 2)
 * 3 个转换函数: IDB flat Message ↔ AI SDK UIMessage ↔ ServerMessage
 *
 * 职责边界:
 *   - 只做数据形状转换, 不做业务持久化 (调用方决定何时调用)
 *   - 字段命名: IDB `citations` / `thinking` / `interrupted` 走 UIMessage.metadata;
 *     reasoning parts 走 UIMessage.parts (type: "reasoning")
 *   - ServerMessage.meta 包含 finish_reason / citations / interrupted (来自 useConversation 后端响应)
 *
 * 3 函数:
 *   1. messageToUIMessage(m: Message): UIMessage — IDB flat → useChat
 *   2. uiMessageToMessage(u: UIMessage): Message — useChat → IDB flat
 *   3. serverMessageToUIMessage(s: ServerMessage): UIMessage — TanStack fetch → useChat (load 历史)
 */

import type { UIMessage, TextUIPart } from "ai";

import type { Message, Citation } from "./types";
import type { ServerMessage } from "./api";
import { nowMs, toInstant } from "@/lib/date";

/**
 * (2026-07-01) UIMessage<TMetadata> 用强类型 metadata 避免每处 cast.
 * 字段: conversationId, citations, thinking, interrupted, createdAt.
 */
export interface ChatMessageMetadata {
  conversationId?: string;
  citations?: Citation[];
  thinking?: Message["thinking"];
  interrupted?: boolean;
  createdAt?: number;
}

/** IDB flat Message → AI SDK UIMessage (with typed metadata).
 *  thinking 走 metadata.thinking (无损), parts 只放 text (UI stream 用).
 */
export const messageToUIMessage = (msg: Message): UIMessage<ChatMessageMetadata> => {
  const parts: TextUIPart[] = [{ type: "text", text: msg.content, state: "done" }];
  const metadata: ChatMessageMetadata = {
    citations: msg.citations,
    conversationId: msg.conversationId,
    createdAt: msg.createdAt,
    interrupted: msg.interrupted,
    thinking: msg.thinking,
  };
  return {
    id: msg.id,
    metadata,
    parts,
    role: msg.role,
  };
};

/** AI SDK UIMessage → IDB flat Message. text part 直接当 content, thinking 从 metadata 拿. */
export const uiMessageToMessage = (ui: UIMessage<ChatMessageMetadata>): Message => {
  const text = ui.parts
    .filter((part): part is TextUIPart => part.type === "text")
    .map((part) => part.text)
    .join("");
  const thinking = ui.metadata?.thinking;
  return {
    citations: ui.metadata?.citations,
    content: text,
    conversationId: ui.metadata?.conversationId,
    createdAt:
      ui.metadata?.createdAt ??
      (Number.isFinite(toInstant(ui.id).epochMilliseconds)
        ? toInstant(ui.id).epochMilliseconds
        : nowMs()),
    id: ui.id,
    interrupted: ui.metadata?.interrupted,
    role: ui.role as "user" | "assistant",
    thinking: thinking?.length ? thinking : undefined,
  };
};

/**
 * ServerMessage → UIMessage (load 历史用).
 * ServerMessage.meta 是个 JSON dict, 包含 finish_reason / citations / error_code / interrupted.
 */
export const serverMessageToUIMessage = (server: ServerMessage): UIMessage<ChatMessageMetadata> => {
  const meta = (server.meta ?? {}) as {
    citations?: Citation[];
    interrupted?: boolean;
  };
  return {
    id: server.id,
    metadata: {
      citations: meta.citations,
      createdAt: toInstant(server.created_at).epochMilliseconds || nowMs(),
      interrupted: meta.interrupted,
    },
    parts: [{ type: "text", text: server.content, state: "done" }],
    role: server.role === "system" ? "assistant" : server.role,
  };
};
