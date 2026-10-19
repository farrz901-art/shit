---
title: 账号设置模块交接
date: 2026-06-18
status: 完成
---

# 账号设置模块交接 (2026-06-18)

## 核心目标

实现账号设置模块 (头像 / 昵称 / 邮箱 / 密码 / 注销 7 天宽限期) + 7 天 APScheduler 自动清理 + 数据匿名化.

## 实施方式 (5 phase, 14 task, 21 commits)

### Phase 1: 后端 Schema (2 commits)
- `3d4bd31` alembic migration + 3 ORM 模型 (avatar_url, deletion_requested_at, EmailChange, DeletionRestore)
- `5f233fe` fix: 删 migration `server_default=sa.func.now()` (跟项目 HKT Python-side default 风格一致)

### Phase 2: 后端 API (10 commits)
- **T2.1** PATCH /profile + POST/DELETE /avatar + GET /avatar/<id> 代理
  - `94f3f11` feat + `f1b1066` fix (4 code quality items + 2 test gaps)
- **T2.2** PATCH /email + POST /email/verify 邮箱改双重验证
  - `11109fc` feat + `9b75bcd` fix (I-3 test fragility + M-1 EmailStr + M-6 docstring)
- **T2.3** PATCH /password 改密码
  - `f29db38` feat + `eaf8c6f` fix (I-1 PASSWORD_MIN_LENGTH in schema + I-3 session param consistency)
- **T2.4** GET/POST/DELETE /deletion 注销 7 天宽限期
  - `787842a` feat + `faa927d` fix (M-1 confirm_text literal match + M-2 expires_at exact value)
- **T2.5** require_active_account 守卫 + /me 加 3 字段 + /login 加 pending_deletion 标志
  - `fc6be7f` feat + `f538450` fix (M-2 remove redundant timedelta + M-4 split error msg)

### Phase 3: 前端基础 (3 commits)
- **T3.1** `22f8ea7` 7 server actions + i18n 30 key (zh+en)
- **T3.2** `a1fc308` /account/settings RSC + PageGuard + 4 Section skeleton
- **T3.2 chore** `be3500b` oxfmt 顺手格式化 (跟 T3.2 一起, 不在 plan 范围)
- **T3.3** `9c995f0` 4 Section 完整实现

### Phase 4: 前端交互 (3 commits)
- **T4.1** `8a70134` 4 Dialog (ChangeEmail/Password + Request/CancelDeletion) 替 T3.3 stub
- **T4.2** `bbfb917` AvatarUploader (文件上传 + 预览 + 移除) 接入 ProfileSection
- **T4.3** `fc90ccc` RestoreDeletionBanner + /account/restore 页 + UserMenu/SettingsDialog 链接

### Phase 5: 收尾 (2 commits)
- **T5.1** `e7a7c82` APScheduler 每天 03:00 清理 pending_deletion
- **T5.2** (this commit) e2e + handoff

## 全量测试结果

| 维度 | 数量 | 状态 |
|------|------|------|
| pytest 后端 (account_settings) | 41 passed | ✅ |
| pytest 后端 (auth + permissions) | 65+ passed, 0 regression | ✅ |
| typecheck (tsgo --noEmit) | 0 error | ✅ |
| vitest 前端 (account + restore + settings) | 24+ passed | ✅ |
| Playwright e2e | 5 case (this commit, not auto-run) | 📋 |
| APScheduler smoke | 1 job registered, 03:00 HKT daily | ✅ |

## 关键设计决策

### 1. 路由选择: 独立页 /account/settings
- 4 模块内容多, 弹框装不下
- 跟 admin/users 同构, 可深链
- PageGuard 守卫清晰

### 2. 邮箱验证 7 天宽限
- 跟注销 7 天一致
- token 寿命由 `EMAIL_CHANGE_EXPIRES_DAYS` env 控制
- dev mode 返 `verification_url`, 生产应接邮件服务 (下个 spec)

