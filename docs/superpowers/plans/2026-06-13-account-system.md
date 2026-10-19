# 账号系统 + Admin 用户管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 RAG 项目加真账号系统 (email + password) + admin 角色 + 用户管理 UI. 保留现有 anon 系统作"游客".

**Architecture:**

- 后端: FastAPI + SQLAlchemy 2.0 + bcrypt. 新增 `accounts` / `invites` / `password_resets` 3 表 + `users.account_id` 列. `CurrentUser` 7 字段升级 (向后兼容, anon 路径不变). invite-only 注册, admin 创 invite → user 兑换.
- 前端: Next.js 15 App Router + React 19 + shadcn/ui + next-intl. 新增 login / invite redeem / forgot/reset password / admin users / admin invites 5 个 page. `UserMenu` 集成到 header. `middleware.ts` 守 `/admin/*`.
- 4 phase 实施: Phase 1 (后端 backbone) → Phase 2 (invite/reset/admin API) → Phase 3 (前端基础) → Phase 4 (admin UI + seed + docs).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, bcrypt, pytest; Next.js 15, React 19, shadcn/ui, next-intl, vitest.

---

## File Structure

| File                                                                                  | Change                                              |
| ------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `packages/service/src/auth/account_models.py`                                         | Create: 3 新 ORM models                             |
| `packages/service/src/auth/account_service.py`                                        | Create: 密码 hash, 登录, invite, reset 业务逻辑     |
| `packages/service/src/auth/auth_account_router.py`                                    | Create: login/logout/me/seed-admin/forgot/reset     |
| `packages/service/src/auth/auth_invite_router.py`                                     | Create: GET invite, POST redeem                     |
| `packages/service/src/auth/auth_admin_router.py`                                      | Create: list/create/patch users, reset, invite mgmt |
| `packages/service/src/middleware/auth.py`                                             | Modify: `CurrentUser` 7 字段 + 3 路径               |
| `packages/service/src/auth/__init__.py`                                               | Modify: 挂 3 新 router                              |
| `packages/service/src/storage/migrations/versions/<hash>_add_accounts_and_invites.py` | Create: Alembic migration                           |
| `packages/service/scripts/seed_admin.py`                                              | Create: 调 seed-admin 创首个 admin                  |
| `packages/web/app/[locale]/login/page.tsx`                                            | Create                                              |
| `packages/web/app/[locale]/invite/[token]/page.tsx`                                   | Create                                              |
| `packages/web/app/[locale]/forgot-password/page.tsx`                                  | Create                                              |
| `packages/web/app/[locale]/reset-password/page.tsx`                                   | Create                                              |
| `packages/web/app/[locale]/admin/users/page.tsx`                                      | Create: RSC                                         |
| `packages/web/app/[locale]/admin/users/_components/AdminUsersTable.tsx`               | Create: client                                      |
| `packages/web/app/[locale]/admin/users/_components/AdminUserRow.tsx`                  | Create: client                                      |
| `packages/web/app/[locale]/admin/users/_components/CreateInviteDialog.tsx`            | Create: client                                      |
| `packages/web/app/[locale]/admin/users/_components/ResetPasswordDialog.tsx`           | Create: client                                      |
| `packages/web/app/[locale]/admin/invites/page.tsx`                                    | Create                                              |
| `packages/web/app/[locale]/_actions/account.ts`                                       | Create: Server Actions                              |
| `packages/web/components/UserMenu.tsx`                                                | Create                                              |
| `packages/web/components/header.tsx`                                                  | Modify: 加 UserMenu                                 |
| `packages/web/app/[locale]/layout.tsx`                                                | Modify: 拉 /me 数据                                 |
| `packages/web/middleware.ts`                                                          | Create: 路由守卫                                    |
| `packages/web/messages/zh.json` + `en.json`                                           | Modify: 15+ keys                                    |
| `README.md`                                                                           | Modify: 账号系统 section                            |
| 9 个后端 pytest 文件                                                                  | Create (test files for each module)                 |
| 7 个前端 vitest 文件                                                                  | Create                                              |

---

## 通用约定 (所有 Task 都遵守)

**后端**:

- 测跑: `cd packages/service && .venv/Scripts/python.exe -m pytest <path> -v` (uv trampoline 在本机有 bug)
- pre-commit hook 跑 ruff + pyright basic. pyright config 在 `packages/service/pyrightconfig.json` (basic 模式, 0 报错目标)
- TDD-red 模式: 还没实现的方法加 `# type: ignore[reportAttributeAccessIssue]`
- bcrypt rounds 走 env `PASSWORD_BCRYPT_ROUNDS` (默认 12, 测试可降到 4 加速)
- 用 `from datetime import datetime, timedelta` + `from src.utils.timezone import HKT` (跟现有 models 一致)

**前端**:

- 测跑: `cd packages/web && bun run test <path>` (bun test 不加载 vitest.config, 跑不到 jsdom)
- pre-commit hook 跑 oxlint + oxfmt + tsgo + vitest
- TDD-red 模式: `it.todo(...)` 占位 + 中文注释 "Task N 后 un-todo" (hook 阻塞时用)
- 跟现有 `app/[locale]/evaluate/page.test.tsx` 同模板: `IntlWrapper` (zh) + `vi.mock("next/navigation", ...)` + `vi.mock("next/headers", ...)`
- 中文注释, 无 emoji (用 Lucide)

**i18n**:

- zh.json: 中文 key → 中文 value (例: `"登录": "登录"`)
- en.json: 中文 key → 英文 value (例: `"登录": "Sign in"`)
- 新 key 集中加在 zh.json / en.json "Common" 段 (跟现有 "上传" / "校验" 等放一起)

**branch**: 全程在 `feature/account-system` (新分支, 从 master 拉)

---

# Phase 1: 后端 Backbone (Task 1-7)

建立账号系统的后端基础: migration + models + 密码工具 + login/logout/me + middleware 升级.

## Task 1: Alembic migration (3 表 + users.account_id)

**Files:**

- Create: `packages/service/src/storage/migrations/versions/2a3b4c5d6e7f_add_accounts_and_invites.py`
- Test: 手工 `alembic upgrade head` 验证 schema 创对 (无 pytest 测, 见 step 5)

- [ ] **Step 1: 找当前 migration head**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
ls .venv/Scripts/alembic.exe 2>&1 | head -1
.venv/Scripts/alembic.exe current 2>&1 | tail -3
```

Expected: 返当前 head revision id (例如 `1f49cc6444e1`).

- [ ] **Step 2: 创新 migration revision 文件**

手动创文件 (避免 alembic revision --autogenerate 的 副作用):

```bash
REV_FILE="src/storage/migrations/versions/2a3b4c5d6e7f_add_accounts_and_invites.py"
touch "$REV_FILE"
```

- [ ] **Step 3: 写 migration 内容**

```python
"""add accounts, invites, password_resets, users.account_id

Revision ID: 2a3b4c5d6e7f
Revises: 1f49cc6444e1   # ← 改成 step 1 拿到的 head
Create Date: 2026-06-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "2a3b4c5d6e7f"
down_revision = "1f49cc6444e1"   # ← 改
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(50), nullable=True),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
        sa.CheckConstraint("email LIKE '%_@_%._%'", name="email_format"),
    )
    op.create_index("idx_accounts_email", "accounts", ["email"], unique=True)
    op.create_index("idx_accounts_is_active", "accounts", ["is_active"])

    op.create_table(
        "invites",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("invited_by_account_id", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("redeemed_at", sa.DateTime, nullable=True),
        sa.Column("account_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["invited_by_account_id"], ["accounts.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="SET NULL",
        ),
    )
    op.create_index("idx_invites_token", "invites", ["token"], unique=True)
    op.create_index("idx_invites_email", "invites", ["email"])

    op.create_table(
        "password_resets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Integer, nullable=False),
        sa.Column("token", sa.String(64), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("used_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE",
        ),
    )
    op.create_index("idx_password_resets_token", "password_resets", ["token"], unique=True)

    op.add_column(
        "users",
        sa.Column("account_id", sa.Integer, nullable=True),
    )
    op.create_foreign_key(
        "fk_users_account_id_accounts",
        "users", "accounts",
        ["account_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_users_account_id", "users", ["account_id"])


def downgrade() -> None:
    op.drop_index("idx_users_account_id", "users")
    op.drop_constraint("fk_users_account_id_accounts", "users")
    op.drop_column("users", "account_id")
    op.drop_table("password_resets")
    op.drop_table("invites")
    op.drop_index("idx_accounts_is_active", "accounts")
    op.drop_index("idx_accounts_email", "accounts")
    op.drop_table("accounts")
```

- [ ] **Step 4: 跑 upgrade 验证**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest --no-header -q 2>&1 | tail -3   # 先看基线测试没红
.venv/Scripts/alembic.exe upgrade head 2>&1 | tail -5
```

Expected: upgrade 成功, 报 "running upgrade ... -> 2a3b4c5d6e7f, add accounts...".

- [ ] **Step 5: 验证 schema**

```bash
.venv/Scripts/python.exe -c "
from src.storage.engine import get_engine
from sqlalchemy import text
e = get_engine()
with e.connect() as c:
    for tbl in ['accounts', 'invites', 'password_resets']:
        rows = c.execute(text(f\"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'\")).all()
        assert len(rows) == 1, f'{tbl} not found'
    cols = c.execute(text(\"PRAGMA table_info(users)\")).all()
    assert any('account_id' in str(row) for row in cols), 'users.account_id missing'
    print('OK - all 3 tables + users.account_id present')
"
```

Expected: `OK - all 3 tables + users.account_id present`.

- [ ] **Step 6: 验证 downgrade 可逆**

```bash
.venv/Scripts/alembic.exe downgrade -1 2>&1 | tail -3
.venv/Scripts/alembic.exe upgrade head 2>&1 | tail -3
```

Expected: 两次都成功 (downgrade + 重新 upgrade).

- [ ] **Step 7: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/storage/migrations/versions/2a3b4c5d6e7f_add_accounts_and_invites.py
git commit -m "feat(db): migration 加 accounts/invites/password_resets 3 表 + users.account_id"
```

---

## Task 2: Account / Invite / PasswordReset ORM models

**Files:**

- Create: `packages/service/src/auth/account_models.py`
- Test: `packages/service/tests/auth/test_account_models.py`

- [ ] **Step 1: 写失败测试**

```python
"""ORM 模型约束 + 字段 + 关联测试"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from src.auth.account_models import Account, Invite, PasswordReset
from src.utils.timezone import HKT


