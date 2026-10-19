// /output page RSC 测试
// (2026-06-14) 不再断言 fetch URL/header (那是 apiFetch 实现细节); 只验证:
//   1) RSC 预取成功 → 客户端 useQuery 接住 → 渲染 input_files[0].name
//   2) fetch 失败 → RSC 不抛 (整页不挂, 客户端 useQuery 重拉 + QueryCache.onError 弹 toast)
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "test-token" } : undefined),
  })),
}));

beforeEach(() => {
  globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
    const urlStr = typeof url === "string" ? url : url.toString();
    // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限 (测试用)
    if (urlStr.includes("/api/permissions/me")) {
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
    return Response.json(
      [
        {
          failed: 0,
          id: "task-rsc",
          input_files: [{ mime: "application/pdf", name: "rsc-doc.pdf", size: 1024 }],
          processed: 1,
          started_at: new Date().toISOString(),
          state: "completed",
          total_files: 1,
        },
      ],
      { headers: { "Content-Type": "application/json" }, status: 200 },
    );
  }) as never;
});

describe("OutputPage (RSC)", () => {
  it("RSC 预取成功 → 客户端 useQuery 接住 → 渲染 input_files[0].name", async () => {
    const mod = await import("./page");
    const page = mod.default;
    const element = await page();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        <QueryClientProvider client={qc}>{element}</QueryClientProvider>
      </NextIntlClientProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText("rsc-doc.pdf")).toBeInTheDocument();
    });
  });

  it("fetch 失败时 RSC 不抛 (HydrationBoundary 包空 cache, 客户端 useQuery 接管重拉)", async () => {
    globalThis.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const mod = await import("./page");
    const page = mod.default;
    // (2026-06-14) prefetchQuery 失败不抛 → RSC 正常 render, 客户端 useQuery 看到 cache miss 会重拉,
    // 重拉失败由 QueryCache.onError 弹 sonner toast, 整页不挂 500.
    await expect(page()).resolves.toBeDefined();
  });
});
