# ingest 单文件支持 + README 拆分 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `uv run python main.py ingest <path>` 支持单文件 / 单目录 / 默认 config 三种用法，并把 README 拆分成 5 个 `docs/` 文件。

**Architecture:**
- 新增顶层入口 `process_path(path)` 到 `src/rag/ingest/pipeline.py`，三路分发
- `main.py` 的 `p_ingest` 加 `path` 位置参数（`nargs="?"`）
- 复用现有 `process_documents / process_cad_files / process_passthrough`（已经接 `list[str]`，完美支持单文件）
- README 保留部署+快速启动+链接，详细内容拆到 `docs/`

**Tech Stack:** Python 3.11+, pytest, argparse, pathlib

---

## 文件结构

### 修改
- `src/rag/ingest/pipeline.py` — 加 `process_path` + `_process_single_file`
- `main.py` — `p_ingest` 加位置参数，`cmd_ingest` 接 `path` kwarg
- `README.md` — 精简到 ~50 行，加 docs 链接

### 新增
- `tests/rag/ingest/test_pipeline_path.py` — 8 个 `process_path` 单测
- `tests/test_main_cli.py` — 3 个 argparse 解析测试
- `tests/test_docs_structure.py` — 3 个文档结构测试
- `docs/deployment.md` — 部署
- `docs/architecture.md` — 架构
- `docs/product-decoder.md` — 产品解析器
- `docs/ingestion.md` — RAG 流水线
- `docs/dev-conventions.md` — 开发规范

---

## Task 1: 写 `process_path` 红测试

**Files:**
- Create: `tests/rag/ingest/test_pipeline_path.py`

- [ ] **Step 1: 创建测试文件**

```python
"""process_path 顶层入口测试

ingest 单文件支持 (2026-06-08):
- process_path 是单文件 / 单目录 / None 三路分发的入口
- 行为：单文件按扩展名路由到现有 process_documents/cad/passthrough
"""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestProcessPathNone:
    """path=None → 走 config 默认目录"""

    def test_none_delegates_to_process_files_no_args(self):
        """path=None 时 process_path 调 process_files() 无参"""
        from src.rag.ingest.pipeline import process_path
        with patch("src.rag.ingest.pipeline.process_files") as mock_pf:
            result = process_path(None)
            mock_pf.assert_called_once_with()

    def test_none_returns_process_files_result(self):
        """path=None 时返回值是 process_files 的返回值"""
        from src.rag.ingest.pipeline import process_path
        sentinel = {"document": [], "cad": [], "passthrough": []}
        with patch("src.rag.ingest.pipeline.process_files", return_value=sentinel) as mock_pf:
            result = process_path(None)
            assert result is sentinel


class TestProcessPathDirectory:
    """path=目录 → 调 process_files(input_dir=...)"""

    def test_directory_delegates_to_process_files_with_input_dir(self, tmp_path):
        """目录路径 → process_files(input_dir=str(dir))"""
        from src.rag.ingest.pipeline import process_path
        with patch("src.rag.ingest.pipeline.process_files") as mock_pf:
            process_path(str(tmp_path))
            mock_pf.assert_called_once_with(input_dir=str(tmp_path))

    def test_zip_file_delegates_to_process_files_with_input_dir(self, tmp_path):
        """zip 文件路径 → 透传给 process_files(input_dir=...)（让 zip 解压逻辑接管）"""
        from src.rag.ingest.pipeline import process_path
        zip_path = tmp_path / "bundle.zip"
        zip_path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # 最小 zip EOCD
        with patch("src.rag.ingest.pipeline.process_files") as mock_pf:
            process_path(str(zip_path))
            mock_pf.assert_called_once_with(input_dir=str(zip_path))


class TestProcessPathSingleFile:
    """path=单文件 → 按扩展名路由到对应 list[str] 入口"""

    def test_pdf_routes_to_process_documents(self, tmp_path):
        """.pdf → process_documents([file])"""
        from src.rag.ingest.pipeline import process_path
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        with patch("src.rag.ingest.pipeline.process_documents") as mock_pd:
            process_path(str(pdf))
            mock_pd.assert_called_once()
            args, _ = mock_pd.call_args
            assert args[0] == [str(pdf)]

    def test_dxf_routes_to_process_cad_files(self, tmp_path):
        """.dxf → process_cad_files([file])"""
        from src.rag.ingest.pipeline import process_path
        dxf = tmp_path / "drawing.dxf"
        dxf.write_bytes(b"0\n")
        with patch("src.rag.ingest.pipeline.process_cad_files") as mock_pc:
            process_path(str(dxf))
            mock_pc.assert_called_once()
            args, _ = mock_pc.call_args
            assert args[0] == [str(dxf)]

    def test_dwg_routes_to_process_cad_files(self, tmp_path):
        """.dwg → process_cad_files([file])（跟 .dxf 同路由）"""
        from src.rag.ingest.pipeline import process_path
        dwg = tmp_path / "drawing.dwg"
        dwg.write_bytes(b"AC1032\x00")
        with patch("src.rag.ingest.pipeline.process_cad_files") as mock_pc:
            process_path(str(dwg))
            mock_pc.assert_called_once()
            args, _ = mock_pc.call_args
            assert args[0] == [str(dwg)]

    def test_md_routes_to_process_passthrough(self, tmp_path):
        """.md → process_passthrough([file])"""
        from src.rag.ingest.pipeline import process_path
        md = tmp_path / "readme.md"
        md.write_text("# Title\n", encoding="utf-8")
        with patch("src.rag.ingest.pipeline.process_passthrough") as mock_pp:
            process_path(str(md))
            mock_pp.assert_called_once()
            args, _ = mock_pp.call_args
            assert args[0] == [str(md)]


class TestProcessPathErrors:
    """错误路径"""

    def test_missing_path_prints_error_returns_none(self, capsys):
        """不存在路径 → 打印 + 返回 None（跟 process_files 行为对齐）"""
        from src.rag.ingest.pipeline import process_path
        result = process_path("/nonexistent/path/to/file.pdf")
        captured = capsys.readouterr()
        assert result is None
        assert "路径不存在" in captured.out

    def test_unknown_extension_prints_warning_returns_empty(self, tmp_path, capsys):
        """.xyz → 打印 WARN 跳过，返回空 dict"""
        from src.rag.ingest.pipeline import process_path
        weird = tmp_path / "thing.xyz"
        weird.write_bytes(b"\x00")
        result = process_path(str(weird))
        captured = capsys.readouterr()
        assert "不支持的文件格式" in captured.out
        assert ".xyz" in captured.out
        assert result == {"document": [], "cad": [], "passthrough": []}
```

