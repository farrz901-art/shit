// @vitest-environment node
// /api/auth/anon BFF 的纯函数测试
// (2026-06-14) BFF 缺失导致 401, 这里测"上游 Response → NextResponse 透传"行为
// - 200: status + body + Set-Cookie 全部透传
// - 4xx: status + body 透传 (BFF 兜底返同 status)
// - 5xx: 透传
// - 没有 set-cookie: 也不报错, 头为空
import { describe, expect, it } from "vitest";
import { proxyAuthResponse } from "./proxy";
import { HTTP_INTERNAL_SERVER_ERROR, HTTP_OK, HTTP_UNAUTHORIZED } from "@/const";

const makeUpstream = (opts: {
  status: number;
  body: string;
  setCookie?: string[];
  contentType?: string;
}): Response => {
  const headers = new Headers();
  if (opts.contentType) {
    headers.set("content-type", opts.contentType);
  }
  const cookieValues: string[] = [];
  if (opts.setCookie) {
    for (const cookie of opts.setCookie) {
      headers.append("set-cookie", cookie);
      cookieValues.push(cookie);
    }
  }
  const response = new Response(opts.body, { headers, status: opts.status });
  // Happy-dom Headers 没实现 getSetCookie() (Node 18+ API), polyfill
  if (typeof response.headers.getSetCookie !== "function") {
    Object.defineProperty(response.headers, "getSetCookie", {
      value: () => cookieValues,
      writable: true,
    });
  }
  return response;
};

describe("proxyAuthResponse", () => {
  it("200: status + body + set-cookie 透传", async () => {
    const upstream = makeUpstream({
      body: JSON.stringify({ token: "abc123" }),
      contentType: "application/json",
      setCookie: ["rag_user_token=abc123; Max-Age=604800; Path=/; HttpOnly; SameSite=Lax"],
      status: 200,
    });
    const out = await proxyAuthResponse(upstream);
    expect(out.status).toBe(HTTP_OK);
    expect(out.headers.get("set-cookie")).toContain("rag_user_token=abc123");
    // NextResponse 跟 Response 是兼容结构, await text() 验证 body
    expect(await out.text()).toBe(JSON.stringify({ token: "abc123" }));
  });

  it("401: status + body 透传 (后端返 '缺少 x-user-token' 时不再 404)", async () => {
    const upstream = makeUpstream({
      body: JSON.stringify({ detail: "缺少 x-user-token" }),
      contentType: "application/json",
      status: 401,
    });
    const out = await proxyAuthResponse(upstream);
    expect(out.status).toBe(HTTP_UNAUTHORIZED);
    expect(await out.text()).toBe(JSON.stringify({ detail: "缺少 x-user-token" }));
  });

  it("500: 透传", async () => {
    const upstream = makeUpstream({
      body: JSON.stringify({ detail: "token 碰撞, 重试" }),
      contentType: "application/json",
      status: 500,
    });
    const out = await proxyAuthResponse(upstream);
    expect(out.status).toBe(HTTP_INTERNAL_SERVER_ERROR);
  });

  it("没 set-cookie 也不报错, 头空", async () => {
    const upstream = makeUpstream({
      body: "{}",
      contentType: "application/json",
      status: 200,
    });
    const out = await proxyAuthResponse(upstream);
    expect(out.headers.get("set-cookie")).toBeNull();
  });
});
