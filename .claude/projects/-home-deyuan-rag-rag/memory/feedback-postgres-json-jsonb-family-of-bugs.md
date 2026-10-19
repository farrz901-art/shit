---
name: feedback-postgres-json-jsonb-family-of-bugs
description: "JSON/JSONB 一族 bug 系统性根因 (sa.JSON() vs JSONB + psycopg3 v3 adapter 协议 + raw SQL 跳过 ORM 类型), 3 次事故同源, 项目级修法清单"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 423308d9-fb4d-4760-bc79-f8116f48bd35
---

# Postgres JSON/JSONB 一族 bug — 同源, 不是孤立

3 次独立事故同一族根因. 没修系统层, 第 4 次还会出.

## 事故清单

| 日期 | 现场 | 错 |
|---|---|---|
| 2026-06-23 buyer_profile | `sa.JSON()` 列 + `jsonb_path_ops` GIN index | `DatatypeMismatch: operator class "jsonb_path_ops" does not accept data type json` |
| 2026-06-24 chat get_conversation | `sa.JSON()` 列读出, `json.loads(m.meta)` | `TypeError: the JSON object must be str, bytes or bytearray, not dict` |
| 2026-06-25 error_logs sink | raw SQL `INSERT ... VALUES (:ctx)`, ctx=dict, 列是 JSONB | `psycopg.ProgrammingError: cannot adapt type 'dict' using placeholder '%s'` |

详见 [[feedback-postgres-json-vs-jsonb-opclass]] / [[feedback-sa-json-psycopg3-dict-not-str]].

## 共因 (6 个系统层面)

1. **历史漂移**: SQLite 时代 migration 用 `sa.JSON()` (跨 dialect 通用), 切 PG 后只部分改 `JSONB`, DB 列类型混乱
2. **SA 抽象层泄漏**: `sa.JSON()` 在 PG 等价 `json` 类型 (text), 业务注释/代码当 `jsonb` 用, 跨 dialect 行为不一致
3. **psycopg3 v3 adapter 协议变更**: 不像 psycopg2 自动 json adapter, v3 raw SQL `text(":ctx")` 不知道列类型, 不会自动 cast `dict → jsonb`
4. **raw SQL 跳过 ORM 类型层**: ORM `Column(JSONB)` 是给 Python 层用, `text("INSERT")` 走 psycopg3 直传, 绕过 ORM 类型映射
5. **psycopg3 读类型不同**: `jsonb` 列 (psycopg3 注册了 loader) → dict, `json` 列 → str; 同字段两种列类型行为相反, `json.loads` 必炸一边
6. **测试 mock 屏蔽**: mock `session_scope` 跑不到真实 type adaptation, 单测全绿 PG 上炸

## 项目级修法 (How to apply)

### ORM / migration
- 全用 `from sqlalchemy.dialects.postgresql import JSONB`, **0 `sa.JSON()`**
- migration 同步: 老的 `sa.JSON()` 列加迁移 `ALTER COLUMN ... TYPE jsonb USING ...::jsonb`
- 自查: `rg "sa\.JSON\(\)" packages/service/src` 应当 0 命中

### raw SQL 写 JSONB 列 (3 种修法, 任选)
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

### 读 JSONB 列 (psycopg3)
- 默认返 `dict`, 直接用, **禁止 `json.loads`**
- 历史脏数据兼容: `x if isinstance(x, dict) else (json.loads(x) if x else None)` — 兜底, 但说明列类型不一致, 应该一次性 ALTER 整齐

### 测试
- mock 模式 1 测不到此族 bug, **关键 JSONB 路径必须模式 2** (`db_session` 集成测) 才能暴露 adapter 问题
- migration 加 AST-parse test 断言 0 `sa.JSON()` 用法 (见 `tests/buyer_profile/test_migration.py`)

## 排查信号 (一眼定位)

| 错误关键词 | 一定是 |
|---|---|
| `operator class "jsonb_path_ops" does not accept data type json` | sa.JSON() + JSONB opclass 不匹配 (migration) |
| `TypeError: the JSON object must be str, bytes or bytearray, not dict` | psycopg3 读 jsonb 返 dict, 业务 `json.loads` 误用 |
| `cannot adapt type 'dict' using placeholder '%s'` | raw SQL 没 cast, psycopg3 不知道 jsonb |

## Why (为什么不修系统就反复犯)

- 三种现场表面错完全不同 (DDL / 读 / 写), 不归因到同源
- 单测 mock 屏蔽, dev 上跑通就过了
- ORM 看上去都接受 `dict`, pyright 0 报警
- 列类型漂移需要 DBA 视角 (\d 看实际列), 业务开发不会主动看

只能靠系统级规范 + grep 守门 + 集成测试三件套防回归.
