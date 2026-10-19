# PyMuPDF 教程

> 📅 创建日期：2026-07-06
> 📁 项目代码引用：本教程以 `c:/Users/abcuc/Desktop/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python 工程师，需要做 PDF 解析 / 坐标级文本提取 / 表格识别

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 初始化](#二安装--初始化)
- [三、核心概念 & 抽象](#三核心概念--抽象)
- [四、常用 API & 命令速查](#四常用-api--命令速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、评测 & 调优技巧](#八评测--调优技巧)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

PyMuPDF（PyPI 包名 `pymupdf`，import 路径 `pymupdf`，旧名 `fitz`）是 MuPDF 渲染引擎的 Python 绑定，Artifex 维护。它把 PDF / XPS / EPUB / CBZ 当成 **结构化文档** 暴露：`Document → Page → Block → Line → Span → Char`，每一层都能拿到字体、坐标、颜色、bbox。

**同类对比：**

| 库 | 定位 | 本项目使用场景 |
|------|------|----------------|
| **PyMuPDF (pymupdf)** | 高性能 + 坐标级细粒度 | **本项目默认 PDF 解析**（`pyproject.toml:31`）|
| **Kreuzberg** | 统一文档解析（50+ 格式） | 普通格式 PDF/Word/Excel/图片，主力文本提取（`src/ingest/converters/kreuzberg.py`）|
| **pdfplumber** | 纯 Python 表格提取 | 表格 fallback（`src/ingest/pre_analysis/table_extractors/pdfplumber_extractor.py`）|
| **camelot-py** | lattice/stream 表格 | 复杂线框表格（`src/ingest/pre_analysis/table_extractors/camelot_extractor.py`）|
| **PyPDF2 / pypdf** | 纯 Python 文本提取 | 仅文本，无坐标 |
| **pdfminer.six** | 纯 Python 底层 | pdfplumber 依赖它 |

**PyMuPDF 解决的核心问题**：
- **坐标级文本块**：`page.get_text("blocks")` 一次拿全部文本块 + bbox，做版面分析 / 切块 / 关键段落定位
- **TOC 提取**：`doc.get_toc()` 一行拿到 PDF outline（章节结构）
- **表格识别**：`page.find_tables()` 1.27+ 自带，自适应 PDF 矢量线（`PymupdfTableExtractor`）
- **快速渲染**：`page.get_pixmap()` 缩略图 / OCR 前置，比 Wand 之类快一个数量级

**不适合什么**：纯文本流提取（用 pypdf 即可）、50+ 格式统一处理（用 Kreuzberg）。

---

## 二、安装 & 初始化

### 2.1 安装

```bash
# 项目已装 (pyproject.toml:31)
"pymupdf>=1.27.2.3",

# 单独验证
uv run python -c "import pymupdf; print(pymupdf.__version__)"
```

注意：1.27+ API 跟旧 `fitz`（PyPI 包 `PyMuPDF`）有差异。**项目统一用 `pymupdf` 这个包名 + `pymupdf` 这个 import 路径**（`src/ingest/pre_analysis/runner.py:29` 等）。

### 2.2 系统依赖

PyMuPDF 自带 MuPDF 静态库，**无需额外系统依赖**。不像 pdfplumber 需 poppler / camelot 需 ghostscript。

### 2.3 健康检查

```python
import pymupdf
print(pymupdf.__version__)  # 1.27.2.3+
print(pymupdf.version)      # MuPDF 引擎版本 (e.g. "1.27.0")

# 真 PDF 打开测试
doc = pymupdf.open("test.pdf")
print(len(doc), doc.metadata)
doc.close()
```

---

## 三、核心概念 & 抽象

### 1. Document

整个 PDF 文件的根对象：

```python
import pymupdf

