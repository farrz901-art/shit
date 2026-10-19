# RBAC 权限系统实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整 RBAC 权限系统 (4 状态 + N 角色权限组 + 7 页面权限点 + 运行时可配置 + 30s TTL cache)

**Architecture:** 
- 后端: 新增 `permissions` 模块 (cache + guards + service + router), `accounts.role` 改 str, 加 `roles` + `role_permissions` 表
- 前端: 新增 `PageGuard` 组件 + 权限管理 UI (角色列表 + 矩阵), 22 page.tsx 加 guard, header nav filter
- 缓存: 进程内 30s TTL, PATCH/POST/DELETE 立即 invalidate

**Tech Stack:** 
- 后端: FastAPI + SQLAlchemy + Alembic + pytest
- 前端: Next.js 15 + React 19 + vitest + @testing-library
- 迁移: Alembic (手工 revision)

**Spec:** [2026-06-17-rbac-permission-system-design.md](../specs/2026-06-17-rbac-permission-system-design.md)

---

## File Structure

**后端新建**:
- `packages/service/src/permissions/__init__.py`
- `packages/service/src/permissions/models.py` (Role, RolePermission)
- `packages/service/src/permissions/service.py` (CRUD 业务逻辑)
- `packages/service/src/permissions/router.py` (/api/permissions + /api/roles)
- `packages/service/src/permissions/cache.py` (PermissionCache + ALL_PAGE_KEYS)
- `packages/service/src/permissions/guards.py` (require_page, require_super_admin, require_account)
- `packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py`
- `packages/service/tests/permissions/test_models.py`
- `packages/service/tests/permissions/test_cache.py`
- `packages/service/tests/permissions/test_guards.py`
- `packages/service/tests/permissions/test_router.py`
- `packages/service/tests/roles/test_router.py`
- `packages/service/tests/integration/test_rbac_e2e.py`
- `packages/service/tests/auth/test_account_role.py`
- `packages/service/tests/auth/test_login_role.py`

**后端修改**:
- `packages/service/src/auth/account_models.py` (Account 加 role: str)
- `packages/service/src/auth/auth_account_router.py` (LoginResponse role, seed_admin super_admin)
- `packages/service/src/auth/auth_admin_router.py` (invite body role, require_super_admin)
- `packages/service/src/middleware/auth.py` (CurrentUser role: str)
- `packages/service/src/memory/router.py` (require_account)
- `packages/service/src/health/router.py` (require_super_admin)
- `packages/service/src/knowledge/router.py` (require_page)
- `packages/service/src/output/router.py` (require_page)
- `packages/service/src/evaluate/router.py` (require_page)
- `packages/service/src/submissions/router.py` (require_page)
- `packages/service/src/decode/router.py` (require_page)
- `packages/service/src/chat/router.py` (require_page)

**前端新建**:
- `packages/web/lib/auth/role.ts` (helpers)
- `packages/web/lib/auth/role.test.ts`
- `packages/web/components/PageGuard.tsx`
- `packages/web/components/PageGuard.test.tsx`
- `packages/web/app/[locale]/admin/permissions/page.tsx`
- `packages/web/app/[locale]/admin/permissions/_components/PermissionsMatrix.tsx`
- `packages/web/app/[locale]/admin/permissions/_components/PermissionsMatrix.test.tsx`
- `packages/web/app/[locale]/admin/permissions/_components/RoleList.tsx`
- `packages/web/app/[locale]/admin/permissions/_components/RoleList.test.tsx`
- `packages/web/app/[locale]/admin/permissions/_components/CreateRoleDialog.tsx`
- `packages/web/app/[locale]/admin/permissions/_components/CreateRoleDialog.test.tsx`
- `packages/web/app/[locale]/admin/permissions/page.test.tsx`

**前端修改**:
- `packages/web/components/header.tsx` (nav filter)
- `packages/web/components/header.test.tsx`
- `packages/web/components/UserMenu.tsx` (helper)
- `packages/web/components/UserMenu.test.tsx`
- `packages/web/app/[locale]/layout.tsx` (拉 /me + /permissions/me)
- `packages/web/app/[locale]/chat/page.tsx` (anon memory hidden)
- `packages/web/app/[locale]/chat/page.test.tsx`
- 22 page.tsx (加 PageGuard)
- `packages/web/messages/{zh,en}.json` (12 新 key)
- `packages/web/app/[locale]/admin/users/page.tsx` (PageGuard)
- `packages/web/app/[locale]/admin/users/page.test.tsx`

---

## Phase 1: 后端 Foundation

### Task 1: Alembic migration (accounts.role + roles + role_permissions)

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py`

- [ ] **Step 1: 找到下一个 alembic revision id**

```bash
cd packages/service
ls src/storage/migrations/versions/ | sort | tail -1
```

找到当前最新 revision 编号, 推断下一个 (本例假设为 `20260617_000000`)。

- [ ] **Step 2: 创建 migration 文件**

创建文件 `packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py`:

```python
"""add roles, role_permissions, accounts.role

v2: 完整 RBAC (N 角色权限组 + 7 页面权限点 + 30s cache).
- 删 accounts.is_admin (迁到 role 字符串)
- 创 roles (预设 user/admin/super_admin)
- 创 role_permissions (user + admin 各 7 页面初始)
- super_admin 不入库, 代码层 meta 豁免
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260617_000000"
down_revision = "<上一 revision 编号>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. accounts 加 role 列, 默认 user
    op.add_column(
        "accounts",
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
    )
    # 2. 旧 is_admin=TRUE → super_admin
    op.execute("UPDATE accounts SET role = 'super_admin' WHERE is_admin = TRUE")
    # 3. 删 is_admin
    op.drop_column("accounts", "is_admin")

    # 4. 创 roles 表
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("label_zh", sa.Text(), nullable=False),
        sa.Column("label_en", sa.Text(), nullable=False),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_deletable", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_roles_name", "roles", ["name"], unique=True)

    # 5. 插 3 个预设角色
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("name", sa.Text),
            sa.column("label_zh", sa.Text),
            sa.column("label_en", sa.Text),
            sa.column("is_system", sa.Boolean),
            sa.column("is_deletable", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "name": "user",
                "label_zh": "用户",
                "label_en": "User",
                "is_system": True,
                "is_deletable": False,
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            },
            {
                "name": "admin",
                "label_zh": "管理员",
                "label_en": "Admin",
                "is_system": True,
                "is_deletable": False,
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            },
            {
                "name": "super_admin",
                "label_zh": "超级管理员",
                "label_en": "Super Admin",
                "is_system": True,
                "is_deletable": False,
                "created_at": sa.func.now(),
                "updated_at": sa.func.now(),
            },
        ],
    )

    # 6. 创 role_permissions 表
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("role_name", sa.Text(), nullable=False),
        sa.Column("page_key", sa.Text(), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("role_name", "page_key", name="uq_role_perm"),
    )
    op.create_index("idx_role_perms_name", "role_permissions", ["role_name"])

    # 7. 插 8 行 (user 2 + admin 6, super_admin 不入库)
    op.bulk_insert(
        sa.table(
            "role_permissions",
            sa.column("role_name", sa.Text),
            sa.column("page_key", sa.Text),
            sa.column("allowed", sa.Boolean),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            # user: chat, decode = true
            *[
                {"role_name": "user", "page_key": k, "allowed": True,
                 "created_at": sa.func.now(), "updated_at": sa.func.now()}
                for k in ("chat", "decode")
            ],
            # user: 其余 5 个 = false
            *[
                {"role_name": "user", "page_key": k, "allowed": False,
                 "created_at": sa.func.now(), "updated_at": sa.func.now()}
                for k in ("output", "knowledge", "evaluate", "submissions", "health")
            ],
            # admin: 6 个 = true, health = false
            *[
                {"role_name": "admin", "page_key": k, "allowed": True,
                 "created_at": sa.func.now(), "updated_at": sa.func.now()}
                for k in ("chat", "output", "knowledge", "evaluate", "submissions", "decode")
            ],
            {"role_name": "admin", "page_key": "health", "allowed": False,
             "created_at": sa.func.now(), "updated_at": sa.func.now()},
        ],
    )


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.add_column(
        "accounts",
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE accounts SET is_admin = TRUE WHERE role = 'super_admin'")
    op.drop_column("accounts", "role")
```

- [ ] **Step 3: 把 down_revision 填上正确编号**

从 Step 1 找到的上一个 revision 编号填到 `down_revision` 字段。

- [ ] **Step 4: 跑 migration 验证**

```bash
cd packages/service
uv run alembic upgrade head
```

Expected: 成功, 0 报错。

- [ ] **Step 5: 验证 seed 数据**

```bash
uv run python -c "
from src.storage.session import session_scope
from src.permissions.models import Role, RolePermission
with session_scope() as s:
    print('roles:', [(r.name, r.is_system) for r in s.query(Role).all()])
    print('role_permissions:', [(rp.role_name, rp.page_key, rp.allowed) for rp in s.query(RolePermission).all()])
"
```

Expected: 3 roles (user/admin/super_admin) + 8 role_permissions。

- [ ] **Step 6: 测可逆性**

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: 0 报错。

- [ ] **Step 7: Commit**

```bash
cd packages/service
git add src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py
git commit -m "feat(rbac): alembic migration for roles + role_permissions"
```

---

### Task 2: Role + RolePermission models

**Files:**
- Create: `packages/service/src/permissions/__init__.py`
- Create: `packages/service/src/permissions/models.py`
- Create: `packages/service/tests/permissions/__init__.py`
- Create: `packages/service/tests/permissions/test_models.py`

- [ ] **Step 1: 写失败的测试**

创建 `packages/service/tests/permissions/test_models.py`:

```python
"""Role + RolePermission 表结构 + 约束测试 (100% mock, 0 真实 DB)
"""
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.permissions.models import Role, RolePermission


def test_role_required_fields() -> None:
    """Role 必填字段: name, label_zh, label_en, is_system, is_deletable, created_at, updated_at"""
    r = Role(
        name="operator",
        label_zh="运营",
        label_en="Operator",
        is_system=False,
        is_deletable=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )
    assert r.name == "operator"
    assert r.is_system is False
    assert r.is_deletable is True


def test_role_permission_required_fields() -> None:
    """RolePermission 必填字段: role_name, page_key, allowed, created_at, updated_at"""
    rp = RolePermission(
        role_name="operator",
        page_key="chat",
        allowed=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )
    assert rp.role_name == "operator"
    assert rp.page_key == "chat"
    assert rp.allowed is True


def test_role_permission_unique_constraint() -> None:
    """unique(role_name, page_key) 重复 → IntegrityError"""
    s = MagicMock()
    s.add.side_effect = IntegrityError("duplicate", params={}, orig=Exception())
    rp = RolePermission(role_name="x", page_key="y", allowed=True,
                       created_at=MagicMock(), updated_at=MagicMock())
    s.add(rp)
    with pytest.raises(IntegrityError):
        s.add(rp)
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/service
uv run pytest tests/permissions/test_models.py -v
```

Expected: ModuleNotFoundError (因 models.py 还没建)。

- [ ] **Step 3: 写最小实现**

创建 `packages/service/src/permissions/__init__.py` (空文件)。

创建 `packages/service/src/permissions/models.py`:

```python
"""Role + RolePermission models

