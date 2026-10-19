# RAG Ingest 流水线演化（包重命名 + 压缩包支持）

**日期**：2026-06-02
**状态**：待用户审 → writing-plans
**作者**：brainstorming 会话产出

---

## Context

RAG 项目第一阶段已经从"只处理 PDF"演化为"多格式文档 → markdown"流水线（kreuzberg / mineru / ezdxf / md passthrough + 4 桶路由）。下一步按用户 `to-do.md` 5 项要求继续演化：

- **真新功能**：压缩包（zip）先解压再处理
- **真重构**：`pdf_processor` 包名不副实 → 重命名为 `rag_ingest`；`main.py` 不再是业务入口
- **已做保持**：7 类格式支持、测试 fixture 放 `tests/fixtures/`、先分类再批量调用

预期：项目从"PDF 处理小工具"演化为"可被上层 RAG 系统调用的 ingest 子系统"，且能处理压缩包这种真实场景下的输入。

---

## §范围（to-do.md 5 项对账）

| # | to-do 项 | 处理 |
|---|---------|------|
| 1 | 文件格式清单（pdf/图片/cad/word/excel/ppt） | 🔧 **重写分工** —— 详见下表 |
| 2 | 压缩包先解压再处理 | 🆕 **新功能** —— 详见 §压缩包支持 |
| 3 | main.py 内移 + 包重命名 | 🆕 **重构** —— 详见 §架构重组 |
| 4 | 测试 fixture 放 `tests/fixtures/` | ✅ **保持** —— `test_process_files_routing.py` 已在用 |
| 5 | 先分类再批量 + CAD 用 TEMP | ✅ **保持** —— `process_files` 已是"扫→4 桶→batch_convert" |

### 第 1 项：格式 → Converter 正确分工（用户 2026-06-02 修正）

| 格式 | Converter | 备注 |
|------|-----------|------|
| **PDF**（含简单 + 复杂） | `KreuzbergConverter`（简单） / `MineruConverter`（复杂） | kreuzberg `extensions=[".pdf"]`，按 PDFInfo 复杂度路由 |
| **图片**（png/jpg/jpeg/gif/webp/bmp/tiff） | `MineruConverter` | mineru 容器原生支持 OCR（多模态） |
| **CAD**（dwg/dxf） | `EzdxfConverter`（单独流水线） | 已有，零修改 |
| **Markdown** | `MarkdownPassthroughHandler` | 直通，零修改 |
| **Word/PPT**（docx/pptx） | `MineruConverter` | mineru 验证通过 |
| **Excel**（xls/xlsx） | **不支持** | `[WARN]` 跳过（mineru 验证 .xls 不支持，.xlsx 未验证保守不加） |
| **HTML/EML/EPUB** | **不支持** | `[WARN]` 跳过（to-do.md 未要求） |

### 关键修正：删除 kreuzberg 的多格式声明

**修正前**（当前 `KreuzbergConverter.extensions` 含 7 大类 20+ 扩展名）—— **错的**：
```python
extensions = [
    ".pdf",                                  # PDF
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",  # 图片（应给 mineru）
    ".docx", ".xlsx", ".pptx",               # Office（应给 mineru）
    ".html", ".htm",                         # 网页（to-do 未要求）
    ".eml", ".msg",                          # 邮件（to-do 未要求）
    ".epub", ".rtf",                         # 电子书（to-do 未要求）
]
```

**修正后**（kreuzberg 只 PDF；其他格式下沉到 mineru 或不支持）：
```python
# KreuzbergConverter.extensions
extensions = [".pdf"]

# MineruConverter.extensions（PDF + 图片 + Office 现代格式，验证通过）
extensions = [
    ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",  # 图片
    ".docx", ".pptx",                                            # Office 现代格式（.xls/.xlsx 不支持）
]
```

### 验证结果（2026-06-02，scripts/verify_mineru_office.py）

真实容器跑出来的结果：

