# PDF 章节树状化 + LLM 增强 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按照 spec [2026-07-09-pdf-chapter-tree-llm-design.md](../specs/2026-07-09-pdf-chapter-tree-llm-design.md) 实现 PDF 章节树状化 + LLM 增强功能. 后端新增 `build_chapter_tree` 算法、多层 fallback、LLM 摘要, 前端加 2 个上传 dialog 控件.

**Architecture:** 增量改造现有 chapter_extractors/ 模块:
- 新增 `chapter_tree.py`: `build_chapter_tree` (page_end 推导 + 嵌套) + `cluster_by_font_size` + `detect_toc_pages` + `parse_toc_pages`
- 新增 `llm_chapter.py`: `llm_refine_chapters` + `llm_summarize_chapters`
- 新增 `chapter_config.py`: `ChapterExtractionConfig` dataclass + `from_form()`
- 新增 `llm_schemas.py`: Pydantic 输出 schema
- 改 `chapters_section.py`: 集成新算法, 改 payload shape (树状, 按 max_level 截断)
- 改 `runner.py`: 传 chapter_config 进 stage 2
- 改 `router.py`: 加 `chapter_config_json` form 字段
- 前端改 `pre-analysis-upload-dialog.tsx`: 加 2 控件 + payload 拼装

**Tech Stack:** Python 3.14 / pymupdf / langchain-core / langchain-openai / langchain-ollama / Pydantic v2 / React 19 / shadcn (AppSelect/AppToggle) / vitest

**测试隔离:** 全部 mode 1 (mock), 0 PG/Redis 依赖. mock pymupdf.Document / mock OpenAILLM / mock LocalLLM.

**工作目录:** `/home/deyuan/rag/rag`, 后端在 `packages/service/` (`uv run` 需在该目录执行).

---

## Global Constraints

- 后端工具链顺序不可颠倒: `uv run ruff format` → `uv run ruff check --fix` → `uv run pyright`（0 error）→ `uv run pytest`（0 新 fail）
- 测试走模式 1 (mock), 0 PG/Redis 依赖
- 代码注释用中文; 不删除已有注释
- 每个函数 ≤ 100 行 (CLAUDE.md §代码长度)
- commit message 前缀: `feat:` / `refactor:` / `test:`
- **不做 M6** (详情页 UI 树状渲染留后续 spec)
- 前端 `pre-analysis-upload-dialog.tsx` 超 500 行但本期不拆 (agent review HIGH 9 决策, 留后续 spec 整改)
- 不引新 LLM 依赖 (复用 `langchain-openai`, `langchain-ollama`, 项目已有)
- 不修改现有 5 stage pipeline 名字
- 后端现有 test_runner.py 的集成测试 (用真 d81_dummy.pdf) 不改 — 它们 mock ObjectStore, 跑真 PDF 验证 pipeline 完整性, 不关心 chapter_structure.json 内部形状
- 现有 test_chapter_extractors.py 的 OutlineExtractor 测试不改 — 新增 `test_chapter_extractors_v2.py` 测试文件覆盖新功能

## 关键代码引用

- **runner.py**: `run(task_id, pdf_uri, table_extraction_config)` line 83-188 — 5 stage pipeline, stage 2 调 `chapters_section.run(ctx)`
- **chapters_section.py**: `run(ctx)` line 37-68 — stage 2 runner, 调 `extract_chapters(doc)`, 写 `chapter_structure.json`
- **outline.py**: `OutlineExtractor.extract(doc)` line 20-24 — 调 `doc.get_toc()`, 返 `{level, title, page_start, page_end}`
- **__init__.py**: `extract_chapters(doc, strategy="outline")` line 30-43 — 顶层入口
- **router.py**: `upload_pre_analysis()` line 66-124 — form: `file` + `table_backend` + `table_params`
- **router.py**: `retry_pre_analysis_task()` line 309-347 — 读 `task.task_config_json` 保留原始配置
- **runner.py**: `_run_pre_analysis(task_id, table_config)` line 353-381 — background 调度
- **finalize_output.py**: `run(ctx, table_extraction_config)` line 28-121 — `task_store.mark_completed` 写 `task_config`
- **pre-analysis-upload-dialog.tsx**: `useUploadState()` line 166-198 — 6 个 state; `handleUpload()` line 244-254 — 拼 config
- **pre-analysis.ts**: `preAnalysisUpload(file, config)` line 165-182 — FormData 拼 `table_backend` + `table_params`
- **generation/llm.py**: `OpenAILLM` line 43-88, `LocalLLM` line 91-108 — 现有 LLM 封装