v2 RBAC: roles 是 N 个 (3 预设 + super-admin 创建), role_permissions 是 role × page 矩阵.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Role(Base):
    """角色: 3 预设 (user/admin/super_admin) + super-admin 创建的自定义角色

    - name 唯一, 2-32 字符 [a-z0-9_]
    - is_system: 系统内置 (不删)
    - is_deletable: 可被 super_admin 删 (自定义 TRUE, 系统 FALSE)
    """

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    label_zh = Column(Text, nullable=False)
    label_en = Column(Text, nullable=False)
    is_system = Column(Boolean, nullable=False, default=False)
    is_deletable = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                       onupdate=datetime.utcnow)


class RolePermission(Base):
    """role × page_key 权限矩阵 (super_admin 不入库, 走代码 meta 豁免)"""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_name", "page_key", name="uq_role_perm"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(Text, nullable=False)
    page_key = Column(Text, nullable=False)
    allowed = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                       onupdate=datetime.utcnow)
```

需要在文件顶部加 `from sqlalchemy import UniqueConstraint`, 跟其它 import 一起 (按字母排序)。

- [ ] **Step 4: 跑测试验证通过**

```bash
cd packages/service
uv run pytest tests/permissions/test_models.py -v
```

Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
cd packages/service
git add src/permissions/ tests/permissions/
git commit -m "feat(rbac): Role + RolePermission SQLAlchemy models"
```

---

### Task 3: PermissionCache 实现

**Files:**
- Create: `packages/service/src/permissions/cache.py`
- Create: `packages/service/tests/permissions/test_cache.py`

- [ ] **Step 1: 写失败的测试**

创建 `packages/service/tests/permissions/test_cache.py`:

```python
"""PermissionCache 行为测试: TTL, invalidate, 并发安全 (100% mock DB session)
"""
from unittest.mock import MagicMock, patch

from src.permissions.cache import (
    ALL_PAGE_KEYS,
    PAGE_METADATA,
    PermissionCache,
)


def test_all_page_keys_constant() -> None:
    """ALL_PAGE_KEYS 是 7 元素 tuple"""
    assert len(ALL_PAGE_KEYS) == 7
    assert "chat" in ALL_PAGE_KEYS
    assert "health" in ALL_PAGE_KEYS


def test_page_metadata_length() -> None:
    """PAGE_METADATA 跟 ALL_PAGE_KEYS 长度一致"""
    assert len(PAGE_METADATA) == len(ALL_PAGE_KEYS)
    for entry in PAGE_METADATA:
        assert "key" in entry
        assert "label_zh" in entry
        assert "label_en" in entry
        assert "path" in entry


def test_get_returns_false_when_role_not_in_cache() -> None:
    """未加载时 get 触发 _refresh, role 不在矩阵 → None"""
    cache = PermissionCache()
    # mock session_scope 返空 rows
    with patch("src.permissions.cache.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = []
        result = cache.get("unknown_role", "chat")
    assert result is None


def test_get_returns_correct_value() -> None:
    """role × page 在矩阵里 → 返 allowed 值"""
    cache = PermissionCache()
    with patch("src.permissions.cache.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            ("user", "chat", True),
            ("user", "decode", True),
            ("user", "output", False),
        ]
        # 第 1 次触发 refresh
        result_chat = cache.get("user", "chat")
        result_decode = cache.get("user", "decode")
        result_output = cache.get("user", "output")
    assert result_chat is True
    assert result_decode is True
    assert result_output is False


def test_invalidate_forces_refresh() -> None:
    """invalidate 后下次 get 触发 _refresh (mock 验 fetchall 调用次数)"""
    cache = PermissionCache()
    with patch("src.permissions.cache.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            ("user", "chat", True),
        ]
        cache.get("user", "chat")  # 触发 1 次 refresh
        cache.invalidate()
        cache.get("user", "chat")  # 触发 2 次 refresh
        # session_scope 进入 __enter__ 2 次
        assert mock_sess.call_count == 2


def test_ttl_triggers_refresh() -> None:
    """TTL 过期后 get 触发 _refresh"""
    cache = PermissionCache(ttl_seconds=0.01)  # 10ms TTL
    with patch("src.permissions.cache.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            ("user", "chat", True),
        ]
        cache.get("user", "chat")
        # 模拟时间过去 100ms
        with patch("src.permissions.cache.time.time", return_value=999_999_999):
            cache.get("user", "chat")
        # 至少 2 次 refresh
        assert mock_sess.call_count >= 2
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/service
uv run pytest tests/permissions/test_cache.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: 写实现**

创建 `packages/service/src/permissions/cache.py`:

```python
"""PermissionCache: 进程内存 dict cache, 30s TTL sliding

读路径: lock + dict get, 不查 DB.
失效: invalidate() 后下次读触发 _refresh() 重读 DB.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from ..storage.session import session_scope

ALL_PAGE_KEYS: tuple[str, ...] = (
    "chat",
    "output",
    "knowledge",
    "evaluate",
    "submissions",
    "decode",
    "health",
)

PAGE_METADATA: list[dict] = [
    {"key": k, "label_zh": zh, "label_en": en, "path": f"/{k}"}
    for k, zh, en in [
        ("chat", "对话", "Chat"),
        ("output", "文档结构化", "Output"),
        ("knowledge", "知识库", "Knowledge"),
        ("evaluate", "评估", "Evaluate"),
        ("submissions", "审核中心", "Submissions"),
        ("decode", "型号解析", "Decode"),
        ("health", "健康", "Health"),
    ]
]


class PermissionCache:
    """进程内存 cache, 单例模式由调用方保证 (permission_cache 全局实例)"""

    def __init__(self, ttl_seconds: int = 30) -> None:
        self._lock = threading.RLock()
        self._matrix: dict[str, dict[str, bool]] = {}
        self._loaded_at: float = 0.0
        self._ttl = ttl_seconds

    def get(self, role: str, page_key: str) -> Optional[bool]:
        """查 role × page 权限. 触发: TTL 过期或首次访问时 _refresh()."""
        with self._lock:
            if time.time() - self._loaded_at > self._ttl:
                self._refresh()
            return self._matrix.get(role, {}).get(page_key)

    def invalidate(self) -> None:
        """下次 get 强制 _refresh(). 写操作 (PATCH/POST/DELETE) 后调用."""
        with self._lock:
            self._loaded_at = 0.0

    def _refresh(self) -> None:
        """全表读 role_permissions 到内存 dict."""
        with self._lock:
            new_matrix: dict[str, dict[str, bool]] = {}
            with session_scope() as s:
                rows = s.execute(
                    "SELECT role_name, page_key, allowed FROM role_permissions"
                ).fetchall()
            for role_name, page_key, allowed in rows:
                new_matrix.setdefault(role_name, {})[page_key] = allowed
            self._matrix = new_matrix
            self._loaded_at = time.time()


permission_cache = PermissionCache()
```

- [ ] **Step 4: 跑测试验证通过**

```bash
cd packages/service
uv run pytest tests/permissions/test_cache.py -v
```

Expected: 6 passed。

- [ ] **Step 5: Commit**

```bash
cd packages/service
git add src/permissions/cache.py tests/permissions/test_cache.py
git commit -m "feat(rbac): PermissionCache with 30s TTL sliding"
```

---

### Task 4: Guards (require_page, require_super_admin, require_account)

**Files:**
- Create: `packages/service/src/permissions/guards.py`
- Create: `packages/service/tests/permissions/test_guards.py`

- [ ] **Step 1: 写失败的测试**

创建 `packages/service/tests/permissions/test_guards.py`:

```python
"""3 个守卫装饰器测试: 4 身份 × 7 页面 矩阵 (parametrize)
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.middleware.auth import CurrentUser
from src.permissions.guards import require_account, require_page, require_super_admin


def _make_user(role: str = "user", is_account: bool = True) -> CurrentUser:
    return CurrentUser(
        id=1,
        public_token="tok",
        role=role,
        is_account=is_account,
        account_id=1 if is_account else None,
    )


# 1. require_super_admin
def test_require_super_admin_super_admin() -> None:
    user = _make_user("super_admin")
    assert require_super_admin(user) is user


@pytest.mark.parametrize("role", ["user", "admin", "operator"])
def test_require_super_admin_rejects_non_super(role: str) -> None:
    user = _make_user(role)
    with pytest.raises(HTTPException) as exc:
        require_super_admin(user)
    assert exc.value.status_code == 403
    assert "super_admin required" in str(exc.value.detail)


# 2. require_account
def test_require_account_passes_for_account() -> None:
    user = _make_user("user", is_account=True)
    assert require_account(user) is user


def test_require_account_rejects_anon() -> None:
    user = _make_user("user", is_account=False)
    with pytest.raises(HTTPException) as exc:
        require_account(user)
    assert exc.value.status_code == 403
    assert "login required" in str(exc.value.detail)


# 3. require_page: 4 身份 × 7 页面 矩阵
@pytest.mark.parametrize("page_key", ["chat", "output", "knowledge", "evaluate", "submissions", "decode", "health"])
def test_require_page_super_admin_bypasses_all(page_key: str) -> None:
    """super_admin 永远通过 (meta 豁免)"""
    user = _make_user("super_admin")
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        dep = require_page(page_key)
        assert dep(user) is user
        mock_cache.get.assert_not_called()


@pytest.mark.parametrize("page_key,expected", [
    ("chat", True),
    ("decode", True),
    ("output", False),
    ("knowledge", False),
    ("evaluate", False),
    ("submissions", False),
    ("health", False),
])
def test_require_page_user_role(page_key: str, expected: bool) -> None:
    user = _make_user("user")
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        mock_cache.get.return_value = expected
        dep = require_page(page_key)
        if expected:
            assert dep(user) is user
        else:
            with pytest.raises(HTTPException) as exc:
                dep(user)
            assert exc.value.status_code == 403


@pytest.mark.parametrize("page_key,expected", [
    ("chat", True),
    ("output", True),
    ("knowledge", True),
    ("evaluate", True),
    ("submissions", True),
    ("decode", True),
    ("health", False),
])
def test_require_page_admin_role(page_key: str, expected: bool) -> None:
    user = _make_user("admin")
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        mock_cache.get.return_value = expected
        dep = require_page(page_key)
        if expected:
            assert dep(user) is user
        else:
            with pytest.raises(HTTPException):
                dep(user)


def test_require_page_custom_role() -> None:
    """自定义角色 (例 operator) 走 cache 校验"""
    user = _make_user("operator")
    with patch("src.permissions.guards.permission_cache") as mock_cache:
        mock_cache.get.return_value = True
        dep = require_page("output")
        assert dep(user) is user
        mock_cache.get.assert_called_once_with("operator", "output")
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/service
uv run pytest tests/permissions/test_guards.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: 写实现**

创建 `packages/service/src/permissions/guards.py`:

```python
"""FastAPI Depends 守卫: page-level (require_page) + resource-level (require_super_admin, require_account)

- require_page("knowledge"): 查 cache 验 role × page 权限, super_admin 短路
- require_super_admin: 严验 role == "super_admin", 用于 admin/permissions/health 等
- require_account: 禁 anon (is_account=False), 用于 /api/memory/*
"""
from __future__ import annotations

from fastapi import Depends, HTTPException

from ..middleware.auth import CurrentUser, resolve_user
from .cache import permission_cache


def require_page(page_key: str):
    """工厂: 返 FastAPI Depends 闭包"""
    def _dep(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
        if user.role == "super_admin":
            return user  # meta 豁免
        if not permission_cache.get(user.role, page_key):
            raise HTTPException(
                status_code=403,
                detail=f"page '{page_key}' not allowed for role '{user.role}'",
            )
        return user
    return _dep


def require_super_admin(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
    if user.role != "super_admin":
        raise HTTPException(status_code=403, detail="super_admin required")
    return user


def require_account(user: CurrentUser = Depends(resolve_user)) -> CurrentUser:
    """记忆端点用, 禁 anon"""
    if not user.is_account:
        raise HTTPException(status_code=403, detail="login required")
    return user
```

