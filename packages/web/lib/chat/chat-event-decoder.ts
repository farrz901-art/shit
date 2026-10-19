// Dify SSE 事件归一化层 (2026-07-01 从 dify.ts 拆出)
// 职责: RawEvent → ChatEvent (6 种事件) + 双发射防御 + 双块 SSE 合并
import type { ChatEvent, Citation } from "./types";
import { log } from "@/lib/log";

interface RawEvent {
  event: string;
  [k: string]: unknown;
}

interface RawRetrieverResource {
  position?: number;
  dataset_name?: string;
  document_name?: string;
  score?: number;
  content?: string;
  summary?: string | null;
}

const toCitation = (resource: RawRetrieverResource): Citation => ({
  content: resource.content ?? "",
  datasetName: resource.dataset_name,
  documentName: resource.document_name ?? "",
  position: resource.position,
  score: resource.score,
  summary: resource.summary ?? null,
});

// ---- 6 种 normalize 函数 ----

/**
 * 规范化 Dify message 事件为 ChatEvent
 * @param ev  原始 Dify 事件对象
 * @returns   包含 message delta 的 ChatEvent 迭代器
 */
export const normalizeMessage = function* normalizeMessage(ev: RawEvent): Iterable<ChatEvent> {
  yield { delta: String(ev.answer ?? ""), type: "message" };
};

/**
 * 规范化 Dify message_end 事件为 ChatEvent
 * @param ev  原始 Dify 事件对象
 * @returns   包含引用和会话 ID 的 ChatEvent 迭代器
 */
export const normalizeMessageEnd = function* normalizeMessageEnd(
  ev: RawEvent,
): Iterable<ChatEvent> {
  const meta = (ev.metadata ?? {}) as { retriever_resources?: RawRetrieverResource[] };
  const citations: Citation[] | undefined = meta.retriever_resources?.map(toCitation);
  yield { citations, conversationId: String(ev.conversation_id ?? ""), type: "message_end" };
};

/**
 * 规范化 Dify node_started 事件为 thinking 事件
 * @param ev  原始 Dify 事件对象
 * @returns   包含节点状态信息的 ChatEvent 迭代器
 */
export const normalizeNodeStarted = function* normalizeNodeStarted(
  ev: RawEvent,
): Iterable<ChatEvent> {
  yield {
    detail: ev.node_type ? String(ev.node_type) : undefined,
    node: String(ev.node_id ?? ""),
    status: "started",
    type: "thinking",
  };
};

/**
 * 规范化 Dify node_finished 事件为 thinking 事件
 * @param ev  原始 Dify 事件对象
 * @returns   包含节点完成状态的 ChatEvent 迭代器
 */
// eslint-disable-next-line no-nested-ternary -- 失败/状态/无详情三态, if-else 嵌套更深
export const normalizeNodeFinished = function* normalizeNodeFinished(
  ev: RawEvent,
): Iterable<ChatEvent> {
  // 失败/状态/无详情三态, if-else 嵌套更深 → 三元保留
  /* eslint-disable no-nested-ternary */
  const detail = ev.error
    ? `failed: ${String(ev.error)}`
    : ev.status
      ? String(ev.status)
      : undefined;
  /* eslint-enable no-nested-ternary */
  yield {
    detail,
    node: String(ev.node_id ?? ""),
    status: "finished",
    type: "thinking",
  };
};

/**
 * 规范化 Dify workflow_finished 事件为 ChatEvent
 * @param ev              原始 Dify 事件对象
 * @param seenMessageRef  双发射防御引用, 标记是否已发出 message
 * @returns               包含工作流完成状态的 ChatEvent 迭代器
 */
export const normalizeWorkflowFinished = function* normalizeWorkflowFinished(
  ev: RawEvent,
  seenMessageRef?: { current: boolean },
): Iterable<ChatEvent> {
  const wfData = (ev.data ?? {}) as { outputs?: { answer?: string } };
  const answer = wfData.outputs?.answer;
  if (answer && !seenMessageRef?.current) {
    yield { delta: answer, type: "message" };
  }
  yield {
    status: String(ev.status ?? "succeeded") as
      | "succeeded"
      | "failed"
      | "partial-succeeded"
      | "stopped",
    type: "workflow_done",
  };
};

/**
 * 规范化 Dify error 事件为 ChatEvent
 * @param ev  原始 Dify 事件对象
 * @returns   包含错误信息的 ChatEvent 迭代器
 */
export const normalizeError = function* normalizeError(ev: RawEvent): Iterable<ChatEvent> {
  yield { code: String(ev.code ?? "unknown"), message: String(ev.message ?? ""), type: "error" };
};

// ---- 查表 dispatch ----

/**
 * 按事件类型分发到对应的 normalize 函数
 * @param ev              原始 Dify 事件对象
 * @param seenMessageRef  双发射防御引用, 透传给 normalizeWorkflowFinished
 * @returns               对应类型的 ChatEvent 迭代器
 */
// eslint-disable-next-line max-statements -- 查表 dispatch, 每个 case 独立 generator
export const normalizeEvent = function* normalizeEvent(
  ev: RawEvent,
  seenMessageRef?: { current: boolean },
): Iterable<ChatEvent> {
  switch (ev.event) {
    case "message":
    case "message_replace": {
      yield* normalizeMessage(ev);
      return;
    }
    case "message_end": {
      yield* normalizeMessageEnd(ev);
      return;
    }
    case "workflow_started": {
      return;
    }
    case "node_started": {
      yield* normalizeNodeStarted(ev);
      return;
    }
    case "node_finished": {
      yield* normalizeNodeFinished(ev);
      return;
    }
    case "workflow_finished": {
      yield* normalizeWorkflowFinished(ev, seenMessageRef);
      return;
    }
    case "error": {
      yield* normalizeError(ev);
      return;
    }
    case "ping":
    case "tts_message":
    case "tts_message_end": {
      return;
    }
    default: {
      log.warn(`[dify] 未知事件: ${ev.event}`);
      return;
    }
  }
};

// ---- Dify 双块 SSE 解析 ----

/**
 * 创建 Dify 双块 SSE 解析函数 (管理 lastEvent 状态)
 * @returns  解析函数, 接收 SSE block 字符串, 返回 RawEvent 或 null
 */
export const createParseBlock = (): ((block: string) => RawEvent | null) => {
  let lastEvent = "";
  // eslint-disable-next-line max-statements -- 解析函数, 逻辑紧凑不宜拆分
  return (block: string): RawEvent | null => {
    const lines = block.split("\n");
    let event = "";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        data += line.slice("data:".length).trimStart();
      }
    }
    if (event && !data) {
      lastEvent = event;
      return null;
    }
    if (data && !event) {
      event = lastEvent;
    }
    if (!event || !data) {
      return null;
    }
    try {
      const parsed = JSON.parse(data);
      return { event: parsed.event ?? event, ...parsed } as RawEvent;
    } catch {
      return null;
    }
  };
};