---

## 后端目录布局 (增量)

```
packages/service/
├── src/ingest/pre_analysis/
│   ├── chapter_extractors/
│   │   ├── __init__.py                          # [改] extract_chapters 加 max_level 参数, 串联 fallback
│   │   ├── base.py                              # [改] ChapterExtractor.extract 加 max_level
│   │   ├── outline.py                           # [改] extract 调 build_chapter_tree, 返嵌套树
│   │   ├── chapter_tree.py                      # [新] build_chapter_tree + cluster_by_font_size + detect/parse toc
│   │   ├── llm_chapter.py                       # [新] llm_refine_chapters + llm_summarize_chapters
│   │   ├── chapter_config.py                    # [新] ChapterExtractionConfig dataclass
│   │   └── llm_schemas.py                       # [新] Pydantic schema
│   ├── chapters_section.py                      # [改] run() 接 chapter_config, payload 树状
│   ├── runner.py                                # [改] run() 传 chapter_config 进 stage 2
│   └── router.py                                # [改] upload + retry 传 chapter_config_json
└── tests/ingest/pre_analysis/
    ├── test_chapter_tree.py                     # [新] build_chapter_tree + fallback 单测
    ├── test_llm_chapter.py                      # [新] llm_refine / llm_summarize 单测
    ├── test_chapter_config.py                   # [新] ChapterExtractionConfig 单测
    ├── test_llm_schemas.py                      # [新] Pydantic schema 单测
    ├── test_chapter_extractors_v2.py            # [新] extract_chapters(..., max_level) 测试
    ├── test_chapters_section.py                 # [改] 加 chapter_config 路径测试
    └── test_router.py                           # [改] 加 chapter_config_json form 校验
```

## 前端目录布局 (增量)

```
packages/web/
├── app/[locale]/admin/pre-analysis/_components/
│   ├── pre-analysis-upload-dialog.tsx             # [改] 高级选项区加 2 控件
│   └── pre-analysis-upload-dialog.test.tsx        # [改] 新增 2 控件 test case
├── lib/api/
│   ├── pre-analysis.ts                            # [改] 新增 chapter config 类型 + form 字段
│   └── pre-analysis.test.ts                       # [改] 新增 chapter config 测试
└── messages/
    ├── zh.json                                    # [改] 加 2 控件 i18n 文案
    └── en.json
```

---

## 实施步骤 (7 Milestone / 7 PR / ~1600 行估算)

### M1a: `chapter_tree.py` — build_chapter_tree + page_end 推导

**估算 250 行 / 2 commits**

**文件:**
- Create: `packages/service/src/ingest/pre_analysis/chapter_extractors/chapter_tree.py`
- Create: `packages/service/tests/ingest/pre_analysis/test_chapter_tree.py`

**核心算法 (`chapter_tree.py`):**

```python
def build_chapter_tree(
    raw_toc: list[tuple[int, str, int]],  # [(level, title, page_start)]
    total_pages: int,
    max_level: int = 6,
) -> list[dict]:
    """从 PyMuPDF doc.get_toc() 平铺 list 转嵌套树, page_end 推导.

    单调栈算法:
    1. 遍历每个 (level, title, page_start), level > max_level 跳过
    2. 当 stack 顶层 level >= 当前 level, pop 回父级
    3. 当前节点入栈, children 字段
    4. 后序遍历推导 page_end (enumerate O(N))
    """
```

- 后序遍历 page_end 推导: 末节点 = total_pages, 非末节点 = 下一同级/上级 page_start - 1
- 返回 dict list: `{id, level, title, page_start, page_end, children: [...]}`
- 验证 fixture: 用假的 (level, title, page_start) 列表, 不依赖真 PDF