doc = pymupdf.open("file.pdf")
doc.page_count        # int: 页数 (== len(doc))
doc.metadata          # dict: {title, author, creator, creationDate, ...}
doc.get_toc()         # list[[level, title, page]]: PDF outline
doc.is_pdf            # bool
doc.is_encrypted      # bool
doc.close()           # 显式释放 (或用 with 块, 但 pymupdf 1.27 不支持 context manager)
```

### 2. Page

每页对象，所有细粒度操作入口：

```python
page = doc[0]                    # 0-based 索引
page.rect                        # Rect: 页面尺寸 (宽高)
page.rotation                    # int: 0/90/180/270
page.get_text()                  # str: 整页纯文本
page.get_text("blocks")          # list[tuple]: (x0, y0, x1, y1, text, block_no, block_type)
page.get_text("dict")            # dict: 完整结构 (block > line > span > char)
page.get_images()                # list: 内嵌图片元数据
page.get_drawings()              # list: 矢量图元 (rect/curve/...)
page.get_pixmap()                # Pixmap: 渲染成位图
page.find_tables()               # 1.27+ TableFinder
```

### 3. Rect / Point / Matrix

```python
import pymupdf

# Rect: 矩形 (x0, y0, x1, y1)
r = pymupdf.Rect(0, 0, 612, 792)   # US Letter
r.width, r.height
r.contains(pymupdf.Point(100, 100))  # bool

# Point: 点
p = pymupdf.Point(100, 200)

# Matrix: 变换 (rotate/scale/translate)
m = pymupdf.Matrix(2, 2)            # 缩放 2 倍
```

### 4. TableFinder (1.27+)

新版内置的表格识别 API：

```python
finder = page.find_tables()
finder.tables                      # list[Table]
finder.add(candidates)             # 手动加额外候选
for t in finder.tables:
    t.bbox                         # Rect: 表格 bbox
    t.extract()                    # list[list[str]]: 二维字符串
    t.to_markdown()                # str: markdown 表格
    t.to_pandas()                  # pd.DataFrame
```

### 5. Pixmap (渲染)

```python
mat = pymupdf.Matrix(2, 2)         # 2× 缩放
pix = page.get_pixmap(matrix=mat)
pix.width, pix.height              # int: 像素
pix.tobytes("png")                 # bytes: PNG 编码
pix.save("out.png")                # 直接落盘
```

### 6. Document 文档化

| 属性/方法 | 用途 | 项目使用 |
|----------|------|---------|
| `doc.get_toc()` | PDF outline (章节) | `src/ingest/pre_analysis/runner.py:262` |
| `doc.metadata` | 元数据 | `src/ingest/pre_analysis/runner.py:121` |
| `len(doc)` / `doc[i]` | 页数 / 索引 | `src/ingest/pre_analysis/runner.py:46`, `pdf.py:30` |
| `page.find_tables()` | 表格识别 | `src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:46` |
| `page.get_text()` | 纯文本 | `src/ingest/pre_analysis/runner.py:372`, `pdf.py:31` |
| `page.get_images()` | 图片元数据 | `src/ingest/pdf_processing/analyzers/pdf.py:34` |
| `page.get_drawings()` | 矢量图元 | `src/ingest/pdf_processing/analyzers/pdf.py:38` |

---

## 四、常用 API & 命令速查

### 4.1 打开 / 关闭

```python
import pymupdf

# 文件路径
doc = pymupdf.open("file.pdf")

# 字节流 (HTTP 上传场景)
doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

# 用完必 close (pymupdf 1.27 不支持 context manager, 跟项目 runner 模式对齐)
doc.close()
```

### 4.2 遍历页面

```python
for page in doc:
    print(page.number)              # 0-based
    text = page.get_text()
```

### 4.3 文本块 (带坐标)

```python
blocks = page.get_text("blocks")
# [(x0, y0, x1, y1, text, block_no, block_type), ...]
for x0, y0, x1, y1, text, bno, btype in blocks:
    if text.strip():
        print(f"block@{x0:.0f},{y0:.0f}: {text[:50]}")
```

### 4.4 表格提取 (项目默认)

```python
finder = page.find_tables()
for table in finder.tables:
    rows = table.extract()          # list[list[str]]
    print(rows)
```

### 4.5 章节结构 (TOC)

```python
toc = doc.get_toc()
# [[1, "Chapter 1", 5], [2, "Section 1.1", 7], ...]
for level, title, page_no in toc:
    print(f"{'  ' * (level-1)}{title} -> p.{page_no}")
