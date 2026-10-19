# 导航子菜单 + 权限树形勾选 设计 (2026-07-02)

> Author: brainstorm session
> Status: Draft → 等待 user review

## 1. 背景与目标

### 1.1 问题

当前 RAG web 顶部导航 (`Header`) 把所有 `page_key` 平铺渲染。字典里 page_key 已经 10 个（admin / chat / output / knowledge / evaluate / submissions / decode / health / buyers / knowledge_extract），未来业务扩展还会继续加，**导航栏长度已经不够**，且每加一个页面要改 4 处（字典 + seed + Header + 权限矩阵）。

更严重的是 `/admin/*` 实际有 5 个子页（users / invites / permissions / dicts / profile-fields），它们全挂在 `page_key="admin"` 之下，**所有 5 个子页都靠 `require_page("admin")` 同一个守卫**，粒度粗到无法做"普通 admin 不能改字典"的细控。

### 1.2 目标

1. **导航支持子菜单**：每个顶级 page_key 可挂 N 个子页面，hover 弹出
2. **权限树形勾选**：`/admin/permissions` 用树形展示 page_key 父子结构，勾叶子 = 给角色权限
3. **数据字典功能不坏**：完全复用现有 lookup 字典机制，super_admin 在 `/admin/dicts` 改 page_key 时新增的 metadata_json 字段都通过现有 API 编辑
4. **改页面只动 1 处**：加新页面 = 在字典 seed 加 1 个 page_key 项（写 `parent_id` 关联到顶级），不需改 Header 或权限组件代码

### 1.3 不做什么 (YAGNI)

- ❌ 多级嵌套（只支持 1 层子菜单：顶级 → 叶子）。3 层及以上的子菜单不做
- ❌ 父级页面也存 role_permissions（只叶子进权限表）
- ❌ 动态角色 + 父子权限继承逻辑（按叶子勾选就够）
- ❌ 后端返回嵌套结构（保持后端扁平 + 前端组装树）
- ❌ 数据库 schema 改动（全部走 metadata_json）

### 1.4 成功标准

- [ ] 加一个新页面 = 改 yaml seed 1 处，不改任何 .ts/.tsx 代码
- [ ] Header 在桌面端 hover 顶级项 200ms 内弹出子菜单（Radix DropdownMenu 默认 0ms delay + Tailwind transition 200ms）
- [ ] `/admin/permissions` 树形展示，勾选/取消勾选即时写回（沿用现有 `usePermissionsTable` 批量 save）
- [ ] 移动端（< sm 断点）Header 折叠为汉堡菜单 + 抽屉，结构跟桌面一致
- [ ] 现有 721+ 测试不退化（新增子菜单相关测试 ≥ 30 个）
- [ ] 字典系统 CRUD（add / patch / delete）不破坏 page_key 的新字段

---

## 2. 数据结构变更

### 2.1 page_key 字典扩展

**`packages/service/config/dictionaries_seed.yaml`** 中 `page_key` 字典的 items 加 metadata_json 字段：

```yaml
- code: page_key
  items:
    # === 顶级 (is_group=true 或 parent_id=null) ===
    - key: admin
      label_zh: 管理中心
      sort: 50
      metadata_json:
        path: "/admin"                    # 父级 path 可选, 用于「直接点击父级」场景
        is_group: true                    # 标记是分组容器, 渲染时不可点
        icon: "shield"                    # lucide-react icon 名
    - key: knowledge
      label_zh: 知识库
      sort: 30
      metadata_json:
        path: "/knowledge"
        icon: "book"

    # === 子页 (parent_id=顶级 key) ===
    - key: admin_users
      label_zh: 用户管理
      sort: 51
      metadata_json:
        path: "/admin/users"
        parent_id: "admin"
    - key: admin_invites
      label_zh: 邀请码
      sort: 52
      metadata_json:
        path: "/admin/invites"
        parent_id: "admin"
    - key: admin_permissions
      label_zh: 权限管理
      sort: 53
      metadata_json:
        path: "/admin/permissions"
        parent_id: "admin"
    - key: admin_dicts
      label_zh: 字典管理
      sort: 54
      metadata_json:
        path: "/admin/dicts"
        parent_id: "admin"
    - key: admin_profile_fields
      label_zh: 画像字段配置
      sort: 55
      metadata_json:
        path: "/admin/profile-fields"
        parent_id: "admin"
    - key: knowledge_extract
      label_zh: 知识图谱抽取
      sort: 31
      metadata_json:
        path: "/knowledge/extract"
        parent_id: "knowledge"
```

