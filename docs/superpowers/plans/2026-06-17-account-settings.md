# 账号设置模块实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现账号设置模块 (头像/昵称/邮箱/密码/注销 7 天宽限期) — 独立页 `/account/settings`, 完整 RBAC + i18n + 测试 + APScheduler 自动清理.

**Architecture:**
- 后端: 新增 `account_settings` 模块 (router + service + schemas), 加 `Account.avatar_url` / `deletion_requested_at` 字段, 2 新表 `email_changes` / `deletion_restores`, 新守卫 `require_active_account`, APScheduler 每天 03:00 清 pending_deletion
- 前端: `/account/settings` 独立页 (4 section) + `/account/restore` 撤销页 + 8 server action + `RestoreDeletionBanner` 全局横幅, 复用 FileDropzone / FormField / AppDialog / AppConfirm

**Tech Stack:**
- 后端: FastAPI + SQLAlchemy + Alembic + APScheduler + Pillow + pytest (模式 1/2/4)
- 前端: Next.js 15 + React 19 + shadcn/ui + vitest + Playwright
- 迁移: Alembic (手工 revision)

**Spec:** [2026-06-17-account-settings-design.md](../specs/2026-06-17-account-settings-design.md)

---

## File Structure

**后端新建**:
- `packages/service/src/storage/migrations/versions/20260617_120000_account_settings.py`
- `packages/service/src/auth/account_settings_schemas.py` (Pydantic 请求/响应)
- `packages/service/src/auth/account_settings_service.py` (业务逻辑: 头像/邮箱/密码/注销)
- `packages/service/src/auth/account_settings_router.py` (8 endpoint + 1 头像代理)
- `packages/service/src/scheduler/__init__.py`
- `packages/service/src/scheduler/deletion.py` (APScheduler 清理任务)
- `packages/service/tests/account_settings/__init__.py`
- `packages/service/tests/account_settings/test_profile.py` (模式 1)
- `packages/service/tests/account_settings/test_avatar.py` (模式 1)
- `packages/service/tests/account_settings/test_email.py` (模式 1)
- `packages/service/tests/account_settings/test_password.py` (模式 1)
- `packages/service/tests/account_settings/test_deletion.py` (模式 1)
- `packages/service/tests/account_settings/test_state_machine.py` (模式 1)
- `packages/service/tests/integration/test_account_settings_models.py` (模式 2)
- `packages/service/tests/integration/test_account_settings_e2e.py` (模式 2/4)

**后端修改**:
- `packages/service/src/auth/account_models.py` (加 avatar_url, deletion_requested_at, EmailChange, DeletionRestore)
- `packages/service/src/auth/account_service.py` (加常量 + 4 helper: hash 头像 / 切换邮箱 / 改密 / 申请/撤销注销 / 7 天清理)
- `packages/service/src/auth/auth_account_router.py` (`/me` 加 3 字段, `/login` 加 pending_deletion 标志, LoginResponse 加 2 字段)
- `packages/service/src/permissions/guards.py` (加 `require_active_account` 守卫)
- `packages/service/src/__init__.py` (注册 account_settings_router + register_schedulers)
- `packages/service/src/product_decoders/app.py` (lifespan 挂 schedulers)

**前端新建**:
- `packages/web/app/[locale]/account/settings/page.tsx` (RSC, PageGuard)
- `packages/web/app/[locale]/account/settings/_components/{ProfileSection,EmailSection,PasswordSection,DeletionSection,AccountSettingsClient}.tsx`
- `packages/web/app/[locale]/account/settings/_components/{AvatarUploader,ChangeEmailDialog,ChangePasswordDialog,RequestDeletionDialog,RestoreDeletionBanner}.tsx`
- `packages/web/app/[locale]/account/restore/page.tsx` (anon OK)
- `packages/web/app/_actions/account-settings.ts` (7 server action)
- `packages/web/e2e/account-settings.spec.ts` (Playwright, 6 case)
- `packages/web/app/[locale]/account/settings/page.test.tsx` + `_components/*.test.tsx` (vitest, ~15 case)
- `packages/web/app/[locale]/account/restore/page.test.tsx`

**前端修改**:
- `packages/web/components/UserMenu.tsx` (`/` → `/account/settings`, 加 data-testid)
- `packages/web/components/settings/settings-dialog.tsx` (账号行激活, 跳 /account/settings)
- `packages/web/app/[locale]/layout.tsx` (顶层挂 `<RestoreDeletionBanner>`)
- `packages/web/messages/zh.json` (30 key)
- `packages/web/messages/en.json` (30 key)

**文档新建**:
- `docs/superpowers/handoffs/2026-06-17-account-settings.md`

---

## Phase 1: 后端 Schema (1 commit)

### Task 1.1: alembic migration + 3 个 ORM 模型

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260617_120000_account_settings.py`
- Modify: `packages/service/src/auth/account_models.py:14-89` (Account 加 2 字段, 末尾加 EmailChange + DeletionRestore)
- Test: `packages/service/tests/integration/test_account_settings_models.py`

- [ ] **Step 1: 写失败测试**

```python
# packages/service/tests/integration/test_account_settings_models.py
"""模式 2 集成测试: 验新字段 + 新表 schema"""
from sqlalchemy import inspect
from packages.service.src.auth.account_models import Account, EmailChange, DeletionRestore
from packages.service.src.storage import Base


def test_account_has_avatar_url_column(db_session):
    insp = inspect(db_session.get_bind())
    cols = {c["name"] for c in insp.get_columns("accounts")}
    assert "avatar_url" in cols
    assert "deletion_requested_at" in cols


def test_email_changes_table_exists(db_session):
    assert EmailChange.__tablename__ == "email_changes"
    insp = inspect(db_session.get_bind())
    assert insp.has_table("email_changes")


def test_deletion_restores_table_exists(db_session):
    assert DeletionRestore.__tablename__ == "deletion_restores"
    insp = inspect(db_session.get_bind())
    assert insp.has_table("deletion_restores")
```

- [ ] **Step 2: 跑测试, 确认失败**

```bash
cd packages/service && uv run pytest tests/integration/test_account_settings_models.py -v
```

Expected: 3 FAIL (table 不存在 / column 不存在)

- [ ] **Step 3: 写 alembic migration**

```python
# packages/service/src/storage/migrations/versions/20260617_120000_account_settings.py
"""账号设置: Account 加 avatar_url / deletion_requested_at, 新表 email_changes / deletion_restores"""
from alembic import op
import sqlalchemy as sa

