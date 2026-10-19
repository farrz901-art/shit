# 任务 ID 可读性规范化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把散落各处、无可读性的任务 ID（如 `pa-3f9a1c2b4d5e`）统一为带类型前缀、可读可排序的 `{prefix}_{YYYYMMDD}{HHMMSS}_{6hex}` 格式，经唯一中央 helper 生成。

**Architecture:** 新增纯函数模块 `src/common/task_id.py` 提供 `make_task_id(prefix)` 与 4 个前缀常量；改造 3 处调用方（pre_analysis / ingest / kg）走 helper；不迁移存量数据；沉淀规范进 `packages/service/CLAUDE.md`。

**Tech Stack:** Python 3.14 / `secrets` / `datetime` / 项目 `HKT` 时区常量 / pytest（模式 1 mock）/ ruff / pyright

## Global Constraints

- 后端工具链顺序不可颠倒: `uv run ruff format` → `uv run ruff check --fix` → `uv run pyright`（0 error）→ `uv run pytest`（0 新 fail）
- 测试走模式 1（mock），0 PG/Redis 依赖；测试文件放 `tests/`，命名 `test_*.py`
- 日志用 loguru（本计划不新增日志，无涉及）
- 代码注释用中文；不删除已有注释
- 每个函数 ≤ 100 行
- 前缀常量是唯一事实源，调用方**禁止传字面量**，必须用 `TASK_PREFIX_*` 常量
- 时间戳用 `src/utils/timezone.py` 的 `HKT`（UTC+8），跟 DB 存储时区一致
- commit message 前缀: `refactor:` / `test:` / `docs:`
- 存量数据不改：只改生成逻辑，不写迁移、不动老任务、老 `pa-xxx` 与新 `pa_xxx` 共存
- 工作目录: `/home/deyuan/rag/rag`，后端在 `packages/service/`（`uv run` 需在该目录执行）

---

### Task 1: 中央 helper 模块 `src/common/task_id.py`

**Files:**
- Create: `packages/service/src/common/task_id.py`
- Test: `packages/service/tests/common/test_task_id.py`

**Interfaces:**
- Consumes: `src.utils.timezone.HKT`（已存在，`timezone(timedelta(hours=8))`）
- Produces:
  - `make_task_id(prefix: str) -> str` — 返回 `{prefix}_{YYYYMMDD}{HHMMSS}_{6hex}`
  - 常量 `TASK_PREFIX_PRE_ANALYSIS = "pa"`、`TASK_PREFIX_INGEST = "ig"`、`TASK_PREFIX_KG_EXTRACT = "kge"`、`TASK_PREFIX_KG_BATCH = "kgb"`

- [ ] **Step 1: 建测试目录 + 写失败测试**

先确认 `packages/service/tests/common/` 是否有 `__init__.py`（跟随项目现有 tests 结构；若其它 `tests/<pkg>/` 有则加）。写测试文件 `packages/service/tests/common/test_task_id.py`：

