# JSONB 使用教程

> 适用版本: 5 列 sa.JSON → JSONB 迁移 (2026-06-26, spec `2026-06-25-postgres-json-jsonb-rooting.md`)
> 阅读对象: 需要读写 JSONB 列的后端工程师

---

## 一、背景 & 迁移范围

**项目 PG 长期混用 `sa.JSON()` (json 类型) 和 `JSONB()`, 导致 3 类同源 bug:**

- GIN index `jsonb_path_ops` 不兼容 json 类型 → migration 炸
- psycopg3 读 json 返回 str, 读 jsonb 返回 dict → 业务 `json.loads` 误用
- raw SQL INSERT/UPDATE 传裸 dict → `cannot adapt type 'dict'`

**2026-06-26 migration 将 5 列从 sa.JSON() 迁为 JSONB:**

| 表 | 列 |
|---|---|
| `chat.messages` | `meta`, `context`, `payload` |
| `chat.conversations` | `meta` |
| `eval.reports` | `meta` |
| `eval.report_items` | `meta` |
| `eval.evaluations` | `meta` |

迁移后, ORM 列声明全部 `JSONB()`, raw SQL 全部带 `CAST` / `::jsonb` / `bindparam(type_=JSONB)`.

---

## 二、ORM 列声明

```python
# 旧 (禁用 — 跨 dialect 抽象层泄漏, GIN index 不兼容)
sa.Column("data", sa.JSON())

# 新 (统一)
from sqlalchemy.dialects.postgresql import JSONB
sa.Column("data", JSONB())
```

已有 `tests/migrations/test_json_jsonb_policy.py` AST 扫所有 migration 文件, 新增 `sa.JSON()` 必 FAIL.

---

## 三、Raw SQL 写 JSONB 列 (3 种正确姿势)

项目内 3 种都有用, 任选:

### A. SQL 内 CAST (最直观, buyer_profile 用)

```python
from sqlalchemy import text
import json

query = """UPDATE buyer_profiles SET
    profile_data = COALESCE(profile_data, '{}'::jsonb) || CAST(:merge AS jsonb)
    WHERE account_id = :aid AND buyer_key = :key"""
sess.execute(text(query), {
    "merge": json.dumps(merge_obj),  # 传字符串, CAST 解析
    "aid": account_id,
    "key": buyer_key,
})
```

### B. bindparam 显式标类型 (最 ORM, logging.py 用)

```python
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

stmt = text("INSERT INTO app_logs (..., context) VALUES (..., :ctx)").bindparams(
    bindparam("ctx", type_=JSONB)
)
sess.execute(stmt, {"ctx": dict_value})  # 传 dict, psycopg3 自动 adapt
```

### C. 业务侧预序列化 + ::jsonb (chat 用)

```python
from sqlalchemy import text
import json

query = "INSERT INTO messages (..., meta) VALUES (..., :meta::jsonb)"
sess.execute(text(query), {"meta": json.dumps(meta)})  # 传字符串, DB 侧 ::jsonb 解析
```

**禁止裸 `:p` 传 dict** — 必抛 `psycopg.ProgrammingError: cannot adapt type 'dict'`.

已有 `tests/migrations/test_jsonb_raw_sql_cast.py` regex 扫 src/ 下所有 raw SQL.

---

## 四、读 JSONB 列 (禁止 json.loads)

psycopg3 v3 注册了 jsonb loader:

| PG 类型 | Python 类型 | 做法 |
|---|---|---|
| `jsonb` | `dict` (自动) | `record["meta"]["key"]` 直接访问, 不要 json.loads |
| `json` (老) | `str` | 需 `json.loads(record["meta"])` (项目已全部迁 JSONB) |

```python
# 旧 (禁用 — psycopg3 读 jsonb 返 dict, json.loads(dict) 炸 TypeError)
meta = json.loads(row["meta"])

# 新 (直接当 dict 用)
title = row["meta"].get("title", "")
```

项目保留 `_parse_meta()` 兜底函数, 兼容历史脏数据 + 单测 mock 给 str 也用:

