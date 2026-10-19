import { beforeEach, describe, expect, it, vi } from "vitest";
import { ONE } from "@/const";

vi.mock("@/lib/api/config", () => ({
  apiFetch: vi.fn(),
}));

vi.mock("@/lib/api/auth.server", () => ({
  serverAuthHeaders: vi.fn(),
}));

vi.mock("server-only", () => ({}));

// Mock react.cache: 在 jsdom 下 cache 可能不完整, 包成简单透传
vi.mock("react", async () => {
  const actual = await vi.importActual("react");
  return {
    ...actual,
    cache: <TCallback extends (...args: never[]) => unknown>(callback: TCallback): TCallback =>
      callback,
  };
});

import { apiFetch } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { getPermissions } from "./permission";

const TEST_ACCOUNT_ID = 42;

describe("getPermissions", () => {
  const mockHeaders = { "x-user-token": "test-tok" };

  beforeEach(() => {
    vi.mocked(serverAuthHeaders).mockResolvedValue(mockHeaders);
  });

  it("super_admin → isSuperAdmin=true, can() 全通 + accountId 映射", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({
      account_id: TEST_ACCOUNT_ID,
      allowed: [],
      pages: [{ key: "admin", label_en: "Admin", label_zh: "管理", path: "/admin" }],
      role: "super_admin",
    });
    const perm = await getPermissions();
    expect(perm.role).toBe("super_admin");
    expect(perm.isAdminLevel).toBe(true);
    expect(perm.isSuperAdmin).toBe(true);
    expect(perm.can("anything")).toBe(true);
    expect(perm.pages).toHaveLength(ONE);
    expect(perm.headers).toEqual(mockHeaders);
    expect(perm.accountId).toBe(TEST_ACCOUNT_ID);
  });

  it("user → isAdminLevel=false, can() 受 allowed 控制", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({
      account_id: null,
      allowed: ["chat"],
      pages: [],
      role: "user",
    });
    const perm = await getPermissions();
    expect(perm.isAdminLevel).toBe(false);
    expect(perm.isSuperAdmin).toBe(false);
    expect(perm.can("chat")).toBe(true);
    expect(perm.can("admin")).toBe(false);
    expect(perm.accountId).toBeNull();
  });

  it("fetch 失败 → 返回 DEFAULT_PERMISSION 不抛异常", async () => {
    vi.mocked(apiFetch).mockRejectedValueOnce(new Error("Network error"));
    const perm = await getPermissions();
    expect(perm.role).toBe("user");
    expect(perm.accountId).toBeNull();
    expect(perm.can("chat")).toBe(true);
    expect(perm.can("knowledge")).toBe(false);
    expect(perm.headers).toEqual({});
  });

  it("account_id 字段缺失时 accountId 为 null", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({
      allowed: ["chat"],
      pages: [],
      role: "user",
    });
    const perm = await getPermissions();
    expect(perm.accountId).toBeNull();
  });
});
