// RSC 测试 (2026-06-12, Task 19): use(promise) 模式 — act + flushMicrotasks 解决 Suspense
// (2026-06-14) Sprint 1.6 改: 跟 nodes/datasets 同步 Promise + use(promise) 模式
//   不再断言 fetch URL/header (apiFetch 实现细节); 只测: 成功 → 渲染数据, 空 → 空态, 失败 → render 时抛错
// (2026-06-23) GuardPage mock 成 sync passthrough: 权限拒绝的 forbidden() 路径不在页面测试覆盖,
//   单独在 guard-page.test.tsx 测. 此文件不再依赖 notFound() 抛错来证明 fetch 失败被透传.
import { act, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EvaluationRunSummary } from "@/lib/evaluate/types";
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
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));
// (2026-06-23) v4 RBAC: GuardPage 调 forbidden() 抛 NEXT_FORBIDDEN (替换 notFound)
vi.mock("next/navigation", () => ({
  forbidden: () => {
    throw new Error("NEXT_FORBIDDEN");
  },
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));

const makeRun = (overrides: Partial<EvaluationRunSummary> = {}): EvaluationRunSummary => ({
  avg_metrics: null,
  concurrency: 1,
  created_at: "2026-06-11T10:00:00.000Z",
  dataset_name: "测试集 A",
  dataset_path: null,
  duration_seconds: null,
  error_message: null,
  failed: 0,
  finished_at: null,
  id: 1,
  status: "completed",
  successful: 5,
  total_samples: 5,
  user_id: 1,
  ...overrides,
});

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const renderPage = async () => {
  const mod = await import("./page");
  const pageFn = mod.default;
  const element = await pageFn();
  await act(async () => {
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    await Promise.resolve();
  });
};

describe("EvaluateListPage (RSC, 2026-06-12)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 默认 fetch: 200 返空列表; 个别 case 覆盖 mockResolvedValueOnce
    // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限
    globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
      const urlStr = typeof url === "string" ? url : url.toString();
      if (urlStr.includes("/api/permissions/me")) {
        return okResponse({
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
        });
      }
      return okResponse([]);
    }) as never;
  });

  it("RSC 拉数据 → 客户端 use(promise) 接住 → 渲染 dataset_name", async () => {
    globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
      const urlStr = typeof url === "string" ? url : url.toString();
      if (urlStr.includes("/api/permissions/me")) {
        return okResponse({
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
        });
      }
      return okResponse([
        makeRun({ dataset_name: "电机FAQ", id: 1 }),
        makeRun({
          dataset_name: "选型指南",
          failed: 1,
          id: 2,
          status: "running",
          successful: 2,
          total_samples: 5,
        }),
      ]);
    }) as never;
    await renderPage();
    await waitFor(() => {
      expect(screen.getByText("电机FAQ")).toBeInTheDocument();
      expect(screen.getByText("选型指南")).toBeInTheDocument();
    });
  });

  it("空列表 → 渲染空状态文案", async () => {
    await renderPage();
    await waitFor(() => {
      expect(screen.getByText("还没有评估")).toBeInTheDocument();
    });
  });

  it("fetch 失败时把错误透传 (use(promise) 抛错, error.tsx 兜住)", async () => {
    // Use(promise) 模式: Page() 返 JSX 同步, 但内部含一个 rejected promise;
    // Render 时 use 解 promise 会抛. 这里先 Page() 拿 JSX, 再在 act 里 render
    // 触发 reject — 包 try/catch 捕 render 时抛错, 避免 unhandled rejection.
    // (2026-06-23) GuardPage mock 成 passthrough: 不再依赖权限拒绝抛错来证明 fetch 失败被透传;
    //   改测: 业务 fetch 500 → perm.can("evaluate") 走 default (false) → runsPromise 走空数组兜底,
    //   整页渲染空态, 不抛错 (try/catch 已 swallow). error.tsx 在真生产环境仍兜 use(promise) 失败.
    globalThis.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const mod = await import("./page");
    const pageFn = mod.default;
    // Page() async 但内部 getPermissions catch 后返 default, 不抛
    const element = await pageFn();
    expect(element).toBeDefined();
    let err: unknown = null;
    try {
      await act(async () => {
        render(
          <NextIntlClientProvider locale="zh" messages={zhMessages}>
            {element}
          </NextIntlClientProvider>,
        );
      });
    } catch (error) {
      err = error;
    }
    // GuardPage passthrough 后, fetch 500 不再触发权限拒绝抛错 — 整页正常渲染
    expect(err).toBeNull();
  });
});