**约束**：
- 子页 key 命名约定：`{parent_key}_{sub_key}` （例 `admin_users`）— 跟现有 `knowledge_extract`（原 key）兼容但不一致，迁移时**统一改成 `knowledge_extract` 不动**（避免动业务代码）
- `parent_id` 必须是已存在的 `page_key` key，否则 buildNavTree 归到 orphans
- 子页必须有 `path`；父级 `path` 可选（你选了"父级不可点"）
- `is_group: true` 标记父级只是容器（不可点击，不可勾选进 role_permissions）

### 2.2 后端 cache.py 透传 metadata_json

**`packages/service/src/permissions/cache.py`** `get_all_page_metadata_sync()`：

```python
# 现状 (line ~85)
result.append({
    "key": item.key,
    "label_zh": item.label_zh,
    "label_en": item.label_en,
    "path": meta.get("path"),
    "is_active": item.is_active,
})

# 改后: 直接把 metadata_json 整块透传
result.append({
    "key": item.key,
    "label_zh": item.label_zh,
    "label_en": item.label_en,
    "path": meta.get("path"),
    "is_active": item.is_active,
    "metadata": dict(meta),   # ← 新增: 透传整块 metadata_json
})
```

零 schema 改动。`LookupCache` / `LookupService` 早就在读写 metadata_json（`lookups/schemas.py:122-139 LookupItemPatch` 已有 `metadata_json` 字段），字典 admin API 自动支持改父/子关系。

### 2.3 前端 PageMeta 类型扩展

**`packages/web/lib/auth/permission-types.ts`**：

```typescript
export interface PageMeta {
  key: string;
  label_zh: string;
  label_en: string;
  path: string | null;
  is_active?: boolean;
  sort?: number;
  // 新增 (2026-07-02 导航子菜单)
  metadata?: {
    path?: string;
    parent_id?: string;
    is_group?: boolean;
    icon?: string;
    [k: string]: unknown;
  };
}
```

### 2.4 NavTree 类型

**新增 `packages/web/lib/nav/nav-types.ts`**：

```typescript
/** 树节点 (渲染用) */
export interface NavNode {
  key: string;
  label_zh: string;
  label_en: string;
  path: string | null;
  icon?: string;
  isGroup: boolean;       // 父级 = true, 叶子 = false
  children: NavNode[];    // 空数组 = 没子项 (自己就是页面)
  sort: number;
}

/** Header / 权限矩阵 / 移动端 共用 */
export interface NavTree {
  roots: NavNode[];       // 顶级节点 (已按 sort 排序)
  orphans: NavNode[];     // 找不到 parent_id 的孤儿节点 (日志报警 + 仍渲染为顶级)
}
```

---

## 3. 前端核心：`buildNavTree` 纯函数

### 3.1 文件

**`packages/web/lib/nav/build-nav-tree.ts`** —— 新文件，零依赖，单导出函数。

