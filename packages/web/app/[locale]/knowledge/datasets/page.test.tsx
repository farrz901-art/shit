// RSC 测试 (2026-06-12): page 改 RSC 后, 直接 await Page() 拿 JSX, 渲染后等 use() 解包.
// (2026-06-14) use(promise) 模式: 用 act + flushMicrotasks 解决 Suspense
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

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

beforeEach(() => {
  // (2026-06-15) 真响应是 Dify 完整包装 { data, has_more, total, limit, page },
  // 配 rscGet 拆包. 旧 mock 返裸数组跟真 Dify 形态不一致, 是 datasets.find is not a function
  // 同一类 bug 的隐藏根因 — 调测看不出问题, 一上 prod 就炸.
  // (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限 (测试用)
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
    return okResponse({
      data: [
        { document_count: 5, id: "1", name: "DS1", word_count: 100 },
        { document_count: 3, id: "2", name: "DS2", word_count: 60 },
      ],
      has_more: false,
      limit: 20,
      page: 1,
      total: 2,
    });
  }) as never;
});

describe("DatasetsPage (RSC)", () => {
  it("渲染 RSC 预取的数据", async () => {
    const mod = await import("./page");
    const page = mod.default;
    const element = await page();
    await act(async () => {
      render(
        <NextIntlClientProvider locale="zh" messages={zhMessages}>
          {element as never}
        </NextIntlClientProvider>,
      );
      await Promise.resolve();
    });
    expect(screen.getByText("DS1")).toBeInTheDocument();
    expect(screen.getByText("DS2")).toBeInTheDocument();
  });

  it("fetch 失败时 RSC 抛错 (error.tsx 兜住)", async () => {
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
            {element as never}
          </NextIntlClientProvider>,
        );
      });
    } catch (error) {
      err = error;
    }
    expect(err).toBeInstanceOf(Error);
  });
});