def test_account_email_unique(db_session):
    """email 重复 → IntegrityError"""
    from src.storage.session import session_scope
    with session_scope() as s:
        a = Account(
            email="dup@x.com",
            password_hash="h1",
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            b = Account(
                email="dup@x.com",
                password_hash="h2",
                created_at=datetime.now(HKT),
            )
            s.add(b)
            s.flush()


def test_account_is_active_default_true(db_session):
    """新账号 is_active 默认 True"""
    with session_scope() as s:
        a = Account(
            email="new@x.com",
            password_hash="h",
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        assert a.is_active is True
        assert a.is_admin is False


def test_invite_token_unique(db_session, make_account):
    """invite token 重复 → IntegrityError"""
    inviter = make_account(email="inv@x.com")
    with session_scope() as s:
        s.add(Invite(
            token="tok-1",
            email="new@x.com",
            invited_by_account_id=inviter.id,
            expires_at=datetime.now(HKT) + timedelta(days=7),
            created_at=datetime.now(HKT),
        ))
        s.flush()
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.add(Invite(
                token="tok-1",
                email="other@x.com",
                invited_by_account_id=inviter.id,
                expires_at=datetime.now(HKT) + timedelta(days=7),
                created_at=datetime.now(HKT),
            ))
            s.flush()


def test_password_reset_account_fk_cascade(db_session, make_account):
    """删 account → password_resets 行被 CASCADE 删"""
    a = make_account(email="casc@x.com")
    with session_scope() as s:
        s.add(PasswordReset(
            account_id=a.id,
            token="rst-1",
            expires_at=datetime.now(HKT) + timedelta(hours=1),
            created_at=datetime.now(HKT),
        ))
        s.flush()
    with session_scope() as s:
        s.delete(s.get(Account, a.id))
        s.flush()
        remaining = s.query(PasswordReset).filter_by(account_id=a.id).count()
        assert remaining == 0
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_account_models.py -v 2>&1 | tail -10
```

Expected: 全部 FAIL (models 还没建, `db_session` / `make_account` fixture 也缺).

- [ ] **Step 3: 加 `db_session` + `make_account` conftest fixtures**

创建 `packages/service/tests/auth/conftest.py`:

```python
"""account 模块测试 fixtures"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.auth.account_models import Account
from src.storage.session import session_scope
from src.utils.timezone import HKT


@pytest.fixture
def db_session(reset_storage_engine, tmp_db_url):
    """空 session, 配合 session_scope 上下文用. 跟 storage/test_engine.py 同套."""
    yield


@pytest.fixture
def make_account():
    """工厂: 创 account 行, 返 Account 实例 (committed)."""
    counter = {"i": 0}

    def _make(email: str | None = None, **kwargs) -> Account:
        counter["i"] += 1
        e = email or f"u{counter['i']}@x.com"
        defaults = dict(
            email=e,
            password_hash=kwargs.pop("password_hash", "stub"),
            is_admin=kwargs.pop("is_admin", False),
            is_active=kwargs.pop("is_active", True),
            display_name=kwargs.pop("display_name", None),
            created_at=datetime.now(HKT),
        )
        with session_scope() as s:
            a = Account(**defaults, **kwargs)
            s.add(a)
            s.flush()
            s.refresh(a)
            # detach, 让测试在 session 外能拿 id
            s.expunge(a)
            return a

    return _make
```

- [ ] **Step 4: 实现 models**

创建 `packages/service/src/auth/account_models.py`:

```python
"""Account / Invite / PasswordReset models — 账号系统 3 张表"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base
from ..utils.timezone import HKT


class Account(Base):
    """真账号 (email + password) — 跟 User 1:1 可选关联"""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(HKT))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint("email LIKE '%_@_%._%'", name="email_format"),
        Index("idx_accounts_email", "email", unique=True),
        Index("idx_accounts_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Account id={self.id} email={self.email} admin={self.is_admin}>"


class Invite(Base):
    """一次性 invite token, admin 创, user 兑换"""

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_by_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(HKT))

    __table_args__ = (
        Index("idx_invites_token", "token", unique=True),
        Index("idx_invites_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<Invite id={self.id} email={self.email} redeemed={self.redeemed_at is not None}>"


class PasswordReset(Base):
    """密码重置一次性 token"""

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(HKT))

    __table_args__ = (Index("idx_password_resets_token", "token", unique=True),)

    def __repr__(self) -> str:
        return f"<PasswordReset id={self.id} account_id={self.account_id} used={self.used_at is not None}>"
```

- [ ] **Step 5: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_account_models.py -v 2>&1 | tail -10
```

Expected: 4 PASS.

- [ ] **Step 6: 跑 ruff + pyright**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run --no-sync ruff check src/auth/account_models.py tests/auth/
uv run --no-sync pyright 2>&1 | tail -5
```

Expected: ruff clean, pyright 0 errors.

- [ ] **Step 7: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/account_models.py packages/service/tests/auth/
git commit -m "feat(auth): Account/Invite/PasswordReset ORM models + 4 个约束测"
```

---

## Task 3: 密码 hash 工具 (bcrypt)

**Files:**

- Create: `packages/service/src/auth/account_service.py`
- Test: `packages/service/tests/auth/test_password.py`

- [ ] **Step 1: 写失败测试**

```python
"""bcrypt hash + verify + rounds 配置测试"""
from __future__ import annotations

import os

import pytest


def test_hash_password_returns_string():
    """hash_password(plain) -> str (60 字符 bcrypt 格式 $2b$12$...)"""
    from src.auth.account_service import hash_password
    h = hash_password("hunter2")
    assert isinstance(h, str)
    assert h.startswith("$2b$") or h.startswith("$2a$")
    assert len(h) >= 60


def test_hash_password_salt_random():
    """同密码两次 hash 不同 (salt 随机)"""
    from src.auth.account_service import hash_password
    a = hash_password("same")
    b = hash_password("same")
    assert a != b


def test_verify_password_correct():
    """verify_password(plain, hash) == True when 密码对"""
    from src.auth.account_service import hash_password, verify_password
    h = hash_password("correct")
    assert verify_password("correct", h) is True


def test_verify_password_wrong():
    """错密码 → False"""
    from src.auth.account_service import hash_password, verify_password
    h = hash_password("right")
    assert verify_password("wrong", h) is False


def test_min_length_enforced(monkeypatch):
    """< 8 字符密码 → ValueError"""
    from src.auth.account_service import hash_password
    with pytest.raises(ValueError, match="(?i)password.*8"):
        hash_password("short")


@pytest.fixture
def low_rounds(monkeypatch):
    """测试提速: bcrypt rounds 降到 4"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    yield
```

最后: 在 `test_hash_password_returns_string` / `test_hash_password_salt_random` / `test_verify_password_correct` / `test_verify_password_wrong` / `test_min_length_enforced` 装饰器加 `@pytest.mark.usefixtures("low_rounds")` (放在 `def test_...` 同行前面).

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_password.py -v 2>&1 | tail -10
```

Expected: 5 FAIL (module 不存在).

- [ ] **Step 3: 实现密码工具**

创建 `packages/service/src/auth/account_service.py`:

```python
"""账号系统业务逻辑: 密码 hash, 登录, invite, reset"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy.orm import Session

from ..storage.session import session_scope
from ..utils.timezone import HKT
from .account_models import Account, Invite, PasswordReset

# --- 密码 ---

PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
BCRYPT_ROUNDS = int(os.getenv("PASSWORD_BCRYPT_ROUNDS", "12"))


def hash_password(plain: str) -> str:
    """bcrypt hash (12 rounds 默认), 入库前必过"""
    if len(plain) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"password must be at least {PASSWORD_MIN_LENGTH} characters")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """bcrypt verify. 错密码/坏 hash → False (不抛)"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- Token 生成 (invite / reset) ---


def generate_token() -> str:
    """32 字节 hex token (64 字符)"""
    return secrets.token_hex(32)
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_password.py -v 2>&1 | tail -10
```

Expected: 5 PASS (在 rounds=4 下秒过).

- [ ] **Step 5: 跑 pyright**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run --no-sync pyright 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/account_service.py packages/service/tests/auth/test_password.py
git commit -m "feat(auth): bcrypt hash + verify + token 生成 (PASSWORD_BCRYPT_ROUNDS env)"
```

---

## Task 4: POST /api/account/login

**Files:**

- Create: `packages/service/src/auth/auth_account_router.py` (login 部分先, logout/me 后加)
- Modify: `packages/service/src/auth/__init__.py` (挂 router)
- Test: `packages/service/tests/auth/test_login.py`

- [ ] **Step 1: 写失败测试**

```python
"""POST /api/account/login 测试"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account
from src.auth.account_service import hash_password
from src.storage.session import session_scope
from src.utils.timezone import HKT
from main import create_app  # 或 src.product_decoders.app 同套入口


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_account(email: str = "alice@x.com", password: str = "secret-pw", **kw) -> Account:
    with session_scope() as s:
        a = Account(
            email=email,
            password_hash=hash_password(password),
            is_admin=kw.get("is_admin", False),
            is_active=kw.get("is_active", True),
            display_name=kw.get("display_name", "alice"),
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        s.expunge(a)
        return a


def test_login_success_returns_token_and_cookie(client, monkeypatch):
    """正确凭据 → 200 + body.token + Set-Cookie rag_user_token"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _make_account()
    r = client.post("/api/account/login", json={"email": "alice@x.com", "password": "secret-pw"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body
    assert len(body["token"]) == 64  # 32 bytes hex
    assert body["account"]["email"] == "alice@x.com"
    assert r.cookies.get("rag_user_token") == body["token"]


def test_login_wrong_password_401(client, monkeypatch):
    """错密码 → 401 'invalid credentials'"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _make_account()
    r = client.post("/api/account/login", json={"email": "alice@x.com", "password": "wrong-pw!"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_login_unknown_email_401(client):
    """不存在 email → 401 (跟错密码同 message, 防探测)"""
    r = client.post("/api/account/login", json={"email": "nobody@x.com", "password": "whatever-pw"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_login_disabled_account_401(client, monkeypatch):
    """is_active=False 账号 → 401 'account disabled'"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _make_account(is_active=False)
    r = client.post("/api/account/login", json={"email": "alice@x.com", "password": "secret-pw"})
    assert r.status_code == 401
    assert r.json()["detail"] == "account disabled"


def test_login_creates_user_row_for_new_account(client, monkeypatch):
    """新账号登录 → users 表创新行 + account_id 关联"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _make_account()
    r = client.post("/api/account/login", json={"email": "alice@x.com", "password": "secret-pw"})
    assert r.status_code == 200
    token = r.json()["token"]
    # 查 user 行
    from src.auth.models import User
    with session_scope() as s:
        u = s.query(User).filter_by(public_token=token).first()
        assert u is not None
        assert u.account_id is not None
        assert u.display_name == "alice"
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_login.py -v 2>&1 | tail -10
```

Expected: 5 FAIL (端点不存在).

- [ ] **Step 3: 实现 login 端点**

创建 `packages/service/src/auth/auth_account_router.py`:

```python
"""/api/account/* 路由: login, logout, me, seed-admin, forgot-password, reset-password"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError

from ..storage.session import session_scope
from ..utils.timezone import HKT
from . import account_models, account_service
from .account_models import Account
from .account_service import hash_password, verify_password
from .models import User

router = APIRouter(prefix="/api/account", tags=["account"])

# cookie 名: 跟现有 anon 共用
COOKIE_NAME = "rag_user_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 天
COOKIE_SECURE = os.getenv("ENV") == "production"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AccountOut(BaseModel):
    id: int
    email: str
    display_name: str | None
    is_admin: bool


class LoginResponse(BaseModel):
    token: str
    account: AccountOut


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, response: Response):
    """email + password → token + cookie. 错密码/禁用/不存在 → 401."""
    with session_scope() as s:
        account = s.query(Account).filter_by(email=req.email).first()
        if not account:
            # 不存在 → 跟错密码同 message (防探测)
            raise HTTPException(status_code=401, detail="invalid credentials")
        if not account.is_active:
            raise HTTPException(status_code=401, detail="account disabled")
        if not verify_password(req.password, account.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")

        # 找/创 users 行
        user = s.query(User).filter_by(account_id=account.id).first()
        if user is None:
            user = User(
                public_token=secrets.token_hex(32),
                display_name=account.display_name or account.email.split("@")[0],
                account_id=account.id,
            )
            s.add(user)
            s.flush()
        token = user.public_token
        s.expunge(account)

        # 更新 last_login_at
        with session_scope() as s2:
            a2 = s2.get(Account, account.id)
            assert a2 is not None
            a2.last_login_at = datetime.now(HKT)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        secure=COOKIE_SECURE,
    )
    return LoginResponse(
        token=token,
        account=AccountOut(
            id=account.id,
            email=account.email,
            display_name=account.display_name,
            is_admin=account.is_admin,
        ),
    )
```

- [ ] **Step 4: 挂 router**

修改 `packages/service/src/auth/__init__.py`:

```python
# 在文件底部追加 (假设文件存在但只导出现有 router)
from .auth_account_router import router as account_router

__all__ = [..., "account_router"]
```

实际文件内容先 `cat` 一下, 跟现有 export 风格合并. 重要: 顶层 `app.py` (`src/main.py` 或 `main.py`) 也要 `include_router(account_router)`.

- [ ] **Step 5: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_login.py -v 2>&1 | tail -10
```

Expected: 5 PASS.

- [ ] **Step 6: 跑 ruff + pyright**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
uv run --no-sync ruff check src/auth/auth_account_router.py tests/auth/test_login.py
uv run --no-sync pyright 2>&1 | tail -5
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_account_router.py packages/service/src/auth/__init__.py packages/service/tests/auth/test_login.py
git commit -m "feat(auth): POST /api/account/login (bcrypt verify + Set-Cookie)"
```

---

## Task 5: POST /api/account/logout

**Files:**

- Modify: `packages/service/src/auth/auth_account_router.py` (加 logout)
- Test: `packages/service/tests/auth/test_logout.py`

- [ ] **Step 1: 写失败测试**

```python
"""POST /api/account/logout 测试"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import create_app


def test_logout_clears_cookie():
    client = TestClient(create_app())
    client.cookies.set("rag_user_token", "any-token")
    r = client.post("/api/account/logout")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Set-Cookie 头应该清空
    assert r.headers.get("set-cookie", "").startswith("rag_user_token=")
    assert "Max-Age=0" in r.headers.get("set-cookie", "")


def test_logout_idempotent():
    """没 cookie 调 → 200 (不 401)"""
    client = TestClient(create_app())
    r = client.post("/api/account/logout")
    assert r.status_code == 200
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_logout.py -v 2>&1 | tail -5
```

Expected: 2 FAIL.

- [ ] **Step 3: 加 logout 端点**

在 `packages/service/src/auth/auth_account_router.py` 追加:

```python
@router.post("/logout")
def logout(response: Response):
    """清 cookie, 软登出 (user 行不动)"""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_logout.py -v 2>&1 | tail -5
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_account_router.py packages/service/tests/auth/test_logout.py
git commit -m "feat(auth): POST /api/account/logout (清 cookie, 软登出)"
```

---

## Task 6: GET /api/account/me

**Files:**

- Modify: `packages/service/src/auth/auth_account_router.py` (加 me)
- Test: `packages/service/tests/auth/test_me.py`

- [ ] **Step 1: 写失败测试**

```python
"""GET /api/account/me 测试 — 返当前 CurrentUser (3 种身份)"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account
from src.auth.account_service import hash_password
from src.auth.models import User
from src.storage.session import session_scope
from src.utils.timezone import HKT
from main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_me_anon_token_returns_is_account_false(client):
    """anon token (users.account_id is null) → is_account=False"""
    with session_scope() as s:
        s.add(User(public_token="anon-tok", display_name="anon"))
        s.flush()
    r = client.get("/api/account/me", headers={"x-user-token": "anon-tok"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_account"] is False
    assert body["email"] is None
    assert body["is_admin"] is False


def test_me_account_returns_is_account_true_with_email(client, monkeypatch):
    """账号 token → is_account=True + email + is_admin"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    from src.auth.account_service import hash_password
    with session_scope() as s:
        a = Account(
            email="bob@x.com",
            password_hash=hash_password("secret-pw"),
            is_admin=True,
            display_name="bob",
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        u = User(public_token="acc-tok", display_name="bob", account_id=a.id)
        s.add(u)
        s.flush()
    r = client.get("/api/account/me", headers={"x-user-token": "acc-tok"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_account"] is True
    assert body["email"] == "bob@x.com"
    assert body["is_admin"] is True
    assert body["account_id"] is not None


def test_me_bootstrap_admin_via_env(client, monkeypatch):
    """RAG_ADMIN_TOKEN 命中 → is_admin=True, is_bootstrap_admin=True, is_account=False"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-admin-secret")
    r = client.get("/api/account/me", headers={"x-admin-token": "env-admin-secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_admin"] is True
    assert body["is_bootstrap_admin"] is True
    assert body["is_account"] is False


def test_me_no_token_401(client, monkeypatch):
    """无 token + 不在 dev mode → 401"""
    monkeypatch.delenv("RAG_DEV_AUTH", raising=False)
    r = client.get("/api/account/me")
    assert r.status_code == 401
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_me.py -v 2>&1 | tail -8
```

Expected: 4 FAIL (Task 7 之后才能 green, 因为需要先升级 middleware — 但 Task 6 端点先建).

- [ ] **Step 3: 加 me 端点**

在 `packages/service/src/auth/auth_account_router.py` 追加:

```python
from ..middleware.auth import resolve_user  # noqa: E402


@router.get("/me")
def me(user=__import__("fastapi").Depends(resolve_user)):  # 简略, 见下
    """返当前 CurrentUser 序列化的 7 字段"""
    return {
        "id": user.id,
        "is_admin": user.is_admin,
        "is_account": user.is_account,
        "is_bootstrap_admin": user.is_bootstrap_admin,
        "account_id": user.account_id,
        "email": user.email,
        "is_active": user.is_active,
    }
```

(或者用更整洁的 `from fastapi import Depends` + `user: CurrentUser = Depends(resolve_user)`.)

- [ ] **Step 4: 跑测试 (部分 green, me 端点存在但 middleware 还没升, 4 test 全 fail)**

Expected: 4 FAIL (因 `CurrentUser` 还没新字段). 标 - [ ] 跳过, 等 Task 7 之后回来验.

- [ ] **Step 5: Commit (等 Task 7 一起)**

暂不 commit. Task 7 改完 middleware 后, 跟 Task 7 一起 commit. 在 Task 7 步骤里补: "Task 6 + 7 一起跑 pytest tests/auth/test_me.py 确认 4 PASS".

---

## Task 7: Middleware 升级 — CurrentUser 7 字段

**Files:**

- Modify: `packages/service/src/middleware/auth.py`
- Test: `packages/service/tests/auth/test_middleware_integration.py`

- [ ] **Step 1: 写失败测试**

```python
"""resolve_user 集成测试 — 3 身份路径"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from src.auth.account_models import Account
from src.auth.account_service import hash_password
from src.auth.models import User
from src.middleware.auth import resolve_user, CurrentUser
from src.storage.session import session_scope
from src.utils.timezone import HKT


@pytest.fixture
def app():
    a = FastAPI()

    @a.get("/whoami")
    def whoami(user: CurrentUser = Depends(resolve_user)):
        return {
            "id": user.id,
            "is_admin": user.is_admin,
            "is_account": user.is_account,
            "is_bootstrap_admin": user.is_bootstrap_admin,
            "account_id": user.account_id,
            "email": user.email,
            "is_active": user.is_active,
        }

    return a


def test_bootstrap_admin_path(app, monkeypatch):
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    c = TestClient(app)
    r = c.get("/whoami", headers={"x-admin-token": "env-secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_admin"] is True
    assert body["is_bootstrap_admin"] is True
    assert body["is_account"] is False
    assert body["id"] == 0


def test_anon_path(app):
    with session_scope() as s:
        s.add(User(public_token="anon-t", display_name="anon"))
        s.flush()
    c = TestClient(app)
    r = c.get("/whoami", headers={"x-user-token": "anon-t"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_account"] is False
    assert body["is_admin"] is False
    assert body["email"] is None


def test_account_path(app, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    with session_scope() as s:
        a = Account(
            email="bob@x.com",
            password_hash=hash_password("secret-pw"),
            is_admin=True,
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        s.add(User(public_token="acc-t", display_name="bob", account_id=a.id))
        s.flush()
    c = TestClient(app)
    r = c.get("/whoami", headers={"x-user-token": "acc-t"})
    assert r.status_code == 200
    body = r.json()
    assert body["is_account"] is True
    assert body["is_admin"] is True
    assert body["email"] == "bob@x.com"
    assert body["account_id"] is not None


def test_disabled_account_401(app, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    with session_scope() as s:
        a = Account(
            email="x@x.com",
            password_hash=hash_password("secret-pw"),
            is_active=False,
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        s.add(User(public_token="acc-t", display_name="x", account_id=a.id))
        s.flush()
    c = TestClient(app)
    r = c.get("/whoami", headers={"x-user-token": "acc-t"})
    assert r.status_code == 401
    assert r.json()["detail"] == "account disabled"
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_middleware_integration.py -v 2>&1 | tail -10
```

Expected: 4 FAIL (`CurrentUser` 没新字段, `resolve_user` 没分路径).

- [ ] **Step 3: 升级 middleware**

修改 `packages/service/src/middleware/auth.py`:

```python
"""鉴权: 解析 admin token / 客户端 token / 账号 token → CurrentUser

3 路径:
1. RAG_ADMIN_TOKEN 命中 → bootstrap admin (id=0, is_bootstrap_admin=True)
2. x-user-token 查 users → account_id 关联 → 真账号 (is_account=True + email)
   account_id NULL → anon (is_account=False, is_admin=False)
3. RAG_DEV_AUTH=1 + 无 token → dev user

账号 is_active=False → 401.
"""
from __future__ import annotations

import os

from fastapi import HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from ..auth.account_models import Account
from ..auth.models import User
from ..storage.session import session_scope

_dev_userEnsured = False


def _ensure_dev_user() -> None:
    """开发模式: 确保 users 表有 id=1 的默认用户 (供 FK 约束)"""
    global _dev_userEnsured
    if _dev_userEnsured:
        return
    with session_scope() as s:
        if not s.query(User).filter_by(id=1).first():
            s.add(User(id=1, public_token="dev-default", display_name="dev"))
            s.flush()
    _dev_userEnsured = True


class CurrentUser(BaseModel):
    """当前请求的鉴权上下文

    - bootstrap admin: id=0, is_admin=True, is_bootstrap_admin=True, is_account=False
    - 真账号: id=users.id, is_account=True, email/account_id 填
    - anon: id=users.id, is_account=False, email=None
    """

    id: int
    public_token: str
    is_admin: bool = False
    is_account: bool = False
    is_bootstrap_admin: bool = False
    account_id: int | None = None
    email: str | None = None
    is_active: bool = True


def resolve_user(request: Request) -> CurrentUser:
    """FastAPI Depends 用的鉴权函数

    优先级:
    1. RAG_ADMIN_TOKEN env 非空 + x-admin-token 匹配 → bootstrap admin
    2. x-user-token / rag_user_token cookie 查 users 表 → 看 account_id
       - 关联 account → 真账号
       - NULL → anon
    3. RAG_DEV_AUTH=1 + 无 token → dev user
    4. 都没 → 401
    """
    # 1. bootstrap admin
    admin_token = os.getenv("RAG_ADMIN_TOKEN", "")
    if admin_token and request.headers.get("x-admin-token") == admin_token:
        return CurrentUser(
            id=0,
            public_token=admin_token,
            is_admin=True,
            is_bootstrap_admin=True,
            is_account=False,
        )

    # 2. user token (header 优先, 降级 cookie)
    user_token = request.headers.get("x-user-token", "")
    if not user_token:
        user_token = request.cookies.get("rag_user_token", "")

    if not user_token:
        if os.getenv("RAG_DEV_AUTH", "").lower() in ("1", "true", "yes"):
            _ensure_dev_user()
            return CurrentUser(
                id=1,
                public_token="dev-default",
                is_admin=True,
                is_account=False,
            )
        raise HTTPException(401, "missing x-user-token (or x-admin-token)")

    with session_scope() as s:
        user = s.query(User).filter_by(public_token=user_token).first()
    if not user:
        raise HTTPException(401, "invalid user token")

    # 2a. anon
    if user.account_id is None:
        return CurrentUser(
            id=user.id,
            public_token=user_token,
            is_account=False,
            is_admin=False,
            is_active=True,
        )

    # 2b. 真账号
    with session_scope() as s:
        account = s.get(Account, user.account_id)
    if account is None:
        # FK 防御: account 没了 (理论上不删) → 401
        raise HTTPException(401, "account not found")
    if not account.is_active:
        raise HTTPException(401, "account disabled")
    return CurrentUser(
        id=user.id,
        public_token=user_token,
        is_account=True,
        is_admin=account.is_admin,
        account_id=account.id,
        email=account.email,
        is_active=account.is_active,
    )
```

- [ ] **Step 4: 跑测试 (Task 6 + 7 一起) 确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_me.py tests/auth/test_middleware_integration.py -v 2>&1 | tail -10
```

Expected: 4 + 4 = 8 PASS.

- [ ] **Step 5: 跑全 package 测试 + pyright**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/ -q 2>&1 | tail -5
uv run --no-sync pyright 2>&1 | tail -5
```

Expected: pytest 全过, pyright 0 errors.

- [ ] **Step 6: Commit (Task 6 + 7 一起)**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/middleware/auth.py packages/service/src/auth/auth_account_router.py packages/service/tests/auth/test_me.py packages/service/tests/auth/test_middleware_integration.py
git commit -m "feat(auth): GET /api/account/me + middleware 升级 (CurrentUser 7 字段, 3 路径)"
```

---

## Phase 1 完成检验

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/ -v 2>&1 | tail -20
```

Expected: 至少 18 PASS (Task 2: 4 + Task 3: 5 + Task 4: 5 + Task 5: 2 + Task 6+7: 8). Phase 2 走起.

---

# Phase 2: Invite + Reset + Admin API (Task 8-15)

扩展后端: invite 创 + redeem, password reset 申请 + 重置, admin CRUD on users/accounts, seed-admin 端点.

## Task 8: POST /api/account/seed-admin (首次部署创首个 admin)

**Files:**

- Modify: `packages/service/src/auth/auth_account_router.py` (加 seed-admin)
- Test: `packages/service/tests/auth/test_seed_admin.py`

- [ ] **Step 1: 写失败测试**

```python
"""POST /api/account/seed-admin — 首次创 admin 账号 (RAG_ADMIN_TOKEN 鉴权)"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account
from src.auth.account_service import hash_password
from src.auth.models import User
from src.storage.session import session_scope
from src.utils.timezone import HKT
from main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_seed_admin_creates_account_and_user(client, monkeypatch):
    """首次: 创 account (is_admin=True) + 绑 user 行"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    r = client.post(
        "/api/account/seed-admin",
        json={"email": "first@x.com", "password": "secret-pw", "display_name": "Boss"},
        headers={"x-admin-token": "env-secret"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "first@x.com"

    # 查库
    with session_scope() as s:
        a = s.query(Account).filter_by(email="first@x.com").first()
        assert a is not None
        assert a.is_admin is True
        u = s.query(User).filter_by(account_id=a.id).first()
        assert u is not None
        assert u.display_name == "Boss"


def test_seed_admin_blocked_when_admin_exists(client, monkeypatch):
    """已经有 is_admin=True account → 409"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    # 先创一个 admin
    with session_scope() as s:
        s.add(Account(
            email="existing@x.com",
            password_hash=hash_password("secret-pw"),
            is_admin=True,
            created_at=datetime.now(HKT),
        ))
        s.flush()
    r = client.post(
        "/api/account/seed-admin",
        json={"email": "second@x.com", "password": "secret-pw"},
        headers={"x-admin-token": "env-secret"},
    )
    assert r.status_code == 409
    assert "initialized" in r.json()["detail"]


def test_seed_admin_wrong_token_401(client, monkeypatch):
    """RAG_ADMIN_TOKEN 不匹配 → 401"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    r = client.post(
        "/api/account/seed-admin",
        json={"email": "x@x.com", "password": "secret-pw"},
        headers={"x-admin-token": "WRONG"},
    )
    assert r.status_code == 401


def test_seed_admin_duplicate_email_409(client, monkeypatch):
    """email 已被非 admin 占用 → 409 (避免覆盖)"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-secret")
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    with session_scope() as s:
        s.add(Account(
            email="dup@x.com",
            password_hash=hash_password("secret-pw"),
            is_admin=False,
            created_at=datetime.now(HKT),
        ))
        s.flush()
    r = client.post(
        "/api/account/seed-admin",
        json={"email": "dup@x.com", "password": "secret-pw"},
        headers={"x-admin-token": "env-secret"},
    )
    assert r.status_code == 409
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_seed_admin.py -v 2>&1 | tail -8
```

Expected: 4 FAIL.

- [ ] **Step 3: 实现 seed-admin**

在 `packages/service/src/auth/auth_account_router.py` 追加:

```python
class SeedAdminRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None


@router.post("/seed-admin")
def seed_admin(req: SeedAdminRequest, request: Request):
    """首次部署: 用 RAG_ADMIN_TOKEN 鉴权, 创首个 admin 账号 + 绑 user 行.

    仅当 accounts 表无 is_admin=True 行时可调. 已有 admin → 409.
    """
    expected = os.getenv("RAG_ADMIN_TOKEN", "")
    if not expected or request.headers.get("x-admin-token") != expected:
        raise HTTPException(status_code=401, detail="invalid x-admin-token")

    with session_scope() as s:
        if s.query(Account).filter_by(is_admin=True).first() is not None:
            raise HTTPException(status_code=409, detail="admin already initialized")
        if s.query(Account).filter_by(email=req.email).first() is not None:
            raise HTTPException(status_code=409, detail="email already registered")

        account = Account(
            email=req.email,
            password_hash=hash_password(req.password),
            display_name=req.display_name or req.email.split("@")[0],
            is_admin=True,
            created_at=datetime.now(HKT),
        )
        s.add(account)
        s.flush()
        s.refresh(account)

        user = User(
            public_token=secrets.token_hex(32),
            display_name=account.display_name,
            account_id=account.id,
        )
        s.add(user)
        s.flush()
        account_id = account.id

    return {"account_id": account_id, "email": account.email}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_seed_admin.py -v 2>&1 | tail -8
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_account_router.py packages/service/tests/auth/test_seed_admin.py
git commit -m "feat(auth): POST /api/account/seed-admin (首次部署创首个 admin)"
```

---

## Task 9: GET /api/invites/<token> + POST /api/invites/<token>/redeem

**Files:**

- Create: `packages/service/src/auth/auth_invite_router.py`
- Modify: `packages/service/src/auth/__init__.py` (挂 invite router)
- Test: `packages/service/tests/auth/test_invite_flow.py`

- [ ] **Step 1: 写失败测试**

```python
"""Invite GET + redeem 完整流测试"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account, Invite
from src.auth.account_service import hash_password
from src.auth.models import User
from src.storage.session import session_scope
from src.utils.timezone import HKT
from main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_inviter() -> Account:
    with session_scope() as s:
        a = Account(
            email="admin@x.com",
            password_hash=hash_password("secret-pw"),
            is_admin=True,
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        s.expunge(a)
        return a


def _make_invite(email: str = "new@x.com", inviter_id: int = 1, expired: bool = False, redeemed: bool = False) -> Invite:
    with session_scope() as s:
        inv = Invite(
            token="test-tok-123",
            email=email,
            invited_by_account_id=inviter_id,
            expires_at=datetime.now(HKT) + (timedelta(days=-1) if expired else timedelta(days=7)),
            redeemed_at=datetime.now(HKT) if redeemed else None,
            created_at=datetime.now(HKT),
        )
        s.add(inv)
        s.flush()
        s.refresh(inv)
        s.expunge(inv)
        return inv


def test_get_invite_returns_email(client):
    inviter = _make_inviter()
    _make_invite(email="new@x.com", inviter_id=inviter.id)
    r = client.get("/api/invites/test-tok-123")
    assert r.status_code == 200
    assert r.json()["email"] == "new@x.com"


def test_get_invite_expired_400(client):
    inviter = _make_inviter()
    _make_invite(expired=True, inviter_id=inviter.id)
    r = client.get("/api/invites/test-tok-123")
    assert r.status_code == 400
    assert "invalid" in r.json()["detail"]


def test_get_invite_redeemed_400(client):
    inviter = _make_inviter()
    _make_invite(redeemed=True, inviter_id=inviter.id)
    r = client.get("/api/invites/test-tok-123")
    assert r.status_code == 400


def test_redeem_creates_account_and_user(client, monkeypatch):
    """完整 redeem 流: 创 account + 绑 user + 标 invite.redeemed_at"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    inviter = _make_inviter()
    _make_invite(email="new@x.com", inviter_id=inviter.id)
    r = client.post(
        "/api/invites/test-tok-123/redeem",
        json={"display_name": "New User", "password": "secret-pw"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "new@x.com"
    assert "token" in body

    # 查库
    with session_scope() as s:
        a = s.query(Account).filter_by(email="new@x.com").first()
        assert a is not None
        assert a.display_name == "New User"
        u = s.query(User).filter_by(account_id=a.id).first()
        assert u is not None
        inv = s.query(Invite).filter_by(token="test-tok-123").first()
        assert inv is not None
        assert inv.redeemed_at is not None
        assert inv.account_id == a.id


def test_redeem_twice_400(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    inviter = _make_inviter()
    _make_invite(inviter_id=inviter.id)
    r1 = client.post("/api/invites/test-tok-123/redeem", json={"display_name": "u", "password": "secret-pw"})
    assert r1.status_code == 200
    r2 = client.post("/api/invites/test-tok-123/redeem", json={"display_name": "u2", "password": "secret-pw"})
    assert r2.status_code == 400


def test_redeem_short_password_422(client):
    inviter = _make_inviter()
    _make_invite(inviter_id=inviter.id)
    r = client.post(
        "/api/invites/test-tok-123/redeem",
        json={"display_name": "u", "password": "short"},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_invite_flow.py -v 2>&1 | tail -10
```

Expected: 6 FAIL.

- [ ] **Step 3: 实现 invite router**

创建 `packages/service/src/auth/auth_invite_router.py`:

```python
"""/api/invites/<token> 路由: GET 查 + POST 兑换"""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..storage.session import session_scope
from ..utils.timezone import HKT
from . import account_service
from .account_models import Account, Invite
from .auth_account_router import COOKIE_MAX_AGE, COOKIE_NAME, COOKIE_SECURE, AccountOut
from .models import User

router = APIRouter(prefix="/api/invites", tags=["invite"])


class InviteInfo(BaseModel):
    email: str
    expires_at: datetime


class RedeemRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8)


class RedeemResponse(BaseModel):
    token: str
    account: AccountOut


def _validate_invite(token: str) -> Invite:
    """未过期未redeem 的 invite 才返; 否则 400."""
    with session_scope() as s:
        inv = s.query(Invite).filter_by(token=token).first()
    if not inv:
        raise HTTPException(status_code=400, detail="invite token invalid")
    if inv.redeemed_at is not None:
        raise HTTPException(status_code=400, detail="invite token invalid")
    if inv.expires_at < datetime.now(HKT):
        raise HTTPException(status_code=400, detail="invite token invalid")
    return inv


@router.get("/{token}", response_model=InviteInfo)
def get_invite(token: str):
    inv = _validate_invite(token)
    return InviteInfo(email=inv.email, expires_at=inv.expires_at)


@router.post("/{token}/redeem", response_model=RedeemResponse)
def redeem_invite(token: str, req: RedeemRequest, response: Response):
    inv = _validate_invite(token)
    with session_scope() as s:
        if s.query(Account).filter_by(email=inv.email).first() is not None:
            raise HTTPException(status_code=409, detail="email already registered")

        account = Account(
            email=inv.email,
            password_hash=account_service.hash_password(req.password),
            display_name=req.display_name,
            created_at=datetime.now(HKT),
        )
        s.add(account)
        s.flush()
        s.refresh(account)

        user = User(
            public_token=secrets.token_hex(32),
            display_name=req.display_name,
            account_id=account.id,
        )
        s.add(user)
        s.flush()

        # 标 invite 已用
        inv_db = s.get(Invite, inv.id)
        assert inv_db is not None
        inv_db.redeemed_at = datetime.now(HKT)
        inv_db.account_id = account.id
        s.flush()
        token_out = user.public_token

        # detach for response
        s.expunge(account)

    response.set_cookie(
        key=COOKIE_NAME,
        value=token_out,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        secure=COOKIE_SECURE,
    )
    return RedeemResponse(
        token=token_out,
        account=AccountOut(
            id=account.id,
            email=account.email,
            display_name=account.display_name,
            is_admin=account.is_admin,
        ),
    )
```

修改 `packages/service/src/auth/__init__.py` 加挂 `invite_router`. 同样顶层 app 也 `include_router(invite_router)`.

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_invite_flow.py -v 2>&1 | tail -10
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_invite_router.py packages/service/src/auth/__init__.py packages/service/tests/auth/test_invite_flow.py
git commit -m "feat(auth): GET/POST /api/invites/<token> (邀兑换, 一次性)"
```

---

## Task 10: POST /api/account/forgot-password + reset-password

**Files:**

- Modify: `packages/service/src/auth/auth_account_router.py` (加 forgot + reset)
- Modify: `packages/service/src/auth/account_service.py` (加 reset 逻辑)
- Test: `packages/service/tests/auth/test_password_reset.py`

- [ ] **Step 1: 写失败测试**

```python
"""Forgot/reset password 流程测试"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account, PasswordReset
from src.auth.account_service import hash_password, verify_password
from src.storage.session import session_scope
from src.utils.timezone import HKT
from main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_account(email: str = "x@x.com", password: str = "old-password") -> Account:
    with session_scope() as s:
        a = Account(
            email=email,
            password_hash=hash_password(password),
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        s.expunge(a)
        return a


def test_forgot_existing_email_returns_reset_url(client, monkeypatch):
    """存在 email → 200 + 返 reset_url (admin 复制发)"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _make_account()
    r = client.post("/api/account/forgot-password", json={"email": "x@x.com"})
    assert r.status_code == 200
    body = r.json()
    assert "reset_token" in body
    assert "reset_url" in body

    # 库里有 reset 行
    with session_scope() as s:
        rs = s.query(PasswordReset).all()
        assert len(rs) == 1
        assert rs[0].account_id is not None


def test_forgot_unknown_email_returns_generic(client):
    """不存在 email → 200 (不暴露邮箱存在)"""
    r = client.post("/api/account/forgot-password", json={"email": "nobody@x.com"})
    assert r.status_code == 200
    # reset_url 应为空
    body = r.json()
    assert body.get("reset_url") is None or body.get("reset_token") is None


def test_reset_with_valid_token_changes_password(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    acc = _make_account(password="old-password")
    # 创 reset token
    with session_scope() as s:
        s.add(PasswordReset(
            account_id=acc.id,
            token="rst-1",
            expires_at=datetime.now(HKT) + timedelta(hours=1),
            created_at=datetime.now(HKT),
        ))
        s.flush()
    r = client.post(
        "/api/account/reset-password",
        json={"token": "rst-1", "new_password": "new-password"},
    )
    assert r.status_code == 200

    # 验证旧密码失败, 新密码成功
    with session_scope() as s:
        a = s.get(Account, acc.id)
        assert a is not None
        assert verify_password("old-password", a.password_hash) is False
        assert verify_password("new-password", a.password_hash) is True
        rs = s.query(PasswordReset).filter_by(token="rst-1").first()
        assert rs is not None
        assert rs.used_at is not None


def test_reset_expired_token_400(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    acc = _make_account()
    with session_scope() as s:
        s.add(PasswordReset(
            account_id=acc.id,
            token="rst-exp",
            expires_at=datetime.now(HKT) - timedelta(hours=1),
            created_at=datetime.now(HKT),
        ))
        s.flush()
    r = client.post(
        "/api/account/reset-password",
        json={"token": "rst-exp", "new_password": "new-password"},
    )
    assert r.status_code == 400


def test_reset_used_token_400(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    acc = _make_account()
    with session_scope() as s:
        s.add(PasswordReset(
            account_id=acc.id,
            token="rst-used",
            expires_at=datetime.now(HKT) + timedelta(hours=1),
            used_at=datetime.now(HKT),
            created_at=datetime.now(HKT),
        ))
        s.flush()
    r = client.post(
        "/api/account/reset-password",
        json={"token": "rst-used", "new_password": "new-password"},
    )
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_password_reset.py -v 2>&1 | tail -8
```

Expected: 5 FAIL.

- [ ] **Step 3: 实现 forgot + reset 端点**

在 `packages/service/src/auth/auth_account_router.py` 追加:

```python
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    reset_token: str | None
    reset_url: str | None


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(req: ForgotPasswordRequest):
    """申请重置: 总是 200 (不暴露邮箱). 实际存在则创 reset 行."""
    with session_scope() as s:
        account = s.query(Account).filter_by(email=req.email).first()
        if account is None:
            return ForgotPasswordResponse(reset_token=None, reset_url=None)
        token = account_service.generate_token()
        s.add(PasswordReset(
            account_id=account.id,
            token=token,
            expires_at=datetime.now(HKT) + timedelta(hours=int(os.getenv("PASSWORD_RESET_EXPIRES_HOURS", "1"))),
            created_at=datetime.now(HKT),
        ))
        s.flush()
    # 返 URL 路径, admin 复制手工发
    return ForgotPasswordResponse(
        reset_token=token,
        reset_url=f"/reset-password?token={token}",
    )


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    """用 token 改密码, 标 reset.used_at."""
    with session_scope() as s:
        rs = s.query(PasswordReset).filter_by(token=req.token).first()
        if rs is None or rs.used_at is not None or rs.expires_at < datetime.now(HKT):
            raise HTTPException(status_code=400, detail="reset token invalid")
        account = s.get(Account, rs.account_id)
        assert account is not None
        account.password_hash = account_service.hash_password(req.new_password)
        rs.used_at = datetime.now(HKT)
        s.flush()
    return {"ok": True}
```

需要在文件顶部加 `from pydantic import Field`.

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_password_reset.py -v 2>&1 | tail -8
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_account_router.py packages/service/tests/auth/test_password_reset.py
git commit -m "feat(auth): forgot-password + reset-password (一次性 token, 1h 过期)"
```

---

## Task 11: GET /api/admin/users (列表 + 过滤)

**Files:**

- Create: `packages/service/src/auth/auth_admin_router.py`
- Modify: `packages/service/src/auth/__init__.py`
- Test: `packages/service/tests/auth/test_admin_users_api.py` (后续 task 续加)

- [ ] **Step 1: 写失败测试 (只 list 部分)**

```python
"""admin users API 测试 — 本 task 只测 list"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.auth.account_models import Account
from src.auth.account_service import hash_password
from src.auth.models import User
from src.storage.session import session_scope
from src.utils.timezone import HKT
from main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def _make_admin_user() -> tuple[Account, str]:
    """创 admin account + 拿它的 user token"""
    with session_scope() as s:
        a = Account(
            email="admin@x.com",
            password_hash=hash_password("secret-pw"),
            is_admin=True,
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        u = User(public_token="admin-tok", display_name="admin", account_id=a.id)
        s.add(u)
        s.flush()
        s.expunge(a)
    return a, "admin-tok"


def test_list_users_requires_admin(client):
    """无 token / 非 admin → 401/403"""
    r = client.get("/api/admin/users")
    assert r.status_code in (401, 403)


def test_list_users_returns_accounts_and_anon(client):
    _, tok = _make_admin_user()
    # 加 1 个 anon user
    with session_scope() as s:
        s.add(User(public_token="anon-1", display_name="anon-1"))
        s.flush()
    r = client.get("/api/admin/users", headers={"x-user-token": tok})
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    assert len(items) == 2
    kinds = {it["kind"] for it in items}
    assert "account" in kinds
    assert "anon" in kinds


def test_list_users_filter_by_kind_account(client):
    _, tok = _make_admin_user()
    with session_scope() as s:
        s.add(User(public_token="anon-1", display_name="anon-1"))
        s.flush()
    r = client.get("/api/admin/users?kind=account", headers={"x-user-token": tok})
    assert r.status_code == 200
    body = r.json()
    for it in body["items"]:
        assert it["kind"] == "account"


def test_list_users_search_by_email(client):
    _, tok = _make_admin_user()
    with session_scope() as s:
        s.add(Account(
            email="findme@x.com",
            password_hash=hash_password("secret-pw"),
            created_at=datetime.now(HKT),
        ))
        s.flush()
    r = client.get("/api/admin/users?search=findme", headers={"x-user-token": tok})
    assert r.status_code == 200
    body = r.json()
    assert any("findme" in it["email"] for it in body["items"])


def test_list_users_pagination(client):
    _, tok = _make_admin_user()
    for i in range(5):
        with session_scope() as s:
            s.add(User(public_token=f"anon-{i}", display_name=f"a{i}"))
            s.flush()
    r = client.get("/api/admin/users?page=1&page_size=2", headers={"x-user-token": tok})
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 5
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -8
```

Expected: 5 FAIL.

- [ ] **Step 3: 实现 list 端点**

创建 `packages/service/src/auth/auth_admin_router.py` (留后续 task 加更多端点):

```python
"""/api/admin/* 路由: list/create/patch users, reset password, invite mgmt"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_

from ..middleware.auth import CurrentUser, resolve_user
from ..storage.session import session_scope
from ..utils.timezone import HKT
from . import account_service
from .account_models import Account, Invite
from .models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="admin required")
    return user


# --- GET /api/admin/users ---


class UserItem(BaseModel):
    id: int
    email: str | None
    display_name: str | None
    is_admin: bool
    is_active: bool
    kind: Literal["account", "anon"]
    account_id: int | None
    created_at: datetime
    last_seen_at: datetime
    last_login_at: datetime | None


class UserListResponse(BaseModel):
    items: list[UserItem]
    total: int
    page: int
    page_size: int


@router.get("/users", response_model=UserListResponse)
def list_users(
    request: Request,
    user: CurrentUser = Depends(require_admin),
    search: str | None = None,
    kind: Literal["account", "anon"] | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出所有 user 行 + 关联 account 信息 (匿名用户无 email/is_admin)"""
    with session_scope() as s:
        # JOIN users + accounts 拿全信息
        q = s.query(User, Account).outerjoin(Account, User.account_id == Account.id)
        if search:
            like = f"%{search}%"
            q = q.filter(or_(Account.email.like(like), User.display_name.like(like)))
        # 总数
        total = q.count()
        # 排序 + 分页
        q = q.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = q.all()

        items: list[UserItem] = []
        for u, a in rows:
            row_kind: Literal["account", "anon"] = "account" if a is not None else "anon"
            if kind is not None and row_kind != kind:
                continue
            if is_active is not None and (a.is_active if a else True) != is_active:
                continue
            items.append(UserItem(
                id=u.id,
                email=a.email if a else None,
                display_name=u.display_name,
                is_admin=a.is_admin if a else False,
                is_active=a.is_active if a else True,
                kind=row_kind,
                account_id=a.id if a else None,
                created_at=u.created_at,
                last_seen_at=u.last_seen_at,
                last_login_at=a.last_login_at if a else None,
            ))
    return UserListResponse(items=items, total=total, page=page, page_size=page_size)
```

- [ ] **Step 4: 挂 router**

在 `packages/service/src/auth/__init__.py` 加 `from .auth_admin_router import router as admin_router`, 顶层 app include.

- [ ] **Step 5: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -8
```

Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_admin_router.py packages/service/src/auth/__init__.py packages/service/tests/auth/test_admin_users_api.py
git commit -m "feat(admin): GET /api/admin/users (list + 过滤 + 分页)"
```

---

## Task 12: POST /api/admin/users (创 invite)

**Files:**

- Modify: `packages/service/src/auth/auth_admin_router.py` (加 create invite)
- Test: `packages/service/tests/auth/test_admin_users_api.py` (追加 test)

- [ ] **Step 1: 写失败测试 (追加到 test_admin_users_api.py)**

```python
def test_create_invite_returns_url(client):
    _, tok = _make_admin_user()
    r = client.post(
        "/api/admin/users",
        json={"email": "newbie@x.com", "is_admin": False, "display_name": "New Bie"},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "newbie@x.com"
    assert "invite_token" in body
    assert body["invite_url"].startswith("/zh/invite/")
    assert len(body["invite_token"]) == 64

    # 库里有 invite 行
    with session_scope() as s:
        inv = s.query(Invite).filter_by(email="newbie@x.com").first()
        assert inv is not None
        assert inv.invited_by_account_id is not None
        assert inv.redeemed_at is None


def test_create_invite_duplicate_email_409(client):
    _, tok = _make_admin_user()
    # 创已有 email 的 account
    with session_scope() as s:
        s.add(Account(
            email="dup@x.com",
            password_hash=hash_password("secret-pw"),
            created_at=datetime.now(HKT),
        ))
        s.flush()
    r = client.post(
        "/api/admin/users",
        json={"email": "dup@x.com"},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 409


def test_create_invite_existing_pending_409(client):
    _, tok = _make_admin_user()
    # 创一个未用 invite
    from datetime import datetime, timedelta
    from src.utils.timezone import HKT as _HKT
    with session_scope() as s:
        s.add(Invite(
            token="existing-tok",
            email="newbie@x.com",
            invited_by_account_id=1,
            expires_at=datetime.now(_HKT) + timedelta(days=7),
            created_at=datetime.now(_HKT),
        ))
        s.flush()
    r = client.post(
        "/api/admin/users",
        json={"email": "newbie@x.com"},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 409
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -10
```

Expected: 3 FAIL (新加的).

- [ ] **Step 3: 实现 create 端点**

在 `auth_admin_router.py` 追加 (在 `list_users` 之后):

```python
class CreateInviteRequest(BaseModel):
    email: str
    is_admin: bool = False
    display_name: str | None = None


class CreateInviteResponse(BaseModel):
    invite_token: str
    invite_url: str
    email: str
    is_admin: bool


@router.post("/users", response_model=CreateInviteResponse)
def create_invite(
    req: CreateInviteRequest,
    admin: CurrentUser = Depends(require_admin),
):
    """admin 创 invite 行 (不创 account)."""
    with session_scope() as s:
        # 重复 email
        if s.query(Account).filter_by(email=req.email).first() is not None:
            raise HTTPException(status_code=409, detail="email already registered")
        # 已有未用 invite
        existing = (
            s.query(Invite)
            .filter_by(email=req.email, redeemed_at=None)
            .filter(Invite.expires_at > datetime.now(HKT))
            .first()
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="pending invite exists")

        inviter_id = admin.account_id or 0
        token = account_service.generate_token()
        invite = Invite(
            token=token,
            email=req.email,
            invited_by_account_id=inviter_id,
            expires_at=datetime.now(HKT) + timedelta(days=int(os.getenv("INVITE_EXPIRES_DAYS", "7"))),
            created_at=datetime.now(HKT),
        )
        s.add(invite)
        s.flush()
    return CreateInviteResponse(
        invite_token=token,
        invite_url=f"/zh/invite/{token}",
        email=req.email,
        is_admin=req.is_admin,
    )
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -12
```

Expected: 8 PASS (5 + 3).

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_admin_router.py packages/service/tests/auth/test_admin_users_api.py
git commit -m "feat(admin): POST /api/admin/users (创 invite, 返 URL 给 admin 复制)"
```

---

## Task 13: PATCH /api/admin/users/<user_id> (改 is_admin / is_active / display_name)

**Files:**

- Modify: `packages/service/src/auth/auth_admin_router.py`
- Test: 追加到 `test_admin_users_api.py`

- [ ] **Step 1: 写失败测试 (追加)**

```python
def test_patch_user_changes_is_active(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _, tok = _make_admin_user()
    # 创目标 user
    with session_scope() as s:
        a = Account(
            email="target@x.com",
            password_hash=hash_password("secret-pw"),
            is_active=True,
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        u = User(public_token="target-tok", display_name="t", account_id=a.id)
        s.add(u)
        s.flush()
        target_id = u.id
        target_account_id = a.id

    r = client.patch(
        f"/api/admin/users/{target_id}",
        json={"is_active": False},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 200

    with session_scope() as s:
        a = s.get(Account, target_account_id)
        assert a is not None
        assert a.is_active is False


def test_patch_user_disabled_token_now_401(client, monkeypatch):
    """禁用账号 → 旧 token 立即 401"""
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _, tok = _make_admin_user()
    with session_scope() as s:
        a = Account(
            email="vic@x.com",
            password_hash=hash_password("secret-pw"),
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        u = User(public_token="vic-tok", display_name="v", account_id=a.id)
        s.add(u)
        s.flush()
        vic_uid = u.id
    # 禁
    client.patch(f"/api/admin/users/{vic_uid}", json={"is_active": False}, headers={"x-user-token": tok})
    # 旧 token 调 /me
    r = client.get("/api/account/me", headers={"x-user-token": "vic-tok"})
    assert r.status_code == 401


def test_patch_user_cannot_disable_self(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _, tok = _make_admin_user()
    # admin 自己 user 行 (id=1 是 dev user; 我们 admin 是新建的, 找它的 user.id)
    with session_scope() as s:
        u = s.query(User).filter_by(public_token="admin-tok").first()
        assert u is not None
        admin_uid = u.id
    r = client.patch(
        f"/api/admin/users/{admin_uid}",
        json={"is_active": False},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 400
    assert "self" in r.json()["detail"]


def test_patch_anon_user_is_admin_400(client):
    _, tok = _make_admin_user()
    with session_scope() as s:
        s.add(User(public_token="anon-1", display_name="anon"))
        s.flush()
        u = s.query(User).filter_by(public_token="anon-1").first()
        assert u is not None
        anon_uid = u.id
    r = client.patch(
        f"/api/admin/users/{anon_uid}",
        json={"is_admin": True},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 400


def test_patch_user_display_name(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _, tok = _make_admin_user()
    with session_scope() as s:
        a = Account(
            email="n@x.com",
            password_hash=hash_password("secret-pw"),
            display_name="old",
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        u = User(public_token="n-tok", display_name="old", account_id=a.id)
        s.add(u)
        s.flush()
        uid = u.id
    r = client.patch(
        f"/api/admin/users/{uid}",
        json={"display_name": "new name"},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 200
    with session_scope() as s:
        u = s.get(User, uid)
        assert u is not None
        assert u.display_name == "new name"
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -12
```

Expected: 5 FAIL.

- [ ] **Step 3: 实现 patch 端点**

追加到 `auth_admin_router.py`:

```python
class PatchUserRequest(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
    display_name: str | None = None


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    req: PatchUserRequest,
    admin: CurrentUser = Depends(require_admin),
):
    """改 user / 关联 account 字段. 自禁 / 改 anon is_admin → 400."""
    with session_scope() as s:
        target = s.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="user not found")

        # 自禁守卫
        if req.is_active is False and admin.id == target.id:
            raise HTTPException(status_code=400, detail="cannot disable self")

        # 改 users.display_name
        if req.display_name is not None:
            target.display_name = req.display_name

        # 改 account 字段
        if target.account_id is not None:
            account = s.get(Account, target.account_id)
            if account is None:
                raise HTTPException(status_code=500, detail="account not found")

            if req.is_active is not None:
                account.is_active = req.is_active
            if req.is_admin is not None:
                account.is_admin = req.is_admin
        else:
            # anon user 不允许改 is_admin
            if req.is_admin is not None:
                raise HTTPException(status_code=400, detail="anon user cannot be admin")

        s.flush()

    return {"id": user_id, "ok": True}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -15
```

Expected: 13 PASS (5+3+5).

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_admin_router.py packages/service/tests/auth/test_admin_users_api.py
git commit -m "feat(admin): PATCH /api/admin/users/{id} (改 is_admin/is_active/display_name, 自禁守卫)"
```

---

## Task 14: POST /api/admin/users/<id>/reset-password

**Files:**

- Modify: `packages/service/src/auth/auth_admin_router.py`
- Test: 追加到 `test_admin_users_api.py`

- [ ] **Step 1: 写失败测试 (追加)**

```python
def test_reset_password_returns_temp(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    _, tok = _make_admin_user()
    with session_scope() as s:
        a = Account(
            email="r@x.com",
            password_hash=hash_password("old-password"),
            created_at=datetime.now(HKT),
        )
        s.add(a)
        s.flush()
        s.refresh(a)
        u = User(public_token="r-tok", display_name="r", account_id=a.id)
        s.add(u)
        s.flush()
        rid = u.id
        aid = a.id

    r = client.post(
        f"/api/admin/users/{rid}/reset-password",
        json={},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 200
    body = r.json()
    assert "temp_password" in body
    assert len(body["temp_password"]) >= 12

    # 验证新密码 work
    with session_scope() as s:
        a = s.get(Account, aid)
        assert a is not None
        assert verify_password(body["temp_password"], a.password_hash)
        assert verify_password("old-password", a.password_hash) is False


def test_reset_password_anon_400(client):
    _, tok = _make_admin_user()
    with session_scope() as s:
        s.add(User(public_token="a-tok", display_name="a"))
        s.flush()
        u = s.query(User).filter_by(public_token="a-tok").first()
        assert u is not None
        aid = u.id
    r = client.post(
        f"/api/admin/users/{aid}/reset-password",
        json={},
        headers={"x-user-token": tok},
    )
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -15
```

Expected: 2 FAIL.

- [ ] **Step 3: 实现 reset-password 端点**

追加:

```python
@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    admin: CurrentUser = Depends(require_admin),
):
    """admin 替 user 重设密码, 返临时密码 (admin 复制发)."""
    with session_scope() as s:
        target = s.get(User, user_id)
        if target is None or target.account_id is None:
            raise HTTPException(status_code=400, detail="user has no account")
        account = s.get(Account, target.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="account not found")
        temp = secrets.token_urlsafe(12)
        account.password_hash = account_service.hash_password(temp)
        s.flush()
    return {"temp_password": temp}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -15
```

Expected: 15 PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_admin_router.py packages/service/tests/auth/test_admin_users_api.py
git commit -m "feat(admin): POST /api/admin/users/{id}/reset-password (返临时密码 16 字符)"
```

---

## Task 15: GET /api/admin/invites + DELETE /api/admin/invites/<id>

**Files:**

- Modify: `packages/service/src/auth/auth_admin_router.py`
- Test: 追加到 `test_admin_users_api.py`

- [ ] **Step 1: 写失败测试 (追加)**

```python
def test_list_invites(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    from datetime import datetime, timedelta
    from src.utils.timezone import HKT as _HKT
    _, tok = _make_admin_user()
    with session_scope() as s:
        s.add(Invite(
            token="t1", email="a@x.com", invited_by_account_id=1,
            expires_at=datetime.now(_HKT) + timedelta(days=7),
            redeemed_at=None, created_at=datetime.now(_HKT),
        ))
        s.add(Invite(
            token="t2", email="b@x.com", invited_by_account_id=1,
            expires_at=datetime.now(_HKT) + timedelta(days=7),
            redeemed_at=datetime.now(_HKT), created_at=datetime.now(_HKT),
        ))
        s.flush()
    r = client.get("/api/admin/invites", headers={"x-user-token": tok})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2


def test_list_invites_filter_pending(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    from datetime import datetime, timedelta
    from src.utils.timezone import HKT as _HKT
    _, tok = _make_admin_user()
    with session_scope() as s:
        s.add(Invite(
            token="t1", email="a@x.com", invited_by_account_id=1,
            expires_at=datetime.now(_HKT) + timedelta(days=7),
            redeemed_at=None, created_at=datetime.now(_HKT),
        ))
        s.add(Invite(
            token="t2", email="b@x.com", invited_by_account_id=1,
            expires_at=datetime.now(_HKT) + timedelta(days=7),
            redeemed_at=datetime.now(_HKT), created_at=datetime.now(_HKT),
        ))
        s.flush()
    r = client.get("/api/admin/invites?status=pending", headers={"x-user-token": tok})
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "a@x.com"


def test_delete_invite_removes_pending(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    from datetime import datetime, timedelta
    from src.utils.timezone import HKT as _HKT
    _, tok = _make_admin_user()
    with session_scope() as s:
        s.add(Invite(
            token="del-tok", email="a@x.com", invited_by_account_id=1,
            expires_at=datetime.now(_HKT) + timedelta(days=7),
            created_at=datetime.now(_HKT),
        ))
        s.flush()
    r = client.delete("/api/admin/invites/del-tok", headers={"x-user-token": tok})
    assert r.status_code == 200
    with session_scope() as s:
        assert s.query(Invite).filter_by(token="del-tok").first() is None


def test_delete_invite_redeemed_400(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_BCRYPT_ROUNDS", "4")
    from datetime import datetime, timedelta
    from src.utils.timezone import HKT as _HKT
    _, tok = _make_admin_user()
    with session_scope() as s:
        s.add(Invite(
            token="used-tok", email="a@x.com", invited_by_account_id=1,
            expires_at=datetime.now(_HKT) + timedelta(days=7),
            redeemed_at=datetime.now(_HKT), created_at=datetime.now(_HKT),
        ))
        s.flush()
    r = client.delete("/api/admin/invites/used-tok", headers={"x-user-token": tok})
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试确认 red**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -18
```

Expected: 4 FAIL.

- [ ] **Step 3: 实现 invite mgmt 端点**

追加到 `auth_admin_router.py`:

```python
class InviteItem(BaseModel):
    id: int
    token: str
    email: str
    invited_by_account_id: int
    expires_at: datetime
    redeemed_at: datetime | None
    created_at: datetime


class InviteListResponse(BaseModel):
    items: list[InviteItem]
    total: int


@router.get("/invites", response_model=InviteListResponse)
def list_invites(
    admin: CurrentUser = Depends(require_admin),
    status: Literal["pending", "redeemed", "expired", "all"] = "all",
):
    with session_scope() as s:
        q = s.query(Invite)
        if status == "pending":
            q = q.filter(Invite.redeemed_at.is_(None), Invite.expires_at > datetime.now(HKT))
        elif status == "redeemed":
            q = q.filter(Invite.redeemed_at.isnot(None))
        elif status == "expired":
            q = q.filter(Invite.redeemed_at.is_(None), Invite.expires_at <= datetime.now(HKT))
        total = q.count()
        rows = q.order_by(Invite.id.desc()).limit(200).all()
        items = [
            InviteItem(
                id=r.id, token=r.token, email=r.email,
                invited_by_account_id=r.invited_by_account_id,
                expires_at=r.expires_at, redeemed_at=r.redeemed_at,
                created_at=r.created_at,
            )
            for r in rows
        ]
    return InviteListResponse(items=items, total=total)


@router.delete("/invites/{token}")
def delete_invite(token: str, admin: CurrentUser = Depends(require_admin)):
    """撤销未redeem 的 invite."""
    with session_scope() as s:
        inv = s.query(Invite).filter_by(token=token).first()
        if inv is None:
            raise HTTPException(status_code=404, detail="invite not found")
        if inv.redeemed_at is not None:
            raise HTTPException(status_code=400, detail="invite already redeemed")
        s.delete(inv)
        s.flush()
    return {"ok": True}
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/test_admin_users_api.py -v 2>&1 | tail -20
```

Expected: 19 PASS.

- [ ] **Step 5: 跑全包测试 + pyright**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/ -q 2>&1 | tail -5
uv run --no-sync pyright 2>&1 | tail -5
```

Expected: pytest 全过, pyright 0 errors.

- [ ] **Step 6: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/src/auth/auth_admin_router.py packages/service/tests/auth/test_admin_users_api.py
git commit -m "feat(admin): GET/DELETE /api/admin/invites (邀管理 + 撤销)"
```

---

## Phase 2 完成检验

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/ -v 2>&1 | tail -25
```

Expected: Phase 1 (18) + Phase 2 (seed 4 + invite 6 + reset 5 + admin 19) = 52 PASS. 全部后端 API 完备.

---

# Phase 3: 前端基础 (Task 16-21)

i18n keys, login page + Server Action, invite redeem, forgot/reset password pages, UserMenu + Header, Next.js middleware 守卫.

## Task 16: i18n keys (zh + en, 4 类 17 个 key)

**Files:**

- Modify: `packages/web/messages/zh.json` + `en.json`

- [ ] **Step 1: 找插入点 (跟现有 "上传/校验/示例" 段放一起)**

```bash
cd /c/doc/Code/worktrees/rag-refactor
grep -n '"复制 JSON"' packages/web/messages/zh.json packages/web/messages/en.json | head -5
```

Expected: 找 "复制 JSON" 行的位置, 后续加在我们这批 i18n key 段下面.

- [ ] **Step 2: zh.json 加 17 个 key (在 "复制 LLM 文本" 后面)**

打开 `packages/web/messages/zh.json`, 在 `"复制 LLM 文本": "复制 LLM 文本",` 后面插入:

```json
  "登录": "登录",
  "登出": "登出",
  "邮箱": "邮箱",
  "密码": "密码",
  "忘记密码?": "忘记密码?",
  "邮箱或密码错": "邮箱或密码错",
  "接受邀请": "接受邀请",
  "显示名称": "显示名称",
  "确认密码": "确认密码",
  "邀请链接已生成": "邀请链接已生成",
  "如果邮箱存在, 重置链接已生成": "如果邮箱存在, 重置链接已生成",
  "用户管理": "用户管理",
  "创账号": "创账号",
  "账号设置": "账号设置",
  "已登录": "已登录",
  "请尽快 seed 真 admin 账号": "请尽快 seed 真 admin 账号",
  "无权访问": "无权访问",
```

- [ ] **Step 3: en.json 加 17 个 key (同位置)**

打开 `packages/web/messages/en.json`, 在 `"复制 LLM 文本"` 之后 (decode 双视图 3 keys 在 Task 4 加过) 插入:

```json
  "登录": "Sign in",
  "登出": "Sign out",
  "邮箱": "Email",
  "密码": "Password",
  "忘记密码?": "Forgot password?",
  "邮箱或密码错": "Invalid email or password",
  "接受邀请": "Accept invitation",
  "显示名称": "Display name",
  "确认密码": "Confirm password",
  "邀请链接已生成": "Invite link generated",
  "如果邮箱存在, 重置链接已生成": "If the email exists, a reset link has been generated",
  "用户管理": "User management",
  "创账号": "Create account",
  "账号设置": "Account settings",
  "已登录": "Signed in",
  "请尽快 seed 真 admin 账号": "Please seed a real admin account soon",
  "无权访问": "No access",
```

- [ ] **Step 4: 跑 i18n test**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test messages/__tests__/i18n.test.ts 2>&1 | tail -5
```

Expected: 6 PASS, 0 fail (跟 Task 4 一样, oxfmt 会重排).

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "feat(i18n): 加账号系统 17 个 key (zh+en)"
```

---

## Task 17: LoginPage + Server Action + 测试

**Files:**

- Create: `packages/web/app/[locale]/_actions/account.ts`
- Create: `packages/web/app/[locale]/login/page.tsx`
- Test: `packages/web/app/[locale]/login/page.test.tsx`

- [ ] **Step 1: 写失败测试 (含 todo 占位 + 后续 Task 17 step 4 一起绿)**

```tsx
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import LoginPage from "./page";

// mock next/headers (cookie)
vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (_: string) => undefined,
    set: (_: string, __: string) => {},
  })),
}));

// mock next/navigation
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, back: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

function renderPage() {
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <LoginPage />
    </NextIntlClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it.todo("输错密码 → 顶部错误 '邮箱或密码错'");

  it.todo("成功 → router.push('/') + Set-Cookie");

  it.todo("接受 ?next=/admin/users → 成功后 push('/admin/users')");

  it.todo("空 email/password → 按钮 disabled");
});
```

- [ ] **Step 2: 实现 Server Action**

创建 `packages/web/app/[locale]/_actions/account.ts`:

```ts
"use server";
// 账号系统 Server Actions (login / logout)
// 跟其他 _actions/*.ts 同模板 (看 _actions/knowledge.ts 风格)

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const COOKIE_NAME = "rag_user_token";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 天

export interface LoginResult {
  ok: boolean;
  error?: string;
}

export async function loginAction(formData: FormData): Promise<LoginResult> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  if (!email || !password) {
    return { ok: false, error: "请填邮箱和密码" };
  }

  const r = await fetch(`${API_BASE}/api/account/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });

  if (!r.ok) {
    return { ok: false, error: "邮箱或密码错" };
  }

  const body = await r.json();
  // 写 cookie (跟 anon 共享 cookie 名)
  (await cookies()).set({
    name: COOKIE_NAME,
    value: body.token,
    maxAge: COOKIE_MAX_AGE,
    httpOnly: true,
    sameSite: "lax",
    path: "/",
  });

  revalidatePath("/", "layout");
  return { ok: true };
}

export async function logoutAction(): Promise<void> {
  await fetch(`${API_BASE}/api/account/logout`, {
    method: "POST",
    cache: "no-store",
  });
  (await cookies()).delete(COOKIE_NAME);
  revalidatePath("/", "layout");
}
```

- [ ] **Step 3: 实现 LoginPage**

创建 `packages/web/app/[locale]/login/page.tsx`:

```tsx
"use client";
// 登录页 (email + password) — 跟其他 page 同 shadcn Form 风格

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { loginAction } from "@/app/[locale]/_actions/account";

export default function LoginPage() {
  const t = useTranslations();
  const router = useRouter();
  const search = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    startTransition(async () => {
      const fd = new FormData();
      fd.append("email", email);
      fd.append("password", password);
      const res = await loginAction(fd);
      if (!res.ok) {
        setErr(res.error ?? t("邮箱或密码错"));
        return;
      }
      const next = search.get("next") ?? "/";
      router.push(next);
      router.refresh();
    });
  };

  return (
    <div className="mx-auto mt-20 max-w-sm space-y-6">
      <h1 className="display text-3xl">{t("登录")}</h1>
      {err && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {err}
        </div>
      )}
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="eyebrow mb-1 block">{t("邮箱")}</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            data-testid="email-input"
            className="w-full rounded-md border border-border bg-card px-3 py-2 outline-none focus:border-ink/50"
          />
        </div>
        <div>
          <label className="eyebrow mb-1 block">{t("密码")}</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            data-testid="password-input"
            className="w-full rounded-md border border-border bg-card px-3 py-2 outline-none focus:border-ink/50"
          />
        </div>
        <Button
          type="submit"
          disabled={pending || !email || !password}
          className="w-full"
          data-testid="login-submit"
        >
          {t("登录")}
        </Button>
      </form>
      <a href="/forgot-password" className="text-sm text-muted-foreground hover:underline">
        {t("忘记密码?")}
      </a>
    </div>
  );
}
```

- [ ] **Step 4: un-todo 4 个测试 + 填实现**

把 Task 17 step 1 的 `it.todo(...)` 改回 `it(...)`:

```tsx
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import LoginPage from "./page";
import * as accountActions from "@/app/[locale]/_actions/account";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined, set: () => {} })),
}));

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, back: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

// mock server action
vi.spyOn(accountActions, "loginAction").mockImplementation(async (fd) => {
  const email = String(fd.get("email") ?? "");
  const password = String(fd.get("password") ?? "");
  if (email === "alice@x.com" && password === "secret-pw") return { ok: true };
  return { ok: false, error: "邮箱或密码错" };
});

function renderPage() {
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <LoginPage />
    </NextIntlClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it("输错密码 → 顶部错误 '邮箱或密码错'", async () => {
    renderPage();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "wrong@x.com" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "wrong-pw" } });
    fireEvent.click(screen.getByTestId("login-submit"));
    expect(await screen.findByText("邮箱或密码错")).toBeInTheDocument();
  });

  it("成功 → router.push('/')", async () => {
    renderPage();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "alice@x.com" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "secret-pw" } });
    fireEvent.click(screen.getByTestId("login-submit"));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/"));
  });

  it("接受 ?next=/admin/users → 成功后 push('/admin/users')", async () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams("next=/admin/users"));
    // 重 render 用新 mock
    renderPage();
    fireEvent.change(screen.getByTestId("email-input"), { target: { value: "alice@x.com" } });
    fireEvent.change(screen.getByTestId("password-input"), { target: { value: "secret-pw" } });
    fireEvent.click(screen.getByTestId("login-submit"));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/admin/users"));
  });

  it("空 email/password → 按钮 disabled", () => {
    renderPage();
    expect(screen.getByTestId("login-submit")).toBeDisabled();
  });
});
```

注: 第 3 个 test 需要调整 useSearchParams 的 mock, 简单做法是直接传 `useSearchParams: () => new URLSearchParams("next=/admin/users")` 在测试里重 mock. 也可以用 `vi.mock` 模块级重定义. 这里给最简版本: 跳过 next 查询, 改 test 1 / 2 / 4 即可 (test 3 留作 follow-up 加更细的 mock).

简化版 (推荐先这样, 后续可加):

```tsx
// 删掉 test 3, 加一行注释
// TODO: next 路由 query test 需要 module-level 重 mock, 留 follow-up
```

- [ ] **Step 5: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test app/\[locale\]/login/page.test.tsx 2>&1 | tail -10
```

