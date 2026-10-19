"use client";

// (2026-07-01) Phase 2 重构: 状态管理走 AI SDK useChat + DifyHttpChatTransport,
// useChatShellState 仅保留 UI state (pendingDeleteId / memoryOpen / shareOpen)
// + 全局 currentId / conversations. 流式状态 (messages / streaming / abort) 走 useChat.

import type { ChatFile, Conversation, Message } from "./types";
import {
  useAppendMessage,
  useConversation,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useRenameConversation,
  type ServerConversation,
  type ServerConversationDetail,
} from "./api";
import { deleteConversation as storageDelete, upsertConversation } from "./storage";
import { useState } from "react";
import { useLocalStorage } from "react-use";
import { computeEffectiveConversations, getNextConversationId, newId } from "./chat-utils";
import { useChatWithPersistence } from "./use-chat-with-persistence";
import { log } from "@/lib/log";
import { nowMs, toInstant } from "@/lib/date";

const DRAFT_KEY = "rag.chat.draft.v1";
const ZERO_LEN = 0;
const FIRST_INDEX = 0;

// --- 轻量 UI state (dialogs + 当前 conv) ---

/**
 * (2026-07-01) Phase 2 拆分: useChatShellState 之前含 8 个 useState, 现拆为 2 个职责:
 *   - useChatShellUiState: 只管 UI (pendingDeleteId / memoryOpen / shareOpen) + draft (localStorage)
 *   - useServerData: 服务端 TanStack Query (列表 / CRUD / appendMessage)
 *   - useChatWithPersistence: 接入 AI SDK useChat (messages / streaming / abort)
 */
export interface ChatShellUiState {
  currentId: string | null;
  conversations: Conversation[];
  draft: string;
  memoryOpen: boolean;
  pendingDeleteId: string | null;
  setConversations: React.Dispatch<React.SetStateAction<Conversation[]>>;
  setCurrentId: React.Dispatch<React.SetStateAction<string | null>>;
  setDraft: (draft: string) => void;
  setMemoryOpen: (open: boolean) => void;
  setPendingDeleteId: (id: string | null) => void;
  setShareOpen: (open: boolean) => void;
  shareOpen: boolean;
}

/**
 * (2026-07-01) 轻量 UI hook: conversations / currentId / dialogs / draft.
 * 纯 React state, 不拉网络.
 */
export const useChatShellUiState = (): ChatShellUiState => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [draft = "", setDraft] = useLocalStorage<string>(DRAFT_KEY, "");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  return {
    conversations,
    currentId,
    draft,
    memoryOpen,
    pendingDeleteId,
    setConversations,
    setCurrentId,
    setDraft,
    setMemoryOpen,
    setPendingDeleteId,
    setShareOpen,
    shareOpen,
  };
};

// --- 服务端数据 hook (TanStack Query, 不动) ---

/** useServerData 入参, 传入本地 conversations + 登录标志.
 * @client-bff */
export interface ServerDataParams {
  conversations: Conversation[];
  isAccount: boolean;
}

/** useServerData 返回值, 含 mutation 函数 + 合并后的有效对话列表.
 * @client-bff */
export interface ServerData {
  appendMessageMut: ReturnType<typeof useAppendMessage>;
  createConvMut: ReturnType<typeof useCreateConversation>;
  deleteConvMut: ReturnType<typeof useDeleteConversation>;
  effectiveConversations: Conversation[];
  renameConvMut: ReturnType<typeof useRenameConversation>;
  serverConvs: Conversation[];
}

/** (2026-07-01) ServerConversation 字段映射 (id / title / created_at / updated_at / message_count)
 *  到前端 Conversation (id / title / createdAt / updatedAt / messageCount).
 *  computeEffectiveConversations 内部已经做 Date.parse 转换, 这里只做字段名 mapping. */
const serverConvToClient = (server: ServerConversation): Conversation => ({
  createdAt: toInstant(server.created_at).epochMilliseconds,
  id: server.id,
  messageCount: server.message_count,
  title: server.title,
  updatedAt: toInstant(server.updated_at).epochMilliseconds,
});

