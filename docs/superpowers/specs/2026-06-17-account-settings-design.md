---
title: 账号设置模块 (含 7 天注销宽限期)
date: 2026-06-17
status: 设计
author: Claude
---

# 账号设置模块 (含 7 天注销宽限期)

## 1. 目标 & 范围

### 1.1 用户故事

| # | 故事 | 优先级 |
|---|------|--------|
| U1 | 登录用户能改自己的昵称和头像 | P0 |
| U2 | 登录用户能改邮箱 (双重验证: 输当前密码 + 验证新邮箱) | P0 |
| U3 | 登录用户能改密码 (输当前密码 + 新密码) | P0 |
| U4 | 登录用户能申请注销账号, 7 天宽限期内可撤销 | P0 |
| U5 | 申请注销后, 登录时被引导到"撤销 / 等待删除"页 | P0 |
| U6 | 7 天后定时任务自动硬删账号 + 匿名化关联数据 | P0 |
| U7 | 所有 UI 文案中英双语 | P0 |

### 1.2 不在范围 (列入下个 spec)

- **审计日志**: 改邮箱/密码/注销等操作写 `AuditLog` 表, 用户在设置页可看自己的操作历史
- **GDPR 数据导出**: 注销前可一键下载自己的聊天/memory/分享数据 ZIP
- **多设备 session 管理 + 踢出其他设备**: 当前 1 token/user, 暂不需要
- **2FA / 邮箱白名单 / 登录失败锁定**: 鉴权强化, 独立 spec

## 2. 架构总览

### 2.1 路由形态: 独立页 (用户已确认)

`/[locale]/account/settings` — RSC, 跟 `/admin/users` 同构, PageGuard 守卫.

为什么不用弹框: 4 个模块 + 头像上传 + 撤销横幅, 弹框装不下, 滚动痛苦, 复杂表单移动端体验差.

### 2.2 模块边界

| 模块 | 后端 | 前端 |
|------|------|------|
| 资料 (昵称+头像) | `PATCH /profile` `POST/DELETE /avatar` | `<ProfileSection>` `<AvatarUploader>` |
| 邮箱 | `PATCH /email` `POST /email/verify` | `<EmailSection>` `<ChangeEmailDialog>` |
| 密码 | `PATCH /password` | `<PasswordSection>` `<ChangePasswordDialog>` |
| 注销 | `POST/DELETE/GET /deletion` | `<DeletionSection>` `<RequestDeletionDialog>` `<RestoreDeletionBanner>` `<RestorePage>` |

### 2.3 守卫

| 路由 | 守卫 |
|------|------|
| `/account/settings` | `PageGuard pageKey="dashboard"` + 必须是 `is_account=True` |
| `/account/restore` | anon OK (token 本身是凭证) |
| 后端 8 endpoint | `require_account` 守卫 (已存在, RBAC v2 加的) |

## 3. 数据模型

### 3.1 alembic migration: `20260617_120000_account_settings.py`

```python
def upgrade():
    # 1. Account 加 avatar_url + deletion_requested_at
    op.add_column("accounts", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column("accounts", sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))

    # 2. 新表 email_changes
    op.create_table(
        "email_changes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("new_email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_email_changes_token", "email_changes", ["token"], unique=True)
    op.create_index("idx_email_changes_account", "email_changes", ["account_id"])

    # 3. 新表 deletion_restores (撤销用)
    op.create_table(
        "deletion_restores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_deletion_restores_token", "deletion_restores", ["token"], unique=True)
    op.create_index("idx_deletion_restores_account", "deletion_restores", ["account_id"])
```

### 3.2 SQLAlchemy 模型 (在 `account_models.py`)

```python
class Account(Base):
    # ... 已有字段 ...
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 派生属性 (Python 端):
    @property
    def is_pending_deletion(self) -> bool:
        return self.deletion_requested_at is not None

    @property
    def deletion_expires_at(self) -> datetime | None:
        if not self.deletion_requested_at:
            return None
        return self.deletion_requested_at + timedelta(days=DELETION_GRACE_DAYS)


class EmailChange(Base):
    """邮箱修改一次性 token, account_id + new_email"""
    __tablename__ = "email_changes"
    # ... 见 migration


class DeletionRestore(Base):
    """注销撤销 token, account_id"""
    __tablename__ = "deletion_restores"
    # ... 见 migration
```