```typescript
import type { PageMeta } from "@/lib/auth/permission-types";
import type { NavNode, NavTree } from "./nav-types";

/**
 * 把扁平 PageMeta[] 组装成 NavTree
 * - 顶层节点 = 无 parent_id + is_active !== false
 * - 子节点 = 有 parent_id 指向存在的 key
 * - 找不到 parent 的 = orphans (日志 warn + 仍渲染)
 * - 父级无 path (is_group=true) → 不可点
 * - 父级有 path → 仍只 hover 弹菜单 (按用户决策 "父级不可点")
 */
export const buildNavTree = (pages: PageMeta[]): NavTree => {
  const byKey = new Map<string, NavNode>();
  const orphans: NavNode[] = [];

  // 1st pass: 全转 NavNode
  for (const pg of pages) {
    if (pg.is_active === false) continue;
    byKey.set(pg.key, {
      key: pg.key,
      label_zh: pg.label_zh,
      label_en: pg.label_en,
      path: pg.metadata?.path ?? pg.path ?? null,
      icon: pg.metadata?.icon,
      isGroup: pg.metadata?.is_group === true,
      children: [],
      sort: pg.sort ?? 0,
    });
  }

  // 2nd pass: 建父子关系
  const roots: NavNode[] = [];
  for (const node of byKey.values()) {
    const parentId = pages.find((p) => p.key === node.key)?.metadata?.parent_id;
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
    console.warn("[buildNavTree] orphan nodes:", orphans.map((n) => n.key));
  }

  return { roots, orphans };
};

/** 用户权限过滤: 叶子节点必须有权限, 父级 = 任一子节点有权限才显示 */
export const filterNavByPermissions = (
  tree: NavTree,
  allowed: string[],
): NavTree => {
  const visibleRoots: NavNode[] = [];
  for (const root of tree.roots) {
    const visibleChildren = root.children.filter((c) => allowed.includes(c.key));
    if (root.isGroup && root.path === null) {
      // 纯分组: 必须有 ≥1 子项可见才渲染
      if (visibleChildren.length > 0) {
        visibleRoots.push({ ...root, children: visibleChildren });
      }
    } else if (root.isGroup && root.path !== null) {
      // 父级可点 + 子菜单: 有权限 OR 有可见子项 → 渲染
      if (allowed.includes(root.key) || visibleChildren.length > 0) {
        visibleRoots.push({ ...root, children: visibleChildren });
      }
    } else {
      // 叶子顶级 (没 parent_id, 没 is_group): 必须自己有权限
      if (allowed.includes(root.key)) {
        visibleRoots.push(root);
      }
    }
  }
  return { roots: visibleRoots, orphans: [] };
};
```

### 3.2 测试覆盖

**`packages/web/lib/nav/build-nav-tree.test.ts`** —— ≥ 15 测试用例：

1. 顶级（无 parent_id）→ roots
2. 子页（有 parent_id 指向存在的 key）→ parent.children
3. 孤儿（parent_id 指向不存在的 key）→ orphans
4. is_active=false 跳过
5. 排序按 sort 字段
6. parent.children 嵌套也按 sort 排
7. metadata.path 优先于 PageMeta.path
8. parent 没 path → isGroup=true
9. parent 有 path + is_group=true → 仍 isGroup（按决策）
10. `filterNavByPermissions`:
    - 父级 isGroup+无 path：仅子项可见时显示
    - 父级 isGroup+有 path：自己可见 OR 子项可见
    - 叶子顶级：仅自己有权限
    - 权限空数组 → 全空树
11. 空数组 → 空树
12. 重复 key（防御）→ 后到的覆盖
13. 中文 label 保留
14. icon 字段透传
15. orphans 不进 roots

---

## 4. 前端 Header 重构

### 4.1 现状

**`packages/web/components/layout/header.tsx:33-54`** 平铺 filter + render。

### 4.2 改后

```tsx
// header.tsx (改后)
import { buildNavTree, filterNavByPermissions } from "@/lib/nav/build-nav-tree";

const tree = buildNavTree(permissions.pages);
const visible = filterNavByPermissions(tree, permissions.allowed);

// 渲染: 父级 → NavDropdownMenu (AppDropdownMenu 已封装)
//        叶子 → NavLink (现状)
return (
  <nav>
    {visible.roots.map((node) =>
      node.children.length > 0 ? (
        <NavDropdown key={node.key} node={node} />
      ) : (
        <NavLink key={node.key} href={node.path!}>{t(node.label_zh)}</NavLink>
      )
    )}
  </nav>
);
```

