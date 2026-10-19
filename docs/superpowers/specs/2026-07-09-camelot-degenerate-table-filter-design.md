# 2026-07-09 Camelot 退化表过滤设计

> Brainstorming 沉淀. 用户报告: Camelot 生成的 CSV 中, 整张表的
> 多行内容被合并到 1 个单元格; 同时生成了大量只有 1 个单元格的"假表".
> 本 spec 在写入边界加硬阈值过滤退化表, 改动最小, 风险最低.

## 1. 背景

用户给的实际故障 CSV 样例 (Camelot stream flavor 输出):

```csv
"Rated power
Efficiency  in %
IEC IE class
...
315 … 1000
95.8
96.0
95.8
94.6
96.5
96.7
96.6
95.4"
```

整段表被压成 **1 列 N 行** (即 1 个双引号块包含全部文本). 同时
伴随大量 **1×1 单单元格**"假表".

### 根因

- `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py:195`
  用 `t.df.values.tolist()` 直接拿 Camelot 输出, 当 `stream` flavor
  在没有线条、扫描型 PDF 上识别失败时, 退化成"整页文本块作为 1 列".
- `packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py:130-131`
  `for page_no, table_no, rows in tables: _write_one_table(...)` 完全无条件
  接受, 不做质量检查.

## 2. 目标

- 在写入前 (CSV + DB artifact) 过滤掉 Camelot 识别出的退化表.
- 退化判定: **行 < 2 或 列 < 2** (即不是横表也不是 2 行以上表格).
- 过滤结果可观察: logger.warning + StageResult 汇总.

## 3. 非目标

- **不**调 Camelot 提取器参数 (`row_tol`/`columns`/`process_background` 等),
  那是数据敏感的赌博, 不同 PDF 最优值不同, 本 spec 不动.
- **不**删 Camelot 后端, 它仍是 R1 兼容期 opt-in 选项.
- **不**改 PDF 编排 (kreuzberg/mineru vs table_backend), 那是另一个 spec.
- **不**改 CSV schema, 不改 DB schema, 不改 API 字段, 不改 BFF, 不改前端.

## 4. 设计

### 4.1 改动范围 (2 文件 + 2 测试文件)

源文件:
- `packages/service/src/ingest/pre_analysis/table_extractors/base.py` — `TableData` 加 `is_valid_table` 静态方法 + 2 常量
- `packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py` — `run()` 调 `TableData.is_valid_table`

测试文件:
- `packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py` (新建) — 测 `is_valid_table` 静态方法 8 case
- `packages/service/tests/ingest/pre_analysis/table_extractors/test_tables_section_filter.py` (新建) — 测 `run()` 集成 3 case

抽到 `base.py` 作 `TableData.is_valid_table` 静态方法, 让 3 个 extractor (pymupdf/camelot/pdfplumber) 后续也能直接调用, 不重复实现.

### 4.2 `base.py` 新增 (TableData 内)

```python
# base.py — TableData dataclass 内 (2026-07-09 新增, 通用退化表判定)

_MIN_ROWS: int = 2   # 至少 2 行 (含表头)
_MIN_COLS: int = 2   # 至少 2 列 (横表)


@dataclass(frozen=True)
class TableData:
    """单张表格单元. 3 个实现统一这个 shape, runner 不关心后端.

    Attributes:
        page_no: 1-based 页码 (跨页合并后是 str 如 "5+6")
        table_no: 1-based (该页内编号)
        rows: 二维字符串表格
    """

    # (2026-07-09) page_no 可 str: 跨页合并表编码 "5+6" 表示 5+6 页拼成 1 张
    page_no: int | str
    table_no: int
    rows: list[list[str]]

    @staticmethod
    def is_valid_table(rows: Sequence[Sequence[str]]) -> bool:
        """(2026-07-09) 硬阈值:行>=2 且 列>=2 (排除整行空白).

        解决 Camelot stream fallback 出来的 1×N 假表 (整段文本当一列),
        以及 pymupdf/pdfplumber 在某些 PDF 上的 1×1 单格输出.

        rows 可能为空 [] 或 [[]] (空表) — 都返回 False.
        2×1 纵列表同样视为退化 (PDF 表格场景几乎不存在真实纵列表).
        整行所有 cell strip 后都是空字符串算作该行无内容, 不计入行数.
        """
        if not rows:
            return False
        non_blank_rows = [r for r in rows if any((c or "").strip() for c in r)]
        if len(non_blank_rows) < _MIN_ROWS:
            return False
        cols = max((len(r) for r in non_blank_rows), default=0)
        return cols >= _MIN_COLS
```

`Sequence` 需要在 base.py 顶部加 `from collections.abc import Sequence`.

