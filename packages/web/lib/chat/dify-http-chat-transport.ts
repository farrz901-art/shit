/**
 * DifyHttpChatTransport (2026-07-01 chat AI SDK 协议层 Phase 2)
 * AI SDK 7 HttpChatTransport subclass, 把 BFF /api/chat/messages 的 ChatEvent SSE
 * 转成 UIMessageChunk 流 (5 段配对模式: text-start/text-delta/text-end 同 id + reasoning 镜像).
 *
 * 职责:
 *   1. processResponseStream — ChatEvent SSE → UIMessageChunk (5 段配对)
 *   2. prepareSendMessagesRequest — 注入 user / conversationId / inputs / query
 *      (跟旧 send-request.ts 行为等价, 但走 AI SDK transport hook)
 *
 * 边界:
 *   - shared / 客户端 (跟 ai SDK 7 + sse.ts 依赖)
 *   - 旧 send-request.ts 在 T6 删除; transport 接管 fetch 入口
 */
import {
  HttpChatTransport,
  type PrepareSendMessagesRequest,
  type UIMessageChunk,
  type UIMessage,
} from "ai";

import { parseSseBlocks } from "./sse";
import type { ChatEvent, ChatFile } from "./types";
import { useAuthStore } from "@/lib/store/auth-store";
import { ANON_USER_ID_KEY } from "@/const";
import { newId } from "./chat-utils";

const TEXT_ID = "msg";
const REASONING_ID = "think";
const ZERO_IDX = 0;
const ONE_IDX = 1;

/**
 * (2026-07-01) 浏览器 anon id (Dify user 字段用).
 * 跟旧 send-request.ts:getAnonUserId 行为等价 — 跨刷新稳定, 同一浏览器历史连续.
 */
const getAnonUserId = (): string => {
  // 真实 SSR 探测: localStorage 是浏览器全局, Node/globalThis 都有 globalThis 定义.
  // 用 localStorage 区分 SSR (没这对象) vs 浏览器, 而不是 globalThis.
  if (typeof localStorage === "undefined") {
    return "anon-ssr";
  }
  const cached = localStorage.getItem(ANON_USER_ID_KEY);
  if (cached) {
    return cached;
  }
  const fresh = newId();
  try {
    localStorage.setItem(ANON_USER_ID_KEY, fresh);
  } catch {
    // LocalStorage 满/禁 (Safari 隐私模式), 降级返 fresh (本次会话稳定)
  }
  return fresh;
};

/**
 * (2026-07-01) AI SDK 7 UIMessageChunk 流必须 5 段配对 (text-start → text-delta* → text-end
 * + reasoning 镜像, [dist/index.d.ts:2401-2542]). 裸 delta 会破坏状态机.
 * 用 startedTextIds / startedReasoningIds Set 跟踪已开始未结束的 id, 保证每个 id 只 start 一次.
 *
 * CONC-001 修复 (2026-07-07): 状态机 Set 改为实例字段, 跨 transport 实例隔离. 模块级 Set 会被
 * 任何实例 finally { clear() } 全局污染. 当前实现: 每个 transport 实例自带 Set, handleMessage /
 * handleMessageEnd / handleThinking 接收 Set 参数, eventToChunks 闭包 capture this.
 */

/** Emit text-start + text-delta. 5 段配对首段. */
const handleMessage = (delta: string, startedIds: Set<string>): UIMessageChunk[] => {
  const chunks: UIMessageChunk[] = [];
  if (!startedIds.has(TEXT_ID)) {
    chunks.push({ type: "text-start", id: TEXT_ID });
    startedIds.add(TEXT_ID);
  }
  chunks.push({ type: "text-delta", id: TEXT_ID, delta });
  return chunks;
};

/** Emit text-end + finish. 5 段配对收尾. */
const handleMessageEnd = (startedIds: Set<string>): UIMessageChunk[] => {
  const chunks: UIMessageChunk[] = [];
  if (startedIds.has(TEXT_ID)) {
    chunks.push({ type: "text-end", id: TEXT_ID });
    startedIds.delete(TEXT_ID);
  }
  chunks.push({ type: "finish", finishReason: "stop" });
  return chunks;
};

/** Emit reasoning-start + reasoning-delta. reasoning 5 段配对首段. */
const handleThinking = (
  node: string,
  status: string,
  startedIds: Set<string>,
): UIMessageChunk[] => {
  const chunks: UIMessageChunk[] = [];
  if (!startedIds.has(REASONING_ID)) {
    chunks.push({ type: "reasoning-start", id: REASONING_ID });
    startedIds.add(REASONING_ID);
  }
  chunks.push({ type: "reasoning-delta", id: REASONING_ID, delta: `${node}:${status}` });
  return chunks;
};

/** (2026-07-01) ChatEvent → UIMessageChunk[] dispatch 表 (按 type 字段路由).
 *  拆小函数避免 max-statements + 单 case 单函数易测.
 *
 * CONC-001 修复: 改成实例方法风格的 named function expression, 用 `this` capture transport
 * 实例字段 startedTextIds / startedReasoningIds. 调用处用 `.call(this, ev)`. */
type ChunkHandler = (ev: ChatEvent) => UIMessageChunk[];

