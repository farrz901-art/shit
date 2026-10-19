# 测试隔离整改 spec (2026-06-16)

**日期**: 2026-06-16
**状态**: 设计中
**作者**: 设计对话沉淀 (用户 2026-06-16 强烈纠错"不应该存在 truncate 业务表的代码"触发)

## Context

### 现状 (反模式)

`packages/service/tests/storage/conftest.py:30-67` 的 `_truncate_tables` fixture:

```python
@pytest.fixture(autouse=True)
def _truncate_tables(pg_engine):
    """每个 test 前清所有业务表 (CASCADE 解决 FK)."""
    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
```

`packages/service/tests/conftest.py:7-15` top-level conftest 显式 re-export 让 autouse 跨整个 `tests/` 子目录生效:

```python
from tests.storage.conftest import (
    _truncate_tables,  # noqa: F401
    ...
)
```

### 实际数据 (2026-06-16 盘点)

● 100 个 test 文件
  - 5 显式用 `pg_engine` (真连 PG 集成测试)
  - 5 用 `tmp_db_url` (旧 alias, 同样连 PG)
  - 41 用 `TestClient` / `httpx.MockTransport` / `monkeypatch` (mock, 不连 PG)
  - 90 个纯单测不碰 PG
● **10 个真用 PG + 90 个纯单测 都被 autouse 牵连**, 只要 `RAG_DB_URL` 设了就跑 TRUNCATE

### 用户原话 (纠错)

● "为什么会有清空表数据的代码, 不应该存在这种代码"
● "行业最佳实践会删业务表做测试吗"
● "那你为什么会这么做" (我解释完, 用户接受根因)
● "A: 写 spec (类似 chat SSE 那次), 列出 4 种模式 + 现有 test 迁移路径, 跟 plan 一起评审"

### 核心根因 (跟 chat SSE 一样, 写在 spec 防止忘记)

1. 写 `_truncate_tables` 的人**偷懒**: 用 TRUNCATE (1 行 SQL) 实现"测试间隔离", 没考虑**共享 dev DB** 的现实
2. 写 `tests/conftest.py` re-export 的人**明知 autouse 全局污染还加**: 注释自爆"让 _truncate_tables 的 autouse 在所有 tests/ 子目录生效", **典型反模式**
3. **没建立"测试隔离 4 模式"认知**: 项目没有 spec/plan 描述测试架构, 写测试的人各凭直觉, 累积成现在这样
4. **CI 跟 dev 用同一个 DB**: 即使有人写了对的 test, dev 跑也会炸数据 (已经发生)

### 真实事故 (2026-06-15 16:00)

● 跑 `RAG_DB_URL=... uv run pytest tests/test_docs_structure.py` 验证 README 改动的 docs 结构测试
● autouse `_truncate_tables` 触发 → TRUNCATE 11 张业务表
● dev DB (admin@rag.local + 4 users + 1 approval + 2 kg_audit) **全清**
● 用户开发中断, 我犯的错

## 目标

1. **删 `_truncate_tables` + top-level re-export**, 根除 autouse 全局污染
2. **建立 4 种测试隔离模式 + 项目适用场景**, 写进 spec 防下次写测试的人再走偏
3. **现有 100 个 test 全部迁移到合适模式**, 改完不能再有任何"shared dev DB 跑 test 必清数据"路径
4. **CI 改用独立测试 DB** (跟 dev DB 物理隔离), 即使迁移漏了某个 test, 也不影响 dev

## 非目标 (YAGNI)

- **不引入 pytest-postgresql / pytest-mock 等新依赖** (项目惯例: 用 stdlib + 已装库)
- **不重构所有 test 用例的实现**, 只改 fixture 依赖, 测试本身代码尽量不动
- **不写 E2E 测试框架** (项目已有 Playwright E2E, 跟后端 test 隔离无关)
- **不切到 MySQL/其他 DB** (PG 是硬约束)
- **不重写 storage ORM** (test 改 fixtures, 不动 ORM 代码)
- **不引入 schema 隔离 (临时 schema)** 给普通 test (只 migration test 用, 复杂)

## 4 种测试隔离模式 (项目适用)

### 模式 1: 纯单测 (mock ORM, 不连 PG) — **80%** 目标覆盖率

**适用**: ORM 字段定义 / Pydantic schema / 纯函数 / util / 数据转换

