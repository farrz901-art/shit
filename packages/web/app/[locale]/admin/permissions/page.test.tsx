// /admin/permissions page 测试 (2026-06-17) v2 RBAC
// 验证: super_admin 拿到矩阵 + 角色列表渲染; 非 super_admin → forbidden (2026-06-18 改 notFound)
// (2026-06-23) GuardPage mock 成 sync passthrough: 权限拒绝的 forbidden() 路径在 guard-page.test.tsx 测.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

const { forbiddenMock, fetchMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  forbiddenMock: vi.fn(() => {
    const err = new Error("NEXT_FORBIDDEN");
    (err as Error & { digest?: string }).digest = "NEXT_FORBIDDEN";
    throw err;
  }),
}));

// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => "tok", set: () => {} })),
}));
vi.mock("next/navigation", () => ({
  forbidden: forbiddenMock,
  notFound: vi.fn(() => {
    const err = new Error("NEXT_NOT_FOUND");
    (err as Error & { digest?: string }).digest = "NEXT_NOT_FOUND";
    throw err;
  }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn(), replace: vi.fn() }),
}));
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(async () => (key: string) => key),
}));

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const superAdminPermissions = (): Response =>
  okResponse({
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
    role: "super_admin",
  });

const nonAdminPermissions = (): Response =>
  okResponse({ allowed: ["chat"], pages: [], role: "user" });

const permissionsData = () => ({
  matrix: {
    admin: {
      chat: true,
      decode: true,
      evaluate: true,
      health: true,
      knowledge: true,
      output: true,
      submissions: true,
    },
    super_admin: {
      chat: true,
      decode: true,
      evaluate: true,
      health: true,
      knowledge: true,
      output: true,
      submissions: true,
    },
    user: { chat: true, decode: true },
  },
  pages: [
    { key: "chat", label_en: "Chat", label_zh: "对话", path: "/chat" },
    { key: "output", label_en: "Output", label_zh: "文档结构化", path: "/output" },
    { key: "knowledge", label_en: "Knowledge", label_zh: "知识库", path: "/knowledge" },
    { key: "evaluate", label_en: "Evaluate", label_zh: "评估", path: "/evaluate" },
    { key: "submissions", label_en: "Submissions", label_zh: "审核中心", path: "/submissions" },
    { key: "decode", label_en: "Decode", label_zh: "型号解析", path: "/decode" },
    { key: "health", label_en: "Health", label_zh: "监控", path: "/health" },
  ],
  role_list: [
    {
      is_deletable: false,
      is_system: true,
      label_en: "Super admin",
      label_zh: "超级管理员",
      name: "super_admin",
      user_count: 1,
    },
    {
      is_deletable: false,
      is_system: true,
      label_en: "Admin",
      label_zh: "管理员",
      name: "admin",
      user_count: 3,
    },
    {
      is_deletable: false,
      is_system: true,
      label_en: "User",
      label_zh: "用户",
      name: "user",
      user_count: 10,
    },
  ],
  roles: [
    { is_system: true, label_en: "Super admin", label_zh: "超级管理员", name: "super_admin" },
    { is_system: true, label_en: "Admin", label_zh: "管理员", name: "admin" },
    { is_system: true, label_en: "User", label_zh: "用户", name: "user" },
  ],
});

globalThis.fetch = fetchMock as any;

import permissionsPageFn from "./page";

describe("/admin/permissions page", () => {
  beforeEach(() => {
    forbiddenMock.mockClear();
    fetchMock.mockReset();
  });

  it("非 super_admin (user role) → forbidden (403 权限页)", async () => {
    // (2026-06-18) 改 notFound() → forbidden(): 显式说"权限不足"而不是"页面不存在"
    fetchMock.mockResolvedValueOnce(nonAdminPermissions());
    await expect(permissionsPageFn()).rejects.toThrow("NEXT_FORBIDDEN");
    expect(forbiddenMock).toHaveBeenCalled();
  });

  it("super_admin → 渲染权限矩阵 + 角色列表", async () => {
    fetchMock.mockResolvedValueOnce(superAdminPermissions());
    fetchMock.mockResolvedValueOnce(okResponse(permissionsData()));
    const Page = await permissionsPageFn();
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        {Page}
      </NextIntlClientProvider>,
    );
    // (2026-07-02) tree UI: 角色行用 permission-role-{name} testid
    expect(screen.getByTestId("permission-role-super_admin")).toBeInTheDocument();
    expect(screen.getByTestId("permission-role-admin")).toBeInTheDocument();
    expect(screen.getByTestId("permission-role-user")).toBeInTheDocument();
    // 新建角色按钮 (PermissionsTable 工具栏)
    expect(screen.getByTestId("permissions-create-role")).toBeInTheDocument();
  });
});