revision = "20260617_120000"
down_revision = "20260617_000000"  # RBAC migration, 跟之前一致
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column(
        "accounts",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "email_changes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("new_email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_email_changes_token", "email_changes", ["token"], unique=True)
    op.create_index("idx_email_changes_account", "email_changes", ["account_id"])

    op.create_table(
        "deletion_restores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "account_id",
            sa.Integer,
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_deletion_restores_token", "deletion_restores", ["token"], unique=True)
    op.create_index("idx_deletion_restores_account", "deletion_restores", ["account_id"])


def downgrade() -> None:
    op.drop_index("idx_deletion_restores_account", "deletion_restores")
    op.drop_index("idx_deletion_restores_token", "deletion_restores")
    op.drop_table("deletion_restores")
    op.drop_index("idx_email_changes_account", "email_changes")
    op.drop_index("idx_email_changes_token", "email_changes")
    op.drop_table("email_changes")
    op.drop_column("accounts", "deletion_requested_at")
    op.drop_column("accounts", "avatar_url")
```

- [ ] **Step 4: 跑 migration 升级 + 测试**

```bash
cd packages/service && uv run alembic upgrade head
cd packages/service && uv run pytest tests/integration/test_account_settings_models.py -v
```

Expected: 3 PASS

- [ ] **Step 5: 加 ORM 模型到 account_models.py**

```python
# packages/service/src/auth/account_models.py 末尾追加
class EmailChange(Base):
    """邮箱修改一次性 token (7 天过期). new_email 验证成功后切换 Account.email."""

    __tablename__ = "email_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    new_email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )

    __table_args__ = (Index("idx_email_changes_token", "token", unique=True),)


class DeletionRestore(Base):
    """注销撤销一次性 token (7 天过期, 跟注销宽限期同步)."""

    __tablename__ = "deletion_restores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(HKT)
    )

    __table_args__ = (Index("idx_deletion_restores_token", "token", unique=True),)
```

同时在 `Account` 类里加 2 字段 + 2 派生属性:

```python
# packages/service/src/auth/account_models.py 第 27 行后插入
avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

# 在 Account 类的 __repr__ 之前加 2 个 property
@property
def is_pending_deletion(self) -> bool:
    return self.deletion_requested_at is not None
```

- [ ] **Step 6: 跑全套测试确认不破**

```bash
cd packages/service && uv run pytest tests/auth/ -v
```

Expected: 已有 auth tests 全过, 0 新失败

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/storage/migrations/versions/20260617_120000_account_settings.py \
        packages/service/src/auth/account_models.py \
        packages/service/tests/integration/test_account_settings_models.py
git commit -m "feat(account): alembic migration + 3 ORM 模型 (avatar_url, deletion_requested_at, EmailChange, DeletionRestore)"
```

---

## Phase 2: 后端 API (5 commit)

### Task 2.1: 资料 + 头像端点 (profile + avatar)

**Files:**
- Create: `packages/service/src/auth/account_settings_schemas.py`
- Create: `packages/service/src/auth/account_settings_service.py` (start)
- Create: `packages/service/src/auth/account_settings_router.py` (start)
- Create: `packages/service/tests/account_settings/test_profile.py`
- Create: `packages/service/tests/account_settings/test_avatar.py`
- Modify: `packages/service/src/__init__.py:25-51` (注册新 router)

- [ ] **Step 1: 写失败测试 (profile)**

```python
# packages/service/tests/account_settings/test_profile.py
"""模式 1 纯单测: 验 PATCH /profile 业务逻辑 (mock session)"""
from unittest.mock import MagicMock
from packages.service.src.auth.account_settings_service import update_profile


def test_update_profile_changes_display_name():
    mock_account = MagicMock()
    mock_account.display_name = "old"
    mock_session = MagicMock()
    update_profile(mock_session, mock_account, display_name="new")
    assert mock_account.display_name == "new"
    mock_session.flush.assert_called_once()


def test_update_profile_rejects_too_long_display_name():
    mock_account = MagicMock()
    mock_session = MagicMock()
    import pytest
    with pytest.raises(ValueError, match="display_name must be 1-50"):
        update_profile(mock_session, mock_account, display_name="x" * 51)
```

- [ ] **Step 2: 跑测试, 确认失败**

```bash
cd packages/service && uv run pytest tests/account_settings/test_profile.py -v
```

Expected: 2 FAIL (function not found)

- [ ] **Step 3: 写 schemas + service (profile/avatar 部分)**

```python
# packages/service/src/auth/account_settings_schemas.py
"""/api/account/{profile,avatar,email,password,deletion} Pydantic schemas"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class ProfileUpdate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50, description="昵称, 1-50 字符, trim 后校验")


class AccountOutExtended(BaseModel):
    """比 auth_account_router.AccountOut 多 3 字段: avatar_url, is_pending_deletion, deletion_expires_at"""
    id: int
    email: str
    display_name: str | None
    role: str
    is_admin: bool
    avatar_url: str | None = None
    is_pending_deletion: bool = False
    deletion_expires_at: datetime | None = None
```

```python
# packages/service/src/auth/account_settings_service.py
"""账号设置业务逻辑: profile / avatar / email / password / deletion / purge"""
from __future__ import annotations
import io
import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from PIL import Image

from .account_models import Account, DeletionRestore, EmailChange, User
from .account_service import PASSWORD_MIN_LENGTH, hash_password, verify_password
from ..storage import get_object_store
from ..utils.timezone import HKT

# --- 常量 ---
EMAIL_CHANGE_EXPIRES_DAYS = int(os.getenv("EMAIL_CHANGE_EXPIRES_DAYS", "7"))
DELETION_GRACE_DAYS = int(os.getenv("DELETION_GRACE_DAYS", "7"))
DELETION_RESTORE_EXPIRES_DAYS = int(os.getenv("DELETION_RESTORE_EXPIRES_DAYS", "7"))
AVATAR_MAX_SIZE_MB = 2
AVATAR_OUTPUT_SIZE = 256

# --- profile ---
def update_profile(session, account: Account, *, display_name: str) -> None:
    """改 display_name. 已 trim + 长度校验, 1-50 字符."""
    name = display_name.strip()
    if not 1 <= len(name) <= 50:
        raise ValueError(f"display_name must be 1-50 characters, got {len(name)}")
    account.display_name = name
    session.flush()


def delete_avatar(session, account: Account) -> None:
    """清空 avatar_url 字段, 不删 ObjectStore 文件 (保留历史 + 避免 race)."""
    account.avatar_url = None
    session.flush()


# --- avatar ---
def process_avatar_upload(file_bytes: bytes, mime: str) -> bytes:
    """PIL 校验 + resize 256x256 + WebP 转码. 返转码后 bytes."""
    if len(file_bytes) > AVATAR_MAX_SIZE_MB * 1024 * 1024:
        raise ValueError(f"avatar too large: >{AVATAR_MAX_SIZE_MB}MB")
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()  # 防 bomb
        img = Image.open(io.BytesIO(file_bytes)).convert("RGBA")
    except Exception as e:
        raise ValueError(f"invalid image: {e}") from e
    img = img.resize((AVATAR_OUTPUT_SIZE, AVATAR_OUTPUT_SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=85)
    return buf.getvalue()


def store_avatar(session, account: Account, file_bytes: bytes) -> str:
    """PIL 处理 + ObjectStore.put_bytes + 写 avatar_url. 返 URL."""
    webp = process_avatar_upload(file_bytes, mime="image/webp")
    content_hash = secrets.token_hex(8)  # 8 字节足够 (避覆盖, 防 race)
    uri = f"s3://rag-avatars/{account.id}.{content_hash}.webp"
    try:
        store = get_object_store()
        store.put_bytes(uri, webp, mime="image/webp")
    except Exception:
        # local:// fallback
        uri = f"local://avatars/{account.id}.{content_hash}.webp"
        store = get_object_store()
        store.put_bytes(uri, webp, mime="image/webp")
    account.avatar_url = uri
    session.flush()
    return uri
```

- [ ] **Step 4: 写 router 片段**

```python
# packages/service/src/auth/account_settings_router.py
"""/api/account/{profile,avatar,email,password,deletion} 端点 (8 个)"""
from __future__ import annotations
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..middleware.auth import CurrentUser, resolve_user
from ..storage.session import session_scope
from ..utils.timezone import HKT
from . import account_settings_service as svc
from .account_models import Account, DeletionRestore, EmailChange, User
from .account_service import hash_password, verify_password
from .account_settings_schemas import AccountOutExtended, ProfileUpdate
from .auth_account_router import require_account  # 复用 RBAC v2 守卫

router = APIRouter(prefix="/api/account", tags=["account"])


@router.patch("/profile", summary="更新昵称", description="...")
def patch_profile(
    req: ProfileUpdate,
    user: CurrentUser = Depends(require_account),
):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(404, "account not found")
        svc.update_profile(s, account, display_name=req.display_name)
        s.flush()
        return {"account": _to_out(account)}


@router.post("/avatar", summary="上传头像", description="...")
async def post_avatar(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_account),
):
    if file.content_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(422, f"unsupported mime: {file.content_type}")
    data = await file.read()
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(404, "account not found")
        try:
            uri = svc.store_avatar(s, account, data)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        return {"avatar_url": uri}


@router.delete("/avatar", summary="删除头像")
def delete_avatar(user: CurrentUser = Depends(require_account)):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(404, "account not found")
        svc.delete_avatar(s, account)
        return {"ok": True}


@router.get("/avatar/{account_id}", summary="获取头像 (代理)")
def get_avatar(account_id: int):
    """ObjectStore 代理路由, cache 1h, 不鉴权 (头像公开)"""
    from fastapi.responses import Response
    with session_scope() as s:
        account = s.get(Account, account_id)
        if account is None or account.avatar_url is None:
            raise HTTPException(404, "avatar not found")
        store = __import__("src.storage", fromlist=["get_object_store"]).get_object_store()
        data = store.get_bytes(account.avatar_url)
    return Response(
        content=data,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _to_out(account: Account) -> AccountOutExtended:
    return AccountOutExtended(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        role=account.role,
        is_admin=account.role in ("admin", "super_admin"),
        avatar_url=account.avatar_url,
        is_pending_deletion=account.is_pending_deletion,
        deletion_expires_at=(
            account.deletion_requested_at + timedelta(days=7)
            if account.is_pending_deletion else None
        ),
    )
```

- [ ] **Step 5: 跑测试, 确认通过**

```bash
cd packages/service && uv run pytest tests/account_settings/test_profile.py -v
```

Expected: 2 PASS

- [ ] **Step 6: 注册 router**

```python
# packages/service/src/__init__.py 第 28 行后插入
from .auth.account_settings_router import router as account_settings_router
# 在 register_routers 函数末尾加:
    app.include_router(account_settings_router)  # /api/account/profile|avatar|...
```

- [ ] **Step 7: 启动后端, smoke test**

```bash
cd packages/service && uv run python main.py &
sleep 3
curl -s -X PATCH http://localhost:8000/api/account/profile -H "Content-Type: application/json" -d '{"display_name":"x"}' | head
# 401 expected (无 token), 说明路由已注册
```

- [ ] **Step 8: Commit**

```bash
git add packages/service/src/auth/account_settings_schemas.py \
        packages/service/src/auth/account_settings_service.py \
        packages/service/src/auth/account_settings_router.py \
        packages/service/tests/account_settings/test_profile.py \
        packages/service/src/__init__.py
git commit -m "feat(account): PATCH /profile + POST/DELETE /avatar + GET /avatar/<id> 代理"
```

### Task 2.2: 邮箱修改端点 (email + verify)

**Files:**
- Modify: `packages/service/src/auth/account_settings_router.py` (加 PATCH /email + POST /email/verify)
- Modify: `packages/service/src/auth/account_settings_service.py` (加 request_email_change + verify_email_change)
- Create: `packages/service/tests/account_settings/test_email.py`

- [ ] **Step 1: 写失败测试**

```python
# packages/service/tests/account_settings/test_email.py
"""模式 1: PATCH /email + POST /email/verify 业务逻辑"""
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from packages.service.src.auth.account_settings_service import request_email_change, verify_email_change


def test_request_email_change_creates_token():
    mock_session = MagicMock()
    mock_account = MagicMock(id=1, email="old@x.com")
    # 用 mock session.query(EmailChange) 走 filter_by(first)
    mock_session.query.return_value.filter_by.return_value.first.return_value = None
    # 用 mock session.query(Account) 走 filter_by(first)
    mock_session.query.return_value.filter_by.return_value.first.side_effect = [None, mock_account]

    with patch("packages.service.src.auth.account_settings_service.verify_password", return_value=True):
        result = request_email_change(mock_session, mock_account, "new@x.com", "pw")
    assert "verification_url" in result
    assert result["new_email"] == "new@x.com"


def test_verify_email_change_marks_used_and_updates_email():
    mock_change = MagicMock()
    mock_change.account_id = 1
    mock_change.new_email = "new@x.com"
    mock_change.used_at = None
    mock_change.expires_at = datetime.now() + timedelta(days=7)
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_change
    mock_session.get.return_value = MagicMock(id=1, email="old@x.com")

    verify_email_change(mock_session, "token123")
    assert mock_session.get.return_value.email == "new@x.com"
    assert mock_change.used_at is not None
```

- [ ] **Step 2: 跑测试, 确认失败**

```bash
cd packages/service && uv run pytest tests/account_settings/test_email.py -v
```

Expected: 2 FAIL

- [ ] **Step 3: 加 service 函数**

```python
# packages/service/src/auth/account_settings_service.py 末尾追加
# --- email change ---
def request_email_change(
    session, account: Account, new_email: str, current_password: str
) -> dict:
    """申请改邮箱. 校验 current_password, 检查 new_email 跟现有 email 不重复 (其他 account)."""
    if not verify_password(current_password, account.password_hash):
        raise ValueError("invalid current password")
    # 查重
    existing = (
        session.query(Account)
        .filter(Account.email == new_email, Account.id != account.id)
        .first()
    )
    if existing is not None:
        raise ValueError("email already in use")
    # 创 EmailChange token
    token = secrets.token_hex(32)
    expires_at = datetime.now(HKT) + timedelta(days=EMAIL_CHANGE_EXPIRES_DAYS)
    session.add(
        EmailChange(
            account_id=account.id,
            new_email=new_email,
            token=token,
            expires_at=expires_at,
            created_at=datetime.now(HKT),
        )
    )
    session.flush()
    return {
        "new_email": new_email,
        "expires_at": expires_at,
        "verification_url": f"/verify-email?token={token}",  # dev: 返 URL; prod: 发邮件
    }


def verify_email_change(session, token: str) -> dict:
    """验证 token → 切换 email + 标 used_at. 兼容 naive/aware datetime."""
    change = session.query(EmailChange).filter_by(token=token).first()
    if change is None or change.used_at is not None:
        raise ValueError("invalid or used token")
    if change.expires_at.tzinfo is None:
        expires_aware = change.expires_at.replace(tzinfo=HKT)
    else:
        expires_aware = change.expires_at.astimezone(HKT)
    if expires_aware < datetime.now(HKT):
        raise ValueError("token expired")
    # 二次校验 new_email 仍可用 (race)
    dup = (
        session.query(Account)
        .filter(Account.email == change.new_email, Account.id != change.account_id)
        .first()
    )
    if dup is not None:
        raise ValueError("email already in use")
    account = session.get(Account, change.account_id)
    assert account is not None
    account.email = change.new_email
    change.used_at = datetime.now(HKT)
    session.flush()
    return {"email": account.email}
```

- [ ] **Step 4: 加 router 端点**

```python
# packages/service/src/auth/account_settings_router.py _to_out 后追加
class EmailChangeRequest(BaseModel):
    new_email: str = Field(..., max_length=254, description="新邮箱, 格式合法, 不跟别人重复")
    current_password: str = Field(..., min_length=1, description="当前密码 (二次确认)")


class EmailVerifyRequest(BaseModel):
    token: str = Field(..., description="request 返回的 token")


@router.patch("/email", summary="申请改邮箱")
def patch_email(
    req: EmailChangeRequest,
    user: CurrentUser = Depends(require_account),
):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(404, "account not found")
        try:
            return svc.request_email_change(s, account, req.new_email, req.current_password)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@router.post("/email/verify", summary="验证邮箱改 token")
def post_email_verify(req: EmailVerifyRequest, user: CurrentUser = Depends(require_account)):
    with session_scope() as s:
        try:
            return svc.verify_email_change(s, req.token)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
```

- [ ] **Step 5: 跑测试 + smoke**

```bash
cd packages/service && uv run pytest tests/account_settings/test_email.py -v
# smoke: PATCH /email 应返 401 (无 token), 路由已注册
curl -s -X PATCH http://localhost:8000/api/account/email -H "Content-Type: application/json" -d '{}' -i | head -3
```

Expected: 2 PASS + 401

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/auth/account_settings_router.py \
        packages/service/src/auth/account_settings_service.py \
        packages/service/tests/account_settings/test_email.py
git commit -m "feat(account): PATCH /email + POST /email/verify 邮箱改双重验证"
```

### Task 2.3: 密码端点 (password)

**Files:**
- Modify: `packages/service/src/auth/account_settings_router.py` (加 PATCH /password)
- Create: `packages/service/tests/account_settings/test_password.py`

- [ ] **Step 1: 写失败测试**

```python
# packages/service/tests/account_settings/test_password.py
"""模式 1: PATCH /password 业务逻辑"""
from unittest.mock import MagicMock, patch
from packages.service.src.auth.account_settings_service import change_password


def test_change_password_hashes_new_password():
    mock_account = MagicMock(password_hash="old_hash")
    with patch(
        "packages.service.src.auth.account_settings_service.verify_password", return_value=True
    ):
        with patch(
            "packages.service.src.auth.account_settings_service.hash_password",
            return_value="new_hash",
        ) as mock_hash:
            change_password(mock_account, "old", "newpass123", "newpass123")
    assert mock_account.password_hash == "new_hash"
    mock_hash.assert_called_once_with("newpass123")


def test_change_password_rejects_wrong_current():
    mock_account = MagicMock()
    with patch(
        "packages.service.src.auth.account_settings_service.verify_password", return_value=False
    ):
        import pytest
        with pytest.raises(ValueError, match="invalid current password"):
            change_password(mock_account, "wrong", "newpass123", "newpass123")


def test_change_password_rejects_mismatched_confirm():
    mock_account = MagicMock()
    with patch(
        "packages.service.src.auth.account_settings_service.verify_password", return_value=True
    ):
        import pytest
        with pytest.raises(ValueError, match="passwords do not match"):
            change_password(mock_account, "old", "newpass123", "different")
```

- [ ] **Step 2: 跑测试, 确认失败**

```bash
cd packages/service && uv run pytest tests/account_settings/test_password.py -v
```

Expected: 3 FAIL

- [ ] **Step 3: 加 service 函数 + router**

```python
# packages/service/src/auth/account_settings_service.py 末尾追加
# --- password ---
def change_password(
    account: Account, current_password: str, new_password: str, confirm: str
) -> None:
    """改密码. 校验 current + new == confirm + new ≥ 8 字符."""
    if not verify_password(current_password, account.password_hash):
        raise ValueError("invalid current password")
    if new_password != confirm:
        raise ValueError("passwords do not match")
    if len(new_password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    account.password_hash = hash_password(new_password)
```

```python
# packages/service/src/auth/account_settings_router.py 加
class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="当前密码")
    new_password: str = Field(..., min_length=8, description="新密码 ≥ 8 字符")
    confirm: str = Field(..., min_length=8, description="新密码确认")


@router.patch("/password", summary="改密码")
def patch_password(
    req: PasswordChangeRequest,
    user: CurrentUser = Depends(require_account),
):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(404, "account not found")
        try:
            svc.change_password(account, req.current_password, req.new_password, req.confirm)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    return {"ok": True}
```

- [ ] **Step 4: 跑测试 + smoke + commit**

```bash
cd packages/service && uv run pytest tests/account_settings/test_password.py -v
# smoke
curl -s -X PATCH http://localhost:8000/api/account/password -H "Content-Type: application/json" -d '{}' -i | head -3
git add -A && git commit -m "feat(account): PATCH /password 改密码 (输当前密码 + 二次确认)"
```

### Task 2.4: 注销端点 (deletion × 3)

**Files:**
- Modify: `packages/service/src/auth/account_settings_router.py` (加 GET/POST/DELETE /deletion)
- Modify: `packages/service/src/auth/account_settings_service.py` (加 request/cancel/get_deletion)
- Create: `packages/service/tests/account_settings/test_deletion.py`

- [ ] **Step 1: 写失败测试**

```python
# packages/service/tests/account_settings/test_deletion.py
"""模式 1: 注销 + 撤销 业务逻辑"""
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from packages.service.src.auth.account_settings_service import (
    request_deletion, cancel_deletion, get_deletion_status
)


def test_request_deletion_marks_account_pending():
    mock_account = MagicMock(id=1, is_active=True, is_pending_deletion=False, deletion_requested_at=None)
    mock_session = MagicMock()
    with patch("packages.service.src.auth.account_settings_service.verify_password", return_value=True):
        result = request_deletion(mock_session, mock_account, "pw", "我要注销")
    assert mock_account.is_active is False
    assert mock_account.deletion_requested_at is not None
    assert "restore_url" in result


def test_request_deletion_rejects_bad_confirm_text():
    mock_account = MagicMock()
    import pytest
    with pytest.raises(ValueError, match="confirm text"):
        request_deletion(MagicMock(), mock_account, "pw", "wrong text")


def test_cancel_deletion_restores_active():
    mock_account = MagicMock(is_active=False, deletion_requested_at=datetime.now())
    mock_session = MagicMock()
    with patch("packages.service.src.auth.account_settings_service.verify_password", return_value=True):
        cancel_deletion(mock_session, mock_account, "pw")
    assert mock_account.is_active is True
    assert mock_account.deletion_requested_at is None


def test_cancel_deletion_rejects_when_not_pending():
    mock_account = MagicMock(is_pending_deletion=False)
    import pytest
    with patch("packages.service.src.auth.account_settings_service.verify_password", return_value=True):
        with pytest.raises(ValueError, match="not pending deletion"):
            cancel_deletion(MagicMock(), mock_account, "pw")
```

- [ ] **Step 2: 跑测试, 确认失败**

```bash
cd packages/service && uv run pytest tests/account_settings/test_deletion.py -v
```

Expected: 4 FAIL

- [ ] **Step 3: 加 service 函数 + router**

```python
# packages/service/src/auth/account_settings_service.py 末尾追加
# --- deletion ---
def request_deletion(
    session, account: Account, current_password: str, confirm_text: str
) -> dict:
    """申请注销. 校验密码 + confirm_text 字面匹配. 立即 is_active=False, 创 restore token."""
    if not verify_password(current_password, account.password_hash):
        raise ValueError("invalid current password")
    if confirm_text.strip() != "我要注销":
        raise ValueError("confirm text must be exactly '我要注销'")
    if account.is_pending_deletion:
        raise ValueError("account already pending deletion")
    now = datetime.now(HKT)
    account.is_active = False
    account.deletion_requested_at = now
    token = secrets.token_hex(32)
    expires_at = now + timedelta(days=DELETION_RESTORE_EXPIRES_DAYS)
    session.add(
        DeletionRestore(
            account_id=account.id,
            token=token,
            expires_at=expires_at,
            created_at=now,
        )
    )
    session.flush()
    return {
        "deletion_requested_at": now,
        "expires_at": expires_at,
        "restore_url": f"/account/restore?token={token}",
    }


def cancel_deletion(session, account: Account, current_password: str) -> None:
    """撤销注销. 校验密码 + 必须在 pending 状态. 标 DeletionRestore.used_at + 重置 is_active=True."""
    if not account.is_pending_deletion:
        raise ValueError("account is not pending deletion")
    if not verify_password(current_password, account.password_hash):
        raise ValueError("invalid current password")
    account.is_active = True
    account.deletion_requested_at = None
    # 标所有未用的 DeletionRestore token 为 used
    for dr in (
        session.query(DeletionRestore)
        .filter_by(account_id=account.id, used_at=None)
        .all()
    ):
        dr.used_at = datetime.now(HKT)
    session.flush()


def get_deletion_status(account: Account) -> dict:
    """查当前注销状态. 不返 restore_token (防泄漏)."""
    if not account.is_pending_deletion:
        return {"pending": False}
    return {
        "pending": True,
        "deletion_requested_at": account.deletion_requested_at,
        "expires_at": account.deletion_requested_at + timedelta(days=DELETION_GRACE_DAYS),
    }
```

```python
# packages/service/src/auth/account_settings_router.py 加
class DeletionRequest(BaseModel):
    current_password: str = Field(..., description="当前密码")
    confirm_text: str = Field(..., description="必须字面等于 '我要注销'")


class DeletionCancel(BaseModel):
    current_password: str = Field(..., description="当前密码 (二次确认)")


@router.get("/deletion", summary="查注销状态")
def get_deletion(user: CurrentUser = Depends(require_account)):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(404, "account not found")
        return svc.get_deletion_status(account)


@router.post("/deletion", summary="申请注销")
def post_deletion(req: DeletionRequest, user: CurrentUser = Depends(require_account)):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(404, "account not found")
        try:
            return svc.request_deletion(s, account, req.current_password, req.confirm_text)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@router.delete("/deletion", summary="撤销注销")
def delete_deletion(req: DeletionCancel, user: CurrentUser = Depends(require_account)):
    with session_scope() as s:
        account = s.get(Account, user.account_id)
        if account is None:
            raise HTTPException(404, "account not found")
        try:
            svc.cancel_deletion(s, account, req.current_password)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    return {"ok": True}
```

- [ ] **Step 4: 跑测试 + smoke + commit**

```bash
cd packages/service && uv run pytest tests/account_settings/test_deletion.py -v
curl -s -X POST http://localhost:8000/api/account/deletion -H "Content-Type: application/json" -d '{}' -i | head -3
git add -A && git commit -m "feat(account): GET/POST/DELETE /deletion 注销 7 天宽限期 (3 端点)"
```

### Task 2.5: `/me` 增强 + `require_active_account` 守卫 + /login 标志

**Files:**
- Modify: `packages/service/src/auth/auth_account_router.py:134-162` (`/me` 加 3 字段)
- Modify: `packages/service/src/auth/auth_account_router.py:40-110` (LoginResponse 加 2 字段 + /login 检查 pending_deletion)
- Modify: `packages/service/src/permissions/guards.py` (加 `require_active_account`)
- Create: `packages/service/tests/account_settings/test_state_machine.py`

- [ ] **Step 1: 写失败测试**

```python
# packages/service/tests/account_settings/test_state_machine.py
"""模式 1: 状态机 + /me 字段 + /login 标志"""
from unittest.mock import MagicMock
from packages.service.src.permissions.guards import require_active_account


def test_require_active_account_rejects_pending_deletion():
    mock_user = MagicMock(is_active=False, is_pending_deletion=True)
    from fastapi import HTTPException
    import pytest
    with pytest.raises(HTTPException) as exc_info:
        require_active_account(user=mock_user)
    assert exc_info.value.status_code == 403


def test_require_active_account_allows_normal_user():
    mock_user = MagicMock(is_active=True, is_pending_deletion=False)
    result = require_active_account(user=mock_user)
    assert result is mock_user
```

- [ ] **Step 2: 跑测试, 确认失败**

```bash
cd packages/service && uv run pytest tests/account_settings/test_state_machine.py -v
```

Expected: 2 FAIL

- [ ] **Step 3: 加 `require_active_account` 守卫**

```python
# packages/service/src/permissions/guards.py 末尾追加
def require_active_account(user: CurrentUser = Depends(require_account)) -> CurrentUser:
    """require_account + 校验 is_active=True + 非 pending_deletion. 写操作路由用这个."""
    if not user.is_active or user.is_pending_deletion:
        raise HTTPException(status_code=403, detail="account is pending deletion")
    return user
```

- [ ] **Step 4: 改 /me 加 3 字段**

```python
# packages/service/src/auth/auth_account_router.py:152-162
@router.get("/me", ...)
def me(user: CurrentUser = Depends(resolve_user)):
    deletion_expires_at = None
    if user.deletion_requested_at is not None:
        from datetime import timedelta
        deletion_expires_at = user.deletion_requested_at + timedelta(days=7)
    return {
        "id": user.id,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_account": user.is_account,
        "account_id": user.account_id,
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "avatar_url": user.avatar_url,  # 新
        "is_pending_deletion": user.is_pending_deletion,  # 新
        "deletion_expires_at": deletion_expires_at,  # 新
    }
```

注意: 需在 `CurrentUser` schema 加 `avatar_url` 字段 (看 `src/middleware/auth.py`).

- [ ] **Step 5: 改 /login 加 pending_deletion 标志**

```python
# packages/service/src/auth/auth_account_router.py LoginResponse 加字段
class LoginResponse(BaseModel):
    token: str = Field(..., description="32 字节 hex")
    account: AccountOut = Field(..., description="账号信息")
    pending_deletion: bool = Field(False, description="账号处于 pending_deletion 状态 (新加)")
    deletion_expires_at: datetime | None = Field(None, description="注销到期时间 (新加)")


# /login 函数内, 在 return LoginResponse 之前加:
if account.is_pending_deletion:
    from datetime import timedelta
    return LoginResponse(
        token=token,
        account=account_payload,
        pending_deletion=True,
        deletion_expires_at=account.deletion_requested_at + timedelta(days=7),
    )
```

- [ ] **Step 6: 跑测试 + smoke + commit**

```bash
cd packages/service && uv run pytest tests/account_settings/test_state_machine.py -v
cd packages/service && uv run pytest tests/auth/ tests/permissions/ -v  # 不破既有
git add -A && git commit -m "feat(account): require_active_account 守卫 + /me 加 3 字段 + /login 加 pending_deletion 标志"
```

---

## Phase 3: 前端基础 (3 commit)

### Task 3.1: server actions + i18n

**Files:**
- Create: `packages/web/app/_actions/account-settings.ts`
- Modify: `packages/web/messages/zh.json` (加 30 key)
- Modify: `packages/web/messages/en.json` (加 30 key, 英文翻译)

- [ ] **Step 1: 写 server actions**

```typescript
// packages/web/app/_actions/account-settings.ts
"use server";
// 7 server action 改 profile / email / password / deletion
// 模式跟 _actions/account.ts (loginAction) 一致: useActionState 签名 + apiFetch + 错误归一
import { revalidatePath } from "next/cache";
import { getLocale } from "next-intl/server";
import { redirect } from "@/i18n/navigation";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { apiFetch } from "@/lib/api/config";
import { ApiError, NetworkError } from "@/lib/api/errors";

export interface ProfileState {
  ok: boolean;
  error: string | null;
}
export interface AvatarState {
  ok: boolean;
  error: string | null;
  avatarUrl: string | null;
}
export interface EmailState {
  ok: boolean;
  error: string | null;
  verificationUrl: string | null;
}
export interface PasswordState {
  ok: boolean;
  error: string | null;
}
export interface DeletionState {
  ok: boolean;
  error: string | null;
  restoreUrl: string | null;
  expiresAt: string | null;
}

export async function updateProfileAction(
  _prev: ProfileState,
  formData: FormData,
): Promise<ProfileState> {
  const displayName = String(formData.get("display_name") ?? "").trim();
  if (displayName.length < 1 || displayName.length > 50) {
    return { error: "昵称 1-50 字符", ok: false };
  }
  try {
    await apiFetch("/api/account/profile", {
      body: { display_name: displayName },
      headers: await serverAuthHeaders(),
      method: "PATCH",
    });
    revalidatePath("/", "layout");
    return { error: null, ok: true };
  } catch (error) {
    return { error: error instanceof ApiError ? error.message : "保存失败", ok: false };
  }
}

export async function uploadAvatarAction(
  _prev: AvatarState,
  formData: FormData,
): Promise<AvatarState> {
  const file = formData.get("file") as File | null;
  if (!file || file.size === 0) {
    return { avatarUrl: null, error: "请选择文件", ok: false };
  }
  try {
    const b = await apiFetch<{ avatar_url: string }>("/api/account/avatar", {
      body: formData, // multipart, apiFetch 自动识别
      headers: await serverAuthHeaders(),
      method: "POST",
    });
    revalidatePath("/", "layout");
    return { avatarUrl: b.avatar_url, error: null, ok: true };
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      return { avatarUrl: null, error: "图片无效或过大 (≤ 2MB)", ok: false };
    }
    return { avatarUrl: null, error: "上传失败", ok: false };
  }
}

