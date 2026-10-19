# Pre-analysis stage 抽离 spec (v1)

**日期**: 2026-07-09
**状态**: 设计待审
**触发来源**: 抽 `_extract_chapters` 到 `chapter_extractors/` 后, runner.py 仍 503 行, 用户决策把 5 个 stage 各自拆到独立模块.

---

## Context

[runner.py:96-266](../packages/service/src/ingest/pre_analysis/runner.py#L96-L266) 主入口 `PreAnalysisRunner.run()` 包含 5 个 stage 完整逻辑 (mark_started → 算法 → 写盘 → DB append → mark_completed → 异常兜底), 共 170 行 try/except + 9 个私有辅助方法 (合计 ~330 行). 文件总 503 行, 超 CLAUDE.md §代码长度 "每类 ≤ 100 行" 约束.

### 现状问题

1. **runner.py 上帝类**: 5 个 stage + 7 个私有方法 (_extract_tables / _detect_cross_page / _write_one_table / _write_chapter_structure / _write_flagged_paragraphs / _write_index / _append_artifact / _output_prefix / _load_config), 单一职责违反.
2. **算法 + I/O 混层**: extractor 目录 (chapter_extractors/flag_extractors/table_extractors) 已是纯算法层, 但**写盘 + DB append 全堆 runner**, 抽象层泄漏.
3. **stage 间数据流不显式**: chapters/tables/flagged 都用局部变量传递, 没有显式 ctx 容器, 后续加 stage (e.g. 目录页解析) 难扩展.

### 已完成前置工作 (2026-07-08)

- 抽 `_extract_chapters` 到 `chapter_extractors/` 子模块, 留 `ChapterExtractor` ABC + `extract_chapters(doc)` 顶层入口
- 9 个单测覆盖 OutlineExtractor + factory, ruff/pyright/pytest 全绿

### 设计目标

1. **runner.py ≤ 200 行**, 只剩编排 (5 段 stage 调用 + mark_running/completed)
2. **每个 stage 自包含**: 算法 + 写盘 + DB append + 异常兜底, 独立单测
3. **stage 间数据流显式**: StageContext dataclass 装依赖 + 累积字段, `ctx.replace()` immutable 传值
4. **零行为差异**: 拆完不引入新逻辑, 跟原 runner.py 行为字节对齐

---

## 架构

### 文件结构

```
packages/service/src/ingest/pre_analysis/
├── runner.py                                (~150 行, 5 段 stage 编排 + mark_running/completed)
├── stage_context.py                         (新, StageContext + StageResult dataclass)
├── db_artifact.py                           (新, append_artifact 公共函数)
├── prepare_input.py                         (新, stage 1: open_local + pymupdf.open + yaml)
├── finalize_output.py                       (新, stage 5: index.json + current_stage='done')
├── chapter_extractors/
│   ├── __init__.py                          (已有)
│   ├── base.py                              (已有)
│   ├── outline.py                           (已有)
│   └── chapters_section.py                  (新, stage 2)
├── flag_extractors/
│   ├── __init__.py                          (已有)
│   ├── extractor.py                         (已有)
│   ├── spacy_enhancer.py                    (已有)
│   ├── splitter.py                          (已有)
│   └── flagged_section.py                   (新, stage 4)
└── table_extractors/
    ├── __init__.py                          (已有)
    ├── base.py                              (已有)
    ├── factory.py                           (已有)
    ├── pymupdf_extractor.py                 (已有)
    ├── camelot_extractor.py                 (已有)
    ├── pdfplumber_extractor.py              (已有)
    └── tables_section.py                    (新, stage 3)
```

测试对应:
```
packages/service/tests/ingest/pre_analysis/
├── test_stage_context.py                    (新, 3 test)
├── test_db_artifact.py                      (新, 3 test)
├── test_prepare_input.py                    (新, 5 test)
├── test_finalize_output.py                  (新, 4 test)
├── chapter_extractors/
│   └── test_chapters_section.py             (新, 4 test)
├── flag_extractors/
│   └── test_flagged_section.py              (新, 3 test)
├── table_extractors/
│   └── test_tables_section.py               (新, 4 test)
└── test_runner.py                           (已有, 不改, 跑回归)
```

### 模块依赖图

```
runner.py
├── prepare_input.py
├── finalize_output.py
├── chapter_extractors/chapters_section.py
│   └── chapter_extractors/__init__.py       (extract_chapters 入口)
│   └── stage_context.py
│   └── db_artifact.py
├── flag_extractors/flagged_section.py
│   └── flag_extractors/__init__.py          (extract_flagged_paragraphs 入口)
│   └── stage_context.py
│   └── db_artifact.py
└── table_extractors/tables_section.py
    ├── table_extractors/factory.py          (get_table_extractor)
    ├── stage_context.py
    └── db_artifact.py
```

---

## 组件契约

### stage_context.py

```python
from dataclasses import dataclass, replace
import pymupdf

# ObjectStoreProto / StageStoreProto Protocol 定义从 runner.py 搬到 stage_context.py
# (stage 文件直接 import Protocol, 不再依赖 runner.py 的内部定义)
class ObjectStoreProto(Protocol): ...
class StageStoreProto(Protocol): ...

@dataclass(frozen=True)
class StageContext:
    """5 个 stage 共用依赖容器. frozen=True + replace() immutable 传值."""
    task_id: str
    pdf_uri: str
    object_store: ObjectStoreProto       # Protocol, 定义在 stage_context.py
    task_store: PreAnalysisTaskStore
    stage_store: StageStoreProto
    start_monotonic: float

    # stage 1 产出
    doc: pymupdf.Document | None = None
    config: dict | None = None
    output_prefix: str | None = None

    # stage 2 产出
    chapters: list[dict] | None = None
    chapter_uri: str | None = None

    # stage 3 产出
    tables: list[tuple[int, int, list[list[str]]]] | None = None
    cross_page_count: int = 0

    # stage 4 产出
    flagged: list[dict] | None = None
    flagged_uri: str | None = None

    # stage 5 产出
    index_uri: str | None = None


@dataclass(frozen=True)
class StageResult:
    """stage 函数返回. ok=False 表示 stage 失败, runner 应终止."""
    ok: bool
    error: str | None = None
    stage_name: str = ""
    message: str | None = None
```

### db_artifact.py

```python
def append_artifact(
    task_id: str,
    kind: str,
    filename: str,
    uri: str,
    size_bytes: int,
) -> None:
    """DB output_files_json append 1 项. 4 个 stage 共享.

    测试时由 conftest::mock_all_db_connections 自动覆盖 session_scope,
    不需要每个测试手动 patch.
    """
    with session_scope() as s:
        task = s.get(PreAnalysisTask, task_id)
        if task is None:
            return
        current = json.loads(task.output_files_json or "[]")
        current.append({
            "kind": kind,
            "filename": filename,
            "uri": uri,
            "size_bytes": size_bytes,
        })
        task.output_files_json = json.dumps(current, ensure_ascii=False)
```

### stage 函数签名统一

```python
def stage_fn(ctx: StageContext, ...) -> tuple[StageContext, StageResult]:
    """每个 stage 函数: 吃 ctx, 返 (新 ctx, StageResult)."""
```

---

## 5 个 stage 实现细节

### stage 1: prepare_input.py

职责: open_local → pymupdf.open → yaml load.

行为对齐原 [runner.py:117-139](../packages/service/src/ingest/pre_analysis/runner.py#L117-L139):

| 失败位置 | mark_stage_failed | mark_task_failed | 返 ok=False |
|---|---|---|---|
| open_local 异常 | ✅ | ✅ | ✅ |
| pymupdf.open 异常 | ✅ | ✅ | ✅ |
| yaml 缺失/解析失败 | ❌ 兜底默认 5 关键词 | ❌ | ❌ 继续 |

返值: `(ctx.replace(doc=doc, config=config, output_prefix=prefix), StageResult(ok=True))`

### stage 2: chapter_extractors/chapters_section.py

职责: `extract_chapters(doc)` → 写 `chapter_structure.json` → DB append.

行为对齐原 [runner.py:141-159](../packages/service/src/ingest/pre_analysis/runner.py#L141-L159) + [_write_chapter_structure](../packages/service/src/ingest/pre_analysis/runner.py#L392-L413).

返值: `(ctx.replace(chapters=chapters, chapter_uri=uri), StageResult(ok=True, message=f"{len(chapters)} 章"))`

### stage 3: table_extractors/tables_section.py

职责: `get_table_extractor(backend)` → 提 tables → `_detect_cross_page` → 逐张写 CSV + DB append.

行为对齐原 [runner.py:161-180](../packages/service/src/ingest/pre_analysis/runner.py#L161-L180) + [_extract_tables](../packages/service/src/ingest/pre_analysis/runner.py#L277-L301) + [_detect_cross_page](../packages/service/src/ingest/pre_analysis/runner.py#L303-L333) + [_write_one_table](../packages/service/src/ingest/pre_analysis/runner.py#L335-L357).

函数签名: `run(ctx: StageContext, table_extraction_config: dict) -> tuple[StageContext, StageResult]` (table_extraction_config 由 runner 透传).

返值: `(ctx.replace(tables=tables, cross_page_count=cross_page), StageResult(ok=True, message=f"{len(tables)} 表 / {cross_page} 跨页候选"))`

### stage 4: flag_extractors/flagged_section.py

职责: `extract_flagged_paragraphs(doc, config)` → 写 14 列 CSV → DB append.

行为对齐原 [runner.py:182-197](../packages/service/src/ingest/pre_analysis/runner.py#L182-L197) + [_write_flagged_paragraphs](../packages/service/src/ingest/pre_analysis/runner.py#L415-L454).

返值: `(ctx.replace(flagged=flagged, flagged_uri=uri), StageResult(ok=True, message=f"{len(flagged)} 段落"))`

### stage 5: finalize_output.py

职责: 写 `index.json` → DB append → 更新 `task.current_stage='done'`.

**不调 mark_task_completed**: 由 runner.run() 末尾统一调, 跟原 [runner.py:246](../packages/service/src/ingest/pre_analysis/runner.py#L246) 行为一致.

函数签名: `run(ctx: StageContext, *, elapsed_ms: int) -> tuple[StageContext, StageResult]`.

返值: `(ctx.replace(index_uri=uri), StageResult(ok=True))`

---

## runner.run() 编排

```python
def run(self, task_id, pdf_uri, table_extraction_config=None):
    if table_extraction_config is None:
        table_extraction_config = {"table_backend": "pymupdf", "table_params": {}}
    start = time.monotonic()

    ctx = StageContext(
        task_id=task_id, pdf_uri=pdf_uri,
        object_store=self.object_store, task_store=self.task_store,
        stage_store=self.stage_store, start_monotonic=start,
    )

    # stage 1
    ctx, r = prepare_input(ctx)
    if not r.ok:
        return PreAnalysisResult(success=False, task_id=task_id, error=r.error)

    # stage 2
    ctx, r = chapters_section(ctx)
    if not r.ok:
        ctx.doc.close()
        return PreAnalysisResult(success=False, task_id=task_id, error=r.error)

    # stage 3
    ctx, r = tables_section(ctx, table_extraction_config)
    if not r.ok:
        ctx.doc.close()
        return PreAnalysisResult(success=False, task_id=task_id, error=r.error)

    # stage 4
    ctx, r = flagged_section(ctx)
    if not r.ok:
        ctx.doc.close()
        return PreAnalysisResult(success=False, task_id=task_id, error=r.error)

    # stage 5
    elapsed_ms = int((time.monotonic() - start) * 1000)
    ctx, r = finalize_output(ctx, elapsed_ms=elapsed_ms)
    if not r.ok:
        ctx.doc.close()
        return PreAnalysisResult(success=False, task_id=task_id, error=r.error)

    ctx.doc.close()
    return self._build_success_result(ctx, table_extraction_config, start)
```

`_build_success_result` 内部: 读 DB 拿 `final_output_files` → 构造 `PreAnalysisResult` → `mark_task_completed`.

---

## 错误处理

| 失败位置 | mark_stage_started | mark_stage_failed | mark_task_failed | doc.close |
|---|---|---|---|---|
| stage 1: open_local | ❌ (try 前) | ✅ | ✅ | ❌ |
| stage 1: pymupdf.open | ✅ | ✅ | ✅ | ❌ |
| stage 1: yaml | ✅ | ❌ 兜底 | ❌ | ❌ |
| stage 2-5 | ✅ | ✅ | ✅ | ✅ (runner 负责) |

**`doc.close()` 责任**: stage 函数**不调** doc.close, 完全由 runner 编排层负责. pymupdf.Document.close() 幂等, 重复调用安全.

**stage 5 特殊性**: 不调 `mark_task_completed`, 只更新 `task.current_stage='done'`. `mark_task_completed` 由 runner._build_success_result 在所有 stage 成功后统一调.

---

## 测试计划

### 测试隔离

- **全局 autouse `mock_all_db_connections`** ([tests/conftest.py](../packages/service/tests/conftest.py)): 自动 mock session_scope, stage 测试不需要手动 patch
- **真 fixture PDF**: `tests/fixtures/d81_dummy.pdf` (5KB, 已有, 仅 prepare_input.py + test_runner.py 集成测试用)
- **单测模式**: mode 1 mock, 全 MagicMock 不开真 PDF (除 prepare_input 部分场景)

### 测试文件 + 覆盖

| 文件 | test 数 | 覆盖 |
|---|---|---|
| test_stage_context.py | 3 | replace() 不可变 / 字段累积 / 默认值 |
| test_db_artifact.py | 3 | happy path / task 不存在静默 / JSON 格式不变 |
| test_prepare_input.py | 5 | open_local ok / pymupdf.open ok / open_local 失败 / pymupdf 失败 / yaml 缺失兜底 |
| test_chapters_section.py | 4 | happy / 0 chapters (toc_source='empty') / 写盘失败 / 异常兜底 |
| test_tables_section.py | 4 | happy / 0 tables / 跨页检测 / 单表写盘失败 |
| test_flagged_section.py | 3 | happy / 0 flagged / 14 列 CSV 写盘 |
| test_finalize_output.py | 4 | happy / DB current_stage 更新 / 写盘失败 / 读 DB 累计 files |
| test_runner.py | (已有 8 个, 不改) | 5 stage 完整流回归 |

合计 **26 个新 test + 8 个回归 test**.

### 不测的内容 (YAGNI)

- ❌ 真 PG 真连 (CLAUDE.md §测试隔离禁止)
- ❌ 真 MinIO/LocalFS (全 mock)
- ❌ 并发 / race condition (单线程同步)
- ❌ spacy / tiktoken 行为 (flag_extractors 已有覆盖)

---

## 风险

1. **stage_context.py dataclass frozen 字段累积**: 字段多了 dataclass 膨胀, 后续每加 stage 都要改. 缓解: 字段命名按 stage 分组, 加注释.
2. **db_artifact.py 共享 session_scope**: 4 个 stage 都依赖, 改 session_scope 行为影响面大. 缓解: 单测覆盖 append_artifact, 行为契约清晰.
3. **stage 1 双重 try + mark_running_done 语义**: 跟原 runner.py 字节对齐, 但 stage 1 函数膨胀. 缓解: 内部 `_fail_open_local` / `_fail_pymupdf` 辅助函数拆 3 行.
4. **stage 5 不 mark_completed 的隐式契约**: 新人接手容易在 stage 5 内部加 mark_completed. 缓解: 注释 + 集成测试覆盖.

---

## 实施顺序 (commit 拆分, 跟 CLAUDE.md §大改动分批提交)

1. **commit 1**: `feat(pre-analysis): 抽 stage_context + db_artifact 公共件`
   - 新文件: stage_context.py, db_artifact.py
   - 新测试: test_stage_context.py (3), test_db_artifact.py (3)
   - runner.py 不动 (验证公共件可独立测试)
2. **commit 2**: `feat(pre-analysis): 抽 stage 1 prepare_input.py`
   - 新文件: prepare_input.py
   - 新测试: test_prepare_input.py (5)
   - runner.py: 删 _load_config + _output_prefix, 改 stage 1 块调 prepare_input
3. **commit 3**: `feat(pre-analysis): 抽 stage 2 chapters_section.py`
   - 新文件: chapter_extractors/chapters_section.py
   - 新测试: test_chapters_section.py (4)
   - runner.py: 删 _write_chapter_structure, 改 stage 2 块调 chapters_section
4. **commit 4**: `feat(pre-analysis): 抽 stage 3 tables_section.py`
   - 新文件: table_extractors/tables_section.py
   - 新测试: test_tables_section.py (4)
   - runner.py: 删 _extract_tables + _detect_cross_page + _write_one_table, 改 stage 3 块调 tables_section
5. **commit 5**: `feat(pre-analysis): 抽 stage 4 flagged_section.py`
   - 新文件: flag_extractors/flagged_section.py
   - 新测试: test_flagged_section.py (3)
   - runner.py: 删 _write_flagged_paragraphs, 改 stage 4 块调 flagged_section
6. **commit 6**: `feat(pre-analysis): 抽 stage 5 finalize_output.py`
   - 新文件: finalize_output.py
   - 新测试: test_finalize_output.py (4)
   - runner.py: 删 _write_index, 改 stage 5 块调 finalize_output
7. **commit 7**: `refactor(pre-analysis): runner.py 移除 _append_artifact, 改调 db_artifact.append_artifact`
   - 删 runner._append_artifact, 4 个 stage 改调 db_artifact
   - 集成测试回归

每 commit 后: ruff format + ruff check + pyright + 单文件 pytest. **最终 commit 前跑全量 pytest**.

---

## 验收

- [ ] runner.py ≤ 200 行 (CLAUDE.md §代码长度)
- [ ] 5 个新 stage 文件每个 ≤ 100 行
- [ ] 26 个新 test 全绿
- [ ] test_runner.py 集成测试 8 个全绿 (零回归)
- [ ] ruff format + ruff check 0 error
- [ ] pyright 0 error
- [ ] uv run pytest 全量无新 fail (pre-existing 不算)
- [ ] 7 个 commit 顺序按实施顺序拆

---

## 不在本期范围

- ❌ 章节提取算法优化 (toc_page / font_size) — 后续 spec
- ❌ 跨页表真合并 — 用户决策 2026-07-02 不做
- ❌ stage 重试 / 断点续跑 — 现有 stage 失败 = 整 task 失败, 后续 spec
- ❌ runner.py 进一步瘦身 (e.g. 删 ObjectStoreProto/StageStoreProto Protocol 移到独立文件) — 后续 spec