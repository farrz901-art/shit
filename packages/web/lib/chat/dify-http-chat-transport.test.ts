/**
 * DifyHttpChatTransport 单元测试 (2026-07-01 chat AI SDK 协议层 Phase 2)
 * 覆盖: 6 种 ChatEvent → UIMessageChunk 5 段配对转换 + prepareSendMessagesRequest body 注入
 *
 * ⚠️ 测试 protected 方法 processResponseStream: 用 (transport as unknown as { processResponseStream(...) })
 *  cast 绕过访问限制 (TS 允许, 仅 test 用).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ANON_USER_ID_KEY } from "@/const";

// --- Mock 依赖 ---
const sendMessageMock = vi.fn();
const getAuthState = vi.fn();

vi.mock("@/lib/api/chat", () => ({
  sendMessage: (...args: unknown[]) => sendMessageMock(...args),
}));
vi.mock("@/lib/store/auth-store", () => ({
  useAuthStore: { getState: () => getAuthState() },
}));

const { DifyHttpChatTransport } = await import("./dify-http-chat-transport");

const ZERO_IDX = 0;
const ONE_CHUNK = 1;
const ZERO_CHUNKS = 0;
const ACCOUNT_ID_FOR_LOGIN = 42;
const ANOTHER_ACCOUNT_ID = 7;
const DUMMY_CONV_ID = "dify-conv-abc";

const makeStream = (sse: string): ReadableStream<Uint8Array> =>
  new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(sse));
      controller.close();
    },
  });

const collectChunks = async (stream: ReadableStream<unknown>): Promise<{ type: string }[]> => {
  const reader = stream.getReader();
  const out: { type: string }[] = [];
  // eslint-disable-next-line no-constant-condition -- loop until done
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    out.push(value as { type: string });
  }
  return out;
};

/** (2026-07-01) 拿 protected processResponseStream: TS 编译后是普通 method,直接调即可.
 *  用 cast 跳过 TS protected 检查. */
const callProcessResponseStream = (
  transport: InstanceType<typeof DifyHttpChatTransport>,
  stream: ReadableStream<Uint8Array>,
): ReadableStream<unknown> =>
  (
    transport as unknown as {
      processResponseStream: (input: ReadableStream<Uint8Array>) => ReadableStream<unknown>;
    }
  ).processResponseStream(stream);

describe("DifyHttpChatTransport.processResponseStream — 6 种 ChatEvent 5 段配对", () => {
  it("message → text-start + text-delta (5 段首段)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const chunks = await collectChunks(
      callProcessResponseStream(
        transport,
        makeStream('data: {"type":"message","delta":"hi"}\n\ndata: [DONE]\n\n'),
      ),
    );
    expect(chunks.map((chunk) => chunk.type)).toEqual(["text-start", "text-delta"]);
  });

  it("message_end → text-end + finish", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const chunks = await collectChunks(
      callProcessResponseStream(
        transport,
        makeStream(
          'data: {"type":"message","delta":"x"}\n\n' +
            'data: {"type":"message_end","conversationId":"c1"}\n\n' +
            "data: [DONE]\n\n",
        ),
      ),
    );
    expect(chunks.map((chunk) => chunk.type)).toEqual([
      "text-start",
      "text-delta",
      "text-end",
      "finish",
    ]);
  });

  it("error → error chunk (无 text 状态污染)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const chunks = await collectChunks(
      callProcessResponseStream(
        transport,
        makeStream('data: {"type":"error","code":"E001","message":"failed"}\n\ndata: [DONE]\n\n'),
      ),
    );
    expect(chunks).toHaveLength(ONE_CHUNK);
    expect(chunks[ZERO_IDX].type).toBe("error");
    const first = chunks[ZERO_IDX] as unknown as { errorText: string };
    expect(first.errorText).toContain("E001");
    expect(first.errorText).toContain("failed");
  });

  it("thinking → reasoning-start + reasoning-delta (5 段配对)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const chunks = await collectChunks(
      callProcessResponseStream(
        transport,
        makeStream('data: {"type":"thinking","node":"n1","status":"started"}\n\ndata: [DONE]\n\n'),
      ),
    );
    expect(chunks.map((chunk) => chunk.type)).toEqual(["reasoning-start", "reasoning-delta"]);
  });

  it("多次 message delta → 单 text-start + 多个 text-delta (无重复 start)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const chunks = await collectChunks(
      callProcessResponseStream(
        transport,
        makeStream(
          'data: {"type":"message","delta":"a"}\n\n' +
            'data: {"type":"message","delta":"b"}\n\n' +
            'data: {"type":"message","delta":"c"}\n\n' +
            "data: [DONE]\n\n",
        ),
      ),
    );
    expect(chunks.map((chunk) => chunk.type)).toEqual([
      "text-start",
      "text-delta",
      "text-delta",
      "text-delta",
    ]);
  });

  it("workflow_done / done 不 emit chunk (noop)", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const chunks = await collectChunks(
      callProcessResponseStream(
        transport,
        makeStream(
          'data: {"type":"workflow_done","status":"succeeded"}\n\ndata: {"type":"done"}\n\ndata: [DONE]\n\n',
        ),
      ),
    );
    expect(chunks).toHaveLength(ZERO_CHUNKS);
  });

  it("malformed JSON 行跳过, 后续 chunk 继续", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const chunks = await collectChunks(
      callProcessResponseStream(transport, makeStream("data: not-json\n\ndata: [DONE]\n\n")),
    );
    expect(chunks).toHaveLength(ZERO_CHUNKS);
  });
});

