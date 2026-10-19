// BFF catch-all 代理 (2026-06-16)
// 替代 client → FastAPI 跨域直连: 客户端只 hit Next.js same-origin, 这里读 cookie
// 拿 token → 转发到 FastAPI (带 x-user-token header)
//
// 跟具体路由 (e.g. /api/chat/messages) 共存: Next.js 路由优先级 specific > catch-all,
// 所以 chat/messages 仍走自己的 route.ts (SSE 透传), 不被这个 catch-all 截胡.
//
// 鉴权: 读 cookie (跟 server action 一致, httpOnly 防 XSS).
// 转发: method / body / query / 必要 header 全部透传, response 原样返.
import type { NextRequest } from "next/server";
import { cookies } from "next/headers";
import { API_BASE as BACKEND_URL } from "@/lib/api/config";
import {
  COOKIE_USER_TOKEN,
  HEADER_CONTENT_TYPE,
  HEADER_X_USER_TOKEN,
  HTTP_BAD_GATEWAY,
  HTTP_NO_CONTENT,
  HTTP_NOT_FOUND,
  MIME_JSON,
  ZERO,
} from "@/const";

/** 路由段配置: 强制动态渲染 */
export const dynamic = "force-dynamic";
/** 路由段配置: 使用 Node.js 运行时 */
export const runtime = "nodejs";

const ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"] as const;

/**
 * notFoundResponse - 404 响应
 * @returns 404 JSON 响应
 * @shared
 */
const notFoundResponse = (): Response =>
  Response.json(
    { detail: "Not Found" },
    { headers: { [HEADER_CONTENT_TYPE]: MIME_JSON }, status: HTTP_NOT_FOUND },
  );

/**
 * buildApiPath - 构建 API path 并验证非空
 * @param path - URL path 段数组
 * @returns API 路径或 null
 */
const buildApiPath = (path: string[] | undefined): string | null => {
  const segments = path ?? [];
  if (segments.length === ZERO) {
    return null;
  }
  return `/api/${segments.join("/")}`;
};

/**
 * buildTargetUrl - 拼接目标 URL (含透传 query string)
 * @param apiPath - API 路径
 * @param reqUrl - 原始请求 URL
 * @returns 目标 URL
 */
const buildTargetUrl = (apiPath: string, reqUrl: string): URL => {
  const targetUrl = new URL(apiPath, BACKEND_URL);
  const incoming = new URL(reqUrl);
  for (const [key, val] of incoming.searchParams.entries()) {
    targetUrl.searchParams.append(key, val);
  }
  return targetUrl;
};

/**
 * getAuthHeaders - Server 端鉴权头
 * @returns 鉴权 headers
 */
const getAuthHeaders = async (): Promise<Record<string, string>> => {
  const jar = await cookies();
  const user = jar.get(COOKIE_USER_TOKEN)?.value;
  const out: Record<string, string> = {};
  const tokenValue = user ?? "";
  if (tokenValue) {
    out[HEADER_X_USER_TOKEN] = tokenValue;
  }
  return out;
};

/**
 * SEC-005 防御: 允许的 origin 白名单. 同源请求无需 origin header.
 * server-to-server (curl / 测试 / cron) 无 origin 也放行.
 * 浏览器跨域 fetch 必带 origin header → 不在白名单的 origin 拒.
 */
const ALLOWED_ORIGINS: readonly string[] = ["http://localhost:3000", "http://127.0.0.1:3000"];

/**
 * validateOrigin - 校验 origin 是否在白名单
 * @param origin - 请求 origin header 值 (可能为 null)
 * @returns true 表示放行, false 表示拒绝
 */
const validateOrigin = (origin: string | null): boolean => {
  if (origin === null) {
    return true; // server-to-server
  }
  return ALLOWED_ORIGINS.includes(origin);
};

/**
 * forbiddenResponse - 403 Forbidden 响应
 * @returns 403 JSON 响应
 * @shared
 */
const forbiddenResponse = (): Response =>
  Response.json(
    { detail: "Forbidden: invalid origin" },
    { status: 403, headers: { [HEADER_CONTENT_TYPE]: MIME_JSON } },
  );

/**
 * buildForwardHeaders - 构建转发 headers (auth + Content-Type)
 * @param req - 请求对象
 * @returns 转发 headers
 */