### 3.3 常量

```python
# account_service.py
EMAIL_CHANGE_EXPIRES_DAYS = int(os.getenv("EMAIL_CHANGE_EXPIRES_DAYS", "7"))
DELETION_GRACE_DAYS = int(os.getenv("DELETION_GRACE_DAYS", "7"))
DELETION_RESTORE_EXPIRES_DAYS = int(os.getenv("DELETION_RESTORE_EXPIRES_DAYS", "7"))  # 跟宽限期同步
AVATAR_MAX_SIZE_MB = 2
AVATAR_ACCEPTED_MIME = {"image/png", "image/jpeg", "image/webp"}
AVATAR_OUTPUT_SIZE = 256  # px
```

## 4. API 设计 (8 endpoint, 全部 `require_account` 守卫)

### 4.1 资料

```
PATCH /api/account/profile
  body: { display_name: str (1-50), avatar_url?: str }   # avatar_url 单独走 /avatar 端点
  resp: { account: AccountOut (带 avatar_url 字段) }

POST /api/account/avatar    multipart/form-data
  body: file: UploadFile (PNG/JPG/WEBP, ≤ 2MB)
  服务端: PIL 打开 → resize 256x256 → 存 WebP → ObjectStore.put_bytes(s3://rag-avatars/<id>.<hash>.webp)
  resp: { avatar_url: str }

DELETE /api/account/avatar
  resp: { ok: true }  # 清空 Account.avatar_url
```

### 4.2 邮箱

```
PATCH /api/account/email
  body: { new_email: str, current_password: str }
  校验: current_password 正确, new_email 不跟别人重复, 格式合法
  resp: { verification_url: str, expires_at: datetime }
  # dev 模式: 返 URL; 生产: 应接邮件服务 (本期不接, log 警告)

POST /api/account/email/verify
  body: { token: str }
  校验: token 存在 + 未 used + 未过期 + new_email 仍可用
  resp: { ok: true, email: str }  # 切换 email + 标 used_at
```

### 4.3 密码

```
PATCH /api/account/password
  body: { current_password: str, new_password: str (≥ 8), confirm: str }
  校验: current 正确, new == confirm, new ≥ 8
  resp: { ok: true }
  # 不踢出当前 session
```

### 4.4 注销

```
GET /api/account/deletion
  resp: { pending: bool, deletion_requested_at?, expires_at? }
  # 注意: restore_token 不返 GET (防泄漏); 仅在 POST /deletion 响应里返一次
  # pending=False → 200 正常; pending=True → 含倒计时

POST /api/account/deletion
  body: { current_password: str, confirm_text: "我要注销" }
  校验: current 正确, confirm_text 字面匹配
  行为: Account.is_active=False, deletion_requested_at=now, 创 DeletionRestore token
  resp: { deletion_requested_at, expires_at, restore_url }

DELETE /api/account/deletion
  body: { current_password: str }
  校验: current 正确, 当前处于 pending_deletion
  行为: 清空 deletion_requested_at, 标 DeletionRestore.used_at, 重置 is_active=True
  resp: { ok: true }
```

### 4.5 `/me` 增强

```python
# GET /api/account/me
# 已存在, 加 2 字段:
{
  ...原有 8 字段,
  "avatar_url": str | null,
  "is_pending_deletion": bool,  # 派生 from deletion_requested_at
  "deletion_expires_at": datetime | null
}
```

## 5. 注销状态机 (核心)

### 5.1 状态定义

```
active (is_active=True, deletion_requested_at=null)
  │
  ├─ POST /deletion (输密码) ──> pending_deletion
  │     │
  │     ├─ DELETE /deletion (输密码) ──> active  (撤销)
  │     │
  │     ├─ token 撤销链接点击 ──> active  (邮件撤销)
  │     │
  │     └─ 7 天到期 (APScheduler) ──> hard_delete + anonymize
  │
  └─ (任何时刻) 登录拦截 (见 §5.3)
```

