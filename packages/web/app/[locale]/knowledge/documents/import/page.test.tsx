// RSC 测试 (2026-06-12): import page 改 RSC 后, 直接 import + 渲染 ImportPage,
//   灌 DocumentsImportForm client 子组件.
// 不再 mock useSWR, 只 mock next/navigation (BackLink) + IntlWrapper 包 i18n.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

// Mock server-only: _actions/knowledge.ts 顶部 "use server" + auth.server.ts "server-only"
vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (sel: (state: { datasetId: string }) => string) => sel({ datasetId: "ds1" }),
}));

// Parse-json 顶层 import zod 触发 pre-existing ESM 问题, 跟本次任务无关 — 测试隔离
vi.mock("@/lib/parse-json", () => ({
  parseJsonText: vi.fn().mockReturnValue({ errors: [], items: [] }),
}));

// BackLink 用 useRouter (useHistory 模式), mock 避免 "expected app router to be mounted"
vi.mock("next/navigation", () => ({
  usePathname: () => "/knowledge/documents/import",
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

// (2026-06-17) v2 RBAC: 套 PageGuard 后, /api/permissions/me 返 admin 全权限 (测试用)
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

import importPage from "./page";

const renderInI18n = (ui: React.ReactNode) => render(<IntlWrapper locale="zh">{ui}</IntlWrapper>);

describe("ImportPage (RSC)", () => {
  beforeEach(() => {
    localStorage.clear();
    // (2026-06-17) v2 RBAC: 套 PageGuard, 渲染时拉 /api/permissions/me, mock 返 admin 全权限
    globalThis.fetch = vi.fn(async () =>
      Response.json(
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
      ),
    ) as never;
  });

  it("渲染 PageHero title=批量导入", async () => {
    const element = await importPage();
    renderInI18n(element);
    expect(screen.getByRole("heading", { name: /批量导入/ })).toBeInTheDocument();
  });

  it("hero actions 含 BackLink → /knowledge/documents", async () => {
    const element = await importPage();
    renderInI18n(element);
    expect(screen.getByTestId("back-link")).toBeInTheDocument();
    expect(screen.getByText("返回向量库")).toBeInTheDocument();
  });

  it("renders upload zone", async () => {
    const element = await importPage();
    renderInI18n(element);
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
  });

  it("shows template links", async () => {
    const element = await importPage();
    renderInI18n(element);
    expect(screen.getByTestId("dl-excel")).toBeInTheDocument();
    expect(screen.getByTestId("dl-json")).toBeInTheDocument();
  });
});