const buildForwardHeaders = async (req: NextRequest): Promise<Record<string, string>> => {
  const authHeaders = await getAuthHeaders();
  const forwardHeaders: Record<string, string> = { ...authHeaders };
  const contentType = req.headers.get(HEADER_CONTENT_TYPE);
  if (contentType) {
    forwardHeaders[HEADER_CONTENT_TYPE] = contentType;
  }
  return forwardHeaders;
};

/**
 * extractRequestBody - 提取请求体 (GET/HEAD 跳过)
 * @param req - 请求对象
 * @param method - HTTP 方法
 * @returns 请求体或 undefined
 */
const extractRequestBody = async (
  req: NextRequest,
  method: string,
): Promise<BodyInit | undefined> => {
  if (method === "GET" || method === "HEAD") {
    return undefined;
  }
  return req.arrayBuffer();
};

/**
 * proxyErrorResponse - 上游不可达错误响应
 * @param error - 错误对象
 * @returns 502 JSON 响应
 */
const proxyErrorResponse = (error: unknown): Response =>
  Response.json(
    { detail: `upstream 不可达: ${(error as Error).message}` },
    { headers: { [HEADER_CONTENT_TYPE]: MIME_JSON }, status: HTTP_BAD_GATEWAY },
  );

/**
 * buildUpstreamHeaders - 构建转发响应 headers (透传 content-type)
 * @param upstream - 上游响应
 * @returns 转发 headers
 */
const buildUpstreamHeaders = (upstream: Response): Headers => {
  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  if (upstreamContentType) {
    responseHeaders.set(HEADER_CONTENT_TYPE, upstreamContentType);
  }
  return responseHeaders;
};

/**
 * ForwardOptions - 上游请求选项
 * @property body - 请求体
 * @property headers - 请求头
 * @property method - HTTP 方法
 * @property signal - AbortSignal
 */
interface ForwardOptions {
  body: BodyInit | undefined;
  headers: Record<string, string>;
  method: string;
  signal: AbortSignal;
}

/**
 * forwardRequest - 执行上游 fetch 并返回透传 response
 * @param url - 上游 URL
 * @param options - 请求选项
 * @returns Response
 */
const forwardRequest = async (url: string, options: ForwardOptions): Promise<Response> => {
  let upstream: Response | undefined = undefined;
  try {
    upstream = await fetch(url, {
      body: options.body,
      headers: options.headers,
      method: options.method,
      signal: options.signal,
    });
  } catch (error) {
    return proxyErrorResponse(error);
  }
  const responseHeaders = buildUpstreamHeaders(upstream);
  return new Response(upstream.body, { headers: responseHeaders, status: upstream.status });
};

/**
 * proxy - 主代理逻辑
 * @param req - 请求对象
 * @param params - 路由参数
 * @param method - HTTP 方法
 * @returns Response
 */
const proxy = async (
  req: NextRequest,
  params: { path: string[] },
  method: string,
): Promise<Response> => {
  if (!validateOrigin(req.headers.get("origin"))) {
    return forbiddenResponse();
  }
  const apiPath = buildApiPath(params.path);
  if (!apiPath) {
    return notFoundResponse();
  }
  const targetUrl = buildTargetUrl(apiPath, req.url);
  const forwardHeaders = await buildForwardHeaders(req);
  const body = await extractRequestBody(req, method);
  return forwardRequest(targetUrl.toString(), {
    body,
    headers: forwardHeaders,
    method,
    signal: req.signal,
  });
};

const handler =
  (method: (typeof ALLOWED_METHODS)[number]) =>
  async (req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) =>
    proxy(req, await ctx.params, method);

/** @client-bff */
export const GET = handler("GET");
/** @client-bff */
export const POST = handler("POST");
/** @client-bff */
export const PUT = handler("PUT");
/** @client-bff */
export const DELETE = handler("DELETE");
/** @client-bff */
export const PATCH = handler("PATCH");

/** OPTIONS 预检 BFF: 直接返 204 空响应
 * @returns 204 空响应
 * @client-bff */
export const OPTIONS = async (): Promise<Response> =>
  new Response(null, { status: HTTP_NO_CONTENT });