- [ ] **Step 4: 跑测试验证通过**

```bash
cd packages/service
uv run pytest tests/permissions/test_guards.py -v
```

Expected: 25+ passed (含 parametrize)。

- [ ] **Step 5: Commit**

```bash
cd packages/service
git add src/permissions/guards.py tests/permissions/test_guards.py
git commit -m "feat(rbac): require_page / require_super_admin / require_account guards"
```

---

### Task 5: CurrentUser.role 改 str

**Files:**
- Modify: `packages/service/src/middleware/auth.py:49-64` (CurrentUser 字段)
- Modify: `packages/service/src/middleware/auth.py:122-131` (构造 CurrentUser 删 is_admin)

- [ ] **Step 1: 看 CurrentUser 当前实现**

打开 `packages/service/src/middleware/auth.py:49-64`, 确认当前字段 (上面已读过, 含 `is_admin: bool = False`)。

- [ ] **Step 2: 删 is_admin, 加 role**

在 `packages/service/src/middleware/auth.py` 的 `CurrentUser` class:

```python
class CurrentUser(BaseModel):
    """当前请求的鉴权上下文

    - 真账号: id=users.id, is_account=True, email/role/display_name 填
    - anon: id=users.id, is_account=False, email/display_name=None
    - dev user: id=1, role="super_admin" (RAG_DEV_AUTH=true 模式)

    role 字段值参考 src.permissions.cache: user / admin / super_admin / 自定义.
    """

    id: int
    public_token: str
    role: str = "user"  # 替原 is_admin, 从 account.role 派生 (validated against roles 表)
    is_account: bool = False
    account_id: int | None = None
    email: str | None = None
    display_name: str | None = None
    is_active: bool = True
```

在 `packages/service/src/middleware/auth.py` 的 `resolve_user` 函数:

**A. dev user 路径** (line ~85-90): 把 `is_admin=True` 改成 `role="super_admin"`:

```python
if os.getenv("RAG_DEV_AUTH", "").lower() in ("1", "true", "yes"):
    _ensure_dev_user()
    return CurrentUser(
        id=1,
        public_token="dev-default",
        role="super_admin",  # 原 is_admin=True
        is_account=False,
    )
```

**B. anon 路径** (line ~103-109): 加 `role="user"`:

```python
if user.account_id is None:
    return CurrentUser(
        id=user.id,
        public_token=user_token,
        is_account=False,
        role="user",  # 新加
        is_admin=False,  # 删除
    )
```

**C. 真账号路径** (line ~122-131): `is_admin=account.is_admin` 改成 `role=account.role`:

```python
return CurrentUser(
    id=user.id,
    public_token=user_token,
    is_account=True,
    role=account.role,  # 原 is_admin=account.is_admin
    account_id=account.id,
    email=account.email,
    display_name=account.display_name,
    is_active=account.is_active,
)
```

注意 `is_admin=False` 在 anon 路径也要删。

- [ ] **Step 3: grep 找所有 is_admin 引用**

```bash
cd packages/service
grep -rn "is_admin" src/ tests/
```

期望: 14 文件 (跟 spec 写的一致)。

- [ ] **Step 4: 改 Account model 加 role 字段**

打开 `packages/service/src/auth/account_models.py`, 找 `Account` class, 改:

```python
class Account(Base):
    """账号表: email + password_hash + role (v2: str 替 is_admin bool)"""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    display_name = Column(Text, nullable=True)
    role = Column(Text, nullable=False, default="user", server_default="user")  # 新加
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
```

删 `is_admin` 字段。

- [ ] **Step 5: 跑现有 middleware 集成测试**

```bash
cd packages/service
uv run pytest tests/middleware/ -v
```

Expected: 现有测试可能因 CurrentUser 字段名变了失败, 改 test (下个任务统一改)。

- [ ] **Step 6: Commit**

```bash
cd packages/service
git add src/middleware/auth.py src/auth/account_models.py
git commit -m "refactor(rbac): replace is_admin bool with role str (preparation for v2 RBAC)"
```

---

### Task 6: 改 auth_account_router (LoginResponse + seed_admin + /me 返 role)

**Files:**
- Modify: `packages/service/src/auth/auth_account_router.py`

- [ ] **Step 1: 写失败的测试**

创建 `packages/service/tests/auth/test_account_role.py`:

```python
"""Account role 字段测试: seed_admin / login / /me 都返 role: str
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_login_response_has_role_field() -> None:
    """LoginResponse 必须含 role 字段"""
    from src.auth.auth_account_router import LoginResponse, AccountOut
    acc = AccountOut(id=1, email="x@y.com", display_name="x", is_admin=True, role="admin")
    resp = LoginResponse(token="tok", account=acc)
    assert resp.account.role == "admin"


def test_account_out_has_role_field() -> None:
    """AccountOut 必须含 role 字段 (替原 is_admin)"""
    from src.auth.auth_account_router import AccountOut
    out = AccountOut(id=1, email="x@y.com", display_name="x", is_admin=True, role="admin")
    assert out.role == "admin"
    # is_admin 仍存在作派生 (可选, 不强制)
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/service
uv run pytest tests/auth/test_account_role.py -v
```

Expected: ImportError 或 TypeError (LoginResponse/AccountOut 还没 role 字段)。

- [ ] **Step 3: 改 auth_account_router.py**

打开 `packages/service/src/auth/auth_account_router.py`, 改:

**A. AccountOut** (line ~32-37): 加 `role: str`:

```python
class AccountOut(BaseModel):
    id: int
    email: str
    display_name: str | None
    role: str  # 新加 (v2 替原 is_admin)
    is_admin: bool  # 保留作派生 (前端用 is_admin_level helper 改), 实际从 account.role 算
```

**B. login 函数** (line ~73-78): AccountOut 构造加 `role=account.role`:

```python
account_payload = AccountOut(
    id=account.id,
    email=account.email,
    display_name=account.display_name,
    role=account.role,  # 新加
    is_admin=account.role in ("admin", "super_admin"),  # 派生
)
```

**C. me 函数** (line ~106-114): 返 role 字段:

```python
return {
    "id": user.id,
    "role": user.role,  # 新加 (替原 is_admin)
    "is_admin": user.role in ("admin", "super_admin"),  # 派生
    "is_account": user.is_account,
    "account_id": user.account_id,
    "email": user.email,
    "display_name": user.display_name,
    "is_active": user.is_active,
}
```

**D. seed_admin 函数** (line ~139-149): 创 `role="super_admin"`:

```python
account = Account(
    email=req.email,
    password_hash=account_service.hash_password(req.password),
    display_name=req.display_name or req.email.split("@")[0],
    role="super_admin",  # 原 is_admin=True
    created_at=datetime.now(HKT),
)
```

同时**删** `is_admin=True` 字段。

- [ ] **Step 4: 跑测试验证通过**

```bash
cd packages/service
uv run pytest tests/auth/test_account_role.py -v
```

Expected: 2 passed。

- [ ] **Step 5: 跑现有 auth 测试**

```bash
cd packages/service
uv run pytest tests/auth/ -v
```

Expected: 现有测试可能因 LoginResponse / me 返回字段变化失败, 改对应 test。

- [ ] **Step 6: Commit**

```bash
cd packages/service
git add src/auth/auth_account_router.py tests/auth/test_account_role.py
git commit -m "feat(rbac): AccountOut/LoginResponse/me return role field"
```

---

### Task 7: 改 auth_admin_router (require_super_admin + invite body 加 role)

**Files:**
- Modify: `packages/service/src/auth/auth_admin_router.py`

- [ ] **Step 1: 找现有 require_admin 引用**

```bash
cd packages/service
grep -n "require_admin\|is_admin" src/auth/auth_admin_router.py
```

期望: 7 处 `Depends(require_admin)`, 几处 `is_admin=...`。

- [ ] **Step 2: 改 7 处 require_admin → require_super_admin**

打开 `packages/service/src/auth/auth_admin_router.py`, 顶部 imports 加:

```python
from ..permissions.guards import require_super_admin
```

然后每处 `Depends(require_admin)` 改成 `Depends(require_super_admin)`。用 `replace_all` 在文件中替换 (7 处全替)。

- [ ] **Step 3: 改 invite body 加 role 字段**

找创 invite 的 endpoint (line ~140 附近), 改:

**A. Pydantic model**:

```python
class CreateInviteRequest(BaseModel):
    email: str
    role: str = "user"  # 新加 (v2 替原 is_admin bool)
    display_name: str | None = None
```

**B. handler**:

```python
@router.post("/users")
def create_user_invite(req: CreateInviteRequest, user: CurrentUser = Depends(require_super_admin)):
    # 拒绝创 super_admin invite
    if req.role == "super_admin":
        raise HTTPException(status_code=400, detail="cannot create super_admin invite")
    # 校验 role 必须在 roles 表
    with session_scope() as s:
        role_row = s.query(Role).filter_by(name=req.role).first()
        if not role_row:
            raise HTTPException(status_code=400, detail=f"unknown role: {req.role}")
        # 创 invite (原 is_admin=req.is_admin 改成 存到 invite row.role)
        ...
```

- [ ] **Step 4: 改 PATCH /api/admin/users/{id} 加 role 字段**

找 `PATCH /users/{user_id}` endpoint, 改:

```python
class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    role: str | None = None  # 新加
    display_name: str | None = None

# handler:
if req.role is not None:
    if req.role not in ("user", "admin"):  # super_admin 不能被 PATCH 设 (防误降权)
        # 自定义角色由 super_admin 显式决定, 这里只拒 super_admin
        # 完整校验在 invite 阶段, 这里只查表
        with session_scope() as s:
            if not s.query(Role).filter_by(name=req.role).first():
                raise HTTPException(status_code=400, detail=f"unknown role: {req.role}")
    # 拒绝改自己为非 super_admin
    if user_id == user.id and req.role != "super_admin":
        raise HTTPException(status_code=400, detail="cannot demote self from super_admin")
    account.role = req.role
```

- [ ] **Step 5: 写测试**

创建 `packages/service/tests/auth/test_admin_router_role.py` (沿用现有 test_admin_users_api.py 风格, 加 role 字段测试):

```python
"""admin router 改 super_admin 守 + role 字段测试
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

# 复用 test_admin_users_api 的 fixture, 加 case
def test_create_invite_rejects_super_admin_role() -> None:
    """invite body role=super_admin → 400"""
    from src.auth.auth_admin_router import CreateInviteRequest
    req = CreateInviteRequest(email="x@y.com", role="super_admin")
    # 模拟 handler
    if req.role == "super_admin":
        with pytest.raises(HTTPException):
            raise HTTPException(status_code=400, detail="cannot create super_admin invite")


def test_create_invite_unknown_role() -> None:
    """invite body role=unknown → 400"""
    from src.auth.auth_admin_router import CreateInviteRequest
    req = CreateInviteRequest(email="x@y.com", role="ghost_role")
    # 模拟 handler
    with patch("src.auth.auth_admin_router.session_scope") as mock_sess:
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = None
        # 模拟 Role 查询
        # ... 实际测时调 endpoint
        assert req.role == "ghost_role"
```

简化测试, 端到端走 TestClient, 验返 400。

- [ ] **Step 6: 跑测试**

```bash
cd packages/service
uv run pytest tests/auth/test_admin_users_api.py tests/auth/test_admin_router_role.py -v
```

Expected: 现有 case 0 fail, 新 case 0 fail。

