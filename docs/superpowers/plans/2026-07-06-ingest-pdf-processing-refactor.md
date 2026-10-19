# Ingest 目录重组：pdf_processing 子包化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `src/ingest/` 中所有 PDF 转 markdown 相关的代码 (analyzers/ + converters/ + api.py + pipeline.py + models.py + store.py + schemas_presign.py + archive_handler.py + markdown_passthrough.py + __init__.py) 搬进 `pdf_processing/` 子包，同时拆分 api.py 中的 ingest 路由和 pre_analysis 路由。

**Architecture:** 
- `src/ingest/pdf_processing/` 新建子包，git mv 搬入全部文件
- `src/ingest/api.py` 拆成 `pdf_processing/router.py` (ingest 路由) + `pre_analysis/router.py` (预分析路由)
- `src/ingest/` 顶层只剩 `pre_analysis/` + 零散残留文件 (后续清理)
- 测试文件同步移动/改 import 路径
- 0 业务改动，纯重命名 + 路径调整

**Tech Stack:** Python 3.14 + git mv (rename detection) + sed/手动改 import

---

## File Structure

### 搬入 `pdf_processing/` 的文件清单

| 来源 | 目标 | 说明 |
|------|------|------|
| `analyzers/__init__.py` | `pdf_processing/analyzers/__init__.py` | 重导出 PDFAnalyzer/PDFInfo/analyze_pdf_complexity + CADAnalyzer/CADInfo |
| `analyzers/pdf.py` | `pdf_processing/analyzers/pdf.py` | PDFAnalyzer + PDFInfo |
| `analyzers/cad.py` | `pdf_processing/analyzers/cad.py` | CADAnalyzer + CADInfo |
| `converters/__init__.py` | `pdf_processing/converters/__init__.py` | CONVERTERS 字典 + classify_files + get_converter |
| `converters/base.py` | `pdf_processing/converters/base.py` | Converter ABC |
| `converters/kreuzberg.py` | `pdf_processing/converters/kreuzberg.py` | PDF→markdown (简单 PDF) |
| `converters/mineru.py` | `pdf_processing/converters/mineru.py` | PDF→markdown (复杂 PDF, docker) |
| `converters/cad.py` | `pdf_processing/converters/cad.py` | CAD 转换器 (EzdxfConverter + ODA) |
| `markdown_passthrough.py` | `pdf_processing/markdown_passthrough.py` | .md 直通 |
| `api.py` | `pdf_processing/router.py` | 拆: ingest 路由 + dataclass (IngestTask/OutputFile/InputFile) |
| `pipeline.py` | `pdf_processing/pipeline.py` | 主流水线 (process_files/process_documents/process_cad_files/process_passthrough) |
| `models.py` | `pdf_processing/models.py` | IngestTask ORM |
| `store.py` | `pdf_processing/store.py` | IngestTask store |
| `schemas_presign.py` | `pdf_processing/schemas_presign.py` | presign schema |
| `archive_handler.py` | `pdf_processing/archive_handler.py` | 压缩包处理 |
| `__init__.py` | `pdf_processing/__init__.py` | 重导出 ingest_router + process_* + PDFAnalyzer + ... |

### 新增文件

| 文件 | 说明 |
|------|------|
| `pre_analysis/router.py` | 从 api.py 拆出: pre_analysis_router + _run_pre_analysis + _orphan_cleanup |
| `tests/ingest/pre_analysis/test_router.py` | 现有 test_api.py 中 pre_analysis 相关的测试 (移过来) |
| `tests/ingest/pdf_processing/` | 原 tests/ingest/ 中搬过来的测试文件 |

### 删除文件

| 文件 | 原因 |
|------|------|
| `src/ingest/api.py` | 内容已拆到 pdf_processing/router.py + pre_analysis/router.py |
| `src/ingest/analyzers/` | 已搬入 pdf_processing/ |
| `src/ingest/converters/` | 已搬入 pdf_processing/ |

### 改 import 路径的文件