**测试 (`test_chapter_tree.py`, mode 1 mock):**
- 空 toc → []
- 单节点 → [{id, level, title, page_start, page_end=total_pages, children: []}]
- 多层级嵌套 (L1-L2-L3) → 验证树结构 + page_end 推导
- max_level 截断: level > max_level 跳过
- D81.1 真值对照: 模拟 382 条 toc 输入, 验证 max_level=3 时输出 75 节点

**验证:** `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_chapter_tree.py -v`

**Commits:**
1. `feat(chapter_tree): build_chapter_tree 算法 + page_end 推导`
2. `test(chapter_tree): 嵌套/截断/边界 case`

---

### M1b: `chapter_tree.py` — 字体聚类 + 视觉目录页 fallback

**估算 200 行 / 2 commits**

**文件:**
- Modify: `chapter_tree.py` [改] 加 `cluster_by_font_size`, `detect_toc_pages`, `parse_toc_pages`

**新增函数:**
- `cluster_by_font_size(doc, max_pages=30) → list[(level, title, page_start)]`: 字体聚类 fallback
  - `_candidate_spans` 生成器过滤 (size 10-30, y0 < 70% 页高, 排除 Italic)
  - Counter 取 Top-3 size, 第二轮过滤, 排除纯数字短文本
- `detect_toc_pages(doc, max_scan=20) → list[int]`: 扫前 20 页找 "Contents/目录" + dotted-leader ≥ 5
- `parse_toc_pages(doc, page_indices) → list[(level, title, page_start)]`: 解析 dotted-leader 行 + 缩进层级

**测试 (`test_chapter_tree.py` 追加, mode 1 mock):**
- mock doc.get_text("dict") 返回含不同字号 span
- mock doc[page_idx].get_text() 返回含/不含 "Contents" 文本
- mock dotted-leader 文本 fixture
- 边界: 无命中 / 单行命中 / 多行 / 编号层级推断

**验证:** `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_chapter_tree.py::test_detect_and_parse -v`

**Commits:**
1. `feat(chapter_tree): cluster_by_font_size + detect/parse toc pages`
2. `test(chapter_tree): fallback 路径边界测试`

---

### M2: `chapter_config.py` + `llm_schemas.py` + `chapters_section.py` 改造

**估算 250 行 / 2 commits**

**文件:**
- Create: `chapter_config.py` (ChapterExtractionConfig dataclass + from_form)
- Create: `llm_schemas.py` (ChapterEntry, LLMChapterOutput, SummaryItem, SummaryOutput)
- Create: `test_chapter_config.py`
- Create: `test_llm_schemas.py`
- Modify: `chapters_section.py` [改] run() 接 chapter_config, payload 树状
- Modify: `test_chapters_section.py` [改] 加 chapter_config 路径测试

**chapter_config.py:**
```python
@dataclass(frozen=True)
class ChapterExtractionConfig:
    enable_llm_refinement: bool = False
    llm_provider: Literal["openai", "ollama"] = "openai"
    chapter_max_level_for_display: int = 3
    llm_summary_max_level: int = 3
    llm_summary_per_chapter_pages: int = 2

    @classmethod
    def from_form(cls, chapter_config_json: str = "{}") -> "ChapterExtractionConfig":
        # json.loads + if-validate, 跟 table_params 同模式 (router.py:96-99)
```

**chapters_section.py 改动:**
- `run(ctx, chapter_config: ChapterExtractionConfig | None = None)` — 签名改
- 内部调 `extract_chapters(doc, max_level=chapter_config.chapter_max_level_for_display)`
- `_build_payload` 改 shape: 加 `max_level`, `total_chapters` 截断后计数, `chapters` 树状
- toc_source 值: `"pdf_outline" | "toc_pages" | "llm_refined" | "empty"`
- 加 `llm_summary_enabled: bool` 字段

**测试 (`test_chapter_config.py`, mode 1 mock):**
- from_form 正常解析
- from_form 缺字段走默认值
- from_form 越界值 clamped
- from_form JSON 非法 → ValueError

