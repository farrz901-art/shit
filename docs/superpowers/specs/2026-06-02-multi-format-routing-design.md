# 多格式路由架构设计

**日期**: 2026-06-02
**状态**: 已批准

## Context

RAG 项目第一阶段当前 main.py 硬编码了文件发现逻辑：

```python
# main.py
pdf_files = sorted(input_path.glob("*.pdf"))
cad_files = sorted(input_path.glob("*.dxf")) + sorted(input_path.glob("*.dwg"))
```

但底层 converter 实际支持更多格式：

| 工具 | 实际支持 |
|---|---|
| pymupdf | PDF / XPS / EPUB / MOBI / FB2 / CBZ / SVG / 图像 |
| kreuzberg 4.9.7 | PDF / DOCX / XLSX / PPTX / HTML / MD / EPUB / RTF / 邮件 / 图片（PNG/JPG/JPEG/GIF/WEBP/BMP/TIFF）|
| mineru | PDF / 图片 |
| ezdxf | DXF / DWG |

**问题**：input_dir 里放 .docx / .png / .html 等都被静默忽略。

**用户决策**：
1. 架构改成"扩展名 → 处理器"的可扩展注册表
2. 不为每种格式单独配 converter，让 converter 自己声明支持的扩展名
3. .md 文件**直接复制**到 output（passthrough）
4. 主流格式（word / ppt / png / jpg 等）必须支持
5. 递归扫描子目录
6. md 跟 PDF 走同样的子目录布局 `<stem>/<stem>.md`

## 关键设计

### 1. 4 类路由桶

| 类别 | 扩展名 | 处理器 |
|---|---|---|
| **Document** | .pdf .png .jpg .jpeg .gif .webp .bmp .tiff .docx .xlsx .pptx .html .htm .txt .eml .msg .epub | kreuzberg（简单）/ mineru（复杂），按 converter 声明过滤 |
| **Markdown** | .md | `MarkdownPassthroughHandler`（直接复制到 output）|
| **CAD** | .dxf .dwg | `EzdxfConverter` |
| **Unknown** | 其它 | `[WARN]` 跳过，不阻塞已知文件 |

### 2. Converter 基类扩展

```python
# src/pdf_processor/converters/__init__.py
class Converter:
    # 新增字段：声明支持哪些扩展名（小写、含点）
    extensions: list[str] = []
    name: str = "base"
    # ... 现有 can_handle / convert / convert_batch 不变

class KreuzbergConverter(Converter):
    # 实际支持：PDF + 图片 + Office + HTML + 邮件 + EPUB + ...
    extensions = [
        ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",
        ".docx", ".xlsx", ".pptx",
        ".html", ".htm", ".epub", ".rtf",
        ".eml", ".msg",
    ]
    name = "kreuzberg"
    # can_handle 不变（用 PDFInfo）

class MineruConverter(Converter):
    # mineru 实际只吃 PDF + 图片（容器命令 `mineru -p` 扫目录）
    extensions = [".pdf", ".png", ".jpg", ".jpeg"]
    name = "mineru"
```

### 3. ezdxf 不动

```python
# src/pdf_processor/cad_converter.py
class EzdxfConverter:
    # 已有等价字段 _CAD_EXTENSIONS，下面新增
    extensions = [".dxf", ".dwg"]
    # 其它不变
```

### 4. 新增 MarkdownPassthroughHandler

跟 Converter 接口对齐（同样的 `convert` / `convert_batch` 签名），但**没有 extensions 字段**或单独走"passthrough"通道。放 src/pdf_processor/markdown_passthrough.py。

输出布局：`<output_dir>/<stem>/<stem>.md`（跟 Document/CAD 一致）。

### 5. 主入口扫描