| 格式 | mineru 容器支持 | 决策 |
|------|---------------|------|
| `.docx` | ✅ 支持（产出 1 个 .md） | 加入 MineruConverter.extensions |
| `.pptx` | ✅ 支持（产出 1 个 .md） | 加入 MineruConverter.extensions |
| `.xls` | ❌ 不支持（"No supported documents found"） | **不加入**，走 [WARN] 跳过 |
| `.xlsx` | ⚠️ **未验证** | **不加入**（保守），需要时再验证 |

**结论**：MineruConverter.extensions 加 `.docx` + `.pptx`，`.xls` + `.xlsx` 走 [WARN] 跳过。`.xls` 是 Office 97-2003 旧格式，现代办公越来越少；`.xlsx` 没在此次验证范围（fixture 只有 .xls），保守不加入。

**最终 MineruConverter.extensions**：

```python
extensions = [
    ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",  # 图片
    ".docx", ".pptx",                                              # Office 现代格式（验证通过）
    # .xls / .xlsx 不支持，to-do.md 的"excel"暂时走 [WARN] 跳过
]
```

**第 4 项** — 测试 fixture 路径（`tests/test_process_files_routing.py:8-10`）：

```python
SAMPLE_PDF = "pdfs/README.pdf"
SAMPLE_DXF = "tests/fixtures/sample.dxf"
SAMPLE_MD = "tests/fixtures/test_doc.md"
```

`tests/fixtures/` 已经是默认位置，`config.toml [paths].input_dir = "tests/fixtures"`。**无需新增代码**。

**第 5 项** — 4 桶路由 + 批量调用（`main.py:42-104`）：

```
递归扫 input_dir
  ↓
分桶 (document / passthrough / cad / unknown)
  ↓
各桶分别调 process_documents / process_passthrough / process_cad_files
  ↓
process_documents 内部：analyze_all → classify_files → convert_batch
  ↓
mineru 内部用 tempfile.TemporaryDirectory 隔离（防越界处理 kreuzberg 文件）
```

CAD 内部是 file-by-file `convert()` 循环，因为 ezdxf 没有 batch API（无 `ezdxf.readfiles()`）。**这是 ezdxf 库限制，不算违反"先分类再批量"原则**——CAD 之间没有 kreuzberg/mineru 这种异构性，loop 是合理选择。**无需新增代码**。

---

## §架构重组（to-do 第 3 项）

### 目录变化

```
# 改名前
rag/
├── main.py                    # 入口（业务 + 调用混在一起）
├── config.toml
└── src/pdf_processor/         # 包名名不副实（已支持 20+ 格式）
    ├── __init__.py
    ├── analyzer.py
    ├── converters/
    ├── cad_converter.py
    ├── cad_analyzer.py
    ├── cad_oda.py
    └── markdown_passthrough.py

# 改名后
rag/
├── main.py                    # 🪶 薄壳（2 行）
├── config.toml
└── src/rag_ingest/            # ✅ 新包名
    ├── __init__.py            # 公共导出
    ├── analyzer.py
    ├── converters/
    ├── cad_converter.py
    ├── cad_analyzer.py
    ├── cad_oda.py
    ├── markdown_passthrough.py
    ├── archive_handler.py     # 🆕 §压缩包支持
    └── pipeline.py            # 🆕 原 main.py 业务逻辑迁入
```

### 入口策略

- **root `main.py` 保留**（用户原话："光删除main.py不行，功能必须保留"），但**只剩 2 行**：
  ```python
  from src.rag_ingest.pipeline import process_files
  if __name__ == "__main__":
      process_files()
  ```
- 业务逻辑（`process_files` / `process_documents` / `process_cad_files` / `process_passthrough` / `process_pdfs` 兼容包装）**全部迁入** `src/rag_ingest/pipeline.py`
- 调用方式不变：`uv run python main.py` 照常工作
- 编程调用：`from src.rag_ingest import process_files`

### 向后兼容

- **不留 shim**（用户决策），一次切干净
- 旧 `process_pdfs()` 仍保留为兼容包装（写在 `pipeline.py` 里），不删
- 旧路径 `from src.pdf_processor import ...` 全部失败（README 写明升级指南）
- 影响面：全部 Python import + README + docs

### 影响范围清单

需要改 import 路径的文件（按估算）：

