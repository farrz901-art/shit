# 多格式路由架构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 RAG 第一阶段从"只认 PDF/CAD"扩展为"按 converter 声明路由 + 4 桶分流（Document/Markdown/CAD/Unknown）"，支持 20+ 主流格式。

**Architecture:** 在 `Converter` 基类加 `extensions: list[str]` 声明字段；主入口递归扫 input_dir，按扩展名分到 4 个桶（document / md passthrough / cad / unknown），各桶独立流水线；document 桶复用现有 `PDFAnalyzer` 走复杂度路由（kreuzberg 简单 / mineru 复杂），CAD 走 EzdxfConverter，md 直接复制；未知格式打 [WARN] 跳过。**输出统一为子目录布局** `<output_dir>/<stem>/<stem>.md`。

**Tech Stack:** Python 3.14, pymupdf, kreuzberg 4.9.7, mineru (Docker), ezdxf 1.4.4, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-06-02-multi-format-routing-design.md`

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `src/pdf_processor/converters/__init__.py` | 改 | `Converter` 基类加 `extensions` 字段；Kreuzberg / Mineru 声明支持列表；`convert_batch` 输出改子目录布局；`classify_pdfs` → `classify_files` |
| `src/pdf_processor/cad_converter.py` | 改 | `EzdxfConverter` 加 `extensions = [".dxf", ".dwg"]` |
| `src/pdf_processor/markdown_passthrough.py` | 新建 | `MarkdownPassthroughHandler` 类，复制 .md 到 `<stem>/<stem>.md` |
| `main.py` | 改 | `process_files` 递归扫 + 4 桶分流 + 警告 unknown；`process_pdfs` 重命名 `process_documents` 接受外部 converters/files；新增 `process_passthrough` |
| `tests/test_converters.py` | 改 | 改 `classify_pdfs` 相关测试名；新增 `classify_files` 测试 |
| `tests/test_markdown_passthrough.py` | 新建 | 测：复制 / 子目录 / auto-mkdir / content 一致 / 不存在报错 |
| `tests/test_process_files_routing.py` | 新建 | 测：4 桶分流 / 递归 / unknown 警告 / md 直通 / dxf 走 CAD / pdf 走 document |
| `tests/fixtures/test_doc.md` | 新建 | 端到端 fixture：内容 `<h1>test</h1>` |

**Files that change together**：`converters/__init__.py` + `main.py`（架构核心）；`tests/` 跟实现一一对应（每加一个功能就有一个测试文件）。

---

## Task 1: Converter 基类加 extensions 字段

**Files:**
- Modify: `src/pdf_processor/converters/__init__.py:6-15`（Converter 基类）
- Test: `tests/test_converters.py`（加 TestConverterExtensions 类）

- [ ] **Step 1: 写测试**

在 `tests/test_converters.py` 末尾加：

```python
class TestConverterExtensions:
    """Converter.extensions 声明机制"""

    def test_kreuzberg_declares_pdf_and_office_and_image(self):
        """kreuzberg 支持 PDF + Office + 图片 + HTML + 邮件 + EPUB"""
        exts = KreuzbergConverter.extensions
        # PDF
        assert ".pdf" in exts
        # 图片（OCR 走 easyocr）
        assert ".png" in exts
        assert ".jpg" in exts
        assert ".jpeg" in exts
        # Office
        assert ".docx" in exts
        assert ".xlsx" in exts
        assert ".pptx" in exts
        # 网页
        assert ".html" in exts
        # 邮件
        assert ".eml" in exts
        # 电子书
        assert ".epub" in exts

    def test_mineru_declares_pdf_and_images(self):
        """mineru 实际只吃 PDF + 图片（容器命令 `mineru -p` 扫目录）"""
        exts = MineruConverter.extensions
        assert ".pdf" in exts
        assert ".png" in exts
        assert ".jpg" in exts
        assert ".jpeg" in exts
        # 不支持 Office（容器没装）
        assert ".docx" not in exts
```

- [ ] **Step 2: 跑测试确认红**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py::TestConverterExtensions -v
```

Expected: `AttributeError: type object 'KreuzbergConverter' has no attribute 'extensions'`

- [ ] **Step 3: 加 extensions 字段**

改 `src/pdf_processor/converters/__init__.py` 第 6-15 行（Converter 基类）：

```python
class Converter:
    """转换器基类"""
    name: str = "base"
    # 子类必须声明：本 converter 支持哪些扩展名（小写、含点）
    # 例：KreuzbergConverter.extensions = [".pdf", ".png", ".docx", ...]
    extensions: list[str] = []

    @staticmethod
    def can_handle(info) -> bool:
        return False
    ...
```

在 `KreuzbergConverter` class 内（第 33 行附近 `name = "kreuzberg"` 后面）加：

```python
    extensions = [
        # PDF
        ".pdf",
        # 图片（OCR 走 easyocr）
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",
        # Office
        ".docx", ".xlsx", ".pptx",
        # 网页
        ".html", ".htm",
        # 邮件
        ".eml", ".msg",
        # 电子书
        ".epub", ".rtf",
    ]
```

在 `MineruConverter` class 内（第 85 行附近 `name = "mineru"` 后面）加：

```python
    extensions = [".pdf", ".png", ".jpg", ".jpeg"]
```

- [ ] **Step 4: 跑测试确认绿**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py::TestConverterExtensions -v
```

Expected: 2 passed

- [ ] **Step 5: 跑全部测试确认没坏**

```bash
.venv/Scripts/python -m pytest tests/ 2>&1 | tail -3
```

Expected: 全部通过（可能 55 passed → 57 passed）

- [ ] **Step 6: Commit**

```bash
git add tests/test_converters.py src/pdf_processor/converters/__init__.py
git commit -m "feat(converters): 加 extensions 字段声明支持的格式