```python
"""task_id 生成器单测 (模式 1: 纯函数, 0 PG 依赖)"""

import re
from datetime import datetime

from src.common.task_id import (
    TASK_PREFIX_INGEST,
    TASK_PREFIX_KG_BATCH,
    TASK_PREFIX_KG_EXTRACT,
    TASK_PREFIX_PRE_ANALYSIS,
    make_task_id,
)
from src.utils.timezone import HKT

# 完整格式: {prefix}_{14位数字}_{6位hex}
_PATTERN = re.compile(r"^(pa|ig|kge|kgb)_\d{14}_[0-9a-f]{6}$")


def test_format_matches_spec():
    """pa 前缀生成结果符合 {prefix}_{YYYYMMDD}{HHMMSS}_{6hex}"""
    tid = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    assert _PATTERN.match(tid), f"格式不符: {tid}"
    assert tid.startswith("pa_")


def test_all_prefixes_wired():
    """4 个前缀常量各自拼到 ID 开头"""
    assert make_task_id(TASK_PREFIX_PRE_ANALYSIS).startswith("pa_")
    assert make_task_id(TASK_PREFIX_INGEST).startswith("ig_")
    assert make_task_id(TASK_PREFIX_KG_EXTRACT).startswith("kge_")
    assert make_task_id(TASK_PREFIX_KG_BATCH).startswith("kgb_")


def test_timestamp_parseable():
    """中间 14 位可被 strptime 解回"""
    tid = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    ts_str = tid.split("_")[1]
    parsed = datetime.strptime(ts_str, "%Y%m%d%H%M%S")  # 不抛即通过
    assert parsed.year >= 2026


def test_uses_hkt_timezone(monkeypatch):
    """时间戳用香港时区 HKT, 不用 UTC/本地"""
    fixed = datetime(2026, 7, 8, 14, 30, 12, tzinfo=HKT)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # 断言调用方确实传了 HKT
            assert tz == HKT, f"应传 HKT, 实传 {tz}"
            return fixed

    monkeypatch.setattr("src.common.task_id.datetime", _FrozenDatetime)
    tid = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    assert tid.startswith("pa_20260708143012_")


def test_uniqueness_same_second(monkeypatch):
    """同一秒内连生成随机段不同 (secrets 部分变化)"""
    fixed = datetime(2026, 7, 8, 14, 30, 12, tzinfo=HKT)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr("src.common.task_id.datetime", _FrozenDatetime)
    ids = {make_task_id(TASK_PREFIX_PRE_ANALYSIS) for _ in range(50)}
    # 时间戳全相同, 靠随机段区分; 50 个 24bit 随机基本不撞
    assert len(ids) == 50


def test_length_stable():
    """pa 前缀总长稳定 24 字符"""
    tid = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    assert len(tid) == 24  # pa(2) + _(1) + 14 + _(1) + 6 = 24
```

- [ ] **Step 2: 跑测试确认失败**

Run（在 `packages/service/` 下）: `uv run pytest tests/common/test_task_id.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.common.task_id'`

- [ ] **Step 3: 写最小实现**

Create `packages/service/src/common/task_id.py`：

```python
"""任务 ID 统一生成: {prefix}_{YYYYMMDD}{HHMMSS}_{6hex}

散落各处的 uuid.uuid4().hex[:12] 无可读性, 本模块提供唯一中央生成器.
所有任务型 ID (pre_analysis / ingest / kg) 必须走 make_task_id, 禁止 inline 生成.
"""

import secrets
from datetime import datetime

from src.utils.timezone import HKT

# 任务类型前缀常量 (唯一事实源, 调用方勿传字面量)
TASK_PREFIX_PRE_ANALYSIS = "pa"
TASK_PREFIX_INGEST = "ig"
TASK_PREFIX_KG_EXTRACT = "kge"
TASK_PREFIX_KG_BATCH = "kgb"


def make_task_id(prefix: str) -> str:
    """生成可读任务 ID: {prefix}_{YYYYMMDD}{HHMMSS}_{6hex}

    入参:
        prefix: 类型前缀, 用本模块 TASK_PREFIX_* 常量 (勿传字面量)
    回参:
        str, 例 'pa_20260708143012_a1b2c3' (pa 前缀时 24 字符)
    """
    # 香港时区时间戳, 跟 DB 存储一致; 14 位可读又可字典序排序
    ts = datetime.now(HKT).strftime("%Y%m%d%H%M%S")
    # 24 bit 随机, 同秒内防碰撞
    rand = secrets.token_hex(3)
    return f"{prefix}_{ts}_{rand}"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/common/test_task_id.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: format / lint / 类型检查**

Run:
```bash
uv run ruff format src/common/task_id.py tests/common/test_task_id.py
uv run ruff check --fix src/common/task_id.py tests/common/test_task_id.py
uv run pyright src/common/task_id.py
```
Expected: 各 0 error

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/common/task_id.py packages/service/tests/common/test_task_id.py
git commit -m "feat: 新增任务 ID 中央生成器 make_task_id"
```

---