### 5.2 pending_deletion 期间行为

| 操作 | 是否允许 | 说明 |
|------|----------|------|
| 查 `/me` | ✅ 允许 | 返 `is_pending_deletion=true` 提示前端 |
| 写操作 (上传文档/创建 share/发消息) | ❌ 403 | `require_account + is_active` 双重检查 |
| 撤销 (输密码) | ✅ 允许 | 走 DELETE /deletion |
| 撤销 (邮件链接) | ✅ 允许 | 走 `/account/restore?token=xxx` |
| 登出 | ✅ 允许 | 走 POST /logout |
| 重新登录 | ⚠️ 受限 | 见 §5.3 |

### 5.3 登录拦截

```python
# POST /api/account/login 现有逻辑 + 检查
# 注: 本期不引入"短 token" 概念, 走更简单的设计:
#  pending_deletion 账号仍返正常 token, 但 login 响应里加 pending_deletion 标志
#  前端拿到标志 → 强制重定向到 /account/restore?account_id=<id>
#  /account/restore 页面用正常 user 鉴权, 显示倒计时 + 撤销按钮
# 撤销时校验 password, 通过后撤销并清 is_active=True

# 在 LoginResponse 加字段 (新加, 不破坏老 schema 兼容):
class LoginResponse(BaseModel):
    token: str
    account: AccountOut
    pending_deletion: bool = False  # 新加, 默认 False 兼容老前端
    deletion_expires_at: datetime | None = None  # 新加, pending_deletion=true 时填
```

**简化理由**: 短 token 设计引入"双 token 表"复杂度, 但 7 天内用户仍可正常访问, 走前端重定向足以. 守卫不需要改 — pending_deletion 期间的写操作拦截在 §5.2 已经覆盖 (各业务 endpoint 走 `is_active=True` 检查).

写操作守卫增强 (在 `require_account` 旁加 `require_active_account`):

```python
# src/permissions/guards.py
def require_active_account(user: CurrentUser = Depends(require_account)) -> CurrentUser:
    if not user.is_active or user.is_pending_deletion:
        raise HTTPException(403, "account is pending deletion")
    return user
```

### 5.4 写操作守卫迁移

pending_deletion 期间禁用所有写操作 (除 `DELETE /deletion` 撤销自己). 不改 `require_account`, 改在各业务 endpoint 加 `Depends(require_active_account)`. 涉及 endpoint 列表 (review 时核对): ingest / knowledge / chat / memory / share / evaluation / kg / 任何 `POST/PATCH/DELETE`.

### 5.5 7 天后硬删 + 匿名化

```python
# scheduler/deletion.py (新)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

async def purge_pending_deletions():
    """每天跑 1 次, 处理到期的 pending_deletion 账号"""
    cutoff = datetime.now(HKT) - timedelta(days=DELETION_GRACE_DAYS)
    with session_scope() as s:
        victims = s.query(Account).filter(
            Account.deletion_requested_at.isnot(None),
            Account.deletion_requested_at < cutoff
        ).all()
        for account in victims:
            anonymize_account(s, account)
            s.flush()
            s.delete(account)  # CASCADE 删 EmailChange, DeletionRestore, PasswordReset
        log.info(f"purged {len(victims)} accounts")


def anonymize_account(s, account: Account) -> None:
    """匿名化用户关联数据, 保留数据引用链"""
    user = s.query(User).filter_by(account_id=account.id).first()
    if user is not None:
        # 重置 public_token (防止旧 share link 找账号)
        user.public_token = secrets.token_hex(32)
        user.account_id = None
        user.display_name = f"已注销用户 #{user.id}"
    # 注: chat_messages / chat_shares / memories / evaluations 仍指向 user.id, 但 user 已匿名
```

启动时注册 (在 `product_decoders/app.py` 的 `create_app`):

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .scheduler.deletion import purge_pending_deletions

def register_schedulers(app):
    scheduler = AsyncIOScheduler(timezone="Asia/Hong_Kong")
    scheduler.add_job(purge_pending_deletions, "cron", hour=3, minute=0)  # 每天凌晨 3 点
    scheduler.start()