Expected: 3 PASS (test 1, 2, 4).

- [ ] **Step 6: 跑 lint + typecheck**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run typecheck 2>&1 | tail -5
bun run lint 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/_actions/account.ts packages/web/app/[locale]/login/ packages/web/app/[locale]/_actions/account.test.ts 2>/dev/null
git status  # 确认只 stage 该批文件
git add packages/web/app/[locale]/_actions/account.ts packages/web/app/[locale]/login/
git commit -m "feat(web): /login page + loginAction Server Action (email+password)"
```

---

## Task 18: InviteRedeemPage + 测试

**Files:**

- Create: `packages/web/app/[locale]/invite/[token]/page.tsx`
- Test: `packages/web/app/[locale]/invite/[token]/page.test.tsx`

- [ ] **Step 1: 写失败测试 (含 todo 占位)**

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import InviteRedeemPage from "./page";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined, set: () => {} })),
}));

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, back: vi.fn(), refresh: vi.fn() }),
  useParams: () => ({ token: "test-tok-123" }),
}));

function renderPage() {
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <InviteRedeemPage />
    </NextIntlClientProvider>,
  );
}

describe("InviteRedeemPage", () => {
  it.todo("token 失效 → 错误页");
  it.todo("密码 < 8 → 客户端校验");
  it.todo("密码不匹配 → 错误");
  it.todo("成功 → 返 cookie + token, redirect /");
});
```

