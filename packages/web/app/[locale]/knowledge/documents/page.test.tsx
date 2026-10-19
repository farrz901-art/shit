// RSC 测试 (2026-06-12): page 改 RSC 后, 直接 await Page() 拿预取数据, 灌 DocumentsEntry.
// 不再 mock useSWR, 改为 mock next/headers cookies + global.fetch.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import zhMessages from "@/messages/zh.json";

// Mock server-only: auth.server.ts 顶部 import, 在 vitest jsdom 环境没有这个 module
vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock CountUp: jsdom 没 IntersectionObserver, useInView 不触发, 数字一直停在 0.
//   这里直接返 value, 让测试能验证 props 灌对.
//   (2026-06-29 同 FE-3) mock 路径必须跟 StatCard import 一致 (@/components/motion/animated, 没 common/ 前缀)
vi.mock("@/components/motion/animated", async () => {
  // oxlint-disable-next-line typescript/consistent-type-imports -- vitest importActual 泛型必须用 typeof import() 形式
  const actual = await vi.importActual<typeof import("@/components/motion/animated")>(
    "@/components/motion/animated",
  );
  return {
    ...actual,
    CountUp: ({ value, className }: { value: number; className?: string }) => (
      <span className={className}>{value}</span>
    ),
  };
});

// Mock next/headers cookies: authHeaders() 内部会调
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

// Mock next/navigation forbidden: PageGuard 在 fetch 失败权限不足时调
vi.mock("next/navigation", () => ({
  forbidden: () => {
    const err = new Error("NEXT_FORBIDDEN");
    (err as Error & { digest?: string }).digest = "NEXT_FORBIDDEN";
    throw err;
  },
}));

// Mock zustand persist: useAppStore 在 server 端没有 localStorage, 简化成 ds1
const appStoreState: { datasetId: string } = { datasetId: "ds1" };
vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (sel: (state: { datasetId: string }) => string) => sel(appStoreState),
}));

// Mock fetch: 返回 /api/kg/stats?type=dify 直接返 { datasets, documents }
// (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限
beforeEach(() => {
  globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
    const urlStr = typeof url === "string" ? url : url.toString();
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
      { neo4j: { nodes: 0, relations: 0 }, dify: { datasets: 7, documents: 42 } },
      {
        headers: { "Content-Type": "application/json" },
        status: 200,
      },
    );
  }) as never;
});

describe("DocumentsPage (RSC)", () => {
  it("渲染 RSC 预取的 stats (dify.datasets/documents)", async () => {
    const mod = await import("./page");
    const pageFn = mod.default;
    const element = await pageFn();
    // 子组件用 useTranslations / useLocale, 包 i18n provider
    const { container } = render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    expect(container.textContent).toContain("42");
    expect(container.textContent).toContain("7");
  });

  it("fetch 失败时 RSC 不抛 (用空数据兜底, 不阻塞整页)", async () => {
    globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
      const urlStr = typeof url === "string" ? url : url.toString();
      // 权限接口仍需正常返回，PageGuard 需要权限判断
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
      return new Response("bad", { status: 500 });
    }) as never;
    const mod = await import("./page");
    const pageFn = mod.default;
    // 不再透传错误给 error.tsx, 直接 catch 后渲染 { datasets: 0, documents: 0 }
    const element = await pageFn();
    const { container } = render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    expect(container.textContent).toContain("0");
  });
});
