// PermissionData 类型序列化验证
import { describe, expect, it } from "vitest";
import type { PermissionData, PageMeta } from "./permission-types";

const TEST_ACCOUNT_ID = 42;

describe("permission-types", () => {
  it("PermissionData 是可序列化的（不含函数/headers）", () => {
    const data: PermissionData = {
      role: "admin",
      accountId: TEST_ACCOUNT_ID,
      allowed: ["chat", "knowledge"],
      pages: [{ key: "chat", label_zh: "聊天", label_en: "Chat", path: "/chat" }],
    };
    const serialized = structuredClone(data);
    expect(serialized.role).toBe("admin");
    expect(serialized.accountId).toBe(TEST_ACCOUNT_ID);
    expect(serialized.allowed).toEqual(["chat", "knowledge"]);
  });

  it("PageMeta 字段完整", () => {
    const meta: PageMeta = {
      key: "admin",
      label_zh: "管理",
      label_en: "Admin",
      path: "/admin/users",
    };
    expect(meta.key).toBe("admin");
    expect(meta.path).toBe("/admin/users");
  });

  it("accountId 可为 null（anon 用户）", () => {
    const data: PermissionData = {
      role: "user",
      accountId: null,
      allowed: ["chat"],
      pages: [],
    };
    expect(data.accountId).toBeNull();
    expect(structuredClone(data).accountId).toBeNull();
  });
});
