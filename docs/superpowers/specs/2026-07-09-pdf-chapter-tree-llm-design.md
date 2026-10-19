# PDF 章节树状化 + LLM 增强 (pre-analysis v2)

**日期**: 2026-07-09
**状态**: 设计待审
**触发来源**: 用户 2026-07-09 反馈 D81.1 fixture 跑 runner.py 后生成 382 章, 几乎每页都当章节, 不可读. 调研 + 头脑风暴后立项.
**关联 spec**:
- [2026-07-02-pdf-pre-analysis-design.md](./2026-07-02-pdf-pre-analysis-design.md) — 5 stage 父 spec
- [2026-07-06-table-extractor-adapter-design.md](./2026-07-06-table-extractor-adapter-design.md) — table_backend 配置模式类比

---

## Context

### 现状 (runner.py:276-281)

```python
def _extract_chapters(self, doc: pymupdf.Document) -> list[dict]:
    """调 doc.get_toc() 拿章节. 返回空 list 如果 PDF 无 outline (logged WARNING, 不报错)."""
    toc = doc.get_toc()  # list[[level, title, page]]
    if not toc:
        logger.warning("PDF 无 outline (get_toc 返空), chapter_structure 标空")
    return [{"level": lvl, "title": title, "page_start": page, "page_end": page} for lvl, title, page in toc]
```

### 根因 (基于 D81.1 fixture 710 页实测)

| 问题 | 现象 |
|---|---|
| **PDF outline 颗粒度极细** | `doc.get_toc()` 返回 **382 条** (Level 1: 5 / L2: 11 / L3: 59 / L4: 168 / L5: 119 / L6: 20). Level 4-6 占 307 条, 几乎每页一节. |
| **chapter.page_end == page_start** | runner.py:281 最后那个 `page_end: page`, 导致每个节点自报"占 1 页". 实际章节范围由 outline 树隐含, 没推导. |
| **平铺 list 无层级** | 382 条 chapter 全是平级 list, 看不到 Chapter 1-8 主章骨架 + 子节树状关系. |
| **无 fallback** | 仅靠 `doc.get_toc()` 一条路径, outline 缺失/异常时直接空 (无目录页 fallback, 无 LLM 补救). |
| **无章节摘要** | 原始 spec §未来工作 #4 提过 (2026-07-02): "每章自动摘要为 1 句话, 写进 chapter_structure.json, admin 阅读加速" — 至今未实现. |

### 目标

1. **树状结构 + 正确 page_end** — 382 条 outline 全部保留为嵌套树, 每个节点的 `page_end` 推导到下一个同级/上级节点的 `page_start - 1`, 末节点 = PDF 总页数. L1 主章能一眼看全, L4-6 子节按需下钻. 后端按 `chapter_max_level` 序列化时截断 (D81.1 max_level=3 时 382→75, 其他 PDF 按实际 L1-3 节点数)
2. **多层 fallback 抽取** (A 优先, B-D 兜底):
   - **A. PDF outline** (优先) — PyMuPDF `doc.get_toc()` 拿内嵌 outline, 已有数据. **D81.1 根因修复不在此处, 靠 `chapter_max_level` 后端截断 (382→75)**
   - **B. 字体聚类 fallback** (D81.1 实测噪声大, 仅备用) — outline 异常/为空时, `page.get_text("dict")` 拿 spans + font-size + 位置过滤 找候选 heading. 实测 D81.1 前 30 页 false positive 率高 (banner/重复 page header), 不解决 outline 颗粒问题
   - **C. 视觉目录页解析** — outline 完全为空时启用, 扫描前 20 页找 "Contents/目录" + dotted-leader 行
   - **D. LLM 重组 (兜底)** — A/B/C 都失败 + checkbox 启用时, langchain + OpenAILLM 拿前 30 页文本推断
3. **LLM 章节摘要 (可选 checkbox)** — 实现原始 spec §未来工作 #4. admin 勾选后每个 L1-3 chapter 自动生成 2-3 句中文摘要, 写进 `chapter.summary` 字段.
   - **顺序: 先 max_level 截断, 再 LLM 摘要**. build_tree 阶段已按 `chapter_max_level` 截断 (D81.1: 382→75), LLM 仅对截断后的 chapters list 生成摘要. 避免 L4+ 浪费 token
4. **前端粒度可调** — dialog `chapter_max_level` AppSelect 1-2/1-3/1-4/1-5/1-6 五档 (默认 1-3), 数值存进 `task_config_json.chapter.chapter_max_level`. 后端序列化时按此值截断, 产物 JSON 颗粒度 = admin 选值 (D81.1 max_level=3 → 75 章, max_level=6 → 382 章)

### 非目标 (本期不做)

- ❌ 不修改现有 5 stage pipeline (`extract_chapters` / `extract_tables` / `extract_flagged` / `write_outputs` 等保持)
- ❌ 不联动 KG 抽取 (admin 手动 2 步走, 跟原 spec 一致)
- ❌ 不实现 LangGraph 流程编排 (单次 invoke + Pydantic 解析即可, 不需要 state machine)
- ❌ 不重写目录页 OCR (扫描件 PDF 走 kreuzberg/mineru, 解耦)
- ❌ 不引新 LLM 依赖 (复用现有 langchain-core/langchain-openai/langchain-ollama)

---

## 决策记录 (用户拍板)

| # | 决策 | 备注 |
|---|---|---|
| 1 | **PDF outline 优先** | outline 数据直接用, 不截断/不重构. 产物颗粒度由 `chapter_max_level` (用户选) 决定后端序列化时截断 (agent review HIGH 4) |
| 2 | **多重 fallback** | outline 失败时 (空/异常) 才走: 字体聚类 (D81.1 实测噪声大, 仅备选) → 视觉目录页 (dotted-leader regex) → LLM (checkbox 启). **D81.1 现状**: outline 完整, 触发不到任何 fallback. fallback 路径为低概率场景设计 |
| 3 | **LLM checkbox** | 默认关闭, 勾上才走. 两个用途: (a) 章节摘要 (优先) (b) fallback 重组 (A/B 都失败时) |
| 4 | **嵌套树状结构** | list 顶层 + 每个节点 `children` 字段. 后端按用户选 `chapter_max_level` 截断 L4+ 子树, 产物 JSON 颗粒度可控. **不存 flat_index map** (agent review 反模式: 无消费者, jq 一行递归查询可替代) |
| 5 | **后端按 max_level 截断** | dialog `chapter_max_level` 默认 3, 后端序列化时截断. admin 拿到的 chapter_structure.json 颗粒度 = 选值. 75 是 D81.1 巧合, 其他 PDF 按实际 L1-3 节点数 |
| 6 | **LLM provider 选项** | OpenAI 兼容 (默认, 走 OPENAI_BASE_URL) + Ollama (本地, 需 OLLAMA_BASE_URL). 复用 `OpenAILLM` + `LocalLLM` (实际类名, `src/generation/llm.py:91`) |
| 7 | **摘要范围用户自选** | 默认 L1-3, UI 选 1-2 / 1-3 / 1-4 / 全部 |
| 8 | **2-3 句批量生成** | 1 个 LLM call 喂多个 chapter 标题 + 首页文本 → 返 list of (chapter_id, summary) |

