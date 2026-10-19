# PR2 — Frontend: buildNavTree Pure Function + PageMeta Types

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pure-function `buildNavTree()` that assembles flat `PageMeta[]` into a navigable tree, plus extend the `PageMeta` type to carry `metadata_json`. Zero UI changes in this PR — just logic and types that PR3/PR4/PR6 consume.

**Files:**
- Create: `packages/web/lib/nav/nav-types.ts`
- Create: `packages/web/lib/nav/build-nav-tree.ts`
- Create: `packages/web/lib/nav/build-nav-tree.test.ts`
- Modify: `packages/web/lib/auth/permission-types.ts:4-10`

---

## Task 2.1: Add failing test for buildNavTree (TDD red phase)

**Files:**
- Create: `packages/web/lib/nav/build-nav-tree.test.ts`

- [ ] **Step 1: Create nav directory**

Run: `mkdir -p packages/web/lib/nav`

- [ ] **Step 2: Write the failing test file**

Create `packages/web/lib/nav/build-nav-tree.test.ts`:

```typescript
/**
 * buildNavTree 纯函数测试 (2026-07-02 nav spec §3.2)
 * 15 个用例覆盖: 树组装 + 权限过滤 + 边角.
 */
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
      mkPage({ key: "chat", path: "/chat", metadata: { path: "/chat" } }),
      mkPage({ key: "admin", path: "/admin", metadata: { path: "/admin", is_group: true } }),
    ]);
    expect(tree.roots.map((n) => n.key)).toEqual(["admin", "chat"]);
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
    const admin = tree.roots.find((n) => n.key === "admin")!;
    expect(admin.children).toHaveLength(1);
    expect(admin.children[0]?.key).toBe("admin_users");
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
    const admin = tree.roots.find((n) => n.key === "admin")!;
    expect(admin.children.map((n) => n.key)).toEqual(["admin_a", "admin_z"]);
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
    const tree = buildNavTree([
      mkPage({ key: "x", path: null, metadata: { is_group: true } }),
    ]);
    expect(tree.roots[0]?.isGroup).toBe(true);
  });

  it("父级有 path + is_group=true → 仍 isGroup (按决策 '父级不可点')", () => {
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

  it("父级 isGroup+无 path：仅子项可见时显示", () => {
    const tree = setup();
    const filtered = filterNavByPermissions(tree, ["admin_users"]); // 父级不在 allowed
    const admin = filtered.roots.find((n) => n.key === "admin")!;
    expect(admin).toBeDefined();
    expect(admin.children.map((c) => c.key)).toEqual(["admin_users"]);
  });

  it("父级 isGroup+无 path：子项全不可见时不显示父级", () => {
    const tree = setup();
    const filtered = filterNavByPermissions(tree, ["chat"]); // admin 全无权限
    expect(filtered.roots.find((n) => n.key === "admin")).toBeUndefined();
  });

  it("父级 isGroup+有 path：自己可见 OR 子项可见都显示", () => {
    const tree = setup();
    // 父级可见, 子项不可见
    const f1 = filterNavByPermissions(tree, ["admin"]);
    expect(f1.roots.find((n) => n.key === "admin")).toBeDefined();
    // 子项可见, 父级不可见 (前一个用例已覆盖)
  });

  it("叶子顶级：仅自己有权限", () => {
    const tree = setup();
    const filtered = filterNavByPermissions(tree, ["admin"]); // chat 无权限
    expect(filtered.roots.find((n) => n.key === "chat")).toBeUndefined();
    expect(filtered.roots.find((n) => n.key === "admin")).toBeDefined();
  });

  it("权限空数组 → 全空树", () => {
    const tree = setup();
    const filtered = filterNavByPermissions(tree, []);
    expect(filtered.roots).toEqual([]);
  });
});
```

- [ ] **Step 3: Update PageMeta type FIRST (so test compiles)**

Modify `packages/web/lib/auth/permission-types.ts`:

