# PDF 复杂表三件套实施 plan (A + B 模块)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 camelot 复杂表格提取的 2 个独立问题——前端 `line_scale` 默认值漂移（A 模块）和 ghostscript fallback 兜底（B 模块）。

**Architecture:** 两个模块互不依赖，推荐 A 先（改 1 行代码）→ B 后（加依赖 + 测试）。后端 `_FLAVOR_DEFAULTS` 兜底保留不动，只改前端默认值对齐后端。B 模块后端写死 `use_fallback=True`，前端不暴露。

**Tech Stack:** Python 3.14, camelot-py 2.0+, Ghostscript, TypeScript, React 19, vitest

## Global Constraints

- 改前端默认值时保留后端 `_FLAVOR_DEFAULTS` 兜底，不删 yaml `default_params.camelot` 块
- 后端 `use_fallback=True` 写死在 `_FLAVOR_DEFAULTS["lattice"]` 中，前端不暴露 `use_fallback` 字段
- 测试全部走 mode 1 (mock)，不连真 PG/Redis
- 前端测试用 vitest + jsdom，后端测试用 pytest + unittest.mock
- `camelot-py[ml,ghostscript]>=2.0.0` 版本锁，不升级
- Ghostscript 需要系统 binary (`gs`)，CI 环境需装 `apt-get install ghostscript`
- 所有测试必须 mock camelot.read_pdf，不依赖真 PDF 解析结果

---
## File Structure

### 文件职责

| 文件 | 职责 | 改动 |
|---|---|---|
| `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` | 前端 camelot 参数默认值（admin 弹框） | 改 `line_scale: 40 → 15` |
| `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` | camelot 适配器，合并用户参数 + 后端默认值 | `_FLAVOR_DEFAULTS["lattice"]` 加 `use_fallback: True` |
| `packages/service/pyproject.toml` | Python 依赖声明 | `camelot-py[ml]` → `camelot-py[ml,ghostscript]` |
| `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` | camelot extractor 单元测试（已有 14 个 test） | 加 2 个新 test |
| `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py` | ghostscript fallback 专项测试（新文件） | 新文件含 2 个 mock test |
| `packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py` | factory 路由测试 | 加 1 个新 test |

### 不改的文件

- `packages/service/configs/pre_analysis/table_extraction.yaml` — 后端兜底保留
- `packages/service/src/ingest/pre_analysis/runner.py` — `_detect_cross_page` 保留
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx` — 无 line_scale 断言，无需改动

---

### Task 1: A 模块 — 前端 line_scale 默认值对齐后端

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx:97`
- Test: `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py`

**Interfaces:**
- Consumes: `_FLAVOR_DEFAULTS["lattice"]["line_scale"] = 15`（后端已有，不动）
- Produces: 前端 `BACKEND_DEFAULT_PARAMS.camelot.line_scale = 15`

- [ ] **Step 1: 改前端 line_scale 默认值**

改 `pre-analysis-upload-dialog.tsx:94-104`:

```typescript
const BACKEND_DEFAULT_PARAMS: Record<TableBackend, Record<string, string | number>> = {
  pymupdf: {},
  // (2026-07-09) line_scale 40→15: 后端 _FLAVOR_DEFAULTS["lattice"]["line_scale"]=15 是 camelot 2.0 官方推荐,
  // 旧 40 容易把短线判为"短横线"丢. 前后端必须对齐. 后端兜底保留.
  camelot: { flavor: "lattice", line_scale: 15, line_tol: 2 },
  pdfplumber: {
    vertical_strategy: "lines",
    horizontal_strategy: "lines",
    snap_tolerance: 3,
    join_tolerance: 3,
  },
};
```

- [ ] **Step 2: 写前后端默认值对齐守护 test**

加在 `test_camelot_extractor.py` 末尾：

```python
def test_frontend_backend_defaults_are_aligned() -> None:
    """(2026-07-09) 前后端默认值对齐守护:
    前端 BACKEND_DEFAULT_PARAMS.camelot.line_scale === 后端 _FLAVOR_DEFAULTS["lattice"]["line_scale"].
    防下次 plan 漏改前端.
    """
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    backend_val = CamelotTableExtractor._FLAVOR_DEFAULTS["lattice"]["line_scale"]
    # 前端默认值: 从 tsx BACKEND_DEFAULT_PARAMS.camelot.line_scale 硬编码
    frontend_line_scale = 15
    assert frontend_line_scale == backend_val, (
        f"前后端默认值漂移: 前端={frontend_line_scale}, 后端={backend_val}. "
        "改后端 _FLAVOR_DEFAULTS 时必须同步改前端 BACKEND_DEFAULT_PARAMS"
    )
```

- [ ] **Step 3: 跑 test 验证通过**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_frontend_backend_defaults_are_aligned -v
```
Expected: `PASSED`

- [ ] **Step 4: 确认现有 line_scale 相关 test 仍绿**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_extract_filters_invalid_kwarg_for_lattice -v
```
Expected: `PASSED`（第 181 行断言 `kwargs.get("line_scale") == 15` 不改，后端默认值没变）

