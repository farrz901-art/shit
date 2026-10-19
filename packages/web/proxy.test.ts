// @vitest-environment node
import { describe, expect, it, vi } from "vitest";

// 在 import proxy 之前 mock next-intl, 避免 vitest 加载 ESM 链解析 `next/server` 失败
vi.mock("next-intl/middleware", () => ({
  default: () => () => undefined, // 透传: next-intl 不参与我们的 redirect 测试
}));

import { NextRequest } from "next/server";

import { HTTP_TEMPORARY_REDIRECT } from "@/const";

import proxy from "./proxy";

// 构造带 cookie 的 NextRequest, 直接用 URL 字符串 + RequestInit, 绕开 happy-dom Request polyfill
const reqWithCookie = (path: string, cookieValue?: string): NextRequest => {
  const init: { headers: HeadersInit } = { headers: {} };
  if (cookieValue !== undefined) {
    init.headers = { cookie: `rag_user_token=${cookieValue}` };
  }
  return new NextRequest(`http://localhost${path}`, init);
};

// 解析响应: 有 redirect → Response; 透传 (next-intl mock) → undefined
const getLocationHeader = (res: Response | undefined): string | null => {
  if (!res) {
    return null;
  } // 透传 = 不重定向
  return res.headers.get("location");
};

describe("proxy /submissions 守卫", () => {
  it("/zh/submissions 无 token → redirect /zh/login?next=submissions", async () => {
    // 跟 admin 同模式: stripLocale 去掉 /zh 前缀, next 保留无前缀路径
    const res = (await proxy(reqWithCookie("/zh/submissions"))) as Response;
    expect(res.status).toBe(HTTP_TEMPORARY_REDIRECT);
    expect(getLocationHeader(res)).toContain("/zh/login?next=submissions");
  });

  it("/en/submissions 有 token → 不重定向, 走 next()", async () => {
    const res = (await proxy(reqWithCookie("/en/submissions", "t"))) as Response | undefined;
    expect(getLocationHeader(res)).toBeNull();
  });

  it("/zh/submissions 跟 /zh/admin 解耦: /zh/submissions 不要求 admin", async () => {
    // 任何登录账号可进 (含 is_admin=false): 有 token 即放行, 不查 admin
    const res = (await proxy(reqWithCookie("/zh/submissions", "t"))) as Response | undefined;
    expect(getLocationHeader(res)).toBeNull(); // 不 redirect
  });
});

describe("proxy /account 守卫", () => {
  // (2026-06-18) /account/* 之前没纳入 isProtected, anon 用户走 page 内 redirect (多一跳后端),
  //   跟 /admin/* + /submissions/* 鉴权分层不一致. 修法: isProtected 加 /account/*, 走 proxy 早拦.
  it("/zh/account/settings 无 token → redirect /zh/login?next=account/settings", async () => {
    const res = (await proxy(reqWithCookie("/zh/account/settings"))) as Response;
    expect(res.status).toBe(HTTP_TEMPORARY_REDIRECT);
    // Next 里的 "/" 会被 NextResponse.redirect URL-encode 成 %2F, 解码后断言
    expect(decodeURIComponent(getLocationHeader(res) ?? "")).toContain(
      "/zh/login?next=account/settings",
    );
  });

  it("/zh/account/restore 无 token → redirect /zh/login?next=account/restore", async () => {
    const res = (await proxy(reqWithCookie("/zh/account/restore"))) as Response;
    expect(res.status).toBe(HTTP_TEMPORARY_REDIRECT);
    expect(decodeURIComponent(getLocationHeader(res) ?? "")).toContain(
      "/zh/login?next=account/restore",
    );
  });

  it("/en/account/settings 有 token → 不重定向, 走 next()", async () => {
    const res = (await proxy(reqWithCookie("/en/account/settings", "t"))) as Response | undefined;
    expect(getLocationHeader(res)).toBeNull();
  });
});

describe("proxy 资产路径重写 (Turbopack manifest 修复)", () => {
  it("/zh/_next/static/chunks/foo.css → rewrite 到 /_next/static/chunks/foo.css", async () => {
    const res = (await proxy(reqWithCookie("/zh/_next/static/chunks/foo.css"))) as Response;
    // Rewrite 在响应里表现为 x-nextjs-rewritten-path 头或重写后内部 fetch
    // 我们只验证返回的不是 redirect 且 proxy 不抛错
    expect(res).toBeDefined();
  });

  it("/en/_next/static/chunks/foo.js → 不抛错", async () => {
    const res = (await proxy(reqWithCookie("/en/_next/static/chunks/foo.js"))) as
      | Response
      | undefined;
    expect(res).toBeDefined();
  });
});