---

## 架构设计

### 后端目录布局 (增量)

```
packages/service/
├── configs/
│   └── pre_analysis/
│       └── chapter_config.yaml                  # [新] LLM provider / max_level 默认值 + 摘要 prompt 模板
├── src/
│   └── ingest/
│       └── pre_analysis/
│           ├── runner.py                          # [改] _extract_chapters 重写 + page_end 推导 + LLM 摘要
│           ├── chapter_extractor.py               # [新] 4 个独立函数: build_tree / detect_toc / parse_toc / llm_refine / llm_summarize
│           ├── chapter_config.py                  # [新] ChapterExtractionConfig dataclass + Pydantic 校验
│           └── llm_schemas.py                     # [新] Pydantic 输出 schema: LLMChapterOutput / SummaryOutput
└── tests/
    ├── ingest/
    │   ├── test_chapter_extractor.py             # [新] 4 函数单测 (mode 1 mock)
    │   ├── test_chapter_tree.py                  # [新] page_end 推导 + 嵌套构造 (mode 1 mock)
    │   ├── test_llm_schemas.py                   # [新] Pydantic 解析 (mode 1 mock)
    │   ├── test_pre_analysis_runner_v2.py        # [新] 集成: outline + LLM 摘要 (mock OpenAILLM)
    │   └── fixtures/
    │       └── pre_analysis/
    │           ├── d81_chapter_tree_expected.json # [新] D81.1 fixture 跑出来的真值对照 (382 节点)
    │           └── toc_pages/
    │               ├── d81_toc_page.txt           # [新] 模拟视觉目录页 (伪造, 非 D81.1 真目录页)
    │               └── d81_no_toc.txt             # [新] 不含 "Contents" 的页文本
```

### 前端目录布局 (增量)

```
packages/web/
├── app/[locale]/admin/pre-analysis/_components/
│   ├── pre-analysis-upload-dialog.tsx             # [改] 高级选项区加 2 控件 (章节显示层级 + LLM checkbox)
│   ├── pre-analysis-upload-dialog.test.tsx       # [改] 新增 2 控件 test case
├── app/[locale]/admin/pre-analysis/[task_id]/
│   └── page.tsx                                   # [改] 用 pre-analysis-chapter-tree 替当前表格
├── lib/api/
│   └── pre-analysis.ts                            # [改] preAnalysisUpload 新增 1 个 chapter_config_json form 字段 (含 5 项配置, UI 控件控 2 项, LLM 子项 3 项默认)
└── messages/
    ├── zh.json                                    # [改] 加 2 控件 i18n 文案
    └── en.json
```

### 2 dialog 控件 (upload dialog 高级选项区)

| # | 控件 | 类型 | 默认 | i18n key (zh) |
|---|---|---|---|---|
| 1 | 章节显示层级 | `AppSelect` (5 档: 1-2/1-3/1-4/1-5/1-6) | 1-3 | `章节显示层级` |
| 2 | 启用 LLM 增强 | `AppToggle` (开关) | 关 | `启用 LLM 增强` |

**章节视图模式 (树状/平级) 留 M6 后续 spec**:
- dialog 不暴露此控件 (本期只有 2 控件)
- 详情页加 toggle 后再做 (M6 留后续)
- 后端 chapter_structure.json 始终输出嵌套树状 (含 `chapters[].children`), 后端按 `chapter_max_level` 截断 L4+ 子树 (agent review HIGH 4 修正). 详情页渲染层负责按 toggle 选 tree / flatten

**视觉目录页 fallback 限制** (agent review HIGH 2 修正):
- 本期项目 corpus 是 native digital PDF (Siemens D81/D84 等), `doc[page_idx].get_text()` 返非空
- 扫描件 PDF 走 kreuzberg/mineru OCR (解耦, 跟原 spec §非目标 一致)
- 视觉目录页 fallback 在扫描件 PDF 上**不会触发** (即使 outline 为空, 因为 `get_text()` 返空, dotted-leader 解析失败)
- 这意味着扫描件 PDF + 无 outline 路径: A 失败 → B 失败 → C (LLM) 才走. 跟本期项目实际使用一致

### 详细数据流

```
admin 上传 PDF (form: file + table_backend + table_params + chapter_*)
    │
    ▼ POST /api/pre-analysis/upload
    │
    │ 1. super_admin guard
    │ 2. ObjectStore.put_bytes(s3://.../pre_analysis_inputs/{uuid}/input/{file})
    │ 3. INSERT pre_analysis_tasks (state='pending', task_config_json={chapter_*})
    │ 4. background.add_task(_run_pre_analysis, uuid)
    │
    ▼ BackgroundTasks
    │
    │ _run_pre_analysis(uuid):
    │   1. ObjectStore.open_local(work_dir + 'input/foo.pdf')
    │   2. pymupdf.open(path) → get_toc()
    │   3. [新] extract_chapters 阶段 (4 层 fallback, 先 max_level 截断再 LLM):
    │      ├─ A. outline 优先 → build_tree(raw_toc, total_pages, max_level=chapter_max_level)
    │      │   (max_level 在 build 时跳过 level > max_level entry, 382 → 75)
    │      ├─ B. outline 为空 → cluster_by_font_size → build_tree (同样截断)
    │      ├─ C. B 失败 → detect_toc_pages + parse_toc_pages → build_tree (同样截断)
    │      ├─ D. A/B/C 都失败 + llm_enabled=true → llm_refine_chapters (产物已含截断)
    │      └─ E. 全失败 → 返空 (跟现状 WARNING 行为一致)
    │   4. [新] 若 llm_enabled=true 且 chapter tree 非空 (截断后):
    │      ├─ chapters list 是 max_level 截断后的产物 (已不含 L4+)
    │      ├─ 按 llm_summary_max_level 过滤 (默认 3, 但实际 ≤ chapter_max_level)
    │      ├─ 每个 chapter 抽 1-2 页首页文本 (page_start..page_end 范围)
    │      ├─ prompt: 章节摘要 (2-3 句批量)
    │      ├─ Pydantic 解析 → 写 chapter.summary
    │      └─ 失败: log WARNING, summary 留空, 不阻断主流程
    │   5. [改] 写 chapter_structure.json (树状, 已经是截断后的 chapters list)
    │   6. extract_tables (不动)
    │   7. extract_flagged (不动)
    │   8. write_outputs (改: index.json 摘要标记 toc_source + llm_summary_enabled)
```