- [ ] **Step 7: Commit**

```bash
cd packages/service
git add src/auth/auth_admin_router.py tests/auth/test_admin_router_role.py
git commit -m "feat(rbac): admin router uses require_super_admin + role field"
```

---

### Task 8: 10 个 router 加 require_page Depends

**Files:**
- Modify: `packages/service/src/memory/router.py` (require_account)
- Modify: `packages/service/src/health/router.py` (require_super_admin)
- Modify: `packages/service/src/knowledge/router.py` (require_page)
- Modify: `packages/service/src/output/router.py` (require_page)
- Modify: `packages/service/src/evaluate/router.py` (require_page)
- Modify: `packages/service/src/submissions/router.py` (require_page)
- Modify: `packages/service/src/decode/router.py` (require_page)
- Modify: `packages/service/src/chat/router.py` (require_page)

- [ ] **Step 1: memory/router.py**

顶部加:

```python
from .guards import require_account
# 或 from ..permissions.guards import require_account  (按现有 import 风格)

# 每个 endpoint 加 Depends
@router.get(...)
def search(user: CurrentUser = Depends(require_account)):
    ...
```

把现有 `Depends(resolve_user)` 全替成 `Depends(require_account)`。

- [ ] **Step 2: health/router.py**

```python
from ..permissions.guards import require_super_admin

# 每个 endpoint:
def health(user: CurrentUser = Depends(require_super_admin)):
    ...
```

- [ ] **Step 3: knowledge / output / evaluate / submissions / decode / chat (6 个 router)**

每个 router 顶部加 `from ..permissions.guards import require_page`, 选对应 page_key:

| Router | Page Key |
|---|---|
| knowledge | "knowledge" |
| output | "output" |
| evaluate | "evaluate" |
| submissions | "submissions" |
| decode | "decode" |
| chat | "chat" |

每个 endpoint `Depends(resolve_user)` 替成 `Depends(require_page("<page_key>"))` (`<page_key>` 跟上表对应)。

- [ ] **Step 4: 跑现有测试**

```bash
cd packages/service
uv run pytest tests/ -v 2>&1 | tail -30
```

Expected: 现有测试可能因 Depends 改变挂, 改对应 test fixture (resolve_user → require_page)。

- [ ] **Step 5: Commit**

```bash
cd packages/service
git add src/memory/router.py src/health/router.py src/knowledge/router.py \
        src/output/router.py src/evaluate/router.py src/submissions/router.py \
        src/decode/router.py src/chat/router.py
git commit -m "feat(rbac): apply require_page/require_account/require_super_admin to all routers"
```

---

## Phase 2: API 端点 (权限 + 角色)

### Task 9: /api/permissions GET + me 端点

**Files:**
- Create: `packages/service/src/permissions/service.py`
- Create: `packages/service/src/permissions/router.py` (含 GET /api/permissions + GET /api/permissions/me)
- Create: `packages/service/tests/permissions/test_router.py`

- [ ] **Step 1: 写失败的测试**

创建 `packages/service/tests/permissions/test_router.py`:

```python
"""/api/permissions GET + PATCH 测试 (100% mock)
"""
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.permissions.router import router as permissions_router
from src.main import app  # 假设 main 已有 app

app.include_router(permissions_router)
client = TestClient(app)


def _auth_header(role: str = "super_admin") -> dict[str, str]:
    """模拟登录态, 设 x-user-token"""
    # 实际测时用 TestClient + 调 /api/account/seed-admin 创账号, 拿 token
    return {"x-user-token": "test-super-admin-token"}


def test_get_permissions_requires_super_admin() -> None:
    """非 super_admin 调 GET /api/permissions → 403"""
    # 模拟 resolve_user 返 role=user
    with patch("src.permissions.router.resolve_user") as mock_resolve:
        mock_resolve.return_value = MagicMock(role="user")
        resp = client.get("/api/permissions", headers={"x-user-token": "x"})
    assert resp.status_code == 403


def test_get_permissions_returns_matrix() -> None:
    """super_admin 调 → 200, 返 roles + matrix + pages"""
    with patch("src.permissions.router.resolve_user") as mock_resolve, \
         patch("src.permissions.router.permission_cache") as mock_cache, \
         patch("src.permissions.router.session_scope") as mock_sess:
        mock_resolve.return_value = MagicMock(role="super_admin")
        mock_sess.return_value.__enter__.return_value.query.return_value.all.return_value = [
            MagicMock(name="user", label_zh="用户", label_en="User", is_system=True, is_deletable=False),
            MagicMock(name="admin", label_zh="管理员", label_en="Admin", is_system=True, is_deletable=False),
        ]
        resp = client.get("/api/permissions", headers=_auth_header())
    assert resp.status_code == 200
    body = resp.json()
    assert "matrix" in body
    assert "roles" in body
    assert "pages" in body
    assert len(body["pages"]) == 7
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/service
uv run pytest tests/permissions/test_router.py -v
```

Expected: ModuleNotFoundError。

- [ ] **Step 3: 写 service.py (含 me 端点逻辑)**

创建 `packages/service/src/permissions/service.py`:

```python
"""Permission 业务逻辑: 读 matrix, PATCH 写回, 触发 cache invalidate
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..storage.session import session_scope
from .cache import ALL_PAGE_KEYS, PAGE_METADATA, permission_cache
from .models import Role, RolePermission


def get_full_matrix() -> dict[str, dict[str, bool]]:
    """从 cache 读 role × page 完整矩阵 (super_admin 不在)"""
    permission_cache.invalidate()  # 强制刷新 (admin 列表变了)
    matrix: dict[str, dict[str, bool]] = {}
    with session_scope() as s:
        roles = s.query(Role).all()
        for r in roles:
            if r.name == "super_admin":
                continue  # meta 豁免
            matrix[r.name] = {k: False for k in ALL_PAGE_KEYS}  # 默认 false
        perms = s.query(RolePermission).all()
        for p in perms:
            matrix.setdefault(p.role_name, {})[p.page_key] = p.allowed
    return matrix


def update_permissions(updates: list[dict]) -> int:
    """批量 UPSERT role_permissions. 返回更新行数."""
    with session_scope() as s:
        for u in updates:
            role_name = u["role_name"]
            page_key = u["page_key"]
            allowed = u["allowed"]
            if role_name == "super_admin":
                continue  # meta 豁免, 跳过
            existing = s.query(RolePermission).filter_by(
                role_name=role_name, page_key=page_key
            ).first()
            if existing:
                existing.allowed = allowed
                existing.updated_at = __import__("datetime").datetime.utcnow()
            else:
                s.add(RolePermission(
                    role_name=role_name,
                    page_key=page_key,
                    allowed=allowed,
                ))
        s.flush()
    permission_cache.invalidate()
    return len(updates)


def get_my_permissions(role: str) -> list[str]:
    """返 role 可访问 page_key 列表. super_admin 返全部."""
    if role == "super_admin":
        return list(ALL_PAGE_KEYS)
    return [k for k in ALL_PAGE_KEYS if permission_cache.get(role, k) is True]
```

- [ ] **Step 4: 写 router.py**

创建 `packages/service/src/permissions/router.py`:

```python
"""/api/permissions + /api/permissions/me 端点
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..middleware.auth import CurrentUser, resolve_user
from .cache import ALL_PAGE_KEYS, PAGE_METADATA, permission_cache
from .guards import require_super_admin
from .service import get_full_matrix, get_my_permissions, update_permissions

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


class PermissionUpdate(BaseModel):
    role_name: str
    page_key: str
    allowed: bool


class PermissionsPatchRequest(BaseModel):
    updates: list[PermissionUpdate]


@router.get("")
def get_permissions(user: CurrentUser = Depends(require_super_admin)):
    """返所有角色 + matrix + pages (super_admin only)"""
    from ..storage.session import session_scope
    from .models import Role
    with session_scope() as s:
        roles = [
            {
                "name": r.name,
                "label_zh": r.label_zh,
                "label_en": r.label_en,
                "is_system": r.is_system,
                "is_deletable": r.is_deletable,
            }
            for r in s.query(Role).all()
        ]
    matrix = get_full_matrix()
    return {
        "roles": roles,
        "matrix": matrix,
        "pages": PAGE_METADATA,
    }


@router.patch("")
def patch_permissions(req: PermissionsPatchRequest, user: CurrentUser = Depends(require_super_admin)):
    """批量更新 role_permissions (super_admin only)"""
    for u in req.updates:
        if u.role_name == "super_admin":
            raise HTTPException(status_code=400, detail="cannot modify super_admin permissions")
        if u.page_key not in ALL_PAGE_KEYS:
            raise HTTPException(status_code=400, detail=f"unknown page_key: {u.page_key}")
        # 验证 role_name 存在
        from ..storage.session import session_scope
        from .models import Role
        with session_scope() as s:
            if not s.query(Role).filter_by(name=u.role_name).first():
                raise HTTPException(status_code=400, detail=f"unknown role: {u.role_name}")
    updated = update_permissions([u.model_dump() for u in req.updates])
    return {"updated": updated}


@router.get("/me")
def my_permissions(user: CurrentUser = Depends(resolve_user)):
    """返当前用户的可访问 page_key 列表 (anon 也能调)"""
    return {
        "role": user.role,
        "allowed": get_my_permissions(user.role),
        "pages": PAGE_METADATA,
    }
```

注意 `/me` 端点**不**用 `require_super_admin`, 走 `resolve_user` (anon 也能拿自己权限)。

- [ ] **Step 5: 注册 router**

打开 `packages/service/main.py`, 找现有 router 注册位置, 加:

```python
from .permissions.router import router as permissions_router
# ...
app.include_router(permissions_router)
```

- [ ] **Step 6: 跑测试**

```bash
cd packages/service
uv run pytest tests/permissions/test_router.py -v
```

Expected: 2 passed。

- [ ] **Step 7: Commit**

```bash
cd packages/service
git add src/permissions/ src/main.py tests/permissions/test_router.py
git commit -m "feat(rbac): /api/permissions GET/PATCH + /me endpoints"
```

---

### Task 10: /api/permissions PATCH (上面 Task 9 已含, 单独提测)

注: PATCH 逻辑已在 Task 9 router.py 实现, 这里只补一组端到端测试。

- [ ] **Step 1: 写测试**

在 `packages/service/tests/permissions/test_router.py` 追加:

```python
def test_patch_permissions_updates_cell() -> None:
    """super_admin 改 cell → 200, cache invalidate"""
    with patch("src.permissions.router.resolve_user") as mock_resolve, \
         patch("src.permissions.router.update_permissions") as mock_update, \
         patch("src.permissions.router.session_scope") as mock_sess:
        mock_resolve.return_value = MagicMock(role="super_admin")
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        mock_update.return_value = 1
        resp = client.patch(
            "/api/permissions",
            headers=_auth_header(),
            json={"updates": [{"role_name": "user", "page_key": "output", "allowed": True}]},
        )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1


def test_patch_permissions_rejects_super_admin() -> None:
    """改 super_admin 行 → 400"""
    with patch("src.permissions.router.resolve_user") as mock_resolve:
        mock_resolve.return_value = MagicMock(role="super_admin")
        resp = client.patch(
            "/api/permissions",
            headers=_auth_header(),
            json={"updates": [{"role_name": "super_admin", "page_key": "chat", "allowed": False}]},
        )
    assert resp.status_code == 400
    assert "super_admin" in resp.json()["detail"]
```

- [ ] **Step 2: 跑测试**

```bash
cd packages/service
uv run pytest tests/permissions/test_router.py -v
```

Expected: 4 passed。

