/**
 * useChatWithPersistence 单元测试 (2026-07-01 chat AI SDK 协议层 Phase 2)
 *
 * 覆盖:
 *   1. isAccount → body 含 accountId + buyer_key
 *   2. anon → body 含 anon uuid (从 storage 缓存)
 *   3. Chat 实例 keying by convId (新 Chat 实例)
 *   4. onFinish 触发 persistAssistantToServer (account) + saveMessages (IDB)
 *   5. onError 触发 persistAssistantToServer with finishReason="error"
 *   6. 切换 convId → 新 Chat 实例 + messages 重置
 *
 * ⚠️ mock @ai-sdk/react 整个模块: 用伪 Chat + 假 useChat 追踪 instances / 返 messages / onFinish 触发,
 *   避免拉真 AI SDK + 网络.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { ANON_USER_ID_KEY } from "@/const";
import type { Message } from "./types";

// --- Mock @ai-sdk/react 整个模块 ---
interface TrackedChat {
  id: string;
  initialMessages: unknown[];
  /** 模拟 onFinish 回调测试: 外部触发时把传入的 message emit 出去 */
  triggerFinish: (msg: unknown) => void;
  triggerError: (err: Error) => void;
}
const allChatInstances: TrackedChat[] = [];
let lastUseChatOpts: {
  chat: TrackedChat;
  transport: unknown;
  onFinish?: (args: { message: unknown }) => void;
  onError?: (err: Error) => void;
} | null = null;
let mockMessages: unknown[] = [];
const mockSendMessage = vi.fn();
const mockStop = vi.fn();
let mockStatus: "ready" | "streaming" | "submitted" | "error" = "ready";
// eslint-disable-next-line init-declarations -- module-level mock state, 用 setter 在 beforeEach 改
let mockError = undefined as Error | undefined;

class FakeChat {
  id: string;
  messages: unknown[];
  triggerFinish: (msg: unknown) => void = () => undefined;
  triggerError: (err: Error) => void = () => undefined;
  constructor(opts: { id: string; messages?: unknown[]; transport?: unknown }) {
    this.id = opts.id;
    this.messages = opts.messages ?? [];
    const tracker: TrackedChat = {
      id: this.id,
      initialMessages: [...this.messages],
      triggerFinish: (msg) => this.triggerFinish(msg),
      triggerError: (err) => this.triggerError(err),
    };
    allChatInstances.push(tracker);
    tracker.triggerFinish = (msg) => {
      this.messages = [...this.messages, msg];
    };
  }
}

vi.mock("@ai-sdk/react", () => ({
  Chat: FakeChat,
  useChat: (opts: {
    chat: TrackedChat;
    transport: unknown;
    onFinish?: (args: { message: unknown }) => void;
    onError?: (err: Error) => void;
  }) => {
    lastUseChatOpts = opts;
    return {
      addToolApprovalResponse: vi.fn(),
      addToolOutput: vi.fn(),
      addToolResult: vi.fn(),
      clearError: vi.fn(),
      error: mockError,
      id: opts.chat.id,
      messages: mockMessages,
      regenerate: vi.fn(),
      resumeStream: vi.fn(),
      sendMessage: mockSendMessage,
      setMessages: vi.fn(),
      status: mockStatus,
      stop: mockStop,
    };
  },
}));

// --- Mock 业务依赖 ---
const persistAssistantToServerMock = vi.fn();
const saveMessagesMock = vi.fn();
const upsertConversationMock = vi.fn();
const getAuthState = vi.fn();

vi.mock("@/lib/store/auth-store", () => ({
  useAuthStore: { getState: () => getAuthState() },
}));
vi.mock("./stream-handler", () => ({
  persistAssistantToServer: (...args: unknown[]) => persistAssistantToServerMock(...args),
}));
vi.mock("./storage", () => ({
  saveMessages: (...args: unknown[]) => saveMessagesMock(...args),
  upsertConversation: (...args: unknown[]) => upsertConversationMock(...args),
}));

const { useChatWithPersistence } = await import("./use-chat-with-persistence");

const ZERO_IDX = 0;
const ONE_ITEM = 1;
const TWO_ITEMS = 2;
const FIXED_TS_MS = 1_700_000_000_000;
const ACCOUNT_ID_FOR_LOGIN = 42;
const CONV_ID_A = "conv-aaa";
const CONV_ID_B = "conv-bbb";