```

## 6. 头像上传链路

### 6.1 流程

```
[用户] 选文件 (≤ 2MB, PNG/JPG/WEBP)
   │
   ▼
[前端] FileDropzone 校验 mime + size
   │
   ▼
[前端] POST /api/account/avatar (multipart)
   │
   ▼
[后端] PIL verify + resize 256x256 + WebP 转码
   │
   ▼
[后端] ObjectStore.put_bytes(uri, data, mime="image/webp")
   │   uri = f"s3://rag-avatars/{account_id}.{hash}.webp"
   │   或 f"local://avatars/{account_id}.{hash}.webp"
   │
   ▼
[后端] Account.avatar_url = uri
   │
   ▼
[后端] 返 { avatar_url }
   │
   ▼
[前端] UserMenu / ProfileSection 重新渲染头像
```

### 6.2 关键点

- **服务端裁剪**: 不依赖前端 `<canvas>`, 避免被绕过
- **WebP 统一**: 输出格式, 体积小, 全浏览器支持
- **Hash 命名**: `<account_id>.<content_hash>.webp` — 同一账号重复上传覆盖, 不会堆积
- **不签 URL**: 头像本身公开可读, ObjectStore 用 public bucket 或在 FastAPI 加 `/api/account/avatar/<id>` 代理
- **选代理方案**: `GET /api/account/avatar/<account_id>` → ObjectStore.get_bytes → Response (image/webp, cache 1h). 原因: MinIO public bucket 在生产环境需额外配置 + ACL, 代理路由统一 1 个鉴权点 (可后续加 CDN), 测试也好做 (mock ObjectStore)
- **代理路由** (本次实现): `GET /api/account/avatar/<account_id>` → 查 Account.avatar_url → ObjectStore.get_bytes → Response (image/webp, cache 1h)

### 6.3 PIL 选型

- `Pillow>=10.0` 已装 (RAG 现有依赖, 看 `pyproject.toml`)
- 处理: `Image.open(io.BytesIO(data))` → `img.convert("RGBA")` → `img.resize((256, 256), Image.LANCZOS)` → `img.save(buf, "WEBP", quality=85)`
- 异常: `Image.DecompressionBomb` / `OSError` → 422 invalid image

## 7. 前端结构

### 7.1 路由

```
/[locale]/account/
  ├── settings/
  │   ├── page.tsx                       # RSC, PageGuard
  │   ├── page.test.tsx
  │   ├── _components/
  │   │   ├── ProfileSection.tsx
  │   │   ├── ProfileSection.test.tsx
  │   │   ├── EmailSection.tsx
  │   │   ├── EmailSection.test.tsx
  │   │   ├── PasswordSection.tsx
  │   │   ├── PasswordSection.test.tsx
  │   │   ├── DeletionSection.tsx
  │   │   ├── DeletionSection.test.tsx
  │   │   ├── AvatarUploader.tsx
  │   │   ├── ChangeEmailDialog.tsx
  │   │   ├── ChangePasswordDialog.tsx
  │   │   ├── RequestDeletionDialog.tsx
  │   │   ├── RestoreDeletionBanner.tsx  (pending_deletion 时显示)
  │   │   ├── RestoreDeletionBanner.test.tsx
  │   │   └── AccountSettingsClient.tsx  (客户端 orchestration)
  │   └── _actions/                       # server actions 走 app/_actions/
  └── restore/
      ├── page.tsx                       # 撤销页 (anon OK, token 验证)
      └── page.test.tsx