### 3. 注销数据匿名化 (非 hard delete)
- 保留 `user.id` (其他用户的 chat / memory / share 引用不能丢)
- 重置 `public_token` (旧 share link 失效)
- `display_name` → `"已注销用户 #<id>"`
- `account_id` → NULL (解绑)
- CASCADE 删 EmailChange / DeletionRestore / PasswordReset

### 4. 写操作守卫 `require_active_account`
- 7 endpoint 用 (patch_profile, post_avatar, delete_avatar, patch_email, post_email_verify, patch_password, post_deletion)
- 3 endpoint 用 `require_account` (get_deletion read + delete_deletion 撤 MUST work + get_avatar public proxy)

### 5. 登录拦截: pending_deletion 标志
- /login 返 `pending_deletion=True` + `deletion_expires_at`
- 前端挂 `RestoreDeletionBanner` 提示用户撤销
- 不阻塞登录, 但写操作被 `require_active_account` 拦截

### 6. 头像上传链路
- multipart → server (PIL verify + resize 256x256 + WebP q=85) → ObjectStore
- 代理路由 GET /avatar/<id> 走 `ObjectStore.get_bytes` (统一 1 鉴权点 + cache 1h)
- bucket 名 + URI scheme 走 `store.backend_name()` (minio vs local)

### 7. APScheduler 集成
- 启动时 `lifespan` 挂, 退出时 `shutdown(wait=False)`
- cron job 03:00 HKT (server local)
- 单次失败不影响后续运行 (`try/except` + `logger.error`)

### 8. i18n 模式
- identity mode: `zh.json` 用中文作 key + value
- 30 新 key (zh+en)
- 严格 commit 前 `node -e "JSON.parse..."` 双向校验

## 关键文件 (新增)

**后端**:
- `packages/service/src/storage/migrations/versions/20260617_120000_account_settings.py`
- `packages/service/src/auth/account_settings_schemas.py`
- `packages/service/src/auth/account_settings_service.py`
- `packages/service/src/auth/account_settings_router.py`
- `packages/service/src/scheduler/__init__.py`
- `packages/service/src/scheduler/deletion.py`
- `packages/service/tests/account_settings/` (8 个 `test_*.py` 文件)
- `packages/service/tests/integration/test_account_settings_models.py`

**前端**:
- `packages/web/app/[locale]/account/settings/page.tsx` + `_components/` (8 个 `.tsx` 文件)
- `packages/web/app/[locale]/account/restore/page.tsx` + `RestoreForm.tsx`
- `packages/web/app/_actions/account-settings.ts` (7 server actions)
- `packages/web/e2e/account-settings.spec.ts` (5 e2e case)

**修改**:
- `Account` 加 `avatar_url` + `deletion_requested_at` 字段
- `CurrentUser` schema 加 3 字段
- 8 endpoint 改 `require_account` → `require_active_account` (7 endpoint 改, 1 endpoint 改 `delete_deletion` 保持 `require_account`)
- `UserMenu` `/` → `/account/settings`
- `SettingsDialog` 激活 "账号" row
- layout 挂 `RestoreDeletionBanner`
- i18n zh+en 加 30 key
- `UserMenu`, `SettingsDialog`, `layout` 接 `me.is_pending_deletion`

## 接手者速查

### 8 endpoint 路由

| 方法 | 路径 | 鉴权 | 用途 |
|------|------|------|------|
| PATCH | /api/account/profile | require_active_account | 改昵称 |
| POST | /api/account/avatar | require_active_account | 上传头像 (multipart) |
| DELETE | /api/account/avatar | require_active_account | 删头像 |
| GET | /api/account/avatar/{account_id} | 无 (公开代理) | 头像下载 (cache 1h) |
| PATCH | /api/account/email | require_active_account | 申请改邮箱 |
| POST | /api/account/email/verify | require_active_account | 验证 token 切邮箱 |
| PATCH | /api/account/password | require_active_account | 改密码 |
| GET | /api/account/deletion | require_account | 查注销状态 |
| POST | /api/account/deletion | require_active_account | 申请注销 |
| DELETE | /api/account/deletion | require_account (撤 MUST work) | 撤销注销 |