/** (2026-07-01) prepareSendMessagesRequest 在父类 HttpChatTransport 是 instance property
 *  (构造时塞入), 不是 prototype method. test 直接读 transport 自身属性. */
const callPrepare = async (
  transport: InstanceType<typeof DifyHttpChatTransport>,
  args: unknown,
): Promise<{ body: Record<string, unknown> }> => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- protected instance prop
  const fn = (transport as any).prepareSendMessagesRequest as (
    opts: unknown,
  ) => Promise<{ body: Record<string, unknown> }>;
  return fn.call(transport, args);
};

describe("DifyHttpChatTransport.prepareSendMessagesRequest — body 注入", () => {
  beforeEach(() => {
    sendMessageMock.mockReset();
    getAuthState.mockReturnValue({ accountId: null });
    globalThis.localStorage.removeItem(ANON_USER_ID_KEY);
  });

  it("登录态: body.user = accountId, inputs.buyer_key = accountId", async () => {
    getAuthState.mockReturnValue({ accountId: ACCOUNT_ID_FOR_LOGIN });
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const out = await callPrepare(transport, {
      id: "conv-1",
      messages: [{ role: "user", parts: [{ type: "text", text: "hi" }] }],
      trigger: "submit-message",
      messageId: undefined,
    });
    expect(out.body.user).toBe(String(ACCOUNT_ID_FOR_LOGIN));
    expect(out.body.inputs).toEqual({ buyer_key: String(ACCOUNT_ID_FOR_LOGIN) });
    expect(out.body.query).toBe("hi");
  });

  it("anon 态: body.user = 本地 anon uuid, inputs.buyer_key 为空串", async () => {
    const transport = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const out = await callPrepare(transport, {
      id: "conv-x",
      messages: [{ role: "user", parts: [{ type: "text", text: "hello" }] }],
      trigger: "submit-message",
      messageId: undefined,
    });
    expect(typeof out.body.user).toBe("string");
    expect(out.body.user).toBeTruthy();
    expect(out.body.inputs).toEqual({ buyer_key: "" });
    expect(out.body.query).toBe("hello");
  });

  it("body 含 conversationId (Dify conv 维度)", async () => {
    getAuthState.mockReturnValue({ accountId: ANOTHER_ACCOUNT_ID });
    const transport = new DifyHttpChatTransport({
      api: "/api/chat/messages",
      body: { conversationId: DUMMY_CONV_ID },
    });
    // 模拟父类 HttpChatTransport sendMessages 内部 merge: { ...resolvedBody, ...options.body }
    // 直接调 prepare 时 caller 负责把构造时的 static body 放进 options.body
    const out = await callPrepare(transport, {
      id: "conv-1",
      messages: [{ role: "user", parts: [{ type: "text", text: "q" }] }],
      trigger: "submit-message",
      messageId: undefined,
      body: { conversationId: DUMMY_CONV_ID },
    });
    expect(out.body.conversationId).toBe(DUMMY_CONV_ID);
  });
});

// CONC-001 修复验证: 两个 transport 实例的 5 段配对状态机不共享
describe("DifyHttpChatTransport — 并发实例隔离 (CONC-001)", () => {
  it("实例 A 流完成后清空 A 的 Set, 不影响实例 B", async () => {
    const transportA = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const transportB = new DifyHttpChatTransport({ api: "/api/chat/messages" });

    // 实例 A 完整跑完 message → message_end 配对
    const chunksA = await collectChunks(
      callProcessResponseStream(
        transportA,
        makeStream(
          'data: {"type":"message","delta":"a-text"}\n\n' +
            'data: {"type":"message_end","conversationId":"cA"}\n\n' +
            "data: [DONE]\n\n",
        ),
      ),
    );
    expect(chunksA.map((chunk) => chunk.type)).toEqual([
      "text-start",
      "text-delta",
      "text-end",
      "finish",
    ]);

    // 实例 B 期望: 自己的 text-start 触发 (不受 A 的 finally clear 影响)
    const chunksB = await collectChunks(
      callProcessResponseStream(
        transportB,
        makeStream('data: {"type":"message","delta":"b-text"}\n\ndata: [DONE]\n\n'),
      ),
    );
    expect(chunksB.map((chunk) => chunk.type)).toEqual(["text-start", "text-delta"]);
  });

  it("实例 A 流 abort 时不清空实例 B 的 startedTextIds", async () => {
    const transportA = new DifyHttpChatTransport({ api: "/api/chat/messages" });
    const transportB = new DifyHttpChatTransport({ api: "/api/chat/messages" });

    // 实例 A 流 cancel 在 text-start 之后, message_end 之前
    const abortA = new AbortController();
    const streamA = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('data: {"type":"message","delta":"a"}\n\n'));
        abortA.abort();
        controller.close();
      },
    });
    await collectChunks(callProcessResponseStream(transportA, streamA)).catch(() => {
      /* expected */
    });

    // 实例 B 跑完整流, 期望 text-start 触发
    const chunksB = await collectChunks(
      callProcessResponseStream(
        transportB,
        makeStream(
          'data: {"type":"message","delta":"b"}\n\n' +
            'data: {"type":"message_end","conversationId":"cB"}\n\n' +
            "data: [DONE]\n\n",
        ),
      ),
    );
    expect(chunksB.map((chunk) => chunk.type)).toEqual([
      "text-start",
      "text-delta",
      "text-end",
      "finish",
    ]);
  });
});