| 文件 | 改动 |
|------|------|
| `src/__init__.py:55-58, 120-128` | `from .ingest import ingest_router, pre_analysis_router` → `from .ingest.pdf_processing import ingest_router, process_*` + `from .ingest.pre_analysis import pre_analysis_router` |
| `src/core/lifespan.py:168` | `from src.ingest.api import _orphan_cleanup` → `from src.ingest.pre_analysis.router import _orphan_cleanup` |
| `tests/ingest/test_api_*.py` | import 路径改 `from src.ingest.pdf_processing.router import ...` |
| `tests/ingest/test_models.py` | `from src.ingest.models` → `from src.ingest.pdf_processing.models` |
| `tests/ingest/test_store_mock.py` | `from src.ingest.store` → `from src.ingest.pdf_processing.store` |
| `tests/ingest/test_analyzer.py` | `from src.ingest.analyzers.pdf` → `from src.ingest.pdf_processing.analyzers.pdf` |
| `tests/ingest/test_converters*.py` | `from src.ingest.converters` → `from src.ingest.pdf_processing.converters` |
| `tests/ingest/test_cad_*.py` | `from src.ingest.converters.cad` → `from src.ingest.pdf_processing.converters.cad` |
| `tests/ingest/test_analyzers.cad` | `from src.ingest.analyzers.cad` → `from src.ingest.pdf_processing.analyzers.cad` |
| `tests/ingest/test_pipeline_*.py` | `from src.ingest.pipeline` → `from src.ingest.pdf_processing.pipeline` |
| `tests/ingest/test_markdown_passthrough.py` | `from src.ingest.markdown_passthrough` → `from src.ingest.pdf_processing.markdown_passthrough` |
| `tests/ingest/test_archive_handler.py` | `from src.ingest.archive_handler` → `from src.ingest.pdf_processing.archive_handler` |
| `tests/ingest/test_api_presign.py` | `from src.ingest.schemas_presign` → `from src.ingest.pdf_processing.schemas_presign` |
| `tests/storage/test_init_exports.py` | `from src.ingest.models` → `from src.ingest.pdf_processing.models` |
| `tests/integration/test_mineru_retry_e2e.py` | `from src.ingest.converters` → `from src.ingest.pdf_processing.converters` |

---

## Task 1: git mv 搬入 pdf_processing/

- [ ] **Step 1: 创建目录结构**

```bash
cd packages/service/src/ingest
mkdir -p pdf_processing/analyzers pdf_processing/converters
```

- [ ] **Step 2: git mv 所有文件**

```bash
cd packages/service/src/ingest

# analyzers/ 整个目录
git mv analyzers/__init__.py pdf_processing/analyzers/__init__.py
git mv analyzers/pdf.py pdf_processing/analyzers/pdf.py
git mv analyzers/cad.py pdf_processing/analyzers/cad.py

# converters/ 整个目录
git mv converters/__init__.py pdf_processing/converters/__init__.py
git mv converters/base.py pdf_processing/converters/base.py
git mv converters/kreuzberg.py pdf_processing/converters/kreuzberg.py
git mv converters/mineru.py pdf_processing/converters/mineru.py
git mv converters/cad.py pdf_processing/converters/cad.py

# 顶层文件
git mv markdown_passthrough.py pdf_processing/markdown_passthrough.py
git mv pipeline.py pdf_processing/pipeline.py
git mv models.py pdf_processing/models.py
git mv store.py pdf_processing/store.py
git mv schemas_presign.py pdf_processing/schemas_presign.py
git mv archive_handler.py pdf_processing/archive_handler.py
```

- [ ] **Step 3: 处理 api.py (先不 mv, 后面拆)**

先放着，Task 2 拆。

- [ ] **Step 4: 处理 __init__.py (先不 mv, 后面改)**

先放着，Task 3 改。

- [ ] **Step 5: 删除空目录**

```bash
cd packages/service/src/ingest
rmdir analyzers converters 2>/dev/null; ls
```

Expected: `pdf_processing/` + `pre_analysis/` + `api.py` + `__init__.py`

---

## Task 2: 拆分 api.py → pdf_processing/router.py + pre_analysis/router.py

- [ ] **Step 1: 读 api.py 确定拆分边界**

```bash
cd packages/service/src/ingest
wc -l api.py
```

Line boundaries:
- `# ==============` at line ~274: ingest router 开头
- `# ==================== pre_analysis (2026-07-02 新增) ====================` at line ~786

- [ ] **Step 2: 提取 ingest 部分 → pdf_processing/router.py**