const eventToChunks = function eventToChunks(
  this: DifyHttpChatTransport,
  ev: ChatEvent,
): UIMessageChunk[] {
  const dispatch: Record<ChatEvent["type"], ChunkHandler> = {
    message: (event) =>
      event.type === "message" ? handleMessage(event.delta, this.startedTextIds) : [],
    message_end: () => handleMessageEnd(this.startedTextIds),
    thinking: (event) =>
      event.type === "thinking"
        ? handleThinking(event.node, event.status, this.startedReasoningIds)
        : [],
    error: (event) =>
      event.type === "error"
        ? [{ type: "error", errorText: `[${event.code}] ${event.message}` }]
        : [],
    workflow_done: () => [],
    done: () => [],
  };
  return dispatch[ev.type](ev);
};

/**
 * DifyHttpChatTransport 初始化参数
 * @shared
 */
export interface DifyHttpChatTransportInit {
  api: string;
  /** (2026-07-01) 静态 body 字段 (Dify conv id / 任何不依赖运行时 state 的字段).
   * 运行时字段 (user / inputs / query) 在 prepareSendMessagesRequest 里注入. */
  body?: { conversationId?: string; files?: ChatFile[] };
}

/** (2026-07-01) 从 messages 抽最后一条 user 的 text part 拼成 query. */
const extractLastUserQuery = (messages: UIMessage[]): string => {
  for (let idx = messages.length - ONE_IDX; idx >= ZERO_IDX; idx -= ONE_IDX) {
    const candidate = messages[idx];
    if (candidate?.role === "user") {
      return candidate.parts
        .filter((part) => part.type === "text")
        .map((part) => part.text)
        .join("");
    }
  }
  return "";
};

/**
 * (2026-07-01) 从 useChat 的 messages 抽最后一条 user text 当 query,
 * 注入 user (accountId 或 anon uuid) + inputs.buyer_key + conversationId (来自 static body).
 *
 * 父类 HttpChatTransport 的 prepareSendMessagesRequest 是 instance property (init option),
 * 不在 constructor 里赋上 → 父类 sendMessages 内部 `await this.prepareSendMessagesRequest?.call(this, ...)`
 * 拿不到,body 走 fallback. 所以必须在构造时塞函数引用.
 */
const prepareSendMessagesRequestFn: PrepareSendMessagesRequest<UIMessage> = async (options) => {
  const { messages } = options;
  const query = extractLastUserQuery(messages);
  const { accountId } = useAuthStore.getState();
  const isAccount = Boolean(accountId);
  const userId = accountId ? String(accountId) : getAnonUserId();
  const staticBody = (options.body ?? {}) as { conversationId?: string; files?: ChatFile[] };
  return {
    body: {
      conversationId: staticBody.conversationId,
      files: staticBody.files,
      inputs: { buyer_key: isAccount ? String(accountId) : "" },
      query,
      user: userId,
    },
  };
};

/**
 * HttpChatTransport 子类 — 把 ChatEvent SSE 转 UIMessageChunk (5 段模式),
 * 把 accountId / anon-id / buyer_key / query 注入到 request body.
 *
 * Use:
 *   const chat = useChat({ chat, transport: new DifyHttpChatTransport({ api, body: { conversationId } }) });
 */
export class DifyHttpChatTransport extends HttpChatTransport<UIMessage> {
  // CONC-001 修复: 实例字段替代模块级 Set, 跨 transport 实例隔离.
  // 模块级 eventToChunks 通过 `this` 引用, 故不加 private 修饰符.
  readonly startedTextIds = new Set<string>();
  readonly startedReasoningIds = new Set<string>();

  constructor(options: DifyHttpChatTransportInit) {
    super({
      api: options.api,
      body: options.body as object | undefined,
      prepareSendMessagesRequest: prepareSendMessagesRequestFn,
    });
  }

  /**
   * (2026-07-01) Override: ChatEvent SSE → UIMessageChunk.
   * 行为等价旧 send-request + applyEvent + handleStreamError, 但走 AI SDK 状态机.
   */
  protected processResponseStream(
    stream: ReadableStream<Uint8Array>,
  ): ReadableStream<UIMessageChunk> {
    const textStream = stream.pipeThrough(
      new TextDecoderStream() as unknown as ReadableWritablePair<string, Uint8Array>,
    );
    return new ReadableStream<UIMessageChunk>({
      start: (controller) => {
        // eslint-disable-next-line max-statements -- 流式解析 + 错误/收尾逻辑紧凑, 拆分会破坏 reader 生命周期
        const pump = async () => {
          try {
            for await (const block of parseSseBlocks(textStream, new AbortController().signal)) {
              const line = block.split("\n").find((ln) => ln.startsWith("data: "));
              if (line) {
                const json = line.slice("data: ".length);
                if (json === "[DONE]") {
                  return;
                }
                try {
                  const ev = JSON.parse(json) as ChatEvent;
                  for (const chunk of eventToChunks.call(this, ev)) {
                    controller.enqueue(chunk);
                  }
                } catch {
                  /* skip malformed JSON */
                }
              }
            }
          } finally {
            controller.close();
            this.startedTextIds.clear();
            this.startedReasoningIds.clear();
          }
        };
        return pump();
      },
    });
  }
}