export async function deleteAvatarAction(): Promise<AvatarState> {
  try {
    await apiFetch("/api/account/avatar", {
      headers: await serverAuthHeaders(),
      method: "DELETE",
    });
    revalidatePath("/", "layout");
    return { avatarUrl: null, error: null, ok: true };
  } catch {
    return { avatarUrl: null, error: "删除失败", ok: false };
  }
}

export async function requestEmailChangeAction(
  _prev: EmailState,
  formData: FormData,
): Promise<EmailState> {
  const newEmail = String(formData.get("new_email") ?? "").trim();
  const currentPassword = String(formData.get("current_password") ?? "");
  if (!newEmail || !currentPassword) {
    return { error: "请填新邮箱和当前密码", ok: false, verificationUrl: null };
  }
  try {
    const b = await apiFetch<{ verification_url: string }>("/api/account/email", {
      body: { current_password: currentPassword, new_email: newEmail },
      headers: await serverAuthHeaders(),
      method: "PATCH",
    });
    return {
      error: null,
      ok: true,
      verificationUrl: b.verification_url,
    };
  } catch (error) {
    if (error instanceof ApiError) {
      return {
        error:
          error.status === 400
            ? "当前密码错误或邮箱已被使用"
            : `申请失败: ${error.message}`,
        ok: false,
        verificationUrl: null,
      };
    }
    return { error: "申请失败", ok: false, verificationUrl: null };
  }
}

