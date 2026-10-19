/**
 * useChatWithPersistence hook (2026-07-01 chat AI SDK 协议层 Phase 2)
 *
 * 职责:
 *   - 包 AI SDK 7 useChat + 注入 DifyHttpChatTransport (5 段 ChatEvent → UIMessageChunk)
 *   - Chat 实例 keying by convId ( 新 Chat 实例 → useChat 自动 reset state)
 *   - onFinish / onError 持久化 callback:
 *     - 登录态 → persistAssistantToServer (account 写后端 PG)
 *     - 全局 → saveMessages (IDB 永远写, account + anon 都走)
 *
 * 跟旧 useChatShellState 的区别:
 *   - 旧: messagesByConv / streamingConvId / aborters 手写状态
 *   - 新: useChat 内置 messages / status / sendMessage / stop, hook 只做 IDB/server 持久化
 *
 * 边界: 客户端 (用 useAuthStore + storage).
 */

import { Chat, useChat } from "@ai-sdk/react";
import type { UIMessage } from "ai";
import { useMemo, useRef } from "react";

import { DifyHttpChatTransport } from "./dify-http-chat-transport";
import {
  messageToUIMessage,
  uiMessageToMessage,
  type ChatMessageMetadata,
} from "./ui-message-adapter";
import type { Message, ChatFile } from "./types";
import { persistAssistantToServer } from "./stream-handler";
import { saveMessages } from "./storage";

type ChatMessage = UIMessage<ChatMessageMetadata>;

const EMPTY_LEN = 0;

/** useChatWithPersistence 入参, 控制 conv / 账号 / 持久化行为.
 * @client-bff */
export interface UseChatWithPersistenceParams {
  convId: string | null;
  /** (2026-07-01) Dify 端 conv id (跟 RAG conv id 不同维度). null = 新 conv. */
  difyConversationId: string | undefined;
  /** (2026-07-01) 账号 id 或 null. isAccount=true 时非 null. */
  accountId: number | null;
  isAccount: boolean;
  /** (2026-07-01) 初始 messages (load 历史用). 通常从 IDB (anon) 或 server detail (account) 来. */
  initialMessages: Message[];
  /** (2026-07-01) TanStack Query mutate (登录态用). anon 跳过. */
  appendMessageMut:
    | ((args: {
        convId: string;
        role: "user" | "assistant" | "system";
        content: string;
        meta?: Record<string, unknown>;
      }) => void)
    | null;
  /** (2026-07-01) 附件列表, 发消息时随 transport body 传 Dify. */
  files?: ChatFile[];
}

/**
 * (2026-07-01) Phase 2 chat hook: 替代 useChatShellState + useChatHandlers.handleSend/stop.
 * Chat 实例 keying by convId; onFinish/onError 触发 IDB + (登录态) server 持久化.
 */
export const useChatWithPersistence = ({
  convId,
  difyConversationId,
  isAccount,
  initialMessages,
  appendMessageMut,
  files,
}: UseChatWithPersistenceParams) => {
  // (2026-07-01) Transport: 5 段 ChatEvent → UIMessageChunk + 注入 user/buyer_key.
  const transport = useMemo(
    () =>
      new DifyHttpChatTransport({
        api: "/api/chat/messages",
        body: {
          conversationId: difyConversationId,
          files: files && files.length > EMPTY_LEN ? files : undefined,
        },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps by design: accountId 由 prepareSendMessagesRequest 实时读 store
    [difyConversationId, files],
  );

  // (2026-07-01) Chat 实例 keying by convId: convId 变 → 新实例 → useChat recreate.
  const chat = useMemo(
    () =>
      new Chat({
        id: convId ?? "transient",
        messages: initialMessages.map(messageToUIMessage),
        transport,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps by design: Chat + transport 双 keying
    [convId, transport],
  );

  // (2026-07-01) 用 ref 包 onFinish callback, 避免 useChat 闭包 stale.
  const appendMessageMutRef = useRef(appendMessageMut);
  appendMessageMutRef.current = appendMessageMut;
  const convIdRef = useRef(convId);
  convIdRef.current = convId;
  const isAccountRef = useRef(isAccount);
  isAccountRef.current = isAccount;

  return useChat<ChatMessage>({
    chat,
    onError: (_err) => {
      const cid = convIdRef.current;
      if (!cid) {
        return;
      }
      const mut = appendMessageMutRef.current;
      if (mut && isAccountRef.current) {
        persistAssistantToServer({
          convId: cid,
          content: "",
          errorCode: "client_error",
          finishReason: "error",
          isAccount: true,
          mutate: mut,
        });
      }
      // IDB 写空内容 (跟旧 handleStreamError 行为对齐: 不管 err 都落库 partial / empty)
      saveMessages(cid, []);
    },
    onFinish: ({ message }) => {
      const cid = convIdRef.current;
      if (!cid) {
        return;
      }
      const flat = uiMessageToMessage(message);
      const mut = appendMessageMutRef.current;
      if (mut && isAccountRef.current) {
        persistAssistantToServer({
          citations: flat.citations,
          convId: cid,
          content: flat.content,
          finishReason: "stop",
          isAccount: true,
          mutate: mut,
        });
      }
      // IDB 永远写 (account 跟 anon 都走, server load 时兜底)
      saveMessages(cid, [flat]);
    },
    transport,
  });
};