### 4.3 NavDropdown 组件

**新增 `packages/web/components/layout/nav-dropdown.tsx`** —— 复用现有 `AppDropdownMenu`（已有 shadcn DropdownMenu 封装）。

```tsx
"use client";
import { AppDropdownMenu } from "@/components/common/input/app-dropdown-menu";
import type { NavNode } from "@/lib/nav/nav-types";

export const NavDropdown = ({ node }: { node: NavNode }) => (
  <AppDropdownMenu
    trigger={
      <button data-testid={`nav-dropdown-${node.key}`} className="...">
        {t(node.label_zh)}
        <ChevronDown className="ml-1 h-3 w-3" />
      </button>
    }
    contentClassName="w-48"
    items={node.children.map((child) => ({
      key: child.key,
      href: child.path!,
      label: t(child.label_zh),
      testid: `nav-dropdown-item-${child.key}`,
    }))}
  />
);
```

**icon 渲染规则**（消除歧义）：
- metadata_json.icon 存 lucide-react 图标名（如 `"shield"` `"book"` `"settings"`）
- 用 `dynamic(() => import('lucide-react').then(m => m[iconName]))` 懒加载
- 找不到 icon 名 → 静默降级到无图标（不报错）
- Header 顶级 trigger 左侧 16px 图标；子菜单项左侧 14px 图标
- 只在 `icon` 字段存在时渲染（不强制每个 page_key 都要 icon）

### 4.4 移动端汉堡菜单

`< sm` 断点时，桌面 nav 隐藏，显示汉堡按钮 → 点开抽屉（用现有 `<AppDrawer>` 封装）。

**新增 `packages/web/components/layout/mobile-nav-drawer.tsx`**：

```tsx
"use client";
import { AppDrawer } from "@/components/common/dialog/app-drawer";
import { LocalizedLink } from "@/components/i18n/localized-link";

export const MobileNavDrawer = ({ tree }: { tree: NavTree }) => {
  // 树形渲染: 父级折叠面板 (Accordion) + 叶子直接 Link
  // 折叠/展开状态用 Radix Accordion
};
```

### 4.5 行为细节

- 父级 trigger **不可点击跳转**（按用户决策），hover/click 才展开
- 父级 trigger 有 `aria-haspopup="menu"` + `aria-expanded`
- 子项 hover 高亮（Radix 默认）
- Esc 关闭菜单（Radix 默认）
- 路由切换时自动关闭菜单（订阅 `usePathname()`）

---

## 5. `/admin/permissions` 权限矩阵改树形勾选

### 5.1 现状

**`packages/web/app/[locale]/admin/permissions/_components/permissions-table.tsx`** —— 平铺矩阵（行=角色，列=page_key）。

### 5.2 改后

**重命名为 `permissions-matrix-tree.tsx`** —— 树形勾选：

```
┌────────────────────────────────────────────────┐
│ 角色     │  页面树 (缩进 + Chevron 展开)         │
├────────────────────────────────────────────────┤
│ user     │ ☐ 知识库                              │
│          │   ☐ 知识图谱抽取                       │
│          │ ☐ 对话                                │
│          │ ☑ 解码                                │
│          │ ...                                  │
│ admin    │ ☐ 管理中心                            │
│          │   ☑ 用户管理                          │
│          │   ☑ 邀请码                            │
│          │   ☐ 权限管理                          │
│          │   ☑ 字典管理                          │
│          │   ☑ 画像字段配置                      │
└────────────────────────────────────────────────┘
```

### 5.3 树形组件

**新增 `packages/web/components/common/display/tree-checkbox.tsx`** —— 通用树形 checkbox（不耦合权限业务），可在未来给"角色组" / "功能开关" 复用。

