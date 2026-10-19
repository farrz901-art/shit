# PostgreSQL JSON/JSONB 一族 bug 根治方案 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复后端 JSON/JSONB 一族 bug 的 1 个活漏洞 (error_logs sink), 把 5 个历史 `sa.JSON()` 列迁到 `JSONB`, 加防回归测试 + 编码规范, 让此族 bug 不再复发.

**Architecture:** 分 4 阶段 — (A) 1 行修活 bug · (B) 5 列 `sa.JSON()` → `JSONB` 整表迁移 + 业务读写端同步 · (C) AST/regex 防回归测试 · (D) CLAUDE.md 规范 + cookbook 教程. B 是生产 DDL 改动 (锁表分钟级), 必须分小步独立 commit + 数据 dry-run.

**Tech Stack:** SQLAlchemy 2.0 / psycopg3 / Alembic / Pydantic v2 / pytest (模式 1 mock + 模式 2 db_session) / loguru

**Background (重要 — 阅读前请先看):**
- [docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md](../handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md) — 系统性根因 + 6 个共因
- [packages/service/CLAUDE.md §测试隔离 4 模式](../../../packages/service/CLAUDE.md) — 测试模式
- 项目铁律 [CLAUDE.md](../../../CLAUDE.md) — 顺序: format → lint → type → test → commit
- 调研结论: 现状已经相当健康, 只剩 1 个真活漏洞 + 5 个历史 `json` 列(无 GIN, 业务已加 `_parse_meta` 兜底)

---

## File Structure

### 新建文件

| 路径 | 责任 |
|---|---|
| `packages/service/src/storage/migrations/versions/20260626_000000_migrate_sa_json_to_jsonb.py` | 5 列 `json → jsonb` ALTER + 可回滚 downgrade |
| `packages/service/tests/migrations/__init__.py` | 包标记 (空文件) |
| `packages/service/tests/migrations/test_json_jsonb_policy.py` | AST parse, 禁止新增 `sa.JSON()` (白名单 = 5 个迁移文件) |
| `packages/service/tests/migrations/test_jsonb_raw_sql_cast.py` | regex, 禁止 raw SQL 写 jsonb 列不带 cast |
| `docs/cookbook/python/jsonb-usage.md` | 完整 JSONB 教程 (cookbook 风格) |

### 修改文件

| 路径 | 行 | 改动 |
|---|---|---|
| `packages/service/src/core/logging.py` | 102-120 | `_error_sink_sync` 加 `bindparam("ctx", type_=JSONB)`, 跟 `_pg_sink_app` (line 71) 对齐 |
| `packages/service/src/chat/models.py` | 87 | `mapped_column(JSON, ...)` → `mapped_column(JSONB, ...)` |
| `packages/service/src/eval/models.py` | 50, 93, 96, 97 | 4 处 `JSON` → `JSONB` |
| `packages/service/src/chat/service.py` | 364-368 | raw SQL 写 messages.meta 改成 `CAST(:meta AS jsonb)` + 传 dict 不传字符串 |
| `packages/service/src/chat/service.py` | 20-36 | `_parse_meta` 兜底保留 (历史脏数据 + mock 兼容), 加注释说明 |
| `packages/service/CLAUDE.md` | 文件末尾 | 加 §JSONB 使用规范章节 |

### 测试覆盖

- 模式 1 (mock, AST/regex): `test_json_jsonb_policy.py` / `test_jsonb_raw_sql_cast.py` — 防回归
- 模式 2 (db_session, 集成测): 已有的 `tests/buyer_profile/test_migration.py` 已覆盖 JSONB 列, 新 migration 在 dev DB upgrade head 验证
- 现有 chat / eval tests: 类型改 JSONB 后 mock 给 dict / 给 str 两种输入都跑

---

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| `messages` 表大, ALTER 锁表数分钟 | 每列独立 ALTER (5 条 op.execute), 维护窗口跑; dev 先验, 生产分批 |
| 历史脏数据 `::jsonb` cast 失败一行整表回滚 | upgrade 前先 dry-run `SELECT meta::jsonb FROM messages WHERE meta IS NOT NULL LIMIT 1` 验证全可解析 |
| 业务代码删 `_parse_meta` 兜底, 历史脏 row 仍是 str | 保留兜底, 注释标记 "JSONB 迁移后冗余, 留作向后兼容" |
| Alembic chain 冲突 (跟之前 20260624 双 head 同样问题) | 新 migration revision = `20260626_000000`, down = `20260624_170000`, 单 head |
| 防回归测试白名单太宽放走真 bug | 白名单写死 5 个文件名 (migration 历史), 新增 `sa.JSON()` 必触发 |

---

## Task 0: 准备工作 + dry-run 验证

**Files:**
- 无新建/修改, 仅验证 dev DB 状态

- [ ] **Step 1: 确认 alembic 当前 head**

```bash
cd packages/service && uv run alembic current
uv run alembic heads
```

Expected:
- `current` = `20260624_170000 (head)` (或同等)
- `heads` 输出仅 1 行

如果 head 不是 `20260624_170000`, **停下来跟用户确认** — 别盲目 upgrade, 可能漂移.

- [ ] **Step 2: dry-run 5 列 jsonb cast 可行性**

```bash
cd packages/service && uv run python -c "
from sqlalchemy import create_engine, text
from src.core.config import get_rag_db_url
eng = create_engine(get_rag_db_url())
with eng.connect() as c:
    for tbl, col in [
        ('messages', 'meta'),
        ('evaluations', 'avg_metrics'),
        ('evaluation_samples', 'contexts'),
        ('evaluation_samples', 'metrics'),
        ('evaluation_samples', 'sources'),
    ]:
        n = c.execute(text(f'SELECT COUNT(*) FROM {tbl} WHERE {col} IS NOT NULL')).scalar()
        if n == 0:
            print(f'OK {tbl}.{col} 0 rows')
            continue
        try:
            c.execute(text(f'SELECT ({col})::jsonb FROM {tbl} WHERE {col} IS NOT NULL LIMIT 5')).all()
            print(f'OK {tbl}.{col} {n} rows cast ok')
        except Exception as e:
            print(f'FAIL {tbl}.{col} {n} rows: {e}')
"
```

Expected: 5 行 OK (任一 FAIL 必须先清脏数据再进 Task 3 迁移).