kreuzberg 声明：PDF + Office + 图片 + HTML + 邮件 + EPUB
mineru 声明：PDF + 图片
main.py 后续 Task 5 会用 extensions 路由"
```

---

## Task 2: EzdxfConverter 加 extensions

**Files:**
- Modify: `src/pdf_processor/cad_converter.py:44`（EzdxfConverter.name 后面）
- Test: `tests/test_cad_converter.py`（加 TestEzdxfExtensions 类）

- [ ] **Step 1: 写测试**

在 `tests/test_cad_converter.py` 末尾加：

```python
class TestEzdxfExtensions:
    """EzdxfConverter.extensions 声明"""

    def test_ezdxf_declares_dxf_and_dwg(self):
        from src.pdf_processor.cad_converter import EzdxfConverter
        exts = EzdxfConverter.extensions
        assert ".dxf" in exts
        assert ".dwg" in exts
```

- [ ] **Step 2: 跑测试确认红**

```bash
.venv/Scripts/python -m pytest tests/test_cad_converter.py::TestEzdxfExtensions -v
```

Expected: AttributeError

- [ ] **Step 3: 实现**

在 `src/pdf_processor/cad_converter.py` 第 44 行 `name: str = "ezdxf"` 后面加：

```python
    extensions = [".dxf", ".dwg"]
```

- [ ] **Step 4: 跑测试确认绿**

```bash
.venv/Scripts/python -m pytest tests/test_cad_converter.py::TestEzdxfExtensions -v
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_cad_converter.py src/pdf_processor/cad_converter.py
git commit -m "feat(cad): EzdxfConverter.extensions = ['.dxf', '.dwg']"
```

---

## Task 3: classify_files 替代 classify_pdfs

**Files:**
- Modify: `src/pdf_processor/converters/__init__.py:189-203`（classify_pdfs → classify_files）
- Test: `tests/test_converters.py`（改 TestClassifyPdfs → TestClassifyFiles）

- [ ] **Step 1: 写测试**

在 `tests/test_converters.py` 末尾加：

```python
from src.pdf_processor.cad_converter import EzdxfConverter  # 放进 imports 段