### 关键算法

#### A. `_build_chapter_tree(raw_toc, total_pages, max_level)` — page_end 推导 + 嵌套 (HIGH 4/5/MEDIUM 修正)

```python
def build_chapter_tree(
    raw_toc: list[tuple[int, str, int]],  # [(level, title, page_start), ...]
    total_pages: int,
    max_level: int = 6,
) -> list[dict]:
    """从 PyMuPDF doc.get_toc() 平铺 list 转嵌套树 (dict shape), page_end 推导.

    返回 dict 而非 dataclass (agent review HIGH 5 修正):
    - 保持 _write_chapter_structure (runner.py:399) `chapters: list[dict]` 接口兼容
    - dict shape: {id, level, title, page_start, page_end, summary?, summary_source?, children: [...]}
    - id 字段仅在 dict 内部使用 (admin 下载 JSON 后 jq 可见), 不存 flat_index

    max_level 截断 (agent review HIGH 4 修正):
    - 后端按 chapter_max_level 序列化时, level > max_level 的节点不写进产物 JSON
    - 实现: build 时跳过 level > max_level 的 entry (节省内存 + JSON 减半)
    - D81.1 max_level=3 时: 382 → 75 节点

    算法:
    1. 单调栈 (stack) 维护当前路径节点 (用 dict).
    2. 遍历每个 (level, title, page_start):
       - 创建节点, page_end=0 (待推)
       - 当 stack 顶层节点 level ≥ 当前 level, pop (回到父级)
       - 当前节点入 stack 顶层节点的 children
       - 当前节点 push 到 stack
    3. 后序遍历推导 page_end (用 enumerate 避免 O(N²), agent review MEDIUM 修正):
       - 末节点: page_end = total_pages
       - 非末节点: page_end = 下一同级/上级节点 page_start - 1
       - 递归推导子节点 page_end
    """
    root_children: list[dict] = []
    # 维护两个并行栈: children_stack[i] = 当前路径第 i 层节点的 children list
    # level_stack[i] = 当前路径第 i 层节点的 level (用于单调 pop)
    children_stack: list[list[dict]] = [root_children]
    level_stack: list[int] = [0]  # 哨兵 level 0
    counter = 0
    for level, title, page_start in raw_toc:
        # 截断: level > max_level 的 entry 不入栈 (agent review HIGH 4)
        if level > max_level:
            continue
        counter += 1
        node = {
            "id": f"ch_{counter}",
            "level": level,
            "title": title,
            "page_start": page_start,
            "page_end": 0,  # 后续推导
            "children": [],
        }
        # 单调 pop: 顶层 level >= 当前 level 时回退到父级
        while level_stack[-1] >= level:
            children_stack.pop()
            level_stack.pop()
        children_stack[-1].append(node)
        children_stack.append(node["children"])
        level_stack.append(level)

    # 后序: 推导 page_end (enumerate O(N))
    def compute_end(children: list[dict], parent_end: int) -> None:
        for idx, node in enumerate(children):
            if not node["children"]:
                node["page_end"] = min(parent_end, total_pages)
            elif idx + 1 < len(children):
                compute_end(node["children"], children[idx + 1]["page_start"] - 1)
            else:
                # 最后一个子节点: page_end = 父节点 page_end
                compute_end(node["children"], parent_end)

    compute_end(root_children, total_pages)
    return root_children
```

#### B. `_cluster_by_font_size(doc, max_pages=30)` — 字体聚类 fallback (agent review HIGH 10 新增)

```python
def _candidate_spans(doc: pymupdf.Document, max_pages: int = 30) -> Iterator[tuple[int, dict]]:
    """生成器: yield (page_no, span) 元组. 过滤 size + 位置 (页面顶部 30% 区域).

    位置过滤理由 (D81.1 实测噪声多):
    - body text 9pt 排除 (size)
    - figure caption / footer 排除 (y 坐标 > 70% 页高)
    - 表格 cell 排除 (y 坐标在表格区, 字号接近 heading 但不是)
    - 阈值: span bbox y0 < page_height * 0.7 (页面顶部 70% 区域)
    """
    for page_idx in range(min(max_pages, len(doc))):
        page_no = page_idx + 1
        page_height = doc[page_idx].rect.height
        for block in doc[page_idx].get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = round(span.get("size", 0), 1)
                    if not (10 <= size <= 30):
                        continue
                    # 位置过滤: y0 < 70% 页高 (页面顶部 70% 区域, 排除 footer/figure caption)
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    if bbox[1] > page_height * 0.7:
                        continue
                    # 字体名过滤: 排除 "Italic" 字体 (figure annotation 常用)
                    fontname = span.get("font", "")
                    if "Italic" in fontname or "Oblique" in fontname:
                        continue
                    yield (page_no, span)


def cluster_by_font_size(doc: pymupdf.Document, max_pages: int = 30) -> list[tuple[int, str, int]]:
    """PDF outline 完全为空时, 用 font-size + 位置 + 字体名过滤找候选 heading.

    触发条件:
    - outline 为空或异常 (几乎所有 native digital PDF 都有 outline, 此路径很少触发)
    - 跟 outline 互斥: 由 runner._extract_chapters 流程控制 — outline 成功就不调本函数,
      本函数仅在 outline 失败时才被调用. 不存在"两者都成功"分支

    算法:
    1. 扫描前 max_pages 页, _candidate_spans 生成器过滤 (size + 位置 + 字体名)
    2. Counter 统计 size 频次, 取 Top-3 频次 size
    3. 第二轮扫: 每页第一个匹配 size 的 span, 排除纯数字短文本 (1/2 类)
    4. 返 list[(level, title, page_start)]

    D81.1 实测噪声 (D81.1 不会走此路径, 留作记录):
    - 28 候选 → 26 过滤后 → 26 还是重复 ("Introduction" 在 24 页重复)
    - 真实 heading 难判, banner/重复 page header 干扰
    - 后续 spec 改进: 加粗体检测 (font.bold) + 字号聚类 (Top-3 不一定对)
    """
    size_counter: Counter[float] = Counter(
        round(span["size"], 1) for _, span in _candidate_spans(doc, max_pages)
    )
    top_sizes = [s for s, _ in size_counter.most_common(3)]
    if not top_sizes:
        return []

    candidates: list[tuple[int, str, int]] = []
    seen_pages: set[int] = set()
    for page_no, span in _candidate_spans(doc, max_pages):
        if page_no in seen_pages:
            continue
        size = round(span["size"], 1)
        if size in top_sizes:
            text = span.get("text", "").strip()
            if text and len(text) > 1 and not re.match(r"^\d+/\d+$", text):
                level = top_sizes.index(size) + 1
                candidates.append((level, text, page_no))
                seen_pages.add(page_no)
    return candidates
```