- [ ] **Step 3: 备份 dev DB (可选, 但强烈推荐)**

```bash
pg_dump -h localhost -U postgres -d rag -F c -f /tmp/rag_before_jsonb_migrate.dump
```

Expected: dump 文件存在, 大小 > 0.

- [ ] **Step 4: 跑现有完整 test suite 拿基线**

```bash
cd packages/service && uv run pytest -x -q --no-cov 2>&1 | tail -20
```

Expected: 记录通过/失败数 (~1075 passed / 22 failed / 38 errors 按 KNOWN_ISSUES.md), 后续任务不能引入新 fail.

- [ ] **Step 5: 无 commit (本任务仅验证, 无代码改动)**

---

## Task A: 修活 bug — `_error_sink_sync` 加 bindparam JSONB

**Files:**
- Modify: `packages/service/src/core/logging.py:102-120`

- [ ] **Step 1: 写失败测试**

新建 `packages/service/tests/core/test_logging_error_sink.py`:

```python
"""error_logs sink JSONB bindparam 修复 (2026-06-25 json-jsonb spec Task A)

测试模式 1 (mock): 验证 _error_sink_sync 用 bindparam(type_=JSONB) 包装 stmt,
不走真 PG.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy.dialects.postgresql import JSONB

from src.core.logging import _error_sink_sync


def test_error_sink_uses_jsonb_bindparam():
    """_error_sink_sync 写 error_logs.context 必须用 bindparam(type_=JSONB).

    防回归: 不加 bindparam 时, psycopg3 传非空 dict 会抛
    'cannot adapt type dict using placeholder %s'.
    """
    captured_stmt = {}

    class _FakeSession:
        def execute(self, stmt, params):
            captured_stmt["stmt"] = stmt
            captured_stmt["params"] = params

    class _CtxMgr:
        def __enter__(self):
            return _FakeSession()
        def __exit__(self, *a):
            return False

    with patch("src.storage.session_scope", return_value=_CtxMgr()):
        req = MagicMock()
        req.url.path = "/api/foo"
        req.method = "POST"
        _error_sink_sync("ERROR", RuntimeError("boom"), req)

    stmt = captured_stmt["stmt"]
    # SQLAlchemy TextClause.bindparams 标过类型后, _bindparams dict 含 ctx 项 + type_ 是 JSONB
    bind = stmt._bindparams.get("ctx")
    assert bind is not None, "ctx 参数未声明 bindparam"
    assert isinstance(bind.type, JSONB), f"ctx 应是 JSONB, 实际 {type(bind.type).__name__}"
```

- [ ] **Step 2: 跑测试验证失败**

```bash
cd packages/service && uv run pytest tests/core/test_logging_error_sink.py -v --no-cov 2>&1 | tail -10
```

Expected: FAIL — `bind is None` 或 `bind.type` 不是 JSONB.

- [ ] **Step 3: 改 `_error_sink_sync` 加 bindparam JSONB**