```

### 7.2 server actions (`app/_actions/account-settings.ts`)

```ts
"use server";
// 7 个 server action, 走 apiFetch + useActionState
export async function updateProfileAction(prev, formData): Promise<ProfileState>
export async function uploadAvatarAction(prev, formData): Promise<AvatarState>  // multipart
export async function deleteAvatarAction(): Promise<AvatarState>
export async function requestEmailChangeAction(prev, formData): Promise<EmailState>
export async function changePasswordAction(prev, formData): Promise<PasswordState>
export async function requestDeletionAction(prev, formData): Promise<DeletionState>
export async function cancelDeletionAction(prev, formData): Promise<DeletionState>
```

### 7.3 UserMenu 链接修复

```diff
- <Link href="/">{t("账号设置")}</Link>
+ <Link href="/account/settings" data-testid="menu-account-settings">
+   {t("账号设置")}
+ </Link>
```

### 7.4 SettingsDialog "账号" 行激活

```diff
- <div className="flex items-center justify-between px-6 py-4 opacity-60">
-   <span className="text-sm font-medium">账号</span>
-   <Badge variant="outline">admin</Badge>
- </div>
+ <LocalizedLink href="/account/settings" onClick={() => onOpenChange(false)}
+   className="flex items-center justify-between px-6 py-4 hover:bg-muted/50">
+   <span className="text-sm font-medium">账号</span>
+   <ChevronRight className="h-4 w-4 text-muted-foreground" />
+ </LocalizedLink>
```

### 7.5 撤销横幅

pending_deletion 用户访问任意页面, layout 顶部显示:

```tsx
<RestoreDeletionBanner
  expiresAt={me.deletion_expires_at}
  onCancel={cancelDeletionAction}