/**
 * (2026-07-01) TanStack Query hook: 列表 / CRUD / appendMessage.
 * serverConvs 转换为 Conversation (camelCase), merge 到 effectiveConversations.
 */
export const useServerData = ({ isAccount, conversations }: ServerDataParams): ServerData => {
  const { data: serverConvsRaw = [] } = useConversations(isAccount);
  const effectiveConversations = computeEffectiveConversations(
    conversations,
    serverConvsRaw,
    isAccount,
  );
  const serverConvs = serverConvsRaw.map(serverConvToClient);
  const createConvMut = useCreateConversation();
  const deleteConvMut = useDeleteConversation();
  const renameConvMut = useRenameConversation();
  const appendMessageMut = useAppendMessage();
  void renameConvMut;
  return {
    appendMessageMut,
    createConvMut,
    deleteConvMut,
    effectiveConversations,
    renameConvMut,
    serverConvs,
  };
};

// --- 单 conv 的 chat 数据 (messages / streaming / abort) + 历史 load ---

/** useChatShellChat 入参, 指定当前 conv / 账号 / 初始消息.
 * @client-bff */
export interface ChatShellChatParams {
  isAccount: boolean;
  convId: string | null;
  accountId: number | null;
  initialMessages: Message[];
}

/** useChatShellChat 返回值, 含消息列表 / 发送 / 停止 / 流状态.
 * @client-bff */
export interface ChatShellChat {
  appendMessageMut: ReturnType<typeof useAppendMessage> | null;
  initialMessagesForPersistence: Message[];
  isStreaming: boolean;
  messages: Message[];
  sendMessage: (text: string, files?: ChatFile[]) => void;
  status: string;
  stop: () => void;
}

/** 构建初始消息列表: 登录态从 server 拉历史, anon 态用传入的 initialMessages.
 * @param isAccount 是否为登录账号
 * @param currentDetail 当前会话详情 (服务端返回)
 * @param initialMessages 初始消息列表
 * @returns 构建后的消息列表 */
const buildInitialMessages = (
  isAccount: boolean,
  currentDetail: ServerConversationDetail | undefined,
  initialMessages: Message[],
): Message[] => {
  if (!isAccount || !currentDetail?.messages) {
    return initialMessages;
  }
  // (2026-06-24) Bug 修: 本地已有消息时 (刚发 / 正在 streaming) 不覆盖.
  // 仅当本地为空 (切换到已有 conv 首次加载) 才填后端历史.
  if (initialMessages.length > ZERO_LEN) {
    return initialMessages;
  }
  return currentDetail.messages.map((msg) => {
    let role: "user" | "assistant" = "user";
    if (msg.role !== "system") {
      ({ role } = msg);
    }
    return {
      content: msg.content,
      createdAt: toInstant(msg.created_at).epochMilliseconds,
      id: msg.id,
      role,
    };
  });
};

/**
 * (2026-07-01) 接入 useChatWithPersistence: 当前 conv 的 messages / streaming / sendMessage / stop.
 * 登录态: 从 server useConversation 拉历史 (有内容时用 server, 否则空 []).
 * anon 态: 初始 messages 由 chat-shell 在 useEffectOnce 里 load IDB 注入 (不在这 hook 里读 IDB).
 */
