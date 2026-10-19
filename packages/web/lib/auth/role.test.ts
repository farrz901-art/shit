import { describe, expect, test } from "vitest";
import { isAdminLevel, isSuperAdmin } from "@/lib/auth/role";

describe("isAdminLevel", () => {
  test("anon (null) → false", () => {
    expect(isAdminLevel(null)).toBe(false);
  });
  test("undefined → false", () => {
    expect(isAdminLevel(undefined)).toBe(false);
  });
  test("user role → false", () => {
    expect(isAdminLevel({ role: "user" })).toBe(false);
  });
  test("admin role → true", () => {
    expect(isAdminLevel({ role: "admin" })).toBe(true);
  });
  test("super_admin role → true", () => {
    expect(isAdminLevel({ role: "super_admin" })).toBe(true);
  });
  test("custom operator role → true", () => {
    expect(isAdminLevel({ role: "operator" })).toBe(true);
  });
});

describe("isSuperAdmin", () => {
  test("null → false", () => {
    expect(isSuperAdmin(null)).toBe(false);
  });
  test("admin → false", () => {
    expect(isSuperAdmin({ role: "admin" })).toBe(false);
  });
  test("super_admin → true", () => {
    expect(isSuperAdmin({ role: "super_admin" })).toBe(true);
  });
});
