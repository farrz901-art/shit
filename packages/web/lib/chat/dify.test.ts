// DifyChatProvider 测试: 手造 Dify SSE 字节, 验证归一化
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DifyChatProvider } from "./dify";
import type { SendMessageRequest } from "./types";

// ── 常量 ──────────────────────────────────────────
const FIRST_IDX = 0;
const SECOND_IDX = 1;
const EXPECTED_CITATION_COUNT = 2;
const SINGLE_RESULT = 1;
const BYTE_CHUNK_SIZE = 1;
const ABORT_TIMEOUT_MS = 5;

// ── 辅助函数 ──────────────────────────────────────
const sseBytes = (...lines: string[]): ReadableStream<Uint8Array> => {
  const text = `${lines.join("\n")}\n\n`;
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
};

const sseBytesChunked = (lines: string[], chunkSize: number): ReadableStream<Uint8Array> => {
  const text = `${lines.join("\n")}\n\n`;
  return new ReadableStream({
    start(controller) {
      for (let idx = 0; idx < text.length; idx += chunkSize) {
        controller.enqueue(new TextEncoder().encode(text.slice(idx, idx + chunkSize)));
      }
      controller.close();
    },
  });
};

const collect = async <TItem>(iter: AsyncIterable<TItem>): Promise<TItem[]> => {
  const out: TItem[] = [];
  for await (const val of iter) {
    out.push(val);
  }
  return out;
};

const REQ: SendMessageRequest = {
  autoGenerateName: true,
  conversationId: undefined,
  inputs: {},
  query: "1LE 电机怎么选?",
  user: "user-1",
};