**测试 (`test_llm_schemas.py`, mode 1 mock):**
- ChapterEntry 正常解析
- SummaryOutput 批量解析
- ValidationError 边界

**测试 (`test_chapters_section.py`, 改, mode 1 mock):**
- 传 chapter_config (max_level=3) 验证 payload.chapters 树状
- 不传 chapter_config 走默认值 (向后兼容)
- 验证 payload 含 max_level / toc_source / llm_summary_enabled 字段

**验证:** `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_chapter_config.py tests/ingest/pre_analysis/test_llm_schemas.py tests/ingest/pre_analysis/test_chapters_section.py -v`

**Commits:**
1. `feat(chapter_config): ChapterExtractionConfig + llm_schemas Pydantic`
2. `refactor(chapters_section): 接 chapter_config + 树状 payload`

---

### M3a: `llm_chapter.py` — LLM 章节重组 (fallback)

**估算 200 行 / 2 commits**

**文件:**
- Create: `llm_chapter.py` [新]
- Create: `test_llm_chapter.py` [新]

**核心函数 (`llm_chapter.py`):**

```python
def llm_refine_chapters(doc: pymupdf.Document, config: ChapterExtractionConfig) -> list[tuple[int, str, int]]:
    """A/B 抽取失败时, 用 LLM 拿前 30 页文本推断章节结构.
    用 with_structured_output(LLMChapterOutput, method="json_mode").
    """
```

- 取前 30 页文本, 拼 `--- Page N ---` 分隔
- `ChatPromptTemplate.from_messages` 构建 prompt
- `OpenAILLM().llm` 或 `LocalLLM().llm` 按 provider
- `with_structured_output(LLMChapterOutput, method="json_mode")`
- 限 30k 字符, 失败 log WARNING 不阻断

**测试 (`test_llm_chapter.py`, mode 1 mock):**
- mock OpenAILLM.llm 返回假 JSON, 验 Pydantic 解析 + 回传格式
- mock Pydantic 失败 → log WARNING + 返 []
- mock LLM 失败 (ConnectionError) → log WARNING + 返 []

**验证:** `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_llm_chapter.py::test_llm_refine -v`

**Commits:**
1. `feat(llm_chapter): llm_refine_chapters + with_structured_output`
2. `test(llm_chapter): mock LLM 路径 + 失败降级`

---

### M3b: `llm_chapter.py` — LLM 章节摘要 + Ollama provider

**估算 250 行 / 3 commits**

**文件:**
- Modify: `llm_chapter.py` [改] 加 `llm_summarize_chapters`
- Modify: `test_llm_chapter.py` [改] 加摘要测试

**核心函数 (`llm_chapter.py`):**

```python
def llm_summarize_chapters(
    doc: pymupdf.Document,
    chapters: list[dict],
    config: ChapterExtractionConfig,
) -> dict[str, str]:
    """为选中层级的每个 chapter 生成 2-3 句中文摘要.
    分批: Ollama 10 章/批, OpenAI 25 章/批.
    返回 {chapter_id: summary}
    """
```

- 筛选 `level <= config.llm_summary_max_level` 的 chapter
- 每章取前 `llm_summary_per_chapter_pages` 页文本 (限 2k 字符)
- 批量 prompt + `with_structured_output(SummaryOutput)`
- Ollama 分批 10 章, OpenAI 分批 25 章
- 单 batch 失败不影响其他 batch

**测试 (`test_llm_chapter.py`, mode 1 mock):**
- mock OpenAILLM 返假 summary JSON, 验 summary 写回 dict
- mock LocalLLM (Ollama) 分批测试
- 部分 chapter 没 summary → dict 只含成功项
- LLM 失败 → 返空 dict

**验证:** `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_llm_chapter.py::test_llm_summarize -v`

**Commits:**
1. `feat(llm_chapter): llm_summarize_chapters 批量摘要`
2. `feat(llm_chapter): Ollama 分批 + 错误降级`
3. `test(llm_chapter): 摘要路径全覆盖`

---

### M3c: `__init__.py` / `base.py` / `outline.py` 改造 + `chapters_section.py` 集成

**估算 150 行 / 1 commit**

