// OpenAIChatProvider 单测
// 覆盖: 构造函数 + sendMessage 流式解析 (SSE 块)
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OpenAIChatProvider } from "./openai";

const HTTP_UNAUTHORIZED = 401;
const FIRST_IDX = 0;
const MIN_EVENT_COUNT = 2;
const SINGLE_EVENT_COUNT = 1;
const LAST_OFFSET = 1;

// Mock apiProxy before module import
const apiProxyMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/config", () => ({ apiProxy: apiProxyMock }));

// 构造一个 SSE 流: 返回 ReadableStream, 在 reader.read() 逐步返回块
const makeStream = (chunks: string[]): ReadableStream<Uint8Array> => {
  const encoder = new TextEncoder();
  let idx = 0;
  return new ReadableStream({
    pull(controller) {
      if (idx < chunks.length) {
        controller.enqueue(encoder.encode(chunks[idx]));
        idx++;
      } else {
        controller.close();
      }
    },
  });
};

// 从 Response.body 构建 mock Response
const streamResponse = (body: ReadableStream): Response =>
  ({ body, ok: true, status: 200, text: async () => "" }) as unknown as Response;

const errorResponse = (status: number): Response =>
  ({ ok: false, status, text: async () => `HTTP ${status}` }) as unknown as Response;

// 收集 async generator 所有事件
const collectEvents = async (
  provider: OpenAIChatProvider,
  query: string,
  signal: AbortSignal,
): Promise<unknown[]> => {
  const events: unknown[] = [];
  for await (const ev of provider.sendMessage({ query, inputs: {}, user: "u" }, signal)) {
    events.push(ev);
  }
  return events;
};

// 构造 OpenAI provider（先 resetModules + 设 env + 动态 import）
const createProvider = async (apiKey: string): Promise<OpenAIChatProvider> => {
  vi.resetModules();
  process.env.OPENAI_API_KEY = apiKey;
  const { OpenAIChatProvider: Provider } = await import("./openai");
  return new Provider();
};

describe("OpenAIChatProvider", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("name = 'openai'", async () => {
    const provider = await createProvider("sk-test");
    expect(provider.name).toBe("openai");
  });

  it("sendMessage: API_KEY 未设时 yield error", async () => {
    const provider = await createProvider("");
    const events = await collectEvents(provider, "hi", new AbortController().signal);
    expect(events).toHaveLength(SINGLE_EVENT_COUNT);
    expect(events[FIRST_IDX]).toMatchObject({ type: "error", code: "config_error" });
  });

  it("sendMessage: 正常流 → message_end", async () => {
    const provider = await createProvider("sk-test");
    const stream = makeStream([
      'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n',
      "data: [DONE]\n\n",
    ]);
    apiProxyMock.mockResolvedValue(streamResponse(stream));
    const events = await collectEvents(provider, "hi", new AbortController().signal);
    const lastIdx = events.length - LAST_OFFSET;
    expect(events.length).toBeGreaterThanOrEqual(MIN_EVENT_COUNT);
    expect(events[FIRST_IDX]).toMatchObject({ type: "message", delta: "你好" });
    expect(events[lastIdx]).toMatchObject({ type: "message_end" });
  });

  it("sendMessage: reasoning_content 累积后输出 thinking 事件", async () => {
    const provider = await createProvider("sk-test");
    const stream = makeStream([
      'data: {"choices":[{"delta":{"reasoning_content":"思考中..."}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"最终答案"}}]}\n\n',
      "data: [DONE]\n\n",
    ]);
    apiProxyMock.mockResolvedValue(streamResponse(stream));
    const events = await collectEvents(provider, "hi", new AbortController().signal);
    const thinkingEvents = events.filter((ev: any) => ev.type === "thinking");
    expect(thinkingEvents.length).toBeGreaterThanOrEqual(SINGLE_EVENT_COUNT);
    expect(thinkingEvents[FIRST_IDX]).toMatchObject({ detail: "思考中...", node: "reasoning" });
  });

  it("sendMessage: HTTP 非 200 时 yield http_ error", async () => {
    const provider = await createProvider("sk-test");
    apiProxyMock.mockResolvedValue(errorResponse(HTTP_UNAUTHORIZED));
    const events = await collectEvents(provider, "hi", new AbortController().signal);
    expect(events[FIRST_IDX]).toMatchObject({ type: "error", code: "http_401" });
  });
});