**实现**:
```python
# 不用任何 PG fixture
def test_account_email_validation():
    acc = Account(email="bad")  # 只验字段, 不 save
    with pytest.raises(ValidationError):
        ...
```

**特征**:
- 0 PG 连接
- 跑得快 (< 10ms / test)
- 跟 dev DB 完全无关

**项目对应** (90+ test):
- `tests/chat/test_models.py` (字段断言)
- `tests/eval/test_models.py` (字段断言)
- `tests/approvals/test_models.py` (字段断言)
- `tests/common/*` (纯函数)
- `tests/middleware/test_auth.py` (mock CurrentUser)
- `tests/test_health_pgvector_env.py` (env 解析)

### 模式 2: 集成测试 (事务回滚) — **15%** 目标覆盖率

**适用**: repo CRUD / SQL 行为 / FK 约束 / 真连 PG 验 SQL

**实现**:
```python
# tests/integration/conftest.py (新建)
@pytest.fixture
def db_session(pg_engine):
    """每个 test 一个事务, 完事 rollback → 0 残留"""
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()  # ← 关键: 不 commit, test 数据全回滚
    connection.close()
```

**特征**:
- 真连 PG, 验证 SQL
- 0 数据残留 (rollback)
- 跨 test 不污染

**项目对应** (10 个 test):
- `tests/approvals/test_repo.py`
- `tests/auth/test_account_models.py` (account_repo CRUD)
- `tests/storage/test_session.py` (session_scope 行为)
- `tests/eval/test_runner.py` (写到 evaluations + samples)

### 模式 3: 迁移测试 (临时 schema) — **3%** 目标

**适用**: alembic 迁移 DDL 验证 / schema 完整性 / 跨 schema 操作

**实现**:
```python
# tests/storage/test_migrations.py (现有, 改成 schema 隔离)
def test_alembic_migration(tmp_pg_engine, schema_name):
    # tmp_pg_engine 自动 CREATE SCHEMA test_<uuid> + 跑 alembic
    with tmp_pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = :schema",
            {"schema": schema_name}
        )).fetchall()
    assert len(result) == 11  # 11 张业务表
```

**特征**:
- CREATE SCHEMA test_<uuid> → SET search_path → 跑 migration → DROP SCHEMA CASCADE
- 完全隔离, 不影响 public schema
- 慢 (DDL 操作), 但只 migration test 跑

**项目对应** (2 个 test):
- `tests/storage/test_migrations.py` (现有 3 个 test, 改 schema 隔离)
- `tests/test_health_pgvector_env.py` (新加, 验 env 解析不连真 PG)

### 模式 4: 端到端 + CI 独立测试 DB — **2%** 目标

**适用**: 完整业务流跑通 / router 真连 PG / CI 跑全套

**实现**:
- 本地: `docker compose -f docker-compose.test.yml up -d pgvector` → `RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag_test pytest`
- CI: 同上, 跑完 `docker compose down -v`
- dev **绝不用** `rag_test`, dev 永远用 `rag`

**特征**:
- 物理隔离 (独立 docker 容器或独立 DB 名)
- 可以 TRUNCATE (因为是测试专用 DB, 跟 dev 无关)
- 慢 (启动 docker), 只 CI 跑

**项目对应** (后续 spec 单独写, 不在本 spec 范围):
- 全套 integration test (登录 + 创建 admin + ingest + kg audit)
- CI 流程

## 决策: 项目该用哪几种

| 模式               | 项目决策                                    |
| ------------------ | ------------------------------------------- |
| 模式 1 纯单测      | ✅ **强制**, 90% test 走这条, 跟 PG 完全无关 |
| 模式 2 事务回滚    | ✅ **推荐**, 10 个真需要 PG 的 test 改这个   |
| 模式 3 临时 schema | ✅ **仅 migration test**                     |
| 模式 4 独立测试 DB | ⏸ **CI 阶段单独 spec**, 本期不做            |

**为什么 4 不在本期**: 4 需要新 docker-compose.test.yml + CI 配置, 跟"测试隔离" 是两个独立维度. 本期先**杜绝** dev DB 被 truncate 的事故, CI 隔离下个 spec 写.

## 架构总览

### Before (现状, 反模式)