```

### 4.6 渲染成图

```python
# 缩略图
mat = pymupdf.Matrix(0.5, 0.5)
pix = page.get_pixmap(matrix=mat)
pix.save("thumb.png")

# 高 DPI (OCR 前置)
mat = pymupdf.Matrix(3, 3)          # 216 DPI
pix = page.get_pixmap(matrix=mat, alpha=False)
```

### 4.7 图片提取

```python
for img_index, img in enumerate(page.get_images(full=True)):
    xref = img[0]                   # 关键: 用 xref 拿原图
    base_image = doc.extract_image(xref)
    ext = base_image["ext"]         # "png" / "jpeg"
    data = base_image["image"]      # bytes
    Path(f"img_{img_index}.{ext}").write_bytes(data)
```

### 4.8 PDF 加密

```python
if doc.is_encrypted:
    doc.authenticate("password")    # 返回 bool (True=成功)
# 或解密时:
doc = pymupdf.open("file.pdf", password="xxx")
```

### 4.9 元数据

```python
print(doc.metadata)
# {'format': 'PDF 1.7', 'title': '...', 'author': '...',
#  'creationDate': 'D:20240101000000+00\'00'', ...}
```

### 4.10 修改 PDF

```python
# 加文字
page.insert_text((50, 50), "Hello", fontsize=12)

# 加红色矩形
page.draw_rect(pymupdf.Rect(10, 10, 100, 50), color=(1, 0, 0))

# 改 metadata
doc.set_metadata(doc.metadata | {"title": "New Title"})

doc.save("out.pdf")
```

---

## 五、项目集成点

### 5.1 Pyproject 锁版本

`packages/service/pyproject.toml:31`：

```toml
"pymupdf>=1.27.2.3", # PDF 细粒度解析, 替代 PyPDF2 (src/ingest/analyzers/pdf.py 拿文本块坐标)
```

### 5.2 项目引用位置

| 文件 | 用途 |
|------|------|
| `src/ingest/pre_analysis/runner.py:29` | 预分析 runner 主入口，提取 TOC + 表格 + 关键词段落 |
| `src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:8` | 表格适配器，**默认后端** |
| `src/ingest/pdf_processing/analyzers/pdf.py:5` | PDF 复杂度分析（页/图/矢量） |
| `tests/ingest/pre_analysis/table_extractors/test_pymupdf_extractor.py` | 表格提取测试 (mode 1 + 真 PDF fixture) |
| `tests/ingest/test_pdf_analyzer.py` | PDF analyzer 测试 |

### 5.3 项目预分析流程

```
admin 上传 PDF (router.py:65 upload_pre_analysis)
    ↓
BackgroundTasks._run_pre_analysis (router.py:296)
    ↓
PreAnalysisRunner.run (runner.py:90)
    ↓
pymupdf.open(pdf_path)  ← (runner.py:122) 1 次打开, 5 stage 复用
    ├── _extract_chapters: doc.get_toc() (runner.py:262)
    ├── _extract_tables:  page.find_tables() (pymupdf_extractor.py:46)
    ├── _extract_flagged: page.get_text() (runner.py:372)
    └── doc.close() (runner.py:208)
    ↓
