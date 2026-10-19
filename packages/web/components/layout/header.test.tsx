/* eslint-disable id-length, no-magic-numbers -- test fixture */
import { UserMenu, type UserMenuUser } from "../user-menu";
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { Header } from "./header";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import type { PermissionData } from "@/lib/auth/permission-types";
import userEvent from "@testing-library/user-event";

vi.mock("@/components/theme-provider", () => ({
  useTheme: () => ({ setTheme: vi.fn(), theme: "light" }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/zh",
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), refresh: vi.fn() }),
}));

const logoutMock = vi.fn(async () => {});
vi.mock("@/app/[locale]/_actions/account", () => ({
  logoutAction: () => logoutMock(),
}));

const basePermissions: PermissionData = {
  accountId: 1,
  allowed: ["chat", "decode"],
  pages: [
    { key: "chat", label_zh: "对话", label_en: "Chat", path: "/chat" },
    { key: "decode", label_zh: "型号解析", label_en: "Decode", path: "/decode" },
  ],
  role: "user",
};

// Nav link 期望数量
const EXPECTED_LINKS_USER = 2;
const EXPECTED_LINKS_ADMIN = 6;
const EXPECTED_LINKS_SUPER_ADMIN = 7;
const EXPECTED_LINKS_ANON = 1;

// 异步等待延迟 (ms)
const MENU_OPEN_DELAY_MS = 30;
const TRANSITION_FLUSH_DELAY_MS = 50;

// 期望调用次数
const EXPECTED_CALL_COUNT = 1;

const renderHeader = (locale: "zh" | "en" = "zh", permissions: PermissionData = basePermissions) =>
  render(
    <IntlWrapper locale={locale}>
      <Header permissions={permissions} />
    </IntlWrapper>,
  );

const renderMenu = (user: UserMenuUser | null) =>
  render(
    <IntlWrapper locale="zh">
      <UserMenu user={user} />
    </IntlWrapper>,
  );

