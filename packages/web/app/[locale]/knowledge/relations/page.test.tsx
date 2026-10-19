// RSC 测试 (2026-06-12): use(promise) 模式 — act + flushMicrotasks 解决 Suspense
import { act, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextIntlClientProvider } from "next-intl";
import enMessages from "@/messages/en.json";
import zhMessages from "@/messages/zh.json";

vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

const NON_EMPTY = 0;
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) => (name === "rag_user_token" ? { value: "tok" } : undefined),
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
        {
          dst: "2",
          dst_business_id: "B001",
          dst_label: "Bearing",
          dst_name: "轴承B",
          props: { weight: "10kg" },
          src: "1",
          src_business_id: "M001",
          src_label: "Motor",
          src_name: "电机A",
          type: "HAS_BEARING",
        },
      ],
      { headers: { "Content-Type": "application/json" }, status: 200 },
    );
  }) as never;
});

const renderInI18n = async (locale: "zh" | "en") => {
  const mod = await import("./page");
  const page = mod.default;
  const element = await page();
  let result: ReturnType<typeof render> | null = null;
  await act(async () => {
    result = render(
      <NextIntlClientProvider locale={locale} messages={locale === "zh" ? zhMessages : enMessages}>
        {element}
      </NextIntlClientProvider>,
    );
    await Promise.resolve();
  });
  return result!;
};

describe("RelationsPage (RSC)", () => {
  it("渲染 RSC 预取的 relations 数据", async () => {
    const { container } = await renderInI18n("zh");
    // Motion 动画延迟, 用 container.textContent 断言
    expect(container.textContent).toContain("电机A");
    expect(container.textContent).toContain("轴承B");
    expect(container.textContent).toContain("HAS_BEARING");
    expect(container.textContent).toContain("weight");
  });

  it("zh locale 渲染 h1=全部关系 + breadcrumb=知识图谱", async () => {
    await renderInI18n("zh");
    expect(screen.getByRole("heading", { name: "全部关系" })).toBeTruthy();
    // (2026-06-28) Phase3 Task3.2: BackLink 现在是 BackLink icon + 返回知识图谱 (PageHero backHref)
    expect(screen.getByRole("link", { name: /返回知识图谱/ })).toBeTruthy();
  });

  it("zh locale 表格列头为 类型/起点/终点/属性", async () => {
    await renderInI18n("zh");
    expect(screen.getByText("起点")).toBeTruthy();
    expect(screen.getByText("终点")).toBeTruthy();
    expect(screen.getAllByText("类型").length).toBeGreaterThan(NON_EMPTY);
    expect(screen.getAllByText("属性").length).toBeGreaterThan(NON_EMPTY);
  });

  it("en locale 渲染 h1=All Relations + 英文 breadcrumb", async () => {
    await renderInI18n("en");
    expect(screen.getByRole("heading", { name: "All Relations" })).toBeTruthy();
    // (2026-06-28) Phase3 Task3.2: BackLink 现在是 BackLink icon + 翻译后的 label (PageHero backHref)
    expect(screen.getByRole("link", { name: /Back to Knowledge Graph/ })).toBeTruthy();
  });

  it("en locale 表格列头为 Type/Start/End/Properties", async () => {
    await renderInI18n("en");
    expect(screen.getByText("Start")).toBeTruthy();
    expect(screen.getByText("End")).toBeTruthy();
    expect(screen.getAllByText("Type").length).toBeGreaterThan(NON_EMPTY);
    expect(screen.getAllByText("Properties").length).toBeGreaterThan(NON_EMPTY);
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