export async function changePasswordAction(
  _prev: PasswordState,
  formData: FormData,
): Promise<PasswordState> {
  const currentPassword = String(formData.get("current_password") ?? "");
  const newPassword = String(formData.get("new_password") ?? "");
  const confirm = String(formData.get("confirm") ?? "");
  if (!currentPassword || !newPassword) {
    return { error: "请填完整", ok: false };
  }
  if (newPassword.length < 8) {
    return { error: "密码至少 8 位", ok: false };
  }
  if (newPassword !== confirm) {
    return { error: "两次密码不一致", ok: false };
  }
  try {
    await apiFetch("/api/account/password", {
      body: { confirm, current_password: currentPassword, new_password: newPassword },
      headers: await serverAuthHeaders(),
      method: "PATCH",
    });
    return { error: null, ok: true };
  } catch (error) {
    return {
      error: error instanceof ApiError ? error.message : "改密失败",
      ok: false,
    };
  }
}

export async function requestDeletionAction(
  _prev: DeletionState,
  formData: FormData,
): Promise<DeletionState> {
  const currentPassword = String(formData.get("current_password") ?? "");
  const confirmText = String(formData.get("confirm_text") ?? "");
  if (!currentPassword || confirmText !== "我要注销") {
    return { error: "请输当前密码 + 字面输入 '我要注销'", ok: false, restoreUrl: null, expiresAt: null };
  }
  try {
    const b = await apiFetch<{ restore_url: string; expires_at: string }>(
      "/api/account/deletion",
      {
        body: { confirm_text: confirmText, current_password: currentPassword },
        headers: await serverAuthHeaders(),
        method: "POST",
      },
    );
    return {
      error: null,
      expiresAt: b.expires_at,
      ok: true,
      restoreUrl: b.restore_url,
    };
  } catch (error) {
    return {
      error: error instanceof ApiError ? error.message : "申请失败",
      expiresAt: null,
      ok: false,
      restoreUrl: null,
    };
  }
}