### Task 2: 改造 pre_analysis 调用方

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/router.py:102`
- Test: `packages/service/tests/ingest/pre_analysis/test_router.py`（已存在，验回归）

**Interfaces:**
- Consumes: `make_task_id`、`TASK_PREFIX_PRE_ANALYSIS`（Task 1）

- [ ] **Step 1: 改生成点**

在 `router.py` 顶部 import 区加（跟随现有 import 风格，放到项目内部 import 段）：

```python
from src.common.task_id import TASK_PREFIX_PRE_ANALYSIS, make_task_id
```

把 `:102` 的：

```python
task_id = f"pa-{uuid.uuid4().hex[:12]}"
```

改为：

```python
task_id = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
```

- [ ] **Step 2: 清理孤儿 import**

Run（在 `packages/service/`）: `grep -n "uuid" src/ingest/pre_analysis/router.py`
若 `import uuid` 在该文件已无其它用处，删掉该 import 行；若仍有其它 `uuid.` 调用，保留。（`ruff check --fix` 会自动标 F401，但先人工确认避免误删。）

- [ ] **Step 3: 跑既有 router 测试确认无回归**

Run: `uv run pytest tests/ingest/pre_analysis/ -v`
Expected: 与改动前同样绿（pre-existing fail 不算新 fail）。测试用的是传入的固定 `pa-abc` fixture（非对生成结果断言），不受影响。

- [ ] **Step 4: format / lint / 类型检查**

Run:
```bash
uv run ruff format src/ingest/pre_analysis/router.py
uv run ruff check --fix src/ingest/pre_analysis/router.py
uv run pyright src/ingest/pre_analysis/router.py
```
Expected: 各 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/ingest/pre_analysis/router.py
git commit -m "refactor: pre_analysis 任务 ID 走中央 make_task_id"
```

---

### Task 3: 改造 ingest (pdf_processing) 调用方

**Files:**
- Modify: `packages/service/src/ingest/pdf_processing/router.py:126-128`
- Test: `packages/service/tests/ingest/`（相关既有测试，验回归）

**Interfaces:**
- Consumes: `make_task_id`、`TASK_PREFIX_INGEST`（Task 1）
- 保留 `_new_task_id() -> str` 包装名不变（调用点 `:308`、`:445` 不动）

- [ ] **Step 1: 改 `_new_task_id` 函数体**

在 `router.py` 内部 import 段加：

```python
from src.common.task_id import TASK_PREFIX_INGEST, make_task_id
```

把 `:126-128`：

```python
def _new_task_id() -> str:
    """YYYYMMDD-HHMMSS-{6hex} — 人类可读, 又够随机"""
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
```

改为：

```python
def _new_task_id() -> str:
    """任务 ID: 走中央 make_task_id, 格式 ig_{YYYYMMDD}{HHMMSS}_{6hex}"""
    return make_task_id(TASK_PREFIX_INGEST)
```

- [ ] **Step 2: 清理孤儿 import**

Run: `grep -n "datetime\|secrets" src/ingest/pdf_processing/router.py`
若 `datetime` / `secrets` 在该文件仅 `_new_task_id` 用到，删掉对应 import；若他处仍用，保留。人工确认后再删。

- [ ] **Step 3: 跑既有 ingest 测试确认无回归**

Run: `uv run pytest tests/ingest/ -v --ignore=tests/ingest/pre_analysis`
Expected: 与改动前同样绿。若有测试断言 task_id 匹配旧格式 `\d{8}-\d{6}-` 正则，改为新格式 `^ig_\d{14}_[0-9a-f]{6}$`（Step 3.1 先查）。

- [ ] **Step 3.1: 查是否有旧格式断言**

Run: `grep -rn "d{8}-\|d{6}\|_new_task_id\|task_id.*match\|startswith" tests/ingest/`
若命中对 task_id 格式的断言，按新格式更新；无命中则跳过。

- [ ] **Step 4: format / lint / 类型检查**