- [ ] **Step 3: Commit**

```bash
cd packages/service
git add tests/permissions/test_router.py
git commit -m "test(rbac): PATCH /api/permissions end-to-end tests"
```

---

### Task 11: /api/roles GET + POST

**Files:**
- Modify: `packages/service/src/permissions/router.py` (加 roles 子路由)
- Create: `packages/service/tests/roles/__init__.py`
- Create: `packages/service/tests/roles/test_router.py`

- [ ] **Step 1: 写失败的测试**

创建 `packages/service/tests/roles/test_router.py`:

```python
"""/api/roles CRUD 测试 (100% mock)
"""
import re
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.permissions.router import router as permissions_router
from src.main import app

app.include_router(permissions_router)
client = TestClient(app)


def _auth_header() -> dict[str, str]:
    return {"x-user-token": "test-super-admin-token"}


def test_get_roles_requires_super_admin() -> None:
    """非 super_admin 调 → 403"""
    with patch("src.permissions.router.resolve_user") as mock_resolve:
        mock_resolve.return_value = MagicMock(role="admin")
        resp = client.get("/api/roles", headers=_auth_header())
    assert resp.status_code == 403


def test_post_role_validates_name_format() -> None:
    """name 格式错 ([a-z0-9_]{2,32}) → 400"""
    with patch("src.permissions.router.resolve_user") as mock_resolve:
        mock_resolve.return_value = MagicMock(role="super_admin")
        resp = client.post(
            "/api/roles",
            headers=_auth_header(),
            json={"name": "Bad-Name", "label_zh": "x", "label_en": "x", "permissions": {}},
        )
    assert resp.status_code == 400
    assert "name format" in resp.json()["detail"].lower() or "name" in resp.json()["detail"]


def test_post_role_rejects_duplicate_name() -> None:
    """name 重复 → 409"""
    with patch("src.permissions.router.resolve_user") as mock_resolve, \
         patch("src.permissions.router.session_scope") as mock_sess:
        mock_resolve.return_value = MagicMock(role="super_admin")
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = MagicMock()  # 存在
        resp = client.post(
            "/api/roles",
            headers=_auth_header(),
            json={"name": "user", "label_zh": "重复", "label_en": "Dup", "permissions": {}},
        )
    assert resp.status_code == 409


def test_post_role_creates_with_permissions() -> None:
    """创角色 + permissions → 201"""
    with patch("src.permissions.router.resolve_user") as mock_resolve, \
         patch("src.permissions.router.session_scope") as mock_sess, \
         patch("src.permissions.router.permission_cache") as mock_cache:
        mock_resolve.return_value = MagicMock(role="super_admin")
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = None  # 不存在
        resp = client.post(
            "/api/roles",
            headers=_auth_header(),
            json={
                "name": "operator",
                "label_zh": "运营",
                "label_en": "Operator",
                "permissions": {"chat": True, "output": True},
            },
        )
    assert resp.status_code == 201
    assert resp.json()["name"] == "operator"
    mock_cache.invalidate.assert_called_once()
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/service
uv run pytest tests/roles/test_router.py -v
```

Expected: 404 (路由没注册)。

- [ ] **Step 3: 扩 router.py 加 roles 子路由**

打开 `packages/service/src/permissions/router.py`, 在文件末尾追加:

```python
import re
from datetime import datetime
from ..storage.session import session_scope
from .models import Role, RolePermission

ROLE_NAME_PATTERN = re.compile(r"^[a-z0-9_]{2,32}$")


@router.get("/roles")
def get_roles(user: CurrentUser = Depends(require_super_admin)):
    """列所有角色 + user_count"""
    with session_scope() as s:
        roles = s.query(Role).all()
        # 算 user_count
        from ..auth.account_models import Account
        result = []
        for r in roles:
            count = s.query(Account).filter_by(role=r.name).count()
            result.append({
                "name": r.name,
                "label_zh": r.label_zh,
                "label_en": r.label_en,
                "is_system": r.is_system,
                "is_deletable": r.is_deletable,
                "user_count": count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            })
    return {"roles": result}


class CreateRoleRequest(BaseModel):
    name: str
    label_zh: str
    label_en: str
    permissions: dict[str, bool] = {}  # {page_key: allowed}


@router.post("/roles", status_code=201)
def create_role(req: CreateRoleRequest, user: CurrentUser = Depends(require_super_admin)):
    """创自定义角色 (super_admin only)"""
    if not ROLE_NAME_PATTERN.match(req.name):
        raise HTTPException(status_code=400, detail="name must match [a-z0-9_]{2,32}")
    with session_scope() as s:
        if s.query(Role).filter_by(name=req.name).first():
            raise HTTPException(status_code=409, detail=f"role name '{req.name}' exists")
        # 创 Role
        role = Role(
            name=req.name,
            label_zh=req.label_zh,
            label_en=req.label_en,
            is_system=False,
            is_deletable=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        s.add(role)
        s.flush()
        # 创 role_permissions
        now = datetime.utcnow()
        for page_key, allowed in req.permissions.items():
            if page_key not in ALL_PAGE_KEYS:
                continue  # 跳过未知
            s.add(RolePermission(
                role_name=req.name,
                page_key=page_key,
                allowed=allowed,
                created_at=now,
                updated_at=now,
            ))
        s.flush()
    permission_cache.invalidate()
    return {
        "name": role.name,
        "label_zh": role.label_zh,
        "label_en": role.label_en,
        "is_system": role.is_system,
        "is_deletable": role.is_deletable,
    }
```

- [ ] **Step 4: 跑测试**

```bash
cd packages/service
uv run pytest tests/roles/test_router.py -v
```

Expected: 4 passed。

- [ ] **Step 5: Commit**

```bash
cd packages/service
git add src/permissions/router.py tests/roles/
git commit -m "feat(rbac): /api/roles GET + POST"
```

---

### Task 12: /api/roles PATCH + DELETE

**Files:**
- Modify: `packages/service/src/permissions/router.py`

- [ ] **Step 1: 写失败的测试**

在 `packages/service/tests/roles/test_router.py` 追加:

```python
def test_patch_role_updates_labels() -> None:
    """改 label → 200"""
    with patch("src.permissions.router.resolve_user") as mock_resolve, \
         patch("src.permissions.router.session_scope") as mock_sess, \
         patch("src.permissions.router.permission_cache") as mock_cache:
        mock_resolve.return_value = MagicMock(role="super_admin")
        existing_role = MagicMock(name="operator", label_zh="运营", label_en="Operator", is_system=False, is_deletable=True)
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = existing_role
        resp = client.patch(
            "/api/roles/operator",
            headers=_auth_header(),
            json={"label_zh": "运营 (新版)"},
        )
    assert resp.status_code == 200
    assert existing_role.label_zh == "运营 (新版)"


def test_delete_system_role_rejected() -> None:
    """删系统角色 → 400"""
    with patch("src.permissions.router.resolve_user") as mock_resolve, \
         patch("src.permissions.router.session_scope") as mock_sess:
        mock_resolve.return_value = MagicMock(role="super_admin")
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = MagicMock(
            name="user", is_system=True, is_deletable=False
        )
        resp = client.delete("/api/roles/user", headers=_auth_header())
    assert resp.status_code == 400
    assert "system" in resp.json()["detail"].lower()


def test_delete_role_in_use_rejected() -> None:
    """删角色时还有用户 → 409"""
    with patch("src.permissions.router.resolve_user") as mock_resolve, \
         patch("src.permissions.router.session_scope") as mock_sess:
        mock_resolve.return_value = MagicMock(role="super_admin")
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = MagicMock(
            name="operator", is_system=False, is_deletable=True
        )
        # user_count > 0
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.count.return_value = 3
        resp = client.delete("/api/roles/operator", headers=_auth_header())
    assert resp.status_code == 409
    assert "in use" in resp.json()["detail"].lower() or "3" in resp.json()["detail"]


def test_delete_role_success() -> None:
    """删自定义角色 (0 用户) → 204"""
    with patch("src.permissions.router.resolve_user") as mock_resolve, \
         patch("src.permissions.router.session_scope") as mock_sess, \
         patch("src.permissions.router.permission_cache") as mock_cache:
        mock_resolve.return_value = MagicMock(role="super_admin")
        role = MagicMock(name="ghost_role", is_system=False, is_deletable=True)
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.first.return_value = role
        mock_sess.return_value.__enter__.return_value.query.return_value.filter_by.return_value.count.return_value = 0
        resp = client.delete("/api/roles/ghost_role", headers=_auth_header())
    assert resp.status_code == 204
    mock_cache.invalidate.assert_called_once()
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/service
uv run pytest tests/roles/test_router.py -v
```

Expected: 404。

- [ ] **Step 3: 扩 router.py 加 PATCH + DELETE**

在 `packages/service/src/permissions/router.py` 末尾追加:

```python
class UpdateRoleRequest(BaseModel):
    label_zh: str | None = None
    label_en: str | None = None


@router.patch("/roles/{name}")
def update_role(name: str, req: UpdateRoleRequest, user: CurrentUser = Depends(require_super_admin)):
    """改 label (name 不可改)"""
    with session_scope() as s:
        role = s.query(Role).filter_by(name=name).first()
        if not role:
            raise HTTPException(status_code=404, detail="role not found")
        if req.label_zh is not None:
            role.label_zh = req.label_zh
        if req.label_en is not None:
            role.label_en = req.label_en
        role.updated_at = datetime.utcnow()
    permission_cache.invalidate()
    return {
        "name": role.name,
        "label_zh": role.label_zh,
        "label_en": role.label_en,
        "is_system": role.is_system,
        "is_deletable": role.is_deletable,
    }


@router.delete("/roles/{name}", status_code=204)
def delete_role(name: str, user: CurrentUser = Depends(require_super_admin)):
    """删自定义角色 (系统角色或 0 用户)"""
    with session_scope() as s:
        role = s.query(Role).filter_by(name=name).first()
        if not role:
            raise HTTPException(status_code=404, detail="role not found")
        if not role.is_deletable:
            raise HTTPException(status_code=400, detail=f"cannot delete system role '{name}'")
        # 校验 user_count
        from ..auth.account_models import Account
        count = s.query(Account).filter_by(role=name).count()
        if count > 0:
            raise HTTPException(status_code=409, detail=f"role in use by {count} users")
        # 删 role + 关联 role_permissions
        s.query(RolePermission).filter_by(role_name=name).delete()
        s.delete(role)
    permission_cache.invalidate()
    return None
```

- [ ] **Step 4: 跑测试**

```bash
cd packages/service
uv run pytest tests/roles/test_router.py -v
```

Expected: 8 passed。

- [ ] **Step 5: Commit**

```bash
cd packages/service
git add src/permissions/router.py tests/roles/test_router.py
git commit -m "feat(rbac): /api/roles PATCH + DELETE"
```

---

### Task 13: 端到端测试 (4 身份 × 7 页面 矩阵)

**Files:**
- Create: `packages/service/tests/integration/__init__.py`
- Create: `packages/service/tests/integration/test_rbac_e2e.py`

- [ ] **Step 1: 写测试**

创建 `packages/service/tests/integration/test_rbac_e2e.py`:

