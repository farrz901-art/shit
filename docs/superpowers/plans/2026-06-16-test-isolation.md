# 测试隔离整改 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删 `_truncate_tables` autouse fixture + top-level re-export, 杜绝"dev DB 跑 test 必清数据"事故; 12 个真用 PG 的 test 改用事务回滚 + 90 个单测保持 0 依赖.

**Architecture:**
- 删 `tests/storage/conftest.py` 的 `_truncate_tables` (autouse)
- 删 `tests/conftest.py` 的 re-export + autouse 副作用
- 新建 `tests/integration/conftest.py` 暴露 `db_session` 事务回滚 fixture (opt-in)
- 12 个真连 PG 的 test 改 fixture 依赖, 跑完 rollback 0 残留
- 90 个纯单测 0 改动 (本身就不依赖 PG)
- CLAUDE.md 加 1 节 "测试隔离 4 模式" 防下次写测试的人造新 shim

**Tech Stack:**
- Python 3.14
- pytest 9.0.3 (现有)
- SQLAlchemy 2.0 (现有)
- 不用新依赖 (项目惯例: stdlib + 已装库)

**Spec:** [../specs/2026-06-16-test-isolation-design.md](../specs/2026-06-16-test-isolation-design.md)
**当前 commit:** `<pending user commit of 8 files>`

---

## 文件结构总览 (6 任务, 0.5d 估)

| 任务 | 工作量 | 核心文件改动 |
|---|---|---|
| 0 基线 + 数据保护 | 0.05d | (只跑测试, 不改代码) |
| 1 删 autouse 清理 | 0.05d | `tests/storage/conftest.py` + `tests/conftest.py` |
| 2 写 db_session 事务回滚 fixture | 0.1d | 新建 `tests/integration/conftest.py` |
| 3 迁 12 个 test 到 db_session | 0.2d | `tests/{auth,approvals,eval,storage}/*` |
| 4 CLAUDE.md 加测试隔离 4 模式 | 0.05d | `packages/service/CLAUDE.md` |
| 5 全量回归 + 验收 | 0.05d | (只跑测试) |

**并行性**: 任务 1 跟 2 必须顺序, 任务 3 (12 test 迁移) 拆 4 个子 commit 可并行, 任务 4 独立.

---

## Task 0: 基线 + 数据保护

**Files:** (无改动, 只跑)

- [ ] **Step 1: 跑全量非 slow 测试做基线**

```bash
cd packages/service && uv run pytest tests/ -m "not slow" --collect-only 2>&1 | tail -5
```

期望: 100+ tests collected, 没 collection error.

- [ ] **Step 2: 备份当前 dev DB 数据 (防止后面迁崩了没退路)**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['RAG_DB_URL'])
with e.connect() as c:
    for tbl in ('accounts', 'users', 'approvals', 'kg_audit'):
        cnt = c.execute(text(f'SELECT COUNT(*) FROM {tbl}')).scalar()
        print(f'{tbl}: {cnt} rows')
" 2>&1 | tail -10
```

期望: 现在 0 rows (之前 TRUNCATE 过). 即使是 0 也记下, 防止后面"以为有但实际没".

---

## Task 1: 删 autouse 清理 (根除)

**Files:**
- Modify: `packages/service/tests/storage/conftest.py:30-67`
- Modify: `packages/service/tests/conftest.py:7-15`

- [ ] **Step 1: 写验证脚本 (跑测试无 autouse 副作用)**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['RAG_DB_URL'])
with e.connect() as c:
    c.execute(text('INSERT INTO accounts (id, email, password_hash, is_admin, is_active, created_at) VALUES (1, \\\"probe@x.com\\\", \\\"h\\\", false, true, NOW())'))
    print('inserted probe row')
" 2>&1 | tail -3
```

期望: 1 row inserted (probe).