```tsx
"use client";
interface TreeCheckboxProps<T> {
  nodes: TreeNode<T>[];
  checked: Set<string>;
  indeterminate: Set<string>;
  onToggle: (key: string) => void;
  renderLabel?: (node: TreeNode<T>) => React.ReactNode;
}

interface TreeNode<T> {
  key: string;
  label: string;
  children?: TreeNode<T>[];
  data?: T;
}
```

**`<TreeCheckbox>` 行为**：
- 父级 checkbox 反映子级状态（全勾 = checked, 部分勾 = indeterminate, 全空 = unchecked）
- **勾选父级 = 不级联子级**（按决策"父级不入权限表"）—— 父级本身不可勾（disabled）
- 叶子单独 toggle → 即时写 pending
- Chevron 展开/折叠（默认全部展开；保留全部折叠按钮）
- **视觉规格**：缩进 24px/级；行高 32px；父级 label 加粗 + 600 字重；hover 整行高亮 `bg-muted/40`

### 5.4 复用现有 usePermissionsTable

**`packages/web/app/[locale]/admin/permissions/_hooks/use-permissions-table.ts`** 内部数据结构 (`pending: Record<"role|page", boolean>`) 不变 —— 只改 UI 层。

**关键规则**（消除歧义）：
- **子页不进 role_permissions 表**：permissions.allowed 中只含"顶级 / 父级 / 叶子顶级"三种，不含子页
- **子菜单可见性 = 父级权限**：用户对 `admin` 有权限 → admin 子菜单显示全部 5 个子项；用户没 `admin` 权限 → admin 子菜单整体不渲染
- **filterNavByPermissions 逻辑**：父级（isGroup=true）按"自己 allowed OR 子项 allowed"判定；叶子顶级按"自己 allowed"判定

```tsx
// 改后:
const tree = buildNavTree(permissions.pages);  // 复用
return (
  <TreeCheckbox
    nodes={tree.roots.map(toTreeNodes)}
    checked={cellChecked}            // 已有逻辑
    indeterminate={cellIndeterminate} // 新增: 计算父级 indeterminate
    onToggle={(pageKey) => toggle(pageKey, currentRole)}
    renderLabel={(node) => <span>{t(node.label_zh)}</span>}
  />
);
```

**indeterminate 计算**：父级 = (some children checked) && (some children unchecked)。注意：因子页不进 role_permissions，**父级的 cell value = 子项 cell value 的 OR**，仅当所有 5 个 admin 子页都勾才 checked。

### 5.5 测试

**`permissions-matrix-tree.test.tsx`** —— ≥ 10 测试：

1. 树渲染（嵌套缩进）
2. 父级 disabled（不可勾）
3. 叶子 toggle 调 onToggle
4. 父级 indeterminate 显示（部分子项 checked）
5. 父级 checked 显示（全部子项 checked）
6. 父级 unchecked 显示（无子项 checked）
7. Chevron 折叠/展开
8. 全部展开 / 全部折叠按钮
9. 键盘可达 (Tab / Space toggle)
10. 拒 super_admin 行（保留现有逻辑）

---

## 6. cache invalidation

**问题**：super_admin 改字典 page_key 的 metadata_json.parent_id 后，前端缓存的 `pages` 不会立即刷新。

**解法**：
- 后端 `LookupCache` 已有 invalidation（`lookups/cache.py`）
- 前端 `PermissionHydrate` 已有 `staleTime: 60_000`（TanStack Query 默认 1 分钟）
- 增加：在 `/admin/dicts` 编辑 page_key 字典项时，调 `apiFetch.invalidatePermissions()` 强制刷新

**新增 `packages/web/lib/api/permissions.ts`** 加：
```typescript
export const invalidatePermissions = () => {
  queryClient.invalidateQueries({ queryKey: ["permissions"] });
};
```

**编辑 dialog 接入**：`<DictItemEditor>` onSuccess 时调 `invalidatePermissions()`。

---

## 7. 测试策略

### 7.1 后端

- **`cache.py`** 单测：metadata 透传测试 (1 个)
- **字典 admin API**：现有 test 不动，新加 metadata_json.parent_id CRUD 测试 (2 个)

