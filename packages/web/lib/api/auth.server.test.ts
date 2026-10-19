// Server-only 鉴权测试: getServerToken() + authHeaders().
// 旧: 跟 client 测试混在 auth.test.ts. 新: 拆到 auth.server.test.ts,
// 因为 auth.server.ts 顶部 import "server-only", 跟 cookies() 一样, 只能在
// Server-side 跑 (vitest 里 mock 成空 module).
import { describe, expect, it, vi } from "vitest";

// Mock server-only: auth.server.ts 顶部 import "server-only" (Next.js marker),
// 在 vitest jsdom 环境没有这个 module, mock 成空 module 让 import 解析通过.
vi.mock("server-only", () => ({}));

// Mock next/headers: 模拟 Next 16 的 async cookies() API
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => {
      const map: Record<string, { value: string }> = {
        rag_user_token: { value: "user-tok" },
      };
      return map[key];
    },
  })),
}));

import { getServerToken, authHeaders } from "./auth.server";

describe("getServerToken", () => {
  it("两 token 同存: 返 user token (admin cookie 已不读)", async () => {
    expect(await getServerToken()).toBe("user-tok");
  });

  it("无 admin 时回退 user token", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValueOnce({
      get: (key: string) => {
        if (key === "rag_user_token") {
          return { value: "user-only" };
        }
        return undefined;
      },
    } as never);
    expect(await getServerToken()).toBe("user-only");
  });

  it("都没时返空字符串", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValueOnce({
      get: () => undefined,
    } as never);
    expect(await getServerToken()).toBe("");
  });
});

describe("authHeaders", () => {
  // (2026-06-24) 后端 resolve_user 不识别 x-admin-token, 统一注 x-user-token.
  it("两 token 同存: 返 x-user-token (user 优先, admin 不再单独注头)", async () => {
    expect(await authHeaders()).toEqual({ "x-user-token": "user-tok" });
  });

  it("只有 user token 时: 返 x-user-token", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValueOnce({
      get: (key: string) => {
        if (key === "rag_user_token") {
          return { value: "user-only" };
        }
        return undefined;
      },
    } as never);
    expect(await authHeaders()).toEqual({ "x-user-token": "user-only" });
  });

  it("都没时: 返空对象 (BFF 透传空 headers, 后端走 RAG_DEV_AUTH 默认用户)", async () => {
    const { cookies } = await import("next/headers");
    vi.mocked(cookies).mockResolvedValueOnce({
      get: () => undefined,
    } as never);
    expect(await authHeaders()).toEqual({});
  });
});