### 4.3 `tables_section.py` 改动

删除原本 spec 中的顶层 `_MIN_ROWS` / `_MIN_COLS` / `_is_valid_table` (已挪到 base.py).

`run()` 改 (tables_section.py 中 _detect_cross_page 调用前插过滤, for 循环原样写):

```python
extractor = get_table_extractor(backend, params)
raw_tables = extractor.extract(
    doc.name or "",
    _pymupdf_doc=doc,
)
tables = [(t.page_no, t.table_no, t.rows) for t in raw_tables]

# (2026-07-09) 过滤退化表 (1×1 / 1×N / 全空白行), 写入前 + cross_page 检测前都丢
valid_tables: list[tuple[int | str, int, Sequence[Sequence[str]]]] = []
skipped_count = 0
for page_no, table_no, rows in tables:
    if not TableData.is_valid_table(rows):
        skipped_count += 1
        logger.warning(
            "丢弃退化表 page={} table={} rows={} cols={}",
            page_no, table_no, len(rows),
            max((len(r) for r in rows), default=0),
        )
        continue
    valid_tables.append((page_no, table_no, rows))
tables = valid_tables

cross_page = _detect_cross_page(tables, config)

for page_no, table_no, rows in tables:
    _write_one_table(ctx.object_store, output_prefix, page_no, table_no, rows, ctx.task_id)
```

注意过滤**必须在 `_detect_cross_page` 之前** (line 128), 否则 cross_page 候选会包含 1×1 假表.

### 4.4 StageResult.message 改动

原: `f"{len(tables)} 表 / {cross_page} 跨页候选"`
新: `f"{len(tables)} 表 / {skipped_count} 丢弃 / {cross_page} 跨页候选"`

`mark_stage_completed` 的 `message` 字段同步更新.

### 4.5 数据流

```
extractor.extract()                            # camelot/pymupdf/pdfplumber
  → raw_tables: list[TableData]                 # 含 1×1 / 1×N 假表
  → tables: list[tuple[page_no, table_no, rows]] # 全部候选
  → TableData.is_valid_table 过滤 (新步骤, 在 cross_page 之前)
    → True:  valid_tables.append
    → False: logger.warning + skipped_count++   # 不写 CSV, 不 append_artifact
  → _detect_cross_page(过滤后 tables, config)    # 现在拿到的表都是有效的
  → for valid_tables: _write_one_table → ObjectStore + db_artifact
  → StageResult(valid_count, skipped_count, cross_page)
```

`_detect_cross_page` 现在拿到**过滤后**的表, 跨页候选统计更准确
(以前包含 1×1 表会把 col_match 比例算崩).

## 5. 错误处理

- `_is_valid_table` 是纯函数, 永不抛.
- `logger.warning` 不影响 stage 状态 (不标 failed).
- `skipped_count` 计入 `StageResult.message`, 便于 UI 弹"3 表被丢弃"提示.
- 不新加 error 类型 — 这是静默过滤, 不是错误.
- DB schema 不变: `output_files_json` 只存通过阈值的表 (本来就该这样).

## 6. 测试

新文件 2 个, 都用模式 1 mock, 无 PG.

### 6.1 `tests/.../test_base.py` (新文件, 测 TableData.is_valid_table 8 case)

| # | Case | 输入 | 期望 |
|---|---|---|---|
| 1 | `test_is_valid_table_2x2_returns_true` | `[["a","b"],["1","2"]]` | True |
| 2 | `test_is_valid_table_3x4_returns_true` | 真实跨页合并后的多行多列 | True |
| 3 | `test_is_valid_table_1x1_returns_false` | `[["text"]]` | False |
| 4 | `test_is_valid_table_1xN_returns_false` | `[["a","b","c"]]` (Camelot 退化 case) | False |
| 5 | `test_is_valid_table_2x1_returns_false` | `[["a"],["b"]]` (纵列退化) | False |
| 6 | `test_is_valid_table_empty_rows_returns_false` | `[]` | False |
| 7 | `test_is_valid_table_single_empty_row_returns_false` | `[[]]` | False |
| 8 | `test_is_valid_table_blank_rows_dont_count` | `[["",""],["",""],["a","b"]]` (前 2 行纯空白) | True (3 行非空白视为 ≥2) |

### 6.2 `tests/.../test_tables_section_filter.py` (新文件, 测 run 集成 3 case)

| # | Case | 断言 |
|---|---|---|
| 9 | `test_run_filters_degenerate_tables` | mock extractor 返混合表; 断言只 valid 进 `object_store.put_bytes` + `append_artifact` |
| 10 | `test_run_logs_warning_per_dropped` | `caplog` 断言每丢弃一条有 warning 含 `rows=N cols=N` |
| 11 | `test_run_stage_result_includes_skipped_count` | message 含 `"3 表 / 2 丢弃 / 0 跨页候选"` |