### 7.2 前端

| 测试文件 | 用例数 | 范围 |
|---|---|---|
| `lib/nav/build-nav-tree.test.ts` | 15 | 纯函数: 树组装 + 权限过滤 |
| `components/layout/nav-dropdown.test.tsx` | 5 | Radix DropdownMenu trigger / items / 关闭 |
| `components/layout/mobile-nav-drawer.test.tsx` | 3 | 折叠面板 + 路由切换关闭 |
| `components/layout/header.test.tsx` | 8 | 顶级渲染 + 子菜单 + 权限过滤 + 移动端 |
| `components/common/display/tree-checkbox.test.tsx` | 6 | indeterminate / toggle / 折叠 |
| `app/[locale]/admin/permissions/_components/permissions-matrix-tree.test.tsx` | 10 | 树渲染 + 现有 usePermissionsTable 集成 |

**总计：47 个新测试**

### 7.3 E2E (Playwright)

**`packages/web/e2e/nav-submenu.spec.ts`**：

1. 登录 admin → hover "管理中心" → 看到 5 个子项
2. hover "用户管理" → 跳 `/admin/users`
3. 切角色到 user → "管理中心" 不显示（admin 权限被剥）
4. 移动端 (375x667)：汉堡菜单 → 展开 → 看到子菜单
5. `/admin/permissions` 树形显示 + 勾选 admin_permissions → user 角色立即有权限

### 7.4 回归保证

- `bun run lint` 0 error
- `bun run typecheck` 0 error
- `bun run test` 不退化（baseline 721 passed）
- `bun run test:e2e` 5 用例全过

---

## 8. 迁移 / 回滚

### 8.1 数据迁移

**新增 page_key 项**：
- 在 `dictionaries_seed.yaml` 加 5 个新 page_key (admin_users / admin_invites / admin_permissions / admin_dicts / admin_profile_fields) + 给现有 knowledge_extract 加 `parent_id: knowledge`
- 跑 `scripts/seed_dictionaries.py` UPSERT（已有逻辑）

**role_permissions 关联**：
- 现状：所有 5 个 admin 子页都用 `require_page("admin")` 一个守卫
- 迁移策略：**两步走**
  - **阶段 1**（本期实施）：保留所有子页用 `require_page("admin")`，子页在 role_permissions 不独立占行。**新 5 个 page_key 不进 role_permissions 表**（parent_id=admin 决定勾"管理中心"=拥有该组权限）
  - **阶段 2**（下一 spec）：拆 require_page 调用，每个子页改用自己 page_key 守卫。**这是本 spec 不做的"硬升级"**，留作 follow-up
- **过渡方案**：本期 Header 子菜单渲染时，子页不参与 permissions.pages.allowed 过滤（直接挂在父级下，父级有权限就显示子菜单，**点击子页时仍走 `require_page("admin")` 旧守卫**）

**等等**：这意味着子页在 `permissions.pages` 里仍要存在（用于渲染），但在 `permissions.allowed` 数组里**不独立占位**（避免 user 角色"没勾 admin_users 但能看到子菜单"的混乱）。

**实际方案修正**（已决）：
- 子页 `page_key` 进字典表（用于 Header 渲染）
- **不进 role_permissions 表**（按决策"只存叶子进权限表"），子页不在 `permissions.allowed` 中出现
- **父级权限 = 子菜单可见性**：用户有 `admin` 权限 → admin 子菜单显示；用户没 `admin` 权限 → 整个 admin 子菜单隐藏
- **点击子页**：服务端仍走 `require_page("admin")` 旧守卫（保持向后兼容）
- **下一 spec**：拆守卫，子页进 role_permissions，每个子页独立可控

### 8.2 回滚

- 改 Header.js 改坏了 → git revert 单 commit 即可（无 DB 改动）
- 字典 seed 加错了 → 重新 UPSERT（字典系统本身支持）
- 不涉及 alembic migration，零回滚成本

