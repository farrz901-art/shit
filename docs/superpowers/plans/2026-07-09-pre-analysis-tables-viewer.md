# Pre-analysis 表格 CSV 查看页 实施 Plan (2026-07-09)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 pre-analysis 表格 CSV viewer 子路由 `/admin/pre-analysis/{task_id}/tables`, 解决详情页只能下载 zip 看表格的问题. 重点解决 **表格 CSV 数量级** (可能数千) — 用 2 个新后端端点 (按页分组 + 单页表格数据) + BFF 透传 + 前端懒加载.

**Architecture:**
- **后端 2 新端点**: `GET /api/pre-analysis/tasks/{id}/tables/pages` (返有表格的页号数组) + `GET /api/pre-analysis/tasks/{id}/tables/page/{page}` (返单页所有 CSV 解析后的 JSON)
- **BFF 2 新路由**: 透传后端 2 端点, 读 cookie → 注入 `x-user-token`
- **前端 helper**: `parseTableFilename` (filename→page/table_index) + `getPreAnalysisTablePages` + `getPreAnalysisTablePage`
- **客户端组件**: 真实 PDF 页号 pagination 条 + 按当前页懒加载多表格 DataTable 渲染 (动态列), 支持 URL hash anchor 滚动
- **详情页改**: `VIEWABLE_KINDS` 加入 "table", 表格数 StatCard 可点击, 产物表格 `kind: "table"` 行加 "查看" 按钮 (跳带 `?page=N#table-M`)

**Tech Stack:**
- Python 3.14 + FastAPI + loguru + Pydantic v2
- Next 16 (App Router, RSC async, params 是 Promise) + React 19 + TanStack Query 5 + next-intl 4 + Tailwind v4 + shadcn/ui
- papaparse 5.5.4 (前端 CSV 解析, **本期不再用 — 后端已直接解析后端返 JSON**)
- TypeScript 8 + vitest + jsdom

---

## Global Constraints

来自 spec + 项目规约 (`packages/web/CLAUDE.md` + `packages/service/CLAUDE.md`):

- **i18n**: 用 `t("中文 key")` 中间接 key, zh.json identity (`value = key`), en.json 翻译. 详见 spec §9.
- **路由跳转**: `import { useRouter } from "@/i18n/navigation"`, 禁止 `next/navigation`
- **useSearchParams**: 仍走 `next/navigation` (next-intl 不重新导出, 详见 [packages/web/CLAUDE.md §路由跳转](packages/web/CLAUDE.md))
- **文件命名**: kebab-case
- **表格封装**: `<DataTable<T>>` from `@/components/common/table/data-table`. 动态列时泛型用 `Record<string, string>`
- **常量命名**: `const FLAG_PAGE_SIZE = 5` 不允许魔法数字
- **import 按字母排序** (oxlint)
- **测试运行**: 单文件 `bun run test -- <path>`, 全量只在 phase 结束跑
- **RSC entry**: `params: Promise<{...}>`, 必须 await, 子组件 client 拿的是 sync value
- **GuardPage**: `<GuardPage pageKey="admin">` (不是 `requiredRole="admin"`)
- **BFF 模式**: `app/api/<module>/<path>/route.ts` → 调 `apiProxy()` + `bffProxyResponse()` + `serverAuthHeaders()`, 完整模板见 `app/api/ingest/tasks/[id]/files/[name]/route.ts`
- **后端 router**: `pre_analysis_router` 已存在, 新增端点沿用 `@audited` 装饰器 (只读 GET 可不装饰, 跟现有 `download_pre_analysis_file` 一致)
- **后端测试**: 模式 1 mock (patch `pa_load_task` + `get_object_store`), 跟现有 `test_router.py` 模板一致
- **核心安全约束**: 后端只返回 `output_files_json` 清单里实际存在的 filename, 防 path traversal

---

## File Structure

### 后端新建/改

| 路径 | 责任 |
|---|---|
| `packages/service/src/ingest/pre_analysis/router.py` | [改] 加 2 个 GET 端点: `/tables/pages` + `/tables/page/{page_num}` |
| `packages/service/src/ingest/pre_analysis/table_view.py` | [新] 纯函数: `extract_table_pages(output_files)` + `build_table_page_response(task, page_num)`, 拆业务逻辑便于单测 |
| `packages/service/tests/ingest/pre_analysis/test_table_view.py` | [新] 模式 1 mock — 测 `extract_table_pages` 解析 page numbers, `build_table_page_response` 拼 JSON |
| `packages/service/tests/ingest/pre_analysis/test_router.py` | [改] 加 2 个 describe 覆盖新端点 (鉴权 403, task 不存在 404, page not found 404, 正常 200 + JSON 结构) |

### 前端新建/改

| 路径 | 责任 |
|---|---|
| `packages/web/app/api/pre-analysis/tasks/[id]/tables/pages/route.ts` | [新] BFF pages 代理 |
| `packages/web/app/api/pre-analysis/tasks/[id]/tables/page/[pageNum]/route.ts` | [新] BFF page 代理 |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/page.tsx` | [新] RSC entry (跟 chapters/page.tsx 同 shape) |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.tsx` | [新] 客户端: pages + pagination + 多表 DataTable + hash 滚动 |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.test.tsx` | [新] 客户端单测 |
| `packages/web/lib/api/pre-analysis.ts` | [改] +类型 (`TablePagesResponse` / `TablePageItem` / `TablePageResponse`) + 2 helper (`getPreAnalysisTablePages` / `getPreAnalysisTablePage`) + `parseTableFilename` |
| `packages/web/lib/api/pre-analysis.test.ts` | [改] +describe: `parseTableFilename` 解析 + 2 helper mock fetch |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx` | [改] `VIEWABLE_KINDS` 加入 "table", `viewHrefForKind` 接受 filename, 表格数 StatCard 加 onClick, actions 列 table 行渲染 "查看" 按钮 |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx` | [改] 加 table 行 "查看" 按钮断言 + StatCard 表格数可点击断言 |
| `packages/web/messages/zh.json` | [改] +12 key |
| `packages/web/messages/en.json` | [改] +12 key |

---

# Phase 1: 后端 2 端点 + 业务逻辑拆分

## Task 1.1: 表格视图业务逻辑 (纯函数)

**Files:**
- Create: `packages/service/src/ingest/pre_analysis/table_view.py`
- Test: `packages/service/tests/ingest/pre_analysis/test_table_view.py`

业务逻辑拆到纯函数, 便于单测不连 PG / ObjectStore. router 只做 HTTP 装.

- [ ] **Step 1: 写失败的 `extract_table_pages` 测试**

新建 `packages/service/tests/ingest/pre_analysis/test_table_view.py`:

```python
"""pre_analysis table_view 业务逻辑测试 (模式 1 mock, 0 PG/Redis)."""

from __future__ import annotations

from src.ingest.pre_analysis.table_view import (
    extract_table_pages,
    build_table_page_response,
    parse_table_filename,
)


def test_parse_table_filename_normal() -> None:
    """'tables/page-9-table-1.csv' → page 9, table 1."""
    assert parse_table_filename("tables/page-9-table-1.csv") == (9, 1)


def test_parse_table_filename_multi_digit_page() -> None:
    """页号/表号支持多位数."""
    assert parse_table_filename("tables/page-123-table-45.csv") == (123, 45)


def test_parse_table_filename_invalid_raises() -> None:
    """非法格式抛 ValueError."""
    import pytest
    with pytest.raises(ValueError, match="Invalid table filename"):
        parse_table_filename("chapters.json")
    with pytest.raises(ValueError, match="Invalid table filename"):
        parse_table_filename("tables/page-9.csv")  # 缺 -table-M
    with pytest.raises(ValueError, match="Invalid table filename"):
        parse_table_filename("tables/page-x-table-1.csv")  # 非数字


def test_extract_table_pages_unique_sorted() -> None:
    """从 output_files 提取去重 + 排序 + total."""
    output_files = [
        {"kind": "table", "filename": "tables/page-9-table-1.csv"},
        {"kind": "table", "filename": "tables/page-9-table-2.csv"},  # 同页 2 张表
        {"kind": "table", "filename": "tables/page-3-table-1.csv"},
        {"kind": "table", "filename": "tables/page-21-table-1.csv"},
        {"kind": "chapter_structure", "filename": "chapters.json"},  # 非 table, 跳过
        {"kind": "flagged_paragraphs", "filename": "flagged.csv"},  # 非 table, 跳过
    ]
    pages, total = extract_table_pages(output_files)
    assert pages == [3, 9, 21]  # 去重 + 排序
    assert total == 4  # 4 个 table 文件


def test_extract_table_pages_empty() -> None:
    """空 output_files → ([], 0)."""
    assert extract_table_pages([]) == ([], 0)
    assert extract_table_pages([{"kind": "chapter_structure", "filename": "x"}]) == ([], 0)