```
src/rag_ingest/__init__.py
src/rag_ingest/analyzer.py
src/rag_ingest/cad_converter.py
src/rag_ingest/cad_analyzer.py
src/rag_ingest/cad_oda.py
src/rag_ingest/markdown_passthrough.py
src/rag_ingest/converters/__init__.py
src/rag_ingest/pipeline.py            # 新建
src/rag_ingest/archive_handler.py     # 新建
main.py                               # 缩成 thin shim
tests/test_analyzer.py
tests/test_converters.py
tests/test_cad_converter.py
tests/test_cad_analyzer.py
tests/test_cad_oda.py
tests/test_markdown_passthrough.py
tests/test_process_files_routing.py
tests/test_e2e_multi_format.py        # 新建（已存在）
docs/cad-converter.md
docs/cad-ezdxf-best-practices.md
docs/mineru-output-for-rag.md
README.md
```

---

## §压缩包支持（to-do 第 2 项）

### 核心思路：解压后并入文件池，复用 4 桶路由

压缩包**不直接进桶**，而是**先解压到临时目录**，再把解压产物当作普通文件走现有 4 桶路由。这样：
- ✅ 压缩包内的 `.pdf` / `.dxf` / `.md` / `.docx` 全部被现有逻辑识别
- ✅ 复杂度分析、批量转换、子目录布局全复用
- ✅ TEMP 用 `tempfile.TemporaryDirectory` 包住整个 `process_files()`，结束自动清理

### 数据流

```
process_files(input_dir, output_dir):
    with tempfile.TemporaryDirectory(prefix="rag_ingest_") as temp_root:
        # 1. 扫 input_dir
        raw_files = list(input_path.rglob("*"))

        # 2. 找所有 .zip，逐个解压到 <temp_root>/<archive_stem>/
        archives = [f for f in raw_files if archive_handler.is_supported(f)]
        for archive in archives:
            archive_handler.extract(archive, temp_root, max_depth=...)

        # 3. 收集"待处理文件池" = raw_files (非压缩包) + 解压产物
        pool = collect_pool(input_path, temp_root)

        # 4. 4 桶路由（已有逻辑，零修改）
        buckets = route(pool)

        # 5. 各自走 process_documents / process_cad_files / process_passthrough

    # 临时目录自动清理
```

### 新模块：`src/rag_ingest/archive_handler.py`

```python
class ArchiveHandler:
    """解压压缩包到目标目录"""

    def __init__(
        self,
        max_depth: int = 1,
        max_total_size: int = 1 << 30,   # 1 GiB，防 zip bomb
        max_file_count: int = 10_000,    # 防 zip bomb
    ):
        ...

    @property
    def supported_extensions(self) -> list[str]:
        return [".zip"]  # 当前只 zip（用户决策）

    def is_supported(self, archive_path: Path) -> bool: ...
    def extract(self, archive_path: Path, target_dir: Path, depth: int = 1) -> list[Path]:
        """解压到 <target_dir>/<archive_stem>/，返回解压出的所有文件路径

        Raises:
            UnsupportedArchiveError: 不支持的格式
            ArchiveSecurityError: 超过大小/文件数上限 / Zip Slip
            ArchivePasswordError: 加密压缩包
            ArchiveCorruptError: 损坏的压缩包
        """
```

### 自定义异常

```python
class ArchiveError(Exception):
    """压缩包处理基类异常"""

class UnsupportedArchiveError(ArchiveError): ...
class ArchiveSecurityError(ArchiveError): ...
class ArchivePasswordError(ArchiveError): ...
class ArchiveCorruptError(ArchiveError): ...
```

### 配置项（`config.toml` 新增）

```toml
[archive]
# 压缩包嵌套解压深度（1 = 不递归，2/3 = 递归几层；用户决策：可配置，默认 1）
max_depth = 1
# 解压总大小上限（字节，默认 1 GiB，防 zip bomb）
max_total_size = 1073741824
# 解压文件总数上限（防 zip bomb）
max_file_count = 10000
```

### 错误处理策略

