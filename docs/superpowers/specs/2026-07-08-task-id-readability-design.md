# 任务 ID 可读性规范化设计

> 日期: 2026-07-08
> 范围: 后端 `packages/service/src/` 任务型 ID 生成
> 目标: 把无可读性的 `pa-3f9a1c2b4d5e` 换成肉眼可读、可排序、带类型前缀的统一格式

## 1. 背景与问题

当前 pre_analysis 任务 ID 形如 `pa-3f9a1c2b4d5e`（`pa-` + `uuid4().hex[:12]`），后半段是纯随机 hex，没有任何可读信息：看不出任务何时创建、无法按时间排序、日志里一串乱码难定位。

调查发现全项目**任务型 ID 生成散落各处、无统一工具**：

| 任务类型 | 生成位置 | 现状格式 | 前缀 |
|---|---|---|---|
| pre_analysis | `src/ingest/pre_analysis/router.py:102` | `pa-{uuid4().hex[:12]}` | `pa-` |
| ingest (pdf_processing) | `src/ingest/pdf_processing/router.py:126-128` | `{YYYYMMDD}-{HHMMSS}-{6hex}` | 无 |
| kg_extract | `src/kg/tasks.py:39` (`TaskStore.submit`) | `{uuid4().hex[:12]}` | 无 |
| kg_batch | `src/kg/tasks.py:39` (同上, `kind` 区分) | `{uuid4().hex[:12]}` | 无 |

其中 ingest 的 `{YYYYMMDD}-{HHMMSS}-{6hex}` 已经是"时间戳+随机"可读范式（Pinterest / CI-CD 业界做法），只差一个类型前缀——本设计把它抽成全项目统一标准。

## 2. 目标与非目标

### 目标
- 新增**唯一中央 helper** `make_task_id(prefix)`，全项目任务型 ID 都走它
- 统一格式：`{prefix}_{YYYYMMDD}{HHMMSS}_{6hex}`，例 `pa_20260708143012_a1b2c3`
- 覆盖 4 类任务：pre_analysis / ingest / kg_extract / kg_batch
- 消除 3 处散落的 inline 生成代码

### 非目标（明确不动）
- **DB 自增整数主键**（evaluations / approvals / evaluation_samples）——动它要改迁移+外键，风险高收益低
- **chat 会话 UUID / chat share_id**——非"任务"，可读性无诉求
- **auth token / request_id**——要的是熵和安全，不能可读
- **前端 BFF batch task_id**（`app/api/knowledge/batch/route.ts`）——前端内存态、不持久、不进 DB/URL，本期不动
- **存量数据不改（重要）**：本设计**只改 ID 生成逻辑，不触碰任何已存在的任务**。DB 里的老 `pa-xxx`、S3 老 key、老任务的下载/重试路径全部保持原样，不写迁移脚本、不批量改 ID、不动老数据。新格式只对本次改动之后新创建的任务生效（见 §6 兼容性）

## 3. ID 格式规范

```
{prefix}_{YYYYMMDD}{HHMMSS}_{6hex}
```

示例: `pa_20260708143012_a1b2c3`（24 字符）

**三段结构（2 个下划线分隔）:**

| 段 | 内容 | 作用 |
|---|---|---|
| `pa` | 类型前缀 | 一眼知道是什么任务，日志/报错定位快 |
| `20260708143012` | 时间戳 `YYYYMMDD`+`HHMMSS`（14 位，无内部分隔） | 肉眼可读 + 字典序≈时间序 + 缩小碰撞窗口到"同秒" |
| `a1b2c3` | `secrets.token_hex(3)`（24 bit 随机） | 同秒内防碰撞 |

**分隔符决策:** 只用 2 个下划线切出「前缀 | 时间 | 随机」三段。理由：
- 前缀与年份贴一起（`pa2026`）会糊成一团，需要分隔
- 下划线让 ID 在终端/浏览器里可**双击整体选中**（`_` 算单词字符，`-` 会断词）——Stripe 用 `_` 同理
- 时间戳内部 14 位不再插分隔符，省字符、更紧凑

**时区:** 时间戳用项目统一的香港时区 `HKT`（`src/utils/timezone.py`，UTC+8），与 DB 存储时区一致，避免日志时间与 DB 记录对不上。

**前缀映射:**

| 任务类型 | 新前缀 | 对应 `kind` / 模块 |
|---|---|---|
| pre_analysis | `pa` | pre_analysis |
| ingest | `ig` | pdf_processing |
| kg_extract | `kge` | `kind="kg_extract"` |
| kg_batch | `kgb` | `kind="kg_batch"` |

## 4. 架构设计

### 4.1 中央 helper

新增 `src/common/task_id.py`（`src/common/` 已是项目共享工具位）：

```python
"""任务 ID 统一生成: {prefix}_{YYYYMMDD}{HHMMSS}_{6hex}"""

import secrets
from datetime import datetime

from src.utils.timezone import HKT

# 任务类型前缀常量 (唯一事实源, 禁止调用方写字面量)
TASK_PREFIX_PRE_ANALYSIS = "pa"
TASK_PREFIX_INGEST = "ig"
TASK_PREFIX_KG_EXTRACT = "kge"
TASK_PREFIX_KG_BATCH = "kgb"


def make_task_id(prefix: str) -> str:
    """生成可读任务 ID: {prefix}_{YYYYMMDD}{HHMMSS}_{6hex}

    入参:
        prefix: 类型前缀 (用本模块 TASK_PREFIX_* 常量, 勿传字面量)
    回参:
        str, 例 'pa_20260708143012_a1b2c3' (24 字符)
    """
    ts = datetime.now(HKT).strftime("%Y%m%d%H%M%S")  # 香港时区, 跟 DB 一致
    rand = secrets.token_hex(3)  # 24 bit 随机, 同秒内防碰撞
    return f"{prefix}_{ts}_{rand}"
```

