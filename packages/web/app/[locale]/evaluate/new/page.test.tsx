// RSC 测试 (2026-06-12) — Task 20 改造 evaluate/new
//   Page 是 server wrapper, 直接 import + render, 灌 EvaluateNewForm client 子组件
//   Client 行为测试搬到 _components/EvaluateNewForm.test.tsx (mock evaluateApi / papaparse)
//   此处只断言 RSC wrapper 把 form 渲染出来 + dropzone 文案
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";

// Mock server-only: 避免 RSC 走 import 链拉 server 端模块
vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

// Client 子组件 import createRun (BFF multipart), 给个 stub 避免 RSC 渲染触发 fetch
vi.mock("@/lib/api/evaluate", () => ({
  createRun: vi.fn(async () => ({ id: 0, status: "pending" })),
  templateUrl: () => "/api/evaluate/template",
}));

// Papaparse 同理 stub, 子组件只在用户选文件时才跑
vi.mock("papaparse", () => ({
  default: { parse: vi.fn() },
}));

// BackLink / useRouter 链 (子组件里有) mock, 防止 "expected app router to be mounted"
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  usePathname: () => "/evaluate/new",
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

// (2026-06-17) v2 RBAC: 套 PageGuard 后, /api/permissions/me 返 admin 全权限 (测试用)
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

// (2026-06-17) v2 RBAC: fetch 返 admin 全权限 (PageGuard 走这里)
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

import newEvalPage from "./page";

const renderInI18n = (ui: React.ReactNode) => render(<IntlWrapper locale="zh">{ui}</IntlWrapper>);

describe("NewEvalPage (RSC wrapper)", () => {
  it("渲染 h1 新建评估", async () => {
    const element = await newEvalPage();
    renderInI18n(element);
    expect(screen.getByRole("heading", { name: /新建评估/ })).toBeInTheDocument();
  });

  it("渲染文件 dropzone (input[type=file] + 文案提示)", async () => {
    const element = await newEvalPage();
    const { container } = renderInI18n(element);
    const input = container.querySelector('input[type="file"]');
    expect(input).toBeTruthy();
    // (2026-06-14) FileDropzone 改成硬编码中文 (拖文件到这 或 点击选择 / 上限 XMB),
    // 跟 zh.json "仅支持 csv, 最多 5MB, 1-200 行" 不再一致. 改测 FileDropzone 实际渲染
    expect(screen.getByText(/拖文件到这 或 点击选择/)).toBeInTheDocument();
    expect(screen.getByText(/上限 5MB/)).toBeInTheDocument();
  });

  it("渲染模板下载链接 (BFF /api/evaluate/template)", async () => {
    const element = await newEvalPage();
    renderInI18n(element);
    const dl = screen.getByText(/没模板\? 下载/);
    expect(dl.closest("a")).toHaveAttribute("href", "/api/evaluate/template");
  });
});