/>
```

横幅高 (60px), 红色, 含倒计时 + "立即撤销" 按钮 + "查看详情" 链接.

## 8. i18n (zh + en)

`messages/zh.json` + `messages/en.json` 加以下 key (identity 模式: 中文作 key, value=中文):

```json
{
  "账号设置": "账号设置",
  "修改昵称": "修改昵称",
  "修改头像": "修改头像",
  "支持 PNG / JPG / WebP, ≤ 2MB": "支持 PNG / JPG / WebP, ≤ 2MB",
  "更换头像": "更换头像",
  "移除头像": "移除头像",
  "邮箱": "邮箱",
  "邮箱未验证": "邮箱未验证",
  "修改邮箱": "修改邮箱",
  "新邮箱": "新邮箱",
  "当前密码": "当前密码",
  "新密码": "新密码",
  "确认新密码": "确认新密码",
  "修改密码": "修改密码",
  "注销账号": "注销账号",
  "注销账号提示": "注销后 7 天内可撤销, 7 天后账号和关联数据将永久删除并匿名化",
  "撤销注销": "撤销注销",
  "账号将在 {days} 天后删除": "账号将在 {days} 天后删除",
  "确认注销": "确认注销",
  "请输入 '我要注销' 确认": "请输入 '我要注销' 确认",
  "撤销账号注销": "撤销账号注销",
  "撤销成功": "撤销成功",
  "头像上传失败": "头像上传失败",
  "邮箱已被使用": "邮箱已被使用",
  "当前密码错误": "当前密码错误",
  "两次密码不一致": "两次密码不一致",
  "密码至少 8 位": "密码至少 8 位",
  "验证链接无效或已过期": "验证链接无效或已过期",
  "请在 7 天内点击验证链接完成修改": "请在 7 天内点击验证链接完成修改"
}
```

总计 ~30 key × 2 语言.

## 9. 测试策略

### 9.1 模式选择 (跟 RBAC handoff 一致)

| 类别 | 模式 | 说明 |
|------|------|------|
| 业务逻辑 (state machine, 校验) | **模式 1 纯单测 (mock)** | 不连 PG, 用 mock session |
| ORM 字段 / 新表 schema | **模式 2 集成 (事务回滚)** | 走 `db_session` fixture |
| API 端到端 | **模式 4 E2E (独立测试 DB)** | 走 Playwright + 独立 DB |
| 前端组件 | vitest + jsdom | 跟现有 32 个 test 同模式 |
| E2E | Playwright | 加 5-8 case 到 `web/e2e/` |

### 9.2 后端测试清单 (~25 case)

- `test_account_settings.py` (模式 1, 12 case)
  - update_profile: 正常 + display_name 长度 + 重复
  - upload_avatar: mime 校验 + size 校验 + 损坏文件
  - request_email_change: current_password 错 + email 重复 + 格式
  - verify_email: token 过期 + 已用 + 邮箱被占
  - change_password: current 错 + 长度 + confirm 不一致
  - request_deletion: current 错 + 确认文字错 + 重复申请 (覆盖前 token?)
  - cancel_deletion: current 错 + 未申请

- `test_deletion_state.py` (模式 1, 5 case)
  - 状态机转换: active → pending → active → pending
  - is_active 立即为 False
  - 7 天后 purge: hard_delete + anonymize

- `test_email_change.py` (模式 2, 4 case)
  - 新表 CRUD
  - CASCADE 行为
  - token unique 约束

- `test_deletion_restore.py` (模式 2, 4 case)
  - 新表 CRUD
  - CASCADE 行为

### 9.3 前端测试 (~15 case)

- ProfileSection: 头像上传后 URL 更新 + display_name 保存
- EmailSection: 弹 dialog 流程
- PasswordSection: 校验提示
- DeletionSection: pending / non-pending 双状态
- RestoreDeletionBanner: 倒计时 + 撤销按钮
- page.tsx: PageGuard 集成

### 9.4 E2E (Playwright, ~6 case)

1. 登录 → 改昵称 → 重载 → 看到新昵称
2. 头像上传 → UserMenu 看到新头像
3. 改密码 → 登出 → 用新密码登录
4. 改邮箱 (输 token) → /me 看到新邮箱
5. 申请注销 → 横幅显示 → 撤销 → 横幅消失
6. 7 天后清理 (mock 时间) → 数据匿名化

## 10. 风险 & 缓解

| 风险 | 缓解 |
|------|------|
| 7 天宽限期 AP 跑挂导致逾期不清 | 启动时 + login 时双检查 (lazy check), 详见 §5 |
| 头像上传 OOM | PIL DecompressionBomb 防护, max 2MB |
| 邮箱改一半时原邮箱被占 | 验证时再校验 new_email 可用, 已被占 → 422 |
| pending_deletion 期间忘记改 | 横幅 + 邮件链接双通道, 7 天足够长 |
| hard delete 关联 cascade 漏 | migration 显式 CASCADE, 测试覆盖 |
| 注销撤销 token 被劫持 | token 64 字节 hex, 单次使用, 7 天过期, https only |
| 多端点同时调用 8 API 的事务 | 走 session_scope 自动事务, 跟现有一致 |
| i18n key 漏同步 | commit 前跑 `node -e "JSON.parse(...)" 双向校验` |
| APScheduler 启停状态 (FastAPI reload) | 用 lifespan 挂载, 跟 connection pool 同步启停 |

## 11. Phase 拆分 & 估 commit

| Phase | 范围 | 估 commit |
|-------|------|----------|
| 1 后端 schema | alembic migration + 3 模型 + 3 service 函数 | 1 |
| 2 后端 API + 测试 | 8 endpoint + 25 单测 + 4 集成测 | 5 |
| 3 前端基础 | /account/settings RSC + 4 Section + server actions + i18n | 3 |
| 4 前端交互 | 4 Dialog + 头像上传 + 撤销横幅 + 撤销页 | 3 |
| 5 APScheduler + e2e + 文档 | 定时清理 + 6 E2E + handoff 文档 | 2 |
| **合计** | | **14 commits** |

## 12. 移交 checklist

- [ ] 14 commit 入库, master HEAD
- [ ] pytest 全过 (含 25+8 新增)
- [ ] tsgo --noEmit 0 error
- [ ] vitest 32+15 全过
- [ ] Playwright e2e 18+6 全过
- [ ] handoff 文档: `docs/superpowers/handoffs/2026-06-17-account-settings.md`
- [ ] i18n zh + en 30 key 入库
- [ ] frontend E2E 截图归档 (1 张 4 模块总览)
- [ ] API 文档同步 (FastAPI 自动渲染, 加 summary/description)

## 13. 关联文档

- Plan (待写): `docs/superpowers/plans/2026-06-17-account-settings.md`
- 关联: [[2026-06-17-rbac-permission-system]] — PageGuard / require_account 复用
- 关联: [[2026-06-16-rag-minio-integration]] — 头像 ObjectStore 复用
- 关联: [[2026-06-16-test-isolation]] — 测试 4 模式
- 关联 (下个 spec): 审计日志 + GDPR 数据导出