- [ ] **Step 2: 跑测试确认全部 FAIL**

Run: `uv run pytest tests/rag/ingest/test_pipeline_path.py -v`
Expected: 9 个测试全部 FAIL with `ImportError: cannot import name 'process_path'`

---

## Task 2: 实现 `process_path` + `_process_single_file`

**Files:**
- Modify: `src/rag/ingest/pipeline.py:7-15` (imports 之后, `process_files` 之前)

- [ ] **Step 1: 在 pipeline.py 顶部加 import**

修改 `src/rag/ingest/pipeline.py` 第 7-15 行：

```python
"""文件结构化主入口（PDF + CAD）

统一入口 process_files()：按扩展名分流
- *.pdf  → PDF 流水线（kreuzberg / mineru）
- *.dxf / *.dwg → CAD 流水线（EzdxfConverter）

process_path() (2026-06-08 新增)：单文件/单目录/默认三路分发入口
"""
from pathlib import Path
import tempfile
from .analyzers.pdf import PDFAnalyzer
from .archive_handler import ArchiveError, ArchiveHandler
from .converters import CONVERTERS, get_converter
from .converters.cad import EzdxfConverter
from .config import get_archive_config, get_paths
from .markdown_passthrough import MarkdownPassthroughHandler
```

- [ ] **Step 2: 在 `process_files` 函数定义之前插入 `process_path` 和 `_process_single_file`**

紧挨着 `def process_files(...)` 上面插入：