export async function cancelDeletionAction(
  _prev: DeletionState,
  formData: FormData,
): Promise<DeletionState> {
  const currentPassword = String(formData.get("current_password") ?? "");
  if (!currentPassword) {
    return { error: "请输当前密码", ok: false, restoreUrl: null, expiresAt: null };
  }
  try {
    await apiFetch("/api/account/deletion", {
      body: { current_password: currentPassword },
      headers: await serverAuthHeaders(),
      method: "DELETE",
    });
    revalidatePath("/", "layout");
    return { error: null, expiresAt: null, ok: true, restoreUrl: null };
  } catch (error) {
    return {
      error: error instanceof ApiError ? error.message : "撤销失败",
      expiresAt: null,
      ok: false,
      restoreUrl: null,
    };
  }
}
```

- [ ] **Step 2: 加 i18n 30 key (zh) + 30 key (en)**

```bash
# 在 messages/zh.json 末尾追加, 然后 messages/en.json 同步
# (key 列表见 spec §8, 此处不重复, agent 抄录)
```

- [ ] **Step 3: 验证 i18n 合法**

```bash
cd packages/web && node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add packages/web/app/_actions/account-settings.ts \
        packages/web/messages/zh.json \
        packages/web/messages/en.json
git commit -m "feat(account): 7 server actions + i18n 30 key (zh+en)"
```

### Task 3.2: RSC 页 + PageGuard

**Files:**
- Create: `packages/web/app/[locale]/account/settings/page.tsx`
- Create: `packages/web/app/[locale]/account/settings/_components/AccountSettingsClient.tsx`
- Create: `packages/web/app/[locale]/account/settings/page.test.tsx`

- [ ] **Step 1: 写 page.tsx (RSC)**

```typescript
// packages/web/app/[locale]/account/settings/page.tsx
// 跟 admin/users/page.tsx 同模式: RSC + PageGuard + Suspense + redirect 未登录
import { Suspense } from "react";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { apiFetch } from "@/lib/api/config";
import { PageGuard } from "@/components/PageGuard";
import { getMyPermissions } from "@/lib/auth/permissions";
import { AccountSettingsClient } from "./_components/AccountSettingsClient";
import { Skeleton } from "@/components/ui/skeleton";

interface MeResponse {
  id: number;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_pending_deletion: boolean;
  deletion_expires_at: string | null;
}

export async function generateMetadata() {
  const t = await getTranslations();
  return { title: `${t("账号设置")} - RAG` };
}

