# RSC 权限统一 + PageGuard 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 统一 RSC 权限入口到 getPermissions(), Client 走 Zustand + hooks, PageGuard 不再收 props, 删 is_admin 前端使用.

**Architecture:** RSC 页调 getPermissions() 一次拿 role/allowed/headers/派生方法. Client 组件通过 Zustand store + usePermissions() hook. PageGuard 内部读 role + allowed 判断.

**Reference Spec:** docs/superpowers/specs/2026-06-18-permission-rsc-hooks-design.md

---

## File Structure

### New Files (2)
- packages/web/lib/auth/permission.ts -- getPermissions() RSC 函数
- packages/web/lib/hooks/usePermissions.ts -- Zustand store + usePermissions() hook

### Modified Files (6)
- packages/web/components/PageGuard.tsx -- props 改签, forbidden() 替 notFound()
- packages/web/app/[locale]/admin/users/page.tsx -- 删 serverAuthHeaders + is_admin
- packages/web/app/[locale]/admin/permissions/page.tsx -- 删 serverAuthHeaders + console.log
- packages/web/app/[locale]/account/settings/page.tsx -- apiFetch headers 走 perm.headers
- packages/web/lib/auth/permissions.ts -- getMyPermissions() 内部改调 getPermissions()
- packages/web/lib/hooks/index.ts -- 加 usePermissions 导出

---

## Test Coverage

| 层 | 测试内容 | 用例数 | 方式 |
|----|----------|--------|------|
| getPermissions() | 3 role cases + fetch fail | 4 | vitest mock apiFetch |
| usePermissions() | store fetch + 派生正确性 | 3 | vitest mock apiFetch |
| PageGuard | 4 role x 5 pageKey 矩阵 | 8 | vitest 组件渲染 |
| 各 page | 每个 page 2-3 场景 (user/super_admin) | 8-10 | vitest mock getPermissions |
| 集成 | curl 4 角色测试 | 6-8 | bash curl |

**全矩阵分析**: 4 角色 x 4 敏感页面 = 16 场景. PageGuard 核心测试覆盖 80%, 每页 2-3 场景覆盖路径, 不需全矩阵重复测. 详见 spec 附录 B.

---

## Task 1: 核心函数 getPermissions()

**Files:** Create packages/web/lib/auth/permission.ts + test

TDD: 写测试 (3 cases: super_admin, user, fetch fail) -> 实现 -> 跑绿 -> commit

## Task 2: Zustand store + usePermissions() hook

**Files:** Create packages/web/lib/hooks/usePermissions.ts + Modify lib/hooks/index.ts

Zustand store: role + allowed + loaded + fetch()
usePermissions: isAdminLevel/isSuperAdmin/can 派生

## Task 3: PageGuard 组件重构

**Files:** Modify packages/web/components/PageGuard.tsx

props: { pageKey: string, role: string, allowed: string[], children }
逻辑: role !== super_admin && !allowed.includes(pageKey) -> forbidden()

## Task 4-6: 切 3 个 page.tsx

每个 page 相同模式: getPermissions() -> 派生方法判断 -> redirect/forbidden/通过
PageGuard 传 role + allowed, 不再传 permissions 对象

## Task 7: 向后兼容 + 测试

getMyPermissions() 内部改调 getPermissions()
全量 vitest 跑绿 + curl 集成验证