#### C. `_detect_toc_pages(doc)` — 视觉目录页检测 (HIGH 10 调整为 outline 完全空时触发)

```python
def detect_toc_pages(doc: pymupdf.Document, max_scan: int = 20) -> list[int]:
    """扫描前 max_scan 页找含 'Contents' 标题 + dotted-leader 行的目录页.

    启发式:
    - 前 300 字符含 'Contents' / 'Table of Contents' / '目录' / '目  录' (大小写不敏感)
    - dotted-leader 行数 ≥ 5 (避免误报章节首页 / 索引页)
    """
    headers = ("table of contents", "contents", "目录", "目  录", "目 录")
    hits = []
    for page_idx in range(min(max_scan, len(doc))):
        text = (doc[page_idx].get_text() or "").lower()
        head = text[:300]
        for kw in headers:
            if kw in head:
                leader_lines = re.findall(r"\.{3,}\s*\d{1,4}\s*$", text, re.MULTILINE)
                if len(leader_lines) >= 5:
                    hits.append(page_idx)
                break
    return hits
```

#### D. `_parse_toc_pages(doc, page_indices)` — 目录页 → chapter entries

```python
def parse_toc_pages(doc: pymupdf.Document, page_indices: list[int]) -> list[tuple[int, str, int]]:
    """从目录页文本解析 (level, title, page_start) 三元组.

    启发式:
    - 行尾 dotted-leader + 页码: r".+?\.{3,}\s*(\d{1,4})\s*$"
    - level 推断: 行首空格缩进层级 (0=1, 1=2, ...) 或 "第 N 章" / "N.M.K" 编号长度
    - 多行 entry: 行尾页码缺失但下一行是纯页码 → 合并
    """
    raw_lines: list[tuple[int, str, int]] = []  # (level, title, page_start)
    for page_idx in page_indices:
        text = doc[page_idx].get_text() or ""
        lines = text.split("\n")
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # dotted-leader + 页码
            match = re.match(r"^(?P<title>.+?)\.+\s*(?P<page>\d{1,4})\s*$", line_stripped)
            if match:
                title = match.group("title").strip()
                page_start = int(match.group("page"))
                # level 推断: 行首空格 / 编号长度
                indent = len(line) - len(line.lstrip())
                level = min(indent // 2 + 1, 6)
                # 或按 "N.M.K" 编号: "1.2.3" → 3 级
                num_match = re.match(r"^(\d+(?:\.\d+)*)\s", title)
                if num_match:
                    level = min(num_match.group(1).count(".") + 1, 6)
                raw_lines.append((level, title, page_start))
    return raw_lines
```

#### E. `_llm_refine_chapters(doc, config)` — fallback LLM 重组 (HIGH 8 修正, with_structured_output)

```python
def llm_refine_chapters(doc: pymupdf.Document, config: ChapterExtractionConfig) -> list[tuple[int, str, int]]:
    """A/B 抽取失败时, 用 LLM 拿前 30 页文本推断章节结构.

    prompt: '你是 PDF 章节结构专家. 这是 PDF 前 30 页文本. 请提取目录结构.
             返回 JSON: [{ level, title, page_start }, ...]'
    """
    # 1. 取前 30 页文本
    chunks = []
    for i in range(min(30, len(doc))):
        chunks.append((i + 1, doc[i].get_text() or ""))
    full_text = "\n\n--- Page N ---\n\n".join(f"{p}\n{t}" for p, t in chunks)

    # 2. prompt + LLM
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是 PDF 章节结构专家. 仅返回 JSON, 不要解释."),
        ("user", """这是 PDF 的前 30 页文本, 用 '--- Page N ---' 分页. 
                  请提取目录结构, 返回 JSON 列表:
                  [{{"level": int (1-6), "title": str, "page_start": int (1-based page number)}}, ...]
                  
                  文本:
                  {text}
                  """),
    ])
    llm = OpenAILLM().llm if config.llm_provider == "openai" else LocalLLM().llm
    # agent review HIGH 8 修正: 用 with_structured_output (LangChain 1.x 推荐)
    # 替代 PydanticOutputParser + chain, 走 OpenAI 兼容协议 native function-call / JSON mode
    structured_llm = llm.with_structured_output(LLMChapterOutput, method="json_mode")
    result: LLMChapterOutput = (prompt | structured_llm).invoke({"text": full_text[:30000]})  # 限 30k 字符
    return [(c.level, c.title, c.page_start) for c in result.chapters]
```

#### F. `_llm_summarize_chapters(doc, chapters, config)` — 章节摘要 (HIGH 7+8 修正, 批量 + with_structured_output)

