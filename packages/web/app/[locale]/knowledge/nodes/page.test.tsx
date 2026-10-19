// RSC 测试 (2026-06-12): use(promise) 模式 — act + flushMicrotasks 解决 Suspense
import { act, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";
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

beforeEach(() => {
  // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限
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
      [
        { business_id: "N001", id: "1", label: "Motor", name: "电机A", props: { power: "5kW" } },
        {
          business_id: "N002",
          id: "2",
          label: "Bearing",
          name: "轴承B",
          props: { type: "6204" },
        },
      ],
      { headers: { "Content-Type": "application/json" }, status: 200 },
    );
  }) as never;
});

const renderPage = async () => {
  const mod = await import("./page");
  const page = mod.default;
  const element = await page();
  await act(async () => {
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    await Promise.resolve();
  });
};

describe("NodesPage (RSC)", () => {
  it("渲染 RSC 预取的 nodes 数据", async () => {
    await renderPage();
    expect(screen.getByText("电机A")).toBeInTheDocument();
    expect(screen.getByText("N001")).toBeInTheDocument();
    expect(screen.getByText("Motor")).toBeInTheDocument();
  });

  it("渲染 h1=全部节点 + breadcrumb=知识图谱", async () => {
    await renderPage();
    expect(screen.getByRole("heading", { name: "全部节点" })).toBeTruthy();
    // (2026-06-28) Phase3 Task3.2: BackLink 现在是 BackLink icon + 返回知识图谱 (PageHero backHref)
    expect(screen.getByRole("link", { name: /返回知识图谱/ })).toBeTruthy();
  });

  it("zh locale 表格列头为 编号/类型/名称/属性", async () => {
    await renderPage();
    expect(screen.getByText("编号")).toBeTruthy();
    expect(screen.getByText("类型")).toBeTruthy();
    expect(screen.getByText("名称")).toBeTruthy();
    expect(screen.getByText("属性")).toBeTruthy();
  });

  it("fetch 失败时把错误透传 (RSC 抛错, error.tsx 兜住)", async () => {
    // Use(promise) 模式: Page() 返 JSX, 但内部含 rejected promise;
    // Render 时 use() 会 throw, 包 try/catch 捕 render 错避免 unhandled rejection
    globalThis.fetch = vi.fn(async () => new Response("bad", { status: 500 })) as never;
    const mod = await import("./page");
    const page = mod.default;
    const element = await page();
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
    expect(err).toBeInstanceOf(Error);
  });
});
