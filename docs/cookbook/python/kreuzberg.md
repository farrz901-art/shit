# Kreuzberg 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 启动](#二安装--启动)
- [三、核心概念](#三核心概念)
- [四、常用命令 & 用法速查](#四常用命令--用法速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、运维 & 最佳实践 + 常见坑](#八运维--最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

Kreuzberg 是一款统一的文档解析库，支持 PDF / Word / Excel / PowerPoint / 图片 OCR / 邮件（.eml）/ Markdown / HTML / TXT 等 50+ 格式。它用一个统一 API 把所有格式转成 Markdown / 文本，替代手工管理多个解析器。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Kreuzberg** | 统一文档解析 | 本项目**主力**（`src/ingest/converters/kreuzberg.py`）|
| **MarkItDown** | 微软文档解析 | 类似，Kreuzberg 更快 |
| **Unstructured** | 工业级解析 | 重，依赖多 |
| **pdfplumber / PyMuPDF** | 单格式 | 项目额外用 PyMuPDF 拿坐标 |
| **EasyOCR / Tesseract** | 仅 OCR | 跟 Kreuzberg 重叠 |
| **Apache Tika** | Java 生态 | 不跨语言 |

**Kreuzberg 解决的核心问题**：
- **统一 API**：50+ 格式，一行 `extract_file(path)` 搞定
- **OCR 内置**：图片扫描件自动 OCR
- **表格提取**：PDF / Excel 表格保留结构
- **Markdown 输出**：适合后续 LlamaIndex 切块嵌入

---

## 二、安装 & 启动

### 2.1 安装

```bash
# 项目已装 (pyproject.toml:22)
"kreuzberg[all]>=4.9.7",  # [all] 含 OCR (Tesseract) + 高级功能
```

### 2.2 系统依赖

Kreuzberg 依赖多个系统库，详见官方文档。项目用 `kreuzberg[all]`：

```bash
# Linux (Debian/Ubuntu)
sudo apt install -y tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
sudo apt install -y libpoppler-cpp-dev  # PDF 后端
sudo apt install -y pandoc  # 多格式转换

# macOS
brew install tesseract tesseract-lang
brew install poppler pandoc

# Windows
# 项目 Dockerfile 里处理了，dev 用 Docker
```

### 2.3 健康检查

```python
from kreuzberg import __version__
print(kreuzberg.__version__)  # 4.9.7+

# 测试 OCR
from kreuzberg import extract_file
result = extract_file("test.png")
print(result.content)
```

---

## 三、核心概念

### 1. ExtractionResult

```python
from kreuzberg import ExtractionResult, ExtractionConfig

result: ExtractionResult = extract_file("doc.pdf")
result.content       # str: Markdown / 纯文本
result.metadata      # dict: 页数、作者、创建时间...
result.tables        # list[Table]: 表格
result.images        # list[bytes]: 内嵌图片
```

### 2. MIME Type 自动检测

Kreuzberg 用文件扩展名 + magic bytes 自动判断格式：

```python
# 任何格式都行
extract_file("doc.pdf")       # PDF
extract_file("sheet.xlsx")    # Excel
extract_file("img.png")       # 图片 (OCR)
extract_file("mail.eml")      # 邮件
extract_file("slide.pptx")    # PPT
```

### 3. ExtractionConfig

```python
config = ExtractionConfig(
    output_format="markdown",   # "text" | "markdown" | "html"
    ocr_enabled=True,
    ocr_language="eng+chi_sim",
    force_ocr=False,            # 已有文字层时不强制 OCR
    chunk_size=None,            # None = 不切块
)
```

### 4. OCR

Kreuzberg 用 Tesseract 做 OCR，支持多语言：

- `eng`：英文
- `chi_sim`：简体中文
- `chi_tra`：繁体中文
- `jpn` / `kor` / `fra` / `deu`：其他语言

---

## 四、常用命令 & 用法速查

### 4.1 基本使用

```python
from kreuzberg import extract_file

result = extract_file("doc.pdf")
print(result.content)
```

### 4.2 异步

```python
from kreuzberg import extract_file_async

result = await extract_file_async("doc.pdf")
```

### 4.3 自定义配置

```python
from kreuzberg import extract_file, ExtractionConfig

config = ExtractionConfig(
    output_format="markdown",
    ocr_enabled=True,
    ocr_language="chi_sim+eng",  # 多语言
)
result = extract_file("scan.pdf", config=config)
```

### 4.4 批量

```python
from kreuzberg import batch_extract_files

results = batch_extract_files(["doc1.pdf", "doc2.docx", "img.png"])
for r in results:
    print(r.content[:100])
```

### 4.5 字节流（HTTP 上传）

```python
from kreuzberg import extract_bytes

result = extract_bytes(
    file_bytes,
    mime_type="application/pdf",
    filename="upload.pdf",   # 用于格式推断
)
```

### 4.6 表格提取

```python
config = ExtractionConfig(
    output_format="markdown",
    extract_tables=True,
)
result = extract_file("report.pdf", config=config)
for table in result.tables:
    print(table.markdown)
```

---

## 五、项目集成点

### 5.1 项目**主力**文档解析器

`pyproject.toml:22`：

```toml
"kreuzberg[all]>=4.9.7", # 通用文档解析 (PDF/Word/Excel/图片 OCR) (src/ingest/converters/kreuzberg.py)
```

### 5.2 项目 ingest 流程

```
上传文件 (PDF/DOCX/PNG/...)
    ↓
src/ingest/api.py:21 (FastAPI UploadFile)
    ↓
src/ingest/converters/kreuzberg.py:to_markdown()
    ↓
    ├── 简单格式 → Kreuzberg
    └── CAD / 特殊 → ezdxf / PyMuPDF
    ↓
Markdown 文本
    ↓
src/ingest/analyzers/ (chunk + metadata)
    ↓
src/retrieval/vector_store.add() (嵌入 + 入 PG)
```

### 5.3 项目 PDF 特殊处理

`src/ingest/analyzers/pdf.py` 用 PyMuPDF 拿文本块坐标（更细粒度），Kreuzberg 用于通用文本提取。

### 5.4 项目 CAD 特殊处理

`src/ingest/converters/cad.py` 用 ezdxf 处理 DWG/DXF，Kreuzberg 不覆盖这些。

---

## 六、项目代码示例

### 6.1 项目统一解析器

`src/ingest/converters/kreuzberg.py`（项目风格）：

```python
from kreuzberg import extract_file, ExtractionConfig, ExtractionResult
from pathlib import Path
import os
from loguru import logger

DEFAULT_CONFIG = ExtractionConfig(
    output_format="markdown",
    ocr_enabled=True,
    ocr_language="chi_sim+eng",
    extract_tables=True,
)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".md", ".txt", ".html", ".png", ".jpg", ".jpeg", ".tiff", ".eml"}

def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS

def to_markdown(file_path: str, config: ExtractionConfig | None = None) -> str:
    """统一文档解析 → Markdown"""
    if not is_supported(file_path):
        raise ValueError(f"Unsupported file: {file_path}")

    cfg = config or DEFAULT_CONFIG
    result: ExtractionResult = extract_file(file_path, config=cfg)
    logger.info("kreuzberg parse ok path={} chars={}", file_path, len(result.content))
    return result.content
```

### 6.2 HTTP 上传解析

```python
from kreuzberg import extract_bytes

@router.post("/api/ingest")
async def ingest(file: UploadFile = File(...), ...):
    # 1. 存 MinIO
    uri = await store.put_bytes(file.filename, await file.read(), mime=file.content_type)

    # 2. Kreuzberg 解析（不落盘，直接读 bytes）
    file_bytes = await file.read()
    result = extract_bytes(
        file_bytes,
        mime_type=file.content_type or "application/octet-stream",
        filename=file.filename,
    )

    # 3. 切块 + 嵌入 + 入库
    chunks = chunk_text(result.content)
    await ingest_chunks(chunks)

    return {"uri": uri, "chunks": len(chunks)}
```

### 6.3 OCR 扫描 PDF

```python
from kreuzberg import extract_file, ExtractionConfig

# 扫描 PDF（纯图片，无文字层）
config = ExtractionConfig(
    output_format="markdown",
    ocr_enabled=True,
    ocr_language="chi_sim+eng",   # 中英双语
    force_ocr=True,                # 强制 OCR（跳过文字层）
)
result = extract_file("scanned.pdf", config=config)
```

### 6.4 表格保留

```python
config = ExtractionConfig(
    output_format="markdown",
    extract_tables=True,
    table_format="github",  # GitHub 风格 markdown 表格
)
result = extract_file("report.pdf", config=config)
# Markdown 中 | col1 | col2 | 表格保留
```

### 6.5 项目切块 + 入库

```python
# src/ingest/pipeline.py (项目风格)
from llama_index.core.node_parser import SentenceSplitter
from src.ingest.converters.kreuzberg import to_markdown
from src.retrieval.vector_store import get_vector_store
from src.retrieval.embedder import get_embedder

async def ingest_file(file_path: str, dataset_id: str):
    # 1. Markdown 解析
    markdown_text = to_markdown(file_path)

    # 2. LlamaIndex 切块
    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    nodes = splitter.get_nodes_from_documents([Document(text=markdown_text, metadata={"source": file_path})])

    # 3. 入 PG 向量库
    store = get_vector_store()
    embedder = get_embedder()
    for node in nodes:
        embedding = embedder.get_text_embedding(node.text)
        await store.add_with_embedding(node, embedding)
```

### 6.6 自定义元数据

```python
result = extract_file("doc.pdf")
metadata = result.metadata or {}
# PDF 元数据: { "pages": 10, "title": "...", "author": "...", "created": "..." }

# 存进 chunks
for chunk in chunks:
    chunk.metadata["source_pages"] = metadata.get("pages")
    chunk.metadata["source_author"] = metadata.get("author")
```

---

## 七、项目没用到的能力

以下 Kreuzberg 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **多语言 OCR** | 自动检测语言 | 文档多语言混合 |
| **Layout 分析** | 保留段落 / 标题层级 | 文档结构敏感 |
| **公式识别** | OCR 数学公式 | 学术论文 |
| **手写识别** | 笔记扫描 | 手写 OCR |
| **二维码识别** | 提取图片中 QR | 票据场景 |
| **流式处理** | 边读边解析 | 大文件 |
| **PDF 加密支持** | 解密 PDF | 受保护文档 |
| **自定义后端** | 接入自研 OCR | 高级场景 |

**建议关注**：Layout 分析能保留 PDF 的层级结构，对 RAG 检索质量有帮助。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **系统依赖**：Tesseract + 语言包 + Poppler + Pandoc 都装齐
2. **OCR 性能**：Tesseract 单页 1-5 秒，PDF 100 页 ≈ 5-10 分钟
3. **并发**：CPU-bound，建议 `ProcessPoolExecutor` 而非线程池
4. **临时文件**：Kreuzberg 内部用 `/tmp`，确保空间足够
5. **升级**：kreuzberg[all] 升级要重装系统依赖

### 常见坑

1. **Tesseract 没装 / 没装中文**：

```bash
# 检查
tesseract --list-langs
# 没有 chi_sim → sudo apt install tesseract-ocr-chi-sim
```

2. **PDF 加密 / 损坏**：Kreuzberg 抛异常，必须 try/except

```python
try:
    result = extract_file("doc.pdf")
except Exception as e:
    logger.error("Kreuzberg failed: {}", e)
    raise HTTPException(500, "Document parse failed")
```

3. **大 PDF 卡死**：内存可能爆，限制页数

```python
config = ExtractionConfig(max_pages=100, ...)
```

4. **图片 OCR 识别率低**：

- 提升分辨率（300 DPI+）
- 黑白二值化预处理
- 用更好的 Tesseract 版本（5.x）

5. **中文 OCR 漏字**：训练数据偏差，用 `chi_sim`（简体）而不是 `chi_tra`（繁体）

6. **表格识别错乱**：PDF 表格样式千变万化，复杂表格可能识别失败

```python
# 退化策略：失败时用纯文本
try:
    result = extract_file("complex.pdf", config=table_config)
except TableExtractionError:
    result = extract_file("complex.pdf", config=text_only_config)
```

7. **异步用法**：跨 FastAPI 必须用 `extract_file_async`，否则阻塞 event loop

8. **版本升级 breaking**：kreuzberg 3 → 4 API 变了（`from kreuzberg import extract_file` 不变，但 config schema 可能变）

### 项目测试隔离

CI 测试**不要**连真实 Kreuzberg（避免系统依赖 + 启动慢）。Mock：

```python
from unittest.mock import patch

@patch("src.ingest.converters.kreuzberg.extract_file")
def test_ingest(mock_extract):
    mock_extract.return_value.content = "# Test\n\nThis is test markdown"
    mock_extract.return_value.metadata = {"pages": 1}
    # 测试逻辑
```

### 项目 OCR 资源监控

```python
# src/health/checks.py (推测): 检查 Tesseract 是否可用
def check_kreuzberg():
    try:
        import kreuzberg
        version = kreuzberg.__version__
        # 测试 OCR
        result = extract_file("health_test.png")  # 准备测试图
        return {"status": "ok", "version": version}
    except Exception as e:
        return {"status": "fail", "error": str(e)}
```

---

## 📚 参考

- [Kreuzberg 官方文档](https://github.com/Goldziher/kreuzberg)
- [Kreuzberg PyPI](https://pypi.org/project/kreuzberg/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [Tesseract 语言包](https://tesseract-ocr.github.io/tessdoc/Data-Files)
- [MarkItDown 替代方案](https://github.com/microsoft/markitdown)
- [项目 cookbook/db/postgres.md](postgres.md)（下游 pgvector 集成）

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25