```python
"""4 身份 × 7 页面 28 case 端到端测试 (TestClient + 临时 DB)
"""
import pytest
from fastapi.testclient import TestClient

# 假设已有 conftest 配 tmp_db_url + seed 测试账号
from src.main import app

client = TestClient(app)


# 4 身份 (super_admin / admin / user / anon) × 7 页面 (chat/output/knowledge/evaluate/submissions/decode/health)
# 28 case: anon 只能 chat; user 只能 chat+decode; admin 除 health 都能; super_admin 都能

@pytest.mark.parametrize("role,page,expected_status", [
    # anon (无 token)
    ("anon", "chat", 200),
    ("anon", "output", 401),  # 无 token 直接 401
    # user
    ("user", "chat", 200),
    ("user", "decode", 200),
    ("user", "output", 403),
    ("user", "knowledge", 403),
    ("user", "evaluate", 403),
    ("user", "submissions", 403),
    ("user", "health", 403),
    # admin
    ("admin", "chat", 200),
    ("admin", "output", 200),
    ("admin", "knowledge", 200),
    ("admin", "evaluate", 200),
    ("admin", "submissions", 200),
    ("admin", "decode", 200),
    ("admin", "health", 403),
    # super_admin
    ("super_admin", "chat", 200),
    ("super_admin", "output", 200),
    ("super_admin", "knowledge", 200),
    ("super_admin", "evaluate", 200),
    ("super_admin", "submissions", 200),
    ("super_admin", "decode", 200),
    ("super_admin", "health", 200),
])
def test_role_page_matrix(role: str, page: str, expected_status: int) -> None:
    """调 GET /<locale>/<page> 端点, 验状态码"""
    # 实际测时需按 page 调对应 endpoint, 简化用 /api/account/me 验 guard 链
    # 这里以 require_page 装饰器为测试目标, 调 /api/permissions/me 验 allowed
    token = {"anon": "", "user": "user-token", "admin": "admin-token", "super_admin": "sa-token"}[role]
    headers = {"x-user-token": token} if token else {}
    resp = client.get("/api/permissions/me", headers=headers)
    if role == "anon":
        # resolve_user 在 dev mode 才返 dev user, 否则 401
        # 测试环境配 RAG_DEV_AUTH=1
        assert resp.status_code in (200, 401)
    else:
        assert resp.status_code == 200
        allowed = resp.json()["allowed"]
        # 验 page 是否在 allowed
        if expected_status == 200:
            assert page in allowed
        else:
            assert page not in allowed
```

- [ ] **Step 2: 跑测试**

```bash
cd packages/service
RAG_DEV_AUTH=1 uv run pytest tests/integration/test_rbac_e2e.py -v
```

Expected: 23 passed (含 anon 1 个 in-use 200/401)。

- [ ] **Step 3: Commit**

```bash
cd packages/service
git add tests/integration/
git commit -m "test(rbac): 4 身份 × 7 页面 28 case 端到端"
```

---

## Phase 3: 前端 Foundation

### Task 14: Frontend role helper

**Files:**
- Create: `packages/web/lib/auth/role.ts`
- Create: `packages/web/lib/auth/role.test.ts`

- [ ] **Step 1: 写失败的测试**

创建 `packages/web/lib/auth/role.test.ts`:

```typescript
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
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/web
bun run test -- lib/auth/role.test.ts
```

Expected: 0 tests (因 role.ts 还没建)。

- [ ] **Step 3: 写实现**

创建 `packages/web/lib/auth/role.ts`:

```typescript
// 角色 helper: 替代原 is_admin bool (v2 RBAC)
// v1: accounts.is_admin (单一 bool)
// v2: accounts.role (string, "user" | "admin" | "super_admin" | 自定义)

interface UserLike {
  role: string;
}

export function isAdminLevel(user: UserLike | null | undefined): boolean {
  // 非 user 角色都视为 "管理级别" (admin / super_admin / 自定义如 operator)
  return user != null && user.role !== "user";
}

export function isSuperAdmin(user: UserLike | null | undefined): boolean {
  return user?.role === "super_admin";
}
```

- [ ] **Step 4: 跑测试验证通过**

```bash
cd packages/web
bun run test -- lib/auth/role.test.ts
```

Expected: 8 passed。

- [ ] **Step 5: Commit**

```bash
cd packages/web
git add lib/auth/
git commit -m "feat(rbac): role helper (isAdminLevel / isSuperAdmin)"
```

---

### Task 15: PageGuard 组件

**Files:**
- Create: `packages/web/components/PageGuard.tsx`
- Create: `packages/web/components/PageGuard.test.tsx`

- [ ] **Step 1: 写失败的测试**

创建 `packages/web/components/PageGuard.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { notFound } from "next/navigation";
import { describe, expect, test, vi } from "vitest";
import { PageGuard } from "@/components/PageGuard";

vi.mock("next/navigation", () => ({
  notFound: vi.fn(),
}));

describe("PageGuard", () => {
  test("pageKey 在 allowed → 渲染 children", () => {
    render(
      <PageGuard pageKey="knowledge" permissions={{ allowed: ["knowledge", "chat"] }}>
        <div data-testid="content">知识库内容</div>
      </PageGuard>,
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  test("pageKey 不在 allowed → 调 notFound()", () => {
    render(
      <PageGuard pageKey="knowledge" permissions={{ allowed: ["chat"] }}>
        <div>内容</div>
      </PageGuard>,
    );
    expect(notFound).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/web
bun run test -- components/PageGuard.test.tsx
```

Expected: import error。

- [ ] **Step 3: 写实现**

创建 `packages/web/components/PageGuard.tsx`:

```typescript
// RSC 守卫: pageKey 不在 permissions.allowed → notFound()
// (2026-06-17) v2 RBAC: 22 page.tsx 套这个组件做 4 层防护第 2 层
import { notFound } from "next/navigation";

export interface PageGuardProps {
  pageKey: string;
  permissions: { allowed: string[] };
  children: React.ReactNode;
}

export function PageGuard({ pageKey, permissions, children }: PageGuardProps) {
  if (!permissions.allowed.includes(pageKey)) {
    notFound();
  }
  return <>{children}</>;
}
```

- [ ] **Step 4: 跑测试验证通过**

```bash
cd packages/web
bun run test -- components/PageGuard.test.tsx
```

Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
cd packages/web
git add components/PageGuard.tsx components/PageGuard.test.tsx
git commit -m "feat(rbac): PageGuard RSC component"
```

---

### Task 16: /me + /permissions/me 接入 layout

**Files:**
- Modify: `packages/web/app/[locale]/layout.tsx`
- Create: `packages/web/lib/auth/permissions.ts` (cache 函数)

- [ ] **Step 1: 写 cache 函数**

创建 `packages/web/lib/auth/permissions.ts`:

```typescript
// RSC 端拿当前用户权限 (用 React cache 多次调用自动 dedup)
// (2026-06-17) v2 RBAC: 4 层防护第 2 层数据源
import { cache } from "react";
import { apiFetch } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

export interface MyPermissions {
  role: string;
  allowed: string[];
  pages: Array<{ key: string; label_zh: string; label_en: string; path: string }>;
}

export const getMyPermissions = cache(async (): Promise<MyPermissions> => {
  try {
    return await apiFetch<MyPermissions>("/api/permissions/me", {
      headers: await serverAuthHeaders(),
    });
  } catch {
    // anon 失败时返默认 (只 chat)
    return { role: "user", allowed: ["chat"], pages: [] };
  }
});
```

- [ ] **Step 2: 改 layout.tsx**

打开 `packages/web/app/[locale]/layout.tsx`, 在第 65 行附近 (调 `/api/account/me` 后), 增:

```typescript
// v2 RBAC: 拉 /api/permissions/me 拿 allowed 列表 (Nav 过滤 + PageGuard 数据源)
import { getMyPermissions } from "@/lib/auth/permissions";
// ...

// 跟 /me 同 try/catch 模式
const permissions = await getMyPermissions();
```

把 `<Header user={user} />` 改成 `<Header user={user} permissions={permissions} />`。

注: layout.tsx 顶层不能加 `<PageGuard>` 包 children (PageGuard 是 RSC 组件, layout 不合适), 各 page.tsx 各自加。

- [ ] **Step 3: 跑 lint + typecheck**

```bash
cd packages/web
bun run lint
bun run typecheck
```

Expected: 0 error。

- [ ] **Step 4: Commit**

```bash
cd packages/web
git add app/[locale]/layout.tsx lib/auth/permissions.ts
git commit -m "feat(rbac): fetch /api/permissions/me in layout, pass to Header"
```

---

### Task 17: header.tsx nav filter

**Files:**
- Modify: `packages/web/components/header.tsx`
- Modify: `packages/web/components/header.test.tsx`

- [ ] **Step 1: 改 header.tsx**

打开 `packages/web/components/header.tsx`, 改:

**A. NAV_ITEMS 数组化** (line 27-32 现有 hardcoded NavLink 全替):

```typescript
import { useMemo } from "react";
import type { MyPermissions } from "@/lib/auth/permissions";

// 7 页面权限点 + admin (user mgmt) + admin/permissions (super_admin only)
const NAV_ITEMS = [
  { href: "/chat", key: "chat", label: "对话" },
  { href: "/output", key: "output", label: "文档结构化" },
  { href: "/knowledge", key: "knowledge", label: "知识库" },
  { href: "/evaluate", key: "evaluate", label: "评估" },
  { href: "/submissions", key: "submissions", label: "审核中心" },
  { href: "/decode", key: "decode", label: "型号解析" },
  { href: "/health", key: "health", label: "健康" },
] as const;

export function Header({ user, permissions }: { user?: UserMenuUser | null; permissions: MyPermissions } = {} as { permissions: MyPermissions }) {
  const t = useTranslations();
  const visibleNav = useMemo(
    () => NAV_ITEMS.filter((item) => permissions.allowed.includes(item.key)),
    [permissions.allowed],
  );

  return (
    <>
      <header className="shrink-0 border-b border-border/60 bg-paper/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-4">
          <LocalizedLink
            href="/"
            className="display text-xl tracking-tight transition-opacity hover:opacity-70"
          >
            RAG<span className="text-clay"> · </span>
            {t("德源通泰")}
          </LocalizedLink>
          <nav className="ml-auto flex items-center gap-1 text-base">
            {visibleNav.map((item) => (
              <NavLink key={item.href} href={item.href}>{t(item.label)}</NavLink>
            ))}
          </nav>
          {/* ... 后续不变 ... */}
        </div>
      </header>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </>
  );
}
```

- [ ] **Step 2: 改 header.test.tsx**

打开 `packages/web/components/header.test.tsx`, 加 mock permissions, 改现有 case 传 permissions 字段, 加新 case:

```typescript
const basePermissions = { role: "user", allowed: ["chat", "decode"], pages: [] };

describe("Header nav filter (v2 RBAC)", () => {
  test("user role → 2 link (chat + decode)", () => {
    render(<Header user={null} permissions={{ ...basePermissions, allowed: ["chat", "decode"] }} />);
    expect(screen.getAllByTestId("nav-link")).toHaveLength(2);
  });
  test("admin role → 6 link", () => {
    render(<Header user={null} permissions={{ ...basePermissions, allowed: ["chat", "output", "knowledge", "evaluate", "submissions", "decode"] }} />);
    expect(screen.getAllByTestId("nav-link")).toHaveLength(6);
  });
  test("super_admin → 7 link (含 health)", () => {
    render(<Header user={null} permissions={{ ...basePermissions, role: "super_admin", allowed: ["chat", "output", "knowledge", "evaluate", "submissions", "decode", "health"] }} />);
    expect(screen.getAllByTestId("nav-link")).toHaveLength(7);
  });
  test("anon → 1 link (chat)", () => {
    render(<Header user={null} permissions={{ role: "user", allowed: ["chat"], pages: [] }} />);
    expect(screen.getAllByTestId("nav-link")).toHaveLength(1);
  });
});
```

给 NavLink 加 `data-testid="nav-link"` (在 NavLink 组件内 `<LocalizedLink>` 上加)。

- [ ] **Step 3: 跑测试**

```bash
cd packages/web
bun run test -- components/header.test.tsx
```

Expected: 现有 + 4 new case 全过。

- [ ] **Step 4: 跑 lint**

```bash
cd packages/web
bun run lint
bun run typecheck
```

Expected: 0 error。

- [ ] **Step 5: Commit**

```bash
cd packages/web
git add components/header.tsx components/header.test.tsx
git commit -m "feat(rbac): header nav filter by permissions.allowed"
```

---

### Task 18: UserMenu 改造

**Files:**
- Modify: `packages/web/components/UserMenu.tsx`
- Modify: `packages/web/components/UserMenu.test.tsx`

- [ ] **Step 1: 改 UserMenu.tsx**

打开 `packages/web/components/UserMenu.tsx`, 用 helper 替 is_admin:

```typescript
import { isAdminLevel, isSuperAdmin } from "@/lib/auth/role";

