/**
 * 服务端消息持久化 helpers (2026-06-24 chat-message-persistence)
 * (2026-07-01) Phase 2 重构: 流式状态 (applyEvent / processStream / handleStreamError / ensureConversation / initMessages)
 *   全部删除, useChat + onFinish/onError 接管. 只保留 persistAssistantToServer / persistUserToServer / AppendMutateFn.
 */

import type { Citation } from "./types";

type AppendMutateFn = (args: {
  convId: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta?: Record<string, unknown>;
}) => void;
export type { AppendMutateFn };

type FinishReason = "stop" | "interrupted" | "error";

/** useChat onFinish callback 内调: 持久化 assistant 完整内容到后端 PG (登录态; anon 跳过).
 *  meta 带 finish_reason + 可选 error_code / citations. */
export const persistAssistantToServer = ({
  convId,
  content,
  finishReason,
  errorCode,
  citations,
  isAccount,
  mutate,
}: {
  convId: string;
  content: string;
  finishReason: FinishReason;
  errorCode?: string;
  citations?: Citation[];
  isAccount: boolean;
  mutate: AppendMutateFn;
}): void => {
  if (!isAccount) {
    return;
  }
  mutate({
    convId,
    role: "assistant",
    content,
    meta: {
      finish_reason: finishReason,
      error_code: errorCode,
      citations,
    },
  });
};

/** useChat handleSend 内调 (新建 user msg). anon 跳过. */
export const persistUserToServer = ({
  convId,
  content,
  isAccount,
  mutate,
}: {
  convId: string;
  content: string;
  isAccount: boolean;
  mutate: AppendMutateFn;
}): void => {
  if (!isAccount) {
    return;
  }
  mutate({ convId, role: "user", content });
};