```python
def llm_summarize_chapters(
    doc: pymupdf.Document,
    chapters: list[dict],  # 已按 max_level 截断的章节树 (来自 build_tree)
    config: ChapterExtractionConfig,
) -> dict[str, str]:
    """为选中层级的每个 chapter 生成 2-3 句中文摘要.

    顺序: build_tree 阶段已按 chapter_max_level 截断, 本函数仅对截断后的
    chapters list 生成摘要. 避免对 L4-6 节点浪费 token.

    Returns: {chapter_id: summary}
    """
    # 1. 筛选选中层级
    target_chapters = [c for c in chapters if c.level <= config.llm_summary_max_level]

    # 2. 抽每章首页文本
    pages_per_chapter = config.llm_summary_per_chapter_pages
    chapter_texts: dict[str, str] = {}
    for ch in target_chapters:
        texts = []
        for p in range(ch.page_start, min(ch.page_start + pages_per_chapter, ch.page_end + 1)):
            if 1 <= p <= len(doc):
                texts.append(doc[p - 1].get_text() or "")
        chapter_texts[ch.id] = "\n".join(texts)[:2000]  # 每章限 2k 字符

    # 3. 批量 prompt
    chapters_block = "\n\n".join(
        f"[{ch.id}] Level {ch.level} | Pages {ch.page_start}-{ch.page_end} | {ch.title}\n"
        f"首页文本: {chapter_texts[ch.id][:1500]}"
        for ch in target_chapters
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是技术文档章节摘要专家. 用中文生成 2-3 句摘要 (50-80 字)."),
        ("user", """为以下 N 个 PDF 章节生成摘要. 每个章节 2-3 句 (50-80 字), 
                  概括主旨 + 技术要点 + 适用场景. 返回 JSON:
                  [{{"chapter_id": str, "summary": str}}, ...]

                  章节:
                  {chapters}
                  """),
    ])
    llm = OpenAILLM().llm if config.llm_provider == "openai" else LocalLLM().llm
    # agent review HIGH 8 修正: 用 with_structured_output (LangChain 1.x 推荐)
    structured_llm = llm.with_structured_output(SummaryOutput, method="json_mode")

    # agent review HIGH 7 修正: Ollama 7B 上下文 4-8k token, D81.1 L1-3 75 章摘要单次
    # 撑爆 (75*2000 字 = 150k 字). 分批 10 章/次, OpenAI 128k 单次即可.
    batch_size = 10 if config.llm_provider == "ollama" else 25
    all_summaries: list[tuple[str, str]] = []  # [(chapter_id, summary), ...]
    for i in range(0, len(target_chapters), batch_size):
        batch = target_chapters[i : i + batch_size]
        chapters_block = "\n\n".join(
            f"[{ch.id}] Level {ch.level} | Pages {ch.page_start}-{ch.page_end} | {ch.title}\n"
            f"首页文本: {chapter_texts[ch.id][:1500]}"
            for ch in batch
        )
        try:
            result: SummaryOutput = (prompt | structured_llm).invoke({"chapters": chapters_block})
            all_summaries.extend((item.chapter_id, item.summary) for item in result.summaries)
        except Exception as e:
            logger.warning("LLM 摘要 batch={} 失败 err={}", i // batch_size, e)
            # 单 batch 失败不影响其他 batch
            continue

    return dict(all_summaries)
```

### Pydantic schemas (新文件 `chapter_config.py` + `llm_schemas.py`)

```python
# chapter_config.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ChapterExtractionConfig:
    """用户上传表单的可选项. 通过 /upload form 传入 runner."""
    enable_llm_refinement: bool = False          # LLM checkbox 总开关
    llm_provider: Literal["openai", "ollama"] = "openai"
    chapter_max_level_for_display: int = 3       # 后端截断层级: 序列化时 L > chapter_max_level 的子树不写进产物 JSON (agent review HIGH 4 修正, 后端控制颗粒度)
    llm_summary_max_level: int = 3               # 摘要生成层级
    llm_summary_per_chapter_pages: int = 2       # 每章喂 LLM 的首页数 (1-3)

    @classmethod
    def from_form(
        cls,
        chapter_config_json: str = "{}",
    ) -> "ChapterExtractionConfig":
        """从 form 字段 chapter_config_json 解析. 缺字段走默认值 + 简单 if-validate.

        agent review MEDIUM 修正: 跟现有 `table_params` 解析模式一致 (router.py:96-99
        json.loads + if-validate + raise HTTPException). 不引入 Pydantic 校验层.
        """
        import json as _json
        try:
            raw = _json.loads(chapter_config_json) if chapter_config_json else {}
        except _json.JSONDecodeError as e:
            raise ValueError(f"chapter_config_json JSON 非法: {e}") from e
        defaults = cls()
        llm_provider = raw.get("llm_provider", defaults.llm_provider)
        if llm_provider not in ("openai", "ollama"):
            llm_provider = defaults.llm_provider
        return cls(
            enable_llm_refinement=str(raw.get("llm_enabled", "false")).lower() == "true",
            llm_provider=llm_provider,
            chapter_max_level_for_display=max(1, min(int(raw.get("chapter_max_level", 3)), 6)),
            llm_summary_max_level=max(1, min(int(raw.get("llm_summary_max_level", 3)), 6)),
            llm_summary_per_chapter_pages=max(1, min(int(raw.get("llm_summary_per_chapter_pages", 2)), 3)),
        )
```

```python
# llm_schemas.py
from pydantic import BaseModel, Field

class ChapterEntry(BaseModel):
    """LLM 输出的单个章节."""
    level: int = Field(ge=1, le=6)
    title: str = Field(min_length=1, max_length=200)
    page_start: int = Field(ge=1)

class LLMChapterOutput(BaseModel):
    """LLM 重组章节输出."""
    chapters: list[ChapterEntry] = Field(min_length=1, max_length=200)

class SummaryItem(BaseModel):
    """LLM 输出的单个章节摘要."""
    chapter_id: str = Field(min_length=1)
    summary: str = Field(min_length=20, max_length=300)

class SummaryOutput(BaseModel):
    """LLM 摘要批量输出."""
    summaries: list[SummaryItem] = Field(min_length=1, max_length=200)
```

### chapter_structure.json 新 shape

```json
{
  "total_pages": 710,
  "total_chapters": 382,
  "max_level": 6,
  "extracted_at": "2026-07-09T14:32:11+08:00",
  "toc_source": "pdf_outline",  // pdf_outline | toc_pages | llm_refined | empty
  "llm_summary_enabled": true,  // 是否做了摘要
  "chapters": [
    {
      "id": "ch_1",
      "level": 1,
      "title": "Catalog D 81.1 · 09/2023",
      "page_start": 1,
      "page_end": 1,
      "summary": "D81.1 是西门子 SIMOTICS 系列低压电机选型手册...",
      "summary_source": "llm",  // llm | none
      "children": [
        {
          "id": "ch_2",
          "level": 2,
          "title": "Related catalogs",
          "page_start": 2,
          "page_end": 3,
          "summary": "...",
          "summary_source": "llm",
          "children": []
        }
      ]
    }
  ],
```

**不存 flat_index 设计动机** (agent review HIGH 3 修正):
- 当前无消费者 (M5 dialog 不读, M6 详情页 toggle 留后续)
- 递归树遍历 jq 一行就够 (e.g. `.. | .children? // empty | .[] | select(.id == "ch_X")`)
- 减少 JSON 大小 ~50%
- 避免 sync invariant (flat_index 必须跟 tree id 同步, 当前 spec 没 validate)