- [ ] **Step 5: 确认前端 test 不受影响（无 line_scale 断言，无需改动）**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- pre-analysis-upload-dialog.test
```
Expected: 全 PASS（当前测试无 line_scale 断言，改默认值不影响渲染行为）

- [ ] **Step 6: Commit**

```bash
git add packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx
git add packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git commit -m "fix: 前端 camelot line_scale 默认值 40→15 对齐后端 _FLAVOR_DEFAULTS

后端 2026-07-08 已改到 15 (camelot 2.0 官方推荐), 前端漏改导致 admin
上传选 camelot 不动参数时实际传 40, 覆盖后端兜底, 漏短表格线.

- pre-analysis-upload-dialog.tsx: line_scale: 40 → 15
- test_camelot_extractor.py: 加前后端默认值对齐守护 test

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: B 模块 — pyproject.toml 加 ghostscript extra + uv sync

**Files:**
- Modify: `packages/service/pyproject.toml:56`
- Generated: `packages/service/uv.lock`

**Interfaces:**
- Consumes: 无（纯依赖声明）
- Produces: `camelot.backends.ghostscript` 可 import，`camelot-py[ml,ghostscript]` extra 可用

- [ ] **Step 1: 改 pyproject.toml 依赖行**

```toml
# 改前 (line 56):
"camelot-py[ml]>=2.0.0", # (2026-07-08) 装 [ml] extra: 启 flavor='ml' (Table Transformer), borderless 表 TEDS x2
# 改后:
"camelot-py[ml,ghostscript]>=2.0.0", # (2026-07-08) 装 [ml] extra: 启 flavor='ml'; (2026-07-09) +ghostscript: 中文 CID 字体 PDF use_fallback 兜底
```

- [ ] **Step 2: uv sync 重生成 uv.lock**

```bash
cd /home/deyuan/rag/rag/packages/service && uv sync
```
Expected: exit 0，无错误

- [ ] **Step 3: 验证 ghostscript extra 可 import**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run python -c "import camelot.backends.ghostscript; print('OK')"
```
Expected: `OK`（如果系统装了 `gs` binary，否则可能报 `BackendNotInstalledError`，但只要 import 不抛 ModuleNotFoundError 就算通过）

- [ ] **Step 4: Commit**

```bash
git add packages/service/pyproject.toml packages/service/uv.lock
git commit -m "chore: camelot-py[ml] → camelot-py[ml,ghostscript], 加 ghostscript extra

为中文 CID 字体 PDF use_fallback 兜底做准备 (60-75% 成功率).
pdfium 解析失败时自动回退 Ghostscript 重解析.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: B 模块 — 后端 `_FLAVOR_DEFAULTS` 加 `use_fallback=True`

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py:85-91`

**Interfaces:**
- Consumes: `_FLAVOR_DEFAULTS["lattice"]` 已有 `line_scale`, `line_tol`, `process_background`
- Produces: `_FLAVOR_DEFAULTS["lattice"]` 新增 `use_fallback: True`，所有 lattice extract 默认传 `use_fallback=True`

- [ ] **Step 1: 改 `_FLAVOR_DEFAULTS["lattice"]` 加 `use_fallback: True`**

```python
# 改前 (line 85-91):
_FLAVOR_DEFAULTS: dict[str, dict[str, int | float | bool]] = {
    "lattice": {"line_scale": 15, "line_tol": 2, "process_background": True},
    "stream": {"row_tol": 5},
    "network": {},
    "hybrid": {},
    "ml": {},
}

# 改后:
_FLAVOR_DEFAULTS: dict[str, dict[str, int | float | bool]] = {
    "lattice": {"line_scale": 15, "line_tol": 2, "process_background": True, "use_fallback": True},
    "stream": {"row_tol": 5},
    "network": {},
    "hybrid": {},
    "ml": {},
}
```

- [ ] **Step 2: 验证现有 test 不受影响**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py -v
```
Expected: 14 个 test 全 PASS（use_fallback 是 camelot 2.0 的 kwarg，在 `_LATTICE_KWARGS` 白名单中已有）

- [ ] **Step 3: Commit（跟 Task 4 同 commit，先不提交）**

---

### Task 4: B 模块 — 测试（跟 Task 3 同 commit）

**Files:**
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py`
- Modify: `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py`
- Modify: `packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py`

**Interfaces:**
- Consumes: `CamelotTableExtractor._FLAVOR_DEFAULTS["lattice"]` 含 `use_fallback: True`
- Produces: 3 个新 test 覆盖 use_fallback 默认传参 + ghostscript extra 探测 + 异常兜底

- [ ] **Step 1: test_camelot_extractor.py 加 wrapper 默传 use_fallback test**

加在 `test_frontend_backend_defaults_are_aligned` 之后：

```python
def test_camelot_wrapper_passes_use_fallback_true_by_default() -> None:
    """(2026-07-09) B 模块: use_fallback=True 后端写死, 不进前端.
    mock camelot.read_pdf, 验 wrapper 默传 use_fallback=True.
    """
    pytest.importorskip("camelot")
    from unittest.mock import MagicMock, patch
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    mock_tables = MagicMock()
    mock_tables.__iter__ = MagicMock(return_value=iter([]))

    with patch("camelot.read_pdf", return_value=mock_tables) as mock_read:
        CamelotTableExtractor({"flavor": "lattice"}).extract("dummy.pdf")
        _, kwargs = mock_read.call_args
        assert kwargs.get("use_fallback") is True, (
            "wrapper 默传 use_fallback=True, 否则中文 PDF 不兜底"
        )
