// (2026-06-23) PermissionHydrate 单测
import { afterEach, describe, expect, it } from "vitest";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { PermissionHydrate } from "./permission-hydrate";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";
import { useAuthStore } from "@/lib/store/auth-store";
import type { PermissionData } from "@/lib/auth/permission-types";

const TEST_ACCOUNT_ID = 42;
const STALE_ACCOUNT_ID = 999;

const basePerm: PermissionData = {
  role: "admin",
  accountId: TEST_ACCOUNT_ID,
  allowed: ["chat", "knowledge"],
  pages: [{ key: "chat", label_zh: "聊天", label_en: "Chat", path: "/chat" }],
};

const resetState = () => {
  usePermissionsStore.setState({
    accountId: null,
    allowed: [],
    loaded: false,
    pages: [],
    role: "user",
  });
  useAuthStore.setState({ accountId: null });
};

describe("PermissionHydrate", () => {
  afterEach(resetState);

  it("hydrate 后 store 状态正确", () => {
    render(<PermissionHydrate permissions={basePerm} />);
    const state = usePermissionsStore.getState();
    expect(state.loaded).toBe(true);
    expect(state.role).toBe("admin");
    expect(state.allowed).toContain("knowledge");
    expect(state.accountId).toBe(TEST_ACCOUNT_ID);
  });

  it("auth-store accountId 无条件更新（覆盖旧值）", () => {
    useAuthStore.getState().setAccountId(STALE_ACCOUNT_ID);
    render(<PermissionHydrate permissions={basePerm} />);
    expect(useAuthStore.getState().accountId).toBe(TEST_ACCOUNT_ID);
  });

  it("accountId 为 null 时清空 auth-store", () => {
    useAuthStore.getState().setAccountId(STALE_ACCOUNT_ID);
    render(<PermissionHydrate permissions={{ ...basePerm, accountId: null }} />);
    expect(useAuthStore.getState().accountId).toBeNull();
  });
});
