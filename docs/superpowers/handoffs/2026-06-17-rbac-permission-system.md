---
title: RBAC 权限系统交接
date: 2026-06-17
status: 完成
---

# RBAC 权限系统交接 (2026-06-17)

## 核心目标

实现完整 RBAC 权限系统 (4 身份 + N 角色权限组 + 7 页面权限点 + 运行时可配置 + 30s TTL cache).

## 实施方式 (4 phase, 24 task, 23 commits)

### Phase 1: 后端 Foundation (8 commits)
- `ccffce6` alembic migration (roles + role_permissions + accounts.role)
- `580837a` Role + RolePermission SQLAlchemy models
- `25cb841` PermissionCache 30s TTL sliding
- `a7eb10c` require_page / require_super_admin / require_account guards
- `0466849` Account/AccountOut/seed_admin/me/invite use role str
- `e172a72` admin router require_super_admin + role field
- `84df587` 4 router (eval/health/ingest/memory) 走 require_page

### Phase 2: 后端 API (5 commits)
- `acccedf` /api/permissions GET + PATCH + /me endpoints
- `636f729` PATCH /api/permissions 端到端测试
- `f433bbe` /api/roles GET + POST
- `7f6cf5c` /api/roles PATCH + DELETE
- `3864946` 4 身份 × 7 页面 28 case 端到端

### Phase 3: 前端 Foundation (5 commits)
- `146ec1b` role helper (isAdminLevel / isSuperAdmin)
- `54d9983` PageGuard RSC component
- `3e06829` UserMenu 权限管理 link
- `2019df2` permissions 防御校验 + ClientPageGuard + shim
- `0588032` 22 page.tsx 套 PageGuard/ClientPageGuard

### Phase 4: 前端 Admin UI (5 commits)
- `7d490a3` hide chat memory UI for anon
- `bd987c6` /admin/permissions page + PermissionsMatrix
- `d32b5fa` RoleList + CreateRoleDialog + i18n
- `9e83c1d` wire RoleList + CreateRoleDialog into /admin/permissions page
- `d211e6b` README 权限系统章节

## 全量测试结果

| 维度 | 数量 | 状态 |
|------|------|------|
| pytest (RBAC + MinIO relevant) | 225 passed, 4 skipped | ✅ |
| pytest 1 flake | test_check_python_returns_uptime (uptime > 60s) | baseline 已知 |
| typecheck (tsgo --noEmit) | 0 error | ✅ |
| 新增 pytest | 92 (45 permissions + 11 roles + 35 e2e + 1) | ✅ |
| 新增 vitest | 32 (6 文件) | ✅ |
| 12 pre-existing 失败 | i18n / app-dialog / memory-management | 跟 RBAC 无关, baseline |

## 关键设计决策

### 1. super_admin 永不入库, 代码层 meta 豁免
- PATCH 拒绝 `role_name == "super_admin"` (400)
- POST 拒绝 name="super_admin" (400)
- GET /api/permissions 过滤掉 super_admin 行
- service.get_my_permissions("super_admin") 返全部 7 页 (短路, 不查 cache)
- UI PermissionsMatrix: super_admin 行 disabled + 始终 checked

### 2. PermissionCache invalidate 触发点
- `service.update_permissions()` 写后 invalidate
- `router.create_role()` / `update_role()` / `delete_role()` 全部 invalidate
- TTL 30s sliding (防 N 角色 × 7 页全量读)

### 3. 4 层防护 (Defense in Depth)
1. 前端 PageGuard RSC (首次加载)
2. 前端 ClientPageGuard (动态路由)
3. 后端 require_page / require_super_admin (最终屏障)
4. 数据库 FK / unique 约束 (兜底)

### 4. /me 端点 anon OK
- 不需要鉴权, anon 也调得动
- 返 anon role="user" 的 allowed 列表
- 跟 /api/permissions (require_super_admin) 区别对待

### 5. 角色删除多重防御
- `is_deletable=False` (Role 模型字段) → 400
- `user_count > 0` → 409 (防止删了角色后用户 role 字段指向不存在的 name)

### 6. Chat 记忆 UI 隐藏 (Task 20)
- ChatShell.tsx 加 `isAccount` prop (默认 true 保持兼容)
- chat/page.tsx 拉 /api/account/me 拿 is_account, 401 视作 anon
- Brain 按钮用 `{isAccount && <Button...>}` 条件渲染

## Plan / Spec 偏差

1. **ALL_PAGE_KEYS** = `["dashboard", "knowledge", "chat", "memory", "evaluate", "submissions", "admin"]` (跟 spec 一致)
2. **Role 字段类型**: spec 说 str, 实施用 str (varchar) - 一致
3. **Task 22 拆分**: agent 把 Task 22 + 23 + 集成拆 3 commits (RoleList + CreateRoleDialog, i18n, 集成)
4. **Phase 4 agent 自我决策**: PermissionsMatrix 用原生 `<table>` + 自定义 Checkbox, 不用 DataTable (矩阵布局自由)

## 关键文件 (新增)

**后端**:
- `packages/service/src/permissions/{models,service,router,cache,guards}.py`
- `packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py`
- `packages/service/tests/permissions/{test_models,test_cache,test_guards,test_router}.py`
- `packages/service/tests/roles/test_router.py`
- `packages/service/tests/integration/test_rbac_e2e.py`

**前端**:
- `packages/web/lib/auth/role.ts`
- `packages/web/components/{PageGuard,ClientPageGuard}.tsx`
- `packages/web/app/[locale]/admin/permissions/{page,_components/{PermissionsMatrix,RoleList,CreateRoleDialog,PermissionsAdminClient}}.tsx`
- `packages/web/app/[locale]/admin/permissions/{_components/*.test,page.test}.tsx`

**修改**:
- `accounts.role: str` (替换 `is_admin: bool`)
- 10 router 加 require_page / require_super_admin / require_account
- 22 page.tsx 加 PageGuard / ClientPageGuard
- header.tsx nav filter
- layout.tsx 拉 /me + /permissions/me
- UserMenu 显示 role badge + 权限管理 link
- `messages/{zh,en}.json` 各加 12 key

## 接手者速查

### 角色 → 默认权限矩阵

| 角色 | dashboard | knowledge | chat | memory | evaluate | submissions | admin |
|------|-----------|-----------|------|--------|----------|-------------|-------|
| user (anon) | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| user (account) | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| super_admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 后端 API

| 方法 | 路径 | 鉴权 |
|------|------|------|
| GET | /api/permissions | super_admin |
| PATCH | /api/permissions | super_admin |
| GET | /api/permissions/me | anon OK |
| GET | /api/roles | super_admin |
| POST | /api/roles | super_admin |
| PATCH | /api/roles/{name} | super_admin |
| DELETE | /api/roles/{name} | super_admin |

### 前端 helpers

```ts
import { isAdminLevel, isSuperAdmin, ALL_PAGE_KEYS } from "@/lib/auth/role";
import { PageGuard } from "@/components/PageGuard";
import { ClientPageGuard } from "@/components/ClientPageGuard";
```

### 跑测试

```bash
cd packages/service && uv run pytest tests/permissions/ tests/roles/ tests/integration/test_rbac_e2e.py -v
cd packages/web && bun run test
```

## 关联文档

- Plan: `docs/superpowers/plans/2026-06-17-rbac-permission-system.md`
- Spec: `docs/superpowers/specs/2026-06-17-rbac-permission-system-design.md`
- 关联: [[2026-06-16-rag-minio-integration]] — 上一个 plan