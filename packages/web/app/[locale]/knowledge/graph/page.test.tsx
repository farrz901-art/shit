// RSC 测试 (2026-06-12): page 改 RSC 后, 直接 await Page() 拿预取数据, 灌 GraphView.
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
//   (2026-06-29 FE-3 fix) mock 路径必须跟 StatCard import 一致 (@/components/motion/animated, 没 common/ 前缀)
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

// Mock fetch: 返回 /api/kg/stats?type=neo4j 返 { nodes, relations }
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
      { neo4j: { nodes: 100, relations: 250 }, dify: { datasets: 0, documents: 0 } },
      {
        headers: { "Content-Type": "application/json" },
        status: 200,
      },
    );
  }) as never;
});

describe("GraphPage (RSC)", () => {
  it("渲染 RSC 预取的 stats (neo4j.nodes/relations)", async () => {
    const { default: pageComponent } = await import("./page");
    const element = await pageComponent();
    // 子组件用 useTranslations, 包 i18n provider
    const { container } = render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    // StatCard 渲染数字; 节点数 + 关系数 都应出现
    expect(container.textContent).toContain("100");
    expect(container.textContent).toContain("250");
  });

  it("渲染 PageHero title=知识图谱 + SchemaBrowser trigger", async () => {
    const { default: pageComponent } = await import("./page");
    const element = await pageComponent();
    const { getByRole, getByTestId } = render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    expect(getByRole("heading", { name: /知识图谱/ })).toBeTruthy();
    expect(getByTestId("schema-browser-trigger")).toBeTruthy();
  });

  it("渲染录入入口卡: 录三元组 + 批量导入", async () => {
    const { default: pageComponent } = await import("./page");
    const element = await pageComponent();
    const { getByRole } = render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    expect(getByRole("heading", { name: "录三元组" })).toBeTruthy();
    expect(getByRole("heading", { name: "批量导入" })).toBeTruthy();
    // 入口 href 正确
    expect(getByRole("link", { name: /录三元组/ }).getAttribute("href")).toBe(
      "/zh/knowledge/triples",
    );
    expect(getByRole("link", { name: /批量导入/ }).getAttribute("href")).toBe(
      "/zh/knowledge/batch",
    );
  });

  it("fetch 失败时 RSC 不抛 (用空数据兜底, 不阻塞整页)", async () => {
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
      return new Response("bad", { status: 500 });
    }) as never;
    const { default: pageComponent } = await import("./page");
    // 不再透传错误给 error.tsx, 直接 catch 后渲染 { nodes: 0, relations: 0 }
    const element = await pageComponent();
    const { container } = render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    expect(container.textContent).toContain("0");
  });
});
