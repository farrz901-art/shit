import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/components/chat/chat-shell", () => ({
  ChatShell: ({ isAccount }: { isAccount?: boolean }) => (
    <div data-testid="chat-shell-mock" data-is-account={String(Boolean(isAccount))}>
      shell
    </div>
  ),
}));

vi.mock("@/components/ui/animated", () => ({
  Reveal: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Stagger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  StaggerItem: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "tok" } : undefined),
  })),
}));

// (2026-06-17) v2 RBAC: /api/permissions/me 返 admin 全权限, /api/account/me 返账号 (测试用)
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
  if (urlStr.includes("/api/account/me")) {
    return Response.json(
      { is_account: true },
      {
        headers: { "Content-Type": "application/json" },
        status: 200,
      },
    );
  }
  return new Response("not mocked", { status: 404 });
}) as never;

import chatPage from "./page";

describe("ChatPage", () => {
  it("mount 渲染 ChatShell + 标题", async () => {
    const Page = await chatPage();
    render(<>{Page}</>);
    expect(screen.getByTestId("chat-shell-mock")).toBeInTheDocument();
    expect(screen.getByText(/跟产品智能体聊聊/)).toBeInTheDocument();
  });

  // (2026-06-17) v2 RBAC: anon → 传 isAccount=false 给 ChatShell, 隐藏 Brain 按钮
  it("anon (/api/account/me 401) → ChatShell 拿 isAccount=false", async () => {
    const orig = globalThis.fetch;
    globalThis.fetch = vi.fn(async (url: string | URL | Request) => {
      const urlStr = typeof url === "string" ? url : url.toString();
      if (urlStr.includes("/api/permissions/me")) {
        return Response.json(
          {
            allowed: ["chat"],
            pages: [],
            role: "user",
          },
          { headers: { "Content-Type": "application/json" }, status: 200 },
        );
      }
      if (urlStr.includes("/api/account/me")) {
        // 401 模拟未登录
        return new Response("unauthorized", { status: 401 });
      }
      return new Response("not mocked", { status: 404 });
    }) as never;
    try {
      const Page = await chatPage();
      render(<>{Page}</>);
      const shell = screen.getByTestId("chat-shell-mock");
      expect(shell.getAttribute("data-is-account")).toBe("false");
    } finally {
      globalThis.fetch = orig;
    }
  });
});