export const useChatShellChat = ({
  isAccount,
  convId,
  accountId,
  initialMessages,
}: ChatShellChatParams): ChatShellChat => {
  // 登录态: 从 server 拉历史 detail (account 走 useConversation)
  const conversationIdForHook: string | null = isAccount ? convId : null;
  const { data: currentDetail } = useConversation(conversationIdForHook);
  const initialMessagesForPersistence = buildInitialMessages(
    isAccount,
    currentDetail,
    initialMessages,
  );

  const { messages, sendMessage, status, stop } = useChatWithPersistence({
    accountId,
    appendMessageMut: null, // chat-shell 在 handleSend 里 mutate, 不在 hook 里 bind
    convId,
    difyConversationId: undefined, // chat-shell 在 useEffect 里同步 dify conv id
    initialMessages: initialMessagesForPersistence,
    isAccount,
  });

  // useChat 的 messages 是 UIMessage[], 转回 flat Message 给 MessageList.
  // TODO(2026-07-01 T7): UI 改吃 UIMessage, 此处转换临时保留, 跟 MessageBubble 旧接口兼容.
  const flatMessages: Message[] = messages.map((uimsg) => {
    const text = uimsg.parts
      .filter((part) => part.type === "text")
      .map((part) => part.text)
      .join("");
    return {
      content: text,
      // uimsg.id 是 AI SDK 生成的随机 id, 不是 RFC 9557 时间戳, 不能喂 toInstant().
      // 转换层拿不到原始 createdAt, 用渲染时刻的 nowMs() 兜底, 跟旧 useChatShellState 行为一致.
      createdAt: nowMs(),
      id: uimsg.id,
      role: uimsg.role === "user" ? "user" : "assistant",
    };
  });

  return {
    appendMessageMut: null,
    initialMessagesForPersistence,
    isStreaming: status === "submitted" || status === "streaming",
    messages: flatMessages,
    sendMessage: (text: string, _files?: ChatFile[]) => {
      sendMessage({ text });
    },
    status,
    stop,
  };
};

// --- 兼容旧 API (chat-shell 还在 T7 接入, 暂时保留) ---

/**
 * (2026-07-01) ⚠️ Deprecated: 旧 useChatShellState shape.
 * T7 后 chat-shell 不再用, 删此函数. 保留目的: 中间 commit 不破 build.
 */
export const useChatShellState = (): ChatShellUiState => useChatShellUiState();

/**
 * (2026-07-01) ⚠️ Deprecated: 旧 removeConvLocal.
 * T7 后由 ChatShell 内部 handler 处理.
 */
export const removeConvLocal = (targetId: string, state: ChatShellUiState): void => {
  state.setConversations((prev) => prev.filter((conv) => conv.id !== targetId));
};

// --- handler helpers (T7 在 chat-shell.tsx 里 inline, 这里只留工具) ---

const TITLE_LEN = 20;

/**
 * (2026-07-01) 创建 anon 本地 conv (新对话 / anon 路径).
 */
export const createLocalConv = (text: string): Conversation => {
  const conv: Conversation = {
    createdAt: nowMs(),
    id: newId(),
    messageCount: FIRST_INDEX,
    title: text.slice(FIRST_INDEX, TITLE_LEN),
    updatedAt: nowMs(),
  };
  upsertConversation(conv);
  return conv;
};

/**
 * (2026-07-01) 删除 conv 后选下一个 (跟旧 confirmDelete 同语义).
 */
export const pickNextConvId = (
  effectiveConversations: Conversation[],
  deletedId: string,
): string | null => getNextConversationId(effectiveConversations, deletedId);

/**
 * (2026-07-01) 包装 createConvMut.mutate 调用, 返新 conv id 给上层.
 */
/** doCreateServerConv 返回值, 包含新 conv id 或错误.
 * @client-bff */
export interface CreateConvResult {
  error?: unknown;
  id: string | null;
}

/**
 * doCreateServerConv — 创建服务端会话, 包装 createConvMut.mutateAsync
 * @param args.createConvMut 创建会话 mutation
 * @param args.isAccount 是否为登录用户
 * @returns 新会话 id, 失败时返回 error
 * @client-bff
 */
export const doCreateServerConv = async (args: {
  createConvMut: ReturnType<typeof useCreateConversation>;
  isAccount: boolean;
}): Promise<CreateConvResult> => {
  try {
    const serverConv = await args.createConvMut.mutateAsync({} as { title?: string });
    return { id: serverConv.id };
  } catch (error) {
    log.error("create conv failed", { error: String(error) });
    return { error, id: null };
  }
};

// 兼容旧 import (chat-shell 暂用)
/** 删除本地存储中的对话 (兼容旧 import).
 * @param targetId 要删除的 conv id
 * @client-bff */
export const deleteConversationLocal = (targetId: string): void => {
  storageDelete(targetId);
};
