// /health page RSC 测试
// (2026-06-14) 不再断言 fetch URL/header (那是 apiFetch 实现细节); 只验证:
//   1) RSC 预取成功 → 客户端 useQuery 接住 → 渲染 HeroSection 的 ok-count testid
//   2) fetch 失败 → RSC 不抛 (整页不挂, 客户端 useQuery 重拉 + QueryCache.onError 弹 toast)
// (2026-06-17) 旧断言 `getByText("Python 后端")` 失真 — hero-section h1 早是 "监控状态",
//   "Python 后端" 仅在 messages/zh.json 注册但无组件引用. 改用 `health-ok-count` testid
//   (hero-section.tsx:94), 验证 RSC 预取真把数据传过 HydrationBoundary → 客户端 useQuery 接管.
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
// Admin user (super_admin 角色) 用 x-user-token 调 system 端点
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: () => undefined,
  })),
}));

const okPayload = {
  checked_at: "2026-06-12T10:30:00Z",
  // Error/latency_ms 用 null: CheckResult 类型契约是 `T | null` (后端 Python dataclass `None` →
  // JSON null). 不能改 undefined, 否则类型 fail. oxlint 配置禁掉 unicorn/no-null 全局生效.
  dify: { error: null, extra: {}, latency_ms: 120, status: "ok" },
  minio: {
    error: null,
    extra: { backend: "minio", bucket: "rag-ingest", endpoint: "http://minio:9000" },
    latency_ms: 18,
    status: "ok",
  },
  neo4j: { error: null, extra: {}, latency_ms: 45, status: "ok" },
  pgvector: { error: null, extra: {}, latency_ms: 30, status: "ok" },
  python: {
    error: null,
    extra: { uptime_s: 12_345, version: "0.1.0" },
    latency_ms: 0,
    status: "ok",
  },
  system: {
    error: null,
    extra: { cpu_pct: 23.5, gpu: [], mem_pct: 67.2, mem_total_mb: 18_000, mem_used_mb: 12_000 },
    latency_ms: 5,
    status: "ok",
  },
  redis: {
    error: null,
    extra: {},
    latency_ms: 2,
    status: "ok",
  },
};

beforeEach(() => {
  // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限 (测试用), 其他走 health payload
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
    return Response.json(okPayload, {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  }) as never;
});

describe("HealthPage (RSC)", () => {
  it("RSC 预取成功 → 客户端 useQuery 接住 → 渲染 HeroSection ok-count", async () => {
    const mod = await import("./page");
    const pageComponent = mod.default;
    const element = await pageComponent();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>
      </NextIntlClientProvider>,
    );
    // 7 个 service 全 ok (python/dify/neo4j/pgvector/minio/redis/system), 期望 okCount === 7
    await waitFor(() => {
      expect(screen.getByTestId("health-ok-count")).toHaveTextContent("7");
    });
  });

  it("fetch 失败时 RSC 不抛 (客户端 useQuery 接管重拉 + QueryCache.onError 弹 toast)", async () => {
    globalThis.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const mod = await import("./page");
    const pageComponent = mod.default;
    // (2026-06-14) prefetchQuery 失败不抛 → 整页不挂 500, 客户端 useQuery 重拉 → QueryCache.onError 弹 toast.
    await expect(pageComponent()).resolves.toBeDefined();
  });
});