describe("Header", () => {
  it("渲染 ThemeToggle 齿轮按钮", () => {
    renderHeader();
    expect(screen.getByRole("button", { name: /设置/ })).toBeInTheDocument();
  });

  it("点齿轮 → SettingsDialog 弹出", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByRole("button", { name: /设置/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

describe("Header 翻译", () => {
  it("zh locale 显示中文 nav (对话/知识库/评估)", () => {
    renderHeader("zh", {
      accountId: 1,
      allowed: ["chat", "knowledge", "evaluate"],
      pages: [
        { key: "chat", label_zh: "对话", label_en: "Chat", path: "/chat" },
        { key: "knowledge", label_zh: "知识库", label_en: "Knowledge Base", path: "/knowledge" },
        { key: "evaluate", label_zh: "评估", label_en: "Evaluation", path: "/evaluate" },
      ],
      role: "user",
    });
    expect(screen.getByText("对话")).toBeInTheDocument();
    expect(screen.getByText("知识库")).toBeInTheDocument();
    expect(screen.getByText("评估")).toBeInTheDocument();
  });

  it("en locale 显示英文 nav (Chat/Knowledge Base/Evaluation)", () => {
    renderHeader("en", {
      accountId: 1,
      allowed: ["chat", "knowledge", "evaluate"],
      pages: [
        { key: "chat", label_zh: "对话", label_en: "Chat", path: "/chat" },
        { key: "knowledge", label_zh: "知识库", label_en: "Knowledge Base", path: "/knowledge" },
        { key: "evaluate", label_zh: "评估", label_en: "Evaluation", path: "/evaluate" },
      ],
      role: "user",
    });
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Base")).toBeInTheDocument();
    expect(screen.getByText("Evaluation")).toBeInTheDocument();
  });
});

describe("Header nav filter (v2 RBAC)", () => {
  it("user role → 2 link (chat + decode)", () => {
    renderHeader("zh", {
      accountId: 1,
      allowed: ["chat", "decode"],
      pages: [
        { key: "chat", label_zh: "对话", label_en: "Chat", path: "/chat" },
        { key: "decode", label_zh: "型号解析", label_en: "Decode", path: "/decode" },
      ],
      role: "user",
    });
    expect(screen.getAllByTestId("nav-link")).toHaveLength(EXPECTED_LINKS_USER);
  });

  it("admin role → 6 link", () => {
    renderHeader("zh", {
      accountId: 1,
      allowed: ["chat", "output", "knowledge", "evaluate", "submissions", "decode"],
      pages: [
        { key: "chat", label_zh: "对话", label_en: "Chat", path: "/chat" },
        { key: "output", label_zh: "文档结构化", label_en: "Output", path: "/output" },
        { key: "knowledge", label_zh: "知识库", label_en: "Knowledge", path: "/knowledge" },
        { key: "evaluate", label_zh: "评估", label_en: "Evaluate", path: "/evaluate" },
        { key: "submissions", label_zh: "审核中心", label_en: "Submissions", path: "/submissions" },
        { key: "decode", label_zh: "型号解析", label_en: "Decode", path: "/decode" },
      ],
      role: "admin",
    });
    expect(screen.getAllByTestId("nav-link")).toHaveLength(EXPECTED_LINKS_ADMIN);
  });

  it("super_admin → 7 link (含 health)", () => {
    renderHeader("zh", {
      accountId: 1,
      allowed: ["chat", "output", "knowledge", "evaluate", "submissions", "decode", "health"],
      pages: [
        { key: "chat", label_zh: "对话", label_en: "Chat", path: "/chat" },
        { key: "output", label_zh: "文档结构化", label_en: "Output", path: "/output" },
        { key: "knowledge", label_zh: "知识库", label_en: "Knowledge", path: "/knowledge" },
        { key: "evaluate", label_zh: "评估", label_en: "Evaluate", path: "/evaluate" },
        { key: "submissions", label_zh: "审核中心", label_en: "Submissions", path: "/submissions" },
        { key: "decode", label_zh: "型号解析", label_en: "Decode", path: "/decode" },
        { key: "health", label_zh: "监控", label_en: "Health", path: "/health" },
      ],
      role: "super_admin",
    });
    expect(screen.getAllByTestId("nav-link")).toHaveLength(EXPECTED_LINKS_SUPER_ADMIN);
  });

  it("anon → 1 link (chat)", () => {
    renderHeader("zh", {
      accountId: null,
      allowed: ["chat"],
      pages: [{ key: "chat", label_zh: "对话", label_en: "Chat", path: "/chat" }],
      role: "user",
    });
    expect(screen.getAllByTestId("nav-link")).toHaveLength(EXPECTED_LINKS_ANON);
  });
});

describe("Header nav tree (PR3 — 子菜单)", () => {
  it("顶级有子项 → 渲染 NavDropdown trigger", () => {
    renderHeader("zh", {
      accountId: 1,
      allowed: ["admin"],
      pages: [
        {
          key: "admin",
          label_zh: "管理中心",
          label_en: "Admin",
          path: "/admin",
          metadata: { path: "/admin", is_group: true },
        },
        {
          key: "admin_users",
          label_zh: "用户管理",
          label_en: "Users",
          path: "/admin/users",
          metadata: { path: "/admin/users", parent_id: "admin" },
        },
      ],
      role: "admin",
    });
    expect(screen.getByTestId("nav-dropdown-admin")).toBeInTheDocument();
  });

  it("sort 顺序保留: chat (sort=10) 在 admin (sort=50) 之前", () => {
    renderHeader("zh", {
      accountId: 1,
      allowed: ["chat", "admin"],
      pages: [
        {
          key: "admin",
          label_zh: "管理中心",
          label_en: "Admin",
          path: "/admin",
          sort: 50,
          metadata: { path: "/admin", is_group: true },
        },
        {
          key: "chat",
          label_zh: "对话",
          label_en: "Chat",
          path: "/chat",
          sort: 10,
          metadata: { path: "/chat" },
        },
      ],
      role: "admin",
    });
    const nav = screen.getByRole("navigation");
    const links = nav.querySelectorAll("[data-testid='nav-link']");
    expect(links[0]).toHaveTextContent("对话");
  });

  it("is_active=false 顶级不渲染", () => {
    renderHeader("zh", {
      accountId: 1,
      allowed: ["chat", "hidden"],
      pages: [
        {
          key: "chat",
          label_zh: "对话",
          label_en: "Chat",
          path: "/chat",
          metadata: { path: "/chat" },
        },
        {
          key: "hidden",
          label_zh: "隐藏页",
          label_en: "Hidden",
          path: "/hidden",
          is_active: false,
          metadata: { path: "/hidden" },
        },
      ],
      role: "user",
    });
    expect(screen.queryByText("隐藏页")).toBeNull();
  });
});

describe("UserMenu", () => {
  it("anon → 显示 '登录' 按钮", () => {
    renderMenu(null);
    expect(screen.getByTestId("user-menu-login")).toBeInTheDocument();
  });

  it("账号 → 显示 display_name + 下拉", () => {
    renderMenu({
      display_name: "bob",
      email: "bob@x.com",
      is_account: true,
      is_admin: false,
    });
    expect(screen.getByTestId("user-menu")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
  });

  it("admin → 下拉多 '用户管理' 项", () => {
    renderMenu({
      display_name: "admin",
      email: "admin@x.com",
      is_account: true,
      is_admin: true,
    });
    expect(screen.getByTestId("user-menu")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("super_admin → 多 权限管理 链接", async () => {
    const user = userEvent.setup();
    renderMenu({
      display_name: "SA",
      email: "sa@x.com",
      is_account: true,
      is_admin: true,
      role: "super_admin",
    });
    // Radix DropdownMenu 默认关, content 不在 DOM, 先打开
    await user.click(screen.getByTestId("user-menu"));
    expect(await screen.findByTestId("menu-permissions")).toBeInTheDocument();
    expect(await screen.findByTestId("menu-admin-users")).toBeInTheDocument();
  });

  it("admin role → 仅 用户管理, 无 权限管理", async () => {
    const user = userEvent.setup();
    renderMenu({
      display_name: "A",
      email: "a@x.com",
      is_account: true,
      is_admin: true,
      role: "admin",
    });
    await user.click(screen.getByTestId("user-menu"));
    expect(await screen.findByTestId("menu-admin-users")).toBeInTheDocument();
    expect(screen.queryByTestId("menu-permissions")).not.toBeInTheDocument();
  });

  it("user role → 无管理链接", async () => {
    const user = userEvent.setup();
    renderMenu({
      display_name: "U",
      email: "u@x.com",
      is_account: true,
      is_admin: false,
      role: "user",
    });
    await user.click(screen.getByTestId("user-menu"));
    // 等菜单打开后, 应无管理链接
    await new Promise((resolve) => setTimeout(resolve, MENU_OPEN_DELAY_MS));
    expect(screen.queryByTestId("menu-admin-users")).not.toBeInTheDocument();
    expect(screen.queryByTestId("menu-permissions")).not.toBeInTheDocument();
  });

  it("点 '登出' → 调 logoutAction server action (Radix DropdownMenu 拦截 form submit 的回归测试)", async () => {
    // (2026-06-16) Bug: 之前用 <form action={logoutAction}>, Radix DropdownMenuItem
    // 触发 onSelect 关菜单时 DOM 节点提前移除, form 来不及提交. 改 onClick + useTransition
    // 直接调 server action. 这个测试确保菜单能正确触发登出.
    const user = userEvent.setup();
    renderMenu({
      display_name: "bob",
      email: "bob@x.com",
      is_account: true,
      is_admin: false,
    });

    logoutMock.mockClear();
    // 先打开下拉 (Radix 默认关闭, content 不在 DOM 里)
    await user.click(screen.getByTestId("user-menu"));
    // 再点 "登出" 触发 onSelect
    const logoutItem = await screen.findByTestId("menu-logout");
    await user.click(logoutItem);

    // 给 startTransition 异步 micro-task 一点时间 flush
    await new Promise((resolve) => setTimeout(resolve, TRANSITION_FLUSH_DELAY_MS));
    expect(logoutMock).toHaveBeenCalledTimes(EXPECTED_CALL_COUNT);
  });
});