`pdf_processing/router.py` 包含:
- 顶部 import (from ...core.audit 等 + from .pipeline + from .schemas_presign)
- dataclass: `OutputFile`, `InputFile`, `IngestTask`
- 辅助函数: `_dict_to_task`, `_save`, `_load`, `_list_user`, `user_hash_for`, `_new_task_id`, `_mime_for`, `_check_token`, `_resolve_task`, `_collect_output_files_legacy`, `_find_output_file`, `_build_workdir_uri`, `_uri_for_backend`, `_mime_for_name`, `_collect_output_files`
- ingest_router 端点: `presign_upload`, `finalize_upload`, `upload`, `_run_ingest`, `list_tasks`, `get_task`, `read_task_file`, `download_zip`

```python
# packages/service/src/ingest/pdf_processing/router.py
"""Ingest HTTP API — PDF 转 markdown 路由 (2026-07-06 从 api.py 拆出)."""
# ruff: noqa: E402
from __future__ import annotations

# ... 完整内容从 api.py 行 1-780 复制
```

- [ ] **Step 3: 提取 pre_analysis 部分 → pre_analysis/router.py**

`pre_analysis/router.py` 包含:
- 顶部 import: `from . import (PreAnalysisStage, ...)` + `from .runner import PreAnalysisRunner`
- pre_analysis_router 端点: `upload_pre_analysis`, `list_pre_analysis_tasks`, `get_pre_analysis_task`, `download_pre_analysis_zip`, `list_pre_analysis_stages`, `retry_pre_analysis_task`
- 后台函数: `_run_pre_analysis`, `_orphan_cleanup_pre_analysis_tasks`

```python
# packages/service/src/ingest/pre_analysis/router.py
"""pre_analysis HTTP API — PDF 预分析路由 (2026-07-06 从 api.py 拆出)."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
import json
import uuid
from loguru import logger

from ...core.audit import audited
from ...middleware.auth import CurrentUser
from ...permissions.guards import require_super_admin
from ...storage.object_store import get_object_store
from ...storage import session_scope
from . import (
    PreAnalysisStage,
    PreAnalysisStageStore,
    PreAnalysisTaskStore,
    pa_list_user_tasks,
    pa_load_task,
    pa_save_task,
)
from .models import PreAnalysisTask
from .stage_store import PreAnalysisStageStore as _StageStore
```

然后把 api.py 中从 `# ==================== pre_analysis (2026-07-02 新增) ====================` 开始到文件尾的代码复制过来。

- [ ] **Step 4: git mv api.py → pdf_processing/router.py**

```bash
cd packages/service/src/ingest
git mv api.py pdf_processing/router.py
```

然后删除 api.py 中 pre_analysis 相关代码（行 786 到文件尾），只剩 ingest 路由。

- [ ] **Step 5: 更新 pdf_processing/router.py 的包内 import**

把 `from .pipeline` → `from .pdf_processing.pipeline` 改回 `from .pipeline` (已经在同一个包内).
把 `from .pre_analysis import ...` 删掉 (pre_analysis import 只在 pre_analysis/router.py).

- [ ] **Step 6: 删除 `src/ingest/api.py`**

```bash
rm packages/service/src/ingest/api.py
```

---

## Task 3: 更新 `src/ingest/__init__.py` 重导出路径

- [ ] **Step 1: 写新的 `pdf_processing/__init__.py`**

```python
"""pdf_processing 子包 — PDF 转 markdown 流水线 (2026-07-06)."""

from .pipeline import (
    process_cad_files,
    process_documents,
    process_files,
    process_passthrough,
)
from .analyzers.pdf import PDFAnalyzer, PDFInfo, analyze_pdf_complexity
from .converters import get_converter, classify_files

from .router import (  # noqa: F401
    IngestTask,
    OutputFile,
    ingest_router,
)
from .store import save_task_dict, load_task_dict, list_user_task_dicts
from .models import IngestTask as ORMIngestTask  # noqa: F401  # alembic 反射

__all__ = [
    "process_files",
    "process_documents",
    "process_cad_files",
    "process_passthrough",
    "PDFAnalyzer",
    "analyze_pdf_complexity",
    "PDFInfo",
    "get_converter",
    "classify_files",
    "ingest_router",
    "IngestTask",
    "OutputFile",
]
```

