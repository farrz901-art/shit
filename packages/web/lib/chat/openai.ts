// OpenAI 兼容 Chat Provider
// 支持所有 OpenAI 格式 API: OpenAI / DeepSeek / Ollama / vLLM / LiteLLM 等
// 通过 OPENAI_BASE_URL 配置 endpoint, OPENAI_API_KEY 配置密钥
// (2026-06-14) 改走 apiProxy() (base=OPENAI_BASE_URL 走外部服务, 跳过本项目 auth)
import "server-only";

import type { ChatEvent, ChatProvider, SendMessageRequest } from "./types";
import { apiProxy } from "@/lib/api/config";
import { parseSseBlocks } from "./sse";

const BASE_URL = process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1";
const API_KEY = process.env.OPENAI_API_KEY ?? "";
const MODEL = process.env.OPENAI_MODEL ?? "gpt-4o";
const FIRST_CHOICE_INDEX = 0; // 第一个 choice 索引

/**
 * OpenAI 兼容 API 流式聊天提供者
 * @server-only
 */
export class OpenAIChatProvider implements ChatProvider {
  readonly name = "openai";

  /**
   * 发送消息并获取流式回复
   * @param req     发送请求参数
   * @param signal  中断信号
   * @returns       流式 ChatEvent 迭代器
   */
  // eslint-disable-next-line max-statements -- 流式解析核心逻辑, 拆分会破坏 reader/abort 生命周期
  async *sendMessage(req: SendMessageRequest, signal: AbortSignal): AsyncIterable<ChatEvent> {
    if (!API_KEY) {
      yield { code: "config_error", message: "OPENAI_API_KEY 未设置", type: "error" };
      return;
    }

    const res = await apiProxy("/chat/completions", {
      base: BASE_URL,
      body: {
        messages: [{ content: req.query, role: "user" }],
        model: MODEL,
        stream: true,
      },
      headers: { Authorization: `Bearer ${API_KEY}` },
      method: "POST",
      signal,
    });

    if (!res.ok) {
      const text = await res.text();
      yield { code: `http_${res.status}`, message: text, type: "error" };
      return;
    }

    const textStream = res.body!.pipeThrough(
      new TextDecoderStream() as unknown as ReadableWritablePair<string, Uint8Array>,
    );
    let reasoningBuf = ""; // 累积深度思考内容

    for await (const block of parseSseBlocks(textStream, signal)) {
      const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
      if (dataLine) {
        const json = dataLine.slice("data: ".length);
        if (json === "[DONE]") {
          // 结束时如果还有未输出的思考内容, 一次性输出
          if (reasoningBuf) {
            yield {
              detail: reasoningBuf,
              node: "reasoning",
              status: "started",
              type: "thinking",
            };
            reasoningBuf = "";
          }
          yield { conversationId: "", type: "message_end" };
          return;
        }

        try {
          const parsed = JSON.parse(json);
          const delta = parsed.choices?.[FIRST_CHOICE_INDEX]?.delta;
          if (delta?.reasoning_content) {
            // 累积思考内容, 不逐字输出
            reasoningBuf += delta.reasoning_content;
          }
          if (delta?.content) {
            // 正式回复开始: 如果有思考内容先输出
            if (reasoningBuf) {
              yield {
                detail: reasoningBuf,
                node: "reasoning",
                status: "started",
                type: "thinking",
              };
              reasoningBuf = "";
            }
            yield { delta: delta.content, type: "message" };
          }
        } catch {
          // 跳过解析失败的行
        }
      }
    }

    // 流正常结束
    if (reasoningBuf) {
      yield { detail: reasoningBuf, node: "reasoning", status: "started", type: "thinking" };
    }
    yield { conversationId: "", type: "message_end" };
  }
}