### /me 11 字段 (T2.5)

`id`, `role`, `is_admin`, `is_account`, `account_id`, `email`, `display_name`, `is_active`, **avatar_url**, **is_pending_deletion**, **deletion_expires_at** (后 3 个新)

### LoginResponse 4 字段 (T2.5)

`token`, `account`, **pending_deletion** (新), **deletion_expires_at** (新)

### 前端 server actions

- `updateProfileAction` - PATCH /profile
- `uploadAvatarAction` - POST /avatar
- `deleteAvatarAction` - DELETE /avatar
- `requestEmailChangeAction` - PATCH /email
- `changePasswordAction` - PATCH /password
- `requestDeletionAction` - POST /deletion
- `cancelDeletionAction` - DELETE /deletion

### 跑测试

```bash
cd packages/service && uv run pytest tests/account_settings/ tests/auth/ -v
cd packages/web && bun run test -- --testPathPattern "account|UserMenu|settings"
```

### 启动 dev server

```bash
# 后端
cd packages/service && uv run python main.py
# 前端
cd packages/web && bun run dev
# Scheduler 自动在 lifespan 启动 (每 03:00 HKT 跑 purge)
```

### 跑 e2e

```bash
# 需要 seed 一个测试账号, 用 env 注入 token
E2E_TEST_TOKEN=xxx E2E_TEST_PASSWORD=yyy bun run test:e2e account-settings
```

### 环境变量 (可选, 都有默认)

```bash
# 后端
EMAIL_CHANGE_EXPIRES_DAYS=7
DELETION_GRACE_DAYS=7
DELETION_RESTORE_EXPIRES_DAYS=7
PASSWORD_MIN_LENGTH=8
```

## Plan / Spec 偏差

1. **i18n key 数**: spec §8 列出 30 key, 实际 27 新 + 3 已存在 (账号设置, 保存, 邮箱)
2. **email 验证 endpoint**: 简化为单 `POST /email/verify` 端点 (spec §4.2 原本可拆为 "验证 + 应用" 2 端点)
3. **硬编码 days=7**: `auth_account_router.py` /me 和 /login 用 `timedelta(days=7)` 而非 `DELETION_GRACE_DAYS` 常量 (import cycle 限制, T2.5 reviewer 提了, 列下个 spec refactor)
4. **审计日志**: spec §1.2 列入下个 spec (跟 logging-system spec 一起做)

## 关键 bug 修复

1. **T1.1 fix** (`5f233fe`): migration `server_default=sa.func.now()` 跟项目 HKT Python-side default 风格不一致
2. **T2.1 fix** (`f1b1066`): 4 code quality items (dead mime param, broad except, type ignore comment, DELETION_GRACE_DAYS) + 2 test gaps
3. **T2.2 fix** (`9b75bcd`): test fragility (I-3) + EmailStr (M-1) + docstring (M-6)
4. **T2.3 fix** (`eaf8c6f`): PASSWORD_MIN_LENGTH in schema (I-1) + session param consistency (I-3)
5. **T2.4 fix** (`faa927d`): confirm_text literal match (M-1) + expires_at exact value (M-2)
6. **T2.5 fix** (`f538450`): redundant timedelta import (M-2) + split error msg (M-4)

## 不在范围 (下个 spec)

- 审计日志 (account audit log) — 跟 logging-system 合并
- GDPR 数据导出
- 多设备 session 管理
- 邮件服务集成 (dev mode 直接返 `verification_url`, 生产应接 SES / SendGrid)
- 硬编码 `days=7` 重构 (用 `DELETION_GRACE_DAYS`)

## 关联文档

- Plan: `docs/superpowers/plans/2026-06-17-account-settings.md`
- Spec: `docs/superpowers/specs/2026-06-17-account-settings-design.md`
- 关联: [[2026-06-17-rbac-permission-system]] — PageGuard / require_account 复用
- 关联: [[2026-06-16-rag-minio-integration]] — 头像 ObjectStore 复用
- 关联: [[2026-06-17-logging-system]] — 审计日志 (下个 spec 合并)