// ── 测试 ──────────────────────────────────────────
describe("DifyChatProvider", () => {
  let fetchMock: ReturnType<typeof vi.fn> = vi.fn();

  beforeEach(() => {
    process.env.DIFY_CHAT_API_KEY = "app-test";
    process.env.DIFY_BASE_URL = "https://dify.test/v1";
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });
  afterEach(() => vi.restoreAllMocks());

  describe("事件归一化", () => {
    it("构造时 name='dify'", () => {
      expect(new DifyChatProvider().name).toBe("dify");
    });

    it("message 事件归一化为 { type: 'message', delta: answer }", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"你好","created_at":1700000000}`,
        ),
        ok: true,
      });
      const provider = new DifyChatProvider();
      const events = await collect(provider.sendMessage(REQ, new AbortController().signal));
      const messages = events.filter((event) => event.type === "message");
      expect(messages).toEqual([{ delta: "你好", type: "message" }]);
    });

    it("message_end 归一化为带 conversationId + citations (retriever_resources)", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: message_end`,
          `data: ${JSON.stringify({
            conversation_id: "conv-xyz",
            created_at: 1_700_000_000,
            event: "message_end",
            id: "m1",
            metadata: {
              retriever_resources: [
                {
                  content: "1LE 系列电机根据功率选型...",
                  dataset_id: "ds1",
                  dataset_name: "电机手册",
                  document_id: "doc1",
                  document_name: "1LE1023.pdf",
                  position: 1,
                  score: 0.87,
                  segment_id: "s1",
                  summary: null,
                },
                {
                  content: "选型步骤...",
                  dataset_id: "ds1",
                  dataset_name: "电机手册",
                  document_id: "doc2",
                  document_name: "选型指南.pdf",
                  position: 2,
                  score: 0.81,
                  segment_id: "s2",
                  summary: null,
                },
              ],
            },
            task_id: "t1",
          })}`,
        ),
        ok: true,
      });
      const provider = new DifyChatProvider();
      const events = await collect(provider.sendMessage(REQ, new AbortController().signal));
      const end = events.find((event) => event.type === "message_end");
      expect(end).toBeDefined();
      if (end?.type !== "message_end") {
        return;
      }
      expect(end.conversationId).toBe("conv-xyz");
      expect(end.citations).toHaveLength(EXPECTED_CITATION_COUNT);
      expect(end.citations?.[FIRST_IDX]).toMatchObject({
        datasetName: "电机手册",
        documentName: "1LE1023.pdf",
        position: 1,
        score: 0.87,
      });
    });

    it("error 事件归一化为 { type: 'error', code, message }", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: error`,
          `data: {"event":"error","task_id":"t1","message_id":"m1","status":"error","code":"provider_quota_exceeded","message":"quota exhausted"}`,
        ),
        ok: true,
      });
      const events = await collect(
        new DifyChatProvider().sendMessage(REQ, new AbortController().signal),
      );
      expect(events).toContainEqual({
        code: "provider_quota_exceeded",
        message: "quota exhausted",
        type: "error",
      });
    });

    it("ping 事件必须被忽略, 不上抛为 ChatEvent", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: ping`,
          `data: {"event":"ping","task_id":"t1","created_at":1700000000}`,
          ``,
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"hi","created_at":1700000001}`,
        ),
        ok: true,
      });
      const events = await collect(
        new DifyChatProvider().sendMessage(REQ, new AbortController().signal),
      );
      // ChatEvent 联合类型故意不含 'ping', 所以用宽松断言: 没有未识别的事件类型就行
      const allowed = new Set([
        "message",
        "message_end",
        "thinking",
        "workflow_done",
        "error",
        "done",
      ]);
      expect(events.some((event) => !allowed.has(event.type))).toBe(false);
      expect(events).toContainEqual({ delta: "hi", type: "message" });
    });

    it("message_replace 归一化为 message (覆盖语义靠前端覆盖 content)", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"违规内容","created_at":1700000000}`,
          ``,
          `event: message_replace`,
          `data: {"event":"message_replace","task_id":"t1","message_id":"m1","answer":"已替换内容","created_at":1700000001}`,
        ),
        ok: true,
      });
      const events = await collect(
        new DifyChatProvider().sendMessage(REQ, new AbortController().signal),
      );
      const messages = events.filter((event) => event.type === "message");
      expect(messages).toEqual([
        { delta: "违规内容", type: "message" },
        { delta: "已替换内容", type: "message" },
      ]);
    });
  });

  describe("Workflow 事件", () => {
    it("workflow_started + node_started + node_finished + workflow_finished 归一化为 thinking/workflow_done", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: workflow_started`,
          `data: {"event":"workflow_started","task_id":"t1","workflow_run_id":"w1","created_at":1700000000}`,
          ``,
          `event: node_started`,
          `data: {"event":"node_started","task_id":"t1","workflow_run_id":"w1","node_id":"n1","node_type":"knowledge-retrieval","title":"检索知识库","index":0,"created_at":1700000001}`,
          ``,
          `event: node_finished`,
          `data: {"event":"node_finished","task_id":"t1","workflow_run_id":"w1","node_id":"n1","node_type":"knowledge-retrieval","title":"检索知识库","index":0,"status":"succeeded","elapsed_time":0.42,"created_at":1700000002}`,
          ``,
          `event: workflow_finished`,
          `data: {"event":"workflow_finished","task_id":"t1","workflow_run_id":"w1","status":"succeeded","elapsed_time":1.23,"total_tokens":100,"total_steps":1,"created_at":1700000003}`,
        ),
        ok: true,
      });
      const events = await collect(
        new DifyChatProvider().sendMessage(REQ, new AbortController().signal),
      );
      const thinkings = events.filter((event) => event.type === "thinking");
      expect(thinkings).toEqual([
        { detail: "knowledge-retrieval", node: "n1", status: "started", type: "thinking" },
        { detail: "succeeded", node: "n1", status: "finished", type: "thinking" },
      ]);
      const done = events.find((event) => event.type === "workflow_done");
      expect(done).toEqual({ status: "succeeded", type: "workflow_done" });
    });

    it("Chatflow: workflow_finished.outputs.answer 跟 message delta 重复时, 必须跳过避免前端 content 重复", async () => {
      // Dify Chatflow app 会双发射: 流式 message delta 拼出完整答案 + workflow_finished.outputs.answer 包含完整答案
      // 旧 normalize 在 workflow_finished 里无脑 yield { type: "message", delta: answer }
      // → 前端 content += delta 看到两次, 答案被显示 2 遍
      // 修法: seenMessage 守卫, 已经流过 message 就跳过 workflow_finished 重发
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"abc","created_at":1700000001}`,
          ``,
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"def","created_at":1700000002}`,
          ``,
          `event: workflow_finished`,
          `data: ${JSON.stringify({
            created_at: 1_700_000_003,
            data: { outputs: { answer: "abcdef" } },
            elapsed_time: 1,
            event: "workflow_finished",
            status: "succeeded",
            task_id: "t1",
            total_steps: 1,
            total_tokens: 50,
            workflow_run_id: "w1",
          })}`,
        ),
        ok: true,
      });
      const events = await collect(
        new DifyChatProvider().sendMessage(REQ, new AbortController().signal),
      );
      // 关键断言: 只看到 2 个 message delta, 绝不能出现 workflow_finished 重发的完整 answer
      const messages = events.filter((event) => event.type === "message");
      expect(messages).toEqual([
        { delta: "abc", type: "message" },
        { delta: "def", type: "message" },
      ]);
      // Workflow_done 仍然发射 (跟原行为一致, 只 message 重复部分被守卫吞)
      expect(events.find((event) => event.type === "workflow_done")).toEqual({
        status: "succeeded",
        type: "workflow_done",
      });
    });

    it("Workflow 老式: 没 message 事件, workflow_finished.outputs.answer 仍能拿到答案 (兼容老 app)", async () => {
      // 守卫必须 NOT 误伤老式 Workflow app: 它们没有 message 事件, 只靠 workflow_finished.outputs.answer
      // 拿答案, seenMessage 始终 false, 所以 answer 必须 yield
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: workflow_started`,
          `data: {"event":"workflow_started","task_id":"t1","workflow_run_id":"w1","created_at":1700000000}`,
          ``,
          `event: node_started`,
          `data: {"event":"node_started","task_id":"t1","workflow_run_id":"w1","node_id":"n1","node_type":"llm","title":"LLM","index":0,"created_at":1700000001}`,
          ``,
          `event: node_finished`,
          `data: {"event":"node_finished","task_id":"t1","workflow_run_id":"w1","node_id":"n1","node_type":"llm","title":"LLM","index":0,"status":"succeeded","elapsed_time":0.5,"created_at":1700000002}`,
          ``,
          `event: workflow_finished`,
          `data: ${JSON.stringify({
            created_at: 1_700_000_003,
            data: { outputs: { answer: "完整答案" } },
            elapsed_time: 0.6,
            event: "workflow_finished",
            status: "succeeded",
            task_id: "t1",
            total_steps: 1,
            total_tokens: 30,
            workflow_run_id: "w1",
          })}`,
        ),
        ok: true,
      });
      const events = await collect(
        new DifyChatProvider().sendMessage(REQ, new AbortController().signal),
      );
      const messages = events.filter((event) => event.type === "message");
      // 老 Workflow: 1 个 message 事件 (来自 workflow_finished.outputs.answer)
      expect(messages).toEqual([{ delta: "完整答案", type: "message" }]);
      expect(events.find((event) => event.type === "workflow_done")).toEqual({
        status: "succeeded",
        type: "workflow_done",
      });
    });

    it("node_finished status=failed 归一化为 thinking finished+fail (detail 带 reason)", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: node_started`,
          `data: {"event":"node_started","task_id":"t1","workflow_run_id":"w1","node_id":"n1","node_type":"llm","title":"LLM","index":0,"created_at":1700000001}`,
          ``,
          `event: node_finished`,
          `data: ${JSON.stringify({
            created_at: 1_700_000_002,
            elapsed_time: 0.1,
            error: "rate_limit",
            event: "node_finished",
            index: 0,
            node_id: "n1",
            node_type: "llm",
            status: "failed",
            task_id: "t1",
            title: "LLM",
            workflow_run_id: "w1",
          })}`,
        ),
        ok: true,
      });
      const events = await collect(
        new DifyChatProvider().sendMessage(REQ, new AbortController().signal),
      );
      const failed = events.filter(
        (event) => event.type === "thinking" && event.status === "finished",
      );
      expect(failed).toHaveLength(SINGLE_RESULT);
      if (failed[FIRST_IDX].type !== "thinking") {
        return;
      }
      expect(failed[FIRST_IDX].detail).toContain("failed");
    });
  });

  describe("请求体 & 边界条件", () => {
    it("HTTP 401 抛错 (不返流)", async () => {
      fetchMock.mockResolvedValueOnce({ ok: false, status: 401, text: async () => "unauthorized" });
      await expect(
        collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal)),
      ).rejects.toThrow(/401/);
    });

    it("请求体包含 query/inputs/user/response_mode='streaming' + Bearer 鉴权", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"x","created_at":1}`,
        ),
        ok: true,
      });
      await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
      const [[url, init]] = fetchMock.mock.calls;
      expect(url).toBe("https://dify.test/v1/chat-messages");
      expect((init.headers as Record<string, string>).Authorization).toBe("Bearer app-test");
      expect(init.method).toBe("POST");
      const body = JSON.parse(init.body as string);
      expect(body).toMatchObject({
        auto_generate_name: true,
        inputs: {},
        query: REQ.query,
        response_mode: "streaming",
        user: REQ.user,
      });
      expect(body.conversation_id).toBeUndefined();
    });

    it("inputs 字段必须存在 (即使为空对象) — Dify API 强制要求", async () => {
      // 2026-06-09 bug fix: 缺少 inputs 字段 → Dify 400 'Field required'
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"x","created_at":1}`,
        ),
        ok: true,
      });
      await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
      const body = JSON.parse(fetchMock.mock.calls[FIRST_IDX][SECOND_IDX].body as string);
      expect(body.inputs).toBeDefined();
      expect(typeof body.inputs).toBe("object");
    });

    it("inputs 可以传自定义字段", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"x","created_at":1}`,
        ),
        ok: true,
      });
      const reqWithInputs = { ...REQ, inputs: { language: "zh", mode: "expert" } };
      await collect(
        new DifyChatProvider().sendMessage(reqWithInputs, new AbortController().signal),
      );
      const body = JSON.parse(fetchMock.mock.calls[FIRST_IDX][SECOND_IDX].body as string);
      expect(body.inputs).toEqual({ language: "zh", mode: "expert" });
    });

    it("续聊带 conversationId → 请求体 conversation_id 字段", async () => {
      fetchMock.mockResolvedValueOnce({
        body: sseBytes(
          `event: message`,
          `data: {"event":"message","id":"m1","task_id":"t1","answer":"x","created_at":1}`,
        ),
        ok: true,
      });
      await collect(
        new DifyChatProvider().sendMessage(
          { ...REQ, conversationId: "conv-prev" },
          new AbortController().signal,
        ),
      );
      const body = JSON.parse(fetchMock.mock.calls[FIRST_IDX][SECOND_IDX].body as string);
      expect(body.conversation_id).toBe("conv-prev");
    });

    it("SSE 字节跨块拼接正确 (1 字节/块, 解析仍归一化)", async () => {
      const lines = [
        `event: message`,
        `data: {"event":"message","id":"m1","task_id":"t1","answer":"abc","created_at":1}`,
      ];
      fetchMock.mockResolvedValueOnce({ body: sseBytesChunked(lines, BYTE_CHUNK_SIZE), ok: true });
      const events = await collect(
        new DifyChatProvider().sendMessage(REQ, new AbortController().signal),
      );
      expect(events).toContainEqual({ delta: "abc", type: "message" });
    });

    it("用户 abort → 抛 AbortError (链断 fetch)", async () => {
      fetchMock.mockImplementationOnce(
        (_url, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("aborted", "AbortError")),
            );
          }),
      );
      const controller = new AbortController();
      const iter = new DifyChatProvider().sendMessage(REQ, controller.signal);
      setTimeout(() => controller.abort(), ABORT_TIMEOUT_MS);
      await expect(collect(iter)).rejects.toThrow(/aborted/);
    });
  });
});