```python
# main.py
def process_files(input_dir, output_dir):
    paths = get_paths()
    input_path = Path(input_dir) if input_dir else paths.input_dir
    output_path = Path(output_dir) if output_dir else paths.output_dir

    if not input_path.exists():
        print(f"输入目录不存在: {input_path}")
        return None

    # 1. 递归扫所有文件
    all_files = [f for f in input_path.rglob("*") if f.is_file()]

    # 2. 按扩展名分桶
    buckets = {"passthrough": [], "cad": [], "document": [], "unknown": []}
    for f in all_files:
        ext = f.suffix.lower()
        if ext == ".md":
            buckets["passthrough"].append(f)
        elif ext in EzdxfConverter.extensions:
            buckets["cad"].append(f)
        elif any(ext in c.extensions for c in CONVERTERS.values()):
            buckets["document"].append(f)
        else:
            buckets["unknown"].append(f)

    print(f"扫描到 {len(buckets['document'])} 个文档 + "
          f"{len(buckets['cad'])} 个 CAD + "
          f"{len(buckets['passthrough'])} 个 md 直通")

    # 3. 警告 unknown
    for f in buckets["unknown"]:
        print(f"  [WARN] 不支持的格式，跳过: {f.relative_to(input_path)}")

    # 4. 各自走各自流水线
    results = {"passthrough": None, "cad": None, "document": None}
    if buckets["passthrough"]:
        print("=" * 50)
        print("Markdown 直通")
        print("=" * 50)
        results["passthrough"] = process_passthrough(buckets["passthrough"], output_path)

    if buckets["cad"]:
        print("=" * 50)
        print("CAD 流水线")
        print("=" * 50)
        results["cad"] = process_cad_files(buckets["cad"], output_path)

    if buckets["document"]:
        print("=" * 50)
        print("Document 流水线")
        print("=" * 50)
        results["document"] = process_documents(buckets["document"], output_path)

    return results
```

### 6. classify_files 替代 classify_pdfs

```python
def classify_files(infos, all_converters):
    """按 converter 声明过滤：不是所有 converter 都吃所有文档"""
    grouped = {c.name: [] for c in all_converters}
    for file_path, info in infos.items():
        ext = Path(file_path).suffix.lower()
        for converter in all_converters:
            if ext in converter.extensions and converter.can_handle(info):
                grouped[converter.name].append(file_path)
                break
    return grouped
```

`PDFAnalyzer` 内部用 pymupdf，对图片/PDF 都有效（pymupdf 吃 30+ 格式），所以**不需要重写**。`has_text` 对扫描件图片返回 False，触发了"无文字内容"→ complex → mineru。

### 7. 输出布局统一

**改动**：`KreuzbergConverter.convert_batch` 当前输出 `<output_dir>/<stem>.md`，改为 `<output_dir>/<stem>/<stem>.md`。

```python
def convert_batch(self, file_paths, output_dir):
    for file_path in file_paths:
        stem = Path(file_path).stem
        subdir = os.path.join(output_dir, stem)
        os.makedirs(subdir, exist_ok=True)
        out_path = os.path.join(subdir, f"{stem}.md")
        ...
```

**影响**：
- kreuzberg 输出从平铺改为子目录，跟 mineru / CAD / passthrough 对齐
- 已有测试 `test_resolve_md_path` 等可能要更新（待审）

### 8. MarkdownPassthroughHandler 简单实现

```python
# src/pdf_processor/markdown_passthrough.py
import shutil
from pathlib import Path


class MarkdownPassthroughHandler:
    """不转换 .md，直接复制到 <stem>/<stem>.md"""
    name = "passthrough"
    passthrough_extensions = [".md"]

    def convert(self, file_path: str, output_dir: str) -> str:
        src = Path(file_path)
        subdir = Path(output_dir) / src.stem
        subdir.mkdir(parents=True, exist_ok=True)
        dst = subdir / src.name
        shutil.copy(src, dst)
        return str(dst)

    def convert_batch(self, file_paths: list[str], output_dir: str) -> dict[str, str]:
        return {p: self.convert(p, output_dir) for p in file_paths}
```

## 关键文件

| 文件 | 动作 | 说明 |
|---|---|---|
| `src/pdf_processor/converters/__init__.py` | 改 | Converter 加 `extensions` 字段；KreuzbergConverter / MineruConverter 声明支持；convert_batch 输出改子目录 |
| `src/pdf_processor/cad_converter.py` | 改 | EzdxfConverter 加 `extensions = [".dxf", ".dwg"]` |
| `src/pdf_processor/markdown_passthrough.py` | 新建 | MarkdownPassthroughHandler |
| `src/pdf_processor/config.py` | 改 | `Paths` 不变；可能加 `is_recursive` 默认 True |
| `main.py` | 改 | process_files 重写（递归扫 + 4 桶 + 警告 unknown）；process_pdfs 改名 process_documents 接受外部 converters；新增 process_passthrough |
| `tests/test_converters.py` | 改 | classify_pdfs 改名 classify_files + 新测试 |
| `tests/test_markdown_passthrough.py` | 新建 | TDD 测：复制 / 输出子目录 / auto-mkdir / 跳过 / content 一致 |
| `tests/test_process_files_routing.py` | 新建 | TDD 测：4 桶分流 / unknown 警告 / md 直通 / dxf 走 CAD / pdf 走 document |
| `tests/test_e2e_multi_format.py` | 新建 | 真端到端：造 .pdf + .png + .md + .dxf + .xyz，跑 process_files，验产物 |
| `docs/cad-converter.md` | 改 | 加一句："其它格式走 Document 流水线" |
| `docs/README.md` | 改 | 文档索引加新文档 |
| `README.md` | 改 | 改"功能特性"为"支持 20+ 格式" |

