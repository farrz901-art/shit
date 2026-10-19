// UsePermissions 单测: hydration-only 模式 + renderHook 测试
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { usePermissions, usePermissionsStore } from "./use-permissions";
import { ONE } from "@/const";
import type { PermissionData } from "@/lib/auth/permission-types";

const TEST_ACCOUNT_ID = 42;

const baseData: PermissionData = {
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
};

describe("usePermissionsStore", () => {
  beforeEach(resetState);
  afterEach(resetState);

  it("默认值: role=user, loaded=false, accountId=null", () => {
    const state = usePermissionsStore.getState();
    expect(state.role).toBe("user");
    expect(state.loaded).toBe(false);
    expect(state.accountId).toBeNull();
  });

  it("hydrate 后状态正确", () => {
    usePermissionsStore.getState().hydrate(baseData);
    const state = usePermissionsStore.getState();
    expect(state.role).toBe("admin");
    expect(state.allowed).toEqual(["chat", "knowledge"]);
    expect(state.accountId).toBe(TEST_ACCOUNT_ID);
    expect(state.loaded).toBe(true);
    expect(state.pages).toHaveLength(ONE);
  });

  it("hydrate 异常时仍标记 loaded=true（防卡死）", () => {
    // @ts-expect-error — 传非法数据模拟 hydrate 异常
    usePermissionsStore.getState().hydrate(null);
    const state = usePermissionsStore.getState();
    expect(state.loaded).toBe(true);
  });
});

describe("usePermissions hook", () => {
  beforeEach(resetState);
  afterEach(resetState);

  it("user: isAdminLevel=false, isSuperAdmin=false", () => {
    usePermissionsStore.setState({ role: "user", loaded: true });
    const { result } = renderHook(() => usePermissions());
    expect(result.current.isAdminLevel).toBe(false);
    expect(result.current.isSuperAdmin).toBe(false);
    // Empty allowed: can() 必为 false
    expect(result.current.can("chat")).toBe(false);
  });

  it("super_admin: isAdminLevel=true, isSuperAdmin=true, can() 全通", () => {
    usePermissionsStore.setState({ role: "super_admin", loaded: true, allowed: ["chat"] });
    const { result } = renderHook(() => usePermissions());
    expect(result.current.isAdminLevel).toBe(true);
    expect(result.current.isSuperAdmin).toBe(true);
    expect(result.current.can("anything")).toBe(true);
  });

  it("普通角色: can() 受 allowed 控制", () => {
    usePermissionsStore.setState({ role: "user", loaded: true, allowed: ["chat"] });
    const { result } = renderHook(() => usePermissions());
    // 普通角色: can() 仅放行 allowed 内的 pageKey
    expect(result.current.can("chat")).toBe(true);
    expect(result.current.can("admin")).toBe(false);
  });
});
