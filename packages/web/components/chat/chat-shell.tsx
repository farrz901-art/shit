/**
 * 智能体聊天 Shell (2026-07-01 chat AI SDK 协议层 Phase 2)
 * 拆分为: useChatShellUiState (UI) + useServerData (TanStack Query) + useChatShellChat (AI SDK useChat)
 * 本组件做 5 件事:
 *   1. useAnonToLoginMigration 切 isAccount 时清 anon local uuid 防 404
 *   2. useEffectOnce 登录态清残留 / anon 态从 IDB 加载首屏
 *   3. 组合 UI state + server data + chat (useChat) 三 hook
 *   4. 组合 ConversationList / MessageList / Composer / ChatHeader / 2 Dialog
 *   5. 用 AppConfirm 做删除二次确认
 */
"use client";
import type { ChatFile, Message } from "@/lib/chat/types";
import { useEffect, useRef } from "react";
import { useEffectOnce } from "react-use";
import { ConversationList } from "./conversation-list";
import { MessageList } from "./message-list";
import { Composer } from "./compose";
import { ChatHeader } from "./chat-header";
import { MemoryManagementDialog } from "./memory-management-dialog";
import { ShareDialog } from "./share-dialog";
import { nowMs } from "@/lib/date";
import { AppConfirm } from "@/components/common/confirm/app-confirm";
import { useAnonToLoginMigration } from "@/lib/chat/migration";
import { loadConversations, loadAllMessages, saveMessages } from "@/lib/chat/storage";
import {
  useChatShellUiState,
  useServerData,
  useChatShellChat,
  createLocalConv,
  pickNextConvId,
  doCreateServerConv,
  deleteConversationLocal,
} from "@/lib/chat/use-chat-state";

const FIRST_INDEX = 0;
const ZERO_MSGS = 0;

/**
 * 智能体聊天 Shell 主组件 — 组合会话列表/消息列表/输入框/弹框
 * @param props.isAccount 是否为登录账号
 * @returns JSX 元素
 * @client-bff
 */