class TestClassifyFiles:
    """classify_files 按 converter 声明过滤"""

    def test_pdf_goes_to_kreuzberg_when_simple(self):
        """简单 PDF → kreuzberg"""
        from src.pdf_processor.converters import classify_files
        infos = {"a.pdf": PDFInfo(has_text=True, is_simple=True)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert "a.pdf" in result["kreuzberg"]
        assert "a.pdf" not in result["mineru"]

    def test_pdf_goes_to_mineru_when_complex(self):
        """复杂 PDF → mineru"""
        from src.pdf_processor.converters import classify_files
        infos = {"a.pdf": PDFInfo(has_text=False, is_simple=False)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert "a.pdf" in result["mineru"]
        assert "a.pdf" not in result["kreuzberg"]

    def test_png_only_goes_to_kreuzberg(self):
        """.png 只能分给声明了 .png 的 converter（kreuzberg）"""
        from src.pdf_processor.converters import classify_files
        infos = {"a.png": PDFInfo(has_text=True, is_simple=True)}
        result = classify_files(infos, list(CONVERTERS.values()))
        # 简单图片 + kreuzberg 支持 .png → 走 kreuzberg
        assert "a.png" in result["kreuzberg"]
        # mineru 暂未在测试里支持 .png（first version 保守）

    def test_docx_only_goes_to_kreuzberg(self):
        """.docx 只能分给 kreuzberg（mineru 不支持 Office）"""
        from src.pdf_processor.converters import classify_files
        infos = {"a.docx": PDFInfo(has_text=True, is_simple=True)}
        result = classify_files(infos, list(CONVERTERS.values()))
        assert "a.docx" in result["kreuzberg"]
        assert "a.docx" not in result["mineru"]

    def test_xyz_not_classified(self):
        """未注册扩展名返回空 grouped（任何 converter 都不分）"""
        from src.pdf_processor.converters import classify_files
        infos = {"a.xyz": PDFInfo(has_text=True, is_simple=True)}
        result = classify_files(infos, list(CONVERTERS.values()))
        # 所有 converter 都不分
        for name in CONVERTERS:
            assert "a.xyz" not in result[name]

    def test_dxf_goes_to_ezdxf(self):
        """.dxf 走 EzdxfConverter（在 CONVERTERS 里也注册一份方便统一调用）"""
        from src.pdf_processor.converters import classify_files
        infos = {"a.dxf": PDFInfo()}  # ezdxf 不走 can_handle
        # 把 EzdxfConverter 加到 converters list 里
        converters = list(CONVERTERS.values()) + [EzdxfConverter]
        result = classify_files(infos, converters)
        assert "a.dxf" in result["ezdxf"]
```

- [ ] **Step 2: 跑测试确认红**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py::TestClassifyFiles -v
```

Expected: ImportError / NameError (classify_files 不存在)

- [ ] **Step 3: 实现 classify_files**

在 `src/pdf_processor/converters/__init__.py` 第 189-203 行替换 `classify_pdfs`：

```python
def classify_pdfs(infos: dict) -> dict[str, list[str]]:
    """保留旧 API，向后兼容 → 直接调用 classify_files"""
    return classify_files(infos, list(CONVERTERS.values()))


def classify_files(infos: dict, converters: list) -> dict[str, list[str]]:
    """按 converter 声明的 extensions 过滤文件 → converter 桶

    Args:
        infos: {file_path: PDFInfo} —— 来自 PDFAnalyzer.analyze_all()
        converters: converter 实例列表或类列表（用 .extensions 和 .can_handle）

    Returns:
        {converter_name: [file_path, ...]} —— 一个文件最多分给一个 converter
    """
    grouped: dict[str, list[str]] = {}
    for conv in converters:
        # 类或实例都兼容
        name = getattr(conv, "name", None) or conv().name
        exts = getattr(conv, "extensions", None) or getattr(conv(), "extensions", [])
        grouped.setdefault(name, [])

    for file_path, info in infos.items():
        ext = Path(file_path).suffix.lower()
        for conv in converters:
            name = getattr(conv, "name", None) or conv().name
            exts = getattr(conv, "extensions", None) or getattr(conv(), "extensions", [])
            if ext not in exts:
                continue
            # ezdxf 不走 can_handle（不分析 PDFInfo），其它 converter 走
            if name == "ezdxf":
                grouped[name].append(file_path)
                break
            # 拿 converter 实例
            conv_instance = conv if not isinstance(conv, type) else conv()
            if conv_instance.can_handle(info):
                grouped[name].append(file_path)
                break
    return grouped
```

- [ ] **Step 4: 跑测试确认绿**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py::TestClassifyFiles -v
```

Expected: 6 passed

- [ ] **Step 5: 跑全部测试确认没坏（classify_pdfs 旧 API 还工作）**

```bash
.venv/Scripts/python -m pytest tests/ 2>&1 | tail -3
```

Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add tests/test_converters.py src/pdf_processor/converters/__init__.py
git commit -m "feat(converters): classify_files 按 converter.extensions 过滤

旧 classify_pdfs 保留作 wrapper（向后兼容）
新 classify_files 接受外部 converter 列表，支持任意扩展名"
```

---

## Task 4: MarkdownPassthroughHandler

**Files:**
- Create: `src/pdf_processor/markdown_passthrough.py`
- Create: `tests/test_markdown_passthrough.py`
- Create: `tests/fixtures/test_doc.md`

- [ ] **Step 1: 建 fixture**

`tests/fixtures/test_doc.md`：

```markdown
# 测试文档

这是测试用的 markdown 文件。
```

- [ ] **Step 2: 写测试**

`tests/test_markdown_passthrough.py`：

```python
"""MarkdownPassthroughHandler 单元测试"""
import os
import pytest
from src.pdf_processor.markdown_passthrough import MarkdownPassthroughHandler


SAMPLE_MD = "tests/fixtures/test_doc.md"


@pytest.mark.skipif(
    not os.path.exists(SAMPLE_MD),
    reason=f"测试 fixture 不存在: {SAMPLE_MD}",
)
class TestMarkdownPassthrough:
    """MarkdownPassthroughHandler 行为测试"""

    def test_name(self):
        """name 必须是 'passthrough'"""
        handler = MarkdownPassthroughHandler()
        assert handler.name == "passthrough"

    def test_passthrough_extensions(self):
        """passthrough_extensions 含 .md"""
        handler = MarkdownPassthroughHandler()
        assert ".md" in handler.passthrough_extensions

    def test_convert_copies_md_to_subdir(self, tmp_path):
        """.md 文件被复制到 <output>/<stem>/<stem>.md"""
        handler = MarkdownPassthroughHandler()
        src = SAMPLE_MD

        result = handler.convert(src, str(tmp_path))

        stem = os.path.splitext(os.path.basename(src))[0]
        expected = tmp_path / stem / f"{stem}.md"
        assert os.path.exists(expected), f"未复制到: {expected}"
        assert result == str(expected), f"convert 返回路径不对: {result}"

    def test_convert_content_identical(self, tmp_path):
        """复制后内容字节级一致"""
        handler = MarkdownPassthroughHandler()
        result = handler.convert(SAMPLE_MD, str(tmp_path))

        with open(result, encoding="utf-8") as f:
            dst_content = f.read()
        with open(SAMPLE_MD, encoding="utf-8") as f:
            src_content = f.read()
        assert dst_content == src_content

    def test_convert_auto_creates_dirs(self, tmp_path):
        """子目录不存在时自动创建（深嵌套）"""
        handler = MarkdownPassthroughHandler()
        deep = tmp_path / "a" / "b" / "c"
        assert not deep.exists()

        handler.convert(SAMPLE_MD, str(deep))

        stem = os.path.splitext(os.path.basename(SAMPLE_MD))[0]
        assert (deep / stem / f"{stem}.md").exists()

    def test_convert_nonexistent_raises(self, tmp_path):
        """源文件不存在时报 FileNotFoundError"""
        handler = MarkdownPassthroughHandler()
        with pytest.raises(FileNotFoundError):
            handler.convert(str(tmp_path / "nonexistent.md"), str(tmp_path))

    def test_convert_batch_returns_dict(self, tmp_path):
        """convert_batch 返回 {src: dst} 字典"""
        handler = MarkdownPassthroughHandler()
        results = handler.convert_batch([SAMPLE_MD], str(tmp_path))

        assert SAMPLE_MD in results
        assert os.path.exists(results[SAMPLE_MD])
```

- [ ] **Step 3: 跑测试确认红**

```bash
.venv/Scripts/python -m pytest tests/test_markdown_passthrough.py -v
```

Expected: ModuleNotFoundError: No module named 'src.pdf_processor.markdown_passthrough'

- [ ] **Step 4: 实现 MarkdownPassthroughHandler**

`src/pdf_processor/markdown_passthrough.py`：

```python
"""Markdown 直通处理器

不转换 .md 文件，直接复制到 <output>/<stem>/<stem>.md。
跟 Document / CAD 输出布局对齐。
"""
import shutil
from pathlib import Path


class MarkdownPassthroughHandler:
    """把 .md 原样复制到 output 子目录"""

    name: str = "passthrough"
    passthrough_extensions: list[str] = [".md"]

    def convert(self, file_path: str, output_dir: str) -> str:
        """复制单个 .md 到 <output>/<stem>/<stem>.md

        Args:
            file_path: 源 .md 路径
            output_dir: 输出根目录

        Returns:
            复制后文件绝对路径

        Raises:
            FileNotFoundError: 源文件不存在
        """
        src = Path(file_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"源文件不存在: {src}")

        subdir = Path(output_dir) / src.stem
        subdir.mkdir(parents=True, exist_ok=True)
        dst = subdir / src.name
        shutil.copy(src, dst)
        return str(dst)

    def convert_batch(self, file_paths: list[str], output_dir: str) -> dict[str, str]:
        """批量复制

        Returns:
            {src_path: dst_path}
        """
        return {p: self.convert(p, output_dir) for p in file_paths}
```

- [ ] **Step 5: 跑测试确认绿**

```bash
.venv/Scripts/python -m pytest tests/test_markdown_passthrough.py -v
```

Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/test_doc.md tests/test_markdown_passthrough.py src/pdf_processor/markdown_passthrough.py
git commit -m "feat(md-passthrough): 加 MarkdownPassthroughHandler

直接复制 .md 到 <output>/<stem>/<stem>.md
跟 Document / CAD 输出布局对齐"
```

---

## Task 5: KreuzbergConverter 输出改子目录布局

**Files:**
- Modify: `src/pdf_processor/converters/__init__.py:51-78`（KreuzbergConverter.convert_batch）
- Modify: `tests/test_converters.py`（TestKreuzbergConverter 相关测试可能要更新）

- [ ] **Step 1: 写测试**

在 `tests/test_converters.py` `TestKreuzbergConverter` 类里加：

```python
    def test_convert_batch_writes_to_stem_subdir(self, tmp_path):
        """输出改为 <output>/<stem>/<stem>.md（跟 mineru 对齐）"""
        from kreuzberg import ExtractionConfig
        from kreuzberg import extract_file_sync
        # 用 kreuzberg 直接产一个 markdown
        real_pdf = "pdfs/README.pdf"
        if not os.path.exists(real_pdf):
            pytest.skip(f"真实测试 PDF 不存在: {real_pdf}")

        pdf_copy = tmp_path / "sample.pdf"
        shutil.copy(real_pdf, pdf_copy)

        converter = KreuzbergConverter()
        out = tmp_path / "out"
        converter.convert_batch([str(pdf_copy)], str(out))

        # 期望: <out>/sample/sample.md
        expected = out / "sample" / "sample.md"
        assert expected.exists(), f"输出应在子目录: {expected}"
```

- [ ] **Step 2: 跑测试确认红**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py::TestKreuzbergConverter::test_convert_batch_writes_to_stem_subdir -v
```

Expected: AssertionError，文件写在 `out/sample.md` 而非 `out/sample/sample.md`

- [ ] **Step 3: 改 convert_batch 写子目录**

`src/pdf_processor/converters/__init__.py` 第 51-78 行替换 `KreuzbergConverter.convert_batch`：

```python
    def convert_batch(self, file_paths: list[str], output_dir: str) -> dict[str, str]:
        """kreuzberg 批量处理

        输出布局: <output_dir>/<stem>/<stem>.md（跟 mineru / CAD / md 直通对齐）
        """
        # 注意：必须用 *_sync 版。kreuzberg 4.9.7 中 batch_extract_files 是 async 协程函数，
        # 直接调用会拿到 coroutine 对象而不是 list，导致 'coroutine' object is not iterable
        # 以及 RuntimeWarning: coroutine ... was never awaited。
        from kreuzberg import batch_extract_files_sync, ExtractionConfig, OutputFormat

        os.makedirs(output_dir, exist_ok=True)

        config = ExtractionConfig(output_format=OutputFormat.MARKDOWN)
        results = batch_extract_files_sync(file_paths, config=config)

        output: dict[str, str] = {}
        for file_path, result in zip(file_paths, results):
            stem = Path(file_path).stem
            # 子目录布局
            subdir = os.path.join(output_dir, stem)
            os.makedirs(subdir, exist_ok=True)
            output_path = os.path.join(subdir, f"{stem}.md")
            if result.content:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(result.content)
                output[file_path] = result.content
            else:
                output[file_path] = ""
        return output
```

- [ ] **Step 4: 跑新测试确认绿**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py::TestKreuzbergConverter::test_convert_batch_writes_to_stem_subdir -v
```

Expected: 1 passed

- [ ] **Step 5: 跑全部测试看其他相关测试是否需要更新**

```bash
.venv/Scripts/python -m pytest tests/ 2>&1 | tail -10
```

如果 `TestKreuzbergConverter::test_convert_batch_real_pdf` 或 `test_convert_batch_auto_creates_output_dir` 失败，按需更新断言（输出路径改为子目录）。Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add tests/test_converters.py src/pdf_processor/converters/__init__.py
git commit -m "refactor(kreuzberg): 输出改子目录布局 <stem>/<stem>.md

跟 mineru / CAD / md 直通统一布局"
```

---

## Task 6: process_pdfs 拆成 process_documents + process_passthrough

**Files:**
- Modify: `main.py:62-170`（process_pdfs → process_documents）
- Modify: `main.py`（新增 process_passthrough）

- [ ] **Step 1: 写 process_passthrough 测试**

`tests/test_process_files_routing.py`（临时先单独建，等 Task 7 加 routing 测试时合并）：

```python
"""process_files 路由测试 + passthrough / documents 子流程测试"""
import os
import shutil
import pytest
from pathlib import Path
from main import process_passthrough, process_documents
from src.pdf_processor.markdown_passthrough import MarkdownPassthroughHandler


SAMPLE_MD = "tests/fixtures/test_doc.md"


@pytest.mark.skipif(
    not os.path.exists(SAMPLE_MD),
    reason=f"fixture 不存在: {SAMPLE_MD}",
)
class TestProcessPassthrough:
    def test_passthrough_copies_md_files(self, tmp_path):
        src_dir = tmp_path / "input"
        src_dir.mkdir()
        shutil.copy(SAMPLE_MD, src_dir / "doc1.md")
        shutil.copy(SAMPLE_MD, src_dir / "doc2.md")

        result = process_passthrough(
            [str(src_dir / "doc1.md"), str(src_dir / "doc2.md")],
            str(tmp_path / "output"),
        )

        assert result["processed"] == 2
        assert (tmp_path / "output" / "doc1" / "doc1.md").exists()
        assert (tmp_path / "output" / "doc2" / "doc2.md").exists()

    def test_passthrough_empty_returns_empty(self, tmp_path):
        result = process_passthrough([], str(tmp_path / "output"))
        assert result == {"processed": [], "errors": []}
```

- [ ] **Step 2: 跑测试确认红**

```bash
.venv/Scripts/python -m pytest tests/test_process_files_routing.py::TestProcessPassthrough -v
```

Expected: ImportError: cannot import name 'process_passthrough' from 'main'

- [ ] **Step 3: 在 main.py 加 process_passthrough**

在 `main.py` 末尾 `if __name__ == "__main__":` 前面加：

```python
def process_passthrough(file_paths: list[str], output_dir: str | None = None) -> dict:
    """处理 .md 直通文件列表

    Args:
        file_paths: .md 文件路径列表
        output_dir: 输出目录，传 None 则用 [paths].output_dir

    Returns:
        {"processed": [...], "errors": [...]}
    """
    from src.pdf_processor.config import get_paths
    paths = get_paths()
    output_path = Path(output_dir) if output_dir else paths.output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    if not file_paths:
        return {"processed": [], "errors": []}

    handler = MarkdownPassthroughHandler()
    print(f"扫描到 {len(file_paths)} 个 md 直通文件")

    results = {"processed": [], "errors": []}
    for file_path in file_paths:
        print(f">>> 复制 {Path(file_path).name}")
        try:
            dst = handler.convert(file_path, str(output_path))
            results["processed"].append({"file": Path(file_path).name, "dst": dst})
            print(f"  ✓ -> {Path(dst).relative_to(output_path)}")
        except Exception as e:
            results["errors"].append({"file": Path(file_path).name, "error": str(e)})
            print(f"  [ERROR] {e}")

    print("=" * 50)
    print("Markdown 直通处理完成")
    print("=" * 50)
    print(f"成功: {len(results['processed'])} | 失败: {len(results['errors'])}")
    return results
```

- [ ] **Step 4: 跑测试确认绿**

```bash
.venv/Scripts/python -m pytest tests/test_process_files_routing.py::TestProcessPassthrough -v
```

Expected: 2 passed

- [ ] **Step 5: 改 process_pdfs 为 process_documents**

把 `main.py` 第 62-170 行 `process_pdfs` 函数改名为 `process_documents` 并改签名：

```python
def process_documents(
    file_paths: list[str] | None = None,
    output_dir: str | None = None,
):
    """处理文档类文件（PDF / 图片 / Office / HTML / ...）

    Args:
        file_paths: 显式传入要处理的文件列表，传 None 时从 input_dir glob PDF
                    （兼容旧调用）
        output_dir: 输出目录，传 None 则用 [paths].output_dir
    """
    from src.pdf_processor.config import get_paths
    paths = get_paths()
    input_path = paths.input_dir
    output_path = Path(output_dir) if output_dir else paths.output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    # 兼容旧调用：没传 file_paths 就从 input_dir 找 PDF
    if file_paths is None:
        file_paths = [str(f) for f in input_path.glob("*.pdf")]
    print(f"扫描到 {len(file_paths)} 个文档文件")

    if not file_paths:
        return {"processed": [], "errors": []}

    # 1. 一次性分析全部
    print("=" * 50)
    print("分析文档复杂度")
    print("=" * 50)
    analyzer = PDFAnalyzer()
    infos = analyzer.analyze_all(file_paths)

    # 2. 分类
    from src.pdf_processor.converters import classify_files, CONVERTERS
    from src.pdf_processor.cad_converter import EzdxfConverter
    converters = list(CONVERTERS.values()) + [EzdxfConverter]  # 实际不分析 dxf，但保持接口一致
    grouped = classify_files(infos, converters)
    counts_line = " | ".join(f"{n}: {len(p)} 个" for n, p in grouped.items() if p)
    if counts_line:
        print(f"  {counts_line}")

    # 3. 打印每个文件的分析结果
    for file_path, info in infos.items():
        status = "简单" if info.is_simple else "复杂"
        print(f"{Path(file_path).name}")
        print(f"  类型: {status} | 页数: {info.page_count} | "
              f"文字: {info.has_text} | 图片: {info.image_count}")
        if info.reasons:
            print(f"  原因: {', '.join(info.reasons)}")

    # 4. 分组批量处理
    print("=" * 50)
    print("开始批量转换")
    print("=" * 50)

    results = {"processed": [], "errors": []}

    for converter_name, paths_in_group in grouped.items():
        if not paths_in_group:
            continue
        # ezdxf 单独路由（CAD 流水线处理）
        if converter_name == "ezdxf":
            print(f">>> {converter_name} {len(paths_in_group)} 个文件（走 CAD 流水线）")
            cad_results = process_cad_files(paths_in_group, str(output_path))
            # 汇总
            for r in cad_results["processed"]:
                results["processed"].append({"file": r["file"], "converter": "ezdxf"})
            for r in cad_results["errors"]:
                results["errors"].append({"file": r["file"], "converter": "ezdxf", "error": r["error"]})
            continue

        print(f">>> 使用 {converter_name} 处理 {len(paths_in_group)} 个文件")
        converter = get_converter(converter_name)

        try:
            batch_results = converter.convert_batch(paths_in_group, str(output_path))
            for file_path, content in batch_results.items():
                if content and not content.startswith("[ERROR]"):
                    results["processed"].append({
                        "file": Path(file_path).name,
                        "converter": converter_name,
                        "size": len(content),
                    })
                else:
                    results["errors"].append({
                        "file": Path(file_path).name,
                        "converter": converter_name,
                        "error": content or "内容为空",
                    })
                    print(f"  [ERROR] {Path(file_path).name}")
        except Exception as e:
            for file_path in paths_in_group:
                results["errors"].append({
                    "file": Path(file_path).name,
                    "converter": converter_name,
                    "error": str(e),
                })
            print(f"  [ERROR] {converter_name} 批量处理失败: {e}")

    print("=" * 50)
    print("处理完成")
    print("=" * 50)
    print(f"成功: {len(results['processed'])} | 失败: {len(results['errors'])}")
    return results


# 兼容旧 API
def process_pdfs(input_dir=None, output_dir=None):
    """旧 API，向后兼容 → 走 process_documents"""
    return process_documents(file_paths=None, output_dir=output_dir)
```

- [ ] **Step 6: 跑全部测试确认没坏**

```bash
.venv/Scripts/python -m pytest tests/ 2>&1 | tail -5
```

Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_process_files_routing.py
git commit -m "refactor(main): process_pdfs → process_documents

加 process_passthrough 单独处理 .md
process_pdfs 保留为 wrapper（向后兼容）"
```

---

## Task 7: process_files 主入口重写

**Files:**
- Modify: `main.py:13-59`（process_files）
- Test: `tests/test_process_files_routing.py`（加 TestProcessFilesRouting 类）

- [ ] **Step 1: 写测试**

在 `tests/test_process_files_routing.py` 末尾加：

```python
import os
import shutil
import tempfile
import pytest
from pathlib import Path
from main import process_files


SAMPLE_PDF = "pdfs/README.pdf"
SAMPLE_DXF = "tests/fixtures/sample.dxf"
SAMPLE_MD = "tests/fixtures/test_doc.md"


class TestProcessFilesRouting:
    """process_files 4 桶路由"""

    def test_routes_pdf_to_document_pipeline(self, tmp_path):
        """.pdf 走 Document 流水线"""
        if not os.path.exists(SAMPLE_PDF):
            pytest.skip(f"fixture 缺: {SAMPLE_PDF}")
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_PDF, in_dir / "test.pdf")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results["document"] is not None
        assert len(results["document"]["processed"]) == 1
        # 输出在子目录
        assert (tmp_path / "output" / "test" / "test.md").exists()

    def test_routes_dxf_to_cad_pipeline(self, tmp_path):
        """.dxf 走 CAD 流水线"""
        if not os.path.exists(SAMPLE_DXF):
            pytest.skip(f"fixture 缺: {SAMPLE_DXF}")
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_DXF, in_dir / "drawing.dxf")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results["cad"] is not None
        assert len(results["cad"]["processed"]) == 1
        assert (tmp_path / "output" / "drawing" / "drawing.md").exists()

    def test_routes_md_to_passthrough(self, tmp_path):
        """.md 走 passthrough 流水线"""
        if not os.path.exists(SAMPLE_MD):
            pytest.skip(f"fixture 缺: {SAMPLE_MD}")
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_MD, in_dir / "doc.md")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results["passthrough"] is not None
        assert len(results["passthrough"]["processed"]) == 1
        assert (tmp_path / "output" / "doc" / "doc.md").exists()

    def test_warns_unknown_format(self, tmp_path, capsys):
        """未支持格式打 [WARN] 跳过"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "weird.xyz").write_text("garbage")

        process_files(str(in_dir), str(tmp_path / "output"))
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out
        assert "weird.xyz" in captured.out

    def test_recursive_scan(self, tmp_path):
        """递归扫子目录"""
        if not os.path.exists(SAMPLE_PDF):
            pytest.skip(f"fixture 缺: {SAMPLE_PDF}")
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        sub = in_dir / "subdir"
        sub.mkdir()
        shutil.copy(SAMPLE_PDF, sub / "nested.pdf")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        # 嵌套文件被处理
        assert results["document"] is not None
        assert len(results["document"]["processed"]) == 1
        assert (tmp_path / "output" / "nested" / "nested.md").exists()
```

- [ ] **Step 2: 跑测试确认红**

```bash
.venv/Scripts/python -m pytest tests/test_process_files_routing.py::TestProcessFilesRouting -v
```

Expected: 全部 FAIL（因为 process_files 还没改）

- [ ] **Step 3: 重写 process_files**

替换 `main.py` 第 13-59 行的 `process_files`：

```python
def process_files(input_dir: str | None = None, output_dir: str | None = None):
    """统一入口：按扩展名分 4 桶（Document / Markdown / CAD / Unknown）

    流程:
        1. 递归扫 input_dir 所有文件
        2. 按扩展名分桶
        3. Document 桶走 process_documents（PDFAnalyzer → kreuzberg/mineru）
        4. Markdown 桶走 process_passthrough（直接复制）
        5. CAD 桶走 process_cad_files（EzdxfConverter）
        6. Unknown 桶打 [WARN] 跳过

    Args:
        input_dir:  输入目录，传 None 则从 config.toml 读 [paths].input_dir
        output_dir: 输出目录，传 None 则从 config.toml 读 [paths].output_dir
    """
    from src.pdf_processor.config import get_paths
    from src.pdf_processor.converters import CONVERTERS
    from src.pdf_processor.cad_converter import EzdxfConverter

    paths = get_paths()
    input_path = Path(input_dir) if input_dir else paths.input_dir
    output_path = Path(output_dir) if output_dir else paths.output_dir

    if not input_path.exists():
        print(f"输入目录不存在: {input_path}")
        return None

    # 1. 递归扫所有文件
    all_files = [f for f in input_path.rglob("*") if f.is_file()]

    # 2. 按扩展名分桶
    document_converters = list(CONVERTERS.values())  # kreuzberg + mineru
    cad_converters = [EzdxfConverter]

    buckets = {"document": [], "passthrough": [], "cad": [], "unknown": []}
    for f in all_files:
        ext = f.suffix.lower()
        if ext in MarkdownPassthroughHandler.passthrough_extensions:
            buckets["passthrough"].append(f)
        elif any(ext in c.extensions for c in cad_converters):
            buckets["cad"].append(f)
        elif any(ext in c.extensions for c in document_converters):
            buckets["document"].append(f)
        else:
            buckets["unknown"].append(f)

    print(f"扫描到 {len(buckets['document'])} 个文档 + "
          f"{len(buckets['cad'])} 个 CAD + "
          f"{len(buckets['passthrough'])} 个 md 直通")
    if buckets["unknown"]:
        print(f"  [WARN] {len(buckets['unknown'])} 个未知格式将被跳过")

    # 3. 警告 unknown
    for f in buckets["unknown"]:
        rel = f.relative_to(input_path) if f.is_relative_to(input_path) else f
        print(f"  [WARN] 不支持的格式，跳过: {rel}")

    results = {"document": None, "cad": None, "passthrough": None}

    # 4. 各自走各自流水线
    if buckets["passthrough"]:
        print("=" * 50)
        print("Markdown 直通")
        print("=" * 50)
        results["passthrough"] = process_passthrough(
            [str(f) for f in buckets["passthrough"]],
            str(output_path),
        )

    if buckets["cad"]:
        print("=" * 50)
        print("CAD 流水线")
        print("=" * 50)
        results["cad"] = process_cad_files(
            [str(f) for f in buckets["cad"]],
            str(output_path),
        )

    if buckets["document"]:
        print("=" * 50)
        print("Document 流水线")
        print("=" * 50)
        results["document"] = process_documents(
            [str(f) for f in buckets["document"]],
            str(output_path),
        )

    if not any(buckets.values()):
        print("未找到可处理的文件")

    return results
```

在文件顶部 import 段加：

```python
from src.pdf_processor.markdown_passthrough import MarkdownPassthroughHandler
```

- [ ] **Step 4: 跑新测试确认绿**

```bash
.venv/Scripts/python -m pytest tests/test_process_files_routing.py -v
```

Expected: 7 passed（2 passthrough + 5 routing）

- [ ] **Step 5: 跑全部测试**

```bash
.venv/Scripts/python -m pytest tests/ 2>&1 | tail -5
```

Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_process_files_routing.py
git commit -m "feat(main): process_files 4 桶路由

document / passthrough / cad / unknown
递归扫子目录，未支持格式 [WARN] 跳过"
```

---

## Task 8: 端到端真跑 + 文档更新

**Files:**
- Test: `tests/test_e2e_multi_format.py`（新建端到端）
- Modify: `README.md`（特性 + 项目结构）
- Modify: `docs/cad-converter.md`（加一句）
- Modify: `docs/README.md`（索引）

- [ ] **Step 1: 写端到端测试**

`tests/test_e2e_multi_format.py`：

```python
"""混合格式端到端测试

