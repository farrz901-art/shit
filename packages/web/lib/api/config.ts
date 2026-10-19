// 后端 API base URL + 纯 transport 封装 (URL + fetch + 错误归一)
//
// (2026-06-16) 砍鉴权逻辑: apiFetch 不再注入 header.
// 鉴权分层:
//   - 浏览器端: cookie 由浏览器自动带, BFF catch-all 代理 (app/api/[...path]/route.ts) 读
//   - Server 端: 调用方自己从 cookies() 读 token, 注入 headers: { "x-user-token": ... }
//     (rsc-queries.ts / RSC 页面 / server action / BFF route.ts)
//
// 鉴权不是 transport 关注的事, 抽到调用方更显式.
// Server-only 模块 (auth.server.ts) 只被 server-only 模块 import, client chain 干净.
//
// 客户端: useQuery/useMutation 的 queryFn / mutationFn 用 apiFetch()
// 服务端: server action / RSC 页面 / route.ts 直接调 apiFetch(), 显式传 auth headers
//
// 不在 RSC 内部用 useQuery (会跟 RQ 客户端 hook 冲突), 改用
// Rsc-queries.ts 的 prefetch + HydrationBoundary 模式

const FALLBACK = "http://127.0.0.1:8000";

/**
 * 后端 (FastAPI) base URL, 仅供 server 端使用 (RSC / route.ts / server action).
 * 浏览器端走同源 BFF (app/api/[...path]/route.ts catch-all + 具体路由), 不依赖此变量.
 * 优先级: RAG_BACKEND_URL env → 兜底 http://127.0.0.1:8000.
 * docker 部署见 docker/rag-docker-compose.yml (运行时 environment 覆盖).
 */
export const API_BASE = process.env.RAG_BACKEND_URL ?? FALLBACK;

import { ApiError, getErrorMessage, NetworkError } from "./errors";
import { NextResponse } from "next/server";
import { HEADER_CONTENT_TYPE, HTTP_NO_CONTENT, MIME_JSON } from "@/const";

type ApiFetchInit = Omit<RequestInit, "body" | "headers"> & {
  body?: unknown; // Object → JSON.stringify, string/FormData/Blob → 原样传
  headers?: Record<string, string>; // 调用方显式覆盖 (e.g. content-type)
};

/**
 * 包装 fetch: 网络错误归一化为 NetworkError (底层连接失败 / DNS / abort)
 * 4xx/5xx 不在此处理, 由调用方检查 res.ok
 */
const fetchWithNetworkError = async (url: string, init: RequestInit): Promise<Response> => {
  try {
    return await fetch(url, init);
  } catch (error) {
    const errorMessageText = getErrorMessage(error);
    throw new NetworkError(errorMessageText);
  }
};

/**
 * 统一 fetch: 拼 URL + JSON 序列化 + 错误归一化 (纯 transport, 无鉴权)
 *
 * 鉴权由调用方负责:
 *   - 浏览器: 不传, cookie 由浏览器自动带, BFF 读
 *   - Server:  传 { headers: { "x-user-token": await getServerToken() } } 显式注入
 *
 * @param path 后端相对路径 (e.g. "/api/kg/stats")
 * @param init 透传 fetch options; body 若是 plain object 自动 JSON.stringify
 * @returns 解析后的 JSON
 * @throws NetworkError 底层 fetch 失败 (ECONNREFUSED / DNS / abort)
 * @throws ApiError 业务错误 (4xx/5xx), .status + .message 可读
 */
// oxlint-disable-next-line id-length -- 泛型 T 是 TypeScript 惯例
export const apiFetch = async <T = unknown>(path: string, init: ApiFetchInit = {}): Promise<T> => {
  const { body, headers: extraHeaders, ...rest } = init;
  const url = resolveUrl(path, API_BASE);
  const { bodyInit, finalHeaders } = serializeRequest(body, extraHeaders);

  const res = await fetchWithNetworkError(url, { ...rest, body: bodyInit, headers: finalHeaders });

  if (!res.ok) {
    throw new ApiError(res.status, await parseErrorDetail(res));
  }

  return parseResponseBody<T>(res);
};

/**
 * 拼 URL: 浏览器 / server 两种情况
 * - 浏览器: /api/* 全走 BFF 同源 (app/api/[...path] catch-all 代理)
 *   这样 cookie 自动带 (same-origin) + 避免 CORS 跨域
 * - Server (RSC / server action / route.ts): 跨域到 API_BASE 直连 FastAPI
 *   server 进程不受 CORS 限制, 但 cookie 不会自动带, 靠 resolveServerAuthHeader 注
 * - 已含 http(s)://: 原样用 (外部服务)
 */
const resolveUrl = (path: string, host: string): string => {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  // oxlint-disable-next-line unicorn/prefer-global-this -- 检测浏览器环境
  if (typeof window !== "undefined" && path.startsWith("/api/")) {
    return new URL(path, globalThis.location.origin).toString();
  }
  return `${host}${path}`;
};

/**
 * Body 序列化 + 合并 headers
 * object → JSON + 自动 Content-Type; FormData/Blob/ArrayBuffer/string 原样
 */