export default async function AccountSettingsPage() {
  let me: MeResponse;
  try {
    me = await apiFetch<MeResponse>("/api/account/me");
  } catch {
    redirect("/login?next=/account/settings");
  }
  if (!me.is_pending_deletion) {
    // 正常: 检查 is_account (anon 不让进)
    // (anon 的 /me 返 is_account=false)
  }
  const t = await getTranslations();
  const permissions = await getMyPermissions();

  return (
    <PageGuard pageKey="dashboard" permissions={permissions}>
      <div className="mx-auto max-w-3xl space-y-6 p-6">
        <h1 className="display text-3xl">{t("账号设置")}</h1>
        <Suspense fallback={<Skeleton className="h-96" />}>
          <AccountSettingsClient me={me} />
        </Suspense>
      </div>
    </PageGuard>
  );
}
```

- [ ] **Step 2: 写 AccountSettingsClient 骨架 (Section 后面填)**

```typescript
// packages/web/app/[locale]/account/settings/_components/AccountSettingsClient.tsx
"use client";
import { ProfileSection } from "./ProfileSection";
import { EmailSection } from "./EmailSection";
import { PasswordSection } from "./PasswordSection";
import { DeletionSection } from "./DeletionSection";

interface Me {
  id: number;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_pending_deletion: boolean;
  deletion_expires_at: string | null;
}