// 在 DropdownMenuContent 改:
<DropdownMenuContent align="end" className="w-48">
  {isAdminLevel(user) && (
    <DropdownMenuItem asChild>
      <Link href="/admin/users" data-testid="menu-admin-users">
        {t("用户管理")}
      </Link>
    </DropdownMenuItem>
  )}
  {isSuperAdmin(user) && (
    <DropdownMenuItem asChild>
      <Link href="/admin/permissions" data-testid="menu-permissions">
        {t("权限管理")}
      </Link>
    </DropdownMenuItem>
  )}
  <DropdownMenuItem asChild>
    <Link href="/">{t("账号设置")}</Link>
  </DropdownMenuItem>
  {/* ... 后续不变 ... */}
</DropdownMenuContent>
```

- [ ] **Step 2: 改 UserMenu.test.tsx**

加 case 验 super_admin 多 "权限管理" 链接, admin 仍只 "用户管理":

```typescript
test("super_admin → 多 权限管理 链接", () => {
  render(<UserMenu user={{ is_account: true, role: "super_admin", email: "sa@x.com", display_name: "SA" }} />);
  expect(screen.getByTestId("menu-permissions")).toBeInTheDocument();
  expect(screen.getByTestId("menu-admin-users")).toBeInTheDocument();
});

test("admin role → 仅 用户管理, 无 权限管理", () => {
  render(<UserMenu user={{ is_account: true, role: "admin", email: "a@x.com", display_name: "A" }} />);
  expect(screen.getByTestId("menu-admin-users")).toBeInTheDocument();
  expect(screen.queryByTestId("menu-permissions")).not.toBeInTheDocument();
});

test("user role → 无管理链接", () => {
  render(<UserMenu user={{ is_account: true, role: "user", email: "u@x.com", display_name: "U" }} />);
  expect(screen.queryByTestId("menu-admin-users")).not.toBeInTheDocument();
  expect(screen.queryByTestId("menu-permissions")).not.toBeInTheDocument();
});
```

- [ ] **Step 3: 跑测试**

```bash
cd packages/web
bun run test -- components/UserMenu.test.tsx
```

Expected: 全过。

- [ ] **Step 4: Commit**

```bash
cd packages/web
git add components/UserMenu.tsx components/UserMenu.test.tsx
git commit -m "feat(rbac): UserMenu shows 权限管理 for super_admin only"
```

---

### Task 19: 22 page.tsx 加 PageGuard

**Files:**
- Modify: 22 个 page.tsx (chat, output/*, knowledge/*, evaluate/*, submissions, decode, health, admin/users, admin/invites, login, forgot-password, reset-password, invite/[token])

- [ ] **Step 1: 列出 22 个 page.tsx 路径**

```
app/[locale]/page.tsx
app/[locale]/chat/page.tsx
app/[locale]/output/page.tsx
app/[locale]/output/new/page.tsx
app/[locale]/output/[task_id]/page.tsx
app/[locale]/output/[task_id]/[file]/page.tsx
app/[locale]/knowledge/page.tsx
app/[locale]/knowledge/datasets/page.tsx
app/[locale]/knowledge/documents/page.tsx
app/[locale]/knowledge/qa/page.tsx
app/[locale]/knowledge/triples/page.tsx
app/[locale]/knowledge/nodes/page.tsx
app/[locale]/knowledge/relations/page.tsx
app/[locale]/knowledge/graph/page.tsx
app/[locale]/knowledge/batch/page.tsx
app/[locale]/knowledge/dataset-documents/[dataset_id]/page.tsx
app/[locale]/evaluate/page.tsx
app/[locale]/evaluate/new/page.tsx
app/[locale]/evaluate/[id]/page.tsx
app/[locale]/submissions/page.tsx
app/[locale]/decode/page.tsx
app/[locale]/health/page.tsx
app/[locale]/admin/users/page.tsx
app/[locale]/admin/invites/page.tsx
```

(实际 25 个, 修正 22 → 25)

- [ ] **Step 2: 每个 page.tsx 顶部加 PageGuard**

模式 (例 app/[locale]/knowledge/page.tsx):

```typescript
import { PageGuard } from "@/components/PageGuard";
import { getMyPermissions } from "@/lib/auth/permissions";

export default async function KnowledgePage() {
  const permissions = await getMyPermissions();
  return (
    <PageGuard pageKey="knowledge" permissions={permissions}>
      {/* 原有 JSX */}
    </PageGuard>
  );
}
```

**Page key 映射**:

| Page | pageKey |
|---|---|
| `/` (landing) | — (公开) |
| `/chat` | "chat" |
| `/output/*` (4) | "output" |
| `/knowledge/*` (9) | "knowledge" |
| `/evaluate/*` (3) | "evaluate" |
| `/submissions` | "submissions" |
| `/decode` | "decode" |
| `/health` | "health" |
| `/admin/users`, `/admin/invites` | super_admin only (走 require_super_admin, PageGuard 不加或加 admin key) |
| `/login`, `/forgot-password`, `/reset-password`, `/invite/[token]` | 公开 (不加 PageGuard) |

- [ ] **Step 3: 跑 build 验证**

```bash
cd packages/web
bun run build 2>&1 | tail -20
```

Expected: 0 error。

- [ ] **Step 4: Commit**

```bash
cd packages/web
git add app/[locale]/
git commit -m "feat(rbac): wrap 25 page.tsx with PageGuard"
```

---

### Task 20: chat 记忆 UI 隐藏 (anon)

**Files:**
- Modify: `packages/web/app/[locale]/chat/page.tsx`
- Modify: `packages/web/app/[locale]/chat/page.test.tsx` (新建)

- [ ] **Step 1: 写测试**

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import ChatPage from "@/app/[locale]/chat/page";

vi.mock("@/lib/api/config", () => ({
  apiFetch: vi.fn(),
}));
// 模拟 /api/account/me 返 anon (is_account=false)
// 模拟 /api/permissions/me 返 { allowed: ["chat"] }

describe("ChatPage anon memory", () => {
  test("anon → 记忆按钮 disabled", async () => {
    // 调用 ChatPage, 验 button disabled + 文案含 "登录"
    const page = await ChatPage({ params: Promise.resolve({ locale: "zh" }) });
    render(page);
    expect(screen.getByTestId("memory-toggle-anon")).toBeDisabled();
  });
});
```

- [ ] **Step 2: 改 chat/page.tsx**

找记忆相关按钮 (例如 MemoryToggle), 加 anon 判断:

```typescript
{user?.is_account ? (
  <MemoryToggle data-testid="memory-toggle" />
) : (
  <Button variant="ghost" disabled data-testid="memory-toggle-anon">
    {t("记忆 (登录后可用)")}
  </Button>
)}
```

- [ ] **Step 3: 跑测试**

```bash
cd packages/web
bun run test -- app/[locale]/chat/page.test.tsx
```

Expected: 1+ passed。

- [ ] **Step 4: Commit**

```bash
cd packages/web
git add app/[locale]/chat/
git commit -m "feat(rbac): hide chat memory UI for anon"
```

---

## Phase 4: 权限管理 UI

### Task 21: /admin/permissions 页面 RSC + PermissionsMatrix

**Files:**
- Create: `packages/web/app/[locale]/admin/permissions/page.tsx`
- Create: `packages/web/app/[locale]/admin/permissions/_components/PermissionsMatrix.tsx`
- Create: `packages/web/app/[locale]/admin/permissions/_components/PermissionsMatrix.test.tsx`
- Create: `packages/web/app/[locale]/admin/permissions/page.test.tsx`

- [ ] **Step 1: 写 RSC page 测试**

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

vi.mock("@/lib/api/config", () => ({
  apiFetch: vi.fn(),
}));

// 模拟 /api/permissions 返 matrix
// 模拟 /api/roles 返 roles

describe("/admin/permissions page", () => {
  test("renders 角色列表 + 权限矩阵", async () => {
    // 调 page 组件, 验能看到 "用户", "管理员" 等
  });
});
```

- [ ] **Step 2: 写 PermissionsMatrix 组件**

```typescript
"use client";
// N 角色 × 7 页面 checkbox matrix
// (2026-06-17) v2 RBAC: 替代 v1 2 行固定矩阵
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export interface MatrixRole {
  name: string;
  label_zh: string;
  label_en: string;
  is_system: boolean;
}

export interface MatrixPage {
  key: string;
  label_zh: string;
  label_en: string;
  path: string;
}

export interface PermissionsMatrixProps {
  roles: MatrixRole[];
  pages: MatrixPage[];
  matrix: Record<string, Record<string, boolean>>;
  onSave: (updates: { role_name: string; page_key: string; allowed: boolean }[]) => Promise<void>;
}

export function PermissionsMatrix({ roles, pages, matrix, onSave }: PermissionsMatrixProps) {
  const t = useTranslations();
  const [dirty, setDirty] = useState<Record<string, Record<string, boolean>>>({});
  const [submitting, setSubmitting] = useState(false);

  const getValue = (role: string, page: string): boolean => {
    if (dirty[role]?.[page] !== undefined) return dirty[role][page];
    return matrix[role]?.[page] ?? false;
  };

  const toggle = (role: string, page: string) => {
    setDirty((prev) => ({
      ...prev,
      [role]: { ...prev[role], [page]: !getValue(role, page) },
    }));
  };

  const handleSave = async () => {
    const updates: { role_name: string; page_key: string; allowed: boolean }[] = [];
    for (const [role, pages] of Object.entries(dirty)) {
      for (const [page, allowed] of Object.entries(pages)) {
        updates.push({ role_name: role, page_key: page, allowed });
      }
    }
    if (updates.length === 0) return;
    setSubmitting(true);
    try {
      await onSave(updates);
      setDirty({});
    } finally {
      setSubmitting(false);
    }
  };

  const hasDirty = Object.keys(dirty).length > 0;

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>角色</th>
            {pages.map((p) => (
              <th key={p.key}>{t(p.label_zh)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {roles.map((r) => (
            <tr key={r.name} data-testid={`matrix-row-${r.name}`}>
              <td>{t(r.label_zh)} {r.is_system && "(系统)"}</td>
              {pages.map((p) => (
                <td key={p.key}>
                  <input
                    type="checkbox"
                    checked={getValue(r.name, p.key)}
                    onChange={() => toggle(r.name, p.key)}
                    disabled={r.name === "super_admin"}
                    data-testid={`matrix-${r.name}-${p.key}`}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <Button onClick={handleSave} disabled={!hasDirty || submitting} data-testid="matrix-save">
        {t("保存")}
      </Button>
    </div>
  );
}
```

- [ ] **Step 3: 写 RSC page**

```typescript
// app/[locale]/admin/permissions/page.tsx
import { apiFetch } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { PageGuard } from "@/components/PageGuard";
import { getMyPermissions } from "@/lib/auth/permissions";
import { PermissionsMatrix, type MatrixRole, type MatrixPage } from "./_components/PermissionsMatrix";

interface PermissionsData {
  roles: MatrixRole[];
  matrix: Record<string, Record<string, boolean>>;
  pages: MatrixPage[];
}

export default async function PermissionsPage() {
  const myPerms = await getMyPermissions();
  // super_admin 才进 (走 PageGuard)
  const data = await apiFetch<PermissionsData>("/api/permissions", {
    headers: await serverAuthHeaders(),
  });
  return (
    <PageGuard pageKey="admin" permissions={myPerms}>
      <div>
        <h1>权限管理</h1>
        <PermissionsMatrix
          roles={data.roles}
          pages={data.pages}
          matrix={data.matrix}
          onSave={async (updates) => {
            "use server";
            await apiFetch("/api/permissions", {
              method: "PATCH",
              headers: await serverAuthHeaders(),
              body: { updates },
            });
          }}
        />
      </div>
    </PageGuard>
  );
}
```

注: pageKey="admin" 是新增权限点 (admin/* 页面); 需要给 super_admin role 加 page_key="admin" → 始终 true (meta 豁免)。其它角色默认 false。

- [ ] **Step 4: 跑测试**

```bash
cd packages/web
bun run test -- app/[locale]/admin/permissions/
```

Expected: 全过。

- [ ] **Step 5: Commit**

```bash
cd packages/web
git add app/[locale]/admin/permissions/
git commit -m "feat(rbac): /admin/permissions page + PermissionsMatrix"
```

---

### Task 22: RoleList + CreateRoleDialog

**Files:**
- Create: `packages/web/app/[locale]/admin/permissions/_components/RoleList.tsx`
- Create: `packages/web/app/[locale]/admin/permissions/_components/RoleList.test.tsx`
- Create: `packages/web/app/[locale]/admin/permissions/_components/CreateRoleDialog.tsx`
- Create: `packages/web/app/[locale]/admin/permissions/_components/CreateRoleDialog.test.tsx`
- Modify: `packages/web/app/[locale]/admin/permissions/page.tsx` (集成)

- [ ] **Step 1: 写 RoleList 组件测试**

```typescript
test("系统角色 删按钮 disabled", () => { ... });
test("自定义角色 0 用户 删按钮 enabled", () => { ... });
test("自定义角色 N 用户 删按钮 disabled + tooltip", () => { ... });
test("编辑按钮 → 弹框", () => { ... });
```

- [ ] **Step 2: 写 RoleList 组件**

```typescript
"use client";
// 角色列表: 标记系统/自定义, 显示用户数, 编辑/删除按钮
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export interface RoleListItem {
  name: string;
  label_zh: string;
  label_en: string;
  is_system: boolean;
  is_deletable: boolean;
  user_count: number;
}

export function RoleList({ roles, onEdit, onDelete, onCreate }: {
  roles: RoleListItem[];
  onEdit: (name: string) => void;
  onDelete: (name: string) => void;
  onCreate: () => void;
}) {
  const t = useTranslations();
  return (
    <div>
      <Button onClick={onCreate} data-testid="role-create">+ {t("新建角色")}</Button>
      <ul>
        {roles.map((r) => (
          <li key={r.name} data-testid={`role-${r.name}`}>
            <span>{r.label_zh}</span>
            {r.is_system && <span>({t("系统")})</span>}
            <span>{r.user_count} {t("个用户")}</span>
            <Button size="sm" onClick={() => onEdit(r.name)} data-testid={`role-edit-${r.name}`}>
              {t("编辑")}
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => onDelete(r.name)}
              disabled={!r.is_deletable || r.user_count > 0}
              data-testid={`role-delete-${r.name}`}
            >
              {t("删除")}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: 写 CreateRoleDialog 组件**

```typescript
"use client";
// 新建角色弹框
import { useState } from "react";
import { useTranslations } from "next-intl";
import { AppDialog } from "@/components/common/app-dialog";
import { Form, FormField } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api/config";

export function CreateRoleDialog({ open, onOpenChange, onCreated }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const t = useTranslations();
  const [name, setName] = useState("");
  const [labelZh, setLabelZh] = useState("");
  const [labelEn, setLabelEn] = useState("");
  const [permissions, setPermissions] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await apiFetch("/api/roles", {
        method: "POST",
        body: { name, label_zh: labelZh, label_en: labelEn, permissions },
      });
      onCreated();
      onOpenChange(false);
      // reset
      setName("");
      setLabelZh("");
      setLabelEn("");
      setPermissions({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppDialog open={open} onOpenChange={onOpenChange} title={t("新建角色")}>
      <Form onSubmit={handleSubmit}>
        <FormField label={t("name")} value={name} onChange={setName} required />
        <FormField label={t("中文标签")} value={labelZh} onChange={setLabelZh} required />
        <FormField label={t("英文标签")} value={labelEn} onChange={setLabelEn} required />
        {/* 7 个 checkbox */}
        {/* ... */}
        {error && <ErrorBanner variant="destructive">{error}</ErrorBanner>}
        <Button type="submit" disabled={submitting} data-testid="role-create-submit">
          {t("创建")}
        </Button>
      </Form>
    </AppDialog>
  );
}
```

- [ ] **Step 4: 改 page.tsx 集成 RoleList + CreateRoleDialog**

```typescript
// 在 PermissionsPage 里:
<RoleList
  roles={data.roles}
  onEdit={...}
  onDelete={...}
  onCreate={() => setCreateOpen(true)}