```typescript
// PermissionData: 可序列化的权限数据子集，跨 RSC→Client 边界传输
// 此文件不含 server-only import，可被 client 组件安全引用

export interface PageMeta {
  key: string;
  label_zh: string;
  label_en: string;
  path: string | null; // (2026-07-02) 改为可空, 父级 is_group=true 可无 path
  is_active?: boolean;
  sort?: number;
  // (2026-07-02 nav spec §2.3) 透传整块 metadata_json 给前端
  // - parent_id: 父级 key (子菜单用)
  // - is_group: true = 父级容器, 不可点
  // - icon: lucide-react 图标名
  metadata?: {
    path?: string;
    parent_id?: string;
    is_group?: boolean;
    icon?: string;
    [k: string]: unknown;
  };
}

export interface PermissionData {
  role: string;
  accountId: number | null;
  allowed: string[];
  pages: PageMeta[];
}
```

Note: changing `path: string` → `path: string | null` may break existing consumers. Run typecheck to find them.

- [ ] **Step 4: Run test to verify it fails (RED phase)**

Run: `cd packages/web && bun run test -- lib/nav/build-nav-tree.test.ts`

Expected: FAIL — `build-nav-tree.ts` not found, import error.

- [ ] **Step 5: Commit failing test + type extension**

```bash
cd c:/doc/Code/rag
git add packages/web/lib/nav/build-nav-tree.test.ts packages/web/lib/auth/permission-types.ts
git commit -m "test(nav): add 15 buildNavTree tests + extend PageMeta type (PR2/1)"
```

---

## Task 2.2: Implement buildNavTree + filterNavByPermissions (GREEN phase)

**Files:**
- Create: `packages/web/lib/nav/build-nav-tree.ts`

- [ ] **Step 1: Create nav-types.ts (types extracted for reuse in PR3/PR4)**

Create `packages/web/lib/nav/nav-types.ts`:

```typescript
/**
 * NavTree 渲染模型 (2026-07-02 nav spec §2.4)
 * Header / 移动端 / 权限矩阵 3 处复用.
 */
export interface NavNode {
  key: string;
  label_zh: string;
  label_en: string;
  path: string | null;
  icon?: string;
  isGroup: boolean; // 父级 = true, 叶子 = false
  children: NavNode[]; // 空数组 = 没子项 (自己就是页面)
  sort: number;
}

export interface NavTree {
  roots: NavNode[]; // 顶级节点 (按 sort 排)
  orphans: NavNode[]; // 找不到 parent_id 的孤儿节点
}
```

- [ ] **Step 2: Implement buildNavTree + filterNavByPermissions**

Create `packages/web/lib/nav/build-nav-tree.ts`:

```typescript
/**
 * buildNavTree: 把扁平 PageMeta[] 组装成 NavTree (2026-07-02 nav spec §3.1)
 *
 * 算法:
 * 1. 全转 NavNode (跳过 is_active=false)
 * 2. 建父子关系 (parent_id → children)
 * 3. 排序 (sort 字段)
 * 4. orphans 报警 (dev only)
 *
 * 决策 (来自 brainstorming 2026-07-02):
 * - 父级 is_group=true 不可点 (Header trigger 不跳页面)
 * - 子菜单可见性 = 父级 allowed OR 任一子项 allowed
 * - 叶子顶级: 自己 allowed 才显示
 */
import type { PageMeta } from "@/lib/auth/permission-types";
import type { NavNode, NavTree } from "./nav-types";

export const buildNavTree = (pages: PageMeta[]): NavTree => {
  const byKey = new Map<string, NavNode>();
  const metaByKey = new Map<string, PageMeta>();
  const orphans: NavNode[] = [];

  // 1st pass: 全转 NavNode + 索引 metadata
  for (const pg of pages) {
    if (pg.is_active === false) continue;
    const meta = pg.metadata ?? {};
    byKey.set(pg.key, {
      key: pg.key,
      label_zh: pg.label_zh,
      label_en: pg.label_en,
      path: meta.path ?? pg.path ?? null,
      icon: meta.icon,
      isGroup: meta.is_group === true,
      children: [],
      sort: pg.sort ?? 0,
    });
    metaByKey.set(pg.key, pg);
  }

  // 2nd pass: 建父子关系
  const roots: NavNode[] = [];
  for (const node of byKey.values()) {
    const parentId = metaByKey.get(node.key)?.metadata?.parent_id;
    if (!parentId) {
      roots.push(node);
      continue;
    }
    const parent = byKey.get(parentId);
    if (!parent) {
      orphans.push(node);
      continue;
    }
    parent.children.push(node);
  }

  // 3rd pass: 排序
  const sortFn = (a: NavNode, b: NavNode) => a.sort - b.sort;
  roots.sort(sortFn);
  for (const root of roots) root.children.sort(sortFn);

  // 4th: orphans 报警 (dev only)
  if (orphans.length > 0 && process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.warn("[buildNavTree] orphan nodes (parent_id 找不到):", orphans.map((n) => n.key));
  }

  return { roots, orphans };
};

/**
 * filterNavByPermissions: 按用户权限过滤 NavTree.
 *
 * 规则:
 * - 父级 isGroup + 无 path (纯分组): 必须有 ≥1 子项 visible
 * - 父级 isGroup + 有 path (可点 + 子菜单): 自己 OR 子项 visible
 * - 叶子顶级 (无 is_group): 自己 visible
 */
export const filterNavByPermissions = (tree: NavTree, allowed: string[]): NavTree => {
  const visibleRoots: NavNode[] = [];
  for (const root of tree.roots) {
    const visibleChildren = root.children.filter((c) => allowed.includes(c.key));

    if (root.isGroup && root.path === null) {
      // 纯分组: 仅子项可见时显示
      if (visibleChildren.length > 0) {
        visibleRoots.push({ ...root, children: visibleChildren });
      }
    } else if (root.isGroup && root.path !== null) {
      // 父级可点 + 子菜单: 自己 OR 子项 visible
      if (allowed.includes(root.key) || visibleChildren.length > 0) {
        visibleRoots.push({ ...root, children: visibleChildren });
      }
    } else {
      // 叶子顶级
      if (allowed.includes(root.key)) {
        visibleRoots.push(root);
      }
    }
  }
  return { roots: visibleRoots, orphans: [] };
};
```

