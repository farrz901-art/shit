// chat-event-decoder.test.ts — Dify 事件归一化 + 双块 SSE 解析
/* eslint-disable no-magic-numbers -- 测试断言中的 [0] 索引/常量, 0/1/2 提取常量反而降低可读性 */
import { describe, expect, it } from "vitest";
import {
  createParseBlock,
  normalizeError,
  normalizeEvent,
  normalizeMessage,
  normalizeMessageEnd,
  normalizeWorkflowFinished,
} from "./chat-event-decoder";

describe("createParseBlock", () => {
  it("event: xxx + data: {...} 在同一块 → 解析出 event+data", () => {
    const parse = createParseBlock();
    const result = parse('event: message\ndata: {"answer":"hi"}');
    expect(result).toBeTruthy();
    expect(result!.event).toBe("message");
    expect(result!.answer).toBe("hi");
  });

  it("event: xxx 单独一块 (无 data) → 缓存 lastEvent, 返 null", () => {
    const parse = createParseBlock();
    expect(parse("event: message")).toBeNull();
  });

  it("data: {...} 单独一块 → 用 lastEvent 补 event", () => {
    const parse = createParseBlock();
    parse("event: message"); // 缓存 lastEvent
    const result = parse('data: {"answer":"hi"}');
    expect(result!.event).toBe("message");
    expect(result!.answer).toBe("hi");
  });

  it("空块 (没 event 也没 data) → 返 null 且 lastEvent 保留", () => {
    const parse = createParseBlock();
    parse("event: message_end"); // 缓存 message_end
    expect(parse("")).toBeNull();
    // 下次出现 data 应仍用 message_end (lastEvent 保留)
    const result = parse('data: {"conversation_id":"c1"}');
    expect(result!.event).toBe("message_end");
  });

  it("data 解析失败 → 返 null, 不抛", () => {
    const parse = createParseBlock();
    expect(parse("event: message\ndata: {not-json}")).toBeNull();
  });
});