---

## 9. 风险与缓解

| 风险 | 严重度 | 缓解 |
|---|---|---|
| 父级 page_key 改 path 后子菜单所有链接走错 | M | E2E 测试覆盖所有路径 |
| 移动端汉堡菜单嵌套折叠面板有 a11y 问题 | M | 用 Radix Accordion + 键盘可达测试 |
| 子页 key 命名混乱（admin_users vs knowledge_extract 风格不一） | L | 文档 + convention lint 检查（不强制本期） |
| 现有 usePermissionsTable hook 改动引入回归 | M | 不动 hook 数据结构，只换 UI 层 |
| super_admin 在 `/admin/dicts` 改 page_key 后前端缓存不刷新 | M | 字典 edit onSuccess 触发 invalidatePermissions |
| 父级 trigger 当作按钮导致 a11y 报错 | L | 用 `<button aria-haspopup="menu">` 不用 `<a>` |
| hover 在触屏设备不响应 | L | 移动端 fallback 到 click (汉堡菜单) |
| 父子 cycle（parent_id 自指或间接循环） | L | buildNavTree 检测 cycle → orphans + warn |

---

## 10. 文件变更总览

### 10.1 后端 (Python)

| 文件 | 变更 |
|---|---|
| `packages/service/config/dictionaries_seed.yaml` | +5 page_key 项 + 现有 10 项 metadata_json |
| `packages/service/src/permissions/cache.py` | metadata 字段透传 (1 行) |
| `packages/service/tests/permissions/test_cache.py` | +1 测试 |

### 10.2 前端 (TypeScript)

**新增 (6 文件)**：
- `lib/nav/build-nav-tree.ts` (纯函数)
- `lib/nav/build-nav-tree.test.ts` (15 测试)
- `lib/nav/nav-types.ts` (类型)
- `components/layout/nav-dropdown.tsx`
- `components/layout/nav-dropdown.test.tsx`
- `components/layout/mobile-nav-drawer.tsx`
- `components/layout/mobile-nav-drawer.test.tsx`
- `components/common/display/tree-checkbox.tsx`
- `components/common/display/tree-checkbox.test.tsx`
- `app/[locale]/admin/permissions/_components/permissions-matrix-tree.tsx` (重命名自 permissions-table)
- `app/[locale]/admin/permissions/_components/permissions-matrix-tree.test.tsx`

**修改 (8 文件)**：
- `components/layout/header.tsx` (用 NavTree)
- `components/layout/header.test.tsx` (覆盖新逻辑)
- `lib/auth/permission-types.ts` (PageMeta 加 metadata)
- `lib/api/permissions.ts` (+ invalidatePermissions)
- `app/[locale]/admin/permissions/_hooks/use-permissions-table.ts` (微调: 加 indeterminate 计算)
- `app/[locale]/admin/permissions/page.tsx` (用新组件)
- `app/[locale]/admin/dicts/_components/dict-item-editor.tsx` (onSuccess invalidatePermissions)
- `messages/zh.json` + `messages/en.json` (子菜单相关 i18n)

### 10.3 E2E (1 新文件)

- `packages/web/e2e/nav-submenu.spec.ts` (5 用例)

---

## 11. 实施顺序建议（写 plan 时细化）

1. **PR 1**：后端 metadata 透传 + yaml seed 更新 + 后端单测
2. **PR 2**：前端 build-nav-tree 纯函数 + 单测 + 类型扩展
3. **PR 3**：Header 改造 (桌面端 hover dropdown) + Header 测试
4. **PR 4**：移动端汉堡菜单 + 测试
5. **PR 5**：TreeCheckbox 通用组件 + 单测
6. **PR 6**：权限矩阵改树形 + 集成测试
7. **PR 7**：字典编辑 invalidate 权限缓存
8. **PR 8**：E2E 测试 + 回归 + 文档

每 PR ≤ 300 行 diff，独立可回滚，CI 全绿才合并。