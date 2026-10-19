// BFF /api/chat/messages 路由测试 (2026-06-09)
// 关键: 鉴权 (x-chat-token) + body 校验 (zod) + provider 流透传 + SSE 头 + 错误降级
// 错误路径: provider 抛错必须 yield error 事件 + [DONE], 不能让流崩
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatEvent } from "@/lib/chat/types";
import type { NextRequest } from "next/server";
import { POST as handlePost } from "./route";
import { resetRateLimiter } from "@/lib/rate-limiter";

vi.mock("@/lib/chat/factory", () => ({
  getChatProvider: vi.fn(),
}));

import { getChatProvider } from "@/lib/chat/factory";

/* ---- 常量 ---- */
const NOT_FOUND = -1;
const SSE_SEPARATOR_LENGTH = 2;
const SSE_BLOCK_START = 0;
const DATA_PREFIX = "data: ";
const STATUS_UNAUTHORIZED = 401;
const STATUS_BAD_REQUEST = 400;
const STATUS_TOO_MANY = 429;
const STATUS_OK = 200;
const FIRST_EVENT_INDEX = 0;
// 跟 route.ts 保持一致: 20 次/分/IP
const RATE_LIMIT_MAX = 20;
const INCREMENT_STEP = 1;

/* ---- helper: 解析单个 SSE 块 ---- */
const parseSSEBlock = (block: string): ChatEvent | null => {
  const dataLine = block.split("\n").find((line) => line.startsWith(DATA_PREFIX));
  if (!dataLine) {
    return null;
  }
  const json = dataLine.slice(DATA_PREFIX.length);
  if (json === "[DONE]") {
    return null;
  }
  return JSON.parse(json) as ChatEvent;
};

/* ---- helper: 从完整文本中提取所有事件 ---- */
const parseSSEBlocks = (text: string): ChatEvent[] => {
  const out: ChatEvent[] = [],
    SSE_SEPARATOR = "\n\n";
  let remaining = text,
    idx = -1;
  while ((idx = remaining.indexOf(SSE_SEPARATOR)) !== NOT_FOUND) {
    const block = remaining.slice(SSE_BLOCK_START, idx);
    remaining = remaining.slice(idx + SSE_SEPARATOR_LENGTH);
    const event = parseSSEBlock(block);
    if (event) {
      out.push(event);
    }
  }
  return out;
};

/* ---- helper: 读取 Response body 全部字节 ---- */
const readBodyAsText = async (res: Response): Promise<string> => {
  const reader = res.body!.getReader(),
    decoder = new TextDecoder();
  const chunks: Uint8Array[] = [];
  while (true) {
    const { value, done: isDone } = await reader.read();
    if (isDone) {
      break;
    }
    if (value) {
      chunks.push(value);
    }
  }
  return decoder.decode(Buffer.concat(chunks));
};

/* ---- 解析 SSE 流 ---- */
const parseSSE = async (body: ReadableStream<Uint8Array>): Promise<ChatEvent[]> => {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buf += decoder.decode(value, { stream: true });
  }
  return parseSSEBlocks(buf);
};

/* ---- mock provider: happy path ---- */
const happyPathMock = async function* happyPathMock(): AsyncIterable<ChatEvent> {
  yield { delta: "你", type: "message" };
  yield { delta: "好", type: "message" };
  yield { citations: [], conversationId: "c1", type: "message_end" };
  yield { type: "done" };
};

/* ---- mock provider: error 事件 ---- */
const errorEventMock = async function* errorEventMock(): AsyncIterable<ChatEvent> {
  yield { code: "provider_quota_exceeded", message: "quota", type: "error" };
  yield { type: "done" };
};

/* ---- mock provider: 抛出异常 ---- */
// oxlint-disable-next-line require-yield
const throwingMock = async function* throwingMock(): AsyncIterable<ChatEvent> {
  throw new Error("Dify 502");
};

/* ---- helper: 构造 POST 请求 ---- */
const makeChatRequest = (): Request =>
  new Request("http://localhost/api/chat/messages", {
    body: JSON.stringify({ inputs: {}, query: "q", user: "u" }),
    headers: {
      "Content-Type": "application/json",
      "x-chat-token": "secret-123",
    },
    method: "POST",
  });