- [ ] **Step 2: 跑一个不需 PG 的 test (test_docs_structure), 验证有 autouse 会清掉 probe**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/test_docs_structure.py -v 2>&1 | tail -10
```

```bash
# 再查 probe 还在不在
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['RAG_DB_URL'])
with e.connect() as c:
    print('probe exists:', c.execute(text(\"SELECT COUNT(*) FROM accounts WHERE email='probe@x.com'\")).scalar())
" 2>&1 | tail -3
```

期望: probe 不存在 (0) — 证明 autouse 当前会清, 这就是我们要修的 bug.

- [ ] **Step 3: 删 `tests/storage/conftest.py` 的 `_truncate_tables` (L30-67)**

删除 L30-67 整段 (autouse fixture + TRUNCATE 实现), 保留:
- `pg_engine` (L13-27)
- `tmp_db_url` (L73-79)
- `reset_storage_engine` (L82-94)

- [ ] **Step 4: 改 `tests/storage/conftest.py` 顶部 docstring**

**改前**:
```python
"""storage 测试 fixture (PG only, 2026-06-15)

提供 pg_engine + 每次测试清表的 autouse fixture.
"""
```

**改后**:
```python
"""storage 测试 fixture (PG only)

提供 pg_engine session-scope + opt-in tmp_db_url / reset_storage_engine.
注意: 这里**不**定义 autouse fixture — 跟 dev DB 共享的项目不允许全局清表.
测试需要 PG 数据用 tests/integration/conftest.py 的 db_session (事务回滚, 0 残留).
"""
```

- [ ] **Step 5: 删 `tests/conftest.py` 顶层的 re-export**

**改前**:
```python
# noqa: F401 — 副作用: 让 _truncate_tables 的 autouse 在所有 tests/ 子目录生效
from tests.storage.conftest import (
    _truncate_tables,  # noqa: F401
    pg_engine,  # noqa: F401
    reset_storage_engine,  # noqa: F401
    tmp_db_url,  # noqa: F401
)
```

**改后**:
```python
"""tests/ 顶层 conftest

pytest 找 conftest 向父级走, tests/<subdir>/conftest.py 不会被顶层这个 re-export.
每个需要 PG 的 test 自己用 `from tests.integration.conftest import db_session`.
这里**不**re-export 任何 autouse fixture, 跟 dev DB 共享的项目不允许全局副作用.
"""
```

- [ ] **Step 6: 跑基线验证 autouse 真删了**

```bash
# 1) 重新插入 probe
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['RAG_DB_URL'])
with e.connect() as c:
    c.execute(text('INSERT INTO accounts (id, email, password_hash, is_admin, is_active, created_at) VALUES (1, \\\"probe@x.com\\\", \\\"h\\\", false, true, NOW())'))
" 2>&1 | tail -2

# 2) 跑不需 PG 的 test (有 env 但应不触发 TRUNCATE)
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/test_docs_structure.py -v 2>&1 | tail -5

# 3) 验证 probe 还在
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['RAG_DB_URL'])
with e.connect() as c:
    print('probe exists:', c.execute(text(\"SELECT COUNT(*) FROM accounts WHERE email='probe@x.com'\")).scalar())
" 2>&1 | tail -3
```

期望: `probe exists: 1` — autouse 删了, dev DB 不再被清.

- [ ] **Step 7: Commit**

```bash
git add packages/service/tests/conftest.py packages/service/tests/storage/conftest.py
git commit -m "test: 删 _truncate_tables autouse fixture + top-level re-export

根除\"dev DB 跑 test 必清数据\"反模式 (2026-06-15 事故: test_docs_structure.py
触发 autouse 清了 dev DB 全部业务表).

改动:
- tests/storage/conftest.py: 删 _truncate_tables (autouse + TRUNCATE 实现)
- tests/storage/conftest.py: docstring 改为说明不走 autouse, 用 db_session
- tests/conftest.py: 删 _truncate_tables re-export + 顶部 docstring 重写
- tests/conftest.py: 注释说明不 re-export 任何 autouse

跟 spec 模式 1 (纯单测, mock) + 模式 2 (事务回滚) 一致; 模式 3 (临时 schema) + 模式 4
(独立测试 DB) 见 spec §决策, 本期不实现.

后续 task 迁 12 个真用 PG 的 test 改用 db_session (opt-in, 0 残留)."
```

---

## Task 2: 写 db_session 事务回滚 fixture (模式 2)

**Files:**
- Create: `packages/service/tests/integration/conftest.py`

- [ ] **Step 1: 写失败测试 (验 db_session 0 残留)**

新建 `packages/service/tests/integration/test_db_session_fixture.py`:

```python
"""验 db_session fixture 0 残留 (事务回滚)

核心断言: 每个 test 在自己事务里改, 完事 rollback → dev DB 不动.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text


@pytest.fixture
def db_session(pg_engine):  # pg_engine 必被 import 才能让 pytest 知道有依赖
    raise NotImplementedError  # 故意失败, 红


def test_db_session_rollback_zero_residue(pg_engine):
    """用 raw SQL 验证 rollback: 插行, 完事查应 0 行."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    try:
        connection.execute(text(
            "INSERT INTO accounts (email, password_hash, is_admin, is_active, created_at) "
            "VALUES ('rollback_test@x.com', 'h', false, true, '2026-06-16')"
        ))
        # 事务内能查到
        in_txn = connection.execute(text(
            "SELECT COUNT(*) FROM accounts WHERE email='rollback_test@x.com'"
        )).scalar()
        assert in_txn == 1
    finally:
        transaction.rollback()
        connection.close()

    # 事务外 (新连接) 应查不到
    with pg_engine.connect() as c:
        after = c.execute(text(
            "SELECT COUNT(*) FROM accounts WHERE email='rollback_test@x.com'"
        )).scalar()
    assert after == 0
```

- [ ] **Step 2: 跑确认红**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/integration/test_db_session_fixture.py -v 2>&1 | tail -10
```

期望: FAIL (db_session fixture 还没实现, NotImplementedError).

- [ ] **Step 3: 写 db_session fixture (tests/integration/conftest.py)**

新建 `packages/service/tests/integration/conftest.py`:

```python
"""集成测试 conftest (PG only, 模式 2: 事务回滚)

db_session fixture: 每个 test 一个事务, 完事 rollback → 0 残留.
这是 _truncate_tables 替代方案: 同样 test 间隔离, 但不动 dev DB.

用法:
    def test_x(db_session):
        acc = Account(email='x@x.com')
        db_session.add(acc)
        db_session.commit()  # 显式 commit 在事务内
        # test 完事 transaction.rollback() 自动, 数据 0 残留
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def db_session(pg_engine):
    """每个 test 一个事务, 完事 rollback. 验 SQL 行为用这个, 别用 autouse TRUNCATE."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    Session_ = sessionmaker(bind=connection, expire_on_commit=False)
    session = Session_()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()  # 关键: test 数据全回滚, dev DB 0 影响
        connection.close()
```

- [ ] **Step 4: 跑测试确认绿**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/integration/test_db_session_fixture.py -v 2>&1 | tail -10
```

期望: PASS (1/1).

- [ ] **Step 5: 跑全量非 slow 测试确认无回归 (Task 1 删 autouse 后的基线)**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/ -m "not slow" --co 2>&1 | tail -5
```

期望: 100+ tests collected, 没 collection error. 跑 5 个真用 `pg_engine` 的 test 可能红 (Task 3 再修).

- [ ] **Step 6: Commit**

```bash
git add packages/service/tests/integration/conftest.py packages/service/tests/integration/test_db_session_fixture.py
git commit -m "test: 加 db_session 事务回滚 fixture (模式 2)

替代 _truncate_tables autouse: 同样 test 间隔离, 事务回滚 0 残留,
不动 dev DB. 1 个 fixture + 1 个回归 test."
```

---

## Task 3: 迁 12 个 test 到 db_session (4 个子 commit, 可并行)

按目录拆 4 个子 task, 每个 1 commit.

### Task 3.1: 迁 `tests/approvals/`

**Files:**
- Modify: `tests/approvals/test_repo.py` (主要)

- [ ] **Step 1: grep approvals 目录用 pg_engine 的 test**

```bash
cd packages/service && grep -l "pg_engine\|tmp_db_url" tests/approvals/ -r 2>&1 | head -5
```

期望: `test_repo.py` 是主要文件, 可能还有其他.

- [ ] **Step 2: 改 fixture 依赖: `pg_engine` → `db_session`**

对每个匹配的 test 文件, 把:
```python
def test_x(pg_engine):
    ...
```
改成:
```python
def test_x(db_session):
    ...
```

- [ ] **Step 3: 跑 approvals 测试**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/approvals/ -v 2>&1 | tail -10
```

期望: 全部 PASS (或 skip 跟之前一样, **不能 fail**).

- [ ] **Step 4: Commit**

```bash
git add tests/approvals/
git commit -m "test(approvals): 改用 db_session 替 pg_engine

0 残留事务回滚替 autouse TRUNCATE, dev DB 跟 test 隔离."
```

### Task 3.2: 迁 `tests/auth/`

**Files:**
- Modify: `tests/auth/test_account_models.py` (用 pg_engine)
- Modify: `tests/auth/test_admin_users_api.py` (用 TestClient + pg_engine)
- Modify: `tests/auth/test_invite_flow.py`
- Modify: `tests/auth/test_login.py`
- Modify: `tests/auth/test_me.py`
- Modify: `tests/auth/test_middleware_integration.py`
- Modify: `tests/auth/test_password_reset.py`

- [ ] **Step 1: grep auth 目录**

```bash
cd packages/service && grep -l "pg_engine\|tmp_db_url" tests/auth/ -r 2>&1 | head -10
```

- [ ] **Step 2: 改 fixture 依赖**

对每个文件, 替换 `pg_engine`/`tmp_db_url` → `db_session` (或 `TestClient` + `db_session` 如果是 router test).

- [ ] **Step 3: 跑 auth 测试**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/auth/ -v 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add tests/auth/
git commit -m "test(auth): 改用 db_session 替 pg_engine / tmp_db_url

7 个 test 迁完. 0 残留事务回滚替 autouse TRUNCATE."
```

### Task 3.3: 迁 `tests/eval/`

**Files:**
- Modify: `tests/eval/test_runner.py` (主要)

- [ ] **Step 1: grep eval 目录**

```bash
cd packages/service && grep -l "pg_engine\|tmp_db_url" tests/eval/ -r 2>&1 | head -5
```

- [ ] **Step 2: 改 fixture 依赖**

- [ ] **Step 3: 跑 eval 测试**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/eval/ -v 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add tests/eval/
git commit -m "test(eval): 改用 db_session 替 pg_engine

test_runner 迁完. 0 残留事务回滚."
```

### Task 3.4: 迁 `tests/storage/`

**Files:**
- Modify: `tests/storage/test_session.py` (用 pg_engine 测 session_scope)
- Modify: `tests/storage/test_migrations.py` (改临时 schema 模式, 模式 3)

- [ ] **Step 1: grep storage 目录**

```bash
cd packages/service && grep -l "pg_engine\|tmp_db_url" tests/storage/ -r 2>&1 | head -5
```

- [ ] **Step 2: 改 fixture 依赖 (test_session.py 用 db_session, test_migrations.py 暂留 pg_engine 因为 alembic 跑 schema 切换复杂)**

- [ ] **Step 3: 跑 storage 测试**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/storage/ -v 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add tests/storage/
git commit -m "test(storage): test_session 改 db_session (test_migrations 留 pg_engine)

test_session 迁完. test_migrations 跟 alembic 跑 schema 切换留待模式 3 实现."
```

---

## Task 4: CLAUDE.md 加测试隔离 4 模式 (防下次写错)

**Files:**
- Modify: `packages/service/CLAUDE.md` (或在 docs/ 加新文档)

- [ ] **Step 1: 找 CLAUDE.md 测试规范章节**

```bash
cd packages/service && grep -n "测试\|test\|fixture" CLAUDE.md 2>&1 | head -10
```

- [ ] **Step 2: 加 "测试隔离 4 模式" 章节**

在 CLAUDE.md 现有测试规范后加:

```markdown
## 测试隔离 4 模式 (2026-06-16 整改后强制)

写新 test 前, **先确认用哪个模式**, 跟现有 100 个 test 保持一致:

| 模式 | 适用 | Fixture | 不该做 |
|---|---|---|---|
| 1 纯单测 (mock) | ORM 字段 / Pydantic / 纯函数 / util | 0 PG 依赖, 用 `monkeypatch` / `unittest.mock` | **不要**连 PG |
| 2 集成 (事务回滚) | repo CRUD / SQL 行为 / FK 约束 | `db_session` (opt-in, 自动 rollback) | **不要**TRUNCATE / autouse 副作用 |
| 3 迁移 (临时 schema) | alembic DDL / schema 完整性 | `tmp_pg_schema` (CREATE/DROP SCHEMA) | **不要**用公共 public schema |
| 4 E2E (独立测试 DB) | 完整业务流 / CI 全套 | `RAG_DB_URL=...rag_test` 独立 DB | **不要**用 dev DB (`rag`) |

**反模式 (2026-06-15 事故根因)**:
- ❌ `_truncate_tables` autouse fixture (强制清表, 跟 dev DB 共享必炸数据)
- ❌ `tests/conftest.py` top-level re-export 让 autouse 跨目录
- ❌ 写新 test 时 "凭直觉造 fixture" (应该问: 我用 4 模式里哪个?)

新 test 选错模式 → 跟事故 user 复盘, spec [2026-06-16-test-isolation-design.md](../specs/2026-06-16-test-isolation-design.md) §4 种模式看完整对比.
```

- [ ] **Step 3: Commit**

```bash
git add packages/service/CLAUDE.md
git commit -m "docs(service): CLAUDE.md 加测试隔离 4 模式章节

防下次写 test 的人再造 autouse TRUNCATE 之类的 shim.
跟 spec 2026-06-16-test-isolation-design.md §决策 对齐."
```

---

## Task 5: 全量回归 + 验收

**Files:** (无改动)

- [ ] **Step 1: 跑全量非 slow 测试 (无 RAG_DB_URL, 验纯单测不连 PG)**

```bash
cd packages/service && uv run pytest tests/ -m "not slow" 2>&1 | tail -10
```

期望: 全 PASS 或 SKIP (不连 PG 的 SKIP, 90+ test 跑过).

- [ ] **Step 2: 跑全量测试 (有 RAG_DB_URL, 验 PG 集成测试用 db_session 0 残留)**

```bash
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/ -m "not slow" 2>&1 | tail -10
```

期望: 全 PASS.

- [ ] **Step 3: 验证 dev DB 数据 0 影响**

```bash
# 1) 插 probe
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['RAG_DB_URL'])
with e.connect() as c:
    c.execute(text('INSERT INTO accounts (id, email, password_hash, is_admin, is_active, created_at) VALUES (1, \\\"probe@x.com\\\", \\\"h\\\", false, true, NOW())'))
" 2>&1 | tail -2

# 2) 跑全量测试
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run pytest tests/ -m "not slow" 2>&1 | tail -3

# 3) 验 probe 还在
cd packages/service && RAG_DB_URL="postgresql+psycopg://postgres:deyuan888@localhost:5432/rag" \
  uv run python -c "
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ['RAG_DB_URL'])
with e.connect() as c:
    print('probe exists:', c.execute(text(\"SELECT COUNT(*) FROM accounts WHERE email='probe@x.com'\")).scalar())
" 2>&1 | tail -3
```

期望: `probe exists: 1` — 测试套件不再清 dev DB.

- [ ] **Step 4: 验收 grep `_truncate_tables` 0 匹配**

```bash
cd packages/service && grep -r "_truncate_tables" tests/ 2>&1 | head -5
```

期望: 无输出.

- [ ] **Step 5: 跟 spec 校验 6 个验收标准**

- [ ] `_truncate_tables` 完全删, grep 0 匹配 ✓ (Step 4)
- [ ] `tests/conftest.py` top-level 不 re-export `_truncate_tables` ✓ (Task 1)
- [ ] 100 个 test 全跑通 ✓ (Step 1+2)
- [ ] dev DB 跑 test 0 影响 ✓ (Step 3)
- [ ] CLAUDE.md 加 4 模式 ✓ (Task 4)
- [ ] CI 独立 DB (后续 spec, 本期不卡)

---

## 风险与回滚

参见 [spec §风险与缓解](../specs/2026-06-16-test-isolation-design.md#风险与缓解).

简述:
- Task 1 改 conftest: 1 个 commit, 删错了 revert 即回
- Task 3 迁 12 test: 4 个子 commit 独立, 任一失败 revert 那个
- Task 4 改 CLAUDE.md: 纯文档, 错改 revert 即回
- 跟 dev DB 共享的事故不会复现: Task 1 删 autouse 是单向的, 不会"不小心"加回来

---

## 跟其他 spec/plan 的关联

- [2026-06-15-chat-sse-refactor-design.md](2026-06-15-chat-sse-refactor-design.md) — 同样规格化流程模板
- [2026-06-15-sqlite-to-pgvector-migration-design.md](2026-06-15-sqlite-to-pgvector-migration-design.md) — 数据迁移相关
- [project-rag-shim-audit-2026-06-08](project-rag-shim-audit-2026-06-08.md) — autouse TRUNCATE 算广义 shim, 本 spec 是清理
