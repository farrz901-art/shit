# Handoff: JSON/JSONB 一族 bug 系统性分析 + audit IP 类型修复

**日期**: 2026-06-25
**触发现场**: 编辑 lookup 字典 (page_key) 后, `GET /api/admin/dicts/page_key/audit` 返 500
**直接修**: 1 行 (admin_router.py:541 stringify)
**系统分析**: 同源 3 次事故 + 6 个共因 + 防回归清单

---

## 1. 本次直接 bug

### 现场

编辑 lookup 后浏览器看到 2 个 500:

| URL | 状态 | 真正根因 |
|---|---|---|
| `GET /api/lookups/page_key?lang=both&only_active=false` | 500 | Bun + Windows node shim ENOENT (Next.js worker), 跟业务无关 |
| `GET /api/admin/dicts/page_key/audit` | **500** | **后端 Pydantic ValidationError**, 见下 |

`curl localhost:8000/api/lookups/page_key` → **200**, 后端 lookup 业务本身正常.
`curl localhost:8000/api/admin/dicts/page_key/audit` → **500 `{"detail":"Internal server error"}`**, 后端真炸.

### 直接报错

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for AuditLogEntry
ip
  Input should be a valid string [type=string_type, input_value=IPv4Address('127.0.0.1'), input_type=IPv4Address]
```

栈尾在 `src/lookups/admin_router.py:532` 构造 `AuditLogEntry(... ip=row.ip ...)`.

### 根因链

1. `audit_logs.ip` 列类型: [src/db/models/audit_log.py:27](../../packages/service/src/db/models/audit_log.py#L27) `Column(INET, nullable=True)` (PG 原生 `inet`)
2. psycopg3 把 PG `INET` 反序列化为 `ipaddress.IPv4Address` 对象, **不是 str**
3. [src/lookups/admin_router.py:541](../../packages/service/src/lookups/admin_router.py#L541) `ip=row.ip` 直接塞给 Pydantic
4. [src/lookups/schemas.py:183](../../packages/service/src/lookups/schemas.py#L183) `ip: str | None`
5. Pydantic v2 不自动 coerce `IPv4Address → str` → ValidationError

### 为什么之前没炸

编辑前 audit_logs 表里没有 `dictionary.%` action row (空列表不构造 `AuditLogEntry`). 编辑 lookup 触发 `log_dict_change` 写 audit, `ip=127.0.0.1` 入库后读出变 `IPv4Address` → 第一次构造就炸. Bug 一直存在, 数据触发.

### 修法 (本次实施)

[src/lookups/admin_router.py:541](../../packages/service/src/lookups/admin_router.py#L541):

```python
# 修改前
ip=row.ip,  # type: ignore[arg-type]

# 修改后
ip=str(row.ip) if row.ip is not None else None,  # type: ignore[arg-type]
```

边界 stringify, 业务侧 ip 一直当字符串用 (前端展示), 一行改动影响面最小.

---

## 2. JSON/JSONB 一族 bug 系统性分析

### 事故清单 (3 次同源)

| 日期 | 现场 | 错误关键词 |
|---|---|---|
| 2026-06-23 buyer_profile | `sa.JSON()` 列 + `jsonb_path_ops` GIN index | `operator class "jsonb_path_ops" does not accept data type json` |
| 2026-06-24 chat get_conversation | `sa.JSON()` 列读出 + `json.loads(m.meta)` | `TypeError: the JSON object must be str, bytes or bytearray, not dict` |
| 2026-06-25 error_logs sink (今天) | raw SQL `INSERT ... VALUES (:ctx)`, ctx=dict, 列是 JSONB | `psycopg.ProgrammingError: cannot adapt type 'dict' using placeholder '%s'` |

附注: 今天还看到 `error_logs write failed: cannot adapt type 'dict' using placeholder '%s'` (来自 5xx 全局 handler 写 error_logs 时), 那是**第 3 次同源事故**, 见 [src/core/logging.py:103-120](../../packages/service/src/core/logging.py#L103-L120) — 本 handoff **不修**, 留作系统级修复时一起处理.

### 6 个系统层共因

1. **历史漂移**: SQLite 时代 migration 用 `sa.JSON()` (跨 dialect 通用), 切 PG 后只部分改 `JSONB`, DB 列类型混乱 (有的 `json` text, 有的 `jsonb` 二进制)
2. **SA 抽象层泄漏**: `sa.JSON()` 在 PG 等于 `json` 类型 (text), ORM 注释 / 业务代码当 `jsonb` 用, 跨 dialect 行为不一致
3. **psycopg3 v3 adapter 协议变更** (关键): 不像 psycopg2 自动 json adapter, v3 raw SQL `text(":ctx")` 不知道列类型, 不会自动 cast `dict → jsonb`
4. **raw SQL 跳过 ORM 类型层**: ORM `Column(JSONB)` 是给 Python 层用, `text("INSERT")` 走 psycopg3 直传, 绕过 ORM 类型映射
5. **psycopg3 读类型不同**: `jsonb` 列 (psycopg3 注册了 loader) → dict, `json` 列 → str; 同字段两种列类型行为相反, `json.loads` 必炸一边
6. **测试 mock 屏蔽**: mock `session_scope` 跑不到真实 type adaptation, 单测全绿 PG 上炸

### 排查信号 (一眼定位)

| 错误关键词 | 一定是 |
|---|---|
| `operator class "jsonb_path_ops" does not accept data type json` | sa.JSON() + JSONB opclass 不匹配 (migration) |
| `TypeError: the JSON object must be str, bytes or bytearray, not dict` | psycopg3 读 jsonb 返 dict, 业务 `json.loads` 误用 |
| `cannot adapt type 'dict' using placeholder '%s'` | raw SQL 没 cast, psycopg3 不知道 jsonb |

### 项目级根治方案 (待后续 spec 实施)

#### A. ORM / migration 统一

- 全用 `from sqlalchemy.dialects.postgresql import JSONB`, **0 `sa.JSON()`**
- migration 同步: 老的 `sa.JSON()` 列加迁移 `ALTER COLUMN ... TYPE jsonb USING ...::jsonb`
- 自查 grep: `rg "sa\.JSON\(\)" packages/service/src` 应当 0 命中
- 当前命中 (2026-06-25): [src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py:128,148,170,171,172](../../packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py) — meta / avg_metrics / contexts / metrics / sources 5 列待迁移

#### B. raw SQL 写 JSONB 列 (3 种修法, 任选)

```python
# A. SQL 内 cast (最直观)
text("INSERT INTO error_logs (..., context) VALUES (..., CAST(:ctx AS jsonb))")

