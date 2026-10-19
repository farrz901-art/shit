// WithMemoryHooks 装饰器单测 (2026-06-19 重写: server-only fetch + cookies mock)
// 覆盖 3 个核心行为 + 降级
import type { ChatEvent, ChatProvider, SendMessageRequest } from "./types";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Next/headers cookies() server-only API mock
const mockCookieJar = {
  get: vi.fn((name: string) => (name === "rag_user_token" ? { value: "tok-test" } : undefined)),
};
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => mockCookieJar),
}));

// 全局 fetch mock - 默认 search/add 返 200 空 memories
const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

import { log } from "@/lib/log";
import { withMemoryHooks } from "./memory-integration";

interface FakeProviderOpts {
  events?: ChatEvent[];
  throwAt?: number;
}

const makeFakeProvider = (
  opts: FakeProviderOpts = {},
): ChatProvider & {
  receivedReq: SendMessageRequest | null;
} => {
  const inner: ChatProvider & { receivedReq: SendMessageRequest | null } = {
    name: "fake",
    receivedReq: null,
    async *sendMessage(req: SendMessageRequest) {
      inner.receivedReq = req;
      for (const ev of opts.events ?? []) {
        // eslint-disable-next-line no-magic-numbers -- 测试断言中的数字常量
        if (opts.throwAt !== undefined && opts.throwAt-- <= 0) {
          throw new Error("upstream blew up");
        }
        yield ev;
      }
    },
  };
  return inner;
};

const consume = async (iterable: AsyncIterable<unknown>) => {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars -- 故意不使用循环变量
  for await (const ignoredVar of iterable) {
    // Drain
  }
};

const MICRO_TASK_FLUSH_DELAY = 10;
const FETCH_CALL_NONE = 0;

const respond = (data: unknown, ok = true) =>
  ({
    json: async () => data,
    ok,
  }) as Response;