| 异常 | 行为 |
|------|------|
| 不支持的格式（`.rar`/`.7z`/其他） | `[WARN]` 跳过，"如需支持请手动解压" |
| 加密 zip | `[ERROR]` 跳过，"请手动解压后重试" |
| 超过大小/文件数上限 | `[ERROR]` 跳过该压缩包（不阻断其他） |
| 单文件损坏 | `[ERROR]` 该文件跳过，压缩包其他文件继续 |
| 嵌套超过 max_depth | 内层 zip 当作未识别格式，跳过（不报错） |
| Zip Slip（路径穿越） | `extract` 时校验 `Path.resolve().is_relative_to(target_dir)`，违规抛 `ArchiveSecurityError` |

### 集成点：只改 `process_files`

3 处插入（在 4 桶路由前后）：

1. 顶层加 `tempfile.TemporaryDirectory`
2. 扫到的 `archives` 列表逐个解压
3. 文件池 = `raw_files - archives + 解压产物`

4 桶路由、批量转换、子目录布局 —— **零修改**。

---

## §关键文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `src/pdf_processor/` → `src/rag_ingest/` | **git mv** | 全包重命名 |
| `main.py` | 改 | 缩成 thin shim（2 行） |
| `src/rag_ingest/pipeline.py` | 新建 | 原 main.py 业务逻辑 |
| `src/rag_ingest/archive_handler.py` | 新建 | 压缩包解压核心 |
| `src/rag_ingest/__init__.py` | 改 | 公共导出（含 `process_files` / `process_pdfs` / `PDFAnalyzer` / `get_converter` 等） |
| `src/rag_ingest/converters/__init__.py` | 改 | import 路径 `src.pdf_processor.*` → `src.rag_ingest.*` |
| `src/rag_ingest/analyzer.py` | 改 | 同上 |
| `src/rag_ingest/cad_converter.py` | 改 | 同上 |
| `src/rag_ingest/cad_analyzer.py` | 改 | 同上 |
| `src/rag_ingest/cad_oda.py` | 改 | 同上 |
| `src/rag_ingest/markdown_passthrough.py` | 改 | 同上 |
| `config.toml` | 改 | 新增 `[archive]` 段 |
| `pyproject.toml` | 改 | 无依赖新增（zip 用 std lib） |
| `README.md` | 改 | 命令升级指南 + 压缩包说明 + 移除 PDF 命名 |
| `docs/*.md` | 改 | import 路径同步 |
| `tests/test_process_files_routing.py` | 改 | import 改 `src.rag_ingest` |
| `tests/test_archive_handler.py` | 新建 | 单元测试 |
| `tests/test_archive_integration.py` | 新建 | 集成测试 |
| `tests/test_e2e_archive.py` | 新建 | 端到端（gated by `RUN_SLOW_TESTS=1`） |
| `tests/test_no_stale_pdf_processor_imports.py` | 新建 | 回归：grep 老路径必须 0 命中 |
| `tests/fixtures/sample_archive.zip` | 新建 | fixture（真 zip，含 PDF+md） |

---

## §测试策略

### 单元测试 `tests/test_archive_handler.py`

- `test_is_supported_zip` / `test_is_supported_unsupported_returns_false`
- `test_extract_zip_returns_list_of_files`
- `test_extract_creates_subdir_named_after_archive_stem`（防解压冲突）
- `test_extract_oversize_raises_security_error`
- `test_extract_too_many_files_raises_security_error`
- `test_extract_password_protected_raises_password_error`
- `test_extract_corrupt_zip_raises_friendly_error`
- `test_extract_blocks_zip_slip`（路径穿越防御）

### 集成测试 `tests/test_archive_integration.py`

- `test_process_files_with_zip_in_input_extracts_and_routes`
- `test_process_files_mixed_zip_and_plain_files`
- `test_process_files_unsupported_archive_warns_and_continues`
- `test_process_files_cleans_temp_after_completion`
- `test_process_files_nested_zip_max_depth_1_skips_inner`
- `test_process_files_nested_zip_max_depth_2_extracts_inner`

### 端到端 `tests/test_e2e_archive.py`（`RUN_SLOW_TESTS=1`）

- fixture `tests/fixtures/sample_archive.zip`（真 zip，含真 PDF+DXF+md）
- 跑全流水线，断言输出结构

