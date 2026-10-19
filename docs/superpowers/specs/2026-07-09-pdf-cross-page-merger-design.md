# PDF 跨页表自动合并 spec (Camelot stack_contiguous + PyMuPDF bbox + LLM 裁重复 header)

**日期**: 2026-07-09
**状态**: 设计待审 + 评审调整 (2026-07-09)

## 评审调整记录 (2026-07-09)

经代码审查, 发现 8 处与现有代码不一致, 全部已在本 spec 内联修复:

| # | 问题 | 修复 |
|---|------|------|
| 1 | `tables_section.py:112` 写死 `_doc = doc if backend == "pymupdf" else None` → camelot 后端 C2 永远拿不到 pymupdf doc 被跳过 | `tables_section.py` 改为始终传 `doc` (文件清单已加) |
| 2 | `trim_repeated_header` 写 `async def` 但 `merge()` 是 sync, 调用链全 sync, async 调不了 | 改为 sync, 用 `ChatOllama.invoke()` / `ChatOpenAI.invoke()` (异步性能要求不高, 同步链路简单) |
| 3 | 硬编码 `qwen2.5-coder:7b` 但用户 `.env.local` 配的是 `deepseek-v4-flash` (OpenAI 兼容), Ollama 只是选项 | 默认走 `src/generation/llm.py` 已有 `_llm_model()`, 支持 openai / ollama 双后端, env `LLM_TRIM_HEADER_MODEL` 显式覆盖 |
| 4 | camelot 2.0 `TableList.stack_contiguous()` API 存在性未在本机验证 (camelot 未装) | 改为自实现 `_stack_contiguous_in_flavor()`, 不依赖 camelot API, 直接对 `list[TableData]` 做列数匹配合并 |
| 5 | 文件清单漏 `tables_section.py` | 加入清单 (2 处改动: `_write_one_table` 类型 + `run()` 传 doc) |
| 6 | `_write_one_table(page_no: int)` 类型未升级 | 同步改 `int \| str` |
| 7 | `LLMUnavailableError` / `LLMParsingError` 建议放新文件 | 放 `src/core/errors.py` (已有), 与项目 error 处理一致 |
| 8 | `CrossPageMerger.merge()` 假设 `pymupdf_doc` 必传 | `pymupdf_doc is None` 时自己 `pymupdf.open(pdf_path)` 兜底 |
**触发来源**: 用户 2026-07-09 反馈 "camelot 简单表能提, 复杂表差" (测试场景: [tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf](packages/service/tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf) 西门子电机手册 710 页), 真根因是 P40-P80 跨页续表. 调研发现 camelot `stack_contiguous()` 只看列数, **不能识别 "Selection table continued" 重复 header** (issue #689 "Missing the last row when it appears on next page"), 业界共识方案是 Camelot lattice (单页) + PyMuPDF join_tables bbox 对齐 + LLM 裁 header 组合拳.

**关联**:
- 主 spec [2026-07-09-pdf-table-complex-scenarios-design.md](./2026-07-09-pdf-table-complex-scenarios-design.md) (A 默认值对齐 + B ghostscript 安装 + 中文 PDF 决策树). 本 spec 是其 C 模块拆出来的独立版, 内容跟主 spec §C 同步, 实施期**单独跑 plan**.
- 前置 plan [2026-07-08-camelot-tuning-fallback-ml.md](../plans/2026-07-08-camelot-tuning-fallback-ml.md) 已完成 R1-R5 修复 (pages='all' / flavor 白名单 / fallback 链 / ml extra).
- 配套调研报告 [2026-07-09-siemens-d81-table-extraction-research.md](../../research/2026-07-09-siemens-d81-table-extraction-research.md) (4 方向 + 21 权威源 + 决策树).
- memory 沉淀 [project-camelot-complex-table-debug-checklist.md](../memory/project-camelot-complex-table-debug-checklist.md) (7 维度根因排查表).

---

## Context

### 用户原话

> "当前 camelot 提取简单的表格没有问题, 但是提取复杂表格, 表现较差, 分析是代码的原因, 还是需要装插件, 还是配置参数的原因, 结合代码分析, 也联网搜索一下原因, 给出优化意见"

**用户场景**: 西门子电机手册 D81.1 (英文, 710 页), 跨页续表 (P40-P80 selection table) 是"复杂表差"的主要来源之一. Runner `_detect_cross_page` 启发式 ([runner.py:192-199](../../packages/service/src/ingest/pre_analysis/runner.py#L309)) **只数不合并**, 跨页表被截成 2 段 → 用户感觉 "复杂表差" (其实提出来了, 但没拼).

### 调研核心结论 (4 方向)

经代码 + memory + 联网调研 (21 源) 三方验证, 结论:

1. **Camelot `stack_contiguous()` 不够** —— 只看列数 (`match="column_count"`), **不能识别** "Selection table continued" 重复 header ([camelot issue #8 关闭 PR](https://github.com/camelot-dev/camelot/issues/628) 实现). D81.1 P40-P80 场景必丢末行 ([issue #689](https://github.com/camelot-dev/camelot/issues/689)).

2. **业界共识方案** — Camelot lattice (单页) + PyMuPDF join_tables bbox 对齐 + LLM 裁重复 header 组合拳. 调研证据:
   - **PyMuPDF** `Document.find_tables()` 跨页 (1.23.19+), 官方 [join_tables.ipynb](https://github.com/pymupdf/PyMuPDF-Utilities/tree/master/table-analysis) 是参考实现
   - **marker** `--use_llm` (Gemini 2.0 Flash) TEDS 0.816 → 0.907, 9 分提升几乎全靠 LLM 合并 + 裁 header ([marker README](https://github.com/datalab-to/marker))
   - **gmft** TATR-based, 明确**不支持多页拼接** ([gmft README](https://github.com/conjuncts/gmft))

3. **D81.1 西门子手册表类型** (P11-P15 实拍):

| 表类型 | 形态 | 跨页合并表现 |
|---|---|---|
| A 纯数据规格矩阵 | 有边框 + 多列对齐数字 | lattice 100% 提得到, 无需合并 |
| B 表头嵌色块长表 | 紫色块表头 | 跟 C 无关 (本期不动) |
| **C 跨页续表** | P40-P80 selection table 跨多页 | ❌ lattice 单页, 必丢末行 → **本期修复** |
| D 双列对照表 | 双侧并排 | false positive, 跟 C 无关 |

4. **本期不引入新依赖** —— ml flavor 已装 (PyTorch 2.12.0+cpu), PyMuPDF 已装 (>=1.27), LLM 客户端已有 (langchain-openai / langchain-ollama).

### 用户已拍的方案

**C1 + C2 一起本期实施**, 不拆 follow-up. C2 用 LLM 调一次 (裁重复 header), 加 LRU cache 缓解性能开销.

---

## 目标

把 "D81.1 跨页续表" 的 2 步修复合并成 1 个 spec, 1 期做完:

1. **C1**: 单 flavor 内 `stack_contiguous()` 基础合并, page_no 编码 `"5+6"`. 半天工作量.
2. **C2**: PyMuPDF `Document.find_tables()` bbox 启发式对齐 + LLM 判重复 header + 行拼接, 真解 D81.1 P40-P80. 2-4 天工作量.

总工作量: **3-5 天**, 1 个 spec 解决跨页续表根因.

---

## 架构

### 数据流 (C1 + C2 串联)

```
extract() 末尾
+-- C.1: camelot stack_contiguous() (单 flavor 内列数对齐合并)
|     (失败 → 跳过, log warning, 保留原 tables)
+-- C.2.1: PyMuPDF Document.find_tables() 拿 bbox 备份 (跨页, 用 Document 而非 Page)
+-- C.2.2: bbox 启发式对齐: 页号相邻 + y 坐标连续 + 列数 80% 一致 → 候选续表对
+-- C.2.3: LLM 判重复 header (LRU cache by (prev_page, curr_page, header_signature))
+-- C.2.4: 行拼接, page_no 编码 "5+6"
+-- C.2.5: 失败兜底 (LLM 失败 / bbox 对齐失败 → 用 C1 结果, log warning)
+-- 返合并后 tables
```

### C1: stack_contiguous() 基础合并

**改动 1 处**: [camelot_extractor.py:189](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L189) `extract()` 末尾

```python
def extract(self, pdf_path, *, _pymupdf_doc=None, **params) -> list[TableData]:
    # ... 现有逻辑到 result.sort(key=lambda t: (t.page_no, t.table_no)) ...

    # (2026-07-09) C1: 单 flavor 内 stack_contiguous 基础合并
    try:
        result = _stack_contiguous_in_flavor(result)
    except Exception as e:
        logger.warning("camelot stack_contiguous 失败, 保留原 tables: {}", e)

    # ... C2 在这里串 ...
    return result
```

**关键设计决策**:

1. **为什么是单 flavor 内合并, 不跨 flavor?** —— fallback 链下 4 个 flavor 各跑一遍, 跨 flavor 合并会让 2 张不同来源的表拼成 1 张, 错. 单 flavor 内合并 = 同一算法识别的 2 张相邻页表拼起来, 安全.

2. **`stack_contiguous()` 跟现有 `_detect_cross_page` 关系?** —— `_detect_cross_page` 启发式只**计数** (跨页候选数量, 写 summary), 不改 tables. `stack_contiguous()` 改 tables. **两者并存**: summary 仍有 `cross_page_candidates` 计数, 但 tables 已是合并后的.
   - **⚠️ 评审调整 #6**: `_detect_cross_page` 当前在 `tables_section.py:44` 做 `prev_page == page_no - 1` 算术, C1 合并后 `page_no` 变 str `"5+6"` 会 TypeError. 修法: `_detect_cross_page` 在 `tables_section.py` 加 `if isinstance(page_no, str): continue` 跳过已合并表 (单点修改, 不影响 spec §数据流).

3. **`stack_contiguous()` 失败兜底?** —— **评审调整 #4**: camelot 2.0 `TableList.stack_contiguous()` API 存在性未在本机验证 (camelot 未装), 自实现 `_stack_contiguous_in_flavor()` 不依赖 camelot API, 直接对 `list[TableData]` 做列数匹配合并. 套 `try/except`, 失败 fall back 到不合并, log warning, 不阻断整个 extract.

**`_stack_contiguous_in_flavor()` 自实现逻辑**:

```python
def _stack_contiguous_in_flavor(tables: list[TableData]) -> list[TableData]:
    """(2026-07-09) 单 flavor 内按列数 + 页号相邻做 stack_contiguous 合并.

    规则: 连续 2 张表, 满足 (1) curr.page_no == prev.page_no + 1
                   (2) len(curr.rows[0]) == len(prev.rows[0]) (列数严格相等)
                       且 len(prev.rows) > 0 且 len(curr.rows) > 0
          → 拼接成 1 张, page_no = f"{prev.page_no}+{curr.page_no}".
    跨 flavor 不会被合并 (extract() 每次只跑一个 flavor).
    """
    if not tables:
        return tables
    merged: list[TableData] = []
    for curr in tables:
        if not merged:
            merged.append(curr)
            continue
        prev = merged[-1]
        if (
            isinstance(prev.page_no, int)
            and isinstance(curr.page_no, int)
            and curr.page_no == prev.page_no + 1
            and prev.rows
            and curr.rows
            and len(prev.rows[0]) == len(curr.rows[0])
        ):
            new_page_no: int | str = f"{prev.page_no}+{curr.page_no}"
            merged[-1] = TableData(
                page_no=new_page_no,
                table_no=prev.table_no,
                rows=prev.rows + curr.rows,
            )
        else:
            merged.append(curr)
    return merged
```

### C2: PyMuPDF bbox + LLM 裁重复 header

**新增 1 个 class + 1 个 helper**:

| 类/函数 | 文件 | 作用 |
|---|---|---|
| `CrossPageMerger` | `camelot_extractor.py` | 跨页续表合并器, 接受 PyMuPDF `Document` + camelot 单页 tables, 返合并后 tables |
| `CrossPageMergerConfig` (dataclass) | `camelot_extractor.py` | 配置: `llm_model`, `cache_enabled=True` |
| `trim_repeated_header()` | `src/core/llm_helper.py` (新) | LLM 调一次判下 1 页表头是不是上 1 页重复, 返 `(is_repeated, rows_to_skip)`. **同步** (评审调整 #2, 因为调用链全 sync) |
| `LLMUnavailableError` / `LLMParsingError` | `src/core/errors.py` (已有, 评审调整 #7) | 错误类, 跟项目现有 error 处理一致 |

**改动 6 处** (评审调整 #5 #6 补入 tables_section.py):

| 改动点 | 内容 |
|---|---|
| 新增 `CrossPageMerger` class | [camelot_extractor.py](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py) 加 class, 100-150 行 |
| 新增 `src/core/llm_helper.py` | `trim_repeated_header(prev_rows, curr_rows, llm_model)` **sync** 函数, 50 行 |
| 改 `extract()` 末尾 | 在 C1 stack_contiguous 之后, 调 `CrossPageMerger.merge()` |
| 改 [base.py](../../packages/service/src/ingest/pre_analysis/table_extractors/base.py) `TableData` | `page_no: int` → `int \| str` (字符串 `"5+6"`) |
| **改 [tables_section.py](../../packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py)** | **评审调整 #5 #6**: `_write_one_table(page_no: int)` → `int \| str`; `run()` 始终传 `doc` 给 extractor (评审调整 #1); `_detect_cross_page` 加 `isinstance(page_no, str)` 跳过守卫 |
| 改 [src/core/errors.py](../../packages/service/src/core/errors.py) | 加 `LLMUnavailableError`, `LLMParsingError` 2 个类 |

#### C.2.1 PyMuPDF Page.find_tables() 拿 bbox

```python
# 用 PyMuPDF Page.find_tables() (1.18.0+, 项目 1.27.2.3 稳), 逐页拿 bbox
# ⚠️ PyMuPDF 没有 Document.find_tables(), 只有 Page.find_tables(), 逐页遍历收集
tables_with_bbox: list[tuple[int, tuple[float, float, float, float]]] = []
for page_idx in range(pymupdf_doc.page_count):
    page = pymupdf_doc.load_page(page_idx)
    for t in page.find_tables(strategy="lines"):  # 用线条策略, 跟 camelot lattice 对齐
        tables_with_bbox.append((page_idx + 1, tuple(t.bbox)))  # 1-based 页码, (x0, y0, x1, y1)
```

**关键设计决策**:

- **评审调整**: 用 `Page.find_tables()` (PyMuPDF 官方稳定 API), 逐页遍历. spec 原稿写 `Document.find_tables()` 不存在 (PyMuPDF 无此 API)
- `strategy="lines"` 而非默认 `strategy="lines_strict"`: 跟 camelot lattice 检测方式对齐, bbox 启发式一致性更好
- 不复用 PyMuPDF 检测的 cell 内容, 只用 bbox: cell 内容仍走 camelot lattice (D81.1 纯数据表 100% 提得到)
- 页码转换: PyMuPDF `page_idx` 是 0-based, camelot `page` 是 1-based, 转 `page_idx + 1` 对齐

#### C.2.2 bbox 启发式对齐

```python
def _align_consecutive_pages(
    tables: list[TableData],
    pymupdf_tables: list,  # PyMuPDF Document.find_tables() 返
) -> list[tuple[int, int]]:
    """返 [(prev_table_idx, curr_table_idx), ...] 候选续表对."""
    # 启发式:
    # - 页号相邻 (curr.page_no == prev.page_no + 1)
    # - y 坐标连续 (curr.bbox.y0 - prev.bbox.y1 < 20 像素, 表示续表接在下面)
    # - 列数差异 ≤ 20% (col_match 类似 runner `_detect_cross_page` 的 min_column_match)
    # - prev table_no == N (最后一张) AND curr table_no == 1 (首页第一张)
```

#### C.2.3 LLM 判重复 header

```python
# src/core/llm_helper.py (评审调整 #2 改为 sync)
def trim_repeated_header(
    prev_rows: list[list[str]],
    curr_rows: list[list[str]],
    llm_model: str | None = None,
) -> tuple[bool, int]:
    """调 LLM 判 curr 表头是不是 prev 表头重复 (sync).

    Args:
        prev_rows: 上 1 页表的全部 rows (含表头)
        curr_rows: 下 1 页表的全部 rows (含表头)
        llm_model: LLM 模型名. None → 走 src/generation/llm.py 默认 (env LLM_MODEL)

    Returns:
        (is_repeated, rows_to_skip) — is_repeated=True 时返需跳过的行数

    Raises:
        LLMUnavailableError: LLM 客户端不可用
        LLMParsingError: LLM 返 invalid JSON
    """
```

**LLM prompt 模板**:

```python
PROMPT = """你是一个 PDF 表格分析助手. 下面是两张相邻页的表格片段, 判断下表 (current) 的表头是不是上表 (previous) 的表头重复.

Previous 表头 (含):
{prev_rows}

Current 表头 (前 5 行):
{curr_rows[:5]}

如果 Current 表头是 Previous 表头的重复 (只是因为跨页拆开), 告诉我 "is_repeated=true" 并指出需跳过的行数.
如果 Current 表头是新的 (例如 "Selection table continued" 标识行 + 真表头), 告诉我 "is_repeated=false".

严格按 JSON 格式返:
{{"is_repeated": true/false, "rows_to_skip": N}}

不要解释. 只返 JSON."""
```

**关键设计决策**:

1. **LLM 模型选择 (评审调整 #3)**: 不硬编码 `qwen2.5-coder:7b`. 复用 `src/generation/llm.py` 已有 `_llm_model()` (env `LLM_MODEL`, 默认 `gpt-4o-mini` / `llama3`), 支持 OpenAI 兼容 / Ollama 双后端. env `LLM_TRIM_HEADER_MODEL` 显式覆盖. 不让用户额外装 Ollama 模型.

2. **LRU cache** (key = `(prev_page, curr_page, prev_header_signature, curr_header_signature)`):
   - 用 `functools.lru_cache(maxsize=128)` 进程内缓存 (评审调整 #2 sync 函数, lru_cache 可用)
   - `header_signature` = `sha256("\n".join(rows[:3]))[:16]` (前 3 行作签名)
   - 跨进程不共享 (后续可换 Redis, 项目已有 redis_client, 但本期不接)

3. **失败兜底**: LLM 调用失败 (网络 / 超时 / 解析错 / 客户端不可用) → 抛 `LLMUnavailableError` 或 `LLMParsingError`, `CrossPageMerger.merge()` 外层 try/except 接住 → 返 base_tables 不变 + log warning, 不阻断 extract. `llm_model=None` 且客户端不可用 → 优雅降级跳过 C2.

4. **LLM 误判风险**: mock test 覆盖 `is_repeated=True/False` 两种结果; e2e 抽样验证合并结果正确性 (人工 review D81.1 几张跨页表).

#### C.2.4 行拼接

```python
def _merge_consecutive_pair(
    prev: TableData, curr: TableData, rows_to_skip: int
) -> TableData:
    """拼接 prev + curr 表, 保留 prev 表头 + curr body (跳过 rows_to_skip 行)."""
    merged_rows = list(prev.rows) + list(curr.rows[rows_to_skip:])
    return TableData(
        page_no=f"{prev.page_no}+{curr.page_no}",  # 字符串 "5+6"
        table_no=prev.table_no,                    # 沿用 prev 的 table_no
        rows=merged_rows,
    )
```

#### C.2.5 失败兜底策略

```python
try:
    merger = CrossPageMerger()
    result = merger.merge(pdf_path, pymupdf_doc, c1_result)
except Exception as e:
    logger.warning("cross_page_merge 失败, 保留 C1 结果: {}", e)
    result = c1_result
```

### fallback 链 + 跨页合并协同

`extract_with_fallback` 内部每个 flavor 跑一轮, 各自过自己的 `extract()`. C1+C2 在每个 flavor 末尾执行, 单 flavor 内正确, 不影响 fallback 链逻辑. fallback 命中后, 返的是合并后的 tables.

### `TableData.page_no` 类型升级

| 场景 | page_no 值 |
|---|---|
| 单页表 | `int` (例 `5`) |
| 跨页合并表 | `str` (例 `"5+6"` 或 `"10+11+12"`) |
| 业务侧判断 | `isinstance(t.page_no, str) and "+" in t.page_no` |

**下游消费方**:
- runner `_write_one_table` 用 `page_no` 拼 URI: `f"page-{page_no}-table-{table_no}.csv"` → 字符串 `"5+6"` 拼出 `"page-5+6-table-1.csv"`, 可读, 不用改
- 前端展示: page_no 是 string 时显示 "5-6" (用 `+` 切分)
- LLM 增强: 现有契约不变 (rows 是 list of list), 加 1 个 metadata 字段 `cross_page: bool` (后续增强 v2 用, 本期不实现)

---

## API 定义

### 新增 `CrossPageMerger` class

```python
@dataclass(frozen=True)
class CrossPageMergerConfig:
    """(2026-07-09) 跨页合并器配置.

    Attributes:
        llm_model: LLM 模型名. None → 走 src/generation/llm.py 默认 (env LLM_MODEL); 不可用时优雅降级
        cache_enabled: LLM 判 header 是否重复的 LRU cache 开关
        min_column_match: bbox 对齐时列数匹配度阈值 (类似 runner _detect_cross_page)
        max_vertical_gap_px: bbox 对齐时上下页 y 坐标连续性阈值 (像素)
    """
    llm_model: str | None = None  # (2026-07-09 评审调整 #3) None = 走 env 默认, 不硬编码
    cache_enabled: bool = True
    min_column_match: float = 0.8
    max_vertical_gap_px: int = 20


class CrossPageMerger:
    """(2026-07-09) 跨页续表合并器.

    数据流 (见架构 §数据流):
    1. PyMuPDF Page.find_tables() 逐页拿 bbox (评审调整: PyMuPDF 无 Document.find_tables)
    2. bbox 启发式对齐 → 候选续表对
    3. LLM 判重复 header (LRU cache)
    4. 行拼接, page_no 编码 "5+6"
    5. 失败兜底 (LLM 失败 / bbox 对齐失败 → 返原 tables + log warning)
    """

    def __init__(self, config: CrossPageMergerConfig | None = None) -> None: ...

    def merge(
        self,
        pdf_path: str,
        pymupdf_doc: pymupdf.Document | None = None,  # 评审调整 #8: None 时自己开
        base_tables: list[TableData] | None = None,    # C1 stack_contiguous 后结果
    ) -> list[TableData]:
        """合并跨页表. 失败时返 base_tables 不变 + log warning."""
```

### 新增 `src/core/llm_helper.py` `trim_repeated_header`

```python
# (2026-07-09 评审调整 #2) 改为 sync, 因为调用链全 sync
def trim_repeated_header(
    prev_rows: list[list[str]],
    curr_rows: list[list[str]],
    llm_model: str | None = None,  # (评审调整 #3) None → 走 src/generation/llm.py 默认
) -> tuple[bool, int]:
    """调 LLM 判下 1 页表头是不是上 1 页重复 (sync).

    Args:
        prev_rows: 上 1 页表的全部 rows (含表头)
        curr_rows: 下 1 页表的全部 rows (含表头)
        llm_model: LLM 模型名, None → 走 src/generation/llm.py 已有 env

    Returns:
        (is_repeated, rows_to_skip) — is_repeated=True 时返需跳过的行数

    Raises:
        LLMUnavailableError: LLM 客户端不可用
        LLMParsingError: LLM 返 invalid JSON
    """
```

### 改 `extract()` 末尾

```python
def extract(self, pdf_path, *, _pymupdf_doc=None, **params) -> list[TableData]:
    # ... 现有逻辑到 result.sort(key=lambda t: (t.page_no, t.table_no)) ...

    # (2026-07-09) C1: 单 flavor 内 stack_contiguous 基础合并
    try:
        result = _stack_contiguous_in_flavor(result)
    except Exception as e:
        logger.warning("camelot stack_contiguous 失败, 保留原 tables: {}", e)

    # (2026-07-09) C2: PyMuPDF bbox + LLM 裁重复 header (真解 D81.1 跨页续表)
    # _pymupdf_doc 可能为 None (camelot 后端, 见 tables_section 评审调整 #1)
    try:
        merger = CrossPageMerger()
        result = merger.merge(pdf_path, _pymupdf_doc, result)
    except Exception as e:
        logger.warning("cross_page_merge 失败, 保留 C1 结果: {}", e)

    return result
```

### 改 `TableData.page_no` 类型

```python
# packages/service/src/ingest/pre_analysis/table_extractors/base.py
@dataclass(frozen=True)
class TableData:
    page_no: int | str  # (2026-07-09) 改: 跨页合并后字符串 "5+6"
    table_no: int
    rows: list[list[str]]
```

### 改 `tables_section.py` (评审调整 #1 #5 #6)

```python
# _detect_cross_page: 跳过已合并表 (str page_no)
def _detect_cross_page(
    tables: list[tuple[int | str, int, list[list[str]]]],  # 评审调整 #6: page_no 可 str
    config: dict,
) -> int:
    # ...
    for page_no, table_no, rows in tables:
        # (2026-07-09 评审调整) 跳过已合并跨页表
        if isinstance(page_no, str):
            continue
        # ... 现有逻辑

# _write_one_table: page_no 类型升级
def _write_one_table(
    object_store,
    prefix: str,
    page_no: int | str,  # 评审调整 #6: int | str
    table_no: int,
    rows: list[list[str]],
    task_id: str,
) -> None:
    uri = f"{prefix}/tables/page-{page_no}-table-{table_no}.csv"
    # ... 不变

# run(): 始终传 doc 给所有后端 (评审调整 #1)
def run(ctx, table_extraction_config=None):
    # ...
    extractor = get_table_extractor(backend, params)
    # (2026-07-09 评审调整 #1) 所有后端都传 doc, camelot C2 需要 PyMuPDF bbox
    raw_tables = extractor.extract(
        doc.name or "",
        _pymupdf_doc=doc,  # 原来是 _doc = doc if backend == "pymupdf" else None
    )
    # ...
```

---

## 数据结构变更

### `TableData.page_no` 升级 `int` → `int | str`

| 场景 | page_no 值 |
|---|---|
| 单页表 | `int` (例 `5`) |
| 跨页合并表 | `str` (例 `"5+6"` 或 `"10+11+12"`) |

**下游消费方**:
- runner `_write_one_table` URI 拼: `f"page-{page_no}-table-{table_no}.csv"` → `"page-5+6-table-1.csv"`, 可读
- 前端展示: `t.page_no.split("+")` 显示 `"5-6"`
- LLM 增强: 现有契约不变 (rows 是 list of list), 加 metadata `cross_page: bool` (后续 v2 用, 本期不实现)

### LLM cache key 格式

```python
# (prev_page, curr_page, prev_header_signature, curr_header_signature)
# header_signature = sha256("\n".join(rows[:3]))[:16]
# functools.lru_cache(maxsize=128), 跨进程不共享
```

---

## 测试

### 新增 `test_camelot_stack_contiguous.py` (C1 部分, 3 mock test)

- mock test: 2 张相邻页表 → stack_contiguous 后变 1 张, page_no="1+2"
- mock test: 2 张非相邻页表 → 不合并
- mock test: stack_contiguous 抛异常 → 不阻断, log warning

### 新增 `test_cross_page_merger.py` (C2 部分, 6 mock + 1 e2e = 7 total)

- mock test: bbox 启发式对齐 (页号相邻 + y 连续 + 列数 80% 一致) → 候选续表对
- mock test: bbox 不对齐 (列数差异 > 80%) → 不合并
- mock test: LLM 判 "is_repeated=True" → 裁掉 curr header, 拼接 prev rows + curr body
- mock test: LLM 判 "is_repeated=False" → 不合并
- mock test: LLM 调用失败 (mock 抛 timeout) → 兜底用 stack_contiguous 结果, log warning
- mock test: LLM cache 命中 → 第二次不调 LLM
- e2e (skipif LLM 不可用): D81.1 fixture 跑真实 extract, 看跨页续表是否合并 (page_no="40+41" 之类)

### 新增 `test_llm_helper.py` (LLM helper, 2 mock test)

- mock test: trim_repeated_header 调 LLM 返 "is_repeated=True, skip=2"
- mock test: LLM 返 invalid JSON → 抛 LLMParsingError, 上层兜底

---

## 风险 & 缓解

| 风险 | 缓解 |
|---|---|
| `TableData.page_no` 从 int 改成 int\|str, pyright 报 | `from __future__ import annotations` + pyright basic 模式不严格, 业务侧 narrow |
| `stack_contiguous()` 对列数差异过大抛异常 | try/except 兜底, log warning, 不合并继续返原 tables |
| LLM 调一次 ~1-3s 慢, 跨页续表多时总时长增加 | 加 LRU cache (by `(prev_page, curr_page, header_signature)`), 重复跨页表只调一次 |
| LLM 误判 (把真表头当重复裁掉) | mock test 覆盖 LLM 返 "is_repeated=False" 场景; e2e 抽样验证合并结果正确性 |
| LLM 客户端不可用 (没装 ollama, openai key 没配) | CrossPageMerger 构造时探测, 不可用时 `cache_enabled=True, llm_model=None` → 跳过 C2 用 C1 结果 + log info (优雅降级) |
| 跨页合并后 LLM 增强阶段看到 1 张大表, 上下文 token 翻倍 | LLM 增强 v2 spec 已规划处理长上下文, 本 spec 不动 |
| runner `_detect_cross_page` 启发式跟 C1/C2 结果不一致 (一边说 5 跨页, 一边合并出 3 张) | 2 者并存, summary cross_page_candidates 是"启发式认为的候选数" (高估值), tables 是"实际合并后" (低估值), 加注释说明 |
| 跨页合并的 table_no 编码冲突 (page_no="5+6" 但 table_no=1, 后续页再来一张 page_no=5 table_no=1 重名) | URI 用 `f"page-{page_no}-table-{table_no}.csv"`, 字符串 `5+6` 已避重; 业务侧加 de-dup |
| C2 用 LLM 调外部服务, 真 PDF e2e 测试可能因 LLM 不可用 skip | `@pytest.mark.skipif(not _has_llm_client())` guard, 跟 [feedback-tdd-test-real-behavior-not-just-no-crash](../memory/feedback-tdd-test-real-behavior-not-just-no-crash.md) 不冲突 (mock 测路径真覆盖) |
| PyMuPDF Document.find_tables() 在加密 PDF / 扫描件上失败 | try/except 兜底, 失败跳 C2 用 C1 结果 + log warning |
| LLM 调本地 ollama 慢 (10-30s/次 CPU) | LRU cache 缓解 + 默认配置 7B 模型 (不大), 真跑测试不阻塞 (mock 测覆盖, e2e 跑真 LLM 时 expect 慢) |

---

## 文件清单

**改动**:

| 文件 | 改动 |
|---|---|
| [packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py](../../packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py) | `extract()` 末尾加 C1 (stack_contiguous) + C2 (CrossPageMerger), try/except 兜底; 新增 `CrossPageMerger` class + `CrossPageMergerConfig` dataclass + `_stack_contiguous_in_flavor` helper (~200 行) |
| 新增 [packages/service/src/core/llm_helper.py](../../packages/service/src/core/llm_helper.py) | `trim_repeated_header` **sync** 函数 (~80 行) + LRU cache by (prev_page, curr_page, header_sig) |
| [packages/service/src/core/errors.py](../../packages/service/src/core/errors.py) | 加 `LLMUnavailableError`, `LLMParsingError` 2 个 Exception 类 (评审调整 #7, 放已有 errors.py 不新建) |
| [packages/service/src/ingest/pre_analysis/table_extractors/base.py](../../packages/service/src/ingest/pre_analysis/table_extractors/base.py) | `TableData.page_no: int` → `int \| str` |
| **新增** [packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py](../../packages/service/src/ingest/pre_analysis/table_extractors/tables_section.py) **(评审调整 #1 #5 #6)** | `_write_one_table(page_no: int)` → `int \| str`; `run()` 始终传 `doc` 给 extractor (camelot C2 需要); `_detect_cross_page` 加 `isinstance(page_no, str) → continue` 守卫 |
| 新增 [packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_stack_contiguous.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_stack_contiguous.py) | C1 3 个 mock test |
| 新增 [packages/service/tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py](../../packages/service/tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py) | C2 6 个 mock test + 1 个 e2e |
| 新增 [packages/service/tests/core/test_llm_helper.py](../../packages/service/tests/core/test_llm_helper.py) | LLM helper 2 个 mock test |

**不改**:

- [runner.py](../../packages/service/src/ingest/pre_analysis/runner.py) `runner._detect_cross_page` thin wrapper **保留** (调 tables_section 实现)
- 其他表格提取后端 (pymupdf / pdfplumber) 不动
- BFF / router / API contract 不动

---

## 执行顺序

1. **C1 先做** (半天) — stack_contiguous 基础合并, 写 3 个 mock test + 1 个 D81.1 e2e
2. **C2 接着做** (2-3 天) — PyMuPDF bbox 对齐 + LLM helper + CrossPageMerger, 写 6+2 个 mock test + 1 个 e2e
3. **集成验收** (半天) — 跑全套测试, 验证 baseline 33 PASS + 12 新 PASS = 45 PASS, 0 新 fail

总工作量: **3-5 天**

---

## 验收 (End-to-End)

### C1 验收

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_stack_contiguous.py -v
```

Expected: 3 个 mock test 全绿.

### C2 验收

```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py tests/core/test_llm_helper.py -v
```

Expected: 6+2=8 个 mock test 全绿; D81.1 e2e skip if LLM 不可用 (mock 全绿即可验收).

### 集成验收

```bash
cd packages/service && uv run pytest -q  # 全套
```

Expected: 跟 baseline (33 passed in 317s) 比 +12 个新 PASS (C1: 3 + C2: 7 + LLM helper: 2), 0 新 fail.

### 真 PDF 端到端 (D81.1)

```bash
cd packages/service && uv run python -c "
from src.ingest.pre_analysis.table_extractors.camelot_extractor import CamelotTableExtractor
tables = CamelotTableExtractor.extract_with_fallback(
    'tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf',
    flavor='lattice',
)
print(f'找到 {len(tables)} 张表 (含跨页合并)')
merged = [t for t in tables if isinstance(t.page_no, str) and '+' in t.page_no]
print(f'跨页合并后: {len(merged)} 张 (page_no 示例: {merged[:3] if merged else \"无\"})')
"
```

Expected: 跨页合并后表数 > baseline (具体数看实际 D81.1); page_no 字符串示例 `"40+41"`.

---

## Out of Scope (本期不实施)

- ❌ **B 类色块表头的真正解** (西门子紫/蓝块) —— 跟本 spec 无关, 留后续 (主 spec §Out of Scope)
- ❌ 旋转表自动 deskew —— 留给后续 spec
- ❌ 合并单元格 `copy_text=['h','v']` 默认开 —— admin 调参解决, 不暴露 UI
- ❌ LLM cache 跨进程共享 (Redis) —— 本期用 lru_cache 进程内, 后续接 Redis
- ❌ LLM 增强 v2 (合并后表的上下文处理) —— 留后续 spec
- ❌ ml flavor 兜底色块表头 —— PyTorch CPU 慢 ~30s/页, 留后续 spec

---

## 附录: 联网调研 21 个权威源

### 官方源

- [camelot-py pypi 页面](https://pypi.org/project/camelot-py/) — v2.0.0 release info
- [camelot-py README](https://github.com/camelot-dev/camelot/blob/master/README.md) — stack_contiguous 推荐
- [camelot-py docs comparison.rst](https://raw.githubusercontent.com/camelot-dev/camelot/master/docs/user/comparison.rst)
- [camelot-dev/camelot issue #628](https://github.com/camelot-dev/camelot/issues/628) — stack_contiguous 跨页 (本期 C1 用)
- [camelot-dev/camelot issue #689](https://github.com/camelot-dev/camelot/issues/689) — **Missing the last row when it appears on next page** (D81.1 真痛点)
- [PyMuPDF Page.find_tables](https://pymupdf.readthedocs.io/en/latest/page.html) — 1.23.19+ `add_lines`
- [PyMuPDF join_tables.ipynb](https://github.com/pymupdf/PyMuPDF-Utilities/tree/master/table-analysis) — 官方跨页拼接笔记本 (本期 C2 参考)

### D81.1 类表格实战

- [marker GitHub README (TEDS 0.816/0.907 FinTabNet)](https://github.com/datalab-to/marker) — LLM 模式 +9 分
- [gmft GitHub README](https://github.com/conjuncts/gmft) — 明确不支持多页拼接

### 学术 / 训练集

- [PubTables-1M arXiv:2110.00061](https://www.microsoft.com/en-us/research/publication/pubtables-1m/) — TATR 训练集
- [Docling Technical Report arXiv:2408.09869v5](https://arxiv.org/abs/2408.09869) — IBM TableFormer
- [PdfTable arXiv:2409.05125](https://arxiv.org/html/2409.05125v1) — 武汉理工 2024-09 跨页测评
- [CED: Catalog Extraction from Documents arXiv:2304.14662](https://arxiv.org/abs/2304.14662)

---

**Why this spec**: 用户 2026-07-09 报 "复杂表差" (D81.1 跨页续表场景) 不能单靠 camelot stack_contiguous (只对齐列数, 不识别重复 header). 经调研, 业界共识方案是 Camelot lattice + PyMuPDF bbox + LLM 裁 header 组合拳. 本 spec 把 C1+C2 一起做, 3-5 天工作量真解 D81.1 P40-P80.
**How to apply**: C1 先 (半天) → C2 后 (2-3 天). 评审后写 plan (task-by-task), 实施期严格 TDD, C2 用 LLM 需真测真调, LLM 不可用时 mock test 全绿即可验收, e2e skip.