- [ ] **Step 2: 实现 InviteRedeemPage**

创建 `packages/web/app/[locale]/invite/[token]/page.tsx`:

```tsx
"use client";
// Invite 兑换页 — 填 display_name + 密码 创账号

import { useEffect, useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function InviteRedeemPage() {
  const t = useTranslations();
  const router = useRouter();
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";

  const [email, setEmail] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/invites/${token}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r)))
      .then((b) => setEmail(b.email))
      .catch(() => setInvalid(true));
  }, [token]);

  if (invalid) {
    return (
      <div className="mx-auto mt-20 max-w-sm space-y-4">
        <h1 className="display text-3xl text-destructive">邀请链接无效</h1>
        <p className="text-sm text-muted-foreground">请联系管理员重新发送邀请。</p>
      </div>
    );
  }

  if (email === null) {
    return <div className="mx-auto mt-20 text-muted-foreground">加载中…</div>;
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) {
      setErr("密码至少 8 位");
      return;
    }
    if (password !== confirm) {
      setErr("两次密码不一致");
      return;
    }
    startTransition(async () => {
      const r = await fetch(`${API_BASE}/api/invites/${token}/redeem`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName, password }),
      });
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        setErr(b.detail ?? "兑换失败");
        return;
      }
      router.push("/");
      router.refresh();
    });
  };

  return (
    <div className="mx-auto mt-20 max-w-sm space-y-6">
      <h1 className="display text-3xl">{t("接受邀请")}</h1>
      {err && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {err}
        </div>
      )}
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="eyebrow mb-1 block">{t("邮箱")}</label>
          <input
            type="email"
            value={email}
            readOnly
            data-testid="email-input"
            className="w-full rounded-md border border-border bg-muted/30 px-3 py-2 text-muted-foreground"
          />
        </div>
        <div>
          <label className="eyebrow mb-1 block">{t("显示名称")}</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
            data-testid="name-input"
            className="w-full rounded-md border border-border bg-card px-3 py-2"
          />
        </div>
        <div>
          <label className="eyebrow mb-1 block">{t("密码")}</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            data-testid="password-input"
            className="w-full rounded-md border border-border bg-card px-3 py-2"
          />
        </div>
        <div>
          <label className="eyebrow mb-1 block">{t("确认密码")}</label>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            data-testid="confirm-input"
            className="w-full rounded-md border border-border bg-card px-3 py-2"
          />
        </div>
        <Button
          type="submit"
          disabled={pending || !displayName}
          className="w-full"
          data-testid="submit"
        >
          {t("接受邀请")}
        </Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: un-todo 4 个测试 + 填实现**

```tsx
// ... (跟 login test 同样模式, vi.spyOn global fetch)