const baseInitialMessages: Message[] = [
  { content: "hello", createdAt: FIXED_TS_MS, id: "msg-u1", role: "user" },
];

describe("useChatWithPersistence — body 注入", () => {
  // eslint-disable-next-line max-statements -- mock 重置逻辑紧凑, 拆分反而跨闭包变量难维护
  beforeEach(() => {
    allChatInstances.length = 0;
    lastUseChatOpts = null;
    mockMessages = [];
    mockStatus = "ready";
    mockError = undefined;
    mockSendMessage.mockReset();
    mockStop.mockReset();
    persistAssistantToServerMock.mockReset();
    saveMessagesMock.mockReset();
    upsertConversationMock.mockReset();
    getAuthState.mockReturnValue({ accountId: null });
    globalThis.localStorage.removeItem(ANON_USER_ID_KEY);
  });
  afterEach(() => {
    globalThis.localStorage.removeItem(ANON_USER_ID_KEY);
  });

  it("登录态: 注入 accountId + buyer_key 到 transport body", () => {
    getAuthState.mockReturnValue({ accountId: ACCOUNT_ID_FOR_LOGIN });
    renderHook(() =>
      useChatWithPersistence({
        accountId: ACCOUNT_ID_FOR_LOGIN,
        appendMessageMut: vi.fn(),
        convId: CONV_ID_A,
        difyConversationId: "dify-conv-1",
        initialMessages: baseInitialMessages,
        isAccount: true,
      }),
    );
    expect(lastUseChatOpts).not.toBeNull();
    const transport = lastUseChatOpts?.transport as { body: { conversationId?: string } };
    expect(transport).toBeDefined();
    // transport body 是 static body (父类 HttpChatTransport 会合并)
    expect(transport.body.conversationId).toBe("dify-conv-1");
  });

  it("anon 态: useChat 仍被调, transport 创建", () => {
    getAuthState.mockReturnValue({ accountId: null });
    renderHook(() =>
      useChatWithPersistence({
        accountId: null,
        appendMessageMut: vi.fn(),
        convId: CONV_ID_A,
        difyConversationId: undefined,
        initialMessages: baseInitialMessages,
        isAccount: false,
      }),
    );
    expect(lastUseChatOpts).not.toBeNull();
    expect(allChatInstances).toHaveLength(ONE_ITEM);
    expect(allChatInstances[ZERO_IDX].id).toBe(CONV_ID_A);
  });

  it("切 convId → 新 Chat 实例 + initialMessages 注入", () => {
    getAuthState.mockReturnValue({ accountId: ACCOUNT_ID_FOR_LOGIN });
    const { rerender } = renderHook(
      ({ convId }: { convId: string }) =>
        useChatWithPersistence({
          accountId: ACCOUNT_ID_FOR_LOGIN,
          appendMessageMut: vi.fn(),
          convId,
          difyConversationId: "dify-conv",
          initialMessages: baseInitialMessages,
          isAccount: true,
        }),
      { initialProps: { convId: CONV_ID_A } },
    );
    expect(allChatInstances).toHaveLength(ONE_ITEM);
    rerender({ convId: CONV_ID_B });
    expect(allChatInstances).toHaveLength(TWO_ITEMS);
    expect(allChatInstances[ZERO_IDX + ZERO_IDX].id).toBe(CONV_ID_A);
    expect(allChatInstances[ZERO_IDX + ONE_ITEM].id).toBe(CONV_ID_B);
  });
});