**边界与依赖:** 纯函数，只依赖 `secrets` + `datetime` + 项目 `HKT` 常量；无 DB、无 I/O、无全局状态。可独立单测。

### 4.2 调用方改造（3 处）

1. **pre_analysis** `router.py:102`
   `task_id = f"pa-{uuid.uuid4().hex[:12]}"`
   → `task_id = make_task_id(TASK_PREFIX_PRE_ANALYSIS)`
   （删掉不再需要的 `import uuid`，若无他用）

2. **ingest** `pdf_processing/router.py:126-128` 的 `_new_task_id()`
   函数体改为 `return make_task_id(TASK_PREFIX_INGEST)`，保留 `_new_task_id` 包装名（两处调用点 `:308` `:445` 不动）。清理 `_new_task_id` 独占的 `datetime` / `secrets` import（若他处仍用则保留）。

3. **kg** `tasks.py:39` `TaskStore.submit`
   当前 `task_id = uuid.uuid4().hex[:12]` 不区分 kind。改为按 `kind` 选前缀：

   ```python
   from src.common.task_id import (
       TASK_PREFIX_KG_BATCH, TASK_PREFIX_KG_EXTRACT, make_task_id,
   )

   def submit(self, kind: str, payload: dict) -> str:
       prefix = TASK_PREFIX_KG_BATCH if kind == "kg_batch" else TASK_PREFIX_KG_EXTRACT
       task_id = make_task_id(prefix)
       ...
   ```

### 4.3 不改动的消费方（验证兼容即可）

以下消费 task_id 的位置**无需改代码**，因为新 ID 仍是 URL/文件名/DB 安全的字符串，且更短（24 vs 15 字符也在 `String(36)` 列容量内）：

- DB 列 `pre_analysis_tasks.id` / `ingest_tasks.id`（均 `String(36)`，24 字符 ✓）
- S3 对象 key 拼接（`pre_analysis_inputs/{task_id}/...`、`inputs/{task_id}/`）
- 前端 URL 路由 `[task_id]`、API client、TanStack Query key
- 日志 `_logger.info("...task=%s...")`

## 5. 错误处理

`make_task_id` 是纯函数，唯一潜在异常来自 `secrets` / `datetime`（系统级，不可恢复），不做额外 try/except——与现有 `_new_task_id` 一致，让异常自然向上抛。

## 6. 兼容性与迁移

**存量 ID 不迁移。** 老任务的 `pa-3f9a1c2b4d5e` 继续存在于 DB / S3，读取/下载/重试路径对 ID 格式无假设（只当字符串用），新老 ID 共存无冲突：

- **无格式校验**：代码中没有对 `pa-` 前缀或长度做正则校验的地方（已确认），改格式不会打破任何断言
- **S3 key**：老 ID 的对象在老 key 下，新 ID 在新 key 下，各自独立
- **前缀分隔符从 `-` 变 `_`**：老 `pa-xxx` 与新 `pa_xxx` 前缀段不同，但都是合法字符串主键，查询按精确 id 匹配，不受影响

**风险点排查**：实施时需 grep 确认无任何代码对 task_id 做 `split("-")` / 前缀正则 / 长度断言（初步调查未发现，实施阶段二次确认）。

## 7. 测试策略（模式 1 mock）

新增 `tests/common/test_task_id.py`（纯单测，0 PG 依赖）：

1. **格式断言**：`make_task_id("pa")` 匹配正则 `^pa_\d{14}_[0-9a-f]{6}$`
2. **前缀正确**：各 `TASK_PREFIX_*` 常量拼接到位
3. **时间戳可解析**：中间 14 位能被 `datetime.strptime(..., "%Y%m%d%H%M%S")` 解回
4. **时区正确**：monkeypatch 固定时间，断言用 HKT 而非 UTC/本地
5. **唯一性**：同一时间戳下连生成 N 个，随机段不同（monkeypatch `datetime.now` 固定，验 `secrets` 部分变化）
6. **长度**：固定前缀下总长稳定（`pa` → 24 字符）

调用方改造后跑既有测试确认无回归：
- `tests/` 下 pre_analysis / ingest / kg 相关测试全绿（pre-existing fail 不算）
- 若既有测试对 task_id 格式有硬编码断言（如 `assert task_id.startswith("pa-")`），同步更新为 `pa_`

## 8. 更新 CLAUDE.md 规范说明

在 `packages/service/CLAUDE.md` 新增一节"任务 ID 生成规范"（跟现有"日志使用约定""函数内 import 规范"等后端局部约定并列），把本设计沉淀为编码铁律，防后人再散落写 `uuid.uuid4().hex[:12]`。**这一步跟代码同批落地**（helper 实现后再写，避免规则先于实现变空头支票）。待写入原文：

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

## 9. 实施顺序

1. 新增 `src/common/task_id.py` + `tests/common/test_task_id.py`（TDD：先测后码）
2. 改 3 处调用方（pre_analysis / ingest / kg）
3. grep 排查格式断言/split，修既有测试硬编码
4. 在 `packages/service/CLAUDE.md` 新增"任务 ID 生成规范"节（原文见 §8）
5. `uv run ruff format` → `uv run ruff check --fix` → `uv run pyright`（0 error）→ `uv run pytest`（0 新 fail）
6. commit（`refactor:` 前缀）

## 10. 关联文档

- 项目铁律: [CLAUDE.md](../../../CLAUDE.md)
- 后端约定: [packages/service/CLAUDE.md](../../../packages/service/CLAUDE.md)
- 业界最佳实践参考: Pragmatic Engineer《Designing Better IDs》、Pinterest Job IDs、Stripe 前缀式 ID