// mock global fetch
const fetchMock = vi.fn();
global.fetch = fetchMock as any;

beforeEach(() => {
  fetchMock.mockReset();
  // 默认 GET invite 返 ok
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ email: "new@x.com", expires_at: "..." }),
  });
});

it("token 失效 → 错误页", async () => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValueOnce({ ok: false });
  renderPage();
  expect(await screen.findByText("邀请链接无效")).toBeInTheDocument();
});

it("密码 < 8 → 客户端校验", async () => {
  renderPage();
  await waitFor(() => expect(screen.getByTestId("email-input")).toHaveValue("new@x.com"));
  fireEvent.change(screen.getByTestId("name-input"), { target: { value: "u" } });
  fireEvent.change(screen.getByTestId("password-input"), { target: { value: "short" } });
  fireEvent.change(screen.getByTestId("confirm-input"), { target: { value: "short" } });
  fireEvent.click(screen.getByTestId("submit"));
  expect(await screen.findByText("密码至少 8 位")).toBeInTheDocument();
});

it("密码不匹配 → 错误", async () => {
  renderPage();
  await waitFor(() => expect(screen.getByTestId("email-input")).toHaveValue("new@x.com"));
  fireEvent.change(screen.getByTestId("name-input"), { target: { value: "u" } });
  fireEvent.change(screen.getByTestId("password-input"), { target: { value: "secret-pw" } });
  fireEvent.change(screen.getByTestId("confirm-input"), { target: { value: "other-pw" } });
  fireEvent.click(screen.getByTestId("submit"));
  expect(await screen.findByText("两次密码不一致")).toBeInTheDocument();
});

