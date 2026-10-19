// /knowledge RSC 测试 (2026-06-14, 改成 redirect 模式):
//   之前 page 是 KnowledgeDashboard (stat 卡 + 录入入口), 现在是 redirect("/knowledge/documents")
//   - 测 redirect() 被调用且目标 URL 对
//   - 测不调 fetch (知识库 dashboard 整页删, documents 子页自己拉 stats)
import { describe, expect, it, vi } from "vitest";

const EXPECTED_REDIRECT_CALLS = 1;
const FIRST_ARGUMENT_INDEX = 0;

// Mock next/navigation redirect: 真实行为是抛 NEXT_REDIRECT, vitest 把这当未处理抛错
// 用 vi.fn() 替代, 走 setRedirect 标记
const mockRedirect = vi.fn();
vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    mockRedirect(url);
  },
}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

// (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限 (知识库 key 在 allowed)
globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
  const urlString = typeof url === "string" ? url : url.toString();
  if (urlString.includes("/api/permissions/me")) {
    return Response.json(
      {
        allowed: [
          "chat",
          "output",
          "knowledge",
          "evaluate",
          "submissions",
          "decode",
          "health",
          "admin",
        ],
        pages: [],
        role: "admin",
      },
      { headers: { "Content-Type": "application/json" }, status: 200 },
    );
  }
  return new Response("not mocked", { status: 404 });
}) as never;

describe("KnowledgePage (redirect)", () => {
  it("redirect 到 /knowledge/documents", async () => {
    mockRedirect.mockClear();
    const mod = await import("./page");
    const knowledgePage = mod.default;
    await knowledgePage();
    expect(mockRedirect).toHaveBeenCalledTimes(EXPECTED_REDIRECT_CALLS);
    expect(mockRedirect).toHaveBeenCalledWith("/knowledge/documents");
  });

  it("不调业务 fetch (重定向无副作用, stats 让 documents 子页自己拉)", async () => {
    // (2026-06-17) v2 RBAC: PageGuard 内部会调 /api/permissions/me 拿权限, 这个调用是允许的;
    //   测的是不调 /api/kg/stats 等业务端点
    mockRedirect.mockClear();
    const fetchSpy = vi.fn(async (url: string | URL | Request) => {
      const urlString = typeof url === "string" ? url : url.toString();
      if (urlString.includes("/api/permissions/me")) {
        return Response.json(
          {
            allowed: [
              "chat",
              "output",
              "knowledge",
              "evaluate",
              "submissions",
              "decode",
              "health",
              "admin",
            ],
            pages: [],
            role: "admin",
          },
          { headers: { "Content-Type": "application/json" }, status: 200 },
        );
      }
      return new Response("not mocked", { status: 404 });
    });
    globalThis.fetch = fetchSpy as never;
    const mod = await import("./page");
    const knowledgePage = mod.default;
    await knowledgePage();
    const urls = fetchSpy.mock.calls.map((call) => call[FIRST_ARGUMENT_INDEX] as string);
    expect(urls.some((url) => url.includes("/api/kg/stats"))).toBe(false);
  });
});