```python
def _parse_meta(raw: str | dict | None) -> dict:
    """JSONB 列安全读取, 兼容 dict / str / None."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    return {}
```

---

## 五、psycopg3 v3 adapter 注意事项

| PG 类型 | Python 类型 | 注意 |
|---|---|---|
| `JSONB` | `dict` | 直接使用, 不要 json.loads |
| `INET` | `ipaddress.IPv4Address` | Pydantic v2 不自动 coerce, 业务需 `str()` |
| `UUID` | `uuid.UUID` | 自动反序列化, OK |
| `json` (老, 已迁) | `str` | 项目已无此场景, 历史数据走 `_parse_meta()` |

---

## 六、测试模式

```python
# tests/migrations/test_jsonb_raw_sql_cast.py — 模式 1 (mock, regex)
# 0 PG 依赖, 纯静态扫 src/ 下所有 raw SQL
# 不能 100% 严密, 但能拦最常见"裸传 dict"模式
def test_jsonb_raw_sql_writes_have_cast_or_bindparam():
    src = _src_dir()
    assert src.exists()
    violations: list[str] = []
    for py in src.rglob("*.py"):
        if "__pycache__" in py.parts or "tests" in py.parts:
            continue
        hits = _scan_file_for_jsonb_writes(py)
        for lineno, line, neighborhood in hits:
            if any(p.search(neighborhood) for p in SAFE_PATTERNS):
                continue
            rel = py.relative_to(src.parent.parent.parent)
            violations.append(f"{rel}:{lineno} 写 JSONB 列裸 :param, 缺 CAST/::jsonb/bindparam JSONB/json.dumps\n  {line}")
    assert not violations, "\n\n".join(violations)
```

---

## 七、常见坑

### 7.1 `psycopg.ProgrammingError: cannot adapt type 'dict'`

**原因**: raw SQL 用 `:p` 传 dict, psycopg3 不知道目标列是 JSONB, 不知道用 jsonb adapter.

**修法**: CAST / bindparam(type_=JSONB) / 预序列化 json.dumps + ::jsonb (见 §三).

### 7.2 `TypeError: the JSON object must be str, bytes or bytearray, not dict`

**原因**: psycopg3 读 JSONB 列返 dict, 业务 `json.loads` 又试图解析.

**修法**: 删掉 `json.loads`, 直接当 dict 用 (见 §四).

### 7.3 `operator class "jsonb_path_ops" does not accept data type json`

**原因**: ORM 列 `sa.JSON()` 生成 PG `json` 类型, 但 GIN index 用 `jsonb_path_ops`.

**修法**: ORM 列改 `JSONB()` (见 §二).

### 7.4 sa.JSON → JSONB 迁移后, 业务读到 str 或 dict 不确定?

迁移后 psycopg3 统一返 dict. 如仍有 str (mock / 脏数据), 用 `_parse_meta()` 格式.

### 7.5 raw SQL 双冒号 `::jsonb` 在 SA 2.0 + psycopg3 报错?

SA 2.0 对 `::` 解析不完整, 用 CAST 替代或 bindparam(type_=JSONB):

```python
# 安全 (不 ::):
CAST(:merge AS jsonb)
# 等价 unsafe:
:merge::jsonb  # 某些 SA 版本 double-colon parse 歧义
```

---

## 八、排查信号速查

| 错误 | 根因 | 修法 |
|---|---|---|
| `cannot adapt type 'dict' using placeholder '%s'` | raw SQL 没 cast | §三 A/B/C 任一 |
| `TypeError: the JSON object must be str, bytes or bytearray, not dict` | 业务 json.loads | §四 删 json.loads |
| `operator class "jsonb_path_ops" does not accept data type json` | ORM sa.JSON() | §二 改 JSONB() |

---

## 相关文档

- Spec: `docs/superpowers/specs/2026-06-25-jsonb-migration.md`
- Plan: `docs/superpowers/plans/2026-06-25-postgres-json-jsonb-rooting.md`
- 后端 CLAUDE.md: `packages/service/CLAUDE.md` §JSONB 使用规范
- Handoff: `docs/superpowers/handoffs/2026-06-25-postgres-json-jsonb-family-bugs.md`