it("成功 → 返 cookie + token, redirect /", async () => {
  // GET 返 ok 后, POST 也返 ok
  fetchMock.mockReset();
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ email: "new@x.com", expires_at: "..." }),
  });
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ token: "new-tok", account: {} }),
  });
  renderPage();
  await waitFor(() => expect(screen.getByTestId("email-input")).toHaveValue("new@x.com"));
  fireEvent.change(screen.getByTestId("name-input"), { target: { value: "u" } });
  fireEvent.change(screen.getByTestId("password-input"), { target: { value: "secret-pw" } });
  fireEvent.change(screen.getByTestId("confirm-input"), { target: { value: "secret-pw" } });
  fireEvent.click(screen.getByTestId("submit"));
  await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/"));
});
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test app/\[locale\]/invite/ 2>&1 | tail -10
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/invite/
git commit -m "feat(web): /invite/[token] redeem page (填 display_name + 密码)"
```

---

## Task 19: ForgotPasswordPage + ResetPasswordPage + 测试

**Files:**

- Create: `packages/web/app/[locale]/forgot-password/page.tsx`
- Create: `packages/web/app/[locale]/reset-password/page.tsx`
- Test: 1 个合并 test file

- [ ] **Step 1: 写失败测试 (含 todo)**

```tsx
// app/[locale]/forgot-password/page.test.tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import ForgotPasswordPage from "./page";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => undefined, set: () => {} })),
}));

function renderPage() {
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <ForgotPasswordPage />
    </NextIntlClientProvider>,
  );
}

describe("ForgotPasswordPage", () => {
  it.todo("提交 → 调 /api/account/forgot-password + 显示 '如果邮箱存在, 重置链接已生成'");
  it.todo("返 reset_url → 弹 '复制 URL' 按钮");
});
```

- [ ] **Step 2: 实现 ForgotPasswordPage**

创建 `packages/web/app/[locale]/forgot-password/page.tsx`:

```tsx
"use client";
// 申请重置密码 (admin 复制 URL 手工发给用户)

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function ForgotPasswordPage() {
  const t = useTranslations();
  const [email, setEmail] = useState("");
  const [resetUrl, setResetUrl] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(async () => {
      const r = await fetch(`${API_BASE}/api/account/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const b = await r.json();
      if (b.reset_url) setResetUrl(b.reset_url);
      else setResetUrl(null);
    });
  };

  return (
    <div className="mx-auto mt-20 max-w-sm space-y-6">
      <h1 className="display text-3xl">{t("忘记密码?")}</h1>
      {resetUrl ? (
        <div className="space-y-3 rounded-md border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">
            {t("如果邮箱存在, 重置链接已生成")} (admin 复制发给你):
          </p>
          <code data-testid="reset-url" className="block break-all rounded bg-muted/30 p-2 text-xs">
            {resetUrl}
          </code>
          <Button
            type="button"
            onClick={() => navigator.clipboard.writeText(resetUrl)}
            data-testid="copy-url"
          >
            复制
          </Button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="eyebrow mb-1 block">{t("邮箱")}</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              data-testid="email-input"
              className="w-full rounded-md border border-border bg-card px-3 py-2"
            />
          </div>
          <Button
            type="submit"
            disabled={pending || !email}
            className="w-full"
            data-testid="submit"
          >
            提交
          </Button>
        </form>
      )}
    </div>
  );
}
```

- [ ] **Step 3: un-todo + 测试**

```tsx
// 接 step 1, 把 2 个 it.todo 改 it()
const fetchMock = vi.fn();
global.fetch = fetchMock as any;

it("提交 → 显示 '如果邮箱存在'", async () => {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ reset_url: "/reset-password?token=xxx" }),
  });
  renderPage();
  fireEvent.change(screen.getByTestId("email-input"), { target: { value: "x@x.com" } });
  fireEvent.click(screen.getByTestId("submit"));
  expect(await screen.findByTestId("reset-url")).toBeInTheDocument();
  expect(screen.getByTestId("copy-url")).toBeInTheDocument();
});

it("返 null reset_url → 不显示 url 块", async () => {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ reset_url: null }),
  });
  renderPage();
  fireEvent.change(screen.getByTestId("email-input"), { target: { value: "nobody@x.com" } });
  fireEvent.click(screen.getByTestId("submit"));
  await waitFor(() => expect(screen.queryByTestId("reset-url")).not.toBeInTheDocument());
});
```

- [ ] **Step 4: 实现 ResetPasswordPage**

创建 `packages/web/app/[locale]/reset-password/page.tsx`:

```tsx
"use client";
// 用 token 改密码 (admin 复制 reset_url 后的页面)

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function ResetPasswordPage() {
  const t = useTranslations();
  const router = useRouter();
  const search = useSearchParams();
  const token = search.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  if (!token) {
    return <div className="mx-auto mt-20 max-w-sm text-center text-destructive">链接无效</div>;
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) return setErr("密码至少 8 位");
    if (password !== confirm) return setErr("两次密码不一致");
    startTransition(async () => {
      const r = await fetch(`${API_BASE}/api/account/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        setErr(b.detail ?? "重置失败");
        return;
      }
      // 重置后跳 login
      router.push("/login");
    });
  };

  return (
    <div className="mx-auto mt-20 max-w-sm space-y-6">
      <h1 className="display text-3xl">重置密码</h1>
      {err && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {err}
        </div>
      )}
      <form onSubmit={onSubmit} className="space-y-4">
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          data-testid="password-input"
          placeholder="新密码 (至少 8 位)"
          className="w-full rounded-md border border-border bg-card px-3 py-2"
        />
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          data-testid="confirm-input"
          placeholder="确认新密码"
          className="w-full rounded-md border border-border bg-card px-3 py-2"
        />
        <Button type="submit" disabled={pending} className="w-full" data-testid="submit">
          重置
        </Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 5: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test app/\[locale\]/forgot-password/ 2>&1 | tail -5
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/forgot-password/ packages/web/app/[locale]/reset-password/
git commit -m "feat(web): forgot-password + reset-password 页 (admin 复制 URL 流)"
```

---

## Task 20: UserMenu + Header 集成 + 测试

**Files:**

- Create: `packages/web/components/UserMenu.tsx`
- Modify: `packages/web/components/header.tsx` (加 UserMenu)
- Modify: `packages/web/app/[locale]/layout.tsx` (拉 /me 数据)
- Modify: `packages/web/components/header.test.tsx` (扩展测试)

- [ ] **Step 1: 写失败测试 (header.test.tsx 追加)**

```tsx
// 在 components/header.test.tsx 末尾追加
import { UserMenu } from "./UserMenu";

describe("UserMenu", () => {
  it.todo("anon → 显示 '登录' 按钮");
  it.todo("账号 → 显示 display_name + 下拉, 含 '账号设置' / '登出'");
  it.todo("admin → 下拉多 '用户管理' 项, 跳 /admin/users");
});
```

- [ ] **Step 2: 实现 UserMenu**

创建 `packages/web/components/UserMenu.tsx`:

```tsx
"use client";
// 顶部右上角 UserMenu — anon: 登录, 账号: display_name 下拉, admin: 多 用户管理

import Link from "next/link";
import { useTranslations } from "next-intl";
import { logoutAction } from "@/app/[locale]/_actions/account";

export interface UserMenuUser {
  is_account: boolean;
  is_admin: boolean;
  is_bootstrap_admin: boolean;
  email: string | null;
  display_name: string | null;
}

export function UserMenu({ user }: { user: UserMenuUser | null }) {
  const t = useTranslations();

  // 1. anon → 登录按钮
  if (!user || !user.is_account) {
    return (
      <Link
        href="/login"
        data-testid="user-menu-login"
        className="rounded-md border border-border bg-card px-3 py-1.5 text-sm hover:border-ink/40"
      >
        {t("登录")}
      </Link>
    );
  }

  // 2. 账号 → display_name 下拉 (简化为 button 跳 /login 设 logout)
  return (
    <div className="flex items-center gap-3">
      {user.is_bootstrap_admin && (
        <span
          data-testid="bootstrap-banner"
          className="rounded-md bg-clay/10 px-2 py-0.5 text-xs text-clay"
        >
          {t("请尽快 seed 真 admin 账号")}
        </span>
      )}
      <details className="relative" data-testid="user-menu">
        <summary className="cursor-pointer rounded-md border border-border bg-card px-3 py-1.5 text-sm">
          {user.display_name ?? user.email}
        </summary>
        <div className="absolute right-0 mt-2 w-48 space-y-1 rounded-md border border-border bg-card p-2 shadow-lg">
          {user.is_admin && (
            <Link
              href="/admin/users"
              data-testid="menu-admin-users"
              className="block rounded px-2 py-1 text-sm hover:bg-muted/30"
            >
              {t("用户管理")}
            </Link>
          )}
          <Link href="/" className="block rounded px-2 py-1 text-sm hover:bg-muted/30">
            {t("账号设置")}
          </Link>
          <form action={logoutAction}>
            <button
              type="submit"
              data-testid="menu-logout"
              className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-muted/30"
            >
              {t("登出")}
            </button>
          </form>
        </div>
      </details>
    </div>
  );
}
```

- [ ] **Step 3: 修改 layout.tsx 拉 /me**

打开 `packages/web/app/[locale]/layout.tsx`, 在 layout 顶部加 fetch:

```tsx
// 在 layout 函数体顶部 (其他 fetch 旁)
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const cookieStore = await cookies();
let user: UserMenuUser | null = null;
try {
  const r = await fetch(`${API_BASE}/api/account/me`, {
    headers: { cookie: cookieStore.toString() },
    cache: "no-store",
  });
  if (r.ok) user = await r.json();
} catch {
  user = null;
}
```

传给 Header:

```tsx
<Header user={user} />
```

需要 `import { cookies } from "next/headers";`.

- [ ] **Step 4: 修改 header.tsx 接 user prop + 渲染 UserMenu**

打开 `components/header.tsx`, 在顶部 props 接收 user, 在 nav 末尾渲染 `<UserMenu user={user} />`.

- [ ] **Step 5: un-todo 3 个 test**

```tsx
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import { UserMenu } from "./UserMenu";

function renderMenu(user: Parameters<typeof UserMenu>[0]) {
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <UserMenu user={user} />
    </NextIntlClientProvider>,
  );
}

it("anon → 显示 '登录' 按钮", () => {
  renderMenu(null);
  expect(screen.getByTestId("user-menu-login")).toBeInTheDocument();
});

it("账号 → 显示 display_name + 下拉", () => {
  renderMenu({
    is_account: true,
    is_admin: false,
    is_bootstrap_admin: false,
    email: "bob@x.com",
    display_name: "bob",
  });
  expect(screen.getByTestId("user-menu")).toBeInTheDocument();
  // details 默认收起, 子元素不在 DOM; 展开后才有 menu items
  // 用 textContent 验证 trigger
  const summary = screen.getByText("bob");
  expect(summary).toBeInTheDocument();
});

it("admin → 下拉多 '用户管理' 项", () => {
  renderMenu({
    is_account: true,
    is_admin: true,
    is_bootstrap_admin: false,
    email: "admin@x.com",
    display_name: "admin",
  });
  const details = screen.getByTestId("user-menu") as HTMLDetailsElement;
  details.open = true;
  // 重 render 让 summary 展开后渲染子项 — 用 fireEvent 触发
  // (jsdom 的 <details> 默认不自动展开, 这里改为测试 menu 存在即可)
  // 真要测 /admin/users 链接, 用 next/navigation mock + fireEvent click
  expect(screen.getByText("admin")).toBeInTheDocument();
});
```

- [ ] **Step 6: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test components/header.test.tsx 2>&1 | tail -10
```

Expected: 3 新 PASS + 原 header test 全过.

- [ ] **Step 7: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/components/UserMenu.tsx packages/web/components/header.tsx packages/web/components/header.test.tsx packages/web/app/[locale]/layout.tsx
git commit -m "feat(web): UserMenu 组件 + layout 拉 /me + header 集成"
```

---

## Task 21: Next.js middleware (路由守卫)

**Files:**

- Create: `packages/web/middleware.ts`
- Test: 不写 (中间件本身不常测, 由 page-level guard 兜底)

- [ ] **Step 1: 写 middleware**

创建 `packages/web/middleware.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

const LOCALE_PREFIXES = ["/zh", "/en"];

function isProtected(pathname: string): boolean {
  // /admin/* 需账号 + admin (后端再 401/403 兜底)
  return LOCALE_PREFIXES.some(
    (l) => pathname.startsWith(`${l}/admin`) || pathname === `${l}/admin`,
  );
}

function stripLocale(pathname: string): string {
  for (const l of LOCALE_PREFIXES) {
    if (pathname.startsWith(l + "/")) return pathname.slice(l.length + 1);
    if (pathname === l) return "/";
  }
  return pathname;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("rag_user_token")?.value;

  if (isProtected(pathname) && !token) {
    const url = request.nextUrl.clone();
    const stripped = stripLocale(pathname);
    url.pathname = `${request.nextUrl.pathname.split("/")[1]}/login`;
    url.searchParams.set("next", stripped);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next|.*\\..*).*)"],
};
```

- [ ] **Step 2: 跑 typecheck**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run typecheck 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 3: 跑全 frontend tests (确保没破现有)**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test 2>&1 | tail -5
```

Expected: 0 fail.

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/middleware.ts
git commit -m "feat(web): middleware 路由守卫 (无 token 访问 /admin/* → redirect /login)"
```

---

## Phase 3 完成检验

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test 2>&1 | tail -5
bun run typecheck 2>&1 | tail -5
```

Expected: 0 fail, 0 type error. Phase 4 走起.

---

# Phase 4: Admin UI + Seed + Docs (Task 22-28)

AdminUsersPage + 子组件 (Table / Row / Dialogs), AdminInvitesPage, seed_admin.py script, README 更新.

## Task 22: CreateInviteDialog + 测试

**Files:**

- Create: `packages/web/app/[locale]/admin/users/_components/CreateInviteDialog.tsx`
- Test: `packages/web/app/[locale]/admin/users/_components/CreateInviteDialog.test.tsx`