# B. bindparam 显式标类型 (最 ORM)
from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql import JSONB
text("INSERT ... VALUES (... :ctx)").bindparams(bindparam("ctx", type_=JSONB))

# C. 业务侧序列化为 JSON 字符串 + ::jsonb
text("INSERT ... VALUES (... :ctx::jsonb)"), {"ctx": json.dumps(d)}
```

#### C. 读 JSONB 列 (psycopg3)

- 默认返 `dict`, 直接用, **禁止 `json.loads`**
- 历史脏数据兼容: `x if isinstance(x, dict) else (json.loads(x) if x else None)` — 兜底, 但说明列类型不一致, 应该一次性 ALTER 整齐

#### D. 测试

- mock 模式 1 测不到此族 bug, **关键 JSONB 路径必须模式 2** (`db_session` 集成测) 才能暴露 adapter 问题
- migration 加 AST-parse test 断言 0 `sa.JSON()` 用法 (见 `tests/buyer_profile/test_migration.py::test_jsonb_columns_use_jsonb_not_sa_json`)

### Why 反复犯 (没修系统就还会出)

- 三种现场表面错完全不同 (DDL / 读 / 写), 不归因到同源
- 单测 mock 屏蔽, dev 上跑通就过了
- ORM 看上去都接受 `dict`, pyright 0 报警
- 列类型漂移需要 DBA 视角 (`\d <table>` 看实际列), 业务开发不会主动看

只能靠**系统级规范 + grep 守门 + 集成测试**三件套防回归.

---

## 3. 已知待修 (本次 handoff 不动)

### 3.1 error_logs sink raw SQL 没 cast

[src/core/logging.py:103-120](../../packages/service/src/core/logging.py#L103-L120):

```python
text("INSERT INTO error_logs (... context) VALUES (... :ctx)")  # 缺 ::jsonb cast
{"ctx": _scrub({})}  # dict, psycopg3 不知道怎么 adapt → JSONB
```

修法: `VALUES (... CAST(:ctx AS jsonb))`. 影响: 每次 5xx 错误日志写不进 DB, 只剩 stderr.

### 3.2 5 个 `sa.JSON()` 历史列待迁移

[20260615_000000_consolidated_pg_init.py](../../packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py): meta / avg_metrics / contexts / metrics / sources. 需新 migration:

```sql
ALTER TABLE <t> ALTER COLUMN <c> TYPE jsonb USING <c>::jsonb;
```

业务读端配合改: `isinstance(x, dict)` 兜 → 迁完后删兜底.

### 3.3 同类隐患 grep 自查

```bash
# 必须 0 命中
rg "sa\.JSON\(\)" packages/service/src
# 必须 0 命中 (jsonb 列上做 json.loads)
rg "json\.loads\(.+\.(meta|ctx|before|after|payload|context)\b" packages/service/src
# 必须 0 命中 (raw SQL :param dict 没 cast)
rg "text\(\"INSERT.+:[a-z]+.+context\b" packages/service/src
```

---

## 4. Memory 记录

[feedback-postgres-json-jsonb-family-of-bugs.md](../../C:/Users/abcuc/.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-postgres-json-jsonb-family-of-bugs.md) — 全套共因 + 修法清单 + 排查信号表.

同族已有:
- [feedback-postgres-json-vs-jsonb-opclass](../../C:/Users/abcuc/.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-postgres-json-vs-jsonb-opclass.md) — DDL 那次
- [feedback-sa-json-psycopg3-dict-not-str](../../C:/Users/abcuc/.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-sa-json-psycopg3-dict-not-str.md) — chat 读那次

---

## 5. 本次 commit 范围

- [x] `src/lookups/admin_router.py:541` 一行 stringify
- [x] handoff 文档 (本文件)
- [x] memory 写入
- [ ] error_logs cast 修复 (留下次)
- [ ] 5 个 `sa.JSON()` 列迁移 (留 spec)
- [ ] AST-parse migration test (留 spec)