编辑 [packages/service/src/core/logging.py:101-120](packages/service/src/core/logging.py#L101-L120):

```python
# 修改前 (line 101-120)
with session_scope() as s:
    s.execute(
        text(
            "INSERT INTO error_logs (ts, level, exception_type, exception_msg, "
            "stacktrace, request_id, user_id, path, method, status_code, context) "
            "VALUES (NOW(), :level, :type, :msg, :trace, :rid, :uid, "
            ":path, :method, :code, :ctx)"
        ),
        {
            "level": level,
            ...
            "ctx": _scrub({}),
        },
    )

# 修改后
with session_scope() as s:
    # context 列是 JSONB, 显式声明类型让 psycopg 自动 adapt dict → JSONB.
    # 跟 _pg_sink_app (line 71) 对齐, 不加 bindparam 时非空 dict 会抛
    # "cannot adapt type 'dict' using placeholder '%s'" (psycopg3 v3 adapter 协议).
    stmt = text(
        "INSERT INTO error_logs (ts, level, exception_type, exception_msg, "
        "stacktrace, request_id, user_id, path, method, status_code, context) "
        "VALUES (NOW(), :level, :type, :msg, :trace, :rid, :uid, "
        ":path, :method, :code, :ctx)"
    ).bindparams(bindparam("ctx", type_=JSONB))
    s.execute(
        stmt,
        {
            "level": level,
            ...
            "ctx": _scrub({}),
        },
    )
```

确认 [logging.py:8-12](packages/service/src/core/logging.py#L8-L12) 顶部已有 `from sqlalchemy import bindparam, text` + `from sqlalchemy.dialects.postgresql import JSONB` (已 import, 不用动).

- [ ] **Step 4: 跑测试验证通过**

```bash
cd packages/service && uv run pytest tests/core/test_logging_error_sink.py -v --no-cov 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 5: 跑 lint + type + 完整 logging 模块测试**

```bash
cd packages/service && uv run ruff format src/core/logging.py tests/core/test_logging_error_sink.py
uv run ruff check src/core/logging.py tests/core/test_logging_error_sink.py
uv run pyright src/core/logging.py tests/core/test_logging_error_sink.py
uv run pytest tests/core/ -v --no-cov 2>&1 | tail -20
```

Expected: 0 format change · 0 lint error · 0 pyright error · 现有 core tests 全过 + 新 test 过.

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/core/logging.py packages/service/tests/core/test_logging_error_sink.py
git commit -m "fix(logging): _error_sink_sync 加 JSONB bindparam (json-jsonb spec Task A)

跟 _pg_sink_app 对齐, 防 5xx handler 写 error_logs.context 非空 dict 时
psycopg3 抛 'cannot adapt type dict using placeholder %s'.

详见 docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md"
```

---

## Task B1: 写 ALTER migration 文件

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260626_000000_migrate_sa_json_to_jsonb.py`

- [ ] **Step 1: 创建 migration 文件**

写入 [packages/service/src/storage/migrations/versions/20260626_000000_migrate_sa_json_to_jsonb.py](packages/service/src/storage/migrations/versions/20260626_000000_migrate_sa_json_to_jsonb.py):

```python
"""migrate 5 sa.JSON() 历史列 → JSONB (json-jsonb spec Task B1)

背景: 2026-06-15 consolidated_pg_init.py 用 sa.JSON() 给 5 列定义 PG json 类型
(text-based, 不支持 GIN jsonb_path_ops). 这些列虽然没用 JSONB operator, 但跟
psycopg3 v3 adapter 协议交互不稳 — 同源踩坑见
docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md

5 列:
  - messages.meta
  - evaluations.avg_metrics
  - evaluation_samples.contexts
  - evaluation_samples.metrics
  - evaluation_samples.sources

注意:
1. dry-run 已验证全部行可 ::jsonb cast (Task 0 Step 2).
2. ALTER 锁表分钟级, 维护窗口跑, 不要在高峰期 upgrade.
3. downgrade 走 ::json cast, 数据语义保留但格式 (空格/键序) 丢失.
"""

from __future__ import annotations

from alembic import op

revision: str = "20260626_000000"
down_revision: str | None = "20260624_170000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """5 列 json → jsonb (USING col::jsonb)."""
    op.execute("ALTER TABLE messages ALTER COLUMN meta TYPE jsonb USING meta::jsonb")
    op.execute(
        "ALTER TABLE evaluations ALTER COLUMN avg_metrics TYPE jsonb USING avg_metrics::jsonb"
    )
    op.execute(
        "ALTER TABLE evaluation_samples ALTER COLUMN contexts TYPE jsonb USING contexts::jsonb"
    )
    op.execute(
        "ALTER TABLE evaluation_samples ALTER COLUMN metrics TYPE jsonb USING metrics::jsonb"
    )
    op.execute(
        "ALTER TABLE evaluation_samples ALTER COLUMN sources TYPE jsonb USING sources::jsonb"
    )


def downgrade() -> None:
    """回滚: jsonb → json (USING col::json, 数据保留语义)."""
    op.execute("ALTER TABLE messages ALTER COLUMN meta TYPE json USING meta::json")
    op.execute(
        "ALTER TABLE evaluations ALTER COLUMN avg_metrics TYPE json USING avg_metrics::json"
    )
    op.execute(
        "ALTER TABLE evaluation_samples ALTER COLUMN contexts TYPE json USING contexts::json"
    )
    op.execute(
        "ALTER TABLE evaluation_samples ALTER COLUMN metrics TYPE json USING metrics::json"
    )
    op.execute(
        "ALTER TABLE evaluation_samples ALTER COLUMN sources TYPE json USING sources::json"
    )
```

- [ ] **Step 2: 验证 alembic 单 head + 解析无错**

```bash
cd packages/service && uv run alembic heads 2>&1 | tail -5
uv run alembic history --rev-range 20260624_170000:20260626_000000 2>&1 | tail -10
```

Expected:
- `heads` 输出仅 `20260626_000000 (head)`
- history 显示新 revision 串在 `20260624_170000` 之后

- [ ] **Step 3: 跑 upgrade head (dev DB 真跑)**

```bash
cd packages/service && uv run alembic upgrade head 2>&1 | tail -10
```

Expected: 5 行 `Running upgrade ... ALTER ...`, exit 0.

- [ ] **Step 4: 验证 DB 列类型已切换**

```bash
cd packages/service && uv run python -c "
from sqlalchemy import create_engine, text
from src.core.config import get_rag_db_url
eng = create_engine(get_rag_db_url())
with eng.connect() as c:
    rows = c.execute(text('''
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE (table_name, column_name) IN (
            ('messages','meta'),('evaluations','avg_metrics'),
            ('evaluation_samples','contexts'),('evaluation_samples','metrics'),
            ('evaluation_samples','sources')
        )
        ORDER BY table_name, column_name
    ''')).all()
    for r in rows:
        print(r)
"
```

Expected: 5 行全部 `data_type == 'jsonb'`.

- [ ] **Step 5: 跑 downgrade -1 验证回滚干净**

```bash
cd packages/service && uv run alembic downgrade -1 2>&1 | tail -10
# 验证回到 json
uv run python -c "
from sqlalchemy import create_engine, text
from src.core.config import get_rag_db_url
eng = create_engine(get_rag_db_url())
with eng.connect() as c:
    t = c.execute(text(\"SELECT data_type FROM information_schema.columns WHERE table_name='messages' AND column_name='meta'\")).scalar()
    print(f'messages.meta type after downgrade: {t}')
"
# 再 upgrade 回 head
uv run alembic upgrade head 2>&1 | tail -3
```

Expected:
- downgrade exit 0, `messages.meta` type = `json`
- upgrade head exit 0

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/storage/migrations/versions/20260626_000000_migrate_sa_json_to_jsonb.py
git commit -m "feat(migration): 20260626 5 列 sa.JSON → JSONB (json-jsonb spec Task B1)

5 列: messages.meta / evaluations.avg_metrics / evaluation_samples.{contexts,metrics,sources}
upgrade: ALTER ... TYPE jsonb USING col::jsonb (dev DB dry-run 已验证 0 脏数据)
downgrade: jsonb → json 可逆 (语义保留, 格式丢失)

详见 docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md"
```

---

## Task B2: ORM model 6 处 `JSON` → `JSONB`

**Files:**
- Modify: `packages/service/src/chat/models.py:87`
- Modify: `packages/service/src/eval/models.py:50, 93, 96, 97`

- [ ] **Step 1: 改 chat/models.py:87**

确认 [packages/service/src/chat/models.py](packages/service/src/chat/models.py) 顶部 import:

```python
# 加 (顶部 from sqlalchemy 后面)
from sqlalchemy.dialects.postgresql import JSONB
```

改 line 87:

```python
# 修改前
meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

# 修改后
# 列类型 jsonb (2026-06-26 migration 迁过, 原 sa.JSON 已废弃).
# psycopg3 读 jsonb 直接返 dict, 写时直接传 dict (不用 json.dumps).
meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

删除原 `from sqlalchemy import JSON` 中的 `JSON`(若该 import 仅服务于这一列). 用 grep 确认:

```bash
cd packages/service && grep -n "JSON" src/chat/models.py
```

如果还有别处用 `JSON`, 保留 import; 否则改成不含 `JSON`.

- [ ] **Step 2: 改 eval/models.py 4 处**

确认 [packages/service/src/eval/models.py](packages/service/src/eval/models.py) 顶部加 `from sqlalchemy.dialects.postgresql import JSONB`.

改 line 50:

```python
# 修改前
avg_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

# 修改后
avg_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

改 line 93, 96, 97 (contexts / sources / metrics) 同样模式:

```python
contexts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

清理 sqlalchemy `JSON` import 同上.

- [ ] **Step 3: 跑相关测试 + lint**

```bash
cd packages/service && uv run ruff format src/chat/models.py src/eval/models.py
uv run ruff check src/chat/models.py src/eval/models.py
uv run pyright src/chat/models.py src/eval/models.py
uv run pytest tests/chat/ tests/eval/ -v --no-cov 2>&1 | tail -30
```

Expected:
- 0 format / lint / type error
- chat/eval 现有 test 全过 (模式 1 mock, 类型改 JSONB 不影响 mock 行为)

- [ ] **Step 4: Commit**

```bash
git add packages/service/src/chat/models.py packages/service/src/eval/models.py
git commit -m "refactor(orm): chat.messages / eval 5 列 JSON → JSONB (json-jsonb spec Task B2)

跟 2026-06-26 migration 对齐 (PG 列已切 jsonb).
psycopg3 读 jsonb 直接返 dict, 后续 Task B3 改业务读写端."
```

---

## Task B3: 业务读写端配合改

**Files:**
- Modify: `packages/service/src/chat/service.py:20-36` (`_parse_meta` 加注释保留)
- Modify: `packages/service/src/chat/service.py:362-368` (写 raw SQL 改 cast)

- [ ] **Step 1: 在 `_parse_meta` 加注释说明保留意图**

编辑 [packages/service/src/chat/service.py:20-36](packages/service/src/chat/service.py#L20-L36):

```python
# 修改前
def _parse_meta(meta):
    """SA 2.0 + psycopg3 + sa.JSON() 读出可能是 dict 不是 str, 统一兜底.

    同个坑踩了 4 次, 抽函数防回归.
    ...
    """
    if meta is None:
        return None
    if isinstance(meta, dict):
        return meta
    return json.loads(meta)

# 修改后
def _parse_meta(meta):
    """messages.meta 读出兜底 (向后兼容).

    历史背景 (2026-06-24): SA 2.0 + psycopg3 + sa.JSON() 读 PG json 列可能给 dict 或 str.
    2026-06-26 migration 已把列迁到 JSONB, psycopg3 一致返 dict.

    本函数保留作向后兼容:
    - 历史脏数据 (迁移前残留为 str 的边角 case)
    - 单测 mock 给 dict / str 都跑通
    - 防回归 (未来某天再退回 json 类型时不立刻炸)
    """
    if meta is None:
        return None
    if isinstance(meta, dict):
        return meta
    return json.loads(meta)
```

- [ ] **Step 2: 改 messages.meta 写 raw SQL 用 CAST**

定位 [packages/service/src/chat/service.py:362-368](packages/service/src/chat/service.py#L362-L368) 附近 (raw SQL `INSERT INTO messages ... meta`).

```python
# 修改前 (示意, 实际行号视代码而定)
s.execute(
    text(
        "INSERT INTO messages (..., meta) VALUES (..., :meta)"
    ),
    {..., "meta": json.dumps(meta) if meta else None},
)

# 修改后
# JSONB 列, CAST(:meta AS jsonb) 显式标类型, 让 psycopg 自动 adapt dict.
# 也可以走 bindparam(type_=JSONB), 跟 _pg_sink_app 一致. 这里选 CAST 是因为
# raw SQL 跟周围 buyer_profile 模式对齐.
s.execute(
    text(
        "INSERT INTO messages (..., meta) VALUES (..., CAST(:meta AS jsonb))"
    ),
    {..., "meta": json.dumps(meta) if meta else None},  # 仍传字符串, CAST 解析
)
```

**注意**: 也可以直接传 dict + `bindparam("meta", type_=JSONB)`, 看跟现有风格那种更一致 — 推荐先看周围代码, 若多处都是 `json.dumps(...)` + cast 模式则保持; 若已切 bindparam 则全 bindparam.

- [ ] **Step 3: 跑 chat 完整测试**

```bash
cd packages/service && uv run ruff format src/chat/service.py
uv run ruff check src/chat/service.py
uv run pyright src/chat/service.py
uv run pytest tests/chat/ -v --no-cov 2>&1 | tail -30
```

Expected: 0 format / lint / type error · chat tests 全过.

- [ ] **Step 4: 手测一遍真路径 (重要 — 模式 2 跑不到 mock 的话, 手测真 PG)**

```bash
# 1. 启动后端
cd packages/service && uv run python main.py serve &
sleep 5

# 2. curl 发一条消息 (含 meta), 看 200
curl -X POST http://localhost:8000/api/chat/conversations \
  -H "Content-Type: application/json" \
  -H "x-user-token: dev" \
  -d '{"title": "jsonb-test"}'
# 拿 conv_id, 再 POST 一条 message 带 meta {"model": "test"}
# 然后 GET /api/chat/conversations/<id>/messages 看返回 meta 是 dict 不是 str

# 3. 看后端日志, 不应有 ValidationError / cannot adapt
```

Expected: 200 + meta 字段 type=dict.

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/chat/service.py
git commit -m "refactor(chat): messages.meta 读写端配合 JSONB 迁移 (json-jsonb spec Task B3)

- 写: raw SQL 加 CAST(:meta AS jsonb), psycopg3 不再误 adapt
- 读: _parse_meta() 保留作向后兼容 (历史脏数据 + mock 兼容)
- 手测真路径 OK"
```

---

## Task C1: AST 防回归测试 — 禁止新增 `sa.JSON()`

**Files:**
- Create: `packages/service/tests/migrations/__init__.py` (空文件)
- Create: `packages/service/tests/migrations/test_json_jsonb_policy.py`

- [ ] **Step 1: 创建包 `__init__.py`**

写入 [packages/service/tests/migrations/__init__.py](packages/service/tests/migrations/__init__.py):

```python
"""migration 防回归测试 (json-jsonb spec)"""
```

- [ ] **Step 2: 创建测试文件**

写入 [packages/service/tests/migrations/test_json_jsonb_policy.py](packages/service/tests/migrations/test_json_jsonb_policy.py):

```python
"""禁止新增 sa.JSON() — 必须用 JSONB (json-jsonb spec Task C1).

测试模式 1 (mock, AST parse): 0 PG 依赖.

历史白名单 = 1 个 migration (2026-06-15 consolidated_pg_init).
2026-06-26 migration 已把这 5 列迁到 JSONB, 白名单按理应清空, 但保留作历史档案
(白名单文件本身已经把 sa.JSON 改成 JSONB 不是再创建 — 这里防的是新引入).

跟 tests/buyer_profile/test_migration.py 同款 AST 风格.
"""

from __future__ import annotations

import ast
from pathlib import Path

# 历史白名单 (这些文件曾经引入过 sa.JSON, 不阻止留作历史档案).
# 注意: 这些文件本身不应再含 sa.JSON 调用 — 白名单只表示"扫到 ast.Call sa.JSON 不报警".
# 但实际上历史 migration 已经凝固, 不再改; 列在白名单里只是表明"这是历史, 任何新行都禁止".
LEGACY_ALLOWLIST: set[str] = {
    "20260615_000000_consolidated_pg_init.py",
}


def _migration_dir() -> Path:
    return Path(__file__).parent.parent.parent / "src" / "storage" / "migrations" / "versions"


def _find_sa_json_calls(tree: ast.Module) -> list[ast.Call]:
    """提取 AST 里所有 `sa.JSON()` / `sqlalchemy.JSON()` / `JSON()` (from sqlalchemy import JSON) 调用."""
    found: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # sa.JSON() or sqlalchemy.JSON()
        if isinstance(func, ast.Attribute) and func.attr == "JSON":
            if isinstance(func.value, ast.Name) and func.value.id in ("sa", "sqlalchemy"):
                found.append(node)
        # 裸 JSON() — from sqlalchemy import JSON 后调用
        # (不强查, AST 看不到 import 来源, 容易误报; 只查 attribute 形式)
    return found


def test_no_new_sa_json_in_migrations():
    """禁止新 migration 用 sa.JSON()."""
    migration_dir = _migration_dir()
    assert migration_dir.exists(), f"migration dir 不存在: {migration_dir}"

    violations: list[str] = []
    for py in migration_dir.glob("*.py"):
        if py.name == "__init__.py" or py.name in LEGACY_ALLOWLIST:
            continue
        source = py.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = _find_sa_json_calls(tree)
        for call in calls:
            violations.append(f"{py.name}:{call.lineno} 用了 sa.JSON() — 必须用 JSONB")

    assert not violations, "\n".join(violations) + "\n\n修法: from sqlalchemy.dialects.postgresql import JSONB"


def test_legacy_allowlist_files_exist():
    """白名单文件存在 (防写错文件名)."""
    migration_dir = _migration_dir()
    for fname in LEGACY_ALLOWLIST:
        assert (migration_dir / fname).exists(), f"白名单文件不存在: {fname}"
```

- [ ] **Step 3: 跑测试验证 PASS (现有 migration 已健康)**

```bash
cd packages/service && uv run pytest tests/migrations/test_json_jsonb_policy.py -v --no-cov 2>&1 | tail -10
```

Expected: 2 passed (现有 migration 除白名单外 0 个 `sa.JSON()`).

- [ ] **Step 4: 手测白名单生效 — 临时塞个违规, 测试该 FAIL**

```bash
cd packages/service
# 临时加个违规
echo "sa.JSON()  # test only" >> src/storage/migrations/versions/20260626_000000_migrate_sa_json_to_jsonb.py
uv run pytest tests/migrations/test_json_jsonb_policy.py -v --no-cov 2>&1 | tail -10
# 应该 FAIL
# 回滚
git checkout src/storage/migrations/versions/20260626_000000_migrate_sa_json_to_jsonb.py
uv run pytest tests/migrations/test_json_jsonb_policy.py -v --no-cov 2>&1 | tail -5
# 应该 PASS
```

Expected: 加违规后 FAIL, 回滚后 PASS.

- [ ] **Step 5: 跑 lint + format**

```bash
cd packages/service && uv run ruff format tests/migrations/
uv run ruff check tests/migrations/
uv run pyright tests/migrations/
```

Expected: 全过.

- [ ] **Step 6: Commit**

```bash
git add packages/service/tests/migrations/
git commit -m "test(migrations): 防 sa.JSON() 回归 AST 测试 (json-jsonb spec Task C1)

扫所有 migration 文件 (除白名单 1 个历史文件), 禁止新 sa.JSON() 调用.
配合 Task B 已迁移的 5 列, 守门未来 PR."
```

---

## Task C2: regex 防回归测试 — JSONB raw SQL 必须 cast

**Files:**
- Create: `packages/service/tests/migrations/test_jsonb_raw_sql_cast.py`

- [ ] **Step 1: 写测试**

写入 [packages/service/tests/migrations/test_jsonb_raw_sql_cast.py](packages/service/tests/migrations/test_jsonb_raw_sql_cast.py):

```python
"""禁止 raw SQL INSERT/UPDATE jsonb 列时传裸 :param (json-jsonb spec Task C2).

测试模式 1 (mock, regex): 0 PG 依赖.

扫 src/ 下所有 .py, 找 text("INSERT/UPDATE ... :ctx|:meta|:before|:after|:context|:metadata|:payload"),
断言上下文 (前后 5 行) 含 CAST / ::jsonb / bindparam(.*JSONB) / json.dumps(.

不是 100% 严密 (regex 静态扫), 但能拦最常见的 "裸传 dict" 模式.
"""

from __future__ import annotations

import re
from pathlib import Path

# JSONB 列名族 (项目里 JSONB 列的典型命名)
JSONB_COL_NAMES = ("ctx", "context", "meta", "metadata", "before", "after", "payload", "merge", "data")

# 安全模式 (出现任一即放过)
SAFE_PATTERNS = [
    re.compile(r"CAST\s*\(\s*:[a-z_]+\s+AS\s+jsonb\s*\)", re.IGNORECASE),  # CAST(:p AS jsonb)
    re.compile(r"::jsonb\b"),                                                  # :p::jsonb / col::jsonb
    re.compile(r"bindparam\s*\(\s*[\"'][a-z_]+[\"']\s*,\s*type_\s*=\s*JSONB"),  # bindparam("p", type_=JSONB)
    re.compile(r"json\.dumps\s*\("),                                            # 预序列化为字符串再传
]


def _src_dir() -> Path:
    return Path(__file__).parent.parent.parent / "src"


def _scan_file_for_jsonb_writes(py: Path) -> list[tuple[int, str, str]]:
    """返回 [(lineno, line, neighborhood)] 命中需要检查的位置."""
    text = py.read_text(encoding="utf-8")
    lines = text.splitlines()
    hits: list[tuple[int, str, str]] = []

    # 找含 INSERT/UPDATE + JSONB 列名族 + :param 的位置
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "INSERT" not in stripped.upper() and "UPDATE" not in stripped.upper():
            continue
        for col in JSONB_COL_NAMES:
            # 简陋判断 = SQL 里出现该列名 (作为列名引用)
            if f" {col}" in line or f",{col}" in line or f"({col}" in line:
                # 看上下文 ±10 行内有没有 :param 跟这列绑
                start = max(0, i - 10)
                end = min(len(lines), i + 11)
                neighborhood = "\n".join(lines[start:end])
                if re.search(r":[a-z_]+", neighborhood):
                    hits.append((i + 1, line.strip(), neighborhood))
                break  # 一条 SQL 一行只看一次
    return hits


def test_jsonb_raw_sql_writes_have_cast_or_bindparam():
    """所有 raw SQL 写 JSONB 列的位置, 必须有 CAST/::jsonb/bindparam JSONB/json.dumps."""
    src = _src_dir()
    assert src.exists()

    violations: list[str] = []
    for py in src.rglob("*.py"):
        if "__pycache__" in py.parts or "tests" in py.parts:
            continue
        hits = _scan_file_for_jsonb_writes(py)
        for lineno, line, neighborhood in hits:
            # 上下文里命中任一安全模式 → 放过
            if any(p.search(neighborhood) for p in SAFE_PATTERNS):
                continue
            rel = py.relative_to(src.parent.parent.parent)
            violations.append(f"{rel}:{lineno} 写 JSONB 列裸 :param, 缺 CAST/::jsonb/bindparam JSONB/json.dumps\n  {line}")

    assert not violations, "\n\n".join(violations)
```

- [ ] **Step 2: 跑测试**

```bash
cd packages/service && uv run pytest tests/migrations/test_jsonb_raw_sql_cast.py -v --no-cov 2>&1 | tail -10
```

Expected: PASS (调研报告确认所有写位都已有 CAST/bindparam/json.dumps).

- [ ] **Step 3: 手测 — 临时引入违规验证 FAIL**

```bash
cd packages/service
# 在 logging.py 临时改回去 (删 bindparam)
# (这步只是验测试有效, 改完恢复)
# ... 改 ...
uv run pytest tests/migrations/test_jsonb_raw_sql_cast.py -v --no-cov 2>&1 | tail -10
# 应 FAIL
# 恢复
git checkout src/core/logging.py
uv run pytest tests/migrations/test_jsonb_raw_sql_cast.py -v --no-cov 2>&1 | tail -5
# 应 PASS
```

Expected: 改回去 FAIL, 恢复 PASS.

- [ ] **Step 4: 跑 lint + format**

```bash
cd packages/service && uv run ruff format tests/migrations/test_jsonb_raw_sql_cast.py
uv run ruff check tests/migrations/test_jsonb_raw_sql_cast.py
uv run pyright tests/migrations/test_jsonb_raw_sql_cast.py
```

Expected: 全过.

- [ ] **Step 5: Commit**

```bash
git add packages/service/tests/migrations/test_jsonb_raw_sql_cast.py
git commit -m "test(migrations): 防 JSONB raw SQL 裸 :param 回归 regex 测试 (json-jsonb spec Task C2)

扫 src/ 所有 raw SQL 写 JSONB 列的位置, 必须有 CAST / ::jsonb / bindparam JSONB / json.dumps 之一."
```

---

## Task D1: CLAUDE.md 加 JSONB 章节

**Files:**
- Modify: `packages/service/CLAUDE.md` (文件末尾追加新章节)

- [ ] **Step 1: 编辑 CLAUDE.md**

在 [packages/service/CLAUDE.md](packages/service/CLAUDE.md) 文件末尾 (跟其他章节风格一致) 追加:

```markdown
## JSONB 使用规范 (2026-06-25 json-jsonb spec)

### 新列必须 JSONB, 禁止 sa.JSON()

```python
# 旧 (禁用, 跨 dialect 抽象层泄漏)
sa.Column("data", sa.JSON())

# 新 (统一)
from sqlalchemy.dialects.postgresql import JSONB
sa.Column("data", JSONB())
```

测试 `tests/migrations/test_json_jsonb_policy.py` AST 扫所有 migration, 新增 `sa.JSON()` 必 FAIL.

### raw SQL 写 JSONB 列 3 种正确姿势 (任选, 项目内 3 种都有用)

```python
# A. SQL 内 cast (最直观, buyer_profile 用)
text("INSERT INTO buyer_profiles (..., profile_data) VALUES (..., CAST(:data AS jsonb))")
{"data": json.dumps(data)}  # 传字符串, CAST 解析

# B. bindparam 显式标类型 (最 ORM, logging.py 用)
from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql import JSONB
stmt = text("INSERT INTO app_logs (..., context) VALUES (..., :ctx)").bindparams(
    bindparam("ctx", type_=JSONB)
)
{"ctx": dict_value}  # 传 dict, psycopg3 自动 adapt

# C. 业务侧预序列化 + ::jsonb (chat 用)
text("INSERT INTO messages (..., meta) VALUES (..., :meta::jsonb)")
{"meta": json.dumps(meta)}
```

裸 `:p` 传 dict 必抛 `psycopg.ProgrammingError: cannot adapt type 'dict' using placeholder '%s'` — 测试 `tests/migrations/test_jsonb_raw_sql_cast.py` regex 扫.

### 读 JSONB 列禁止 `json.loads`, 直接当 dict 用

psycopg3 v3 注册了 jsonb loader, 读 JSONB 列 → dict; 读老 PG json 列 → str. 项目里 messages.meta 等历史列已迁 JSONB (2026-06-26 migration), 但保留 `_parse_meta()` 兜底, 兼容历史脏数据 + 单测 mock 给 str 也跑.

### psycopg3 v3 adapter 其他注意

- `INET` 列 (audit_logs.ip) 反序列化为 `ipaddress.IPv4Address`, Pydantic v2 不自动 coerce, 业务 stringify 边界
- `UUID` 列自动反序列化, OK
- 任何 PG 特殊类型给 Python 类型, 不能假设 == str

### 排查信号 (3 个错误关键词, 同源)

| 错误关键词 | 一定是 |
|---|---|
| `operator class "jsonb_path_ops" does not accept data type json` | sa.JSON() + JSONB opclass 不匹配 (migration) |
| `TypeError: the JSON object must be str, bytes or bytearray, not dict` | psycopg3 读 jsonb 返 dict, 业务 `json.loads` 误用 |
| `cannot adapt type 'dict' using placeholder '%s'` | raw SQL 没 cast, psycopg3 不知道 jsonb |

完整分析见 [docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md](../../docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md).
```

- [ ] **Step 2: lint 文档 (markdown 不需要 ruff, 但跑 grep 确认链接正确)**

```bash
cd c:/Users/abcuc/Desktop/rag
# 检查链接到的文件都存在
grep -oE '\[.*?\]\(.*?\)' packages/service/CLAUDE.md | tail -10
ls docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md
ls packages/service/tests/migrations/test_json_jsonb_policy.py
ls packages/service/tests/migrations/test_jsonb_raw_sql_cast.py
```

Expected: 全部 ls 命中.

- [ ] **Step 3: Commit**

```bash
git add packages/service/CLAUDE.md
git commit -m "docs(claudemd): 加 §JSONB 使用规范 (json-jsonb spec Task D1)

3 种 raw SQL 写法 / 读端不 json.loads / psycopg3 v3 adapter 注意 / 排查信号表."
```

---

## Task D2: 写 cookbook 教程

**Files:**
- Create: `docs/cookbook/python/jsonb-usage.md`

- [ ] **Step 1: 查 cookbook 已有风格 (3 篇样例)**

```bash
ls docs/cookbook/python/ 2>&1 | tail -10
```

Expected: 看到 `lookup.md`, `fastapi.md` 等 (用户在 git log 提到的). Read 1-2 篇看 layout.

- [ ] **Step 2: 写 jsonb-usage.md**

写入 [docs/cookbook/python/jsonb-usage.md](docs/cookbook/python/jsonb-usage.md):

```markdown
# PostgreSQL JSONB 字段使用教程

> 本文档面向 RAG 项目后端开发者. 不熟悉 PG JSONB 直接用本文 4 段 + 复制代码.
> 历史背景见 [2026-06-25-postgres-json-jsonb-family-bugs.md](../../superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md).

## 1. 什么时候用 JSONB

- 用 JSONB: 字段是结构化 dict / list, 要查询子键 / 要 GIN index / 要 `@>` `?` `||` operator
- 用 JSONB: 默认选 JSONB, 比 `json` 性能好, 项目内全 JSONB
- **不要**用 `sa.JSON()`: 在 PG 上是 text-based `json`, 跟 JSONB opclass 不兼容
- 用 `Text`: 字段是 JSON 字符串快照, 只整体读写不查询子键 (e.g. `chat_shares.messages_json`, `ingest_tasks.input_files_json`)

## 2. 定义 JSONB 列 (migration / ORM)

```python
# migration (alembic)
from sqlalchemy.dialects.postgresql import JSONB
sa.Column("profile_data", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb"))

# ORM model
from sqlalchemy.dialects.postgresql import JSONB
class BuyerProfile(Base):
    profile_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
```

加 GIN 索引 (高频按内容查 / `@>` 子集查 / `?` key 存在):

```python
op.create_index(
    "idx_buyer_profiles_data",
    "buyer_profiles",
    ["profile_data"],
    postgresql_using="gin",
    postgresql_ops={"profile_data": "jsonb_path_ops"},
)
```

`jsonb_path_ops` 比默认 `jsonb_ops` 索引更小、查询更快, 缺点是只支持 `@>` operator. 项目 buyer_profiles 用 path_ops.

## 3. 写入 JSONB 列 (raw SQL — 3 种姿势)

ORM `.add()` / `.commit()` 自动 adapt, 不操心. **只有 raw SQL `text(...)` 才需要注意**.

### A. SQL 内 cast (推荐, 跟 buyer_profile 一致)

```python
text("INSERT INTO buyer_profiles (account_id, profile_data) VALUES (:aid, CAST(:data AS jsonb))")
s.execute(stmt, {"aid": uid, "data": json.dumps(payload)})  # 传字符串
```

### B. bindparam 显式标类型 (logging.py 一致)

```python
from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql import JSONB

stmt = text("INSERT INTO app_logs (..., context) VALUES (..., :ctx)").bindparams(
    bindparam("ctx", type_=JSONB)
)
s.execute(stmt, {"ctx": dict_value})  # 直接传 dict
```

### C. 预序列化 + ::jsonb (chat 一致)

```python
text("INSERT INTO messages (..., meta) VALUES (..., :meta::jsonb)")
s.execute(stmt, {"meta": json.dumps(meta)})
```

**3 种都对**, 选项目里相近代码已经用的那种. 看到周围都是 A 就 A, 不要混搭.

### 错误姿势 — 别这么写

```python
# ❌ 裸 :param 传 dict, psycopg3 不知道列类型, 抛 'cannot adapt type dict'
text("INSERT INTO app_logs (..., context) VALUES (..., :ctx)")
s.execute(stmt, {"ctx": dict_value})  # FAIL
```

## 4. 读取 JSONB 列

ORM 自动反序列化为 dict / list:

```python
row = s.execute(select(BuyerProfile).where(...)).scalar_one()
print(type(row.profile_data))  # → dict
```

raw SQL 也是 dict:

```python
result = s.execute(text("SELECT profile_data FROM buyer_profiles WHERE id = :id"), {"id": 1})
row = result.fetchone()
print(type(row.profile_data))  # → dict
```

**不要 `json.loads(row.profile_data)`** — psycopg3 已经反序列化, 再 loads 抛 `TypeError: JSON object must be str, bytes or bytearray, not dict`.

历史脏数据兼容 (列曾经是 `json` 后改 `jsonb`, 边角 row 可能仍是 str):

```python
def _parse_meta(meta):
    if meta is None:
        return None
    if isinstance(meta, dict):
        return meta
    return json.loads(meta)  # 兜底
```

## 5. 高级查询 (JSONB operator)

```python
# 子键查询: ->> (返回 text), -> (返回 jsonb)
text("SELECT profile_data->>'name' FROM buyer_profiles WHERE id = :id")

# 子集匹配 (@>)
text("SELECT * FROM buyer_profiles WHERE profile_data @> :q")
{"q": json.dumps({"status": "active"})}

# key 存在 (?)
text("SELECT * FROM dictionary_items WHERE metadata_json ? 'icon'")

# 合并 (||)
text("UPDATE buyer_profiles SET profile_data = COALESCE(profile_data, '{}'::jsonb) || CAST(:patch AS jsonb)")
```

## 6. 防回归测试

- `tests/migrations/test_json_jsonb_policy.py` — AST 扫所有 migration, 禁止新 `sa.JSON()`
- `tests/migrations/test_jsonb_raw_sql_cast.py` — regex 扫 raw SQL, 禁止裸 `:param` 写 JSONB
- 列表/dict 字段类型变更必须加 migration test (参考 `tests/buyer_profile/test_migration.py`)

## 7. 排查 (3 个高频错误)

| 错误关键词 | 修法 |
|---|---|
| `operator class "jsonb_path_ops" does not accept data type json` | migration 把列从 `sa.JSON()` 改 `JSONB()` |
| `TypeError: JSON object must be str, bytes or bytearray, not dict` | 删 `json.loads`, 直接当 dict 用; 或加 `isinstance(x, dict)` 兜 |
| `cannot adapt type 'dict' using placeholder '%s'` | 加 CAST / bindparam / 预序列化, 见 §3 |
```

- [ ] **Step 3: 加到 cookbook 索引 (如果有)**

```bash
ls docs/cookbook/python/ 2>&1
# 如果有 README.md 或 index.md, 加一行 - [JSONB 使用](python/jsonb-usage.md)
```

如有索引文件就加链接; 没有就跳过.

- [ ] **Step 4: Commit**

```bash
git add docs/cookbook/python/jsonb-usage.md
git commit -m "docs(cookbook): 加 JSONB 使用教程 (json-jsonb spec Task D2)

7 节: 选型 / 定义 / 3 种写姿势 / 读 / operator / 测试 / 排查."
```

---

## Task Z: 收尾验证

- [ ] **Step 1: 跑完整 test suite 对比基线**

```bash
cd packages/service && uv run pytest --no-cov 2>&1 | tail -10
```

Expected: passed >= 基线 (Task 0 Step 4 记录的), 0 新 fail / new error.

- [ ] **Step 2: 跑 lint + type 全套**

```bash
cd packages/service && uv run ruff format --check
uv run ruff check
uv run pyright 2>&1 | tail -5
```

Expected: 0 format change · 0 lint error · 0 pyright error.

- [ ] **Step 3: 前后端联调手测一遍 chat / lookup 编辑**

```bash
# 1. 启后端 + 前端
cd packages/service && uv run python main.py serve &
cd packages/web && bun run dev &
sleep 10

# 2. 浏览器:
# - /chat 发消息带 meta → 看历史能拉回
# - /admin/dicts → 编辑某字典 → 看 audit 表 200 (修过的 INET 列)
# - 触发任一 500 → 看 error_logs 表有新 row (Task A 修过的 bindparam)
```

Expected: 全 200, 后端日志无 ValidationError / cannot adapt.

- [ ] **Step 4: 更新 handoff 标记 spec 完成**

编辑 [docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md](../handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md) §5 commit 范围 checklist 全打勾, 加完成日期.

```bash
git add docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md
git commit -m "docs(handoff): json-jsonb spec 全部完成 (Tasks A/B/C/D)"
```

- [ ] **Step 5: 写完成 memory**

写 [feedback-postgres-json-jsonb-spec-done.md](../../../C:/Users/abcuc/.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-postgres-json-jsonb-spec-done.md), 记录:
- 5 列已迁 JSONB
- 防回归 2 测试已上 CI
- 教程 + 规范已写
- 后续遇 JSON/JSONB 走 cookbook + CLAUDE.md, 不再开新 spec

加到 MEMORY.md 索引行.

---

## Self-Review (Plan 完成度自检)

### 1. Spec coverage

| Spec 项 | Task | 状态 |
|---|---|---|
| A 修 error_logs sink 活 bug | A | ✅ |
| B1 写 ALTER migration | B1 | ✅ |
| B2 ORM 类型同步 | B2 | ✅ |
| B3 业务读写端配合 | B3 | ✅ |
| C1 AST 防回归测试 (sa.JSON 禁用) | C1 | ✅ |
| C2 regex 防回归测试 (raw SQL 必 cast) | C2 | ✅ |
| D1 CLAUDE.md 规范章节 | D1 | ✅ |
| D2 cookbook 教程 | D2 | ✅ |
| 收尾验证 + 完成记 | Z | ✅ |

### 2. Placeholder scan

- ❌ 无 "TBD" / "TODO" / "fill in"
- ❌ 无 "implement appropriate error handling" 类含糊指令
- ❌ 无 "similar to Task N" 引用 — 每 Task 代码完整列出
- ✅ 所有命令含 expected output

### 3. Type consistency

- `bindparam("ctx", type_=JSONB)` 在 A / D 一致
- `_parse_meta` 在 B3 / D2 引用一致
- 5 列名 (messages.meta / evaluations.avg_metrics / evaluation_samples.{contexts,metrics,sources}) Task 0/B1/B2 一致
- migration revision `20260626_000000` Task B1 / C1 白名单一致

无问题.

---

## 风险二次确认

| 项 | 控制 |
|---|---|
| 生产 ALTER 锁表 | dev DB 先跑, dump 备份, 维护窗口 |
| 历史脏数据 cast 失败 | Task 0 Step 2 dry-run, 0 FAIL 才进 B |
| `_parse_meta` 删除引入回归 | **保留** 不删, 加注释说明 |
| Alembic 多 head | 新 revision `20260626_000000` 严格 down=`20260624_170000`, 单 head |
| 防回归测试白名单太宽 | 白名单只 1 个文件 (consolidated_pg_init), 任何新文件触发 |