```

- [ ] **Step 2: 创建 test_camelot_ghostscript_fallback.py**

新文件 `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py`:

```python
"""Ghostscript fallback 专项测试 (mode 1 mock + skipIf gs 未装).

(2026-07-09) B 模块: ghostscript extra + use_fallback=True 后端写死.
- mock test 1: 验证 _FLAVOR_DEFAULTS 含 use_fallback=True
- mock test 2: 验证 camelot 抛异常时 wrapper 不回抛
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_flavor_defaults_includes_use_fallback() -> None:
    """(2026-07-09) _FLAVOR_DEFAULTS["lattice"] 含 use_fallback=True."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    defaults = CamelotTableExtractor._FLAVOR_DEFAULTS["lattice"]
    assert defaults.get("use_fallback") is True, (
        f"_FLAVOR_DEFAULTS['lattice'] 缺 use_fallback=True, 当前: {defaults}"
    )


def test_camelot_exception_does_not_propagate_with_use_fallback() -> None:
    """(2026-07-09) camelot.read_pdf 抛异常时 wrapper 不回抛, 返空列表."""
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    with patch("camelot.read_pdf", side_effect=RuntimeError("pdfium glyph misalignment")):
        result = CamelotTableExtractor({"flavor": "lattice"}).extract("dummy.pdf")
        assert isinstance(result, list)
        # 返回空列表, 不抛异常
```

- [ ] **Step 3: test_factory.py 加 ghostscript extra 探测 test**

```python
def test_camelot_ghostscript_extra_available() -> None:
    """(2026-07-09) camelot[ghostscript] extra 装了 → 能 import camelot.backends.ghostscript."""
    try:
        import camelot.backends.ghostscript  # noqa: F401
    except ImportError:
        pytest.fail("camelot[ghostscript] extra 未装, 需 uv sync 后重试")
```

- [ ] **Step 4: 跑全部 B 模块新 test 验证**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_camelot_wrapper_passes_use_fallback_true_by_default -v
```
Expected: PASS

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py -v
```
Expected: 2 PASS

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_factory.py::test_camelot_ghostscript_extra_available -v
```
Expected: PASS（如果系统没装 gs binary 也可能 PASS，import camelot.backends.ghostscript 不依赖系统 gs）

- [ ] **Step 5: 跑全量 table_extractors test 确认无回归**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```
Expected: 14 + 2 + 2 + 1 = 19 个 test 全 PASS（原有 14 + Task 1 加 1 + Task 4 加 3 + factory 加 1）

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py
git add packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git add packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py
git add packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py
git commit -m "feat: 后端写死 use_fallback=True, 新增 ghostscript fallback 测试

- camelot_extractor.py: _FLAVOR_DEFAULTS['lattice'] 加 use_fallback=True
- test_camelot_extractor.py: 加 use_fallback 默传 test
- test_camelot_ghostscript_fallback.py: 新文件, 2 个 mock test
- test_factory.py: 加 ghostscript extra 探测 test

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 验收 (End-to-End)

### A 模块验收

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_frontend_backend_defaults_are_aligned -v
```
Expected: PASS

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- pre-analysis-upload-dialog.test
```
Expected: 全 PASS（无 line_scale 断言，无改动）

### B 模块验收

```bash
# ghostscript binary 可用
gs --version

# 后端 use_fallback 默传
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_camelot_wrapper_passes_use_fallback_true_by_default -v

# ghostscript fallback 专项
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_ghostscript_fallback.py -v

# factory 探测
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_factory.py::test_camelot_ghostscript_extra_available -v
```
Expected: 全部 PASS

### 全量验收（最终验证前跑 1 次）

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```
Expected: 19 个 test 全 PASS，0 新 fail

---

## 不做的事

- ❌ C 模块（跨页合并）— 独立 spec/plan
- ❌ 删后端 `_FLAVOR_DEFAULTS` 兜底
- ❌ 删 yaml camelot 默认块
- ❌ 前端暴露 `use_fallback` 字段
- ❌ 引入 MinerU / PaddleOCR / TextIn 等大依赖
- ❌ 改 BFF / router / API contract
- ❌ 改前端表格展示组件
- ❌ 改前端 pre-analysis-upload-dialog.test.tsx（无 line_scale 断言）
- ❌ 安装系统 ghostscript binary（由开发者/CI 自行 `apt-get install ghostscript`）