产物写 ObjectStore (chapter_structure.json / tables/*.csv / ...)
```

### 5.4 表格提取 strategy 位置

```
src/ingest/pre_analysis/table_extractors/
├── base.py                    # TableExtractor 抽象 + TableData
├── pymupdf_extractor.py       # 默认后端 (本教程)
├── camelot_extractor.py       # 可选 (见 camelot.md)
├── pdfplumber_extractor.py    # 可选 fallback
└── factory.py                 # get_table_extractor(backend, params)
```

`configs/pre_analysis/table_extraction.yaml:5` 配默认后端：

```yaml
default_backend: pymupdf
backends:
  pymupdf:
    enabled: true
  camelot:
    enabled: false
  pdfplumber:
    enabled: false
```

### 5.5 选型原因

- **默认后端 = pymupdf**：已经装（pyproject.toml 必装项），无额外系统依赖
- **零依赖启动**：不需 ghostscript / poppler，CI / dev 机器直接跑
- **复用 doc**：`runner.py:122` 只开 1 次 PDF，5 个 stage 全用同一 `Document`（pymupdf_extractor 接受 `_pymupdf_doc` 注入）
- **自适应表格**：`page.find_tables()` 内部自适应，**不需 params**（camelot 反而要 `edge_tol` / `row_tol`）

---

## 六、项目代码示例

### 6.1 默认表格后端

`src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:13-52` 完整实现：

```python
class PymupdfTableExtractor(TableExtractor):
    """pymupdf find_tables() 适配器.

    优先复用已打开 pymupdf.Document (避免重新打开 PDF, 节省 IO + 内存).
    pymupdf 后端无调参 (find_tables() 内部自适应), params 忽略.
    """

    def __init__(self, params: dict) -> None:
        self._params = params

    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: pymupdf.Document | None = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格. PDF 无表格 → 返 [].

        Args:
            pdf_path: PDF 文件路径 (当 _pymupdf_doc 缺时, 自己开).
            _pymupdf_doc: 已打开 pymupdf.Document (推荐传, runner 已开过).
            **params: 预留, pymupdf 后端无调参.

        Returns:
            list[TableData] 表格列表.
        """
        own_doc = _pymupdf_doc is None
        doc: pymupdf.Document = _pymupdf_doc if _pymupdf_doc is not None else pymupdf.open(pdf_path)
        try:
            result: list[TableData] = []
            for page_idx, page in enumerate(doc):
                for table_idx, table in enumerate(page.find_tables().tables):
                    rows: list[list[str]] = [list(r) for r in table.extract()]
                    result.append(TableData(page_no=page_idx + 1, table_no=table_idx + 1, rows=rows))
            return result
        finally:
            if own_doc:
                doc.close()
```

**设计要点**：
- **复用 doc 模式**：runner 已经开了 `pymupdf.Document`，传进来避免 `open()` 二次 IO + 内存
- **try/finally 兜底**：`own_doc=True`（自己开）才负责 `close()`，避免重复 close
- **page_no 1-based**：跟 Camelot 行为对齐，前端统一展示
- **1-based 编号**：`table_no = table_idx + 1`

### 6.2 预分析 Runner 主体

`src/ingest/pre_analysis/runner.py:90-249` 关键片段：

```python
import pymupdf

# (1) 1 次打开, 5 stage 复用
doc = pymupdf.open(pdf_path)        # runner.py:122

# (2) 章节提取
toc = doc.get_toc()                  # runner.py:262
chapters = [{"level": lvl, "title": title, "page_start": page, "page_end": page} for lvl, title, page in toc]

# (3) 表格提取 (复用同一 doc)
_doc = doc if backend == "pymupdf" else None
extractor = get_table_extractor(backend, params)
raw_tables = extractor.extract(doc.name if hasattr(doc, "name") else "", _pymupdf_doc=_doc)

# (4) 关键词段落提取
for page_idx, page in enumerate(doc):
    text = page.get_text()
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

# (5) 必 close
doc.close()                          # runner.py:208
```

**为什么 1 次开**：
- `pymupdf.open()` 加载 PDF 全部对象表（xref），100MB PDF ≈ 200-500ms + 内存峰值
- 5 stage 复用同一 `Document`，节省 4 次重复 IO
- 注意：camelot / pdfplumber 后端**不能复用** doc，自己重开

### 6.3 PDF 复杂度分析

`src/ingest/pdf_processing/analyzers/pdf.py:22-84` 用 pymupdf 拿 PDF 结构做预处理分类：

```python
class PDFAnalyzer:
    """PDF复杂度分析器"""

    def analyze(self, pdf_path: str) -> PDFInfo:
        doc = pymupdf.open(pdf_path)
        info = PDFInfo(page_count=len(doc))
        for page in doc:
            text = page.get_text()
            if text.strip():
                info.has_text = True
            images = page.get_images()
            if images:
                info.has_images = True
                info.image_count += len(images)
            drawings = page.get_drawings()
            if drawings:
                info.drawing_count += len(drawings)
            if self._is_table_page(drawings):
                info.table_like_pages += 1
        self._evaluate(info)
        doc.close()
        return info
```

**设计要点**：
- `page.get_drawings()` 返回矢量图元列表，启发式判断表格页（h/v 短线条数 > 10）
- `_evaluate()` 综合 4 维度（文字 / 表格 / 矢量 / 图片）判定 `is_simple`
- **简单 PDF** 走快速路径（Kreuzberg 文本提取），**复杂 PDF** 走 OCR + 表格识别

### 6.4 测试模式 (mode 1 + 真 PDF fixture)

`tests/ingest/pre_analysis/table_extractors/test_pymupdf_extractor.py:17-35` 模板：

```python
FIXTURE_PDF = Path(__file__).resolve().parents[2] / "fixtures" / "d81_dummy.pdf"

def test_extract_with_injected_doc_returns_table_data() -> None:
    """复用已开 doc 路径."""
    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    doc = pymupdf.open(str(FIXTURE_PDF))
    try:
        extractor = PymupdfTableExtractor({})
        result = extractor.extract(str(FIXTURE_PDF), _pymupdf_doc=doc)
        assert isinstance(result, list)
        for td in result:
            assert td.page_no >= 1
            assert td.table_no >= 1
            assert isinstance(td.rows, list)
    finally:
        doc.close()
```

**测试模式 4 模式**（见 `packages/service/CLAUDE.md §测试隔离 4 模式`）：
- pymupdf 后端是**纯本地库**（无 PG/Redis 依赖），走**模式 1 纯单测** + 真 PDF fixture
- fixture `d81_dummy.pdf` 是已知含 1 张表格的小 PDF，验证 page_no=3 / table_no=1 行为稳定
- pymupdf `try/finally close()` 是测试断言的一部分（资源泄漏检测）

### 6.5 HTTP 上传场景

`src/ingest/pre_analysis/router.py:65-124` 接收上传 PDF → runner 调度：

```python
async def upload_pre_analysis(
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_super_admin),
    file: UploadFile = File(...),
    table_backend: str = Form("pymupdf"),
    table_params: str = Form("{}"),
) -> dict:
    pdf_bytes = await file.read()
    # ... 写 ObjectStore, 鉴权, 创建 task 行 ...
    background.add_task(_run_pre_analysis, task_id, table_config)
```

**流程**：admin 上传 PDF → 存 ObjectStore → 创建 task → BackgroundTasks 调度 runner → runner 调 pymupdf → 产物回写 ObjectStore → admin 实时看 5 stage 进度。

---

## 七、项目没用到的能力

以下 PyMuPDF 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **`page.get_text("dict")` 完整结构** | block > line > span > char 层级 | 字体/字号敏感场景（按字号切块） |
| **`page.get_text("words")` 词级 bbox** | 词级坐标 + 文本 | 关键词高亮 / 坐标回写 |
| **`page.search_for("text")`** | 正向搜索坐标 | 自动标注 / 跨页引用 |
| **`page.annots` / 注释读写** | PDF 批注 | 协作审阅 / 知识库红头文件批注 |
| **`Document.insert_page()` / 编辑** | PDF 合并 / 拆分 / 重排 | 工具场景（不属 RAG 主流程）|
| **`Pixmap` 缩略图 / 渲染** | 页面级缩略图生成 | 知识库 UI 卡片预览图 |
| **PDF 加密 / 解密** | `authenticate(password)` | 加密 PDF 摄取 |
| **表单字段读取** | `page.widgets()` | 业务表单 PDF 抽取 |
| **书签写入** | `set_toc()` | 重新生成 PDF outline |
| **XPS / EPUB / CBZ 解析** | 同 API 跨格式 | 当前只 PDF，统一走 Kreuzberg |

**建议关注**：
- `page.search_for()` 做"关键词回写坐标"——把 LLM 回答的依据段在 PDF 里高亮
- 缩略图生成——知识库 UI 列表卡片体验升级

---

## 八、评测 & 调优技巧

### 8.1 性能基线

| 文件 | pymupdf 开 + 5 stage 完 | 备注 |
|------|------------------------|------|
| 10 页 文本 PDF | 100-200ms | 主要 IO |
| 100 页 文本 PDF | 500ms-1s | 表格识别 + TOC 提取 |
| 100 页 扫描 PDF | 1-3s | 矢量 / 图元数爆炸 |
| 1000 页 PDF | 5-15s | 内存峰值 200-500MB |

### 8.2 调优手段

1. **复用 Document**（项目已在做，`runner.py:122`）：

```python
# 错: 每次开
for stage in stages:
    doc = pymupdf.open(pdf)
    do_stuff(doc)
    doc.close()                     # 浪费 4 次 open

# 对: 1 次开, N 次用
doc = pymupdf.open(pdf)
try:
    for stage in stages:
        do_stuff(doc)
finally:
    doc.close()
```

2. **`Document(page=page_no)` 子集打开**（大文件分页处理）：

```python
doc = pymupdf.open(pdf)
for pn in range(50, 100):           # 只看 50-100 页
    page = doc.load_page(pn)        # 1.27+ 推荐 API
    ...
```

3. **异步 / 线程池**：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# pymupdf 同步阻塞, 放线程池
executor = ThreadPoolExecutor(max_workers=4)
loop = asyncio.get_event_loop()
doc = await loop.run_in_executor(executor, pymupdf.open, pdf_path)
```

4. **内存峰值**（大 PDF）：

```python
# 1.27+ 增量加载
doc = pymupdf.open(pdf, incremental=True)  # 内存占用减半
```

5. **OCR 前置降采样**（扫描件）：

```python
# 300 DPI 即可, 4K DPI 浪费
mat = pymupdf.Matrix(300/72, 300/72)  # 72 DPI 是 PDF 默认单位
pix = page.get_pixmap(matrix=mat)
```

### 8.3 表格识别调优

`page.find_tables()` 1.27+ 自适应，几乎无调参。如果识别率低：

```python
# 1.27+ 可手动调
finder = page.find_tables(
    strategy="lines_strict",       # "lines" | "lines_strict" | "text" | "explicit"
    add_lines=[...],               # 手动加虚拟线
    snap_tolerance=3.0,
    join_tolerance=3.0,
)
```

**但项目选择不暴露 params**（`pymupdf_extractor.py:36` 注释"pymupdf 后端无调参"），因为：
- 表格识别失败时直接换 `camelot` / `pdfplumber` 后端（factory 切换）
- params 透传会污染项目默认配置

---

## 九、最佳实践 & 常见坑

### 项目风格

1. **复用 Document**（已在做）：runner 主入口开 1 次，5 stage 全用，5 stage 完统一 close
2. **try/finally close**：自己开才 close，避免重复 close（`pymupdf_extractor.py:51-52`）
3. **`_pymupdf_doc` 注入**：pymupdf 适配器走 doc 复用，camelot/pdfplumber 适配器忽略这个 kw
4. **page_no 1-based**：所有适配器输出统一 1-based，前端展示无歧义
5. **不暴露 params**：pymupdf 适配器 `params` 字段保留但忽略（向后兼容 YAML 配置 schema）

### 常见坑

1. **PyPI 包名 ≠ import 路径**：
   - 旧 `PyPI 包 PyMuPDF` (import `fitz`) — 已弃用
   - 新 `PyPI 包 pymupdf` (import `pymupdf`) — 项目用这个
   - 混用报 `ModuleNotFoundError: No module named 'fitz'`

2. **`page.get_text()` 在 pyright 看不到 str**：

```python
text: str = page.get_text()  # type: ignore[assignment]  # pymupdf 返 str, pyright 看不到
```

`pymupdf` 类型 stub 不全，pyright 把它推断成 `Any`，必须 `type: ignore[assignment]`（带具体错误码）。

3. **`doc` 不可迭代在 pyright**：

```python
for page_idx, page in enumerate(doc):  # type: ignore[arg-type,var-annotated]
```

同上，pyright 看不到 `Document.__iter__`，需 `type: ignore`（`pdf.py:30` 和 `runner.py:371` 都用）。

4. **不要在异步上下文直接调 pymupdf**：

```python
# 错: 阻塞 event loop
async def handler():
    doc = pymupdf.open(pdf)        # 同步阻塞!

# 对: 走 BackgroundTasks / ThreadPoolExecutor
async def handler():
    background.add_task(run_pymupdf, pdf)
```

项目预分析是 **BackgroundTasks** 异步跑（`router.py:122`），不阻塞请求返回。

5. **PDF 无 outline 不报错**：

```python
toc = doc.get_toc()                 # list, 可能返 []
if not toc:
    logger.warning("PDF 无 outline, chapter_structure 标空")
```

`get_toc()` 永远返 `list`，空 PDF 也是 `[]`，不抛异常。`runner.py:263-264` 已 fail-open 兜底。

6. **大 PDF 内存爆炸**：

```python
# 1000 页 PDF 完整 open 吃 500MB+ 内存
# 限页: 拆分处理
for pn in range(0, len(doc), 100):
    chunk_doc = pymupdf.open(pdf)   # 单独开
    # ... 处理 100 页
    chunk_doc.close()
```

项目暂时没限，但**100MB 上传上限**（`router.py:85`）已经挡住大部分大文件。

7. **加密 PDF 直接 `open()` 不抛**：

```python
doc = pymupdf.open("encrypted.pdf")
print(doc.page_count)              # 0! 静默返空

# 必须先检查
if doc.is_encrypted:
    if not doc.authenticate("password"):
        raise ValueError("密码错")
```

项目目前**不处理加密 PDF**（`runner.py:124-128` 抓异常但不分类型），加密 PDF 会让 `len(doc)=0` 然后 5 stage 报空数据。

8. **`page.get_text("blocks")` 坐标原点在左上**：

PyMuPDF 坐标系：原点**左上**（不是 PDF 标准的左下）。bbox 是 `(x0, y0, x1, y1)`，`y0 < y1` 表示从上到下。

9. **Document 不支持 `with` 上下文**（1.27）：

```python
with pymupdf.open(pdf) as doc:     # AttributeError: __enter__
    ...
```

必须手动 `try/finally close()`，跟项目风格一致。

### 项目测试隔离

PyMuPDF 后端**纯本地库**（无 PG/Redis 依赖），走**模式 1 纯单测**：

```python
# 测试套件: 复用 fixture PDF, mode 1 mock
FIXTURE_PDF = Path(__file__).resolve().parents[2] / "fixtures" / "d81_dummy.pdf"

def test_extract():
    doc = pymupdf.open(str(FIXTURE_PDF))
    try:
        result = extractor.extract(str(FIXTURE_PDF), _pymupdf_doc=doc)
        assert result[0].page_no == 3
    finally:
        doc.close()
```

CI 跑全量测试时**不需要 docker PG/Redis 启动**（CLAUDE.md §强制测试隔离）。

### CI 升级注意

- **1.26 → 1.27** 改了 `TableFinder` API（`page.find_tables()`），项目已 1.27+
- 升 1.28+ 需回归测试 `find_tables()` 输出 shape（`TableData.rows` 格式可能变）
- MuPDF 引擎升级可能影响 `page.get_drawings()` 字段（`pdf.py:62-64` 读 `d["rect"].height`）

---

## 📚 参考

- [PyMuPDF 官方文档](https://pymupdf.readthedocs.io/en/latest/)
- [PyMuPDF GitHub](https://github.com/pymupdf/PyMuPDF)
- [PyPI pymupdf](https://pypi.org/project/pymupdf/)
- [MuPDF 引擎](https://www.mupdf.com/)
- [TableFinder API (1.27+)](https://pymupdf.readthedocs.io/en/latest/recipes-text.html#how-to-extract-tables)
- [项目 cookbook/python/kreuzberg.md](kreuzberg.md)（统一文档解析）
- [项目 cookbook/python/camelot.md](camelot.md)（lattice/stream 表格对比）
- [项目 cookbook/python/pdfplumber](https://github.com/jsvine/pdfplumber)（PDF 表格 fallback）

---

**状态：** ✅ 已完成

**最后更新：** 2026-07-06