**文件:**
- Modify: `__init__.py` [改] `extract_chapters` 加 max_level 参数
- Modify: `base.py` [改] `ChapterExtractor.extract` 加 max_level
- Modify: `outline.py` [改] extract 加 max_level, 调 `build_chapter_tree`
- Modify: `test_chapter_extractors_v2.py` [新] max_level 测试

**改动:**
- `extract_chapters(doc, max_level=6)` — 传 `max_level` 进 extractor
- `OutlineExtractor.extract(doc, max_level=6)` — `build_chapter_tree(toc, len(doc), max_level)`
- chapters_section.run() 调 `extract_chapters(doc, max_level=...)` 拿到树状 chapters

**测试 (`test_chapter_extractors_v2.py`, mode 1 mock):**
- extract_chapters 带 max_level → 树状输出
- extract_chapters 默认 max_level=6 → 完整树 (跟 OutlineExtractor 一致)
- max_level=1 时仅 L1 节点

**验证:** `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_chapter_extractors_v2.py tests/ingest/pre_analysis/test_chapters_section.py -v`

**Commit:**
1. `refactor(chapter_extractors): extract_chapters 加 max_level, OutlineExtractor 返树状`

---

### M4: API `chapter_config_json` form 字段 + 端点测试

**估算 150 行 / 2 commits**

**文件:**
- Modify: `router.py` [改] upload + retry 传 chapter_config_json
- Modify: `test_router.py` [改] 加 chapter_config_json 测试

**router.py 改动:**
- `POST /upload`: form 加 `chapter_config_json` (str, default "{}")
- merge: `chapter_cfg = ChapterExtractionConfig.from_form(chapter_config_json)`
- `task_config_json` = `{"table_backend": ..., "table_params": ..., "chapter": chapter_raw_dict}`
- runner 传: `runner.run(task_id, pdf_uri, table_config, chapter_config=chapter_cfg)`
- `POST /retry`: 从 `task.task_config_json.chapter` 取, 走同样解析
- `_run_pre_analysis(task_id, table_config, chapter_config)` — 传 chapter_config

**测试 (`test_router.py` 追加, mode 1 mock):**
- 上传带 `chapter_config_json={"chapter_max_level": 4, "llm_enabled": true}` → 200
- 上传缺字段 → 默认值
- 上传 JSON 非法 → 400
- retry 路径: 保留原 chapter 配置

**验证:** `cd packages/service && uv run pytest tests/ingest/pre_analysis/test_router.py -v`

**Commits:**
1. `feat(router): upload + retry 加 chapter_config_json form 字段`
2. `test(router): chapter_config_json 校验 + 边界`

---

### M5: 前端 upload dialog 2 控件 + i18n + API 层

**估算 350 行 / 3 commits**

**文件:**
- Modify: `pre-analysis-upload-dialog.tsx` [改] 加 2 控件 + payload 拼装
- Modify: `pre-analysis-upload-dialog.test.tsx` [改] 加控件测试
- Modify: `pre-analysis.ts` [改] 加 ChapterExtractionConfig type + form 字段
- Modify: `pre-analysis.test.ts` [改] 加 chapter config 测试
- Modify: `zh.json` [改] i18n
- Modify: `en.json` [改] i18n

**pre-analysis.ts 改动:**
- 新增 `ChapterExtractionConfig` type (跟后端 dataclass 对应)
- `preAnalysisUpload(file, config, chapterConfig?)` — 第 3 参数
- formData 加 `chapter_config_json = JSON.stringify(chapterConfig ?? {})`

**pre-analysis-upload-dialog.tsx 改动:**
- 高级选项区加 2 控件 (在 table 控件下方):
  1. **章节显示层级**: `<AppSelect>` (5 档: 1-2 / 1-3 / 1-4 / 1-5 / 1-6, 默认 1-3)
  2. **启用 LLM 增强**: `<AppToggle>` (开关, 默认关)
- state 新增 `chapterState: { maxLevel: 3, llmEnabled: false }`
- `handleUpload` 拼 `chapterConfig`

