// Config.ts 单元测试: resolveUrl 的客户端/服务端分流
// (2026-06-16) 砍 localStorage 鉴权 + catch-all BFF 代理后:
//   - 浏览器端: 所有 /api/* → 同源 (BFF catch-all + 具体路由)
//   - Server 端 (RSC / server action / route.ts): 跨域直连 FastAPI
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock next/headers, 服务端 cookies() 返空
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: () => undefined,
  })),
}));

// Mock 内部 server-only 模块, 避免 Node 环境找不到
vi.mock("server-only", () => ({}));

import { apiFetch, bffProxyResponse } from "./config";
import { HEADER_CONTENT_TYPE, HTTP_NOT_FOUND, HTTP_OK, MIME_JSON } from "@/const";

const getFetchedUrl = (): string =>
  // oxlint-disable-next-line no-magic-numbers -- mock calls 数组索引
  (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;

const mockBrowser = (origin = "http://localhost:3000") =>
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: { location: { origin } },
  });

const mockServer = () =>
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: undefined,
  });

// oxlint-disable-next-line max-statements -- 测试函数需要多步验证
describe("apiFetch URL 解析", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      text: async () => "{}",
    })) as never;
  });

  it("浏览器端 /api/ingest/tasks → 同源 (BFF catch-all 代理)", async () => {
    mockBrowser();
    await apiFetch("/api/ingest/tasks");
    expect(getFetchedUrl()).toBe("http://localhost:3000/api/ingest/tasks");
  });

  it("浏览器端 /api/kg/health → 同源 (BFF catch-all 代理)", async () => {
    mockBrowser();
    await apiFetch("/api/kg/health");
    expect(getFetchedUrl()).toBe("http://localhost:3000/api/kg/health");
  });

  it("浏览器端 /api/account/me → 同源 (BFF catch-all 代理)", async () => {
    mockBrowser();
    await apiFetch("/api/account/me");
    expect(getFetchedUrl()).toBe("http://localhost:3000/api/account/me");
  });

  it("浏览器端 /api/admin/users → 同源 (BFF catch-all 代理)", async () => {
    mockBrowser();
    await apiFetch("/api/admin/users");
    expect(getFetchedUrl()).toBe("http://localhost:3000/api/admin/users");
  });

  it("浏览器端 /api/memory/list → 同源 (BFF catch-all 代理)", async () => {
    mockBrowser();
    await apiFetch("/api/memory/list");
    expect(getFetchedUrl()).toBe("http://localhost:3000/api/memory/list");
  });

  it("浏览器端 query string 透传", async () => {
    mockBrowser();
    await apiFetch("/api/knowledge/batch?task_id=x&page=2");
    expect(getFetchedUrl()).toBe("http://localhost:3000/api/knowledge/batch?task_id=x&page=2");
  });

  it("server 端 /api/kg/health → 跨域直连后端 (无 window, 走 API_BASE)", async () => {
    mockServer();
    await apiFetch("/api/kg/health");
    expect(getFetchedUrl()).toBe("http://127.0.0.1:8000/api/kg/health");
  });

  // 回归 (2026-07-06 P-cleanup): 删 ?? 链后, 设 RAG_BACKEND_URL 必须生效, 不走兜底.
  it("server 端设 RAG_BACKEND_URL → 跨域直连走 env 值, 不走兜底 localhost", async () => {
    mockServer();
    process.env.RAG_BACKEND_URL = "http://staging-backend.internal:9000";
    try {
      vi.resetModules();
      const { apiFetch: apiFetchFresh } = await import("./config");
      await apiFetchFresh("/api/kg/health");
      expect(getFetchedUrl()).toBe("http://staging-backend.internal:9000/api/kg/health");
    } finally {
      delete process.env.RAG_BACKEND_URL;
      vi.resetModules();
    }
  });

  it("server 端 /api/ingest/tasks → 跨域直连后端", async () => {
    mockServer();
    await apiFetch("/api/ingest/tasks");
    expect(getFetchedUrl()).toBe("http://127.0.0.1:8000/api/ingest/tasks");
  });

  it("server 端 /api/account/login → 跨域直连后端 (login 时还没 cookie)", async () => {
    mockServer();
    await apiFetch("/api/account/login", { body: { email: "x", password: "y" }, method: "POST" });
    expect(getFetchedUrl()).toBe("http://127.0.0.1:8000/api/account/login");
  });

  it("完整 URL 直接用 (外部服务 / Dify / OpenAI)", async () => {
    mockBrowser();
    await apiFetch("https://api.dify.ai/v1/chat-messages");
    expect(getFetchedUrl()).toBe("https://api.dify.ai/v1/chat-messages");
  });
});

// BFF 透传工厂单测 (2026-06-28 P4 refactor)

describe("bffProxyResponse", () => {
  it("应该透传 status 和 body", async () => {
    const upstream = new Response('{"ok":true}', {
      status: HTTP_OK,
      headers: { "content-type": "application/json" },
    });
    const result = await bffProxyResponse(upstream);
    expect(result.status).toBe(HTTP_OK);
    expect(await result.text()).toBe('{"ok":true}');
  });

  it("应该用上游 content-type 当默认值", async () => {
    const upstream = new Response("", {
      status: HTTP_OK,
      headers: { "content-type": "text/plain" },
    });
    const result = await bffProxyResponse(upstream);
    expect(result.headers.get("content-type")).toBe("text/plain");
  });

  it("上游无 content-type 应默认 JSON", async () => {
    // Response 构造器会自动注入 text/plain, 手动删掉模拟"上游未设 content-type"
    const upstream = new Response('{"x":1}', { status: HTTP_OK });
    upstream.headers.delete("content-type");
    const result = await bffProxyResponse(upstream);
    expect(result.headers.get(HEADER_CONTENT_TYPE)).toBe(MIME_JSON);
  });

  it("应该透传非 200 状态码", async () => {
    const upstream = new Response('{"error":"x"}', { status: HTTP_NOT_FOUND });
    const result = await bffProxyResponse(upstream);
    expect(result.status).toBe(HTTP_NOT_FOUND);
  });
});