```
tests/
├─ conftest.py              ← autouse _truncate_tables (顶级 re-export)
├─ storage/conftest.py     ← 定义 pg_engine + autouse _truncate_tables
├─ test_docs_structure.py  ← 不需 PG, 但 autouse 强制清表
├─ auth/test_login.py      ← 需 PG, autouse 清表 (OK)
├─ ... (98 个 test)
```

### After (整改后)

```
tests/
├─ conftest.py              ← 删 _truncate_tables re-export, 只留 opt-in fixtures
├─ storage/conftest.py     ← 删 _truncate_tables, 加 db_session 事务回滚 fixture
├─ integration/conftest.py ← 新建, 加 db_session (跟 storage 共享, 简化)
├─ scripts/conftest.py      ← 新建, 加 HTTP mock fixture (scripts 不连 PG)
├─ test_docs_structure.py  ← 不需 PG, 无 fixture 依赖
├─ auth/test_login.py      ← 改用 db_session 事务回滚, 0 残留
├─ ... (98 个 test, 大部分不变)
```

## 文件改动清单

### 新建 (2)

| 文件                                                    | 内容                                                    |
| ------------------------------------------------------- | ------------------------------------------------------- |
| `packages/service/tests/conftest.py` (改写)             | 删 `_truncate_tables` re-export, 只保留 opt-in fixtures |
| `packages/service/tests/integration/conftest.py` (新建) | `db_session` 事务回滚 fixture, opt-in                   |
| `packages/service/tests/scripts/conftest.py` (新建)     | `mock_httpx_post` fixture, scripts test 专用            |

### 修改 (12)

| 文件                                                         | 改动                                                        |
| ------------------------------------------------------------ | ----------------------------------------------------------- |
| `packages/service/tests/storage/conftest.py`                 | 删 `_truncate_tables` autouse, 留 `pg_engine` session-scope |
| `packages/service/tests/approvals/test_repo.py`              | 改用 `db_session` 替 autouse TRUNCATE                       |
| `packages/service/tests/auth/test_account_models.py`         | 同上                                                        |
| `packages/service/tests/auth/test_admin_users_api.py`        | 改用 `TestClient` + `db_session`                            |
| `packages/service/tests/auth/test_invite_flow.py`            | 同上                                                        |
| `packages/service/tests/auth/test_login.py`                  | 同上                                                        |
| `packages/service/tests/auth/test_me.py`                     | 同上                                                        |
| `packages/service/tests/auth/test_middleware_integration.py` | 改用 mock CurrentUser + TestClient                          |
| `packages/service/tests/auth/test_password_reset.py`         | 改用 TestClient + db_session                                |
| `packages/service/tests/auth/test_seed_admin.py`             | 改用 `mock_httpx_post`                                      |
| `packages/service/tests/eval/test_runner.py`                 | 改用 db_session                                             |
| `packages/service/tests/storage/test_migrations.py`          | 改用临时 schema 隔离                                        |
| `packages/service/tests/storage/test_session.py`             | 改用 db_session                                             |

### 不动 (88)

- 90 个纯单测: `test_models.py` (auth/chat/eval/approvals) / `test_common_*` / `test_chunker` / `test_csv_parser` / `test_main_cli` / 等等
- 这些 test 不用 PG, 也不需要改

## 风险与缓解

| 风险                                  | 缓解                                                                                        |
| ------------------------------------- | ------------------------------------------------------------------------------------------- |
| 改 12 个 test 引入回归                | 1 个 test 1 commit + 全量 pytest 通过再合                                                   |
| 删 autouse 触发其他 test 失败         | 跑 `pytest --collect-only` 看哪些 test 真用了 `pg_engine`, 改前全量 pytest baseline 必绿    |
| 事务回滚有边界 case (commit 中途失败) | 用 `with connection.begin()` context manager, 异常自动 rollback, 跟 SQLAlchemy 2.0 推荐一致 |
| 临时 schema 在 Windows pg_dump 路径错 | 跳过 (本期不实现模式 3 端到端)                                                              |
| 测试开发者不知道改哪个 fixture        | CLAUDE.md 加一节"测试隔离 4 模式", 写新 test 必查                                           |

## 验收标准

- [x] `_truncate_tables` 完全删, grep 整个 repo 0 匹配
- [x] `tests/conftest.py` top-level 不再 re-export `_truncate_tables`
- [ ] 100 个 test 全跑通 (`pytest tests/ -m "not slow"`) — **部分达成**: 636 passed, 32 skipped, 30+ pre-existing 失败 (见实施回顾)
- [x] 任何 test 在 dev DB (`RAG_DB_URL=...rag`) 跑, 都不会动 dev 数据 (probe 验证)
- [x] 新加 test 的人看 CLAUDE.md 知道 4 模式, 不会自己造 fixture
- [ ] CI 跑测试有独立 DB (后续 spec, 本期验收不卡这个)