**i18n (zh.json):**
```json
"章节显示层级": "章节显示层级",
"启用 LLM 增强": "启用 LLM 增强",
"控制章节结构的显示粒度，层级越小，章节越少": "控制章节结构的显示粒度，层级越小，章节越少",
"开启后将对章节内容进行 LLM 智能分析": "开启后将对章节内容进行 LLM 智能分析",
"1-2 级": "1-2 级",
"1-3 级": "1-3 级",
"1-4 级": "1-4 级",
"1-5 级": "1-5 级",
"1-6 级": "1-6 级",
```

**测试 (`pre-analysis-upload-dialog.test.tsx`, vitest + RTL):**
- 渲染 2 控件 (AppSelect + AppToggle)
- 默认值: maxLevel=3, llmEnabled=false
- 切换 llmEnabled → formData 含 chapter_config_json
- 选择 maxLevel=4 → formData 含 chapter_max_level: 4
- 不展开高级选项时默认值

**测试 (`pre-analysis.test.ts`, vitest + fetch mock):**
- preAnalysisUpload 带 chapterConfig → formData 含 chapter_config_json
- preAnalysisUpload 不带 chapterConfig → formData 含 "{}"

**验证:** `bun run test packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx`

**Commits:**
1. `feat(api): pre-analysis.ts 加 ChapterExtractionConfig type + form 字段`
2. `feat(dialog): upload dialog 加 2 控件 (章节层级 + LLM 增强)`
3. `test(dialog): 2 控件渲染 + form 提交测试`

---

## 验证方案

### 单元测试全量跑

```bash
# 后端
cd packages/service && uv run pytest \
  tests/ingest/pre_analysis/test_chapter_tree.py \
  tests/ingest/pre_analysis/test_chapter_config.py \
  tests/ingest/pre_analysis/test_llm_schemas.py \
  tests/ingest/pre_analysis/test_llm_chapter.py \
  tests/ingest/pre_analysis/test_chapter_extractors_v2.py \
  tests/ingest/pre_analysis/test_chapters_section.py \
  tests/ingest/pre_analysis/test_router.py \
  -v

# 前端
bun run test packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx
bun run test packages/web/lib/api/pre-analysis.test.ts
```

### 代码质量铁律

```bash
cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright
cd packages/web && bun run format && bun run lint:fix && bun run typecheck
```

### 最终验证 (commit 前)

```bash
cd packages/service && uv run pytest -v
cd packages/web && bun run test
```

### 不做的事

- 不实现详情页树状/平级切换 toggle (M6 留后续 spec)
- 不联动 KG 抽取
- 不引新 LLM 依赖
- 不重写目录页 OCR
- 不实现章节合并/拆分规则
- 不修改现有 test_runner.py 集成测试 (用真 d81_dummy.pdf)

---

## 提交顺序总览 (7 PR / 14 commits)

| PR # | Milestone | Commits | 行数 | 验证命令 |
|---|---|---|---|---|
| PR1 | M1a | 2 | 250 | `uv run pytest tests/ingest/pre_analysis/test_chapter_tree.py` |
| PR2 | M1b | 2 | 200 | `uv run pytest tests/ingest/pre_analysis/test_chapter_tree.py::test_detect_and_parse` |
| PR3 | M2 | 2 | 250 | `uv run pytest tests/ingest/pre_analysis/test_chapter_config.py test_llm_schemas.py test_chapters_section.py` |
| PR4 | M3a | 2 | 200 | `uv run pytest tests/ingest/pre_analysis/test_llm_chapter.py::test_llm_refine` |
| PR5 | M3b | 3 | 250 | `uv run pytest tests/ingest/pre_analysis/test_llm_chapter.py::test_llm_summarize` |
| PR6 | M3c | 1 | 150 | `uv run pytest tests/ingest/pre_analysis/test_chapter_extractors_v2.py test_chapters_section.py` |
| PR7 | M4 | 2 | 150 | `uv run pytest tests/ingest/pre_analysis/test_router.py` |
| PR8 | M5 | 3 | 350 | `bun run test pre-analysis-upload-dialog.test.tsx pre-analysis.test.ts` |

**总计**: ~1800 行, 14 commits, 8 PRs