Run:
```bash
uv run ruff format src/ingest/pdf_processing/router.py
uv run ruff check --fix src/ingest/pdf_processing/router.py
uv run pyright src/ingest/pdf_processing/router.py
```
Expected: 各 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/ingest/pdf_processing/router.py
git commit -m "refactor: ingest 任务 ID 走中央 make_task_id (加 ig 前缀)"
```

---

### Task 4: 改造 kg TaskStore 调用方

**Files:**
- Modify: `packages/service/src/kg/tasks.py:38-42`（`TaskStore.submit`）
- Test: `packages/service/tests/kg/test_kg_tasks.py`、`test_tasks.py`（既有，验回归）

**Interfaces:**
- Consumes: `make_task_id`、`TASK_PREFIX_KG_EXTRACT`、`TASK_PREFIX_KG_BATCH`（Task 1）
- `submit(self, kind: str, payload: dict) -> str` 签名不变

- [ ] **Step 1: 写失败测试（前缀按 kind 分流）**

在 `packages/service/tests/kg/test_kg_tasks.py` 末尾加（若该文件用 class 组织，加到合适 class 内；跟随文件现有风格）：

```python
def test_submit_prefix_by_kind():
    """kg_extract → kge_ 前缀; kg_batch → kgb_ 前缀"""
    from src.kg.tasks import TaskStore

    store = TaskStore()
    extract_id = store.submit("kg_extract", {})
    batch_id = store.submit("kg_batch", {})
    assert extract_id.startswith("kge_"), f"应 kge_ 前缀: {extract_id}"
    assert batch_id.startswith("kgb_"), f"应 kgb_ 前缀: {batch_id}"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/kg/test_kg_tasks.py::test_submit_prefix_by_kind -v`
Expected: FAIL — 现有 `uuid.uuid4().hex[:12]` 无前缀，`startswith` 断言失败

- [ ] **Step 3: 改 `submit` 方法**

在 `tasks.py` import 段加：

```python
from src.common.task_id import (
    TASK_PREFIX_KG_BATCH,
    TASK_PREFIX_KG_EXTRACT,
    make_task_id,
)
```

把 `:38-42`：

```python
    def submit(self, kind: str, payload: dict) -> str:
        task_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._tasks[task_id] = TaskStatus(task_id=task_id, kind=kind, state="queued", payload=payload)
        return task_id
```

改为：

```python
    def submit(self, kind: str, payload: dict) -> str:
        # 按 kind 选前缀: kg_batch → kgb_, 其余 (kg_extract) → kge_
        prefix = TASK_PREFIX_KG_BATCH if kind == "kg_batch" else TASK_PREFIX_KG_EXTRACT
        task_id = make_task_id(prefix)
        with self._lock:
            self._tasks[task_id] = TaskStatus(task_id=task_id, kind=kind, state="queued", payload=payload)
        return task_id
```

- [ ] **Step 4: 清理孤儿 import**

Run: `grep -n "uuid" src/kg/tasks.py`
若 `import uuid` 在该文件无其它用处，删掉；否则保留。

- [ ] **Step 5: 跑测试确认通过 + 无回归**

Run: `uv run pytest tests/kg/test_kg_tasks.py tests/kg/test_tasks.py -v`
Expected: 新测试 PASS，既有测试无新 fail。既有 `test_kg_tasks.py:85-86` 断言的是内存排序（`recent[0].task_id == b`，用返回值比对，不涉及格式），不受影响。

- [ ] **Step 6: format / lint / 类型检查**

Run:
```bash
uv run ruff format src/kg/tasks.py tests/kg/test_kg_tasks.py
uv run ruff check --fix src/kg/tasks.py tests/kg/test_kg_tasks.py
uv run pyright src/kg/tasks.py
```
Expected: 各 0 error

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/kg/tasks.py packages/service/tests/kg/test_kg_tasks.py
git commit -m "refactor: kg TaskStore 任务 ID 走中央 make_task_id (kge/kgb 前缀)"
```

---

### Task 5: 全局回归 + 排查残余 inline 生成

**Files:**
- 只读扫描，无固定修改文件

- [ ] **Step 1: 确认无残余任务型 inline 生成**