- [ ] **Step 3: Run test to verify it passes (GREEN)**

Run: `cd packages/web && bun run test -- lib/nav/build-nav-tree.test.ts`

Expected: 15 tests PASS.

- [ ] **Step 4: Run typecheck**

Run: `cd packages/web && bun run typecheck 2>&1 | head -50`

Expected: 0 errors. If `path: string` → `path: string | null` broke consumers, find them and fix (likely header.tsx:34 `pg.path &&` truthy check, may need to remain).

- [ ] **Step 5: Run lint**

Run: `cd packages/web && bun run lint -- lib/nav/ 2>&1 | tail -10`

Expected: 0 errors. (Note: use `bun run lint:fix` if needed.)

- [ ] **Step 6: Commit GREEN phase**

```bash
cd c:/doc/Code/rag
git add packages/web/lib/nav/build-nav-tree.ts packages/web/lib/nav/nav-types.ts
git commit -m "feat(nav): add buildNavTree + filterNavByPermissions (PR2/2)

Pure function, zero deps. Header / 移动端 / 权限矩阵 3 处复用.
15 unit tests green. PageMeta.metadata 字段类型扩展."
```

---

## Task 2.3: Verify no regressions on existing pages that consume PageMeta

- [ ] **Step 1: Run full frontend test suite**

Run: `cd packages/web && bun run test 2>&1 | tail -20`

Expected: 721 baseline + 15 new = 736 passed. No new failures.

- [ ] **Step 2: Check Header still renders (it consumes PageMeta)**

Run: `cd packages/web && bun run test -- components/layout/header.test.tsx 2>&1 | tail -20`

Expected: existing tests still pass.

If header.test.tsx breaks because `path` became nullable:
- Read error, find `pg.path` access without null guard
- Add `pg.path && ...` guard or non-null assertion `pg.path!` (only when path guaranteed)

- [ ] **Step 3: Verify lint + format pass**

Run: `cd packages/web && bun run lint && bun run format:check 2>&1 | tail -10`

Expected: 0 errors / warnings.

- [ ] **Step 4: Final commit if lint/format fixed anything**

```bash
cd c:/doc/Code/rag
git status
# 如果有需要补的 fix, git add -u && git commit -m "fix(nav): guard nullable path in PageMeta consumers (PR2/3)"
```

---

## PR2 Definition of Done

- [ ] `buildNavTree` + `filterNavByPermissions` implemented
- [ ] 15 unit tests green
- [ ] PageMeta.metadata field typed
- [ ] path: string → path: string | null migration doesn't break Header
- [ ] 721 baseline tests still pass
- [ ] typecheck / lint / format 0 errors
- [ ] Ready for PR3 (Header desktop UI)