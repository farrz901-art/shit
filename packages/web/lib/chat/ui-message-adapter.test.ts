/**
 * ui-message-adapter 单元测试 (2026-07-01 chat AI SDK 协议层 Phase 2)
 * 覆盖 3 个转换函数:
 *   1. messageToUIMessage — IDB flat → UIMessage (含 metadata + parts)
 *   2. uiMessageToMessage — UIMessage → IDB flat (round-trip)
 *   3. serverMessageToUIMessage — ServerMessage (TanStack fetch) → UIMessage (load 历史)
 *
 * 6 个 case:
 *   - user message (无 thinking/citations)
 *   - assistant message (content + thinking)
 *   - assistant interrupted (metadata.interrupted = true)
 *   - assistant with citations (metadata.citations 保留)
 *   - round-trip (message → ui → message, 内容一致)
 *   - server load (ServerMessage → UIMessage, meta citations 转移到 metadata)
 */
import { describe, expect, it } from "vitest";

import type { ServerMessage } from "./api";
import type { Message } from "./types";

const { messageToUIMessage, uiMessageToMessage, serverMessageToUIMessage } =
  await import("./ui-message-adapter");

const FIXED_TS_MS = 1_700_000_000_000;
const FIXED_TS_ISO = new Date(FIXED_TS_MS).toISOString();
const ZERO_IDX = 0;
const ONE_ITEM = 1;

const SAMPLE_CITATIONS = [
  {
    content: "RAG 是检索增强生成",
    datasetName: "kb-1",
    documentName: "intro.md",
    position: 0,
    score: 0.9,
  },
];

const SAMPLE_THINKING = [
  { detail: "开始检索", node: "n1", status: "started" as const },
  { detail: "完成", node: "n1", status: "finished" as const },
];

const USER_MSG_BASE: Message = {
  content: "你好",
  createdAt: FIXED_TS_MS,
  id: "msg-u1",
  role: "user",
};

describe("ui-message-adapter — messageToUIMessage (IDB → UIMessage)", () => {
  it("user message: 单 text part + 元数据", () => {
    const ui = messageToUIMessage(USER_MSG_BASE);
    expect(ui.role).toBe("user");
    expect(ui.id).toBe("msg-u1");
    expect(ui.parts).toHaveLength(ONE_ITEM);
    expect(ui.parts[ZERO_IDX]).toMatchObject({ type: "text", text: "你好", state: "done" });
    expect(ui.metadata?.conversationId).toBeUndefined();
    expect(ui.metadata?.citations).toBeUndefined();
    expect(ui.metadata?.interrupted).toBeUndefined();
  });

  it("assistant with thinking: metadata.thinking 保留 + 单 text part", () => {
    const assistant: Message = {
      ...USER_MSG_BASE,
      content: "回答",
      role: "assistant",
      thinking: SAMPLE_THINKING,
    };
    const ui = messageToUIMessage(assistant);
    expect(ui.parts).toHaveLength(ONE_ITEM);
    expect(ui.parts[ZERO_IDX]).toMatchObject({ type: "text", text: "回答", state: "done" });
    expect(ui.metadata?.thinking).toEqual(SAMPLE_THINKING);
  });

  it("assistant interrupted: metadata.interrupted = true", () => {
    const assistant: Message = {
      ...USER_MSG_BASE,
      content: "部分回答",
      interrupted: true,
      role: "assistant",
    };
    const ui = messageToUIMessage(assistant);
    expect(ui.metadata?.interrupted).toBe(true);
    expect(ui.parts).toHaveLength(ONE_ITEM);
    expect(ui.parts[ZERO_IDX]).toMatchObject({ type: "text", text: "部分回答" });
  });

  it("assistant with citations: metadata.citations 保留", () => {
    const assistant: Message = {
      ...USER_MSG_BASE,
      citations: SAMPLE_CITATIONS,
      content: "带引用的回答",
      role: "assistant",
    };
    const ui = messageToUIMessage(assistant);
    expect(ui.metadata?.citations).toEqual(SAMPLE_CITATIONS);
  });
});

describe("ui-message-adapter — uiMessageToMessage (UIMessage → IDB)", () => {
  it("round-trip: message → ui → message 字段全部保留", () => {
    const original: Message = {
      citations: SAMPLE_CITATIONS,
      content: "完整回答",
      conversationId: "conv-1",
      createdAt: 1_700_000_000_000,
      id: "msg-a1",
      role: "assistant",
      thinking: SAMPLE_THINKING,
    };
    const ui = messageToUIMessage(original);
    const back = uiMessageToMessage(ui);
    expect(back.id).toBe(original.id);
    expect(back.role).toBe(original.role);
    expect(back.content).toBe(original.content);
    expect(back.createdAt).toBe(original.createdAt);
    expect(back.conversationId).toBe(original.conversationId);
    expect(back.citations).toEqual(original.citations);
    expect(back.thinking).toEqual(original.thinking);
  });

  it("UI 无 metadata: round-trip 后 metadata 字段 undefined", () => {
    const ui = messageToUIMessage(USER_MSG_BASE);
    const back = uiMessageToMessage(ui);
    expect(back.citations).toBeUndefined();
    expect(back.thinking).toBeUndefined();
    expect(back.interrupted).toBeUndefined();
  });
});

describe("ui-message-adapter — serverMessageToUIMessage (TanStack fetch → UIMessage)", () => {
  it("服务端 user 消息: text part + role 一致", () => {
    const serverMsg: ServerMessage = {
      content: "客户端消息",
      created_at: FIXED_TS_ISO,
      id: "srv-u1",
      meta: null,
      role: "user",
    };
    const ui = serverMessageToUIMessage(serverMsg);
    expect(ui.role).toBe("user");
    expect(ui.id).toBe("srv-u1");
    expect(ui.parts).toHaveLength(ONE_ITEM);
    expect(ui.parts[ZERO_IDX]).toMatchObject({ type: "text", text: "客户端消息", state: "done" });
    expect(ui.metadata?.createdAt).toBe(FIXED_TS_MS);
  });

  it("服务端 system 消息映射为 assistant (项目规则)", () => {
    const serverMsg: ServerMessage = {
      content: "[系统提示]",
      created_at: FIXED_TS_ISO,
      id: "srv-s1",
      meta: null,
      role: "system",
    };
    const ui = serverMessageToUIMessage(serverMsg);
    expect(ui.role).toBe("assistant");
  });

  it("服务端 meta.citations 转移到 metadata.citations", () => {
    const serverMsg: ServerMessage = {
      content: "带引用",
      created_at: FIXED_TS_ISO,
      id: "srv-a1",
      meta: { citations: SAMPLE_CITATIONS, finish_reason: "stop" },
      role: "assistant",
    };
    const ui = serverMessageToUIMessage(serverMsg);
    expect(ui.metadata?.citations).toEqual(SAMPLE_CITATIONS);
  });
});