### 5 stage 改造点

| Stage | 改动 |
|---|---|
| `load_config` | 加载 `chapter_config.yaml` (新增) |
| `extract_chapters` | **重写**: 调用 `chapter_extractor.py` 4 函数 + 多层 fallback + page_end 推导 + 嵌套 |
| `extract_tables` | **不动** |
| `extract_flagged` | **不动** |
| `write_outputs` | **改**: `chapter_structure.json` 写新 shape (树状, 后端按 `chapter_max_level` 截断). `index.json` 加 `llm_summary_enabled` 字段 |

### API 4 端点改动

| Method | Path | 改动 |
|---|---|---|
| POST | `/api/pre-analysis/upload` | form 加 1 个字段: `chapter_config_json` (JSON 字符串, 含 5 配置项). 跟 `table_backend` + `table_params` 合并进 `task_config_json` dict (agent review HIGH 6 修正):<br>**router.py 合并逻辑** (跟现有 table_backend/table_params 同模式):<br>```python<br># 现有 line 108: table_config = {"table_backend": ..., "table_params": ...}<br>chapter_raw = json.loads(chapter_config_json) if chapter_config_json else {}<br>merged_config = {**table_config, "chapter": chapter_raw}<br>pa_save_task(..., task_config=merged_config)  # 存进 task_config_json 列<br>```<br>**retry 路径** (router.py:329):<br>```python<br>original = json.loads(task.task_config_json or "{}")<br>chapter_cfg = original.get("chapter", {})<br>```<br>然后 runner 拿到 chapter_cfg dict 走同样解析逻辑. 复用现有 `_run_ingest` 模板 |
| GET | `/api/pre-analysis/tasks/{id}` | 响应透传 `task_config_json.chapter` 子字段 |
| GET | `/api/pre-analysis/tasks/{id}/files/{filename}` | 不动, blob 下载走原路径 |
| GET | `/api/pre-analysis/tasks/{id}/download` | 不动, zip 内含新版 chapter_structure.json |

---

## 错误处理

| 失败点 | 降级行为 |
|---|---|
| PDF 上传空文件 / 非 .pdf | 422 `bad_request`, 不入库 (跟现有) |
| PDF 打开失败 / 损坏 | task state='failed', error='pymupdf.open raised: ...', UI 显示可重试 (跟现有) |
| outline 解析异常 (rare) | log WARNING, 走视觉目录页 fallback |
| 视觉目录页扫不到 (false negative) | log WARNING, 走 LLM (若 checkbox 启用) |
| 视觉目录页 dotted-leader 解析失败 | log WARNING, 走 LLM (若 checkbox 启用) |
| LLM 调失败 (rate limit / 超时 / 网络) | log WARNING, chapter 树返空 (无 summary), UI toast "LLM 调用失败, 已回退" |
| LLM 输出 Pydantic ValidationError | log WARNING, summary 留空, 不阻断主流程 |
| Ollama 端点未起 | ConnectionError → log WARNING, summary 留空 |
| 后端 chapter_config_json JSON 解析失败 | 400 `bad_request: chapter_config_json JSON 非法: ...` |
| 后端 chapter_config_json 字段缺 (e.g. `chapter_max_level=7`) | Pydantic 限 1-6, 越界抛 ValueError → API 层 400 |
| 后端 llm_summary_per_chapter_pages 越界 (e.g. 5) | Pydantic 限 1-3, 越界返 400 `bad_request` |

---

## 测试隔离 (CLAUDE.md §强制 4 模式)

| 模块 | 模式 | Fixture | 备注 |
|---|---|---|---|
| `chapter_extractor.build_chapter_tree` | 1 (mock doc) | 假 `(level, title, page)` 列表, 验嵌套 + page_end | 边界: 空 toc / 单节点 / 多层级 / 跨页 |
| `chapter_extractor.detect_toc_pages` | 1 (mock doc) | 假 `page.get_text()` 含/不含 "Contents" + dotted-leader | 边界: 0 命中 / 1 命中 / 多命中 |
| `chapter_extractor.parse_toc_pages` | 1 (mock doc) | dotted-leader 文本 fixture | 边界: 单行 / 多行 / 多行编号 |
| `chapter_extractor.llm_refine_chapters` | 1 (mock OpenAILLM) | 假 LLM 返 JSON, 验 Pydantic 解析 + build_tree 串联 | 边界: Pydantic 失败 / LLM 失败 |
| `chapter_extractor.llm_summarize_chapters` | 1 (mock OpenAILLM) | 假 LLM 返 JSON, 验 summary 写回 chapter 树 | 边界: 部分 chapter 没 summary |
| `chapter_structure.json` 序列化 | 1 (mock runner) | 假数据, 验 JSON shape 正确 | 边界: 382 节点 / 0 节点 / 嵌套深 6 层 |
| API 4 端点 | 1 (mock runner) | form `chapter_config_json` 校验 + 422/400/500 | 鉴权 + JSON 解析 |
| `lib/api/pre-analysis.ts` | 1 (vitest + fetch mock) | 1 form `chapter_config_json` 字段 + 错误码 | 跟现有模式 |
| `pre-analysis-upload-dialog.tsx` | 1 (vitest + RTL) | 2 控件渲染 + form 提交 | 默认隐藏 LLM 控件 (checkbox 关时不传 llm_enabled=true) |
| `pre-analysis-chapter-tree.tsx` | 1 (vitest + RTL) | 假 chapter tree 渲染, 默认展开 L1-3 | 验证 level 切换 |

**模式 1 mock 覆盖率目标**: 100% (跟前几期一致)

---

## 验证 (Verification)

### 单元测试

```bash
cd packages/service && uv run pytest \
    tests/ingest/test_chapter_extractor.py \
    tests/ingest/test_chapter_tree.py \
    tests/ingest/test_llm_schemas.py \
    tests/ingest/test_pre_analysis_runner_v2.py \
    -v
```

### D81.1 fixture 真实数据验证