## 7. 范围与风险

- **范围**: 2 个源文件 + 2 个测试文件, 总改动 < 80 行, 单 spec 周期.
- **风险**: 极低. 唯一可观察行为变化是 (a) 某些 PDF 生成的退化 CSV 不再写入,
  (b) StageResult.message 多一段 `"N 丢弃"`. 既有正常表格识别不受影响.
- **回滚**: 单 git revert, 无 DB 迁移.

## 8. 后续 spec (不在本期)

- 调 Camelot `stream` 参数 (`row_tol`/`columns`) 减少源头假表 (数据敏感, 需跑 5+ PDF 验证).
- 删 Camelot 后端, 只留 PyMuPDF (跨 8 文件, 影响 `table_backend` API, 单独 spec).

## 9. 实施记录 (2026-07-09)

### 改动 commit

| Commit | Task | 内容 |
|---|---|---|
| `f9a41e37` | Task 1 | `TableData.is_valid_table` 静态方法 + 8 单测 (行≥2 且 列≥2, 排除整行空白) |
| `78235af9` | Task 2 | `tables_section.run()` 调过滤 + skipped_count 进 StageResult.message + 3 集成测试 |
| `45352897` | Task 3 | `TableData.filter_valid(tables, backend_name)` 抽到 base (3 个 extractor 共用), 内部 loguru |
| `68670162` | Task 4 | pymupdf/pdfplumber/camelot 3 个 extractor `extract()` 末尾调用 `filter_valid` (replaces 原内联 `is_valid_table` 循环); 4 个 test 文件加 filter 验证 + 修复 2 个旧 camelot mock 1×N → 2×2 |
| `ea5b792d` | Task 5 | 前端 stage 枚举 `load_config` → `prepare_input` 跟后端 STAGE_NAME 对齐 (4 文件, 5 行) |
| 待 commit | Task 6 | (a) chapters message 用 `_count_all` 递归总数, 跟 payload.total_chapters 对齐; (b) extract_tables message 删 M 丢弃字段 (extractor 已 filter_valid, 永远是 0 会让用户误解), 改 `N 表 / K 跨页候选` |

### 验收

- `uv run pytest tests/ingest/pre_analysis/` → **205 passed, 2 skipped** (slow/e2e)
- `uv run pyright` → **0 errors**
- `uv run ruff format` → **506 files left unchanged** (Task 4 reformat 3 test 文件)
- `uv run ruff check` → **All checks passed**
- `lint-staged` (Task 1 + 2 commit 时自动跑) → ruff + pyright + pytest --picked 全过

### 文件改动统计

- 源: `base.py` +34 / -0 行 (含 is_valid_table + filter_valid 实现), `tables_section.py` +18 / -3 行,
  `pymupdf_extractor.py` +2 / -2 行, `pdfplumber_extractor.py` +2 / -2 行, `camelot_extractor.py` +2 / -2 行
- 测试: `test_base.py` +57 行 (13 个 case), `test_tables_section_filter.py` +150 行新建 (3 个 case),
  `test_pymupdf_extractor.py` +44 行 (1 个 case), `test_pdfplumber_extractor.py` +46 行 (1 个 case),
  `test_camelot_extractor.py` +24 / -2 行 (1 个新 case + 2 个旧 mock 修)
- 总改动: ~380 行, 全部 TDD

### 行为变化 (用户可观察)

- `extract_chapters` message: `"N 章"` (顶层数) → `"N 章"` (递归总数, 含子章节, 跟 payload.total_chapters 对齐)
- `extract_tables` message: `"N 表 / M 丢弃 / K 跨页候选"` → `"N 表 / K 跨页候选"` (M 丢弃字段删除)
  - 原因: extractor 层 filter_valid 后 M 永远 = 0, 显示给用户会让 admin 误以为过滤失效
  - 退化表过滤逻辑保留作双层防御 (tables_section 兜底), logger.warning 仍打, 仅不进 message
- 1×1 / 1×N / 全空白行的退化表不再写 CSV + 不再 append_artifact
- 每条丢弃有 `logger.warning("{backend} 过滤退化表 page={} table={} rows={} cols={}", ...)`
- `_detect_cross_page` 拿到的表全是 valid (避免 col_match 比例算上 1×1 假表)
- **Task 4 后**: 退化表过滤下沉到 3 个 extractor 内部 (pymupdf/pdfplumber/camelot),
  `tables_section` 拿到 list 已经是 valid; 双重防御保留 (extractor 过滤 + tables_section 兜底), 防新 extractor 漏接 filter_valid