```python
def process_path(path: str | None = None) -> dict | None:
    """三路分发：单文件 / 单目录 / 默认 config

    Args:
        path: 单文件路径 / 目录路径 / None（None 时走 config.toml 默认 input_dir）
    """
    if path is None:
        # None → 走 config 默认目录
        return process_files()

    p = Path(path)
    if not p.exists():
        print(f"路径不存在: {path}")
        return None

    if p.is_file():
        # 单文件 → 按扩展名路由（zip 走目录分支让 process_files 接管）
        return _process_single_file(str(p))

    # 目录（含 zip 路径）→ 走完整目录流水线
    return process_files(input_dir=str(p))


def _process_single_file(file_path: str) -> dict:
    """单文件模式：按扩展名路由到 document/cad/passthrough

    zip 文件不在这里处理（外层 process_path 把 zip 当目录透传）
    """
    # EzdxfConverter / MarkdownPassthroughHandler / get_paths 已在模块顶部 import
    p = Path(file_path)
    ext = p.suffix.lower()
    paths = get_paths()
    output_path = paths.output_dir

    if ext in MarkdownPassthroughHandler.extensions:
        return process_passthrough([file_path], str(output_path))
    if ext in EzdxfConverter.extensions:
        return process_cad_files([file_path], str(output_path))
    if any(ext in c.extensions for c in CONVERTERS.values()):
        return process_documents([file_path], str(output_path))

    # 未知扩展名
    print(f"[WARN] 不支持的文件格式: {ext}（跳过: {p.name}）")
    return {"document": [], "cad": [], "passthrough": []}
```

- [ ] **Step 3: 跑测试确认全部 PASS**

Run: `uv run pytest tests/rag/ingest/test_pipeline_path.py -v`
Expected: 9 个测试全部 PASS

- [ ] **Step 4: 跑全量测试确认无回归**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过（除 slow 标记的）

- [ ] **Step 5: 提交**

```bash
git add src/rag/ingest/pipeline.py tests/rag/ingest/test_pipeline_path.py
git commit -m "feat(ingest): 新增 process_path 入口支持单文件/单目录/默认"
```

---

## Task 3: `main.py` argparse 加 `path` 位置参数

**Files:**
- Modify: `main.py:27-37`

- [ ] **Step 1: 写 CLI 解析红测试**

**Files:**
- Create: `tests/test_main_cli.py`

```python
"""main.py argparse 解析测试

ingest 单文件支持 (2026-06-08):
- p_ingest 加 path 位置参数 (nargs="?")
"""
from unittest.mock import patch
import sys


class TestIngestParser:
    """p_ingest 子解析器接受可选 path"""

    def test_ingest_accepts_no_args(self):
        """ingest 无参 → cmd_ingest 被调, path=None"""
        with patch("main.cmd_ingest") as mock_handler:
            with patch("sys.argv", ["main.py", "ingest"]):
                from main import main
                main()
            mock_handler.assert_called_once_with(path=None)

    def test_ingest_accepts_optional_path(self):
        """ingest ./abc.pdf → cmd_ingest 被调, path='./abc.pdf'"""
        with patch("main.cmd_ingest") as mock_handler:
            with patch("sys.argv", ["main.py", "ingest", "./abc.pdf"]):
                from main import main
                main()
            mock_handler.assert_called_once_with(path="./abc.pdf")

    def test_ingest_accepts_directory_path(self):
        """ingest ./pdfs/ → cmd_ingest 被调, path='./pdfs/'"""
        with patch("main.cmd_ingest") as mock_handler:
            with patch("sys.argv", ["main.py", "ingest", "./pdfs/"]):
                from main import main
                main()
            mock_handler.assert_called_once_with(path="./pdfs/")
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_main_cli.py -v`
Expected: 3 个测试全部 FAIL with `TypeError: cmd_ingest() got an unexpected keyword argument 'path'`

- [ ] **Step 3: 改 `main.py`**

修改 `main.py` 第 27-37 行：

```python
def cmd_ingest(path: str | None = None) -> None:
    """跑 PDF 离线流水线

    Args:
        path: 可选，单文件路径 / 目录路径 / None 走 config.toml 默认 input_dir
    """
    from src.rag.ingest.pipeline import process_path
    process_path(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 入口")
    sub = parser.add_subparsers(dest="mode")

    p_ingest = sub.add_parser("ingest", help="跑 PDF 离线流水线")
    p_ingest.add_argument(
        "path", nargs="?", default=None,
        help="可选：单个文件路径 或 目录路径；不传走 config.toml 默认 input_dir",
    )
    p_ingest.set_defaults(_handler=cmd_ingest)

    p_serve = sub.add_parser("serve", help="启动产品订货号解析服务")
    p_serve.add_argument("--host", default=DEFAULT_HOST)
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(_handler=cmd_serve)

    args = parser.parse_args()
    if not getattr(args, "_handler", None):
        # 没指定子命令 → 默认走 serve
        args = parser.parse_args(["serve"])

    kwargs = {k: v for k, v in vars(args).items() if k not in ("mode", "_handler")}
    args._handler(**kwargs)
    return 0
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `uv run pytest tests/test_main_cli.py -v`
Expected: 3 个测试全部 PASS

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 6: 提交**

```bash
git add main.py tests/test_main_cli.py
git commit -m "feat(main): ingest 子命令加 path 位置参数支持单文件"
```

---

## Task 4: 创建 `docs/deployment.md`

**Files:**
- Create: `docs/deployment.md`

- [ ] **Step 1: 创建部署文档**

```markdown
# 部署