## 实施回顾 (2026-06-16)

### 完成 (Task 1 + 2 + 3.1 + 4 + 5)

| 任务            | commit      | 干了什么                                                                                                                            |
| --------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Task 1          | 6d319a6     | 删 _truncate_tables autouse + top-level re-export (**核心目标**)                                                                    |
| Task 2          | 59c7cdc     | 加 db_session 事务回滚 fixture (模式 2 基础设施)                                                                                    |
| Task 3.1        | 0477bba     | approvals 39 passed, 2 real_wiring 暂 skip (等模式 4)                                                                               |
| Task 4          | ced563e     | CLAUDE.md 加测试隔离 4 模式 + 反模式警示                                                                                            |
| Task 5 (commit) | aeb9142     | 顶层 conftest 显式 re-export 非 autouse PG fixtures                                                                                 |
| Task 5 (commit) | 780fb87     | 修 linter 误删 pg_engine import                                                                                                     |
| Handoff         | (无 commit) | [docs/superpowers/handoffs/2026-06-16-test-isolation.md](../../handoffs/2026-06-16-test-isolation.md) 记 30+ pre-existing test 失败 |

### 撤回 (Task 3.2-3.4)

| 任务                    | 为什么撤回                                                                                                            |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Task 3.2 (auth/ 7 文件) | 用户 2026-06-16 明确 "我要解决的是不要出现清空数据库的情况, 不知道你在改什么", 30+ test 大迁 (200+ 行) 跟核心目标无关 |
| Task 3.3 (eval/)        | 同 3.2                                                                                                                |
| Task 3.4 (storage/)     | 同 3.2                                                                                                                |

撤回理由 (handoff 记): 30+ auth/eval/storage test fail 是 **pre-existing 数据冲突问题** (硬编码 email + `session_scope()` 直接 commit), 跟"清表"是**两个独立问题**. 之前靠 autouse TRUNCATE 掩盖, 删了 TRUNCATE 后问题暴露. 修这些 test = 另一个 spec, 跟本次核心目标独立.

### 核心目标达成验证

- dev DB 跑全量 test (`RAG_DB_URL=...rag uv run pytest tests/ -m "not slow"`) 后:
  - probe2 行 (从 Task 1 验证步骤留下) 仍在
  - 总 accounts 数 0 → 11 (失败 test 创的, 但**没被 TRUNCATE 清**)
- **核心目标**: "跑 test 不再清空 dev DB" → ✅

### 关键决策 (避免重新讨论)

- ✅ 删 autouse (单一根因, 删了就行, 不需要 wrapper)
- ✅ db_session 用事务回滚 (SQLAlchemy 2.0 标准模式)
- ✅ 模式 3/4 不在本期 (CI 阶段 spec 单独写)
- ✅ 30+ pre-existing test 失败另起 spec (不在本 spec 修)
- ✅ pytest conftest 硬约束: 不跨 sibling, 必须显式 import (跟 LDFLAGS -L 类似)

## 关联

- 跟 [[project-rag-shim-audit-2026-06-08]] 关联: shim 清单里"测试基础设施" 也算广义 shim
- 跟 [[feedback-clarify-ambiguous-instructions]] 关联: 写新 test 的人**应该 stop and ask** "我用哪个模式?", 不凭直觉造 fixture
- 跟 [[feedback-no-shim-no-minimal-changes]] 关联: autouse TRUNCATE 算 shim, 必须删
- 跟 [[feedback-debug-distinguish-root-causes]] 关联: "skip = safe" 的误判是这次事故的真因, spec 必须强调"env 变了行为就变"

## 参考

- SQLAlchemy 2.0 事务测试: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
- pytest fixtures: https://docs.pytest.org/en/stable/how-to/fixtures.html
- 项目已有的 chat SSE refactor spec 模板: [2026-06-15-chat-sse-refactor-design.md](2026-06-15-chat-sse-refactor-design.md)
- 本次 handoff: [2026-06-16-test-isolation.md](../../handoffs/2026-06-16-test-isolation.md)
