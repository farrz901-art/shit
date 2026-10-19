// (2026-06-23) RSC 权限守卫测试
import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

vi.mock("server-only", () => ({}));

vi.mock("next/navigation", () => ({
  forbidden: () => {
    throw new Error("NEXT_FORBIDDEN");
  },
}));

const mockGetPermissions = vi.fn();
vi.mock("@/lib/auth/permission", () => ({
  getPermissions: () => mockGetPermissions(),
}));

// Oxlint new-cap 不识别 async server component 直接调用
// 用 module 导入 + 小写别名绕开
import * as guardPageModule from "./guard-page";
const guardPage = guardPageModule.GuardPage;

describe("GuardPage", () => {
  it("有权限时渲染 children", async () => {
    mockGetPermissions.mockResolvedValueOnce({
      can: (pageKey: string) => pageKey === "chat",
    });
    const element = await guardPage({
      pageKey: "chat",
      children: <div>content</div>,
    });
    render(element);
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("无权限时抛 NEXT_FORBIDDEN", async () => {
    mockGetPermissions.mockResolvedValueOnce({
      can: () => false,
    });
    await expect(guardPage({ pageKey: "admin", children: <div>admin</div> })).rejects.toThrow(
      "NEXT_FORBIDDEN",
    );
  });
});