## 环境要求

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- ODA File Converter（仅 DWG 转 DXF 需要，[下载](https://www.opendesign.com/guestfiles/oda_file_converter)）
- GPU + Docker（仅 mineru 复杂 PDF 解析需要）

## 同步依赖

```bash
uv sync
```

## 启动命令

| 命令 | 行为 |
|---|---|
| `uv run python main.py` | 默认启动产品订货号解析服务（端口 8000） |
| `uv run python main.py serve` | 同上，显式指定 |
| `uv run python main.py serve --port 9000` | 改端口 |
| `uv run python main.py serve --reload` | 开发热重载 |
| `uv run uvicorn main:app --reload` | 同上（开发时少一层 wrapper） |

## 环境变量

| 变量 | 用途 |
|---|---|
| `ODA_WIN_PATH` | ODA File Converter Windows 路径（DWG 转换需要） |
| `ODA_UNIX_PATH` | ODA File Converter Linux 路径 |
| `PRODUCT_DECODERS_CONFIGS` | 覆盖默认产品配置目录（部署数据） |

## Docker / GPU

mineru 复杂 PDF 解析需要 GPU + Docker。详见 [ingestion.md](ingestion.md#mineru-配置)。
```

- [ ] **Step 2: 提交**

```bash
git add docs/deployment.md
git commit -m "docs: 新增 deployment.md 部署指南"
```

---

## Task 5: 创建 `docs/architecture.md`

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: 创建架构文档**

```markdown
# 架构

## 项目结构

```
rag/
├── main.py                              # 统一入口：默认 serve, 子命令 ingest
├── configs/                             # 产品配置 (YAML, 部署数据, 根目录)
│   └── product_decoders/
│       └── motor/
│           └── siemens/
│               └── 1le0_low_voltage.yaml
├── src/
│   ├── product_decoders/                # 产品订货号解析 (FastAPI, 纯代码)
│   │   ├── __init__.py
│   │   ├── app.py                       # FastAPI 工厂
│   │   ├── engine.py                    # ProductDecoder 核心引擎
│   │   └── config_loader.py             # ConfigLoader
│   └── rag/                             # RAG PDF 处理流水线
│       ├── ingest/
│       │   ├── pipeline.py              # 统一入口 process_files + process_path
│       │   ├── analyzers/
│       │   ├── converters/              # kreuzberg / mineru / ezdxf
│       │   └── ...
│       └── ...
├── tests/
│   ├── product_decoders/
│   ├── rag/
│   └── integration/
├── docs/
│   ├── deployment.md                    # 部署
│   ├── architecture.md                  # 本文件
│   ├── product-decoder.md               # 产品解析器
│   ├── ingestion.md                     # RAG 流水线
│   ├── dev-conventions.md               # 开发规范
│   ├── cad-converter.md                 # CAD 转换器
│   ├── cad-ezdxf-best-practices.md
│   └── mineru-output-for-rag.md
└── pyproject.toml
```

## 模块职责

### `src/product_decoders/`

产品订货号解析服务（FastAPI HTTP）。

- 入口：`create_app()` 工厂
- 路由：`/decode` 解码、`/series` 列支持系列、`/health` 健康检查
- 引擎：`ProductDecoder` 按型号前缀路由到 YAML 配置
- 配置加载：`ConfigLoader` 从 `configs/product_decoders/` 目录递归加载

### `src/rag/ingest/`

PDF + CAD 离线处理流水线。

- 入口：
  - `process_files(input_dir, output_dir)` — 完整目录流水线（含 zip 解压、tempfile 隔离、递归扫描）
  - `process_path(path)` (2026-06-08 新增) — 单文件 / 单目录 / 默认三路分发
- 底层：`process_documents / process_cad_files / process_passthrough` 三个 list[str] 入口
- 转换器：
  - `KreuzbergConverter` — 快速 PDF 文本提取
  - `MineruConverter` — Docker 容器跑复杂 PDF（OCR + 表格）
  - `EzdxfConverter` — DXF/DWG 解析 + SVG 渲染

### `main.py`

统一入口，argparse 子命令分发。

- 默认（无子命令）→ `serve` 模式（FastAPI）
- `ingest [path]` → RAG 流水线
- `serve` → 显式启动服务

## 配置文件位置

| 文件 | 用途 |
|---|---|
| `pyproject.toml` | Python 依赖 |
| `config.toml` | RAG 路径 / archive / cad 配置（代码读） |
| `.env` | 环境变量覆盖（ODA 路径等） |
| `configs/product_decoders/**/*.yaml` | 产品解码规则（部署数据） |
```

- [ ] **Step 2: 提交**

```bash
git add docs/architecture.md
git commit -m "docs: 新增 architecture.md 项目架构说明"
```

---

## Task 6: 创建 `docs/product-decoder.md`

**Files:**
- Create: `docs/product-decoder.md`

- [ ] **Step 1: 把 README 第 3 节"产品订货号解析服务"整体搬过来**

```markdown
# 产品订货号解析服务

## 添加新系列

1. 在 `configs/product_decoders/<category>/<vendor>/` 下新建 YAML
2. 复制 `configs/product_decoders/motor/siemens/1le0_low_voltage.yaml` 的结构，按实际编码规则修改
3. 填好 `router.prefix` 和 `router.pattern`
4. 重启服务即可

**零代码改动**。模型前缀路由 (`ProductDecoder.route()`) 自动选配置。

## 配置目录

`configs/product_decoders/` 是默认的产品配置目录，**部署数据**而非代码：

- 加新厂商/新系列：直接在此目录下加 YAML
- 多环境覆盖：用环境变量 `PRODUCT_DECODERS_CONFIGS=/path/to/other/configs` 启动服务即可
- 默认路径用 `Path(__file__).resolve()` 推导，**不依赖 CWD**

## 统一输出 Schema

```json
{
  "series": "siemens_1le0_low_voltage",
  "manufacturer": "Siemens",
  "raw_input": "1LE0001-1AA42-1AA4",
  "normalized": "1LE00011AA421AA4",
  "display": "1LE0001-1AA42-1AA4",
  "prefix": "1LE000",
  "efficiency_grade": "EFF3",
  "efficiency_grade_zh": "高效电动机，中国能效等级 3 级",
  "efficiency_grade_en": "High Efficiency, China Energy Efficiency Grade 3",
  "frame_size": 100,
  "frame_size_zh": "100mm 机座",
  "frame_size_en": "100mm frame",
  "frame_size_raw": "1A",
  "poles": 2,
  "poles_zh": "2 极",
  "poles_en": "2 poles",
  "poles_raw": "A",
  "frame_length": "L",
  "frame_length_zh": "长机座",
  "frame_length_en": "long",
  "frame_length_raw": "4",
  "voltage": "220VD/380VY/50",
  "voltage_zh": "220VD/380VY 50Hz",
  "voltage_en": "220VD/380VY 50Hz",
  "voltage_raw": "21",
  "mounting": "IM B3",
  "mounting_zh": "IM B3 卧式底脚安装",
  "mounting_en": "IM B3",
  "mounting_raw": "A",
  "winding_protection": "NONE",
  "winding_protection_zh": "无绕组保护 / without winding protection",
  "winding_protection_en": "without winding protection",
  "winding_protection_raw": "A",
  "box_location": "TOP",
  "box_location_zh": "置顶 / on top",
  "box_location_en": "on top",
  "box_location_raw": "4"
}
```

**设计要点**：
- 主值用 `code` 或简短中文（如 `"L"`、`"IM B3"`），方便程序处理
- `_zh` / `_en` 后缀字段提供完整中文/英文说明
- `_raw` 后缀字段保留原始编码，方便追溯
- `display` 字段是按 YAML `position.group` 视觉分组还原的展示形式

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/decode` | 解码一个型号，body: `{"model": "..."}` |
| `GET`  | `/series` | 列出所有支持系列 |
| `GET`  | `/health` | 健康检查，返回 `series_count` |

## Dify 工作流接入

```
[开始] 用户输入: "1LE0001-1AA42-1AA4"
   ↓
[HTTP 请求节点]
   POST http://localhost:8000/decode
   Body: {"model": "{{sys.query}}"}
   ↓
[LLM 节点] 格式化输出
   Prompt: "你是产品选型助手，根据解码结果用中文分点解释。
            {{#http_response.body#}}"
   ↓
[直接回复]
```

## 解码示例

输入：`1LE0001-1AA42-1AA4`（16 字符，标准化后 `1LE00011AA421AA4`，4 段 display）

| 位置 | 编码 | group | 含义 |
|---|---|---|---|
| 1-6 | `1LE000` | 1 | 型号前缀（低压系列） |
| 7 | `1` | 1 | 能效等级 3 级 |
| 8-9 | `1A` | 2 | 机座号 100 |
| 10 | `A` | 2 | 2 极 |
| 11 | `4` | 2 | 长机座 L |
| 12-13 | `21` | 3 | 220VD/380VY 50Hz |
| 14 | `A` | 4 | IM B3 安装 |
| 15 | `A` | 4 | 无绕组保护 |
| 16 | `4` | 4 | 接线盒置顶 |
```

- [ ] **Step 2: 提交**

```bash
git add docs/product-decoder.md
git commit -m "docs: 新增 product-decoder.md 产品解析器使用说明"
```

---

## Task 7: 创建 `docs/ingestion.md`

**Files:**
- Create: `docs/ingestion.md`

- [ ] **Step 1: 创建 RAG 流水线文档**

```markdown
# RAG 流水线

## 用法

```bash
# 走 config.toml [paths].input_dir 默认目录（最常用）
uv run python main.py ingest

# 显式指定目录
uv run python main.py ingest ./pdfs/

# 单文件模式（按扩展名自动路由）
uv run python main.py ingest ./abc.pdf
uv run python main.py ingest ./drawing.dxf
uv run python main.py ingest ./readme.md

# zip 压缩包（自动解压到临时目录后处理）
uv run python main.py ingest ./bundle.zip
```

### 行为表

| 输入 | 行为 |
|---|---|
| 不传参 | 走 `config.toml [paths].input_dir` 全扫 |
| 单文件 PDF | 调 `process_documents(["abc.pdf"])` |
| 单文件 DXF/DWG | 调 `process_cad_files(["abc.dxf"])` |
| 单文件 MD | 调 `process_passthrough(["abc.md"])` |
| 单文件未知扩展 | 打印 WARN 跳过 |
| 目录 | 调 `process_files(input_dir=...)` 完整流水线 |
| zip | 透传给 `process_files`，内含 zip 解压 |
| 不存在路径 | 打印报错返回 None |

## 转换器选择

| 格式 | 转换器 | 触发条件 |
|---|---|---|
| PDF（简单：纯文本 + 少图） | `KreuzbergConverter` | 自动路由 |
| PDF（复杂：扫描件/多图/表格） | `MineruConverter`（需 Docker） | 自动路由 |
| DXF | `EzdxfConverter` | `.dxf` |
| DWG | `EzdxfConverter` + ODA 转 DXF | `.dwg`，需装 ODA |
| MD | `MarkdownPassthroughHandler` | `.md` 直通复制 |

简单/复杂由 `PDFAnalyzer` 判定（页数、文本量、图片数）。

## mineru 配置

复杂 PDF 走 mineru Docker 容器，需要：

1. Docker daemon 运行
2. （可选）NVIDIA GPU + nvidia-container-toolkit（GPU 加速）
3. 配置镜像：`mineru` 相关环境变量

详见 [mineru-output-for-rag.md](mineru-output-for-rag.md)。

## ODA 配置

DWG → DXF 转换需要 ODA File Converter。两种配置方式（按优先级）：

### 1. 环境变量（推荐）

```bash
# Windows
set ODA_WIN_PATH=C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe
# Linux
export ODA_UNIX_PATH=/usr/bin/ODAFileConverter
```

### 2. `config.toml` `[cad]` 段

```toml
[cad]
oda_win_path = "C:\\Program Files\\ODA\\ODAFileConverter\\ODAFileConverter.exe"
oda_unix_path = "/usr/bin/ODAFileConverter"
```

[cad] 段缺失或键缺失都走默认空串（合法，DXF 不需要 ODA）。

## archive_handler 配置

`config.toml [archive]` 段控制压缩包解压行为：

```toml
[archive]
max_depth = 1               # zip 嵌套解压层数
max_total_size = 1073741824 # 总大小上限 (默认 1 GiB)
max_file_count = 10000      # 总文件数上限
```

[archive] 段缺失会 raise KeyError（项目必备）。

## 输出

所有产物输出到 `config.toml [paths].output_dir`（默认 `./output/`）。
```

- [ ] **Step 2: 提交**

```bash
git add docs/ingestion.md
git commit -m "docs: 新增 ingestion.md RAG 流水线使用说明"
```

---

## Task 8: 创建 `docs/dev-conventions.md`

**Files:**
- Create: `docs/dev-conventions.md`

- [ ] **Step 1: 创建开发规范文档**

```markdown
# 开发规范

## 测试

```bash
uv run pytest tests/                      # 跑全部
uv run pytest tests/ -m "not slow"        # 跑非 slow 测试
uv run pytest tests/product_decoders/     # 跑产品解析器
uv run pytest tests/rag/                  # 跑 RAG 流水线
```

测试位置：跟源码镜像（`src/rag/ingest/pipeline.py` → `tests/rag/ingest/test_pipeline.py`）。

## 编码规范

- **中文注释**：所有代码注释用中文
- **中文日志**：所有 `print(...)` / `logging.*` 用中文
- **不删注释**：改代码时保留所有原有注释
- **TDD 流程**：先红 → 绿 → 重构

## 依赖管理

- 用 `uv run` 跑 Python（确保依赖一致）
- 实施完成时核对 `pyproject.toml` dependencies 跟实际 import 匹配
- 验证包用 `import` 而非 `pip show`

## 设计文档 & 实施计划

- 设计文档：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- 实施计划：`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- 都提交 git

## shim 禁令

**严禁**写 shim / 兼容代码 / 兜底包装。**新项目零技术债**。

包括但不限于：
- "旧 API 兼容 shim"（新项目没旧 API）
- "未来可能用到的抽象"
- "如果 A 失败就 fallback 到 B"（除非有真实用户场景）
- "反射测试"（测 `xxx_NOT_importable` 这种"不存在"的属性）

每个决策都要能回答"为什么"。惯例或模板出发前先停下来想"原始需求是什么"。

## 调试原则

- 区分不同根因，别用最简单的解释掩盖真正问题
- 外部系统 bug 修复必须真实端到端验证，不信 mock
- 测加密 / 压缩 / IO 路径要测真行为，不是"不崩"
```

- [ ] **Step 2: 提交**

```bash
git add docs/dev-conventions.md
git commit -m "docs: 新增 dev-conventions.md 开发规范"
```

---

## Task 9: 精简 README

**Files:**
- Modify: `README.md` (full rewrite)

- [ ] **Step 1: 写文档结构红测试**

**Files:**
- Create: `tests/test_docs_structure.py`

```python
"""文档结构守门测试

README 拆分 (2026-06-08):
- README 只留项目简介 + 快速启动 + 链接
- 详细内容进 docs/
"""
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
DOCS_DIR = REPO_ROOT / "docs"


class TestDocsSubdirsExist:
    """5 个 docs 主题文件必须存在"""

    def test_deployment_md_exists(self):
        assert (DOCS_DIR / "deployment.md").exists()

    def test_architecture_md_exists(self):
        assert (DOCS_DIR / "architecture.md").exists()

    def test_product_decoder_md_exists(self):
        assert (DOCS_DIR / "product-decoder.md").exists()

    def test_ingestion_md_exists(self):
        assert (DOCS_DIR / "ingestion.md").exists()

    def test_dev_conventions_md_exists(self):
        assert (DOCS_DIR / "dev-conventions.md").exists()


class TestReadmeLinksResolve:
    """README 里的所有相对链接必须指向真实文件"""

    def test_all_readme_links_resolve(self):
        import re
        content = README.read_text(encoding="utf-8")
        # 匹配 [text](./xxx) 或 [text](xxx) 形式
        links = re.findall(r"\]\((?!https?://|mailto:|#)([^)]+)\)", content)
        for link in links:
            # 去掉 anchor 部分
            link_path = link.split("#", 1)[0]
            if not link_path:
                continue
            target = (REPO_ROOT / link_path).resolve()
            assert target.exists(), f"README 链接指向不存在的文件: {link}"


class TestReadmeDoesNotContainExtractedSections:
    """README 不应再含详细 schema / YAML 示例 / API 列表（避免回滚）"""

    def test_readme_no_longer_has_detailed_api_table(self):
        """旧 README 的 API 详细表格应已搬走"""
        content = README.read_text(encoding="utf-8")
        assert "/decode" not in content, (
            "README 不应再含 /decode 详细说明（已搬到 product-decoder.md）"
        )

    def test_readme_no_longer_has_full_schema_example(self):
        """旧 README 的完整 JSON Schema 示例应已搬走"""
        content = README.read_text(encoding="utf-8")
        assert "efficiency_grade_zh" not in content, (
            "README 不应再含完整 JSON Schema（已搬到 product-decoder.md）"
        )
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `uv run pytest tests/test_docs_structure.py -v`
Expected: 11 个测试 FAIL（docs 还没建）

- [ ] **Step 3: 全量重写 README.md**

**Files:**
- Modify: `README.md` (整个覆盖)

```markdown
# RAG 项目

RAG 离线流水线 + 产品订货号解析 HTTP 服务。

## 快速启动

```bash
uv sync

# 启动产品订货号解析服务（默认，端口 8000）
uv run python main.py

# 跑 RAG 离线流水线
uv run python main.py ingest                       # 走 config.toml [paths].input_dir
uv run python main.py ingest ./pdfs/               # 显式目录
uv run python main.py ingest ./abc.pdf             # 单文件
uv run python main.py ingest ./bundle.zip          # zip 自动解压
```

调用测试：

```bash
curl -X POST http://localhost:8000/decode \
  -H "Content-Type: application/json" \
  -d '{"model": "1LE0001-1AA42-1AA4"}'
```

## 文档

| 文档 | 内容 |
|---|---|
| [docs/deployment.md](docs/deployment.md) | 环境要求、启动命令、环境变量、Docker/GPU |
| [docs/architecture.md](docs/architecture.md) | 项目结构、模块职责、配置文件位置 |
| [docs/product-decoder.md](docs/product-decoder.md) | 产品订货号解析服务使用说明、API、Dify 接入 |
| [docs/ingestion.md](docs/ingestion.md) | RAG 流水线用法、转换器选择、ODA 配置、archive 配置 |
| [docs/dev-conventions.md](docs/dev-conventions.md) | 测试、编码规范、shim 禁令 |

## 测试

```bash
uv run pytest tests/                      # 跑全部
uv run pytest tests/ -m "not slow"        # 跑非 slow 测试
```

详见 [dev-conventions.md](docs/dev-conventions.md)。
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `uv run pytest tests/test_docs_structure.py -v`
Expected: 11 个测试全部 PASS

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 6: 提交**

```bash
git add README.md tests/test_docs_structure.py
git commit -m "docs: 精简 README 拆 5 个 docs 主题文档"
```

---

## Task 10: 全量验证 + 提交

**Files:**
- (no code changes)

- [ ] **Step 1: 跑全量测试**

Run: `uv run pytest tests/ -m "not slow" -q`
Expected: 全过

- [ ] **Step 2: 跑 ruff**

Run: `uv run ruff check .`
Expected: 全过

- [ ] **Step 3: 手测 ingest 单文件**

```bash
# 创建测试文件
echo "# Title" > /tmp/test.md
uv run python main.py ingest /tmp/test.md
```

Expected: 输出 "扫描到 1 个 md 直通文件"，`config.toml [paths].output_dir` 下出现 `test.md`

- [ ] **Step 4: 手测 ingest 不传参**

```bash
uv run python main.py ingest
```

Expected: 走 config.toml [paths].input_dir 扫目录（如果存在）

- [ ] **Step 5: 手测 ingest 不存在路径**

```bash
uv run python main.py ingest /tmp/nonexistent.pdf
```

Expected: 打印 "路径不存在: /tmp/nonexistent.pdf"

- [ ] **Step 6: 验证 git log**

Run: `git log --oneline -10`
Expected: 看到所有 task 的 commit (T2, T3, T4, T5, T6, T7, T8, T9)

---

## 总结

11 个 commit，TDD 流程（红→绿→重构），无 shim 代码（[feedback-no-shim-no-minimal-changes] 配对）。

实现完后：
- `uv run python main.py ingest <file>` 单文件模式跑通
- README 拆 5 个 docs，主 README 精简到 ~30 行
- 14 个新单测守住行为契约