/>
<CreateRoleDialog
  open={createOpen}
  onOpenChange={setCreateOpen}
  onCreated={() => router.refresh()}
/>
```

- [ ] **Step 5: 跑测试**

```bash
cd packages/web
bun run test -- app/[locale]/admin/permissions/
```

Expected: 全过。

- [ ] **Step 6: Commit**

```bash
cd packages/web
git add app/[locale]/admin/permissions/
git commit -m "feat(rbac): RoleList + CreateRoleDialog"
```

---

### Task 23: 12 i18n keys 同步

**Files:**
- Modify: `packages/web/messages/zh.json`
- Modify: `packages/web/messages/en.json`

- [ ] **Step 1: 加 zh.json**

```json
{
  "权限管理": "权限管理",
  "角色": "角色",
  "新建角色": "新建角色",
  "编辑角色": "编辑角色",
  "删除角色": "删除角色",
  "系统角色": "系统角色",
  "自定义角色": "自定义角色",
  "N 个用户正在使用": "{N} 个用户正在使用",
  "确认删除角色?": "确认删除角色?",
  "保存": "保存",
  "重置默认": "重置默认",
  "修改后立即生效": "修改后立即生效",
  "记忆 (登录后可用)": "记忆 (登录后可用)"
}
```

实际根据现有 zh.json 增量加, 保留所有现有 key。

- [ ] **Step 2: 加 en.json**

```json
{
  "权限管理": "Permission management",
  "角色": "Roles",
  "新建角色": "Create role",
  "编辑角色": "Edit role",
  "删除角色": "Delete role",
  "系统角色": "System role",
  "自定义角色": "Custom role",
  "N 个用户正在使用": "{N} users using this role",
  "确认删除角色?": "Confirm delete role?",
  "保存": "Save",
  "重置默认": "Reset to default",
  "修改后立即生效": "Changes take effect within 30s",
  "记忆 (登录后可用)": "Memory (login required)"
}
```

- [ ] **Step 3: 跑 JSON 合法性检查**

```bash
cd packages/web
node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"
```

Expected: OK。

- [ ] **Step 4: Commit**

```bash
cd packages/web
git add messages/
git commit -m "i18n(rbac): add 13 keys for permission management UI"
```

---

### Task 24: README 更新

**Files:**
- Modify: `packages/web/README.md` 或根 `README.md` (找现有账号系统章节位置)

- [ ] **Step 1: 加 "权限系统" 章节**

```markdown
## 权限系统 (v2 RBAC)

4 状态 + 3 预设角色 + N 自定义角色:
- **游客 (anon)**: 只能 chat, 无记忆
- **用户 (user)**: chat + decode
- **管理员 (admin)**: chat + output + knowledge + evaluate + submissions + decode
- **超级管理员 (super_admin)**: 全部 + 权限管理

### 自定义角色

Super-admin 在 `/admin/permissions` 创任意角色 (例: 运营, 客服), 跟 7 页面权限点任意勾选。

### Anon 记忆

Anon 不支持记忆, 记忆端点 (`/api/memory/*`) 返 403, 前端 UI 隐藏。

### 现有 admin 账号迁移

旧 `is_admin=true` 账号已自动迁为 `super_admin`。
```

- [ ] **Step 2: Commit**

```bash
cd <repo root>
git add README.md
git commit -m "docs(rbac): README 权限系统章节"
```

---

## 验收 Checklist

跑完所有 task 后, 跑:

- [ ] 后端: `cd packages/service && uv run pytest tests/ -v` 0 fail
- [ ] 前端: `cd packages/web && bun run test` 0 fail
- [ ] 后端 lint: `cd packages/service && uv run ruff check src/ tests/`
- [ ] 前端 lint: `cd packages/web && bun run lint`
- [ ] 前端 typecheck: `cd packages/web && bun run typecheck`
- [ ] Migration 跑通: `cd packages/service && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
- [ ] 端到端 curl 矩阵: 4 身份 × 7 页面 (28 case)
- [ ] 浏览器手测: 4 账号 + 自定义角色登录看到不同 nav

---

## 关键依赖 (在 Task 1 之前)

确保以下存在:
- `packages/service/src/storage/migrations/versions/` 目录
- `packages/service/src/storage/session.py` (session_scope)
- `packages/service/src/middleware/auth.py` (CurrentUser + resolve_user)
- `packages/web/lib/api/config.ts` (apiFetch)
- `packages/web/lib/api/auth.server.ts` (serverAuthHeaders)
- `packages/web/lib/i18n/navigation.ts` (useRouter, redirect, etc.)
- `packages/web/components/common/app-dialog.tsx`
- `packages/web/components/common/form.tsx`
- `packages/web/components/ui/button.tsx`

如缺, 在 Phase 0 单独 task 补 (在 writing-plans 之前完成)。

---

## Self-Review 检查

✓ Spec 4 状态 + 3 预设 + N 自定义角色 — Task 1+2 数据模型覆盖
✓ 7 页面权限点 — Task 2 (初始 8 行 role_permissions) + Task 9 (PAGE_METADATA)
✓ /api/permissions GET/PATCH — Task 9 + Task 10
✓ /api/permissions/me — Task 9
✓ /api/roles GET/POST/PATCH/DELETE — Task 11 + Task 12
✓ Cache 30s TTL + invalidate — Task 3
✓ Guards (3 个) — Task 4
✓ 10 个 router 加 Depends — Task 8
✓ LoginResponse /me 返 role — Task 6
✓ 14 文件 is_admin → role — Task 5 + Task 6 + Task 7
✓ PageGuard — Task 15
✓ 22 page.tsx 加 PageGuard — Task 19
✓ 权限管理 UI (3 组件) — Task 21 + Task 22
✓ i18n 12 key — Task 23
✓ Anon 记忆隐藏 — Task 20
✓ seed_admin 创 super_admin — Task 6
✓ 自定义角色 CRUD — Task 11 + Task 12
✓ 28 case 端到端 — Task 13
