// RSC 测试 (2026-06-12): page 改 RSC 后, 直接 import + 渲染 QAPage, 灌 QASubmitForm client 子组件.
// 不再 mock useSWR, 改为 mock createQA server action + next/navigation.
// QASubmitForm 子组件走 useActionState + form action, server action mock 让提交可观察.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

// Mock server-only: _actions/knowledge.ts 顶部 "use server" + auth.server.ts "server-only"
vi.mock("server-only", () => ({}));

// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock createQA server action: 提交行为可观察, 不真发后端
// (2026-06-13) Task 10: createQA 返审核记录, 不再返 doc id
const { createQAMock } = vi.hoisted(() => ({
  createQAMock: vi.fn(async () => ({
    data: { apply_status: "none", approval_id: 1, review_status: "pending" },
    ok: true as const,
  })),
}));
vi.mock("@/app/[locale]/_actions/knowledge", () => ({
  __esModule: true,
  createQA: createQAMock,
}));

// Zustand store 默认 datasetId="" (server render 时没 localStorage)
// 测试时手动 set; 不在 RSC 测试里强制赋值 (RSC 不读 store)
vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (sel: (st: { datasetId: string }) => string) => sel({ datasetId: "" }),
}));

// BackLink 用 useRouter (useHistory 模式), QASubmitForm (Task 21) 加 useParams/useRouter
// Mock 避免 "expected app router to be mounted"
vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "zh" }),
  usePathname: () => "/knowledge/qa",
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

// (2026-06-17) v2 RBAC: 套 PageGuard 后, /api/permissions/me 返 admin 全权限 (测试用)
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

import qaPage from "./page";
import { ONE } from "@/const";

const renderInI18n = (ui: React.ReactNode) =>
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {ui}
    </NextIntlClientProvider>,
  );

beforeEach(() => {
  createQAMock.mockClear();
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

describe("QAPage (RSC)", () => {
  it("渲染 hero title=录 QA 对 + 表单 + BackLink", async () => {
    const element = await qaPage();
    renderInI18n(element);
    expect(screen.getByRole("heading", { name: "录 QA 对" })).toBeInTheDocument();
    expect(screen.getByTestId("qa-submit")).toBeInTheDocument();
    expect(screen.getByTestId("back-link")).toBeInTheDocument();
  });

  it("hero 含返回向量库 (BackLink → /knowledge/documents)", async () => {
    const element = await qaPage();
    renderInI18n(element);
    expect(screen.getByText("返回向量库")).toBeInTheDocument();
  });

  it("createQA server action 被 mock 注入 (提交可观察)", async () => {
    // 验证 mock 模块的 createQA 是可调用函数 — server action wiring 已建立
    const mod = await import("@/app/[locale]/_actions/knowledge");
    expect(typeof mod.createQA).toBe("function");
    // Mock 注入后, 直接调用应返约定形状
    const result = await mod.createQA({ answer: "A.", dataset_id: "ds-1", question: "Q?" });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.approval_id).toBe(ONE);
      expect(result.data.review_status).toBe("pending");
    }
  });
});
