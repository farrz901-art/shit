// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const COOKIE_VALUE = "test-token-abc";
const STATUS_OK = 200;
const STATUS_FORBIDDEN = 403;
const LOCALHOST_ORIGIN = "http://localhost:3000";

beforeEach(async () => {
  vi.resetModules();
  // Mock next/headers cookies
  vi.mock("next/headers", () => ({
    cookies: async () => ({
      get: (name: string) => (name === "rag_user_token" ? { value: COOKIE_VALUE } : undefined),
    }),
  }));
  // Mock global fetch — 不让真请求出去
  globalThis.fetch = vi.fn(async () => new Response("ok", { status: STATUS_OK })) as never;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("catch-all /api/[...path] — origin 白名单 (SEC-005)", () => {
  it("origin 在白名单 → 正常转发", async () => {
    process.env.NEXT_PUBLIC_API_BASE = "http://localhost:8000";
    const { GET } = await import("./route");
    // 用 NextRequest 绕开 happy-dom Request polyfill (Origin 是 forbidden header)
    // eslint-disable-next-line new-cap -- BFF handler 调用
    const resp = await GET(
      new NextRequest("http://localhost:3000/api/health/check", {
        headers: { origin: LOCALHOST_ORIGIN },
      }) as never,
      {
        params: Promise.resolve({ path: ["health", "check"] }),
      },
    );
    expect(resp.status).toBe(STATUS_OK);
  });

  it("origin 不在白名单 → 403 Forbidden", async () => {
    process.env.NEXT_PUBLIC_API_BASE = "http://localhost:8000";
    const { GET } = await import("./route");
    // eslint-disable-next-line new-cap -- BFF handler 调用
    const resp = await GET(
      new NextRequest("http://localhost:3000/api/health/check", {
        headers: { origin: "http://evil.com" },
      }) as never,
      {
        params: Promise.resolve({ path: ["health", "check"] }),
      },
    );
    expect(resp.status).toBe(STATUS_FORBIDDEN);
    expect(await resp.text()).toContain("Forbidden");
  });

  it("无 origin header (server-to-server) → 仍允许", async () => {
    process.env.NEXT_PUBLIC_API_BASE = "http://localhost:8000";
    const { GET } = await import("./route");
    // eslint-disable-next-line new-cap -- BFF handler 调用
    const resp = await GET(new NextRequest("http://localhost:3000/api/health/check") as never, {
      params: Promise.resolve({ path: ["health", "check"] }),
    });
    expect(resp.status).toBe(STATUS_OK);
  });
});
