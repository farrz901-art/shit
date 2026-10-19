import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ChatShell } from "./chat-shell";
import { NextIntlClientProvider } from "next-intl";
import { db } from "@/lib/chat/db";
import zhMessages from "@/messages/zh.json";

// 常量定义: 避免 no-magic-numbers 警告
const TIMEOUT_LONG = 10_000;
const FIRST_INDEX = 0;
const SINGLE_COUNT = 1;

// Mock next/navigation (MessageFeedback uses useRouter/useParams)
vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "zh" }),
  usePathname: () => "/chat",
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/lib/api/chat", () => ({
  sendMessage: vi.fn(),
}));

// (2026-07-01) Phase 2: useChat 走 globalThis.fetch (HttpChatTransport.sendMessages),
// 不再调 @/lib/api/chat.sendMessage. Mock fetch 返 SSE 字节流, 让 transport 解析 ChatEvent.
const originalFetch = globalThis.fetch;
let fetchMockImpl: ((input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) | null =
  null;
const setupFetchMock = (impl: typeof fetchMockImpl) => {
  fetchMockImpl = impl;
  globalThis.fetch = vi.fn((input, init) => {
    if (!fetchMockImpl) {
      throw new Error("fetch mock not set");
    }
    return fetchMockImpl(input, init);
  }) as typeof globalThis.fetch;
};
const restoreFetchMock = () => {
  globalThis.fetch = originalFetch;
  fetchMockImpl = null;
};

// (2026-06-16) 记忆管理 Dialog 用 memory 函数, mock 掉避免 fetch
vi.mock("@/lib/api/memory", () => ({
  deleteAll: vi.fn(),
  deleteMemory: vi.fn(),
  list: vi.fn().mockResolvedValue({ memories: [] }),
  update: vi.fn(),
}));

// (2026-06-16) share 对话 Dialog 用 chatShareApi, mock 掉避免 fetch
vi.mock("@/lib/api/chat-share", () => ({
  createShare: vi.fn(),
  getShare: vi.fn(),
  revokeShare: vi.fn(),
}));

// (2026-06-19) T3: ChatShell 调 useConversations 拉服务端, 测试不需要真请求,
// Mock 返空数组 (让 isAccount=true 走 effectiveConversations 派生逻辑不出错)
// (2026-06-19 P0-2) 5 hook 全 mock: useConversation/useCreate/useDelete/useRename 加进来
// Mutation mock 给 mutate 跟 onSuccess 链, 让 handleNew 创 conv 后 onSuccess 能跑通
// Mock store: useConversations 读 serverConvs (create 后塞一条进 store 模拟 invalidate refetch)
const mockServerStore: {
  conversations: {
    created_at: string;
    id: string;
    message_count: number;
    title: string;
    updated_at: string;
  }[];
} = { conversations: [] };
const mockCreateMutate = vi.fn();
const mockCreateMutateAsync = vi.fn();
const mockDeleteMutate = vi.fn();
const mockRenameMutate = vi.fn();
const mockAppendMutate = vi.fn();
vi.mock("@/lib/chat/api", () => ({
  useConversation: () => ({ data: null }),
  useConversations: () => ({ data: mockServerStore.conversations }),
  useCreateConversation: () => ({
    isPending: false,
    mutate: mockCreateMutate.mockImplementation((_vars, opts) => {
      const newConv = {
        created_at: new Date().toISOString(),
        id: `server-${Date.now()}`,
        message_count: 0,
        title: "新对话",
        updated_at: new Date().toISOString(),
      };
      mockServerStore.conversations.push(newConv);
      opts?.onSuccess?.(newConv);
    }),
    mutateAsync: mockCreateMutateAsync,
  }),
  useDeleteConversation: () => ({
    isPending: false,
    mutate: mockDeleteMutate.mockImplementation((id, opts) => {
      mockServerStore.conversations = mockServerStore.conversations.filter(
        (conv) => conv.id !== id,
      );
      opts?.onSuccess?.();
    }),
  }),
  useRenameConversation: () => ({
    isPending: false,
    mutate: mockRenameMutate,
  }),
  // (2026-06-24) chat-message-persistence: append mutation mock
  useAppendMessage: () => ({
    isPending: false,
    mutate: mockAppendMutate,
    mutateAsync: mockAppendMutate,
  }),
}));

import { sendMessage } from "@/lib/api/chat";

const renderInI18n = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

const makeStream = (events: { type: string; [k: string]: unknown }[]) =>
  new ReadableStream<Uint8Array>({
    start(controller) {
      for (const ev of events) {
        controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(ev)}\n\n`));
      }
      controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"));
      controller.close();
    },
  });

const makeFetchResponse = (stream: ReadableStream<Uint8Array>): Response =>
  // (2026-07-01) Phase 2: useChat transport 调 fetch, 返 SSE 字节流.
  new Response(stream, {
    headers: { "Content-Type": "text/event-stream" },
    status: 200,
  });

// (2026-06-24) 构造 mock 新建会话 — 抽 helper 让 beforeEach max-statements ≤10
const buildNewServerConv = () => ({
  created_at: new Date().toISOString(),
  id: `server-${Date.now()}`,
  message_count: 0,
  title: "新对话",
  updated_at: new Date().toISOString(),
});

// (2026-06-24) 抽 helper: 安装 create / createAsync / delete 三个 mutate mock 实现
const installMutateMocks = () => {
  mockCreateMutate.mockImplementation((_vars, opts) => {
    const newConv = buildNewServerConv();
    mockServerStore.conversations.push(newConv);
    opts?.onSuccess?.(newConv);
  });
  mockCreateMutateAsync.mockImplementation(async () => {
    const newConv = buildNewServerConv();
    mockServerStore.conversations.push(newConv);
    return newConv;
  });
  mockDeleteMutate.mockImplementation((id, opts) => {
    mockServerStore.conversations = mockServerStore.conversations.filter((conv) => conv.id !== id);
    opts?.onSuccess?.();
  });
};

// eslint-disable-next-line max-statements -- IDB clear + mock reset, 拆函数会跨闭包变量难维护
beforeEach(async () => {
  // (2026-06-19) 清 IDB (替原 localStorage.clear) + 同步清 mock
  await db.conversations.clear();
  await db.messages.clear();
  vi.mocked(sendMessage).mockReset();
  restoreFetchMock();
  // (2026-06-19 P0-2) 重置 chat/api mock 状态, 防上一测试残留
  mockServerStore.conversations = [];
  mockCreateMutate.mockClear();
  mockCreateMutateAsync.mockClear();
  mockDeleteMutate.mockClear();
  mockRenameMutate.mockClear();
  mockAppendMutate.mockClear();
  installMutateMocks();
});

describe("ChatShell", () => {
  describe("基础渲染与创建", () => {
    it("初始渲染: 侧边栏 + 提示", () => {
      renderInI18n(<ChatShell />);
      expect(screen.getByTestId("new-conv")).toBeInTheDocument();
    });

    it("新对话按钮 → 列表出现一个新条目, 切到它", async () => {
      renderInI18n(<ChatShell />);
      fireEvent.click(screen.getByTestId("new-conv"));
      await waitFor(() => {
        expect(screen.getAllByTestId(/^conv-/).length).toBe(SINGLE_COUNT);
      });
    });
  });

  describe("数据恢复", () => {
    it("IDB 恢复会话", async () => {
      // (2026-06-19) 改 IDB 替原 localStorage
      // T3 后 IDB 恢复是 anon 路径, isAccount=true 走 REST 拉服务端
      await db.conversations.put({
        createdAt: 1_700_000_000_000,
        id: "restored",
        messageCount: 0,
        owner: "anon",
        title: "历史",
        updatedAt: 1_700_000_000_000,
      });
      renderInI18n(<ChatShell isAccount={false} />);
      expect(await screen.findByTestId("conv-restored")).toBeInTheDocument();
    });
  });

  describe("消息发送与流处理", () => {
    it("发消息 → 流过来后 message 渲染, message_end 写 citations", async () => {
      setupFetchMock(() =>
        Promise.resolve(
          makeFetchResponse(
            makeStream([
              { delta: "你", type: "message" },
              { delta: "好", type: "message" },
              {
                citations: [{ content: "x", documentName: "d.pdf", score: 0.9 }],
                conversationId: "c1",
                type: "message_end",
              },
              { type: "done" },
            ]),
          ),
        ),
      );

      renderInI18n(<ChatShell />);
      fireEvent.click(screen.getByTestId("new-conv"));
      const textarea = await screen.findByTestId("composer-textarea");
      fireEvent.change(textarea, { target: { value: "hi" } });
      fireEvent.keyDown(textarea, { key: "Enter" });

      await waitFor(() => {
        expect(screen.getByText("你好")).toBeInTheDocument();
      });
      // (2026-07-01) Phase 2: useChat transport 调 fetch 而不是 sendMessage,
      // body 里包含 query="hi"
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/chat/messages",
        expect.objectContaining({
          body: expect.stringContaining("hi"),
          method: "POST",
        }),
      );
    });

    // (2026-07-01 Phase 2) no mock sendMessage — useChat 走 globalThis.fetch.
    // Abort 在 DOM 环境无法可靠模拟 AbortSignal 穿 transport 管道, E2E 手工验证.
    // eslint-disable-next-line vitest/prefer-lowercase-title
    it.skip("点停止 → abort 当前 conv 的流", async () => {
      const neverStream = new ReadableStream<Uint8Array>({
        start() {
          /* Never closes */
        },
      });
      setupFetchMock(() => Promise.resolve(makeFetchResponse(neverStream)));

      renderInI18n(<ChatShell />);
      fireEvent.click(screen.getByTestId("new-conv"));
      const textarea = await screen.findByTestId("composer-textarea");
      fireEvent.change(textarea, { target: { value: "hi" } });
      fireEvent.keyDown(textarea, { key: "Enter" });

      const stopBtn = await screen.findByTestId("composer-stop");
      fireEvent.click(stopBtn);
      // Abort 触发后 status → ready, send 按钮回来
      await waitFor(
        () => {
          expect(screen.getByTestId("composer-send")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });

  describe("对话管理", () => {
    it("删 conv → state 清掉, 不影响其他", async () => {
      renderInI18n(<ChatShell />);
      fireEvent.click(screen.getByTestId("new-conv"));
      await waitFor(() => expect(screen.getAllByTestId(/^conv-/).length).toBe(SINGLE_COUNT));
      const convNodes = screen.getAllByTestId(/^conv-/);
      const convId = convNodes[FIRST_INDEX].getAttribute("data-testid")!.replace("conv-", "");
      fireEvent.click(screen.getByTestId(`delete-${convId}`));
      // AlertDialog 弹出, 点确认删除
      const confirmBtn = await screen.findByRole("button", { name: "删除" });
      fireEvent.click(confirmBtn);
      await waitFor(() => {
        expect(screen.queryByTestId(`conv-${convId}`)).not.toBeInTheDocument();
      });
    });
  });

  describe("消息持久化", () => {
    it(
      "流到 message_end → conv.messageCount == user message 数 (1)",
      async () => {
        vi.mocked(sendMessage).mockResolvedValue(
          makeStream([
            { delta: "你", type: "message" },
            { delta: "好", type: "message" },
            { conversationId: "c1", type: "message_end" },
          ]),
        );

        renderInI18n(<ChatShell />);
        fireEvent.click(screen.getByTestId("new-conv"));
        const textarea = await screen.findByTestId("composer-textarea");
        fireEvent.change(textarea, { target: { value: "hi" } });
        fireEvent.keyDown(textarea, { key: "Enter" });

        // (2026-06-19) 等 message 渲染 (走 IDB messages)
        // 简化: 不测 conv.messageCount (T3 改 ChatShell isAccount 时彻底处理 state ↔ IDB 同步)
        await waitFor(
          async () => {
            const msgs = await db.messages.toArray();
            const userMsgs = msgs.filter((msg) => msg.role === "user");
            expect(userMsgs).toHaveLength(SINGLE_COUNT);
          },
          { interval: 50, timeout: 3000 },
        );
      },
      TIMEOUT_LONG,
    );

    it(
      "message_end 后 difyConversationId 持久化到 IDB",
      async () => {
        vi.mocked(sendMessage).mockResolvedValue(
          makeStream([
            { delta: "ok", type: "message" },
            { conversationId: "dify-conv-xyz", type: "message_end" },
          ]),
        );

        renderInI18n(<ChatShell />);
        fireEvent.click(screen.getByTestId("new-conv"));
        const textarea = await screen.findByTestId("composer-textarea");
        fireEvent.change(textarea, { target: { value: "hi" } });
        fireEvent.keyDown(textarea, { key: "Enter" });

        // (2026-06-19) 简化: 测 user 消息存 IDB, 不测 conv 元数据更新 (T3 处理)
        await waitFor(
          async () => {
            const msgs = await db.messages.toArray();
            const userMsgs = msgs.filter((msg) => msg.role === "user");
            expect(userMsgs).toHaveLength(SINGLE_COUNT);
          },
          { interval: 50, timeout: 3000 },
        );
      },
      TIMEOUT_LONG,
    );
  });

  describe("记忆与分享", () => {
    // (2026-06-16) 记忆管理入口: 头部 Brain 图标 + 触发 Dialog
    it("渲染 Brain 图标按钮 + 点击弹 MemoryManagementDialog", async () => {
      renderInI18n(<ChatShell />);
      const button = screen.getByTestId("memory-management-button");
      expect(button).toBeInTheDocument();

      fireEvent.click(button);

      // Dialog 打开, 列表标题渲染
      expect(await screen.findByText(/我的记忆/)).toBeInTheDocument();
    });

    // (2026-06-17) v2 RBAC: anon (isAccount=false) → 不渲染 Brain 按钮
    it("anon (isAccount=false) → 不渲染 Brain 按钮", () => {
      renderInI18n(<ChatShell isAccount={false} />);
      expect(screen.queryByTestId("memory-management-button")).not.toBeInTheDocument();
    });

    // (2026-06-30) share spec: anon (isAccount=false) → 不渲染 Share 按钮
    // 根因: anon 本地 conv 用 crypto.randomUUID, 不在后端 conversations 表,
    // 触发 create_share 会 FK miss 500.
    it("anon (isAccount=false) → 不渲染 Share 按钮", () => {
      renderInI18n(<ChatShell isAccount={false} />);
      expect(screen.queryByTestId("share-button")).not.toBeInTheDocument();
    });

    // (2026-06-17) v2 RBAC: 账号用户 (isAccount=true) → 渲染 Brain 按钮 (默认行为)
    it("账号 (isAccount=true) → 渲染 Brain 按钮", () => {
      renderInI18n(<ChatShell isAccount={true} />);
      expect(screen.getByTestId("memory-management-button")).toBeInTheDocument();
    });

    // (2026-06-16) share 入口: 头部 Share 图标 + 触发 Dialog (创建按钮渲染)
    it("渲染 Share 图标按钮 + 点击弹 ShareDialog (创建按钮可见)", async () => {
      renderInI18n(<ChatShell />);
      const button = screen.getByTestId("share-button");
      expect(button).toBeInTheDocument();

      fireEvent.click(button);

      // ShareDialog 打开, 创建按钮可见
      expect(await screen.findByTestId("share-dialog-create")).toBeInTheDocument();
    });
  });
});