造一个 input_dir 装 .pdf + .md + .dxf + .xyz + 子目录里的 .png（如果支持）
跑 process_files，验证产物
"""
import os
import shutil
import pytest
from PIL import Image
from main import process_files


SAMPLE_PDF = "pdfs/README.pdf"
SAMPLE_DXF = "tests/fixtures/sample.dxf"
SAMPLE_MD = "tests/fixtures/test_doc.md"


@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="端到端慢测试（跑真实 kreuzberg），设 RUN_SLOW_TESTS=1 开启",
)
class TestMultiFormatEndToEnd:
    def test_mixed_input_routes_to_correct_pipelines(self, tmp_path):
        """混合 PDF + MD + DXF + 未知格式 → 4 桶分流"""
        for f in (SAMPLE_PDF, SAMPLE_DXF, SAMPLE_MD):
            if not os.path.exists(f):
                pytest.skip(f"fixture 缺: {f}")

        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_PDF, in_dir / "doc.pdf")
        shutil.copy(SAMPLE_MD, in_dir / "readme.md")
        shutil.copy(SAMPLE_DXF, in_dir / "drawing.dxf")
        (in_dir / "weird.xyz").write_text("garbage")

        # 造一个 1x1 PNG 测图片
        png = in_dir / "image.png"
        Image.new("RGB", (10, 10), color="red").save(str(png))

        results = process_files(str(in_dir), str(tmp_path / "output"))

        # PDF → Document 流水线
        assert results["document"] is not None
        assert any(r["file"] == "doc.pdf" for r in results["document"]["processed"])
        # MD → passthrough
        assert results["passthrough"] is not None
        assert any(r["file"] == "readme.md" for r in results["passthrough"]["processed"])
        # DXF → CAD
        assert results["cad"] is not None
        assert any(r["file"] == "drawing.dxf" for r in results["cad"]["processed"])
        # PNG → Document（kreuzberg 支持）
        # 注意：PNG 是否真能跑通看实际，不在这里强制断言

        # 验证子目录布局
        out = tmp_path / "output"
        assert (out / "doc" / "doc.md").exists()
        assert (out / "readme" / "readme.md").exists()
        assert (out / "drawing" / "drawing.md").exists()
```

- [ ] **Step 2: 跑测试（要 RUN_SLOW_TESTS）**

```bash
RUN_SLOW_TESTS=1 .venv/Scripts/python -m pytest tests/test_e2e_multi_format.py -v
```

Expected: 1 passed

- [ ] **Step 3: 更新 README.md**

把"功能特性"段改为：

```markdown
## 功能特性

- **多格式支持**：PDF / 图片（PNG/JPG/...）/ Office（DOCX/XLSX/PPTX）/ HTML / EPUB / EML 等 20+ 主流格式
- **格式自动路由**：按 converter 声明的扩展名自动分桶到 Document / Markdown / CAD 三条流水线
- **复杂度自动评估**：Document 流水线用 PDFAnalyzer 评估每个文件的复杂度
- **转换器分派**：
  - 简单文件 → `KreuzbergConverter`（纯本地）
  - 复杂文件 → `MineruConverter`（Docker 容器）
- **CAD 支持**：DXF/DWG → `EzdxfConverter`（ezdxf + ODA File Converter）
- **Markdown 直通**：.md 文件不转换，直接复制到 output
- **统一输出布局**：`<output_dir>/<stem>/<stem>.md`（所有流水线对齐）
- **递归扫描**：自动发现 input_dir 子目录里的可处理文件
```

把"项目结构"段更新（加 markdown_passthrough.py + test_e2e_multi_format.py + tests/fixtures/test_doc.md）

- [ ] **Step 4: 更新 docs/cad-converter.md**

在"快速开始"段后面加：

```markdown
> 💡 其它格式（.png / .docx / .html / .eml 等）走 Document 流水线，由 kreuzberg / mineru 处理。详见 [README.md](../../README.md)。
```

- [ ] **Step 5: 更新 docs/README.md 索引**

加：

```markdown
| [multi-format-routing.md](multi-format-routing.md) | 多格式路由架构设计 spec |
```

（spec 路径已在 [docs/superpowers/specs/2026-06-02-multi-format-routing-design.md](../superpowers/specs/2026-06-02-multi-format-routing-design.md)）

- [ ] **Step 6: 跑 ruff + 全部测试**

```bash
.venv/Scripts/python -m ruff check tests/ src/ main.py
.venv/Scripts/python -m pytest tests/ 2>&1 | tail -5
```

Expected: ruff all passed, all tests passed

- [ ] **Step 7: Commit**

```bash
git add tests/test_e2e_multi_format.py README.md docs/cad-converter.md docs/README.md
git commit -m "docs: 端到端测试 + README/cad-converter/README 文档更新

新支持 20+ 主流格式（PNG/JPG/DOCX/PPTX/HTML/EML/...）
格式自动路由，4 桶分流（document/md/cad/unknown）"
```

---

## Self-Review

- **Spec 覆盖检查**：
  - 4 桶路由 → Task 1/2/3/4/7 ✅
  - Converter.extensions 声明 → Task 1/2 ✅
  - classify_files → Task 3 ✅
  - MarkdownPassthroughHandler → Task 4 ✅
  - 输出子目录布局统一 → Task 4/5 ✅
  - 递归扫子目录 → Task 7 ✅
  - 警告 unknown → Task 7 ✅
  - .docx / .pptx / .png / .jpg 主流支持 → Task 1（extensions 声明）✅
  - 端到端验证 → Task 8 ✅
  - 文档更新 → Task 8 ✅

- **Placeholder 扫描**：无 "TBD" / "fill in" / 模糊描述，每步都有具体代码和命令 ✅

- **类型一致性**：
  - `classify_files(infos, converters)` 签名在 Task 3 定义，Task 6 引用 ✅
  - `MarkdownPassthroughHandler.convert(file_path, output_dir) -> str` 在 Task 4 定义，Task 6/7 引用 ✅
  - `process_files(input_dir, output_dir) -> dict[str, Any]` 在 Task 7 定义 ✅
  - `EzdxfConverter.extensions` 在 Task 2 定义，Task 3/7 引用 ✅

- **文件边界**：
  - `markdown_passthrough.py` 独立，单独职责
  - `main.py` 只做编排，每个 task 增量加一个函数
  - `converters/__init__.py` 是核心抽象，所有 task 都动它但局部修改

---

## 风险与回退

1. **Kreuzberg 对图片实际支持**：Task 8 端到端测验证，如果挂了 Task 1 的 extensions 列表回退到只有 .pdf + Office + HTML
2. **Kreuzberg 实际支持的扩展名不全**：只声明 kreuzberg _detect_mime_type_ 能正确识别的，其他加进来跑挂了再删
3. **mineru 容器对非 PDF 图片**：第一版 MineruConverter.extensions 只含 .pdf，PNG 走 kreuzberg 路径

---

## 总提交计划（8 个 commits）

1. `feat(converters): 加 extensions 字段声明支持的格式`
2. `feat(cad): EzdxfConverter.extensions = ['.dxf', '.dwg']`
3. `feat(converters): classify_files 按 converter.extensions 过滤`
4. `feat(md-passthrough): 加 MarkdownPassthroughHandler`
5. `refactor(kreuzberg): 输出改子目录布局 <stem>/<stem>.md`
6. `refactor(main): process_pdfs → process_documents`
7. `feat(main): process_files 4 桶路由`
8. `docs: 端到端测试 + README/cad-converter/README 文档更新`
