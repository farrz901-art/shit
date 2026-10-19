// (2026-06-23) GuardClient 单测
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

const mockReplace = vi.fn();
const mockPush = vi.fn();
const mockBack = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: mockPush, back: mockBack }),
}));

import { usePermissionsStore } from "@/lib/hooks/use-permissions";
import { GuardClient } from "./guard-client";

const resetState = () => {
  usePermissionsStore.setState({
    accountId: null,
    allowed: [],
    loaded: false,
    pages: [],
    role: "user",
  });
  mockReplace.mockReset();
  mockPush.mockReset();
  mockBack.mockReset();
};

describe("GuardClient", () => {
  afterEach(resetState);

  it("loaded + 有权限 → 渲染 children + 不跳转", async () => {
    usePermissionsStore.setState({
      allowed: ["chat"],
      loaded: true,
      role: "admin",
    });
    await act(async () => {
      render(
        <GuardClient pageKey="chat">
          <div>content</div>
        </GuardClient>,
      );
    });
    expect(screen.getByText("content")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("loaded + 无权限 → redirect /404", async () => {
    usePermissionsStore.setState({
      allowed: ["chat"],
      loaded: true,
      role: "user",
    });
    await act(async () => {
      render(
        <GuardClient pageKey="admin">
          <div>admin</div>
        </GuardClient>,
      );
    });
    expect(mockReplace).toHaveBeenCalledWith("/404");
  });

  it("super_admin 即使 allowed 不含 pageKey 也不跳转（can bypass）", async () => {
    usePermissionsStore.setState({
      allowed: ["chat"],
      loaded: true,
      role: "super_admin",
    });
    await act(async () => {
      render(
        <GuardClient pageKey="anything">
          <div>content</div>
        </GuardClient>,
      );
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("loaded=false 时不跳转（等 hydrate）", async () => {
    usePermissionsStore.setState({
      allowed: ["chat"],
      loaded: false,
      role: "user",
    });
    await act(async () => {
      render(
        <GuardClient pageKey="admin">
          <div>content</div>
        </GuardClient>,
      );
    });
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