### 架构重组回归

- 旧 `test_process_files_routing.py` 改 import 到 `src.rag_ingest` 跑通（行为不变）
- `test_no_stale_pdf_processor_imports.py`：grep 全代码 `from src.pdf_processor` 必须 0 命中

---

## §风险与缓解

| 风险 | 缓解 |
|------|------|
| 包重命名影响 ~20+ 文件 import | 一次性 `git mv` + sed 改 + 跑全套测试 |
| 路径穿越攻击（Zip Slip） | `Path.resolve().is_relative_to` 校验 |
| Zip bomb | `max_total_size` + `max_file_count` 双保险 |
| 解压冲突（同名文件覆盖） | `<temp_root>/<archive_stem>/...` 命名空间隔离 |
| 临时目录未清理（异常路径） | `with tempfile.TemporaryDirectory()` 上下文管理器 |
| 加密 zip 死循环 | 显式检测 `RuntimeError("File encrypted")`，不尝试密码字典 |
| 嵌套 zip 死循环 | `max_depth` 硬限制 |
| 旧 import 在用户 jupyter 残留 | README 醒目位置写"升级指南"（用户决策不留 shim） |
| `main.py` 误以为还有业务逻辑 | 注释里写明 thin shim 性质 |

---

## §决策记录

| 决策 | 选项 | 选定 |
|------|------|------|
| 新包名 | rag_ingest / ingest / pipeline / docflow | **rag_ingest** |
| 压缩包范围 | zip / zip+rar / zip+rar+7z / 全格式+软依赖 | **只 zip** |
| 向后兼容 | 永久 shim / 不留 shim / 临时 shim | **不留 shim** |
| 嵌套策略 | 不递归 / 递归 / 可配置深度 | **可配置深度（默认 1）** |
| `main.py` 处理 | 删除 / 保留 thin shim | **保留 thin shim** |
| `process_pdfs` | 删 / 留兼容包装 | **留兼容包装**（不变） |
| 解析 zip 库 | std lib zipfile / zipfile36 | **stdlib zipfile**（零依赖） |
| 旧 doc 路径 | 一次性改 / 保留重定向 | **一次性改** |

---

## §验证方法

```bash
# 1. 重命名 + 改 import（一次性 git mv + sed 改）
git mv src/pdf_processor src/rag_ingest
# 用脚本批量替换 import 路径
python scripts/rename_imports.py  # 一次性脚本，跑完删

# 2. 跑全部测试
uv run pytest

# 3. 单独跑压缩包测试
uv run pytest tests/test_archive_handler.py tests/test_archive_integration.py -v

# 4. 跑真实端到端（fixture zip）
RUN_SLOW_TESTS=1 uv run pytest tests/test_e2e_archive.py -v

# 5. 端到端：跑真实含 zip 的 input_dir
uv run python main.py  # 行为应跟改名前一致
```

---

## §可复用现有模式

- **4 桶路由**：[main.py:48-58](main.py#L48-L58) 的 `process_files` 分桶逻辑（不动）
- **批量转换**：[src/pdf_processor/converters/__init__.py:73-108](src/pdf_processor/converters/__init__.py#L73-L108) 的 `KreuzbergConverter.convert_batch`（不动）
- **子目录布局**：`<output>/<stem>/<stem>.md`（不动）
- **TEMP 隔离模式**：[src/pdf_processor/converters/__init__.py:164-183](src/pdf_processor/converters/__init__.py#L164-L183) 的 `tempfile.TemporaryDirectory` for mineru（已用同样模式）
- **TDD 守门**：[tests/test_process_files_routing.py](tests/test_process_files_routing.py) 的 `if not exists: pytest.skip()` 模式
- **错误处理风格**：中文 `print` + `[WARN]` / `[ERROR]` 前缀（main.py 已用）
- **docstring 风格**：中文 + "修复前 X / 修复后 Y" 段

---

## §后续（不在本 spec）

- CAD 多路融合（VLM 路线）—— 用户已决策走 ezdxf + SVG，暂不动
- 真正的 RAG 上层（chunker / embedder / 向量库）—— 项目外
- web UI / API 层 —— 项目外