// eslint-disable-next-line max-statements -- 5 useState/useRef + 3 hooks, 拆分跨闭包变量难维护
export const ChatShell = ({ isAccount = true }: { isAccount?: boolean } = {}) => {
  const uiState = useChatShellUiState();
  const accountIdFromStore = useAccountId(isAccount);

  // (2026-06-23) isAccount 切换时 reset currentId, 防止 anon local uuid 残留 → 404.
  useAnonToLoginMigration(isAccount);

  // anon 路径: 首屏从 IDB 加载 (conversations + messages)
  // 登录路径: 由 useChatShellChat 内部 useConversation 拉 server detail
  const initialMessagesByConv = useRef<Record<string, Message[]>>({});
  /** 从 IDB 加载 anon 会话首屏数据 */
  const loadInitialAnonData = async () => {
    // (2026-06-23) db 层已只返 owner=anon, 这里不再过滤 owner
    const saved = await loadConversations();
    uiState.setConversations(saved);
    const savedMessages = await loadAllMessages();
    initialMessagesByConv.current = savedMessages;
    if (saved.length > FIRST_INDEX) {
      uiState.setCurrentId(saved[FIRST_INDEX].id);
    }
  };

  useEffectOnce(() => {
    if (isAccount) {
      // 登录态: 不读 IDB, 不设 currentId. 等用户点 / 选.
      // 同时把可能残留的 anon local uuid 清掉.
      if (uiState.currentId !== null) {
        const isLocal = !/^[0-9a-f]{8}-/i.test(uiState.currentId);
        if (isLocal) {
          uiState.setCurrentId(null);
        }
      }
      return;
    }
    loadInitialAnonData();
  });

  const serverData = useServerData({
    conversations: uiState.conversations,
    isAccount,
  });

  // 当前 conv 的 messages / sendMessage / stop / streaming
  // initialMessages: anon 路径从 IDB 缓存拿, 登录路径空 (由 useConversation 拉 server)
  const initialMessagesForChat: Message[] =
    !isAccount && uiState.currentId ? (initialMessagesByConv.current[uiState.currentId] ?? []) : [];

  const chat = useChatShellChat({
    accountId: accountIdFromStore,
    convId: uiState.currentId,
    initialMessages: initialMessagesForChat,
    isAccount,
  });

  // 侧栏点击 / 创建 / 删除 handler
  const handlers = {
    confirmDelete: async () => {
      const targetId = uiState.pendingDeleteId;
      if (!targetId) {
        return;
      }
      const nextId = pickNextConvId(serverData.effectiveConversations, targetId);
      if (isAccount) {
        serverData.deleteConvMut.mutate(targetId);
      } else {
        deleteConversationLocal(targetId);
        // 同步清 anon IDB 残留
      }
      uiState.setConversations((prev) => prev.filter((conv) => conv.id !== targetId));
      uiState.setCurrentId((prev) => (prev === targetId ? nextId : prev));
      uiState.setPendingDeleteId(null);
    },
    handleNew: () => {
      if (isAccount) {
        serverData.createConvMut.mutate({} as { title?: string }, {
          onSuccess: (serverConv: { id: string; title: string }) => {
            uiState.setCurrentId(serverConv.id);
          },
        });
        return;
      }
      const conv = createLocalConv("新对话");
      uiState.setConversations((prev) => [...prev, conv]);
      uiState.setCurrentId(conv.id);
    },
    // eslint-disable-next-line max-statements -- 登录态建 conv + 发消息 + IDB 同步, 拆函数会跨闭包变量
    handleSend: async (text: string, files: ChatFile[] = []) => {
      // 登录态: 如 conv 不在 server, 先建 server conv
      if (isAccount) {
        const cid = uiState.currentId;
        const inServer = serverData.effectiveConversations.some((conv) => conv.id === cid);
        if (!inServer) {
          const result = await doCreateServerConv({
            createConvMut: serverData.createConvMut,
            isAccount,
          });
          if (result.id) {
            uiState.setCurrentId(result.id);
          } else {
            return;
          }
        }
      }
      chat.sendMessage(text, files);
      // 写 user msg 进 IDB (anon + account 都走, 兜底 + 跨刷新稳定)
      const cid = uiState.currentId;
      if (cid) {
        const currentMsgs = initialMessagesByConv.current[cid] ?? [];
        const newUserMsg: Message = {
          content: text,
          createdAt: nowMs(),
          id: `msg-${nowMs()}`,
          role: "user",
        };
        const updated = [...currentMsgs, newUserMsg];
        initialMessagesByConv.current[cid] = updated;
        saveMessages(cid, updated);
      }
    },
    handleStop: () => {
      chat.stop();
    },
  };

  // 当 chat.messages 更新 (流式 / onFinish), 同步写 IDB
  useEffect(() => {
    if (!isAccount) {
      const cid = uiState.currentId;
      if (cid && chat.messages.length > ZERO_MSGS) {
        saveMessages(cid, chat.messages);
        initialMessagesByConv.current[cid] = chat.messages;
      }
    }
  }, [chat.messages, uiState.currentId, isAccount]);

  return (
    <div className="flex h-full min-h-0 w-full" data-testid="chat-shell">
      <ConversationList
        conversations={serverData.effectiveConversations}
        currentId={uiState.currentId}
        onCreate={handlers.handleNew}
        onDelete={(id) => uiState.setPendingDeleteId(id)}
        onSelect={(id) => uiState.setCurrentId(id)}
      />
      <div className="flex flex-1 flex-col">
        <ChatHeader
          isAccount={isAccount}
          onMemoryOpen={() => uiState.setMemoryOpen(true)}
          onShareOpen={() => uiState.setShareOpen(true)}
        />
        <MessageList
          messages={chat.messages}
          streamingMessageId={chat.isStreaming ? "current" : undefined}
        />
        <Composer
          disabled={false}
          onChange={uiState.setDraft}
          onSend={handlers.handleSend}
          onStop={handlers.handleStop}
          streaming={chat.isStreaming}
          value={uiState.draft}
        />
      </div>

      <AppConfirm
        cancelText="取消"
        confirmText="删除"
        description="该会话的所有消息将被永久删除, 不可恢复。"
        onConfirm={handlers.confirmDelete}
        onOpenChange={(open) => {
          if (!open) {
            uiState.setPendingDeleteId(null);
          }
        }}
        open={uiState.pendingDeleteId !== null}
        title="确认删除会话?"
        variant="destructive"
      />

      <MemoryManagementDialog onOpenChange={uiState.setMemoryOpen} open={uiState.memoryOpen} />
      <ShareDialog
        convId={uiState.currentId}
        messages={chat.messages}
        onOpenChange={uiState.setShareOpen}
        open={uiState.shareOpen}
      />
    </div>
  );
};

/**
 * (2026-07-01) 拿账号 id: 登录态从 store 取, anon 返 null.
 * 用 useRef 包 + read on demand, 避免每次 render 触发 auth-store subscribe.
 */
/**
 * useAccountId - 获取当前账号 ID
 * @param isAccount - 是否为登录账号
 * @returns 账号 ID 或 null
 */
import { useAuthStore } from "@/lib/store/auth-store";
const useAccountId = (isAccount: boolean): number | null => {
  const ref = useRef<number | null>(null);
  if (isAccount) {
    ref.current = useAuthStore.getState().accountId;
  } else {
    ref.current = null;
  }
  return ref.current;
};
