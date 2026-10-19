// DifyChatProvider: 把 Dify Chatflow SSE 归一化到 6 种 ChatEvent
// API 参考: https://docs.dify.ai/api-reference/对话流/发送对话消息
// 鉴权: Authorization: Bearer {API_KEY} (固定 scheme, 严禁 shim 兼容 x-api-key)
// SSE 格式: "event: <name>\ndata: <json>\n\n", 可分多块; ping 无 data
// (2026-06-14) 改走 apiProxy() (base=DIFY_BASE_URL 走外部服务, 跳过本项目 auth)
// (2026-06-15) parseStream 内部用 parseSseBlocks 切字节, lastEvent 闭包化
// (2026-07-01) 字节→文本由 body.pipeThrough(new TextDecoderStream()) 处理; normalize* 拆到 chat-event-decoder.ts
import "server-only";

import type { ChatEvent, ChatProvider, SendMessageRequest } from "./types";
import { apiProxy } from "@/lib/api/config";
import { createParseBlock, normalizeEvent } from "./chat-event-decoder";
import { parseSseBlocks } from "./sse";

const DEFAULT_API_URL = "https://api.dify.ai/v1";

/**
 * Dify Chatflow SSE 流式聊天提供者
 * @server-only
 */
export class DifyChatProvider implements ChatProvider {
  readonly name = "dify";

  /**
   * 发送消息并获取流式回复
   * @param req     发送请求参数
   * @param signal  中断信号
   * @returns       流式 ChatEvent 迭代器
   */
  // eslint-disable-next-line max-statements -- 流式消息处理核心, 逻辑紧凑不宜拆分
  async *sendMessage(req: SendMessageRequest, signal: AbortSignal): AsyncIterable<ChatEvent> {
    const apiKey = process.env.DIFY_CHAT_API_KEY;
    const apiUrl = process.env.DIFY_BASE_URL ?? DEFAULT_API_URL;
    if (!apiKey) {
      throw new Error("DIFY_CHAT_API_KEY 未设置");
    }

    // ApiProxy(base=apiUrl) 走外部服务, init.headers 注 Bearer 鉴权
    const res = await apiProxy("/chat-messages", {
      base: apiUrl,
      body: {
        auto_generate_name: req.autoGenerateName ?? true,
        conversation_id: req.conversationId,
        files: req.files,
        inputs: req.inputs ?? {}, // Dify API 必须有 inputs 字段
        query: req.query,
        response_mode: "streaming",
        user: req.user,
      },
      headers: { Authorization: `Bearer ${apiKey}` },
      method: "POST",
      signal,
    });
    if (!res.ok || !res.body) {
      // eslint-disable-next-line unicorn/prefer-ternary -- block is clearer here
      let text = "";
      if (res.body) {
        text = await res.text();
      }
      throw new Error(`Dify ${res.status}: ${text}`);
    }

    yield* this.parseStream(res.body, signal);
  }

  private async *parseStream(
    body: ReadableStream<Uint8Array>,
    signal: AbortSignal,
  ): AsyncIterable<ChatEvent> {
    // Dify Chatflow app 双发射防御: 流式 message delta 拼出完整答案
    // + workflow_finished.data.outputs.answer 包含完整答案.
    // SeenMessage 标志让 normalize 知道当前流是否已经流过 message,
    // 见过则 workflow_finished.outputs.answer 跳过 (避免前端 content 重复).
    // 老式 Workflow app (无 message 事件) 不受影响, seenMessage 始终 false.
    const seenMessageRef = { current: false };
    // 每次 sendMessage 调用的 parseBlock 独立闭包, lastEvent 不会跨实例串味
    const parseBlock = createParseBlock();
    // 字节流先经 TextDecoderStream 转到 string, 再走 SSE 切块器
    // TextDecoderStream.writable 类型是 BufferSource, pipeThrough 入参是 Uint8Array, 走 unknown 中转
    const textStream = body.pipeThrough(
      new TextDecoderStream() as unknown as ReadableWritablePair<string, Uint8Array>,
    );
    for await (const block of parseSseBlocks(textStream, signal)) {
      const ev = parseBlock(block);
      if (ev) {
        for (const chatEv of normalizeEvent(ev, seenMessageRef)) {
          if (chatEv.type === "message") {
            seenMessageRef.current = true;
          }
          yield chatEv;
        }
      }
    }
  }
}