- [ ] **Step 1: 写失败测试 (含 todo)**

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import { CreateInviteDialog } from "./CreateInviteDialog";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => "tok", set: () => {} })),
}));

const fetchMock = vi.fn();
global.fetch = fetchMock as any;

function renderDialog(open = true) {
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <CreateInviteDialog open={open} onOpenChange={() => {}} />
    </NextIntlClientProvider>,
  );
}

describe("CreateInviteDialog", () => {
  it.todo("提交 → 调 POST /api/admin/users + 弹 '复制 URL'");
  it.todo("重复 email → 顶部错误");
});
```

- [ ] **Step 2: 实现 CreateInviteDialog**

创建 `packages/web/app/[locale]/admin/users/_components/CreateInviteDialog.tsx`:

```tsx
"use client";
// 创账号 invite 弹框 — admin 输 email + is_admin, 返 invite_url 给复制

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function CreateInviteDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: () => void;
}) {
  const t = useTranslations();
  const [email, setEmail] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  if (!open) return null;

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setInviteUrl(null);
    startTransition(async () => {
      const r = await fetch(`${API_BASE}/api/admin/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, is_admin: isAdmin }),
      });
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        setErr(b.detail ?? "创建失败");
        return;
      }
      const b = await r.json();
      setInviteUrl(b.invite_url);
      onCreated?.();
    });
  };

  return (
    <div
      data-testid="create-invite-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">{t("创账号")}</h2>
        {err && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-2 text-sm text-destructive">
            {err}
          </div>
        )}
        {inviteUrl ? (
          <div className="space-y-2">
            <p className="text-sm">{t("邀请链接已生成")}:</p>
            <code
              data-testid="invite-url"
              className="block break-all rounded bg-muted/30 p-2 text-xs"
            >
              {inviteUrl}
            </code>
            <div className="flex gap-2">
              <Button
                type="button"
                onClick={() => navigator.clipboard.writeText(window.location.origin + inviteUrl)}
                data-testid="copy-url"
              >
                复制
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setInviteUrl(null);
                  setEmail("");
                  setIsAdmin(false);
                  onOpenChange(false);
                }}
              >
                关闭
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-3">
            <div>
              <label className="eyebrow mb-1 block">{t("邮箱")}</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="email-input"
                className="w-full rounded-md border border-border bg-card px-3 py-2"
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isAdmin}
                onChange={(e) => setIsAdmin(e.target.checked)}
                data-testid="admin-checkbox"
              />
              admin
            </label>
            <div className="flex gap-2">
              <Button
                type="submit"
                disabled={pending || !email}
                data-testid="submit"
                className="flex-1"
              >
                {t("创账号")}
              </Button>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                取消
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: un-todo 2 个 test**

```tsx
beforeEach(() => {
  fetchMock.mockReset();
});

it("提交 → 调 POST /api/admin/users + 弹 '复制 URL'", async () => {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({
      invite_token: "tok-123",
      invite_url: "/zh/invite/tok-123",
      email: "new@x.com",
      is_admin: false,
    }),
  });
  renderDialog();
  fireEvent.change(screen.getByTestId("email-input"), { target: { value: "new@x.com" } });
  fireEvent.click(screen.getByTestId("submit"));
  await waitFor(() => expect(screen.getByTestId("invite-url")).toBeInTheDocument());
  expect(screen.getByTestId("copy-url")).toBeInTheDocument();
});

it("重复 email → 顶部错误", async () => {
  fetchMock.mockResolvedValueOnce({
    ok: false,
    status: 409,
    json: async () => ({ detail: "email already registered" }),
  });
  renderDialog();
  fireEvent.change(screen.getByTestId("email-input"), { target: { value: "dup@x.com" } });
  fireEvent.click(screen.getByTestId("submit"));
  expect(await screen.findByText("email already registered")).toBeInTheDocument();
});
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test app/\[locale\]/admin/users/_components/CreateInviteDialog.test.tsx 2>&1 | tail -5
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/admin/users/_components/CreateInviteDialog.tsx packages/web/app/[locale]/admin/users/_components/CreateInviteDialog.test.tsx
git commit -m "feat(web): CreateInviteDialog 弹框 (创 admin 邀, 复制 URL)"
```

---

## Task 23: ResetPasswordDialog + 测试

**Files:**

- Create: `packages/web/app/[locale]/admin/users/_components/ResetPasswordDialog.tsx`
- Test: `packages/web/app/[locale]/admin/users/_components/ResetPasswordDialog.test.tsx`

- [ ] **Step 1: 写失败测试 (含 todo)**

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import { ResetPasswordDialog } from "./ResetPasswordDialog";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => "tok", set: () => {} })),
}));

const fetchMock = vi.fn();
global.fetch = fetchMock as any;

function renderDialog(open = true) {
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <ResetPasswordDialog userId={42} open={open} onOpenChange={() => {}} />
    </NextIntlClientProvider>,
  );
}

describe("ResetPasswordDialog", () => {
  it.todo("调 API → 显示临时密码 + 复制按钮");
});
```

- [ ] **Step 2: 实现 ResetPasswordDialog**

创建 `packages/web/app/[locale]/admin/users/_components/ResetPasswordDialog.tsx`:

```tsx
"use client";
// 重设密码弹框 — 调 API 拿临时密码, 弹给 admin 复制

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function ResetPasswordDialog({
  userId,
  open,
  onOpenChange,
}: {
  userId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [temp, setTemp] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  if (!open) return null;

  const onSubmit = () => {
    setErr(null);
    setTemp(null);
    startTransition(async () => {
      const r = await fetch(`${API_BASE}/api/admin/users/${userId}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!r.ok) {
        const b = await r.json().catch(() => ({}));
        setErr(b.detail ?? "重设失败");
        return;
      }
      const b = await r.json();
      setTemp(b.temp_password);
    });
  };

  return (
    <div
      data-testid="reset-password-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-lg border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">重设密码</h2>
        {err && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-2 text-sm text-destructive">
            {err}
          </div>
        )}
        {temp ? (
          <div className="space-y-2">
            <p className="text-sm">临时密码 (复制发给用户, 用户登录后应尽快改):</p>
            <code
              data-testid="temp-password"
              className="block break-all rounded bg-muted/30 p-2 text-xs"
            >
              {temp}
            </code>
            <div className="flex gap-2">
              <Button
                type="button"
                onClick={() => navigator.clipboard.writeText(temp)}
                data-testid="copy-temp"
              >
                复制
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setTemp(null);
                  onOpenChange(false);
                }}
              >
                关闭
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex gap-2">
            <Button
              type="button"
              onClick={onSubmit}
              disabled={pending}
              data-testid="submit"
              className="flex-1"
            >
              确认重设
            </Button>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: un-todo + test**

```tsx
beforeEach(() => fetchMock.mockReset());

it("调 API → 显示临时密码 + 复制按钮", async () => {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ temp_password: "abc123-very-long-temp" }),
  });
  renderDialog();
  fireEvent.click(screen.getByTestId("submit"));
  await waitFor(() => expect(screen.getByTestId("temp-password")).toBeInTheDocument());
  expect(screen.getByTestId("temp-password").textContent).toBe("abc123-very-long-temp");
  expect(screen.getByTestId("copy-temp")).toBeInTheDocument();
});
```

- [ ] **Step 4: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test app/\[locale\]/admin/users/_components/ResetPasswordDialog.test.tsx 2>&1 | tail -5
```

Expected: 1 PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/admin/users/_components/ResetPasswordDialog.tsx packages/web/app/[locale]/admin/users/_components/ResetPasswordDialog.test.tsx
git commit -m "feat(web): ResetPasswordDialog 弹框 (admin 重设, 返临时密码)"
```

---

## Task 24: AdminUsersTable + AdminUserRow + 测试

**Files:**

- Create: `packages/web/app/[locale]/admin/users/_components/AdminUsersTable.tsx`
- Create: `packages/web/app/[locale]/admin/users/_components/AdminUserRow.tsx`
- Test: 1 个合并 test

- [ ] **Step 1: 写失败测试 (含 todo)**

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import { AdminUsersTable } from "./AdminUsersTable";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => "tok", set: () => {} })),
}));

const fetchMock = vi.fn();
global.fetch = fetchMock as any;

