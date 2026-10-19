/**
 * buildNavTree 纯函数测试 (2026-07-02 nav spec §3.2)
 * 11 个用例覆盖: 树组装 + 权限过滤 + 边角.
 *
 * eslint-disable-next-line: 测试 fixture 用单字符变量名 + 数组索引, 业务代码遵守规范
 */
/* eslint-disable id-length, no-magic-numbers, max-statements */
import { describe, expect, it } from "vitest";
import type { PageMeta } from "@/lib/auth/permission-types";
import { buildNavTree, filterNavByPermissions } from "./build-nav-tree";

const mkPage = (overrides: Partial<PageMeta>): PageMeta => ({
  key: "x",
  label_zh: "X",
  label_en: "X",
  path: "/x",
  is_active: true,
  ...overrides,
});

describe("buildNavTree", () => {
  it("顶级 (无 parent_id) → roots", () => {
    const tree = buildNavTree([
      mkPage({ key: "chat", path: "/chat", sort: 10, metadata: { path: "/chat" } }),
      mkPage({
        key: "admin",
        path: "/admin",
        sort: 50,
        metadata: { path: "/admin", is_group: true },
      }),
    ]);
    expect(tree.roots.map((n) => n.key)).toEqual(["chat", "admin"]);
    expect(tree.orphans).toEqual([]);
  });

  it("子页 (有 parent_id 指向存在的 key) → parent.children", () => {
    const tree = buildNavTree([
      mkPage({ key: "admin", path: "/admin", metadata: { path: "/admin", is_group: true } }),
      mkPage({
        key: "admin_users",
        path: "/admin/users",
        metadata: { path: "/admin/users", parent_id: "admin" },
      }),
    ]);
    const admin = tree.roots.find((n) => n.key === "admin");
    expect(admin?.children).toHaveLength(1);
    expect(admin?.children[0]?.key).toBe("admin_users");
  });

  it("孤儿 (parent_id 指向不存在的 key) → orphans", () => {
    const tree = buildNavTree([
      mkPage({
        key: "orphan",
        path: "/orphan",
        metadata: { path: "/orphan", parent_id: "nonexistent" },
      }),
    ]);
    expect(tree.roots).toHaveLength(0);
    expect(tree.orphans.map((n) => n.key)).toEqual(["orphan"]);
  });

  it("is_active=false 跳过", () => {
    const tree = buildNavTree([
      mkPage({ key: "chat", path: "/chat", metadata: { path: "/chat" } }),
      mkPage({ key: "hidden", path: "/h", is_active: false, metadata: { path: "/h" } }),
    ]);
    expect(tree.roots.map((n) => n.key)).toEqual(["chat"]);
  });

  it("排序按 sort 字段", () => {
    const tree = buildNavTree([
      mkPage({ key: "z", path: "/z", sort: 99, metadata: { path: "/z" } }),
      mkPage({ key: "a", path: "/a", sort: 1, metadata: { path: "/a" } }),
      mkPage({ key: "m", path: "/m", sort: 50, metadata: { path: "/m" } }),
    ]);
    expect(tree.roots.map((n) => n.key)).toEqual(["a", "m", "z"]);
  });

  it("parent.children 也按 sort 排", () => {
    const tree = buildNavTree([
      mkPage({ key: "admin", path: "/admin", metadata: { path: "/admin", is_group: true } }),
      mkPage({
        key: "admin_z",
        path: "/admin/z",
        sort: 99,
        metadata: { path: "/admin/z", parent_id: "admin" },
      }),
      mkPage({
        key: "admin_a",
        path: "/admin/a",
        sort: 1,
        metadata: { path: "/admin/a", parent_id: "admin" },
      }),
    ]);
    const admin = tree.roots.find((n) => n.key === "admin");
    expect(admin?.children.map((n) => n.key)).toEqual(["admin_a", "admin_z"]);
  });

  it("metadata.path 优先于 PageMeta.path", () => {
    const tree = buildNavTree([
      mkPage({
        key: "x",
        path: "/fallback",
        metadata: { path: "/override" },
      }),
    ]);
    expect(tree.roots[0]?.path).toBe("/override");
  });

  it("父级没 path → isGroup=true", () => {
    const tree = buildNavTree([mkPage({ key: "x", path: null, metadata: { is_group: true } })]);
    expect(tree.roots[0]?.isGroup).toBe(true);
  });

  it("父级有 path + is_group=true → 仍 isGroup", () => {
    const tree = buildNavTree([
      mkPage({ key: "admin", path: "/admin", metadata: { path: "/admin", is_group: true } }),
    ]);
    expect(tree.roots[0]?.isGroup).toBe(true);
  });

  it("icon 字段透传", () => {
    const tree = buildNavTree([
      mkPage({ key: "x", path: "/x", metadata: { path: "/x", icon: "shield" } }),
    ]);
    expect(tree.roots[0]?.icon).toBe("shield");
  });

  it("空数组 → 空树", () => {
    const tree = buildNavTree([]);
    expect(tree.roots).toEqual([]);
    expect(tree.orphans).toEqual([]);
  });
});

describe("filterNavByPermissions", () => {
  const setup = () =>
    buildNavTree([
      mkPage({ key: "admin", path: "/admin", metadata: { path: "/admin", is_group: true } }),
      mkPage({
        key: "admin_users",
        path: "/admin/users",
        metadata: { path: "/admin/users", parent_id: "admin" },
      }),
      mkPage({
        key: "admin_dicts",
        path: "/admin/dicts",
        metadata: { path: "/admin/dicts", parent_id: "admin" },
      }),
      mkPage({ key: "chat", path: "/chat", metadata: { path: "/chat" } }),
      mkPage({
        key: "knowledge",
        path: "/knowledge",
        metadata: { path: "/knowledge", is_group: true },
      }),
      mkPage({
        key: "knowledge_extract",
        path: "/knowledge/extract",
        metadata: { path: "/knowledge/extract", parent_id: "knowledge" },
      }),
    ]);

  it("父级 isGroup+无 path: 仅子项可见时显示", () => {
    const tree = setup();
    const filtered = filterNavByPermissions(tree, ["admin_users"]);
    const admin = filtered.roots.find((n) => n.key === "admin");
    expect(admin).toBeDefined();
    expect(admin?.children.map((c) => c.key)).toEqual(["admin_users"]);
  });

  it("父级 isGroup+无 path: 子项全不可见时不显示父级", () => {
    const tree = setup();
    const filtered = filterNavByPermissions(tree, ["chat"]);
    expect(filtered.roots.find((n) => n.key === "admin")).toBeUndefined();
  });

  it("父级 isGroup+有 path: 自己可见 OR 子项可见都显示", () => {
    const tree = setup();
    const f1 = filterNavByPermissions(tree, ["admin"]);
    expect(f1.roots.find((n) => n.key === "admin")).toBeDefined();
  });

  it("叶子顶级: 仅自己有权限", () => {
    const tree = setup();
    const filtered = filterNavByPermissions(tree, ["admin"]);
    /* eslint-disable id-length -- test fixture single-char var names */
    expect(filtered.roots.find((n) => n.key === "chat")).toBeUndefined();
    expect(filtered.roots.find((n) => n.key === "admin")).toBeDefined();
    /* eslint-enable id-length */
  });

  it("权限空数组 → 全空树", () => {
    const tree = setup();
    const filtered = filterNavByPermissions(tree, []);
    expect(filtered.roots).toEqual([]);
  });
});