describe("/api/chat/messages", () => {
  beforeEach(() => {
    process.env.CHAT_PUBLIC_TOKEN = "secret-123";
    vi.mocked(getChatProvider).mockReset();
  });
  afterEach(() => {
    vi.restoreAllMocks();
    resetRateLimiter();
  });

  it("缺 x-chat-token 头返 401", async () => {
    const req = new Request("http://localhost/api/chat/messages", {
      body: JSON.stringify({ inputs: {}, query: "q", user: "u" }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
    const res = await handlePost(req as unknown as NextRequest);
    expect(res.status).toBe(STATUS_UNAUTHORIZED);
  });

  it("x-chat-token 错返 401", async () => {
    const req = new Request("http://localhost/api/chat/messages", {
      body: JSON.stringify({ inputs: {}, query: "q", user: "u" }),
      headers: {
        "Content-Type": "application/json",
        "x-chat-token": "wrong",
      },
      method: "POST",
    });
    const res = await handlePost(req as unknown as NextRequest);
    expect(res.status).toBe(STATUS_UNAUTHORIZED);
  });

  it("缺 query 返 400", async () => {
    const req = new Request("http://localhost/api/chat/messages", {
      body: JSON.stringify({ inputs: {}, user: "u" }),
      headers: {
        "Content-Type": "application/json",
        "x-chat-token": "secret-123",
      },
      method: "POST",
    });
    const res = await handlePost(req as unknown as NextRequest);
    expect(res.status).toBe(STATUS_BAD_REQUEST);
  });

  it("happy path: 鉴权 + provider 流透传 + SSE 头正确", async () => {
    vi.mocked(getChatProvider).mockReturnValue({
      name: "mock",
      sendMessage: happyPathMock,
    });

    const req = new Request("http://localhost/api/chat/messages", {
      body: JSON.stringify({ inputs: {}, query: "1LE 电机?", user: "user-1" }),
      headers: {
        "Content-Type": "application/json",
        "x-chat-token": "secret-123",
      },
      method: "POST",
    });
    const res = await handlePost(req as unknown as NextRequest);
    expect(res.status).toBe(STATUS_OK);
    expect(res.headers.get("Content-Type")).toBe("text/event-stream");
    expect(res.headers.get("Cache-Control")).toBe("no-cache, no-transform");
    const events = await parseSSE(res.body!);
    expect(events).toEqual([
      { delta: "你", type: "message" },
      { delta: "好", type: "message" },
      { citations: [], conversationId: "c1", type: "message_end" },
      { type: "done" },
    ]);
  });

  it("超出限流阈值返 429", async () => {
    vi.mocked(getChatProvider).mockReturnValue({
      name: "mock",
      sendMessage: happyPathMock,
    });

    // 前 RATE_LIMIT_MAX 次请求必须成功
    for (let idx = 0; idx < RATE_LIMIT_MAX; idx += INCREMENT_STEP) {
      const res = await handlePost(makeChatRequest() as unknown as NextRequest);
      expect(res.status).toBe(STATUS_OK);
    }

    // 第 RATE_LIMIT_MAX + 1 次应该被限流
    const lastRes = await handlePost(makeChatRequest() as unknown as NextRequest);
    expect(lastRes.status).toBe(STATUS_TOO_MANY);
    const body = (await lastRes.json()) as Record<string, unknown>;
    expect(body).toHaveProperty("remaining");
  });

  it("error 事件透传, 不会让流崩", async () => {
    vi.mocked(getChatProvider).mockReturnValue({
      name: "mock",
      sendMessage: errorEventMock,
    });
    const req = new Request("http://localhost/api/chat/messages", {
      body: JSON.stringify({ inputs: {}, query: "q", user: "u" }),
      headers: {
        "Content-Type": "application/json",
        "x-chat-token": "secret-123",
      },
      method: "POST",
    });
    const res = await handlePost(req as unknown as NextRequest);
    const events = await parseSSE(res.body!);
    expect(events[FIRST_EVENT_INDEX]).toEqual({
      code: "provider_quota_exceeded",
      message: "quota",
      type: "error",
    });
  });

  it("provider 抛错 → 流里 yield error 事件 + [DONE]", async () => {
    vi.mocked(getChatProvider).mockReturnValue({
      name: "mock",
      sendMessage: throwingMock,
    });
    const req = new Request("http://localhost/api/chat/messages", {
      body: JSON.stringify({ inputs: {}, query: "q", user: "u" }),
      headers: {
        "Content-Type": "application/json",
        "x-chat-token": "secret-123",
      },
      method: "POST",
    });
    const res = await handlePost(req as unknown as NextRequest);
    expect(res.status).toBe(STATUS_OK);
    const text = await readBodyAsText(res);
    expect(text).toContain('"code":"upstream_error"');
    expect(text).toContain("[DONE]");
  });
});