```bash
# 跑真 D81.1 fixture, 生成期望产物
cd packages/service && uv run python -c "
from pathlib import Path
import pymupdf
import re
import json
from collections import Counter
from typing import Iterator
from src.ingest.pre_analysis.chapter_extractor import build_chapter_tree

doc = pymupdf.open('tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf')
toc = doc.get_toc()
tree = build_chapter_tree(toc, len(doc))
print(f'Total: {len(toc)} chapters → {len(tree)} L1 nodes')

# 输出 fixture 期望值
out = Path('tests/ingest/fixtures/pre_analysis/d81_chapter_tree_expected.json')
out.write_text(json.dumps({
    'total_pages': len(doc),
    'total_chapters': len(toc),
    'max_level': max(c[0] for c in toc),
    'tree_size': sum(1 + len(t['children']) for t in tree),
}, indent=2))
"
```

### 手工 E2E (dev 环境)

1. 启动后端 `uv run python main.py` + 前端 `bun run dev`
2. 拿 super_admin token 登录
3. 访问 `http://localhost:3000/zh/admin/pre-analysis`
4. 上传 D81.1 PDF + 勾选 "启用 LLM 增强" + 选 "摘要范围: L1-3" + 选 "LLM Provider: openai"
5. 等 ~60s (PDF 解析 + LLM 摘要), 列表显示 `completed`
6. 点详情页, 看到:
   - chapter_structure.json 含树状 75 节点 (chapter_max_level=3 默认截断, agent review HIGH 4 设计修正)
   - 75 个 L1-3 chapter 都带 `summary` 字段 (2-3 句中文)
   - 默认展开到 Level 3 (本期 UI 展开逻辑留 M6, 当前 admin 下载 chapter_structure.json 看)
7. 关掉 "启用 LLM 增强" checkbox 再上传一份, 验证 summary 为空, 树仍完整
8. 视觉目录页 fallback 测试: 用一个 PDF (outline 为空但有视觉目录页) 验证 toc_source="toc_pages"
9. Curl 验鉴权: anon token POST /api/pre-analysis/upload → 403

### 代码质量铁律

```bash
uv run ruff format && uv run ruff check --fix && uv run pyright
bun run format && bun run lint:fix && bun run typecheck
```

### 业务验收

| 验收项 | 期望 |
|---|---|
| 上传 710 页 D81.1 PDF (无 LLM) | 60s 内完成, chapter_structure.json ~25KB (chapter_max_level=3 默认, 75 节点, 树状) |
| 上传 D81.1 (LLM on, openai) | 90s 内完成, 75 个 L1-3 chapter 都带 summary |
| 上传 D81.1 (LLM on, ollama) | 180s 内完成 (本地推理慢), summary 质量低于 openai |
| chapter.page_end 推导 | L1 root: page_end = 710; L2 末节点: page_end = 上级 page_end |
| 嵌套结构 | L1 5 个 root, L2 11 个 child of root, L3 59 个 grandchild (chapter_max_level=3 截断后产物 JSON 只含这 75 节点) |
| 视觉目录页 fallback | 仅当 outline 为空 + 视觉页 ≥ 5 dotted-leader 行 才启用 |
| LLM 调失败降级 | chapter 树仍存在, summary 字段留空, UI toast 提示 |
| anon token 尝试 upload | 403, audit log 有记录 |

---

## 实施拆分 (8 Milestone / 估算 4 工作日 / 18 commits)

> **范围控制**: 8 PR / 各 ≤ 350 行单 PR 红线. 跟 CLAUDE.md §单 PR 500 行红线 留缓冲.

| # | Milestone | 文件 | 行数估算 | 验证 | commits |
|---|---|---|---|---|---|
| **M1a** | `chapter_extractor.py` outline 路径: `build_chapter_tree` + page_end 推导 + 嵌套构造 + `ChapterNode` dataclass | `chapter_extractor.py` [新, partial] + `chapter_config.py` [新] + `test_chapter_tree.py` [新] + D81.1 fixture 真值对照 | 250 | `uv run pytest tests/ingest/test_chapter_tree.py -v` | 2 |
| **M1b** | `chapter_extractor.py` 视觉目录页 fallback: `_detect_toc_pages` + `_parse_toc_pages` + 单元测试 | `chapter_extractor.py` [改] + tests | 200 | `uv run pytest tests/ingest/test_chapter_extractor.py::test_detect_and_parse -v` (mock doc + 真 d81_no_toc.txt fixture) | 2 |
| **M2** | `runner.py` 重写 `_extract_chapters` + 多层 fallback 串联 + 树状 JSON 序列化 | `runner.py` [改] + `test_pre_analysis_runner_v2.py` [新] + fixtures | 200 | `uv run pytest tests/ingest/test_pre_analysis_runner_v2.py -v` (mock runner + D81.1 fixture) | 2 |
| **M3a** | LLM 章节重组 (fallback): `_llm_refine_chapters` + `LLMChapterOutput` Pydantic schema + OpenAI 路径 | `llm_schemas.py` [新] + `chapter_extractor.py` [改] + tests | 200 | `uv run pytest tests/ingest/test_chapter_extractor.py::test_llm_refine -v` (mock OpenAILLM) | 2 |
| **M3b** | LLM 章节摘要: `_llm_summarize_chapters` + `SummaryOutput` Pydantic schema + Ollama provider | `chapter_extractor.py` [改] + `llm_schemas.py` [改] + tests | 250 | `uv run pytest tests/ingest/test_chapter_extractor.py::test_llm_summarize -v` (mock OpenAILLM + LocalLLM) | 3 |
| **M4** | API 1 个 `chapter_config_json` form 字段 + `ChapterExtractionConfig.from_form()` + 端点测试 | `router.py` [改] + `tests/ingest/test_pre_analysis_api.py` [改] | 150 | `uv run pytest tests/ingest/test_pre_analysis_api.py -v` (form 校验 + JSON 解析 422/400) | 2 |
| **M5** | 前端 upload dialog 2 控件 + i18n (章节显示层级 / 启用 LLM 增强). LLM 子项 (provider / 摘要范围 / 每章首页数) 后端支持但 UI 不暴露, 走默认值 (openai / L1-3 / 2 页). 压缩风格估算: 2 控件 ~50 行 + test ~30 行 + i18n ~5 行 + payload 拼装 ~15 行 = ~100 行净增. **接受 dialog 超 500 行 (432+100=532, agent review HIGH 9 用户决策不拆 sub-component, 留后续 spec 整改)**. 详情页改造 + 树状/平级视图切换 toggle 留 M6 后续 spec | `pre-analysis-upload-dialog.tsx` [改] + `pre-analysis.ts` [改] + i18n zh/en.json + 1 个 test | 350 | `bun run test packages/web/app/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx` | 3 |
| **M6** | **(留后续 spec)** 前端详情页加 1 个 "树状/平级" 切换 toggle (UI 控件, 不依赖后端 API). 详情页加载 chapter_structure.json 后按 toggle 渲染. 不抽独立组件 (1 处用, 不满足 ≥2 次封装门槛). 同时完善 "章节显示层级" 应用 (UI 展开到用户选的层级) | — (deferred) | — | — | — |