- [ ] **Step 2: 改 `src/ingest/__init__.py` 指向 pdf_processing**

```python
"""rag_ingest 业务包（多格式文档 → markdown 流水线）

public API 包含:
- PDF 转 markdown: pdf_processing/ 子包
- PDF 预分析: pre_analysis/ 子包
"""

from .pdf_processing import (
    IngestTask,
    OutputFile,
    PDFAnalyzer,
    PDFInfo,
    analyze_pdf_complexity,
    get_converter,
    ingest_router,
    process_cad_files,
    process_documents,
    process_files,
    process_passthrough,
)
from .pre_analysis import pre_analysis_router  # noqa: F401  # (2026-07-02) PDF 预分析 router

__all__ = [
    "process_files",
    "process_documents",
    "process_cad_files",
    "process_passthrough",
    "PDFAnalyzer",
    "analyze_pdf_complexity",
    "PDFInfo",
    "get_converter",
    "ingest_router",
    "IngestTask",
    "OutputFile",
    "pre_analysis_router",
]
```

- [ ] **Step 3: 更新 `pre_analysis/__init__.py` 导出 pre_analysis_router**

`packages/service/src/ingest/pre_analysis/__init__.py` 加:

```python
from .router import pre_analysis_router  # noqa: F401  # 路由注册用
```

- [ ] **Step 4: 删除旧的 `ingest/__init__.py` 引用 (已经改完)**

---

## Task 4: 更新 `src/__init__.py` 路由注册

- [ ] **Step 1: 改 `register_routers()` 函数**

`packages/service/src/__init__.py:55-58`:

```python
from .ingest.pdf_processing import (
    ingest_router,
)
from .ingest.pre_analysis import pre_analysis_router  # (2026-07-02) PDF 预分析
```

- [ ] **Step 2: 改 public API 导出 (line 120-128)**

```python
from .ingest.pdf_processing import (
    PDFAnalyzer,
    PDFInfo,
    analyze_pdf_complexity,
    get_converter,
    process_cad_files,
    process_documents,
    process_files,
    process_passthrough,
)
```

---

## Task 5: 更新 `src/core/lifespan.py` import

- [ ] **Step 1: 改 import**

`packages/service/src/core/lifespan.py:168`:

```python
# 原:
from src.ingest.api import _orphan_cleanup_pre_analysis_tasks
# 改为:
from src.ingest.pre_analysis.router import _orphan_cleanup_pre_analysis_tasks
```

---

## Task 6: 更新测试文件 import 路径

- [ ] **Step 1: 批量替换测试 import**