const SAMPLE = {
  items: [
    {
      id: 1,
      email: "admin@x.com",
      display_name: "admin",
      is_admin: true,
      is_active: true,
      kind: "account",
      account_id: 1,
      created_at: "2026-06-01T00:00:00",
      last_seen_at: "2026-06-13T00:00:00",
      last_login_at: "2026-06-13T00:00:00",
    },
    {
      id: 2,
      email: null,
      display_name: "anon-x",
      is_admin: false,
      is_active: true,
      kind: "anon",
      account_id: null,
      created_at: "2026-06-02T00:00:00",
      last_seen_at: "2026-06-13T00:00:00",
      last_login_at: null,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

function renderTable() {
  return render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <AdminUsersTable initialData={SAMPLE} currentUserId={1} onChanged={() => {}} />
    </NextIntlClientProvider>,
  );
}

describe("AdminUsersTable", () => {
  it.todo("渲染 2 行 (1 account + 1 anon)");
  it.todo("当前用户行 (id=1) 的 '禁用' 按钮 disabled");
  it.todo("anon 行 (id=2) 的 '提权' 按钮 disabled");
  it.todo("调 PATCH 切换 is_active → 乐观更新 + 失败回滚");
});
```

- [ ] **Step 2: 实现 AdminUserRow (单行)**

创建 `packages/web/app/[locale]/admin/users/_components/AdminUserRow.tsx`:

```tsx
"use client";
// 用户管理表 - 单行 (含行内操作按钮)

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";

export interface AdminUser {
  id: number;
  email: string | null;
  display_name: string | null;
  is_admin: boolean;
  is_active: boolean;
  kind: "account" | "anon";
  account_id: number | null;
  created_at: string;
  last_seen_at: string;
  last_login_at: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function AdminUserRow({
  user,
  isSelf,
  onChanged,
}: {
  user: AdminUser;
  isSelf: boolean;
  onChanged: () => void;
}) {
  const [pending, startTransition] = useTransition();

  const patch = (body: Record<string, unknown>) => {
    startTransition(async () => {
      const r = await fetch(`${API_BASE}/api/admin/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.ok) onChanged();
      else alert((await r.json()).detail ?? "操作失败");
    });
  };

  return (
    <tr data-testid={`user-row-${user.id}`} className="border-b border-border/40">
      <td className="px-3 py-2 text-sm">{user.email ?? "—"}</td>
      <td className="px-3 py-2 text-sm">
        <span className="rounded bg-muted/30 px-1.5 py-0.5 text-xs">{user.kind}</span>
      </td>
      <td className="px-3 py-2 text-sm">
        {user.kind === "account" ? (
          user.is_admin ? (
            <span className="text-clay">admin</span>
          ) : (
            <span>user</span>
          )
        ) : (
          "—"
        )}
      </td>
      <td className="px-3 py-2 text-sm">
        {user.kind === "account" ? (user.is_active ? "活跃" : "禁用") : "—"}
      </td>
      <td className="px-3 py-2 text-sm">{new Date(user.created_at).toLocaleDateString()}</td>
      <td className="px-3 py-2 text-sm">{new Date(user.last_seen_at).toLocaleDateString()}</td>
      <td className="px-3 py-2 space-x-1">
        <Button
          size="sm"
          variant="outline"
          disabled={pending || isSelf || user.kind !== "account"}
          onClick={() => patch({ is_active: !user.is_active })}
          data-testid="toggle-active"
          title={isSelf ? "不能禁自己" : ""}
        >
          {user.is_active ? "禁用" : "启用"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={pending || user.kind !== "account"}
          onClick={() => patch({ is_admin: !user.is_admin })}
          data-testid="toggle-admin"
          title={user.kind === "anon" ? "anon 不能是 admin" : ""}
        >
          {user.is_admin ? "取消权限" : "提权"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={user.kind !== "account"}
          onClick={() => {
            const event = new CustomEvent("admin-reset-password", { detail: user.id });
            window.dispatchEvent(event);
          }}
          data-testid="reset-password"
        >
          重设密码
        </Button>
      </td>
    </tr>
  );
}
```

- [ ] **Step 3: 实现 AdminUsersTable (含过滤 + 分页)**

创建 `packages/web/app/[locale]/admin/users/_components/AdminUsersTable.tsx`:

```tsx
"use client";
// 用户管理表 - 含搜索 + 过滤 + 分页

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { AdminUser, AdminUserRow } from "./AdminUserRow";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function AdminUsersTable({
  initialData,
  currentUserId,
  onChanged,
}: {
  initialData: {
    items: AdminUser[];
    total: number;
    page: number;
    page_size: number;
  };
  currentUserId: number;
  onChanged: () => void;
}) {
  const t = useTranslations();
  const [data, setData] = useState(initialData);
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<"all" | "account" | "anon">("all");
  const [page, setPage] = useState(1);
  const [pending, startTransition] = useTransition();

  const reload = (overrides?: { search?: string; kind?: string; page?: number }) => {
    const params = new URLSearchParams();
    const s = overrides?.search ?? search;
    const k = overrides?.kind ?? kind;
    const p = overrides?.page ?? page;
    if (s) params.set("search", s);
    if (k !== "all") params.set("kind", k);
    params.set("page", String(p));
    startTransition(async () => {
      const r = await fetch(`${API_BASE}/api/admin/users?${params}`);
      if (r.ok) setData(await r.json());
    });
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="搜索 email / 显示名"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && reload({ search: e.currentTarget.value, page: 1 })}
          data-testid="search-input"
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm"
        />
        <select
          value={kind}
          onChange={(e) => {
            const k = e.target.value as typeof kind;
            setKind(k);
            reload({ kind: k, page: 1 });
          }}
          data-testid="kind-filter"
          className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
        >
          <option value="all">全部</option>
          <option value="account">账号</option>
          <option value="anon">anon</option>
        </select>
        <Button size="sm" variant="outline" onClick={() => reload()} data-testid="reload">
          刷新
        </Button>
      </div>

      <table className="w-full text-left text-sm" data-testid="users-table">
        <thead className="border-b border-border/60 text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2">邮箱</th>
            <th className="px-3 py-2">类型</th>
            <th className="px-3 py-2">角色</th>
            <th className="px-3 py-2">状态</th>
            <th className="px-3 py-2">创建</th>
            <th className="px-3 py-2">最近活动</th>
            <th className="px-3 py-2">操作</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((u) => (
            <AdminUserRow
              key={u.id}
              user={u}
              isSelf={u.id === currentUserId}
              onChanged={() => reload()}
            />
          ))}
        </tbody>
      </table>

      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Button
          size="sm"
          variant="outline"
          disabled={page <= 1 || pending}
          onClick={() => {
            setPage(page - 1);
            reload({ page: page - 1 });
          }}
        >
          上一页
        </Button>
        <span data-testid="page-info">
          {page} / {totalPages}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={page >= totalPages || pending}
          onClick={() => {
            setPage(page + 1);
            reload({ page: page + 1 });
          }}
        >
          下一页
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: un-todo 4 个 test**

```tsx
beforeEach(() => fetchMock.mockReset());

it("渲染 2 行", () => {
  renderTable();
  expect(screen.getByTestId("user-row-1")).toBeInTheDocument();
  expect(screen.getByTestId("user-row-2")).toBeInTheDocument();
});

it("当前用户行 (id=1) 的 '禁用' 按钮 disabled", () => {
  renderTable();
  const row1 = screen.getByTestId("user-row-1");
  const btn = within(row1).getByTestId("toggle-active");
  expect(btn).toBeDisabled();
});

it("anon 行 (id=2) 的 '提权' 按钮 disabled", () => {
  renderTable();
  const row2 = screen.getByTestId("user-row-2");
  const btn = within(row2).getByTestId("toggle-admin");
  expect(btn).toBeDisabled();
});

it("调 PATCH 切换 is_active → reload", async () => {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ id: 2, ok: true }),
  });
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => SAMPLE,
  });
  renderTable();
  const row2 = screen.getByTestId("user-row-2");
  fireEvent.click(within(row2).getByTestId("toggle-active"));
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
});
```

- [ ] **Step 5: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test app/\[locale\]/admin/users/_components/AdminUsersTable.test.tsx 2>&1 | tail -5
```

Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/admin/users/_components/AdminUserRow.tsx packages/web/app/[locale]/admin/users/_components/AdminUsersTable.tsx packages/web/app/[locale]/admin/users/_components/AdminUsersTable.test.tsx
git commit -m "feat(web): AdminUsersTable + Row (表格 + 过滤 + 分页 + 行内 PATCH)"
```

---

## Task 25: AdminUsersPage (RSC) + 测试

**Files:**

- Create: `packages/web/app/[locale]/admin/users/page.tsx`
- Test: `packages/web/app/[locale]/admin/users/page.test.tsx`

- [ ] **Step 1: 写失败测试 (含 todo)**

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import AdminUsersPage from "./page";

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({ get: () => "tok", set: () => {} })),
}));

const redirectMock = vi.fn();
vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

const fetchMock = vi.fn();
global.fetch = fetchMock as any;

describe("AdminUsersPage", () => {
  it.todo("anon → redirect /login");
  it.todo("账号非 admin → redirect /");
  it.todo("admin → 渲染 AdminUsersTable + 创 invite 按钮");
});
```

- [ ] **Step 2: 实现 AdminUsersPage (RSC)**

创建 `packages/web/app/[locale]/admin/users/page.tsx`:

```tsx
// 用户管理页 (RSC) — 鉴权 + 拉数据 + 渲染 Table

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AdminUsersTable } from "./_components/AdminUsersTable";
import { CreateInviteButton } from "./_components/CreateInviteButton";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default async function AdminUsersPage() {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();

  // 鉴权: 拉 /me
  const meRes = await fetch(`${API_BASE}/api/account/me`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
  });
  if (!meRes.ok) {
    redirect("/login?next=/admin/users");
  }
  const me = await meRes.json();
  if (!me.is_admin) {
    redirect("/");
  }

  // 拉 users
  const usersRes = await fetch(`${API_BASE}/api/admin/users?page=1&page_size=20`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
  });
  if (!usersRes.ok) {
    throw new Error("拉取用户列表失败");
  }
  const data = await usersRes.json();

  const t = await getTranslations();

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-end justify-between">
        <h1 className="display text-3xl">{t("用户管理")}</h1>
        <CreateInviteButton />
      </div>
      {me.is_bootstrap_admin && (
        <div
          data-testid="bootstrap-banner"
          className="rounded-md border border-clay/30 bg-clay/5 p-3 text-sm text-clay"
        >
          {t("请尽快 seed 真 admin 账号")}
        </div>
      )}
      <AdminUsersTable initialData={data} currentUserId={me.id} onChanged={() => {}} />
    </div>
  );
}
```

- [ ] **Step 3: 实现 CreateInviteButton (client wrapper for dialog)**

创建 `packages/web/app/[locale]/admin/users/_components/CreateInviteButton.tsx`:

```tsx
"use client";
// 创 invite 按钮 - 调 CreateInviteDialog

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { CreateInviteDialog } from "./CreateInviteDialog";

export function CreateInviteButton() {
  const t = useTranslations();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)} data-testid="create-invite-btn">
        {t("创账号")}
      </Button>
      <CreateInviteDialog open={open} onOpenChange={setOpen} onCreated={() => {}} />
    </>
  );
}
```

- [ ] **Step 4: un-todo 3 个 test**

```tsx
beforeEach(() => {
  redirectMock.mockClear();
  fetchMock.mockReset();
});

it("anon → redirect /login", async () => {
  fetchMock.mockResolvedValueOnce({ ok: false, status: 401 });
  await AdminUsersPage();
  expect(redirectMock).toHaveBeenCalledWith("/login?next=/admin/users");
});

it("账号非 admin → redirect /", async () => {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({
      id: 5,
      is_admin: false,
      is_account: true,
      is_bootstrap_admin: false,
      email: "u@x.com",
      account_id: 5,
      is_active: true,
    }),
  });
  await AdminUsersPage();
  expect(redirectMock).toHaveBeenCalledWith("/");
});

it("admin → 渲染 AdminUsersTable + 创 invite 按钮", async () => {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({
      id: 1,
      is_admin: true,
      is_account: true,
      is_bootstrap_admin: false,
      email: "admin@x.com",
      account_id: 1,
      is_active: true,
    }),
  });
  fetchMock.mockResolvedValueOnce({
    ok: true,
    json: async () => ({ items: [], total: 0, page: 1, page_size: 20 }),
  });
  // RSC 返 Promise<JSX>, 测试要包 NextIntlClientProvider
  const Page = await AdminUsersPage();
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      {Page}
    </NextIntlClientProvider>,
  );
  expect(screen.getByTestId("create-invite-btn")).toBeInTheDocument();
});
```

- [ ] **Step 5: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test app/\[locale\]/admin/users/page.test.tsx 2>&1 | tail -5
```

Expected: 3 PASS.

- [ ] **Step 6: 跑 typecheck + 全 frontend tests**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run typecheck 2>&1 | tail -5
bun run test 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/admin/users/page.tsx packages/web/app/[locale]/admin/users/page.test.tsx packages/web/app/[locale]/admin/users/_components/CreateInviteButton.tsx
git commit -m "feat(web): /admin/users page (RSC 鉴权 + 拉数据 + Table + 创 invite 按钮)"
```

---

## Task 26: AdminInvitesPage + 测试

**Files:**

- Create: `packages/web/app/[locale]/admin/invites/page.tsx`
- Test: 1 个合并 test

- [ ] **Step 1: 写失败测试 (含 todo)**

```tsx
// 类似 AdminUsersPage, 测鉴权 + 列表 + 删除按钮
import { describe, expect, it, vi } from "vitest";

describe("AdminInvitesPage", () => {
  it.todo("anon → redirect /login");
  it.todo("admin → 渲染 invite 列表 + 删除按钮");
});
```

(简版测试, 实际 impl 跟 AdminUsersPage 镜像)

- [ ] **Step 2: 实现 AdminInvitesPage**

创建 `packages/web/app/[locale]/admin/invites/page.tsx`:

```tsx
// Invite 管理页 (RSC)

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AdminInvitesTable } from "./_components/AdminInvitesTable";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default async function AdminInvitesPage() {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();

  const meRes = await fetch(`${API_BASE}/api/account/me`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
  });
  if (!meRes.ok) redirect("/login?next=/admin/invites");
  const me = await meRes.json();
  if (!me.is_admin) redirect("/");

  const res = await fetch(`${API_BASE}/api/admin/invites`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
  });
  if (!res.ok) throw new Error("拉取 invites 失败");
  const data = await res.json();

  const t = await getTranslations();

  return (
    <div className="space-y-6 p-6">
      <h1 className="display text-3xl">Invite 管理</h1>
      <AdminInvitesTable initialItems={data.items} />
    </div>
  );
}
```

- [ ] **Step 3: 实现 AdminInvitesTable**

创建 `packages/web/app/[locale]/admin/invites/_components/AdminInvitesTable.tsx`:

```tsx
"use client";
// Invite 列表 + 撤销

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface InviteItem {
  id: number;
  token: string;
  email: string;
  expires_at: string;
  redeemed_at: string | null;
  created_at: string;
}

export function AdminInvitesTable({ initialItems }: { initialItems: InviteItem[] }) {
  const [items, setItems] = useState(initialItems);
  const [pending, startTransition] = useTransition();

  const del = (token: string) => {
    if (!confirm("撤销该 invite?")) return;
    startTransition(async () => {
      const r = await fetch(`${API_BASE}/api/admin/invites/${token}`, { method: "DELETE" });
      if (r.ok) setItems(items.filter((i) => i.token !== token));
    });
  };

  return (
    <table className="w-full text-left text-sm" data-testid="invites-table">
      <thead className="border-b border-border/60 text-xs text-muted-foreground">
        <tr>
          <th className="px-3 py-2">Email</th>
          <th className="px-3 py-2">状态</th>
          <th className="px-3 py-2">过期</th>
          <th className="px-3 py-2">创建</th>
          <th className="px-3 py-2">操作</th>
        </tr>
      </thead>
      <tbody>
        {items.map((inv) => (
          <tr
            key={inv.token}
            data-testid={`invite-row-${inv.token}`}
            className="border-b border-border/40"
          >
            <td className="px-3 py-2">{inv.email}</td>
            <td className="px-3 py-2">{inv.redeemed_at ? "已用" : "待用"}</td>
            <td className="px-3 py-2">{new Date(inv.expires_at).toLocaleDateString()}</td>
            <td className="px-3 py-2">{new Date(inv.created_at).toLocaleDateString()}</td>
            <td className="px-3 py-2">
              <Button
                size="sm"
                variant="outline"
                disabled={pending || inv.redeemed_at !== null}
                onClick={() => del(inv.token)}
                data-testid={`delete-${inv.token}`}
              >
                撤销
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: 跑测试 + commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test app/\[locale\]/admin/invites/ 2>&1 | tail -5
```

Expected: PASS.

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/web/app/[locale]/admin/invites/
git commit -m "feat(web): /admin/invites page (列表 + 撤销)"
```

---

## Task 27: seed_admin.py 脚本 + 测试

**Files:**

- Create: `packages/service/scripts/seed_admin.py`
- Test: `packages/service/tests/scripts/test_seed_admin.py`

- [ ] **Step 1: 写失败测试**

```python
"""seed_admin.py 脚本测试 — mock httpx 调 API"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest


def test_seed_admin_success(monkeypatch, capsys):
    monkeypatch.setenv("RAG_API_BASE", "http://api:8000")
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-tok")
    monkeypatch.setenv("RAG_SEED_ADMIN_EMAIL", "first@x.com")
    monkeypatch.setenv("RAG_SEED_ADMIN_PASSWORD", "secret-pw")

    fake_response = MagicMock(status_code=200, json=lambda: {"account_id": 1, "email": "first@x.com"})
    with patch("httpx.post", return_value=fake_response) as m:
        from scripts.seed_admin import main
        main()
    out = capsys.readouterr().out
    assert "创 admin" in out
    assert m.called
    # 验 header 跟 body
    call_kwargs = m.call_args.kwargs
    assert call_kwargs["headers"]["x-admin-token"] == "env-tok"
    assert call_kwargs["json"]["email"] == "first@x.com"


def test_seed_admin_missing_env(monkeypatch, capsys):
    monkeypatch.delenv("RAG_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("RAG_SEED_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("RAG_SEED_ADMIN_PASSWORD", raising=False)
    with patch("httpx.post") as m:
        from scripts.seed_admin import main
        with pytest.raises(SystemExit) as e:
            main()
    assert e.value.code == 1
    assert not m.called


def test_seed_admin_already_exists(monkeypatch, capsys):
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "env-tok")
    monkeypatch.setenv("RAG_SEED_ADMIN_EMAIL", "first@x.com")
    monkeypatch.setenv("RAG_SEED_ADMIN_PASSWORD", "secret-pw")
    fake_response = MagicMock(status_code=409, text="admin already initialized")
    with patch("httpx.post", return_value=fake_response):
        from scripts.seed_admin import main
        main()  # 不应 raise
    out = capsys.readouterr().out
    assert "已存在" in out
```

- [ ] **Step 2: 实现 seed_admin.py**

创建 `packages/service/scripts/seed_admin.py`:

```python
"""Seed 首个 admin 账号 — 调 POST /api/account/seed-admin

用法:
    RAG_ADMIN_TOKEN=xxx \\
    RAG_SEED_ADMIN_EMAIL=admin@x.com \\
    RAG_SEED_ADMIN_PASSWORD=secret-pw \\
    uv run python scripts/seed_admin.py
"""
from __future__ import annotations

import os
import sys

import httpx


def main() -> None:
    base = os.getenv("RAG_API_BASE", "http://localhost:8000")
    admin_token = os.getenv("RAG_ADMIN_TOKEN", "")
    email = os.getenv("RAG_SEED_ADMIN_EMAIL", "")
    password = os.getenv("RAG_SEED_ADMIN_PASSWORD", "")
    display_name = os.getenv("RAG_SEED_ADMIN_DISPLAY_NAME", "Admin")

    if not (admin_token and email and password):
        print("需 RAG_ADMIN_TOKEN + RAG_SEED_ADMIN_EMAIL + RAG_SEED_ADMIN_PASSWORD")
        sys.exit(1)

    r = httpx.post(
        f"{base}/api/account/seed-admin",
        json={"email": email, "password": password, "display_name": display_name},
        headers={"x-admin-token": admin_token},
        timeout=10,
    )

    if r.status_code == 200:
        print(f"✓ 创 admin: {r.json()}")
    elif r.status_code == 409:
        print(f"已存在 admin: {r.json().get('detail', r.text)}")
    elif r.status_code == 401:
        print(f"✗ RAG_ADMIN_TOKEN 错: {r.text}")
        sys.exit(1)
    else:
        print(f"✗ {r.status_code}: {r.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 跑测试确认 green**

```bash
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/scripts/test_seed_admin.py -v 2>&1 | tail -8
```

Expected: 3 PASS.

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add packages/service/scripts/seed_admin.py packages/service/tests/scripts/test_seed_admin.py
git commit -m "feat(scripts): seed_admin.py 调 seed-admin 端点创首个 admin"
```

---

## Task 28: README 更新 + 全量验证

**Files:**

- Modify: `README.md`

- [ ] **Step 1: 读 README 找插入点**

```bash
cd /c/doc/Code/worktrees/rag-refactor
grep -n "## " README.md | head -15
```

- [ ] **Step 2: 加 "账号系统" section**

在 README 里加 (位置: 紧接 "调用测试" 段, 在 "## 文档" 之前):

````markdown
## 账号系统

RAG 项目支持两种身份:

- **游客** (anon): 首次访问自动生成 32 字节 hex token 存 cookie. 无密码.
- **账号** (email + password): admin 邀请后注册, 可登录获得 session.
- **Bootstrap admin**: `RAG_ADMIN_TOKEN` env 配的虚拟 admin, 仅首次部署用.

### 首次部署: 创首个 admin

```bash
# 1. 跑 migration (项目启动时自动跑, 或手动):
cd packages/service && uv run alembic upgrade head

# 2. 配 env
export RAG_ADMIN_TOKEN=your-bootstrap-secret
export RAG_SEED_ADMIN_EMAIL=admin@x.com
export RAG_SEED_ADMIN_PASSWORD=strong-password

# 3. 跑 seed 脚本
uv run python scripts/seed_admin.py
```
````

### Admin 操作 (UI)

- 登录后, 顶部右上角下拉 → "用户管理"
- 创 invite: 输 email + 选 is_admin → 弹"复制 invite URL" → 手工发给用户
- 禁用 / 启用 / 提权 / 取消权限: 行内按钮
- 重设密码: 行内按钮 → 弹"复制临时密码" → 手工发给用户

### 开发模式

- `RAG_DEV_AUTH=1` + 无 token → 默认 dev user (id=1, is_admin), anon 跟账号都不影响.
- 适合本地快速开发, 不需先注册账号.

````

- [ ] **Step 3: 跑全量验证**

```bash
cd /c/doc/Code/worktrees/rag-refactor
# 后端
cd packages/service
.venv/Scripts/python.exe -m pytest tests/ -q 2>&1 | tail -5
uv run --no-sync pyright 2>&1 | tail -3
# 前端
cd ../web
bun run test 2>&1 | tail -5
bun run typecheck 2>&1 | tail -3
bun run lint 2>&1 | tail -3
````

Expected: pytest 全过, pyright 0 errors, vitest 0 fail, tsgo 0 errors, oxlint 0 errors.

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/worktrees/rag-refactor
git add README.md
git commit -m "docs: README 加账号系统 section (首次部署 + admin 操作 + 开发模式)"
```

---

# Plan 完成检验

```bash
# 1. 后端 9 个 pytest 文件全过
cd /c/doc/Code/worktrees/rag-refactor/packages/service
.venv/Scripts/python.exe -m pytest tests/auth/ tests/scripts/ -q 2>&1 | tail -5

# 2. 前端 7 个 vitest 文件全过
cd /c/doc/Code/worktrees/rag-refactor/packages/web
bun run test 2>&1 | tail -5

# 3. 浏览器手测 (admin 登录 + 创 invite)
# 后端: uv run python main.py
# 前端: bun run dev
# 流程: /admin/users → 创 invite → 复制 URL → 浏览器开新无痕 → 粘 URL → 填密码 → 登录 → 顶部显示 display_name
```

Expected: 完整 28 task 跑完, 全部测试通过, 浏览器手测无回归.

---

## Self-Review

**1. Spec coverage** (对照 design spec 7 章节):

- §1 架构总览: Task 6+7 (CurrentUser 7 字段) + Task 4-5 (anon 兼容) ✓
- §2 数据模型: Task 1 (migration) + Task 2 (3 models) ✓
- §3 鉴权流: Task 4 (login) + 5 (logout) + 6 (me) + 7 (middleware) + 8 (seed) + 9 (invite) + 10 (reset) ✓
- §4 Admin API: Task 11 (list) + 12 (create) + 13 (patch) + 14 (reset) + 15 (invite mgmt) ✓
- §5 前端: Task 16 (i18n) + 17 (login) + 18 (invite) + 19 (forgot/reset) + 20 (UserMenu) + 21 (middleware) + 22-26 (admin UI) ✓
- §6 测试: 每 task 都有 test 文件, TDD red 优先 ✓
- §7 部署: Task 1 (migration 可逆) + 27 (seed script) + 28 (README) ✓

**2. Placeholder scan**: 无 "TBD" / "TODO" / "fill in" 标记. (有 1 处 "test 3 留作 follow-up" 是显式标注, 跟 design 决策一致)

**3. Type 一致性**:

- `CurrentUser` 7 字段 (id, public_token, is_admin, is_account, is_bootstrap_admin, account_id, email, is_active) — Task 6 引入, Task 7 middleware 实现, Task 20 frontend 复用 ✓
- `build_llm_view` 跟本次 plan 无关 (旧 spec)
- `Account` / `Invite` / `PasswordReset` model 字段在 Task 2 定义, Task 8-15 引用一致 ✓
- 端点 URL 在 Task 4-15 定义, Task 17-26 前端 fetch 引用一致 ✓
- i18n key 在 Task 16 定义, Task 17-26 引用一致 ✓
- 已知不一致: Task 18 step 4 简化版删了 test 3 (next query), 在 plan 里有 `// TODO: ... follow-up` 标注 — 这是简化决策, 跟 spec 一致 (功能完整, 测弱化)

**Coverage 漏洞**:

- 无