**总 ~1600 行 (本期), 拆 7 个 PR (8 个 milestone 中 M6 留后续)**:
- PR1 = M1a (2 commits, 250 行) — 树状 + page_end 算法
- PR2 = M1b (2 commits, 200 行) — 视觉目录页 fallback
- PR3 = M2 (2 commits, 200 行) — runner 集成 + D81.1 fixture
- PR4 = M3a (2 commits, 200 行) — LLM fallback 重组
- PR5 = M3b (3 commits, 250 行) — LLM 摘要 + Ollama
- PR6 = M4 (2 commits, 150 行) — API chapter_config_json
- PR7 = M5 (3 commits, 350 行) — 前端 dialog 2 控件

**注**: 详情页 UI 树状展示 + 树状/平级视图切换已留后续 spec. 本期后端输出树状 JSON, 前端 dialog 仅加 form 控件 (不联动详情页渲染). Admin 下载 chapter_structure.json 后用 jq 或 VSCode 自行分析树状数据. 立项依据: admin 主要场景是下载产物验收, UI 树状渲染不紧急.

---

## 不要做的事 (Top 8)

1. **不引 LangGraph / LangSmith** — 项目 LangChain 1.x + langchain-ollama 已够, 单次 invoke + Pydantic 解析无需 state graph
2. **不装 sentence-transformers / tiktoken** — 摘要靠 LLM, 不本地做 embedding
3. **不修改现有 5 stage pipeline 名字** — `extract_chapters` / `extract_tables` / `extract_flagged` / `write_outputs` 4 个 stage 保留, 只改 `extract_chapters` 内部实现
4. **不联动 KG 抽取** — admin 手动 2 步走 (原 spec §非目标 一致)
5. **不写新前端组件** — `<AppSelect>` / `<AppToggle>` / `<AppRadioGroup>` 已封装, 直接复用. 只新增 `pre-analysis-chapter-tree.tsx` (本期新业务, 1 处用, 不抽 AppTreeView)
6. **不删现有 chapter_structure.json schema** — 加 `chapters[].children`, 保留 `chapters[].{level/title/page_start/page_end}` 兼容 (admin 历史下载能解析). 弃 flat_index (反模式)
7. **不重写目录页 OCR** — 扫描件 PDF 走 kreuzberg/mineru, 解耦 (原 spec §非目标 一致)
8. **不实现章节合并/拆分规则** — LLM 摘要仅生成 summary 文本, 不动章节树结构 (避免 LLM 输出错误导致树损坏)

---

## 未来工作 (独立 spec, 本期后另起)

| # | 工作 | 工作量 | 立项依据 |
|---|---|---|---|
| 1 | **跨页表格合并** — 沿用原 spec §未来工作 #1, pymupdf `find_tables()` 启发式合并相邻页同名表 | 1.5 天 | D81.1 真手册含跨页表, admin 反馈后立项 |
| 2 | **OCR 层** — 扫描件 PDF (pymupdf `get_text()` 返空) 走 Tesseract / paddleOCR | 3 天 | 沿用原 spec §未来工作 #3 |
| 3 | **详情页 UI "树状/平级" 切换 toggle** — 详情页加 1 个 toggle 控件 (不抽独立组件), 加载 chapter_structure.json 后按 toggle 渲染 (tree 直接用 / flat 递归 flatten children). 本期不做, 留 M6 后续 spec | 0.3 天 | 本期后端已输出树状 JSON (按 chapter_max_level 截断), 详情页 toggle 渲染待补. admin 当前用下载 JSON + jq 分析 |
| 4 | **LangGraph 流程编排** — 章节摘要 + 实体抽取 + 章节合并 多步骤编排 | 2 天 | 章节摘要 LLM 后下一阶段扩展 |
| 5 | **章节对比** — 2 个 PDF 章节树 diff, 找新增/删除/重命名章节 | 1.5 天 | D81.1 多版本对比需求 |
| 6 | **摘要质量评估** — admin 评分 + LLM-as-judge, 自动调 prompt | 2 天 | 摘要上线后质量闭环 |

---

## 关联文档

- 项目根 [CLAUDE.md](../../CLAUDE.md) — 代码质量铁律
- 后端 [packages/service/CLAUDE.md](../../packages/service/CLAUDE.md) — 4 测试模式 + ObjectStore ABC
- 前端 [packages/web/CLAUDE.md](../../packages/web/CLAUDE.md) — i18n + 组件封装 + 路由跳转
- 触发: [2026-07-02-pdf-pre-analysis-design.md](./2026-07-02-pdf-pre-analysis-design.md) — 父 spec, 5 stage pipeline + 字段定义
- 关联: [2026-07-06-table-extractor-adapter-design.md](./2026-07-06-table-extractor-adapter-design.md) — `table_backend` 配置模式类比 (本章 chapter_* 配置同模式)
- LLM 复用: `packages/service/src/generation/llm.py` — OpenAILLM + LocalLLM 已封装

---

## 待用户审阅

本 spec 是头脑风暴后定稿, 请审阅以下决策点:

1. **8 milestone 拆分 (7 PR + M6 留后续)**: 同意按 M1a/M1b/M2/M3a/M3b/M4/M5 拆 7 个 PR, M6 (详情页 UI 树状渲染) 留后续 spec?
2. ~~**flat_index map 设计**: 同意在 chapter_structure.json 加 `flat_index` (id → 节点元信息) 字段, 便于 jq 分析? 还是仅依赖 `chapters[].children` 递归?~~ → **2026-07-09 修订 (agent review): 弃 flat_index (反模式). 当前 spec 仅 `chapters[]` 嵌套树**
3. **Ollama 作为 LLM provider 选项**: 同意 Ollama checkbox 默认显示在 UI, 还是仅 OpenAI (Ollama 留为下期)?
4. **API form 字段合并**: 同意 upload form 加 1 个 `chapter_config_json` JSON 字段 (含 5 配置项, 跟 `table_backend + table_params` 拆 2 字段略有不同)? 还是拆 5 个独立 form 字段?
5. **保留兼容 schema**: 同意 `chapters[].{level/title/page_start/page_end}` 4 字段保留, 仅新增 `children` + `summary` 字段 (admin 历史下载 JSON 兼容)?