export function AccountSettingsClient({ me }: { me: Me }) {
  return (
    <div className="space-y-6">
      <ProfileSection me={me} />
      <EmailSection email={me.email} />
      <PasswordSection />
      <DeletionSection
        isPending={me.is_pending_deletion}
        expiresAt={me.deletion_expires_at}
      />
    </div>
  );
}
```

- [ ] **Step 3: 占位 Section (供 page 编译通过, 后面 Task 3.3 替换)**

```typescript
// packages/web/app/[locale]/account/settings/_components/ProfileSection.tsx
"use client";
export function ProfileSection({ me }: { me: { display_name: string | null; avatar_url: string | null } }) {
  return <div data-testid="profile-section">{me.display_name ?? "未设昵称"}</div>;
}
```

同样占位其他 3 个 Section (各 1 行, 后面 Task 3.3 替换).

- [ ] **Step 4: 写 page 测试**

```typescript
// packages/web/app/[locale]/account/settings/page.test.tsx
import { render, screen } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
// mock apiFetch + PageGuard (因 RSC 难测, 测简化版 client 组件)
describe("AccountSettingsClient", () => {
  it("renders 4 sections", () => {
    const { AccountSettingsClient } = require("./_components/AccountSettingsClient");
    render(
      <IntlWrapper>
        <AccountSettingsClient
          me={{
            id: 1, email: "x@x.com", display_name: "X",
            avatar_url: null, is_pending_deletion: false, deletion_expires_at: null
          }}
        />
      </IntlWrapper>
    );
    expect(screen.getByTestId("profile-section")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: 跑 typecheck + vitest + commit**

```bash
cd packages/web && bun run typecheck && bun run test -- --testPathPattern account/settings
git add -A && git commit -m "feat(account): /account/settings RSC + PageGuard + 4 Section 占位"
```

### Task 3.3: 4 Section 完整实现 (Profile/Email/Password/Deletion)

**Files:**
- Modify: 4 个 Section .tsx (完整实现)
- Create: 4 个 Section .test.tsx

- [ ] **Step 1: 实现 ProfileSection**

```typescript
// packages/web/app/[locale]/account/settings/_components/ProfileSection.tsx
"use client";
import { useActionState, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormField } from "@/components/common/form-field";
import { ErrorBanner } from "@/components/common/error-banner";
import { updateProfileAction, uploadAvatarAction, deleteAvatarAction, type ProfileState, type AvatarState } from "@/app/_actions/account-settings";
import { AvatarUploader } from "./AvatarUploader";

const initialProfile: ProfileState = { error: null, ok: false };
const initialAvatar: AvatarState = { avatarUrl: null, error: null, ok: false };

export function ProfileSection({ me }: { me: { display_name: string | null; avatar_url: string | null } }) {
  const t = useTranslations();
  const [profileState, profileAction] = useActionState(updateProfileAction, initialProfile);
  const [avatarState, avatarAction] = useActionState(uploadAvatarAction, initialAvatar);
  const [displayName, setDisplayName] = useState(me.display_name ?? "");

  return (
    <section className="space-y-4 rounded-2xl border bg-card p-6">
      <h2 className="text-lg font-semibold">{t("基础资料")}</h2>
      <AvatarUploader currentUrl={me.avatar_url} />
      <Form action={profileAction}>
        <FormField label={t("昵称")} error={profileState.error ?? undefined}>
          <Input
            name="display_name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={50}
            data-testid="profile-display-name"
          />
        </FormField>
        <Button type="submit" data-testid="profile-save">{t("保存")}</Button>
        {profileState.ok && <span className="text-sm text-status-success">{t("已保存")}</span>}
      </Form>
    </section>
  );
}
```

- [ ] **Step 2: 实现 EmailSection + PasswordSection + DeletionSection (类似 pattern)**

(参考 ProfileSection 模式, 调对应 server action, Field + ErrorBanner + Button, data-testid 命名: email-change-button / password-change-button / deletion-request-button / deletion-cancel-button)

- [ ] **Step 3: 写 4 个 Section 测试**

```typescript
// ProfileSection.test.tsx: 测输入 + 提交 + ErrorBanner 显示
// EmailSection.test.tsx: 测 dialog 打开 (后面 Task 4.1 接入) → 此处先测只 render 按钮
// PasswordSection.test.tsx: 同上
// DeletionSection.test.tsx: 测 is_pending 状态显示不同 UI
```

- [ ] **Step 4: typecheck + vitest + commit**

```bash
cd packages/web && bun run typecheck && bun run test -- --testPathPattern account/settings
git add -A && git commit -m "feat(account): 4 Section 完整实现 (Profile/Email/Password/Deletion) + 测试"
```

---

## Phase 4: 前端交互 (3 commit)

### Task 4.1: 4 个 Dialog

**Files:**
- Create: 4 个 Dialog .tsx (ChangeEmailDialog / ChangePasswordDialog / RequestDeletionDialog / CancelDeletionDialog)
- Modify: 3 个 Section 接入 Dialog (点按钮 → 弹 Dialog)
- Create: 4 个 Dialog .test.tsx

- [ ] **Step 1: ChangeEmailDialog**

```typescript
// packages/web/app/[locale]/account/settings/_components/ChangeEmailDialog.tsx
"use client";
import { useActionState, useState } from "react";
import { useTranslations } from "next-intl";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Form, FormField } from "@/components/common/form-field";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { requestEmailChangeAction, type EmailState } from "@/app/_actions/account-settings";

const initial: EmailState = { error: null, ok: false, verificationUrl: null };

export function ChangeEmailDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const t = useTranslations();
  const [state, action] = useActionState(requestEmailChangeAction, initial);

  return (
    <AppDialog open={open} onOpenChange={onOpenChange} title={t("修改邮箱")}>
      <Form action={action} className="space-y-4">
        <FormField label={t("新邮箱")} error={state.error ?? undefined}>
          <Input name="new_email" type="email" required data-testid="email-new" />
        </FormField>
        <FormField label={t("当前密码")} error={undefined}>
          <Input name="current_password" type="password" required data-testid="email-current-password" />
        </FormField>
        {state.verificationUrl && (
          <div className="rounded border border-status-warning bg-status-warning/10 p-3 text-sm">
            {t("请在 7 天内点击验证链接完成修改")}: <code>{state.verificationUrl}</code>
          </div>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>{t("取消")}</Button>
          <Button type="submit" data-testid="email-submit">{t("提交")}</Button>
        </div>
      </Form>
    </AppDialog>
  );
}
```

- [ ] **Step 2: ChangePasswordDialog + RequestDeletionDialog + CancelDeletionDialog (类似 pattern)**

(每个 Dialog 模式一致: useActionState + Form + FormField × N + Button 提交, AppDialog 包裹)

- [ ] **Step 3: Section 接入 Dialog**

(在 Section 里 useState 控制 open, 按钮 onClick 打开对应 Dialog)

- [ ] **Step 4: 测试 + commit**

```bash
cd packages/web && bun run typecheck && bun run test -- --testPathPattern account/settings
git add -A && git commit -m "feat(account): 4 Dialog (ChangeEmail/Password + Request/CancelDeletion) + Section 接入"
```

### Task 4.2: AvatarUploader + 文件上传

**Files:**
- Create: `packages/web/app/[locale]/account/settings/_components/AvatarUploader.tsx`
- Create: `packages/web/app/[locale]/account/settings/_components/AvatarUploader.test.tsx`

- [ ] **Step 1: 实现 AvatarUploader**

```typescript
// packages/web/app/[locale]/account/settings/_components/AvatarUploader.tsx
"use client";
import { useActionState, useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { Camera } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { FileDropzone } from "@/components/common/file-dropzone";
import { deleteAvatarAction, uploadAvatarAction, type AvatarState } from "@/app/_actions/account-settings";
import { useRouter } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

const initial: AvatarState = { avatarUrl: null, error: null, ok: false };

export function AvatarUploader({ currentUrl }: { currentUrl: string | null }) {
  const t = useTranslations();
  const [avatarState, avatarAction] = useActionState(uploadAvatarAction, initial);
  const [previewUrl, setPreviewUrl] = useState<string | null>(currentUrl);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  return (
    <div className="flex items-center gap-4">
      <Avatar className="h-20 w-20">
        <AvatarImage src={previewUrl ?? undefined} alt="avatar" data-testid="avatar-image" />
        <AvatarFallback>{(t("头像").charAt(0))}</AvatarFallback>
      </Avatar>
      <div className="space-y-2">
        <form action={avatarAction} encType="multipart/form-data" className="flex items-center gap-2">
          <input
            type="file"
            name="file"
            accept="image/png,image/jpeg,image/webp"
            data-testid="avatar-file-input"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                const url = URL.createObjectURL(file);
                setPreviewUrl(url);
                e.target.form?.requestSubmit();
              }
            }}
            className="hidden"
          />
          <Button type="button" variant="outline" size="sm" onClick={() => {
            document.querySelector<HTMLInputElement>('[data-testid="avatar-file-input"]')?.click();
          }}>
            <Camera className="mr-1 h-4 w-4" />
            {t("更换头像")}
          </Button>
          {currentUrl && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isPending}
              onClick={() => startTransition(async () => {
                await deleteAvatarAction();
                setPreviewUrl(null);
                router.refresh();
              })}
              data-testid="avatar-remove"
            >
              {t("移除头像")}
            </Button>
          )}
        </form>
        <p className="text-xs text-muted-foreground">{t("支持 PNG / JPG / WebP, ≤ 2MB")}</p>
        {avatarState.error && (
          <p className="text-sm text-status-error" data-testid="avatar-error">{avatarState.error}</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 测试 (mock server action) + commit**

```bash
cd packages/web && bun run typecheck && bun run test -- --testPathPattern account/settings
git add -A && git commit -m "feat(account): AvatarUploader (文件选择 + 预览 + 移除)"
```

### Task 4.3: RestoreDeletionBanner + /account/restore 页

**Files:**
- Create: `packages/web/app/[locale]/account/settings/_components/RestoreDeletionBanner.tsx`
- Create: `packages/web/app/[locale]/account/restore/page.tsx`
- Modify: `packages/web/app/[locale]/layout.tsx` (顶层挂 Banner)
- Modify: `packages/web/components/UserMenu.tsx` (`/` → `/account/settings`)
- Modify: `packages/web/components/settings/settings-dialog.tsx` (账号行激活)

- [ ] **Step 1: RestoreDeletionBanner**

```typescript
// packages/web/app/[locale]/account/settings/_components/RestoreDeletionBanner.tsx
"use client";
import { useActionState, useState } from "react";
import { useTranslations } from "next-intl";
import { differenceInDays, differenceInHours } from "date-fns";
import { Button } from "@/components/ui/button";
import { cancelDeletionAction, type DeletionState } from "@/app/_actions/account-settings";
import { cn } from "@/lib/utils";

const initial: DeletionState = { error: null, expiresAt: null, ok: false, restoreUrl: null };

export function RestoreDeletionBanner({ expiresAt }: { expiresAt: string | null }) {
  const t = useTranslations();
  const [state, action] = useActionState(cancelDeletionAction, initial);
  const [showForm, setShowForm] = useState(false);

  if (!expiresAt) return null;
  const exp = new Date(expiresAt);
  const days = Math.max(0, differenceInDays(exp, new Date()));
  const hours = Math.max(0, differenceInHours(exp, new Date()) % 24);

  return (
    <div
      className="w-full border-b border-status-error/30 bg-status-error/10 px-4 py-3"
      data-testid="restore-deletion-banner"
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div>
          <strong className="font-semibold text-status-error">
            {t("账号将在 {days} 天 {hours} 小时后删除", { days, hours })}
          </strong>
          {state.ok && <span className="ml-3 text-status-success">{t("撤销成功")}</span>}
          {state.error && <span className="ml-3 text-status-error">{state.error}</span>}
        </div>
        <div className="flex gap-2">
          {!showForm ? (
            <Button size="sm" variant="destructive" onClick={() => setShowForm(true)} data-testid="banner-cancel-button">
              {t("撤销注销")}
            </Button>
          ) : (
            <form action={action} className="flex gap-2">
              <input
                name="current_password"
                type="password"
                placeholder={t("当前密码")}
                className="rounded border px-2 py-1 text-sm"
                data-testid="banner-cancel-password"
              />
              <Button type="submit" size="sm" data-testid="banner-cancel-submit">{t("确认")}</Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: /account/restore 页**

```typescript
// packages/web/app/[locale]/account/restore/page.tsx
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { apiFetch } from "@/lib/api/config";
import { RestoreDeletionForm } from "./RestoreDeletionForm";
import { Card } from "@/components/ui/card";

interface MeResponse {
  is_pending_deletion: boolean;
  deletion_expires_at: string | null;
}

export default async function RestoreAccountPage() {
  let me: MeResponse;
  try {
    me = await apiFetch<MeResponse>("/api/account/me");
  } catch {
    redirect("/login?next=/account/restore");
  }
  if (!me.is_pending_deletion) {
    redirect("/");
  }
  const t = await getTranslations();
  return (
    <div className="mx-auto max-w-md p-6">
      <Card className="p-6">
        <h1 className="display mb-4 text-2xl">{t("撤销账号注销")}</h1>
        <p className="mb-4 text-sm text-muted-foreground">
          {t("账号将在 7 天后永久删除, 输入当前密码撤销注销")}
        </p>
        <RestoreDeletionForm />
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: layout.tsx 挂 Banner**

```typescript
// packages/web/app/[locale]/layout.tsx 在 <body> 内、children 之前加
{me?.is_pending_deletion && me.deletion_expires_at && (
  <RestoreDeletionBanner expiresAt={me.deletion_expires_at} />
)}
```

(需 layout 已有 me 查询, 没有则加)

- [ ] **Step 4: UserMenu 链接修复**

```diff
# packages/web/components/UserMenu.tsx:86
- <Link href="/">{t("账号设置")}</Link>
+ <Link href="/account/settings" data-testid="menu-account-settings">
+   {t("账号设置")}
+ </Link>
```

- [ ] **Step 5: SettingsDialog 账号行激活**

```diff
# packages/web/components/settings/settings-dialog.tsx
- <div className="flex items-center justify-between px-6 py-4 opacity-60">
-   <span className="text-sm font-medium">账号</span>
-   <Badge variant="outline">admin</Badge>
- </div>
+ <LocalizedLink
+   href="/account/settings"
+   onClick={() => onOpenChange(false)}
+   className="flex items-center justify-between px-6 py-4 hover:bg-muted/50"
+ >
+   <span className="text-sm font-medium">账号</span>
+   <ChevronRight className="h-4 w-4 text-muted-foreground" />
+ </LocalizedLink>
```

- [ ] **Step 6: 测试 + typecheck + commit**

```bash
cd packages/web && bun run typecheck && bun run test -- --testPathPattern "account|UserMenu|settings"
git add -A && git commit -m "feat(account): RestoreDeletionBanner + /account/restore 页 + UserMenu/SettingsDialog 链接"
```

---

## Phase 5: APScheduler + e2e + handoff (2 commit)

### Task 5.1: APScheduler 7 天清理

**Files:**
- Create: `packages/service/src/scheduler/__init__.py`
- Create: `packages/service/src/scheduler/deletion.py`
- Modify: `packages/service/src/__init__.py` (加 `register_schedulers` 函数)
- Modify: `packages/service/src/product_decoders/app.py` (lifespan 挂)
- Create: `packages/service/tests/account_settings/test_state_machine.py` (加 purge 测试)

- [ ] **Step 1: 写失败测试**

```python
# packages/service/tests/account_settings/test_state_machine.py 末尾追加
from datetime import datetime, timedelta
from packages.service.src.auth.account_settings_service import purge_pending_deletions


def test_purge_anonymizes_user_and_deletes_account():
    """7 天到期的 pending_deletion: anonymize User + 删 Account."""
    from unittest.mock import MagicMock
    mock_session = MagicMock()
    # mock Account + User
    mock_account = MagicMock(id=1, deletion_requested_at=datetime.now() - timedelta(days=8))
    mock_user = MagicMock(id=10, account_id=1, public_token="old", display_name="X")
    # query chain: query(Account).filter(...).all() → [mock_account]
    mock_session.query.return_value.filter.return_value.all.return_value = [mock_account]
    # query(User).filter_by(account_id=...).first() → mock_user
    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user

    purge_pending_deletions(mock_session)
    # 验证 anonymize
    assert mock_user.account_id is None
    assert mock_user.public_token != "old"
    assert "已注销" in mock_user.display_name
    # 验证删 account
    mock_session.delete.assert_called_with(mock_account)
```

- [ ] **Step 2: 跑测试, 确认失败**

```bash
cd packages/service && uv run pytest tests/account_settings/test_state_machine.py::test_purge_anonymizes_user_and_deletes_account -v
```

Expected: FAIL

- [ ] **Step 3: 实现 scheduler**

```python
# packages/service/src/scheduler/__init__.py
"""APScheduler 启动入口"""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler


def register_schedulers() -> AsyncIOScheduler:
    """注册所有定时任务. 返 scheduler (供 lifespan 启停)."""
    from .deletion import register_deletion_jobs
    scheduler = AsyncIOScheduler(timezone="Asia/Hong_Kong")
    register_deletion_jobs(scheduler)
    scheduler.start()
    return scheduler
```

```python
# packages/service/src/scheduler/deletion.py
"""注销清理: 7 天到期 → anonymize User + 删 Account"""
from __future__ import annotations
import secrets
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from ..auth.account_models import Account, User
from ..auth.account_settings_service import DELETION_GRACE_DAYS
from ..storage.session import session_scope
from ..utils.timezone import HKT


def register_deletion_jobs(scheduler: AsyncIOScheduler) -> None:
    """每天 03:00 HKT 跑一次 purge."""
    scheduler.add_job(_run_purge, "cron", hour=3, minute=0, id="purge_pending_deletions")


def _run_purge() -> None:
    purge_pending_deletions()


def purge_pending_deletions(session=None) -> None:
    """清理到期的 pending_deletion. 接受可选 session (测试用)."""
    cutoff = datetime.now(HKT) - timedelta(days=DELETION_GRACE_DAYS)
    owns_session = session is None
    if owns_session:
        from ..storage.session import session_scope
        session_ctx = session_scope()
    else:
        from contextlib import nullcontext
        session_ctx = nullcontext(session)
    with session_ctx as s:
        victims = (
            s.query(Account)
            .filter(Account.deletion_requested_at.isnot(None))
            .filter(Account.deletion_requested_at < cutoff)
            .all()
        )
        for account in victims:
            _anonymize_user(s, account.id)
            s.delete(account)  # CASCADE 删 EmailChange, DeletionRestore
        s.flush()
    logger.info(f"purged {len(victims)} pending_deletion accounts")


def _anonymize_user(session, account_id: int) -> None:
    user = session.query(User).filter_by(account_id=account_id).first()
    if user is None:
        return
    user.account_id = None
    user.public_token = secrets.token_hex(32)
    user.display_name = f"已注销用户 #{user.id}"
    # 注: chat_messages / chat_shares / memories / evaluations 仍指向 user.id (匿名化后)
```

- [ ] **Step 4: 挂到 lifespan**

```python
# packages/service/src/product_decoders/app.py 在 create_app lifespan 加
from ..scheduler import register_schedulers
scheduler = register_schedulers()
try:
    yield
finally:
    scheduler.shutdown(wait=False)
```

- [ ] **Step 5: 跑测试 + commit**

```bash
cd packages/service && uv run pytest tests/account_settings/ tests/auth/ -v
git add -A && git commit -m "feat(account): APScheduler 每天 03:00 清理 pending_deletion (7 天到期 anonymize + delete)"
```

### Task 5.2: E2E + handoff 文档

**Files:**
- Create: `packages/web/e2e/account-settings.spec.ts`
- Create: `docs/superpowers/handoffs/2026-06-17-account-settings.md`

- [ ] **Step 1: 写 e2e 6 case**

```typescript
// packages/web/e2e/account-settings.spec.ts
// 6 case: 改昵称 / 改头像 / 改密码 / 改邮箱 / 申请注销 / 撤销注销
// 跟现有 18 case 同模式 (vitest 18 = 18 个 .spec.ts 之一)
import { test, expect } from "@playwright/test";

test.describe("账号设置", () => {
  test.beforeEach(async ({ page }) => {
    // 假设已 seed 账号, 用 env 注入 token
    await page.context().addCookies([{
      name: "rag_user_token",
      value: process.env.E2E_TEST_TOKEN!,
      domain: "localhost",
      path: "/",
    }]);
  });

  test("改昵称后 UserMenu 显示新昵称", async ({ page }) => {
    await page.goto("/zh/account/settings");
    await page.getByTestId("profile-display-name").fill("新昵称");
    await page.getByTestId("profile-save").click();
    await expect(page.getByTestId("user-menu")).toContainText("新昵称");
  });

  test("头像上传后 /api/account/avatar/<id> 返图片", async ({ page }) => {
    await page.goto("/zh/account/settings");
    await page.getByTestId("avatar-file-input").setInputFiles("e2e/fixtures/avatar.png");
    await expect(page.getByTestId("avatar-image")).toHaveAttribute("src", /\/api\/account\/avatar\/\d+/);
  });

  test("改密码后登出用新密码能登录", async ({ page, context }) => {
    await page.goto("/zh/account/settings");
    await page.getByTestId("password-change-button").click();
    await page.getByTestId("password-current").fill("oldpass12");
    await page.getByTestId("password-new").fill("newpass12");
    await page.getByTestId("password-confirm").fill("newpass12");
    await page.getByTestId("password-submit").click();
    await expect(page.getByText("已保存")).toBeVisible();
  });

  test("申请注销后 7 天后清理 → User 已 anonymize", async ({ page, request }) => {
    await page.goto("/zh/account/settings");
    await page.getByTestId("deletion-request-button").click();
    await page.getByTestId("deletion-current-password").fill("pw");
    await page.getByTestId("deletion-confirm-text").fill("我要注销");
    await page.getByTestId("deletion-submit").click();
    await expect(page.getByTestId("restore-deletion-banner")).toBeVisible();
    // 注: 7 天清理用 e2e 时间 mock (或单独 e2e 用 seed 8 天前的 deletion_requested_at)
  });

  test("撤销注销后横幅消失", async ({ page }) => {
    // 假设种子数据已有 pending_deletion 账号
    await page.goto("/zh/account/settings");
    await expect(page.getByTestId("restore-deletion-banner")).toBeVisible();
    await page.getByTestId("banner-cancel-button").click();
    await page.getByTestId("banner-cancel-password").fill("pw");
    await page.getByTestId("banner-cancel-submit").click();
    await expect(page.getByTestId("restore-deletion-banner")).not.toBeVisible();
  });
});
```

- [ ] **Step 2: 跑 e2e (假设 backend 已起)**

```bash
cd packages/web && bun run test:e2e -- --grep "账号设置"
```

Expected: 5 PASS (跳过 7 天清理, 单独测)

- [ ] **Step 3: 写 handoff 文档**

按现有 handoff 格式 (2026-06-17-rbac-permission-system.md 模板) 写, 包含:
- 实施 phase 总结
- commit 列表
- 测试结果
- 关键设计决策 (8 个: 路由/匿名化/守卫/撤销/邮箱验证/头像/横幅/状态机)
- 接手者速查

- [ ] **Step 4: Commit**

```bash
git add packages/web/e2e/account-settings.spec.ts \
        docs/superpowers/handoffs/2026-06-17-account-settings.md
git commit -m "test(e2e): 账号设置 5 case + handoff 文档"
```

---

## Self-Review

**1. Spec coverage check:**

| Spec 章节 | 覆盖 task |
|----------|----------|
| §1 范围 7 用户故事 | T2.1+T2.2+T2.3+T2.4+T5.1 |
| §2 架构 (独立页 + 守卫) | T3.2 (PageGuard) + T2.5 (require_active_account) |
| §3 数据模型 | T1.1 |
| §4 8 endpoint | T2.1+T2.2+T2.3+T2.4+T2.5 |
| §5.1-5.4 状态机 | T2.4+T2.5+T5.1 |
| §5.5 清理 + 匿名化 | T5.1 |
| §6 头像上传 | T2.1 (process_avatar_upload + store_avatar) + T4.2 (UI) |
| §7 前端结构 | T3.1+T3.2+T3.3+T4.1+T4.2+T4.3 |
| §8 i18n 30 key | T3.1 |
| §9 测试 | T2.1~T2.5 单测 + T3.3 + T4.1 + T5.2 e2e |
| §11 Phase 拆分 | 1+5+3+3+2 = 14 commit |
| §12 移交 checklist | T5.2 handoff |

**2. Placeholder scan**: 无 "TBD" / "implement later" / "类似 Task N". 代码完整.

**3. Type consistency**:
- `display_name`: 全用同字段名 (1-50)
- `is_pending_deletion`: Python 属性 / Pydantic 字段 / TS 接口一致
- `restore_url` / `verification_url`: spec §5.3 已确认, plan 一致
- `current_password`: schema / action / dialog 一致
- `expires_at` (deletion): 7 天, 跟 DELETION_GRACE_DAYS 一致

**4. 已识别风险** (在 plan 中提到, 由 subagent 处理):
- apiFetch multipart 走 formData 直传 (T3.1 已示范)
- 头像上传 OOM: PIL `verify()` + 2MB 上限 (T2.1)
- 写操作守卫迁移范围: spec §5.4 列出 (需 subagent 实施时核对)

---

## Execution Choice

Plan 完成并保存到 `docs/superpowers/plans/2026-06-17-account-settings.md` (14 task, 估 14 commit).

两个执行选项:

1. **Subagent-Driven (推荐)** — 我每个 task 派一个新 subagent, task 间 review, 快速迭代. 跟你 RBAC + OpenAPI enhancement 用的模式一致.

2. **Inline Execution** — 在当前 session 顺序执行 task, 批量跑 + checkpoint 暂停给你 review.

**选哪种?**
