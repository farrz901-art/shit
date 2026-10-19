// BFF /api/chat/messages (2026-06-09)
// 鉴权: x-chat-token 必须等于 CHAT_PUBLIC_TOKEN (与 NEXT_PUBLIC_CHAT_TOKEN 对称, 防 token 透传)
// 限流: 同一 IP 20 次/分, 超阈值返 429
// Body: zod 校验 Dify Chatflow 字段 (query / inputs / user / conversationId / autoGenerateName)
// 流出错降级: provider 抛错 → 流里 yield error 事件 + [DONE], 客户端 UI 不会卡死
// SSE 编码: 走 AI SDK JsonToSseTransformStream (自动 data: 前缀 + \n\n + [DONE] flush)
import type { ChatEvent } from "@/lib/chat/types";
import type { NextRequest } from "next/server";
import { JsonToSseTransformStream } from "ai";
import { getChatProvider } from "@/lib/chat/factory";
import { checkAndIncrement, extractClientIp } from "@/lib/rate-limiter";
import { z } from "zod";
import {
  HEADER_CONTENT_TYPE,
  HEADER_X_CHAT_TOKEN,
  HTTP_BAD_REQUEST,
  HTTP_INTERNAL_SERVER_ERROR,
  HTTP_TOO_MANY_REQUESTS,
  HTTP_UNAUTHORIZED,
  MIME_JSON,
  ONE,
} from "@/const";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";
/** 路由段配置: 使用 Node.js 运行时 */
export const runtime = "nodejs";

const MAX_QUERY_LENGTH = 16_000;
const MAX_USER_LENGTH = 64;

// 限流: 20 次/分/IP
const RATE_LIMIT_MAX = 20;
const RATE_LIMIT_WINDOW_MS = 60_000;

const BodySchema = z.object({
  autoGenerateName: z.boolean().optional(),
  conversationId: z.string().optional(),
  inputs: z.record(z.string(), z.unknown()).optional().default({}),
  query: z.string().min(ONE).max(MAX_QUERY_LENGTH),
  user: z.string().min(ONE).max(MAX_USER_LENGTH),
});

const unauthorized = (): Response =>
  Response.json(
    { error: "unauthorized" },
    {
      headers: { [HEADER_CONTENT_TYPE]: MIME_JSON },
      status: HTTP_UNAUTHORIZED,
    },
  );

const badRequest = (detail: string): Response =>
  Response.json(
    { error: detail },
    {
      headers: { [HEADER_CONTENT_TYPE]: MIME_JSON },
      status: HTTP_BAD_REQUEST,
    },
  );

const tooManyRequests = (remaining: number): Response =>
  Response.json(
    { error: "too many requests", remaining },
    {
      headers: { [HEADER_CONTENT_TYPE]: MIME_JSON },
      status: HTTP_TOO_MANY_REQUESTS,
    },
  );

const checkAuth = (req: NextRequest): true | Response => {
  const expected = process.env.CHAT_PUBLIC_TOKEN;
  if (!expected) {
    return badRequest("server 未配置 CHAT_PUBLIC_TOKEN");
  }
  const got = req.headers.get(HEADER_X_CHAT_TOKEN);
  if (got !== expected) {
    return unauthorized();
  }
  return true;
};

const resolveProvider = (): ReturnType<typeof getChatProvider> | Response => {
  try {
    return getChatProvider();
  } catch (error) {
    return Response.json(
      { error: (error as Error).message },
      {
        headers: { [HEADER_CONTENT_TYPE]: MIME_JSON },
        status: HTTP_INTERNAL_SERVER_ERROR,
      },
    );
  }
};

interface SetupState {
  body: z.infer<typeof BodySchema>;
  provider: ReturnType<typeof getChatProvider>;
}

const setupRequest = async (req: NextRequest): Promise<SetupState | Response> => {
  const authResult = checkAuth(req);
  if (authResult !== true) {
    return authResult;
  }

  const parsed = BodySchema.safeParse(await req.json());
  if (!parsed.success) {
    return badRequest(`body 校验失败: ${parsed.error.message}`);
  }

  const providerResult = resolveProvider();
  if (providerResult instanceof Response) {
    return providerResult;
  }

  return { body: parsed.data, provider: providerResult };
};

/** Chat 消息 SSE BFF: 鉴权 + 限流 + 流式转发到 LLM provider
 * @param req - 请求对象
 * @returns SSE 流式 Response
 * @client-bff */
export const POST = async (req: NextRequest): Promise<Response> => {
  // IP 限流: 20 次/分, 超阈值返 429
  const ip = extractClientIp(req.headers);
  const rateResult = checkAndIncrement(`chat:${ip}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_MS);
  if (!rateResult.allowed) {
    return tooManyRequests(rateResult.remaining);
  }

  const setup = await setupRequest(req);
  if (setup instanceof Response) {
    return setup;
  }
  const { body, provider } = setup;

  // provider 事件流 (ReadableStream<ChatEvent>) — 不再做 SSE 编码
  const chatEventStream = new ReadableStream<ChatEvent>({
    async start(controller) {
      try {
        for await (const ev of provider.sendMessage(
          {
            autoGenerateName: body.autoGenerateName,
            conversationId: body.conversationId,
            inputs: body.inputs,
            query: body.query,
            user: body.user,
          },
          req.signal,
        )) {
          controller.enqueue(ev);
        }
      } catch (error) {
        controller.enqueue({
          code: "upstream_error",
          message: (error as Error).message,
          type: "error",
        } as ChatEvent);
      } finally {
        controller.close();
      }
    },
  });

  // AI SDK: 走 JsonToSseTransformStream 自动加 data: 前缀 + \n\n, flush 时补 [DONE]
  // 注: pipeTextStreamToResponse 接收 Node.js ServerResponse, 不适配 App Router Response,
  //     所以这里手写 Response + 显式 SSE 头 (Content-Type / Cache-Control / Connection)
  return new Response(
    chatEventStream
      .pipeThrough(new JsonToSseTransformStream() as unknown as TransformStream<ChatEvent, string>)
      .pipeThrough(new TextEncoderStream()),
    {
      headers: {
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "Content-Type": "text/event-stream",
      },
      status: 200,
    },
  );
};