Run（在 `packages/service/`）:
```bash
grep -rn 'uuid.uuid4().hex\[:12\]\|token_hex(3)' src/ | grep -iv 'test'
```
Expected: 只剩非任务型用途（若有 chat_share 等非本期范围的命中，确认它们不在 4 类任务内即可忽略）。pre_analysis / pdf_processing / kg/tasks.py 三处应已无 inline 生成。

- [ ] **Step 2: 跑后端全量测试**

Run（在 `packages/service/`）: `uv run pytest`
Expected: 新测试全绿；fail/error 数不超过 pre-existing 基线（见 KNOWN_ISSUES.md：22 fail + 38 error）。逐条比对新增 fail=0。

- [ ] **Step 3: 全量 pyright**

Run: `uv run pyright`
Expected: 0 error

- [ ] **Step 4: 若前面各 Task 已分别 commit，本 Task 无新增改动则跳过 commit**

若 Step 1-3 发现问题并修复，则：
```bash
git add -A
git commit -m "refactor: 任务 ID 规范化全局回归修复"
```

---

### Task 6: 沉淀规范进 packages/service/CLAUDE.md

**Files:**
- Modify: `packages/service/CLAUDE.md`（末尾追加新节）

**Interfaces:**
- Consumes: Task 1-4 已落地的 helper 与前缀常量（规范描述必须与实现一致）

- [ ] **Step 1: 追加规范节**

在 `packages/service/CLAUDE.md` 末尾（现有"函数内 import 规范"节之后）追加：

````markdown
## 任务 ID 生成规范 (2026-07-08 task-id spec)

### 任务型 ID 必须走中央 helper, 禁止 inline 生成

```python
# 旧 (禁用, 无可读性 + 散落各处)
task_id = f"pa-{uuid.uuid4().hex[:12]}"

# 新 (统一)
from src.common.task_id import make_task_id, TASK_PREFIX_PRE_ANALYSIS
task_id = make_task_id(TASK_PREFIX_PRE_ANALYSIS)  # pa_20260708143012_a1b2c3
```

### 格式: `{prefix}_{YYYYMMDD}{HHMMSS}_{6hex}`

- 3 段, 2 个下划线分隔: 类型前缀 | 14 位香港时区时间戳 | 24 bit 随机
- 时间戳可读 + 字典序≈时间序; 下划线让 ID 可双击整选 (终端/浏览器)
- 时区用 `src/utils/timezone.py` 的 `HKT`, 跟 DB 存储一致

### 前缀常量唯一事实源 (禁止传字面量)

| 任务类型 | 常量 | 值 |
|---|---|---|
| pre_analysis | `TASK_PREFIX_PRE_ANALYSIS` | `pa` |
| ingest | `TASK_PREFIX_INGEST` | `ig` |
| kg_extract | `TASK_PREFIX_KG_EXTRACT` | `kge` |
| kg_batch | `TASK_PREFIX_KG_BATCH` | `kgb` |

新增任务类型: 在 `src/common/task_id.py` 加 `TASK_PREFIX_*` 常量, 勿在调用方写 `make_task_id("xx")` 字面量.

### 范围与例外

- **只治理任务型 ID** (跑批任务, 用户会在 UI/URL/日志看到)
- **不治理**: DB 自增主键 (evaluations/approvals) / chat UUID / auth token / request_id — 各有其诉求 (安全熵 / DB 语义), 不追求可读
- **存量 ID 不迁移**: 老 `pa-xxx` 与新 `pa_xxx` 共存, 代码对 task_id 无格式校验
````

- [ ] **Step 2: Commit**

```bash
git add packages/service/CLAUDE.md
git commit -m "docs: 后端约定新增任务 ID 生成规范"
```

---

## 完成标准

- [ ] `src/common/task_id.py` + 单测落地，6 测试全绿
- [ ] pre_analysis / ingest / kg 三处调用方走 `make_task_id`，无 inline 生成残留
- [ ] `uv run pytest` 无新增 fail（对齐 pre-existing 基线）
- [ ] `uv run pyright` 0 error
- [ ] `packages/service/CLAUDE.md` 新增"任务 ID 生成规范"节
- [ ] 存量数据零改动（无迁移脚本、无老任务改写）