const serializeRequest = (
  body: unknown,
  extraHeaders: Record<string, string> | undefined,
): { bodyInit: BodyInit | undefined; finalHeaders: Record<string, string> } => {
  const finalHeaders: Record<string, string> = { ...extraHeaders };
  if (body === undefined || body === null) {
    return { bodyInit: undefined, finalHeaders };
  }
  if (
    body instanceof FormData ||
    body instanceof Blob ||
    body instanceof ArrayBuffer ||
    typeof body === "string"
  ) {
    return { bodyInit: body as BodyInit, finalHeaders };
  }
  finalHeaders[HEADER_CONTENT_TYPE] ??= MIME_JSON;
  return { bodyInit: JSON.stringify(body), finalHeaders };
};

/**
 * 4xx/5xx body 提取 detail: 优先 body.detail, 否则 statusText
 * 跟成功路径一致用 res.text() (统一走 text, 避免 mock 必须同时有 text + json)
 * (2026-06-28 P3 refactor) 提升为 public export: lib/api/ingest.ts 重用
 */
export const parseErrorDetail = async (res: Response): Promise<string> => {
  const text = await res.text().catch(() => "");
  try {
    const body = JSON.parse(text);
    if (typeof body === "object" && body && "detail" in body) {
      return String(body.detail);
    }
  } catch {
    // 非 JSON, 走 statusText
  }
  return res.statusText;
};

/**
 * 成功 body 解析: 204/空 → undefined; 否则优先 JSON, 失败返原文
 */
// oxlint-disable-next-line id-length -- 泛型 T 是 TypeScript 惯例
const parseResponseBody = async <T>(res: Response): Promise<T> => {
  if (res.status === HTTP_NO_CONTENT) {
    return undefined as T;
  }
  const text = await res.text();
  if (!text) {
    return undefined as T;
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
};

/**
 * 透传 fetch (BFF 路由用): 不解析 body, 不归一错误, 原样返 Response
 *
 * 跟 apiFetch 的区别:
 * - 不 throw, 4xx/5xx 仍返 Response (BFF 路由要透传 status + body 给 client)
 * - 不 parse JSON, 返 raw text 走 NextResponse (上游可能是 JSON / Blob / stream)
 * - 不强制 Content-Type (BFF 转发 multipart, boundary 由上游定)
 *
 * 鉴权: BFF 路由自己注入 (读 cookie 拼 x-user-token header)
 *
 * @param init.base override 默认的 API_BASE (用于外部服务 Dify/OpenAI, 拼不同 host)
 */
export const apiProxy = async (
  path: string,
  init: ApiFetchInit & { base?: string } = {},
): Promise<Response> => {
  const { body, headers: extraHeaders, base, ...rest } = init;
  // 外部服务 (Dify/OpenAI) 走 base 时自带鉴权 (Bearer key), 不需要本项目 auth
  const host = base ?? API_BASE;
  const url = resolveProxyUrl(path, host, base);
  const { bodyInit, finalHeaders } = serializeRequest(body, extraHeaders);
  return fetch(url, { ...rest, body: bodyInit, headers: finalHeaders });
};

/**
 * ApiProxy 专用 URL 拼装: 当传 base (外部服务) 时, /api/ 路径不视作同源
 * (走外部 host 而不是 globalThis.location.origin)
 */
const resolveProxyUrl = (path: string, host: string, base: string | undefined): string => {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  // oxlint-disable-next-line unicorn/prefer-global-this -- 检测浏览器环境
  if (!base && path.startsWith("/api/") && typeof window !== "undefined") {
    return new URL(path, globalThis.location.origin).toString();
  }
  return `${host}${path}`;
};

/**
 * BFF 透传工厂 (2026-06-28 P4 refactor): 把上游 Response 包成 NextResponse.
 * 替 13 处重复的 `new NextResponse(await resp.text(), { headers: {...}, status: resp.status })`.
 *
 * @param upstream 上游 Response (e.g. apiProxy() 返回)
 * @returns NextResponse with 透传 status + body + content-type (兜底 JSON)
 */
export const bffProxyResponse = async (upstream: Response): Promise<NextResponse> => {
  const contentType = upstream.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON;
  const body = await upstream.text();
  return new NextResponse(body, {
    headers: { [HEADER_CONTENT_TYPE]: contentType },
    status: upstream.status,
  });
};

/**
 * BFF 文件下载工厂 (2026-06-29 P4 §4.1): 在 bffProxyResponse 基础上强制设置
 * Content-Disposition 触发浏览器下载 + 覆盖 Content-Type 为自定义 mime.
 * 替 evaluate/template 等 1 处文件下载 BFF 的 12 行模板.
 *
 * @param upstream 上游 Response (e.g. apiProxy() 返回)
 * @param options.filename 下载文件名 (浏览器 Save As 默认值)
 * @param options.mime 自定义 mime type (e.g. "text/csv; charset=utf-8"), 不传则透传上游
 * @returns NextResponse with 下载头 + 透传 status/body
 */
export const bffDownloadResponse = async (
  upstream: Response,
  options: { filename: string; mime?: string },
): Promise<NextResponse> => {
  const upstreamContentType = upstream.headers.get(HEADER_CONTENT_TYPE);
  const contentType = options.mime ?? upstreamContentType ?? MIME_JSON;
  const body = await upstream.text();
  return new NextResponse(body, {
    headers: {
      "content-disposition": `attachment; filename="${options.filename}"`,
      [HEADER_CONTENT_TYPE]: contentType,
    },
    status: upstream.status,
  });
};