## 实施步骤

**第 1 步：Converter 加 extensions 字段（TDD）**
- 写测试：`KreuzbergConverter.extensions` 含 `.pdf` / `.png` / `.docx` 等
- 写测试：`MineruConverter.extensions` 含 `.pdf` / `.png`
- 写测试：`EzdxfConverter.extensions` 含 `.dxf` / `.dwg`
- 实现：在每个 converter class 加 `extensions = [...]`

**第 2 步：classify_files 替代 classify_pdfs（TDD）**
- 写测试：`.png` 文件只分给声明了 `.png` 的 converter
- 写测试：`.docx` 只能分给 kreuzberg
- 写测试：`.xyz`（无人接）返回空 grouped
- 实现：照设计

**第 3 步：MarkdownPassthroughHandler（TDD）**
- 写测试：复制 .md 到 `<stem>/<stem>.md`
- 写测试：auto-mkdir
- 写测试：content 完全一致
- 实现

**第 4 步：KreuzbergConverter 输出改子目录布局**
- 改 convert_batch 写 `<output_dir>/<stem>/<stem>.md`
- 跑现有 test_convert_batch_real_pdf 验证（可能要更新断言）

**第 5 步：process_files 主入口重写（TDD）**
- 写测试：扫 4 类文件 → 4 桶分流
- 写测试：递归子目录
- 写测试：unknown 格式打 [WARN] 跳过
- 写测试：md 直通
- 实现

**第 6 步：process_pdfs → process_documents**
- 改函数名 + 接受外部 converter list + 接受外部 file list
- 保留 process_pdfs 作为 wrapper 兼容旧调用

**第 7 步：端到端真跑**
- 造 .pdf + .png + .md + .dxf + .xyz 的混合 input_dir
- 跑 process_files
- 验产物

**第 8 步：文档更新**
- 更新 README 特性 + 项目结构
- 更新 docs/cad-converter.md 加 "其它格式" 提示
- 更新 docs/README.md 索引

## 已知限制

1. **PDFAnalyzer 对图片的判定**：`has_text` 对扫描件图片返回 False（pymupdf 拿不到文字）→ 走 mineru 复杂路径，**正确**。
2. **mineru 处理图片**：容器命令是 `mineru -p <dir>`，里面会扫所有支持格式。**注意**：mineru 容器对非 PDF 图片支持可能不稳，第一版只声明 .pdf 即可，图片走 kreuzberg 路径（kreuzberg 对图片有 easyocr fallback）。**这一项要等真实跑 .png 验过才知道**。
3. **子目录递归**：会扫到 .venv / .git / __pycache__ 等。**第一次实现先不过滤**（用户有责任把 input_dir 摆干净），后续可加 `exclude_dirs` 配置。
4. **同名 .md 和 .pdf**：让冲突自然发生（用户决策）。**实际场景**：a.pdf → a/auto/a.md，a.md → a/a.md，**不冲突**（不同子目录）。

## 验证方法

```bash
# 1. 装依赖（如有新增）
uv sync

# 2. 跑所有单元测试
.venv/Scripts/python -m pytest tests/ -v

# 3. 跑端到端混合格式测试
RUN_SLOW_TESTS=1 .venv/Scripts/python -m pytest tests/test_e2e_multi_format.py -v

# 4. 手动跑真 input_dir
# 准备 input_dir 含 .pdf + .png + .md + .dxf + .docx + .xyz
.venv/Scripts/python main.py
```

## 风险点

1. **mineru 容器对非 PDF 图片支持**：第一版保守起见，KreuzbergConverter.extensions 不含 .png，**先验证 .docx / .html 等文本型格式走 kreuzberg 没问题**，再决定是否扩到图片。
2. **递归扫到非用户文件**（.git 等）：第一版不过滤。
3. **已有测试断言 kreuzberg 平铺输出**：要更新。