// eslint-disable-next-line max-statements -- 14 个测试用例的 normalizeEvent dispatcher 全覆盖
describe("normalizeEvent", () => {
  it("message → yield {type: message, delta}", () => {
    const result = [...normalizeEvent({ answer: "你好", event: "message" })];
    expect(result).toEqual([{ delta: "你好", type: "message" }]);
  });

  it("message_replace → 同 message", () => {
    const result = [...normalizeEvent({ answer: "替换内容", event: "message_replace" })];
    expect(result).toEqual([{ delta: "替换内容", type: "message" }]);
  });

  it("message_end → yield {type: message_end, conversationId, citations}", () => {
    const result = [
      ...normalizeEvent({
        conversation_id: "c1",
        event: "message_end",
        metadata: {
          retriever_resources: [{ content: "c1", document_name: "d1" }],
        },
      }),
    ];
    expect(result[0].type).toBe("message_end");
    const messageEndEvent = result[0] as Extract<(typeof result)[0], { type: "message_end" }>;
    expect(messageEndEvent.conversationId).toBe("c1");
    expect(messageEndEvent.citations).toHaveLength(1);
    expect(messageEndEvent.citations?.[0].documentName).toBe("d1");
  });

  it("message_end 无 metadata → citations undefined", () => {
    const result = [...normalizeEvent({ event: "message_end" })];
    expect(result[0].type).toBe("message_end");
    const messageEndEvent = result[0] as Extract<(typeof result)[0], { type: "message_end" }>;
    expect(messageEndEvent.citations).toBeUndefined();
  });

  it("node_started → thinking with status: started", () => {
    const result = [
      ...normalizeEvent({ event: "node_started", node_id: "n1", node_type: "knowledge-retrieval" }),
    ];
    expect(result[0]).toMatchObject({
      detail: "knowledge-retrieval",
      node: "n1",
      status: "started",
      type: "thinking",
    });
  });

  it("node_finished with status → thinking with status: finished", () => {
    const result = [
      ...normalizeEvent({ event: "node_finished", node_id: "n1", status: "succeeded" }),
    ];
    expect(result[0]).toMatchObject({
      detail: "succeeded",
      node: "n1",
      status: "finished",
      type: "thinking",
    });
  });

  it("node_finished with error → detail: failed: {error}", () => {
    const result = [...normalizeEvent({ error: "timeout", event: "node_finished", node_id: "n1" })];
    expect(result[0]).toMatchObject({ detail: "failed: timeout", status: "finished" });
  });

  it("workflow_finished + seenMessage=false → yield message delta + workflow_done", () => {
    const result = [
      ...normalizeWorkflowFinished(
        {
          data: { outputs: { answer: "完整答案" } },
          event: "workflow_finished",
          status: "succeeded",
        },
        { current: false },
      ),
    ];
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ delta: "完整答案", type: "message" });
    expect(result[1]).toEqual({ status: "succeeded", type: "workflow_done" });
  });

  it("workflow_finished + seenMessage=true → 跳过 answer, 只 yield workflow_done", () => {
    const result = [
      ...normalizeWorkflowFinished(
        {
          data: { outputs: { answer: "完整答案" } },
          event: "workflow_finished",
          status: "succeeded",
        },
        { current: true },
      ),
    ];
    expect(result).toEqual([{ status: "succeeded", type: "workflow_done" }]);
  });

  it("workflow_finished 无 data.outputs.answer → 只 yield workflow_done", () => {
    const result = [
      ...normalizeWorkflowFinished({ event: "workflow_finished", status: "stopped" }),
    ];
    expect(result).toEqual([{ status: "stopped", type: "workflow_done" }]);
  });

  it("error → yield {type: error, code, message}", () => {
    const result = [...normalizeError({ code: "E001", event: "error", message: "失败" })];
    expect(result).toEqual([{ code: "E001", message: "失败", type: "error" }]);
  });

  it("未知事件 → 不 yield (log.warn, 不抛)", () => {
    const result = [...normalizeEvent({ event: "unknown_event_type" })];
    expect(result).toEqual([]);
  });

  it("workflow_started → 不 yield", () => {
    const result = [...normalizeEvent({ event: "workflow_started" })];
    expect(result).toEqual([]);
  });

  it("ping / tts_message / tts_message_end → 不 yield", () => {
    expect([...normalizeEvent({ event: "ping" })]).toEqual([]);
    expect([...normalizeEvent({ event: "tts_message" })]).toEqual([]);
    expect([...normalizeEvent({ event: "tts_message_end" })]).toEqual([]);
  });
});

describe("normalizeMessage", () => {
  it("answer 字段 → delta", () => {
    const result = [...normalizeMessage({ answer: "x", event: "message" })];
    expect(result).toEqual([{ delta: "x", type: "message" }]);
  });

  it("无 answer → delta 为空串", () => {
    const result = [...normalizeMessage({ event: "message" })];
    expect(result).toEqual([{ delta: "", type: "message" }]);
  });
});

describe("normalizeMessageEnd", () => {
  it("citations 包含 position/dataset_name/score 等字段映射", () => {
    const result = [
      ...normalizeMessageEnd({
        conversation_id: "c1",
        event: "message_end",
        metadata: {
          retriever_resources: [
            {
              content: "doc content",
              dataset_name: "ds1",
              document_name: "doc1",
              position: 1,
              score: 0.95,
              summary: null,
            },
          ],
        },
      }),
    ];
    const messageEndCitations = (result[0] as Extract<(typeof result)[0], { type: "message_end" }>)
      .citations;
    expect(messageEndCitations?.[0]).toMatchObject({
      content: "doc content",
      datasetName: "ds1",
      documentName: "doc1",
      position: 1,
      score: 0.95,
      summary: null,
    });
  });

  it("summary 为 undefined → null", () => {
    const result = [
      ...normalizeMessageEnd({
        conversation_id: "c1",
        event: "message_end",
        metadata: {
          retriever_resources: [{ content: "x", document_name: "d1" }],
        },
      }),
    ];
    const messageEndCitations = (result[0] as Extract<(typeof result)[0], { type: "message_end" }>)
      .citations;
    expect(messageEndCitations?.[0].summary).toBeNull();
  });
});