```bash
cd packages/service/tests/ingest

# 把旧 import 换成新 import
# 注: 有些文件可能同时引用多个模块, 每行单独 sed

# test_analyzer.py
sed -i 's|src\.ingest\.analyzers\.pdf|src.ingest.pdf_processing.analyzers.pdf|g' test_analyzer.py

# test_api_mock.py
sed -i 's|src\.ingest\.api|src.ingest.pdf_processing.router|g' test_api_mock.py

# test_api_ingest_uri.py
sed -i 's|src\.ingest\.api|src.ingest.pdf_processing.router|g' test_api_ingest_uri.py

# test_api_presign.py
sed -i 's|src\.ingest\.api|src.ingest.pdf_processing.router|g' test_api_presign.py
sed -i 's|src\.ingest\.schemas_presign|src.ingest.pdf_processing.schemas_presign|g' test_api_presign.py

# test_archive_handler.py
sed -i 's|src\.ingest\.archive_handler|src.ingest.pdf_processing.archive_handler|g' test_archive_handler.py

# test_converters.py
sed -i 's|src\.ingest\.analyzers\.pdf|src.ingest.pdf_processing.analyzers.pdf|g' test_converters.py
sed -i 's|src\.ingest\.converters|src.ingest.pdf_processing.converters|g' test_converters.py

# test_converters_init.py
sed -i 's|src\.ingest\.converters|src.ingest.pdf_processing.converters|g' test_converters_init.py

# test_markdown_passthrough.py
sed -i 's|src\.ingest\.markdown_passthrough|src.ingest.pdf_processing.markdown_passthrough|g' test_markdown_passthrough.py

# test_models.py
sed -i 's|src\.ingest\.models|src.ingest.pdf_processing.models|g' test_models.py

# test_pipeline_api_contract.py
sed -i 's|src\.ingest\.pipeline|src.ingest.pdf_processing.pipeline|g' test_pipeline_api_contract.py

# test_pipeline_path.py
sed -i 's|src\.ingest\.pipeline|src.ingest.pdf_processing.pipeline|g' test_pipeline_path.py

# test_pipeline_mock.py
sed -i 's|src\.ingest\.pipeline|src.ingest.pdf_processing.pipeline|g' test_pipeline_mock.py

# test_process_files_routing.py
sed -i 's|src\.ingest\.pipeline|src.ingest.pdf_processing.pipeline|g' test_process_files_routing.py

# test_e2e_multi_format.py
sed -i 's|src\.ingest\.pipeline|src.ingest.pdf_processing.pipeline|g' test_e2e_multi_format.py

# test_store_mock.py
sed -i 's|src\.ingest\.models|src.ingest.pdf_processing.models|g' test_store_mock.py
sed -i 's|src\.ingest\.store|src.ingest.pdf_processing.store|g' test_store_mock.py

# CAD 相关
sed -i 's|src\.ingest\.analyzers\.cad|src.ingest.pdf_processing.analyzers.cad|g' test_cad_analyzer.py
sed -i 's|src\.ingest\.converters\.cad|src.ingest.pdf_processing.converters.cad|g' test_cad_converter.py
sed -i 's|src\.ingest\.converters|src.ingest.pdf_processing.converters|g' test_cad_converter.py
sed -i 's|src\.ingest\.converters\.cad|src.ingest.pdf_processing.converters.cad|g' test_cad_oda.py
```

- [ ] **Step 2: 更新 tests/storage/test_init_exports.py**

```bash
cd packages/service/tests/storage
sed -i 's|src\.ingest\.models|src.ingest.pdf_processing.models|g' test_init_exports.py
```

- [ ] **Step 3: 更新 tests/integration/test_mineru_retry_e2e.py**

```bash
cd packages/service/tests/integration
sed -i 's|src\.ingest\.converters|src.ingest.pdf_processing.converters|g' test_mineru_retry_e2e.py
```

- [ ] **Step 4: 更新 pre_analysis 测试**

```bash
cd packages/service/tests/ingest/pre_analysis
# test_api.py → 拆成 test_router.py (pre_analysis 路由测试, 从原 test_api.py 复制 pre_analysis 相关)
# 新建 test_router.py, 保留原 import 路径不变 (from src.ingest.pre_analysis)
# 把 test_api.py 中 pre_analysis 相关的 7 个测试移入 test_router.py
```

---

## Task 7: 验证 + 清理

- [ ] **Step 1: 运行后端测试**

```bash
cd packages/service
uv run pytest tests/ingest/pre_analysis/ -v --no-cov
```

Expected: 45 passed, 2 skipped (跟搬移前一样)

- [ ] **Step 2: 运行迁移测试**

```bash
uv run pytest tests/migrations/test_pre_analysis_task_config.py -v --no-cov
```

Expected: 5 passed

- [ ] **Step 3: 运行合同测试**

```bash
uv run pytest tests/test_api_contract.py -v --no-cov
```

Expected: 4 passed

- [ ] **Step 4: 运行 pdf_processing 相关测试**

```bash
# 暂时可能跑不全 (测试文件还没搬), 但至少确认改过 import 的测试能过
uv run pytest tests/ingest/test_models.py tests/ingest/test_store_mock.py -v --no-cov
```

- [ ] **Step 5: pyright + ruff**

```bash
uv run ruff format && uv run ruff check --fix && uv run pyright
```

Expected: 0 error

- [ ] **Step 6: git status 检查**

```bash
git status --short
```

确认: `pdf_processing/` 下所有文件 Added/Renamed, `analyzers/` + `converters/` 已删除, `api.py` 已删除, `__init__.py` Modified.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(service): move all PDF-to-markdown files into pdf_processing/ subpackage"
```

---

## 回滚方案

如果出了问题:

```bash
git checkout HEAD~1 packages/service/
```