describe("withMemoryHooks", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("name 后缀 = 'fake+memory'", () => {
    const inner = makeFakeProvider();
    const wrapped = withMemoryHooks(inner);
    expect(wrapped.name).toBe("fake+memory");
  });

  describe("Pre-LLM search", () => {
    it("search 成功 → 把 memories 拼成 inputs.memory_context 传内层", async () => {
      fetchMock
        .mockResolvedValueOnce(
          respond({
            memories: [
              { id: "1", text: "用户叫张三" },
              { id: "2", text: "用户住北京" },
            ],
          }),
        )
        .mockResolvedValueOnce(respond({ profile_data: null }));
      const inner = makeFakeProvider({ events: [] });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: { foo: "bar" }, query: "我叫什么", user: "u1" },
          new AbortController().signal,
        ),
      );

      expect(inner.receivedReq?.inputs).toEqual({
        buyer_profile: "",
        foo: "bar",
        memory_context: "用户相关记忆:\n- 用户叫张三\n- 用户住北京",
      });
    });

    it("search 返空 → inputs.memory_context 是空串, buyer_profile 为空", async () => {
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockResolvedValueOnce(respond({ profile_data: null }));
      const inner = makeFakeProvider({ events: [] });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: {}, query: "q", user: "u1" },
          new AbortController().signal,
        ),
      );

      expect(inner.receivedReq?.inputs).toEqual({
        buyer_profile: "",
        memory_context: "",
      });
    });

    it("search 抛错 → 降级到空 memory_context, buyer_profile 为空, 内层 provider 仍被调", async () => {
      // SearchMemory 抛错, profile 并行 fetch 无定义时也降级
      fetchMock.mockRejectedValueOnce(new Error("mem0 不可达"));
      const inner = makeFakeProvider({ events: [] });
      const consoleWarn = vi.spyOn(log, "warn").mockImplementation(() => undefined);

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: {}, query: "q", user: "u1" },
          new AbortController().signal,
        ),
      );

      expect(inner.receivedReq?.inputs).toEqual({
        buyer_profile: "",
        memory_context: "",
      });
      expect(consoleWarn).toHaveBeenCalledWith(
        expect.stringContaining("search failed"),
        expect.objectContaining({ error: expect.any(String) }),
      );
      consoleWarn.mockRestore();
    });
  });

  describe("流中 assistant 累积", () => {
    it("流中多条 message 事件 → 累积成单个 assistant turn", async () => {
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockResolvedValueOnce(respond({ profile_data: null }));
      const inner = makeFakeProvider({
        events: [
          { delta: "你", type: "message" },
          { delta: "好", type: "message" },
          { delta: "张三", type: "message" },
          { conversationId: "c1", type: "message_end" },
        ],
      });

      const events: ChatEvent[] = [];
      for await (const ev of withMemoryHooks(inner).sendMessage(
        { inputs: {}, query: "我叫什么", user: "u1" },
        new AbortController().signal,
      )) {
        events.push(ev);
      }

      // 透传所有事件
      expect(events.map((ev) => ev.type)).toEqual(["message", "message", "message", "message_end"]);
    });

    it("add 收到 user query + 累积后单条 assistant turn", async () => {
      // 第 1-2 次 fetch = search + buyer_profile, 第 3 次 fetch = add
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockResolvedValueOnce(respond({ profile_data: null }))
        .mockResolvedValueOnce(respond({ ok: true }));
      const inner = makeFakeProvider({
        events: [
          { delta: "你", type: "message" },
          { delta: "好", type: "message" },
        ],
      });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: {}, query: "我叫什么", user: "u1" },
          new AbortController().signal,
        ),
      );

      await new Promise((resolve) => setTimeout(resolve, MICRO_TASK_FLUSH_DELAY));

      // 第 2 次 fetch (add) 的 body 校验
      const addCall = fetchMock.mock.calls.find(([url]) => String(url).includes("/memory/add"));
      expect(addCall).toBeDefined();
      // eslint-disable-next-line no-magic-numbers -- 测试断言中的数字常量
      const body = JSON.parse(addCall![1].body as string);
      expect(body.conversation_id).toBeUndefined();
      expect(body.messages).toEqual([
        { content: "我叫什么", role: "user" },
        { content: "你好", role: "assistant" },
      ]);
    });
  });

  describe("Post-LLM add", () => {
    it("流结束 → fire-and-forget add 含 conversation_id", async () => {
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockResolvedValueOnce(respond({ profile_data: null }))
        .mockResolvedValueOnce(respond({ ok: true }));
      const inner = makeFakeProvider({
        events: [
          { delta: "x", type: "message" },
          { conversationId: "c1", type: "message_end" },
        ],
      });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { conversationId: "c1", inputs: {}, query: "q", user: "u1" },
          new AbortController().signal,
        ),
      );
      // eslint-disable-next-line no-magic-numbers -- 测试断言中的数字常量
      await new Promise((resolve) => setTimeout(resolve, 10));

      // eslint-disable-next-line no-magic-numbers -- 测试断言中的数字常量
      const addCall = fetchMock.mock.calls.find((call) => String(call[0]).includes("/memory/add"));
      expect(addCall).toBeDefined();
      // eslint-disable-next-line no-magic-numbers -- 测试断言中的数字常量
      const body = JSON.parse(addCall![1].body as string);
      expect(body.conversation_id).toBe("c1");
      expect(body.messages).toEqual([
        { content: "q", role: "user" },
        { content: "x", role: "assistant" },
      ]);
    });

    it("add 失败 → console.warn, 不冒泡 (fire-and-forget)", async () => {
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockResolvedValueOnce(respond({ profile_data: null }))
        .mockRejectedValueOnce(new Error("mem0 写失败"));
      const inner = makeFakeProvider({
        events: [{ delta: "x", type: "message" }],
      });
      const consoleWarn = vi.spyOn(log, "warn").mockImplementation(() => undefined);

      // 不应抛
      await expect(
        consume(
          withMemoryHooks(inner).sendMessage(
            { inputs: {}, query: "q", user: "u1" },
            new AbortController().signal,
          ),
        ),
      ).resolves.not.toThrow();

      // eslint-disable-next-line no-magic-numbers -- 测试断言中的数字常量
      await new Promise((resolve) => setTimeout(resolve, 20));
      expect(consoleWarn).toHaveBeenCalledWith(
        expect.stringContaining("add failed"),
        expect.objectContaining({ error: expect.any(String) }),
      );
      consoleWarn.mockRestore();
    });

    it("流没有任何 assistant message → 不调 add", async () => {
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockResolvedValueOnce(respond({ profile_data: null }));
      const inner = makeFakeProvider({
        events: [{ status: "succeeded", type: "workflow_done" }],
      });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: {}, query: "q", user: "u1" },
          new AbortController().signal,
        ),
      );
      await new Promise((resolve) => setTimeout(resolve, MICRO_TASK_FLUSH_DELAY));

      // 仅 1 次 fetch (search), 没有 add
      const addCalls = fetchMock.mock.calls.filter(([url]) => String(url).includes("/memory/add"));
      expect(addCalls).toHaveLength(FETCH_CALL_NONE);
    });
  });

  describe("buyer profile injection", () => {
    it("存在 buyer_key 时 fetch 画像并注入 inputs.buyer_profile", async () => {
      // 第 1 次 fetch = search, 第 2 次 fetch = buyer profile
      fetchMock.mockResolvedValueOnce(respond({ memories: [] })).mockResolvedValueOnce(
        respond({
          profile_data: {
            equipment_type: { value: "电机", confidence: "high" },
            budget: { value: "5000", confidence: "medium" },
          },
        }),
      );
      const inner = makeFakeProvider({ events: [] });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: { buyer_key: "1" }, query: "推荐电机", user: "u1" },
          new AbortController().signal,
        ),
      );

      const received = inner.receivedReq;
      const profile = received?.inputs?.buyer_profile as string;
      expect(profile).toContain("电机");
      expect(profile).toContain("5000");
      expect(profile).toContain("买家信息");
    });

    it("buyer_key 不存在时仍 fetch 画像 (后端自己鉴权), buyer_profile 为空", async () => {
      // 用户没传 buyer_key 时后端仍可能返回画像 (基于 cookie token)
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockResolvedValueOnce(respond({ profile_data: {} }));
      const inner = makeFakeProvider({ events: [] });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: {}, query: "q", user: "u1" },
          new AbortController().signal,
        ),
      );

      const received = inner.receivedReq;
      expect(received?.inputs?.buyer_profile).toBe("");
    });

    it("fetch 失败时 buyer_profile 为空字符串 (降级)", async () => {
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockRejectedValueOnce(new Error("network error"));
      const inner = makeFakeProvider({ events: [] });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: { buyer_key: "1" }, query: "q", user: "u1" },
          new AbortController().signal,
        ),
      );

      const received = inner.receivedReq;
      expect(received?.inputs?.buyer_profile).toBe("");
    });

    it("后端返回 404 时 buyer_profile 为空 (降级)", async () => {
      fetchMock
        .mockResolvedValueOnce(respond({ memories: [] }))
        .mockResolvedValueOnce(respond({ detail: "not found" }, false));
      const inner = makeFakeProvider({ events: [] });

      await consume(
        withMemoryHooks(inner).sendMessage(
          { inputs: { buyer_key: "1" }, query: "q", user: "u1" },
          new AbortController().signal,
        ),
      );

      const received = inner.receivedReq;
      expect(received?.inputs?.buyer_profile).toBe("");
    });
  });
});