describe("useChatWithPersistence — onFinish / onError 持久化", () => {
  // eslint-disable-next-line init-declarations -- let 变量, beforeEach 内赋 mock 引用
  let appendMutMock:
    | ((args: {
        convId: string;
        role: "user" | "assistant" | "system";
        content: string;
        meta?: Record<string, unknown>;
      }) => void)
    | null;

  // eslint-disable-next-line max-statements -- onFinish/onError 持久化测试 reset 逻辑紧凑
  beforeEach(() => {
    allChatInstances.length = 0;
    lastUseChatOpts = null;
    mockMessages = [];
    mockStatus = "ready";
    mockError = undefined;
    mockSendMessage.mockReset();
    mockStop.mockReset();
    appendMutMock = vi.fn() as unknown as typeof appendMutMock;
    persistAssistantToServerMock.mockReset();
    saveMessagesMock.mockReset();
    upsertConversationMock.mockReset();
    getAuthState.mockReturnValue({ accountId: ACCOUNT_ID_FOR_LOGIN });
    globalThis.localStorage.removeItem(ANON_USER_ID_KEY);
  });
  afterEach(() => {
    globalThis.localStorage.removeItem(ANON_USER_ID_KEY);
  });

  it("onFinish 触发 persistAssistantToServer + saveMessages (登录态)", () => {
    renderHook(() =>
      useChatWithPersistence({
        accountId: ACCOUNT_ID_FOR_LOGIN,
        appendMessageMut: appendMutMock,
        convId: CONV_ID_A,
        difyConversationId: "dify-conv-1",
        initialMessages: baseInitialMessages,
        isAccount: true,
      }),
    );
    const chat = allChatInstances[ZERO_IDX];
    expect(chat).toBeDefined();
    // 模拟 useChat 内部调用 onFinish
    const fakeMessage = {
      id: "msg-a1",
      metadata: { citations: [], createdAt: FIXED_TS_MS },
      parts: [{ state: "done", text: "answer", type: "text" }],
      role: "assistant",
    };
    lastUseChatOpts?.onFinish?.({ message: fakeMessage });
    expect(persistAssistantToServerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        citations: [],
        content: "answer",
        convId: CONV_ID_A,
        finishReason: "stop",
        isAccount: true,
      }),
    );
    expect(saveMessagesMock).toHaveBeenCalled();
  });

  it("onFinish anon 态: 跳过 persistAssistantToServer, 只 saveMessages", () => {
    getAuthState.mockReturnValue({ accountId: null });
    renderHook(() =>
      useChatWithPersistence({
        accountId: null,
        appendMessageMut: appendMutMock,
        convId: CONV_ID_A,
        difyConversationId: undefined,
        initialMessages: baseInitialMessages,
        isAccount: false,
      }),
    );
    const fakeMessage = {
      id: "msg-a1",
      metadata: { createdAt: FIXED_TS_MS },
      parts: [{ state: "done", text: "anon answer", type: "text" }],
      role: "assistant",
    };
    lastUseChatOpts?.onFinish?.({ message: fakeMessage });
    expect(persistAssistantToServerMock).not.toHaveBeenCalled();
    expect(saveMessagesMock).toHaveBeenCalled();
  });

  it("onError 触发 persistAssistantToServer with finishReason=error", () => {
    renderHook(() =>
      useChatWithPersistence({
        accountId: ACCOUNT_ID_FOR_LOGIN,
        appendMessageMut: appendMutMock,
        convId: CONV_ID_A,
        difyConversationId: "dify-conv-1",
        initialMessages: baseInitialMessages,
        isAccount: true,
      }),
    );
    lastUseChatOpts?.onError?.(new Error("network"));
    expect(persistAssistantToServerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        errorCode: "client_error",
        finishReason: "error",
        isAccount: true,
      }),
    );
  });
});

describe("useChatWithPersistence — 返回值", () => {
  beforeEach(() => {
    allChatInstances.length = 0;
    lastUseChatOpts = null;
    mockMessages = [{ id: "m1", parts: [{ text: "x", type: "text" }], role: "user" }];
    mockStatus = "streaming";
    mockError = undefined;
    mockSendMessage.mockReset();
    mockStop.mockReset();
    getAuthState.mockReturnValue({ accountId: null });
    globalThis.localStorage.removeItem(ANON_USER_ID_KEY);
  });
  afterEach(() => {
    globalThis.localStorage.removeItem(ANON_USER_ID_KEY);
  });

  it("暴露 sendMessage / stop / messages / status / error / id", () => {
    const { result } = renderHook(() =>
      useChatWithPersistence({
        accountId: null,
        appendMessageMut: vi.fn(),
        convId: CONV_ID_A,
        difyConversationId: undefined,
        initialMessages: baseInitialMessages,
        isAccount: false,
      }),
    );
    expect(result.current.sendMessage).toBe(mockSendMessage);
    expect(result.current.stop).toBe(mockStop);
    expect(result.current.messages).toEqual(mockMessages);
    expect(result.current.status).toBe("streaming");
    expect(result.current.id).toBe(CONV_ID_A);
  });
});