def test_extract_table_pages_skips_invalid_filenames() -> None:
    """非法 filename 跳过 (e.g. runner 写错格式)."""
    output_files = [
        {"kind": "table", "filename": "tables/page-9-table-1.csv"},
        {"kind": "table", "filename": "bad.csv"},  # 非法, 跳过
    ]
    pages, total = extract_table_pages(output_files)
    assert pages == [9]
    assert total == 1
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/test_table_view.py -v
```

Expected: `ImportError: cannot import name 'parse_table_filename' from 'src.ingest.pre_analysis.table_view'` (模块不存在)

- [ ] **Step 3: 实现 `table_view.py`**

新建 `packages/service/src/ingest/pre_analysis/table_view.py`:

```python
"""pre_analysis 表格视图业务逻辑 (2026-07-09 新增).

提供 2 个纯函数:
- `parse_table_filename(filename)` → `(page_num, table_index)` 元组
- `extract_table_pages(output_files)` → `(pages: list[int], total: int)`

跟 HTTP 解耦, router 直接 import 调用, 单测不依赖 FastAPI / PG / ObjectStore.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

_TABLE_FILENAME_RE = re.compile(r"^tables/page-(\d+)-table-(\d+)\.csv$")


def parse_table_filename(filename: str) -> tuple[int, int]:
    """从表格 CSV 文件名提取 (页号, 表索引).

    Args:
        filename: 产物文件名 (e.g. "tables/page-9-table-1.csv")

    Returns:
        (page_num, table_index) 元组.

    Raises:
        ValueError: 文件名不符合 `tables/page-{N}-table-{M}.csv` 格式.
    """
    match = _TABLE_FILENAME_RE.match(filename)
    if not match:
        raise ValueError(
            f"Invalid table filename: {filename!r} "
            f"(expected 'tables/page-{{N}}-table-{{M}}.csv')"
        )
    return int(match.group(1)), int(match.group(2))


def extract_table_pages(output_files: list[dict[str, Any]]) -> tuple[list[int], int]:
    """从 output_files 提取去重 + 排序后的有表格页号列表.

    只看 `kind == "table"` 条目. 非法 filename 静默跳过 (runner 异常产物
    不应阻断整个 pages 接口).

    Args:
        output_files: PreAnalysisTask.output_files 列表.

    Returns:
        (pages, total): pages 是排序去重的页号数组; total 是表格文件总数
            (含同页多张表).
    """
    pages: set[int] = set()
    total = 0
    for f in output_files:
        if f.get("kind") != "table":
            continue
        filename = f.get("filename", "")
        try:
            page_num, _ = parse_table_filename(filename)
        except ValueError:
            continue
        pages.add(page_num)
        total += 1
    return sorted(pages), total


def build_table_page_response(
    task: dict[str, Any],
    page_num: int,
    csv_contents: dict[str, bytes],
) -> dict[str, Any]:
    """构造指定页的表格数据响应 JSON.

    Args:
        task: PreAnalysisTask dict (含 output_files).
        page_num: PDF 页号.
        csv_contents: filename → CSV 字节内容 dict (调用方负责从 ObjectStore 读).

    Returns:
        {"page": int, "tables": [TableItem, ...]} 格式 dict.

    Raises:
        KeyError: 该页没有任何表格条目.
    """
    tables_for_page = []
    for f in task["output_files"]:
        if f.get("kind") != "table":
            continue
        try:
            f_page, f_idx = parse_table_filename(f["filename"])
        except ValueError:
            continue
        if f_page != page_num:
            continue
        csv_bytes = csv_contents[f["filename"]]
        # python stdlib csv.DictReader — 不引第三方
        text = csv_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        rows = [dict(r) for r in reader]  # materialize (reader 是一次性的)
        columns = reader.fieldnames or []
        tables_for_page.append({
            "table_index": f_idx,
            "filename": f["filename"],
            "size_bytes": f.get("size_bytes", 0),
            "columns": list(columns),
            "rows": rows,
        })

    if not tables_for_page:
        raise KeyError(f"No tables found for page {page_num}")

    # 按 table_index 升序
    tables_for_page.sort(key=lambda t: t["table_index"])
    return {"page": page_num, "tables": tables_for_page}
```

- [ ] **Step 4: 加 `build_table_page_response` 测试**

追加到 `test_table_view.py`:

```python
def test_build_table_page_response_filters_and_parses() -> None:
    """build_table_page_response: 过滤该页 CSV + csv.DictReader 解析."""
    task = {
        "output_files": [
            {
                "kind": "table",
                "filename": "tables/page-9-table-1.csv",
                "uri": "s3://x/tables/page-9-table-1.csv",
                "size_bytes": 100,
            },
            {
                "kind": "table",
                "filename": "tables/page-9-table-2.csv",
                "uri": "s3://x/tables/page-9-table-2.csv",
                "size_bytes": 200,
            },
            {
                "kind": "table",
                "filename": "tables/page-3-table-1.csv",  # 其它页, 跳过
                "uri": "s3://x/tables/page-3-table-1.csv",
                "size_bytes": 50,
            },
            {
                "kind": "chapter_structure",
                "filename": "chapters.json",  # 非 table, 跳过
                "uri": "s3://x/chapters.json",
                "size_bytes": 1000,
            },
        ],
    }
    csv_1 = b"col_a,col_b\nv1,v2\nv3,v4\n"
    csv_2 = b"col_x\nfoo\nbar\n"
    csv_contents = {
        "tables/page-9-table-1.csv": csv_1,
        "tables/page-9-table-2.csv": csv_2,
    }

    resp = build_table_page_response(task, 9, csv_contents)

    assert resp["page"] == 9
    assert len(resp["tables"]) == 2
    # 按 table_index 升序
    assert resp["tables"][0]["table_index"] == 1
    assert resp["tables"][0]["filename"] == "tables/page-9-table-1.csv"
    assert resp["tables"][0]["columns"] == ["col_a", "col_b"]
    assert resp["tables"][0]["rows"] == [
        {"col_a": "v1", "col_b": "v2"},
        {"col_a": "v3", "col_b": "v4"},
    ]
    assert resp["tables"][1]["table_index"] == 2
    assert resp["tables"][1]["rows"] == [{"col_x": "foo"}, {"col_x": "bar"}]


def test_build_table_page_response_no_tables_raises_keyerror() -> None:
    """指定页没表格 → KeyError."""
    task = {"output_files": [{"kind": "table", "filename": "tables/page-3-table-1.csv"}]}
    import pytest
    with pytest.raises(KeyError, match="No tables found for page 99"):
        build_table_page_response(task, 99, {})
```

- [ ] **Step 5: 跑测试确认全绿**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/test_table_view.py -v
```

Expected: 9 tests pass.

- [ ] **Step 6: Commit**

```bash
cd packages/service && git add src/ingest/pre_analysis/table_view.py tests/ingest/pre_analysis/test_table_view.py
git commit -m "feat(pre-analysis): 表格视图纯函数 (parse_table_filename + extract_table_pages + build_table_page_response)"
```

---

## Task 1.2: 后端 GET `/tables/pages` 端点

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/router.py` (在 `download_pre_analysis_file` 之后追加)
- Modify: `packages/service/tests/ingest/pre_analysis/test_router.py`

- [ ] **Step 1: 写失败的 router 测试**

追加到 `test_router.py` (复用现有 `client` fixture + `_make_task` + `_patch_audit_persist`):

```python
def test_list_table_pages_success(client: tuple[TestClient, Any]) -> None:
    """正常: 返回 {pages: [...], total: N}."""
    from src.ingest.pre_analysis.router import pa_load_task

    cli, _ = client
    fake_task = _make_task(
        output_files=[
            {"kind": "table", "filename": "tables/page-3-table-1.csv",
             "uri": "s3://x", "size_bytes": 50},
            {"kind": "table", "filename": "tables/page-9-table-1.csv",
             "uri": "s3://x", "size_bytes": 100},
            {"kind": "table", "filename": "tables/page-9-table-2.csv",
             "uri": "s3://x", "size_bytes": 200},
            {"kind": "table", "filename": "tables/page-21-table-1.csv",
             "uri": "s3://x", "size_bytes": 150},
            {"kind": "chapter_structure", "filename": "chapters.json",
             "uri": "s3://x", "size_bytes": 1000},
        ],
    )
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/pages")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"pages": [3, 9, 21], "total": 4}


def test_list_table_pages_task_not_found(client: tuple[TestClient, Any]) -> None:
    """task 不存在 → 404."""
    cli, _ = client
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=None):
        resp = cli.get("/api/pre-analysis/tasks/missing/tables/pages")
    assert resp.status_code == 404


def test_list_table_pages_non_super_admin_403(client: tuple[TestClient, Any]) -> None:
    """非 super_admin → 403."""
    from src.middleware.auth import resolve_user

    app = client[1]
    app.dependency_overrides[resolve_user] = lambda: _make_user(role="user")
    cli = client[0]
    resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/pages")
    assert resp.status_code == 403


def test_list_table_pages_empty(client: tuple[TestClient, Any]) -> None:
    """无表格 → {pages: [], total: 0}."""
    from src.ingest.pre_analysis.router import pa_load_task

    cli, _ = client
    fake_task = _make_task(
        output_files=[{"kind": "chapter_structure", "filename": "chapters.json",
                       "uri": "s3://x", "size_bytes": 1000}],
    )
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/pages")
    assert resp.status_code == 200
    assert resp.json() == {"pages": [], "total": 0}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/test_router.py -v -k "list_table_pages"
```

Expected: 404 (路由不存在).

- [ ] **Step 3: 实现 `/tables/pages` 端点**

修改 `router.py`, 先加 import:

```python
from .table_view import extract_table_pages
```

在文件末尾 (`download_pre_analysis_file` 之后) 追加:

```python
@pre_analysis_router.get(
    "/tasks/{task_id}/tables/pages",
    summary="列出有表格的 PDF 页号 (用于前端 pagination)",
    description=(
        "## 用途\n\n"
        "返回当前任务中所有含表格的 PDF 页号 (升序去重) + 表格文件总数.\n"
        "前端 tables viewer 用此构建 pagination 条.\n\n"
        "## 性能\n\n"
        "只读 output_files_json DB 字段, 不读 ObjectStore, 几十毫秒级.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫."
    ),
    response_model=None,
    responses={
        200: {"description": "{pages: number[], total: number}"},
        401: {"description": "未登录"},
        403: {"description": "非 super_admin"},
        404: {"description": "任务不存在"},
    },
)
async def list_table_pages(
    request: Request,
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """(2026-07-09 tables viewer) 列出有表格的 PDF 页号.

    Args:
        request: FastAPI Request (audit 上下文).
        task_id: 预分析任务 ID.
        user: super_admin (Depends).

    Returns:
        {"pages": [3, 9, 12, ...], "total": 12}.
    """
    _check_token(user)  # 一致性: 现有端点都过 token check, 即使 require_super_admin 已挡
    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    pages, total = extract_table_pages(task["output_files"])
    return {"pages": pages, "total": total}
```

注意: 现有端点用 `_check_token(user)` 做 token 一致性 (尽管 `require_super_admin` 已守).
不引入新模式, 沿用相同调用.

- [ ] **Step 4: 跑测试确认绿**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/test_router.py -v -k "list_table_pages"
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
cd packages/service && git add src/ingest/pre_analysis/router.py tests/ingest/pre_analysis/test_router.py
git commit -m "feat(pre-analysis): GET /tables/pages 端点 + 测试"
```

---

## Task 1.3: 后端 GET `/tables/page/{page_num}` 端点

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/router.py`
- Modify: `packages/service/tests/ingest/pre_analysis/test_router.py`

- [ ] **Step 1: 写失败的 router 测试**

追加到 `test_router.py`:

```python
def test_get_table_page_success(client: tuple[TestClient, Any]) -> None:
    """正常: 返回 {page, tables} 含 CSV 解析 JSON."""
    from src.ingest.pre_analysis.router import pa_load_task

    cli, _ = client
    fake_task = _make_task(
        output_files=[
            {"kind": "table", "filename": "tables/page-9-table-1.csv",
             "uri": "s3://x/tables/page-9-table-1.csv", "size_bytes": 50},
            {"kind": "table", "filename": "tables/page-9-table-2.csv",
             "uri": "s3://x/tables/page-9-table-2.csv", "size_bytes": 100},
            {"kind": "table", "filename": "tables/page-3-table-1.csv",  # 其它页
             "uri": "s3://x/tables/page-3-table-1.csv", "size_bytes": 80},
        ],
    )
    csv_1 = b"col_a,col_b\nv1,v2\nv3,v4\n"
    csv_2 = b"col_x\nfoo\nbar\n"

    fake_store = MagicMock(get_bytes=MagicMock(side_effect=lambda uri: {
        "s3://x/tables/page-9-table-1.csv": csv_1,
        "s3://x/tables/page-9-table-2.csv": csv_2,
    }.get(uri, b"")))

    with (
        patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task),
        patch("src.ingest.pre_analysis.router.get_object_store", return_value=fake_store),
    ):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/page/9")

    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 9
    assert len(body["tables"]) == 2
    # 按 table_index 升序
    assert body["tables"][0]["table_index"] == 1
    assert body["tables"][0]["filename"] == "tables/page-9-table-1.csv"
    assert body["tables"][0]["columns"] == ["col_a", "col_b"]
    assert body["tables"][0]["rows"] == [
        {"col_a": "v1", "col_b": "v2"},
        {"col_a": "v3", "col_b": "v4"},
    ]
    assert body["tables"][0]["size_bytes"] == 50


def test_get_table_page_not_found(client: tuple[TestClient, Any]) -> None:
    """指定页没表格 → 404 'page not found'."""
    from src.ingest.pre_analysis.router import pa_load_task

    cli, _ = client
    fake_task = _make_task(
        output_files=[{"kind": "table", "filename": "tables/page-3-table-1.csv",
                       "uri": "s3://x", "size_bytes": 50}],
    )
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=fake_task):
        resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/page/999")
    assert resp.status_code == 404
    assert "page" in resp.json()["detail"].lower() or "999" in resp.json()["detail"]


def test_get_table_page_task_not_found(client: tuple[TestClient, Any]) -> None:
    """task 不存在 → 404."""
    cli, _ = client
    with patch("src.ingest.pre_analysis.router.pa_load_task", return_value=None):
        resp = cli.get("/api/pre-analysis/tasks/missing/tables/page/9")
    assert resp.status_code == 404


def test_get_table_page_non_super_admin_403(client: tuple[TestClient, Any]) -> None:
    """非 super_admin → 403."""
    from src.middleware.auth import resolve_user

    app = client[1]
    app.dependency_overrides[resolve_user] = lambda: _make_user(role="user")
    cli = client[0]
    resp = cli.get("/api/pre-analysis/tasks/pa-abc/tables/page/9")
    assert resp.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/test_router.py -v -k "get_table_page"
```

Expected: 404 (路由不存在).

- [ ] **Step 3: 实现 `/tables/page/{page_num}` 端点**

修改 `router.py` (继续在 `list_table_pages` 之后追加), import 加 `build_table_page_response`:

```python
from .table_view import build_table_page_response, extract_table_pages
```

追加:

```python
@pre_analysis_router.get(
    "/tasks/{task_id}/tables/page/{page_num}",
    summary="获取指定 PDF 页的表格数据 (含 CSV → JSON 解析)",
    description=(
        "## 用途\n\n"
        "返回指定页所有表格的解析数据 (columns + rows JSON), 避免前端解析 CSV.\n"
        "前端 tables viewer 按 ?page=N 查询, 单页通常 1-3 张表.\n\n"
        "## 性能\n\n"
        "读取该页 N 个 CSV 文件从 ObjectStore + csv.DictReader 解析, 一般 < 100ms.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫."
    ),
    response_model=None,
    responses={
        200: {"description": "{page: number, tables: TableItem[]}"},
        401: {"description": "未登录"},
        403: {"description": "非 super_admin"},
        404: {"description": "任务不存在 或 该页无表格"},
    },
)
async def get_table_page(
    request: Request,
    task_id: str,
    page_num: int,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """(2026-07-09 tables viewer) 查指定页所有表格的解析数据.

    Args:
        request: FastAPI Request.
        task_id: 预分析任务 ID.
        page_num: PDF 页号 (1-based).
        user: super_admin (Depends).

    Returns:
        {"page": int, "tables": [{"table_index", "filename", "size_bytes", "columns", "rows"}, ...]}.

    Raises:
        HTTPException 404: 任务不存在 或 该页无表格.
    """
    _check_token(user)
    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")

    # 收集该页 filename → uri
    page_files: dict[str, str] = {}
    for f in task["output_files"]:
        if f.get("kind") != "table":
            continue
        try:
            from .table_view import parse_table_filename
            f_page, _ = parse_table_filename(f["filename"])
        except ValueError:
            continue
        if f_page == page_num:
            page_files[f["filename"]] = f["uri"]

    if not page_files:
        raise HTTPException(404, detail=f"页 {page_num} 无表格")

    # 从 ObjectStore 读所有该页 CSV
    store = get_object_store()
    csv_contents: dict[str, bytes] = {}
    for filename, uri in page_files.items():
        try:
            csv_contents[filename] = store.get_bytes(uri)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(404, detail=f"产物文件 {filename} 读取失败: {e}") from e

    try:
        return build_table_page_response(task, page_num, csv_contents)
    except KeyError as e:
        raise HTTPException(404, detail=str(e)) from e
```

- [ ] **Step 4: 跑测试确认绿**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/test_router.py -v -k "get_table_page"
```

Expected: 4 tests pass.

- [ ] **Step 5: 跑整个 router 测试文件确认无回归**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/test_router.py -v
```

Expected: 全部 pass.

- [ ] **Step 6: Commit**

```bash
cd packages/service && git add src/ingest/pre_analysis/router.py tests/ingest/pre_analysis/test_router.py
git commit -m "feat(pre-analysis): GET /tables/page/{page_num} 端点 + 测试"
```

---

# Phase 2: BFF 代理路由 + 前端 helper + types

## Task 2.1: BFF `/api/pre-analysis/tasks/[id]/tables/pages` 路由

**Files:**
- Create: `packages/web/app/api/pre-analysis/tasks/[id]/tables/pages/route.ts`

- [ ] **Step 1: 创建 BFF route 文件**

新建 `packages/web/app/api/pre-analysis/tasks/[id]/tables/pages/route.ts`:

```ts
// Pre-analysis 表格页列表 BFF: GET /api/pre-analysis/tasks/{id}/tables/pages
// 透传后端: GET /api/pre-analysis/tasks/{id}/tables/pages
// 跟 ingest/tasks/[id]/files/[name]/route.ts 同 pattern: apiProxy + serverAuthHeaders + bffProxyResponse.
import { type NextRequest } from "next/server";

import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** Next.js 路由配置: 禁用静态优化, 强制动态渲染
 * @client-bff */
export const dynamic = "force-dynamic";

/** Pre-analysis 表格页列表 BFF (2026-07-09 tables viewer)
 * @param _req - 请求对象 (未使用)
 * @param ctx - 路由上下文, 含任务 id
 * @returns Response
 * @client-bff */
export const GET = async (
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
) => {
  const { id } = await ctx.params;
  const resp = await apiProxy(
    `/api/pre-analysis/tasks/${encodeURIComponent(id)}/tables/pages`,
    { cache: "no-store", headers: await serverAuthHeaders() },
  );
  return bffProxyResponse(resp);
};
```

- [ ] **Step 2: TypeScript 类型检查**

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
cd packages/web && git add app/api/pre-analysis/
git commit -m "feat(web): pre-analysis tables pages BFF route"
```

---

## Task 2.2: BFF `/api/pre-analysis/tasks/[id]/tables/page/[pageNum]` 路由

**Files:**
- Create: `packages/web/app/api/pre-analysis/tasks/[id]/tables/page/[pageNum]/route.ts`

- [ ] **Step 1: 创建 BFF route 文件**

新建 `packages/web/app/api/pre-analysis/tasks/[id]/tables/page/[pageNum]/route.ts`:

```ts
// Pre-analysis 指定页表格数据 BFF: GET /api/pre-analysis/tasks/{id}/tables/page/{pageNum}
// 透传后端: GET /api/pre-analysis/tasks/{id}/tables/page/{page}
import { type NextRequest } from "next/server";

import { apiProxy, bffProxyResponse } from "@/lib/api/config";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** Next.js 路由配置: 禁用静态优化, 强制动态渲染
 * @client-bff */
export const dynamic = "force-dynamic";

/** Pre-analysis 单页表格数据 BFF (2026-07-09 tables viewer)
 * @param _req - 请求对象 (未使用)
 * @param ctx - 路由上下文, 含任务 id 和页号
 * @returns Response
 * @client-bff */
export const GET = async (
  _req: NextRequest,
  ctx: { params: Promise<{ id: string; pageNum: string }> },
) => {
  const { id, pageNum } = await ctx.params;
  const resp = await apiProxy(
    `/api/pre-analysis/tasks/${encodeURIComponent(id)}/tables/page/${encodeURIComponent(pageNum)}`,
    { cache: "no-store", headers: await serverAuthHeaders() },
  );
  return bffProxyResponse(resp);
};
```

- [ ] **Step 2: TypeScript 类型检查**

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
cd packages/web && git add app/api/pre-analysis/
git commit -m "feat(web): pre-analysis table page BFF route"
```

---

## Task 2.3: 前端 types + helpers + 单测

**Files:**
- Modify: `packages/web/lib/api/pre-analysis.ts` (在 file 末尾, `getPreAnalysisFlaggedParagraphs` 后追加)
- Modify: `packages/web/lib/api/pre-analysis.test.ts`

- [ ] **Step 1: 写失败的 helper 单测**

追加到 `packages/web/lib/api/pre-analysis.test.ts` (在 `getPreAnalysisFlaggedParagraphs` describe 之后):

```ts
import {
  parseTableFilename,
  getPreAnalysisTablePages,
  getPreAnalysisTablePage,
  type TablePagesResponse,
  type TablePageResponse,
} from "./pre-analysis";

describe("parseTableFilename", () => {
  it("extract page 9 table 1", () => {
    expect(parseTableFilename("tables/page-9-table-1.csv")).toEqual({
      pageNumber: 9,
      tableIndex: 1,
    });
  });

  it("support multi-digit page and table index", () => {
    expect(parseTableFilename("tables/page-123-table-45.csv")).toEqual({
      pageNumber: 123,
      tableIndex: 45,
    });
  });

  it("throw on invalid format", () => {
    expect(() => parseTableFilename("chapters.json")).toThrow(/Invalid table filename/);
    expect(() => parseTableFilename("tables/page-9.csv")).toThrow(/Invalid table filename/);
    expect(() => parseTableFilename("tables/page-x-table-1.csv")).toThrow(/Invalid table filename/);
  });
});

describe("getPreAnalysisTablePages", () => {
  it("GET pages endpoint → return {pages, total}", async () => {
    const mock: TablePagesResponse = { pages: [3, 9, 12, 21], total: 5 };
    installMockFetch(Response.json(mock, { status: 200 }));

    const result = await getPreAnalysisTablePages("pa-1");
    expect(result).toEqual({ pages: [3, 9, 12, 21], total: 5 });
  });

  it("empty pages list", async () => {
    installMockFetch(Response.json({ pages: [], total: 0 }, { status: 200 }));
    const result = await getPreAnalysisTablePages("pa-1");
    expect(result).toEqual({ pages: [], total: 0 });
  });

  it("404 throws", async () => {
    installMockFetch(Response.json({ detail: "任务不存在" }, { status: 404 }));
    await expect(getPreAnalysisTablePages("missing")).rejects.toThrow(/任务不存在/);
  });
});

describe("getPreAnalysisTablePage", () => {
  it("GET page endpoint → return {page, tables}", async () => {
    const mock: TablePageResponse = {
      page: 9,
      tables: [
        {
          table_index: 1,
          filename: "tables/page-9-table-1.csv",
          size_bytes: 100,
          columns: ["col_a", "col_b"],
          rows: [{ col_a: "v1", col_b: "v2" }],
        },
      ],
    };
    installMockFetch(Response.json(mock, { status: 200 }));

    const result = await getPreAnalysisTablePage("pa-1", 9);
    expect(result.page).toBe(9);
    expect(result.tables).toHaveLength(1);
    expect(result.tables[0]?.filename).toBe("tables/page-9-table-1.csv");
    expect(result.tables[0]?.rows[0]).toEqual({ col_a: "v1", col_b: "v2" });
  });

  it("page not found → 404 throws", async () => {
    installMockFetch(Response.json({ detail: "页 999 无表格" }, { status: 404 }));
    await expect(getPreAnalysisTablePage("pa-1", 999)).rejects.toThrow(/页 999 无表格/);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/web && bun run test -- lib/api/pre-analysis.test.ts
```

Expected: ImportError or similar.

- [ ] **Step 3: 实现 types + helpers**

追加到 `packages/web/lib/api/pre-analysis.ts` 末尾 (在 `getPreAnalysisFlaggedParagraphs` 之后):

```ts
// ===== (2026-07-09) 表格 viewer types + helpers =====

/**
 * 表格页列表响应.
 * @property pages 有表格的 PDF 页号数组 (升序)
 * @property total 表格文件总数 (含同页多张)
 */
export interface TablePagesResponse {
  pages: number[];
  total: number;
}

/**
 * 单张表格的解析数据 (来自后端 csv.DictReader).
 * @property table_index 该页内的表索引 (从 1 开始)
 * @property filename 产物文件名 (e.g. "tables/page-9-table-1.csv")
 * @property size_bytes CSV 字节数
 * @property columns 表头列名 (从 CSV 第一行读)
 * @property rows 数据行 (Record<column_name, value>)
 */
export interface TablePageItem {
  table_index: number;
  filename: string;
  size_bytes: number;
  columns: string[];
  rows: Record<string, string>[];
}

/**
 * 指定页的表格数据响应.
 * @property page PDF 页号
 * @property tables 该页所有表格 (按 table_index 升序)
 */
export interface TablePageResponse {
  page: number;
  tables: TablePageItem[];
}

/** 正则匹配 tables/page-{N}-table-{M}.csv 文件名. */
const TABLE_FILENAME_PATTERN = /^tables\/page-(\d+)-table-(\d+)\.csv$/;

/**
 * 从表格 CSV 文件名提取页号和表索引.
 * 跟后端 `parse_table_filename` 严格对齐 (router.py table_view.py).
 *
 * @param filename 产物文件名 (e.g. "tables/page-9-table-1.csv")
 * @returns `{ pageNumber, tableIndex }`
 * @throws 文件名不符格式时抛错
 * @shared
 */
export const parseTableFilename = (filename: string): { pageNumber: number; tableIndex: number } => {
  const match = TABLE_FILENAME_PATTERN.exec(filename);
  if (!match) {
    throw new Error(`Invalid table filename: ${filename} (expected tables/page-{N}-table-{M}.csv)`);
  }
  return { pageNumber: Number(match[1]), tableIndex: Number(match[2]) };
};

/**
 * 查询任务的有表格页号列表 (用于前端 pagination).
 * BFF: GET /api/pre-analysis/tasks/{taskId}/tables/pages.
 *
 * @param taskId 预分析任务 ID
 * @returns `{ pages, total }`
 * @throws 4xx/5xx 时 handleError 抛
 * @client-bff
 */
export const getPreAnalysisTablePages = async (taskId: string): Promise<TablePagesResponse> => {
  const resp = await apiFetch<TablePagesResponse>(
    `/api/pre-analysis/tasks/${encodeURIComponent(taskId)}/tables/pages`,
    { credentials: "include" },
  );
  return resp;
};

/**
 * 查询指定 PDF 页的表格数据 (含 columns + rows JSON, 后端已 parse).
 * BFF: GET /api/pre-analysis/tasks/{taskId}/tables/page/{pageNum}.
 *
 * @param taskId 预分析任务 ID
 * @param pageNum PDF 页号 (1-based)
 * @returns `{ page, tables: TablePageItem[] }`
 * @throws 4xx/5xx 时 handleError 抛 (404 表示该页无表格)
 * @client-bff
 */
export const getPreAnalysisTablePage = async (
  taskId: string,
  pageNum: number,
): Promise<TablePageResponse> => {
  const resp = await apiFetch<TablePageResponse>(
    `/api/pre-analysis/tasks/${encodeURIComponent(taskId)}/tables/page/${pageNum}`,
    { credentials: "include" },
  );
  return resp;
};
```

- [ ] **Step 4: 跑测试确认绿**

```bash
cd packages/web && bun run test -- lib/api/pre-analysis.test.ts
```

Expected: 全部 pass (含新 describe).

- [ ] **Step 5: lint + typecheck**

```bash
cd packages/web && bun run lint:fix && bun run typecheck
```

Expected: 0 error.

- [ ] **Step 6: Commit**

```bash
cd packages/web && git add lib/api/pre-analysis.ts lib/api/pre-analysis.test.ts
git commit -m "feat(web): pre-analysis table types + parseTableFilename + 2 helpers + 单测"
```

---

# Phase 3: 客户端组件 — Tables Viewer

## Task 3.1: 客户端组件 `admin-pre-analysis-tables-client.tsx`

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.tsx`
- Test: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.test.tsx`

- [ ] **Step 1: 写失败的 client 测试**

新建 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.test.tsx`:

```tsx
// 表格 viewer 客户端组件测试 (mode 1 mock fetch)

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import {
  type TablePageItem,
  type TablePageResponse,
  type TablePagesResponse,
} from "@/lib/api/pre-analysis";
import { AdminPreAnalysisTablesClient } from "./admin-pre-analysis-tables-client";

vi.mock("server-only", () => ({}));

// react-router / next-intl navigation mock
const mockPush = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// useSearchParams mock
const mockSearchParams = new Map<string, string>();
vi.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: (key: string) => mockSearchParams.get(key) ?? null,
  }),
}));

afterEach(() => {
  vi.restoreAllMocks();
  mockSearchParams.clear();
  mockPush.mockClear();
});

const FIXTURE_PAGES: TablePagesResponse = {
  pages: [3, 9, 12, 15, 21, 31, 39, 45],
  total: 12,
};

const FIXTURE_PAGE_DATA: TablePageResponse = {
  page: 9,
  tables: [
    {
      table_index: 1,
      filename: "tables/page-9-table-1.csv",
      size_bytes: 50,
      columns: ["col_a", "col_b"],
      rows: [
        { col_a: "v1", col_b: "v2" },
        { col_a: "v3", col_b: "v4" },
      ],
    },
    {
      table_index: 2,
      filename: "tables/page-9-table-2.csv",
      size_bytes: 30,
      columns: ["col_x"],
      rows: [{ col_x: "foo" }, { col_x: "bar" }],
    },
  ] satisfies TablePageItem[],
};

const renderWithProviders = (ui: React.ReactElement, initialSearchParams: Record<string, string> = {}) => {
  Object.entries(initialSearchParams).forEach(([k, v]) => mockSearchParams.set(k, v));
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">{ui}</IntlWrapper>
    </QueryClientProvider>,
  );
};

describe("AdminPreAnalysisTablesClient", () => {
  it("renders pagination buttons for all pages", async () => {
    globalThis.fetch = vi.fn(async () => Response.json(FIXTURE_PAGES, { status: 200 })) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, { page: "9" });

    await waitFor(() => {
      // 8 个页号按钮 (P3, P9, P12, P15, P21, P31, P39, P45)
      const pageButtons = screen.getAllByTestId(/^page-button-/);
      expect(pageButtons).toHaveLength(8);
    });
  });

  it("当前页高亮", async () => {
    globalThis.fetch = vi.fn(async () => Response.json(FIXTURE_PAGES, { status: 200 })) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, { page: "9" });

    await waitFor(() => {
      const current = screen.getByTestId("page-button-9");
      expect(current.getAttribute("aria-current")).toBe("page");
    });
  });

  it("click P12 → router.push", async () => {
    const fetchMock = vi.fn(async () => Response.json(FIXTURE_PAGES, { status: 200 })) as unknown as typeof fetch;
    globalThis.fetch = fetchMock;
    const user = userEvent.setup();
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, { page: "9" });

    await waitFor(() => screen.getByTestId("page-button-12"));
    await user.click(screen.getByTestId("page-button-12"));

    expect(mockPush).toHaveBeenCalledWith("/admin/pre-analysis/pa-1/tables?page=12");
  });

  it("mock page data 2 tables → 2 DataTable 渲染", async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn(async () => {
      callCount += 1;
      if (callCount === 1) return Response.json(FIXTURE_PAGES, { status: 200 });
      return Response.json(FIXTURE_PAGE_DATA, { status: 200 });
    }) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, { page: "9" });

    await waitFor(() => {
      // 表格 1 的列名 + 表格 2 的列名
      expect(screen.getAllByText("col_a").length).toBeGreaterThan(0);
      expect(screen.getAllByText("col_x").length).toBeGreaterThan(0);
    });

    // anchor id 检查
    expect(document.getElementById("table-1")).toBeTruthy();
    expect(document.getElementById("table-2")).toBeTruthy();
  });

  it("empty pages → <DataEmpty>", async () => {
    globalThis.fetch = vi.fn(async () => Response.json({ pages: [], total: 0 }, { status: 200 })) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("无表格数据")).toBeTruthy();
    });
  });

  it("无效 page param (999) 自动 fallback 到 pages[0] (3)", async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn(async () => {
      callCount += 1;
      if (callCount === 1) return Response.json(FIXTURE_PAGES, { status: 200 });
      // 第 2 次调用是 page=3 (fallback)
      return Response.json({ ...FIXTURE_PAGE_DATA, page: 3 }, { status: 200 });
    }) as unknown as typeof fetch;
    renderWithProviders(<AdminPreAnalysisTablesClient params={{ task_id: "pa-1" }} />, { page: "999" });

    await waitFor(() => {
      const current = screen.getByTestId("page-button-3");
      expect(current.getAttribute("aria-current")).toBe("page");
    });
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/web && bun run test -- app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.test.tsx
```

Expected: 找不到模块错误.

- [ ] **Step 3: 实现客户端组件**

新建 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.tsx`:

```tsx
"use client";
// admin/pre-analysis 表格 viewer 客户端组件 (2026-07-09)
// 调 getPreAnalysisTablePages 拉页号数组, 调 getPreAnalysisTablePage 拉当前页所有表格数据.
// pagination 显示真实 PDF 页号 (P3, P9, P12...). 当前页多个表格纵向堆叠, 动态列 DataTable 渲染.
// 复用 <DataTable<T>> + <BackLink> + <PageHero> + <ErrorBanner> + <DataEmpty>.
// 跟 chapters/flagged viewer 模式一致, 差异在 URL searchParams + lazy per-page fetch + 动态列.

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo } from "react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { useRouter } from "@/i18n/navigation";
import {
  getPreAnalysisTablePage,
  getPreAnalysisTablePages,
  type TablePageItem,
  type TablePageResponse,
  type TablePagesResponse,
} from "@/lib/api/pre-analysis";

/** pagination 中间省略号时的显示位置枚举 */
const ELLIPSIS_LEFT_PAGE_COUNT = 3;
const ELLIPSIS_RIGHT_PAGE_COUNT = 2;
const ELLIPSIS_SIBLING_COUNT = 1;
/** tables 区域滚动到 anchor 时的 behavior 选项 */
const SCROLL_BEHAVIOR: ScrollBehavior = "smooth";
/** rowKey 拼接前缀 (table_index-行索引) */
const ROW_KEY_SEP = "-";
/** 表格 DataTable 默认行高 (跟其他 viewer 一致) */
const TABLE_MAX_HEIGHT_PX = 400;
/** DataTable 行 key 兜底字符串 (行索引序列化成字符串) */
const STRING_INDEX_BASE = 10;

/** 页面组件路由参数 */
interface PageProps {
  /** 路由参数 */
  params: { task_id: string };
}

/**
 * 从所有页列表 + 当前索引算可见页号按钮 + ellipsis.
 * 模仿 shadcn 标准 pagination 风格: 首 3 + 当前 ±1 + 末 2, 中间 ... 收起.
 */
const buildVisiblePages = (
  allPages: number[],
  currentIdx: number,
): Array<{ kind: "page"; page: number } | { kind: "ellipsis"; key: string }> => {
  if (allPages.length <= ELLIPSIS_LEFT_PAGE_COUNT + ELLIPSIS_RIGHT_PAGE_COUNT + 2 * ELLIPSIS_SIBLING_COUNT + 1) {
    // 总数较少, 全显示
    return allPages.map((p) => ({ kind: "page" as const, page: p }));
  }

  const leftEnd = ELLIPSIS_LEFT_PAGE_COUNT;
  const rightStart = allPages.length - ELLIPSIS_RIGHT_PAGE_COUNT;
  const siblingsStart = Math.max(leftEnd + 1, currentIdx - ELLIPSIS_SIBLING_COUNT);
  const siblingsEnd = Math.min(rightStart - 1, currentIdx + ELLIPSIS_SIBLING_COUNT);

  const visible: Array<{ kind: "page"; page: number } | { kind: "ellipsis"; key: string }> = [];

  // 左半 (首 3 页)
  for (let idx = 0; idx < leftEnd; idx += 1) {
    const p = allPages[idx];
    if (p !== undefined) {
      visible.push({ kind: "page", page: p });
    }
  }

  // 左 ellipsis (如果 siblingsStart > leftEnd)
  if (siblingsStart > leftEnd + 1) {
    visible.push({ kind: "ellipsis", key: "left" });
  }

  // 中间 siblings (当前 ±1)
  for (let idx = siblingsStart; idx <= siblingsEnd; idx += 1) {
    const p = allPages[idx];
    if (p !== undefined) {
      visible.push({ kind: "page", page: p });
    }
  }

  // 右 ellipsis
  if (siblingsEnd < rightStart - 1) {
    visible.push({ kind: "ellipsis", key: "right" });
  }

  // 右半 (末 2 页)
  for (let idx = rightStart; idx < allPages.length; idx += 1) {
    const p = allPages[idx];
    if (p !== undefined) {
      visible.push({ kind: "page", page: p });
    }
  }

  return visible;
};

/**
 * 从 CSV 列名构造 DataTable ColumnDef (动态列场景).
 */
const buildDynamicColumns = (columns: string[]): ColumnDef<Record<string, string>>[] =>
  columns.map((col) => ({
    accessorKey: col,
    header: col,
  }));

/**
 * 表格 viewer 客户端组件 (2026-07-09).
 *
 * 1. 拉 pages 数组 → 构建 pagination bar
 * 2. 当前页用 useQuery 拉单页所有 CSV 解析数据
 * 3. 每张表渲染独立 DataTable (动态列)
 * 4. URL ?page=N 不在 pages 中 → fallback pages[0]
 * 5. URL #table-M → 数据到位后 scrollIntoView
 *
 * @param props - 组件属性
 * @param props.params - 路由参数
 * @param props.params.task_id - 预分析任务 ID
 * @returns 页面 React 元素
 * @client-bff
 */
export const AdminPreAnalysisTablesClient = ({ params }: PageProps): React.ReactElement => {
  const translate = useTranslations();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [hashHandled, setHashHandled] = useState(false);

  // ① 拉所有有表格的页号列表
  const pagesQuery = useQuery<TablePagesResponse>({
    queryKey: ["pre-analysis-tables-pages", params.task_id],
    queryFn: () => getPreAnalysisTablePages(params.task_id),
  });

  const allPages = pagesQuery.data?.pages ?? [];

  // 当前页 (URL ?page=N, 无效或缺失 → fallback pages[0])
  const pageParam = searchParams.get("page");
  const requestedPage = pageParam !== null ? Number(pageParam) : null;
  const currentPage = useMemo<number | null>(() => {
    if (allPages.length === ZERO_PLACEHOLDER) {
      return null;
    }
    if (requestedPage !== null && allPages.includes(requestedPage)) {
      return requestedPage;
    }
    const firstPage = allPages[ZERO_PLACEHOLDER];
    return firstPage ?? null;
  }, [allPages, requestedPage]);

  // ② 当前页数据 (懒加载, 只 fetch 当前页)
  const pageQuery = useQuery<TablePageResponse>({
    queryKey: ["pre-analysis-tables-page", params.task_id, currentPage],
    queryFn: () => {
      if (currentPage === null) {
        throw new Error("currentPage not ready");
      }
      return getPreAnalysisTablePage(params.task_id, currentPage);
    },
    enabled: currentPage !== null,
  });

  // ③ hash anchor 滚动: 数据加载后滚到 #table-M
  useEffect(() => {
    if (hashHandled || !pageQuery.data) {
      return;
    }
    const hash = window.location.hash;
    if (hash.length > 1) {
      const el = document.getElementById(hash.slice(1));
      el?.scrollIntoView({ behavior: SCROLL_BEHAVIOR, block: "start" });
    }
    setHashHandled(true);
  }, [pageQuery.data, hashHandled]);

  /** 切到指定 PDF 页 (URL ?page=N). */
  const handlePageClick = useCallback(
    (page: number) => {
      router.push(`/admin/pre-analysis/${params.task_id}/tables?page=${page}`);
    },
    [router, params.task_id],
  );

  // pagination 可见按钮
  const visibleItems = useMemo(() => {
    if (allPages.length === ZERO_PLACEHOLDER) {
      return [];
    }
    const currentIdx = currentPage === null ? ZERO_PLACEHOLDER : allPages.indexOf(currentPage);
    return buildVisiblePages(allPages, currentIdx);
  }, [allPages, currentPage]);

  const tablesForPage = pageQuery.data?.tables ?? [];
  const tableDataPairs = useMemo(
    () =>
      tablesForPage.map((table: TablePageItem) => ({
        table,
        columns: buildDynamicColumns(table.columns),
      })),
    [tablesForPage],
  );

  return (
    <div className="space-y-6">
      <BackLink href={`/admin/pre-analysis/${params.task_id}`} label={translate("返回")} />
      <PageHero
        description={
          pagesQuery.data
            ? `${translate("共 {N} 页含表格").replace("{N}", String(pagesQuery.data.total))}`
            : undefined
        }
        eyebrow="admin"
        title={translate("表格查看")}
      />

      {/* pagination bar */}
      {pagesQuery.error ? (
        <ErrorBanner description={String(pagesQuery.error)} variant="destructive" />
      ) : null}
      {allPages.length > ZERO_PLACEHOLDER ? (
        <nav
          aria-label="pagination"
          className="flex flex-wrap items-center gap-1"
          data-testid="tables-pagination"
        >
          {/* Prev */}
          {(() => {
            const currentIdx = currentPage === null ? 0 : allPages.indexOf(currentPage);
            const prevPage = currentIdx > ZERO_PLACEHOLDER ? allPages[currentIdx - 1] ?? null : null;
            return (
              <Button
                aria-label={translate("上一页")}
                data-testid="page-prev"
                disabled={prevPage === null}
                onClick={() => {
                  if (prevPage !== null) {
                    handlePageClick(prevPage);
                  }
                }}
                size="sm"
                variant="outline"
              >
                &lt; Prev
              </Button>
            );
          })()}

          {/* 页号按钮 */}
          {visibleItems.map((item) => {
            if (item.kind === "ellipsis") {
              return (
                <span
                  className="px-2 text-muted-foreground"
                  data-testid={`ellipsis-${item.key}`}
                  key={item.key}
                >
                  …
                </span>
              );
            }
            const isCurrent = item.page === currentPage;
            return (
              <Button
                aria-current={isCurrent ? "page" : undefined}
                aria-label={`P${item.page}`}
                className="min-w-[3rem]"
                data-testid={`page-button-${item.page}`}
                key={item.page}
                onClick={() => {
                  handlePageClick(item.page);
                }}
                size="sm"
                variant={isCurrent ? "default" : "outline"}
              >
                P{item.page}
              </Button>
            );
          })}

          {/* Next */}
          {(() => {
            const currentIdx = currentPage === null ? -1 : allPages.indexOf(currentPage);
            const nextPage =
              currentIdx >= 0 && currentIdx < allPages.length - 1
                ? allPages[currentIdx + 1] ?? null
                : null;
            return (
              <Button
                aria-label={translate("下一页")}
                data-testid="page-next"
                disabled={nextPage === null}
                onClick={() => {
                  if (nextPage !== null) {
                    handlePageClick(nextPage);
                  }
                }}
                size="sm"
                variant="outline"
              >
                Next &gt;
              </Button>
            );
          })()}
        </nav>
      ) : null}

      {/* 空态: 无任何表格 */}
      {pagesQuery.data && allPages.length === ZERO_PLACEHOLDER ? (
        <DataEmpty description={translate("该任务没有提取到表格")} title={translate("无表格数据")} />
      ) : null}

      {/* page 数据 error */}
      {pageQuery.error ? (
        <ErrorBanner description={String(pageQuery.error)} variant="destructive" />
      ) : null}

      {/* 当前页所有表格 */}
      {tableDataPairs.length > ZERO_PLACEHOLDER ? (
        <div className="space-y-8">
          {tableDataPairs.map(({ table, columns }) => (
            <div className="space-y-2" data-testid={`table-block-${table.table_index}`} key={table.table_index}>
              <h3
                className="text-sm font-medium text-muted-foreground"
                id={`table-${table.table_index}`}
              >
                {translate("表格 {index}").replace("{index}", String(table.table_index))}
                <span className="ml-2 text-xs">
                  ({table.filename} · {table.rows.length} {translate("行")})
                </span>
              </h3>
              <DataTable<Record<string, string>>
                columns={columns}
                dataSource={table.rows}
                emptyText={<DataEmpty title={translate("无表格数据")} />}
                loading={pageQuery.isLoading}
                maxHeight={TABLE_MAX_HEIGHT_PX}
                pagination={undefined}
                rowKey={(row, idx) => `${table.table_index}${ROW_KEY_SEP}${idx.toString(STRING_INDEX_BASE)}`}
              />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};

// ZERO_PLACEHOLDER: 不在文件顶部 import 是为避免改动其它 viewer (CLAUDE.md 不强制 0 复用常量)
const ZERO_PLACEHOLDER = 0;
```

**注意**:
- 末尾的 `const ZERO_PLACEHOLDER = 0` 是本地常量, 不引外部常量文件, 避免污染其他文件. 满足 lint `no-magic-numbers`.
- `buildDynamicColumns` 每次表渲染都新建 ColumnDef 数组, 用 `useMemo` 包了但 maps 仍是新数组, 业务层 OK.
- `RowKey` 用 `table_index-idx` 避免同表内 row 索引冲突.
- `visibleItems` 用 `useMemo` 缓存 pagination 结构.

- [ ] **Step 4: 跑测试确认绿**

```bash
cd packages/web && bun run test -- app/[locale]/admin/pre-analysis/[task_id]/tables/_components/admin-pre-analysis-tables-client.test.tsx
```

Expected: 6 tests pass.

- [ ] **Step 5: lint + typecheck**

```bash
cd packages/web && bun run lint:fix && bun run typecheck
```

Expected: 0 error. 如果有 import 排序 / magic number / 命名等问题, lint:fix 会自动修一部分.

- [ ] **Step 6: Commit**

```bash
cd packages/web && git add "app/[locale]/admin/pre-analysis/[task_id]/tables"
git commit -m "feat(web): pre-analysis tables viewer 客户端组件 + 单测"
```

---

## Task 3.2: RSC entry `tables/page.tsx`

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/page.tsx`

- [ ] **Step 1: 创建 RSC entry**

新建 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/tables/page.tsx`:

```tsx
// admin/pre-analysis/[task_id]/tables/page.tsx — RSC entry (2026-07-09)
// 调 AdminPreAnalysisTablesClient 渲染表格 viewer 页.
// 跟 chapters/page.tsx + flagged/page.tsx 同 shape (params 是 Promise, await 后传 sync value).

import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisTablesClient } from "./_components/admin-pre-analysis-tables-client";

/**
 * admin/pre-analysis 表格查看页 (RSC).
 *
 * 渲染表格 viewer. 路由参数 task_id 透传给 client 子组件.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数 Promise
 * @param props.params.task_id - 预分析任务 ID
 * @server-only
 */
export default async function AdminPreAnalysisTablesPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisTablesClient params={{ task_id }} />
    </GuardPage>
  );
}
```

- [ ] **Step 2: typecheck**

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error.

- [ ] **Step 3: Commit**

```bash
cd packages/web && git add "app/[locale]/admin/pre-analysis/[task_id]/tables/page.tsx"
git commit -m "feat(web): pre-analysis tables viewer RSC entry"
```

---

# Phase 4: 详情页改动 + i18n

## Task 4.1: i18n keys

**Files:**
- Modify: `packages/web/messages/zh.json`
- Modify: `packages/web/messages/en.json`

- [ ] **Step 1: 加 zh.json keys**

读取 `packages/web/messages/zh.json` 末尾追加 (用 Edit 工具):

```jsonc
"表格查看": "表格查看",
"共 {N} 页含表格": "共 {N} 页含表格",
"该任务没有提取到表格": "该任务没有提取到表格",
"表格 {index}": "表格 {index}",
"上一页": "上一页",
"下一页": "下一页",
"无表格数据": "无表格数据",
"行": "行",
```

(注: 表格数 / 总表格数 / PDF 页码 / 第 {page} 页 等已经在 flagged viewer 时段加过,
查重: 如果 zh.json 里已有 `表格数` / `无标记段落` 等 key, 不重复加. 用 grep 验证.)

- [ ] **Step 2: 加 en.json keys**

读取 `packages/web/messages/en.json` 末尾追加:

```jsonc
"表格查看": "Table Viewer",
"共 {N} 页含表格": "{N} pages with tables",
"该任务没有提取到表格": "No tables extracted from this task",
"表格 {index}": "Table {index}",
"上一页": "Previous",
"下一页": "Next",
"无表格数据": "No table data",
"行": "rows",
```

- [ ] **Step 3: 校验 zh identity**

```bash
cd packages/web && node -e "
const zh = JSON.parse(require('fs').readFileSync('messages/zh.json'));
const en = JSON.parse(require('fs').readFileSync('messages/en.json'));
const KEYS = ['表格查看', '共 {N} 页含表格', '该任务没有提取到表格', '表格 {index}', '上一页', '下一页', '无表格数据', '行'];
for (const k of KEYS) {
  if (zh[k] !== k) console.error('zh identity broken:', k);
  if (!en[k]) console.error('en missing:', k);
}
console.log('OK');
"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd packages/web && git add messages/zh.json messages/en.json
git commit -m "i18n: pre-analysis tables viewer +8 keys (zh identity / en translation)"
```

---

## Task 4.2: 详情页 actions 列 + StatCard 改动

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx`
- Modify: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx`

- [ ] **Step 1: 写失败的详情页测试**

打开 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx`, 在末尾追加:

```tsx
import { getPreAnalysisTablePages } from "@/lib/api/pre-analysis";

describe("tables viewer 集成", () => {
  // 表行 "查看" 按钮: kind="table" 行渲染, table/index 不渲染 (跟 chapters/flagged 一致)
  it("kind=table 行渲染 '查看' 按钮, 跳 URL 含 ?page=N#table-M", async () => {
    const fetchMock = vi.fn(async () => Response.json({
      id: "pa-1",
      state: "completed",
      user_hash: "h",
      pdf_filename: "D81.pdf",
      pdf_uri: "local://x",
      started_at: "2026-07-09T10:00:00Z",
      finished_at: "2026-07-09T10:01:00Z",
      current_stage: "done",
      task_config_json: {},
      output_files: [
        { kind: "table", filename: "tables/page-9-table-1.csv", uri: "local://x", size_bytes: 100 },
        { kind: "table", filename: "tables/page-12-table-1.csv", uri: "local://x", size_bytes: 200 },
        { kind: "index", filename: "index.json", uri: "local://x", size_bytes: 50 },
      ],
      summary: { total_chapters: 0, total_tables: 5, total_flagged_paragraphs: 0, elapsed_ms: 1000, cross_page_candidates: 0 },
      error: null,
    }, { status: 200 })) as unknown as typeof fetch;
    globalThis.fetch = fetchMock;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      // 2 个 table 行 各有 "查看" 按钮
      expect(screen.getByTestId("view-file-tables/page-9-table-1.csv")).toBeTruthy();
      expect(screen.getByTestId("view-file-tables/page-12-table-1.csv")).toBeTruthy();
    });
    // index 行无 "查看" 按钮
    expect(screen.queryByTestId("view-file-index.json")).toBeNull();
  });

  it("表格数 StatCard 可点击 (total_tables > 0)", async () => {
    // mock fetches for: getPreAnalysisTask + getPreAnalysisTablePages (StatCard hover preload)
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/tables/pages")) {
        return Response.json({ pages: [9], total: 1 }, { status: 200 });
      }
      return Response.json({
        id: "pa-1", state: "completed", user_hash: "h",
        pdf_filename: "D81.pdf", pdf_uri: "local://x",
        started_at: "2026-07-09T10:00:00Z", finished_at: "2026-07-09T10:01:00Z",
        current_stage: "done", task_config_json: {},
        output_files: [],
        summary: { total_chapters: 0, total_tables: 5, total_flagged_paragraphs: 0, elapsed_ms: 1000, cross_page_candidates: 0 },
        error: null,
      }, { status: 200 });
    }) as unknown as typeof fetch;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => screen.getByTestId("stat-card-tables"));

    const card = screen.getByTestId("stat-card-tables");
    expect(card.getAttribute("role")).toBe("button");
  });
});
```

(实际可能跟现有 test 文件 import 略有差异, 跑测试时按 `never-overwrite-existing-test-files` 守则
先 Read 现有测试, 用 Edit 追加而非 Write 覆盖.)

- [ ] **Step 2: 跑测试确认失败**

```bash
cd packages/web && bun run test -- "app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx"
```

Expected: `view-file-tables/page-9-table-1.csv` 找不到.

- [ ] **Step 3: 改详情页**

修改 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx`:

**a. import 改动** (顶部):

```tsx
import {
  downloadPreAnalysisFile,
  downloadPreAnalysisZip,
  getPreAnalysisTask,
  parseTableFilename,            // ← 新
  type PreAnalysisOutputFile,
  type PreAnalysisTaskState,
} from "@/lib/api/pre-analysis";
```

**b. VIEWABLE_KINDS 改动** (line 66 附近):

```tsx
/**
 * (2026-07-09 viewer pages) 可在 web 端预览的产物 kind — chapter_structure 跳 chapters 子路由,
 * flagged_paragraphs 跳 flagged 子路由, table 跳 tables 子路由 (带 ?page=N#table-M).
 * index 没 viewer 页, 仍只走 download 按钮.
 *
 * (2026-07-09 tables viewer) 加入 "table".
 */
const VIEWABLE_KINDS = ["chapter_structure", "flagged_paragraphs", "table"] as const;
type ViewableKind = (typeof VIEWABLE_KINDS)[number];
```

**c. viewHrefForKind 改动** (line 83 附近):

```tsx
/**
 * (2026-07-09 tables viewer) 算 viewable href.
 * chapter_structure / flagged_paragraphs 跟 task_id 拼固定子路由.
 * table 需要从 filename 解析 page + table_index, URL 带 ?page=N#table-M.
 *
 * @param kind ViewableKind
 * @param taskId 任务 ID
 * @param filename (table 必填) 文件名, e.g. "tables/page-9-table-1.csv"
 * @returns 子路由 href
 */
const viewHrefForKind = (
  kind: ViewableKind,
  taskId: string,
  filename?: string,
): string => {
  if (kind === "table") {
    if (!filename) {
      throw new Error("table kind 需要 filename 算 ?page=N#table-M");
    }
    const { pageNumber, tableIndex } = parseTableFilename(filename);
    return `/admin/pre-analysis/${taskId}/tables?page=${pageNumber}#table-${tableIndex}`;
  }
  if (kind === "chapter_structure") return `/admin/pre-analysis/${taskId}/chapters`;
  return `/admin/pre-analysis/${taskId}/flagged`;
};
```

**d. actions 列 cell 改动** (line 220 附近, `cell: (ctx) => {` 体内):

```tsx
cell: (ctx) => {
  const file = ctx.row.original;
  const viewable = isViewableKind(file.kind)
    ? viewHrefForKind(file.kind, params.task_id, file.filename)
    : null;
  return (
    <div className="flex gap-2">
      {viewable ? (
        <Button
          data-testid={`view-file-${file.filename}`}
          onClick={() => {
            router.push(viewable);
          }}
          size="sm"
          variant="outline"
        >
          <Eye className="mr-1 h-4 w-4" />
          {translate("查看")}
        </Button>
      ) : null}
      <Button
        data-testid={`download-file-${file.filename}`}
        onClick={() => {
          void handleDownloadFile(file.filename);
        }}
        size="sm"
        variant="outline"
      >
        <Download className="mr-1 h-4 w-4" />
        {translate("下载")}
      </Button>
    </div>
  );
},
```

(`isViewableKind` 守卫已存在, 扩展后 type 自动 narrow, 不改 `isViewableKind` 实现.)

**e. 表格数 StatCard 改 onClick** (line 277 附近):

```tsx
<StatCard
  accent="clay"
  hint={translate("跨页候选: {N}", { N: data.summary.cross_page_candidates })}
  index={0}
  label={translate("表格数")}
  onClick={
    data.summary.total_tables > ZERO
      ? () => {
          router.push(`/admin/pre-analysis/${params.task_id}/tables`);
        }
      : undefined
  }
  testId="stat-card-tables"
  value={data.summary.total_tables}
/>
```

- [ ] **Step 4: 跑测试确认绿**

```bash
cd packages/web && bun run test -- "app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx"
```

Expected: 全部 pass.

- [ ] **Step 5: 跑详情页相关所有测试**

```bash
cd packages/web && bun run test -- "app/[locale]/admin/pre-analysis"
```

Expected: 全部 pass (含 chapters/flagged/tables/detail 4 个 client test).

- [ ] **Step 6: lint + typecheck**

```bash
cd packages/web && bun run lint:fix && bun run typecheck
```

Expected: 0 error.

- [ ] **Step 7: Commit**

```bash
cd packages/web && git add \
  "app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx" \
  "app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx"
git commit -m "feat(web): pre-analysis detail — table 行 查看 按钮 + 表格数 StatCard 可点击"
```

---

# Phase 5: 端到端验证

## Task 5.1: 后端测试 + 前端测试全量

- [ ] **Step 1: 后端代码质量**

```bash
cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright
```

Expected: 0 error.

- [ ] **Step 2: 后端测试 (新改 + 邻近模块无回归)**

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/ -v
```

Expected: 全部 pass. (pre-existing fail 在 [KNOWN_ISSUES.md](../service/KNOWN_ISSUES.md), 不算新 fail.)

- [ ] **Step 3: 前端 lint + typecheck**

```bash
cd packages/web && bun run format && bun run lint:fix && bun run typecheck
```

Expected: 0 error.

- [ ] **Step 4: 前端测试 (改过的文件单跑)**

```bash
cd packages/web && bun run test -- lib/api/pre-analysis.test.ts
cd packages/web && bun run test -- "app/[locale]/admin/pre-analysis"
```

Expected: 全部 pass.

- [ ] **Step 5: 前端测试 (全量)**

```bash
cd packages/web && bun run test
```

Expected: 全部 pass (~720+ tests, 含原有 + 新加的 ~17 tests).

- [ ] **Step 6: 跑契约测试**

```bash
cd packages/service && uv run pytest tests/test_api_contract.py -v
```

Expected: 0 fail (新增 BFF 路由 + 后端 2 端点都不破坏 contract).

- [ ] **Step 7: 手工 E2E (dev 环境)**

```bash
# 1. 启动后端
cd packages/service && uv run python main.py
# 2. 启动前端 (另一个终端)
cd packages/web && bun run dev
# 3. 浏览器访问 http://localhost:3000/zh/admin/pre-analysis
# 4. 选一条 completed 的任务
# 5. 详情页点 "查看" (kind=table 行) → 跳 /tables?page=N#table-M, 验证:
#    - URL hash 锚点滚动到指定 table
#    - pagination 条显示所有 PDF 页号 (P3, P9, P12, ...)
#    - 当前页高亮
#    - 表格按列渲染
#    - 点别的页号 → URL ?page=N 更新, 数据重新 fetch
#    - 边界: 点 "Prev" / "Next" 按钮正确切换
# 6. 详情页点 StatCard "表格数" → 跳 /tables (默认第 1 页有表格的 PDF 页)
```

- [ ] **Step 8: 记录实施结果**

在 `docs/superpowers/specs/2026-07-09-pre-analysis-tables-viewer-design.md` 末尾追加实施记录段:

```markdown
## 实施记录 (2026-07-09)

- PR #N (后端): `feat(pre-analysis): tables viewer 后端 2 端点` (Tasks 1.1-1.3)
- PR #N (BFF + helper): `feat(web): pre-analysis tables BFF + types + helpers` (Tasks 2.1-2.3)
- PR #N (client): `feat(web): pre-analysis tables viewer client` (Tasks 3.1-3.2)
- PR #N (detail + i18n): `feat(web): pre-analysis detail 查看 + StatCard + i18n` (Tasks 4.1-4.2)
- 测试结果: 后端 N tests pass / 前端 M tests pass / 0 回归
- 浏览器手测: pagination + hash 滚动 + StatCard 跳转 OK
```

- [ ] **Step 9: Commit 实施记录**

```bash
git add docs/superpowers/specs/2026-07-09-pre-analysis-tables-viewer-design.md
git commit -m "docs(spec): pre-analysis tables viewer 实施记录"
```

---

# 关联文档

- 设计 spec: [`2026-07-09-pre-analysis-tables-viewer-design.md`](../specs/2026-07-09-pre-analysis-tables-viewer-design.md)
- 上游 viewer plan: [`2026-07-09-pre-analysis-viewer-pages.md`](2026-07-09-pre-analysis-viewer-pages.md) (chapters + flagged, 同样模式)
- BFF 模式: `app/api/ingest/tasks/[id]/files/[name]/route.ts`
- 后端 router 模板: `src/ingest/pre_analysis/router.py`
- 后端 store: `src/ingest/pre_analysis/store.py` (`pa_load_task`)
- 后端测试模板: `tests/ingest/pre_analysis/test_router.py`
- 前端 client 模板: `app/[locale]/admin/pre-analysis/[task_id]/chapters/_components/admin-pre-analysis-chapters-client.tsx`
- 前端 detail 模板: `app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx`
- 项目规约: [`packages/web/CLAUDE.md`](../../packages/web/CLAUDE.md), [`packages/service/CLAUDE.md`](../../packages/service/CLAUDE.md), [根 CLAUDE.md](../../CLAUDE.md)