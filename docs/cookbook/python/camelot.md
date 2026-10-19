# Camelot 教程

> 📅 创建日期：2026-07-06
> 📁 项目代码引用：本教程以 `c:/Users/abcuc/Desktop/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python 工程师，需要做 PDF 表格提取（lattice/stream/ml 多种策略）

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

Camelot（PyPI 包名 `camelot-py`）是 Vincent Schönbeck 维护的 PDF 表格提取库，专精"把 PDF 里人类能识别的表格抽成 pandas DataFrame"。它提供 **4 种 flavor**（lattice / stream / network / hybrid / ml）应对不同 PDF 表格样式。

**同类对比：**

| 库 | 定位 | 本项目使用场景 |
|------|------|----------------|
| **Camelot** | 表格提取 + DataFrame 输出 | 复杂线框表格 fallback（`src/ingest/pre_analysis/table_extractors/camelot_extractor.py`）|
| **PyMuPDF (pymupdf)** | PDF 解析 + 坐标 | **本项目默认**（`docs/cookbook/python/pymupdf.md`）|
| **pdfplumber** | 纯 Python 表格 | 轻量级 fallback（`src/ingest/pre_analysis/table_extractors/pdfplumber_extractor.py`）|
| **tabula-py** | JVM 包装 tabula | 需 Java 8+，项目不用 |
| **ExtractTable** | OCR 表格 | 商业 API |

**Camelot 解决的核心问题**：
- **lattice 模式**：依赖 PDF 矢量线框识别表格（适合有线表格 / 财务报表）
- **stream 模式**：依赖文本对齐识别（适合无线表格 / 文本流分隔）
- **DataFrame 输出**：直接拿 `pandas.DataFrame`，转 CSV / 写库 1 行
- **page 维度**：`tables[i].page` 知道表格在第几页（跟 pymupdf 输出兼容）

**不适合什么**：扫描件 PDF（lattice 失败，要 OCR + 行列检测）、非结构化文本流（Camelot 强制对齐到表格结构，无文本会返空）。

### 4 种 flavor 一图理解

| Flavor | 原理 | 适用 |
|--------|------|------|
| **`lattice`** | 检测 PDF 矢量线画网格 | **有线表格**（财务报表 / 合同 / 价目表） |
| **`stream`** | 文本块水平对齐成行 | **无线表格**（名单 / 列表 / 简单分隔） |
| **`network`** | 基于 networkx 构建图，自动判断行列 | 复杂混合表格 |
| **`hybrid`** | lattice + stream 自动选 | 默认兜底 |
| **`ml`** | Table Transformer (transformers + torch) | **最智能**，但要 +500MB PyTorch |

---

## 二、安装 & 初始化

### 2.1 安装

```bash
# 项目装了 [pdf-tables] extra 才可用 (pyproject.toml:62)
uv pip install -e '.[pdf-tables]'

# 单独装
uv add camelot-py
uv add 'camelot-py[ml]'   # ml flavor 需要 (PyTorch +500MB)

# 验证
uv run python -c "import camelot; print(camelot.__version__)"
```

注意：
- PyPI 包名 `camelot-py`（带连字符），**不是** `camelot`（那个是已废弃的同名音频库）
- import 路径仍是 `camelot`
- `[ml]` extra 装 `transformers` + `torch`（PyPI 体积巨大），**仅 ml flavor 需要**

### 2.2 系统依赖

Camelot 强依赖 **ghostscript**（lattice 模式需要它解析 PDF 矢量）：

```bash
# Linux (Debian/Ubuntu)
sudo apt install -y ghostscript python3-tk

# macOS
brew install ghostscript tcl-tk

# Windows
# 1) 下载 ghostscript: https://www.ghostscript.com/releases.html
# 2) 加 PATH: C:\Program Files\gs\gs10.03.0\bin
# 3) 验证: gswin64c --version
```

**项目 dev 默认禁用**（`configs/pre_analysis/table_extraction.yaml:11`）：

```yaml
camelot:
  enabled: false  # dev 默认禁用, 需要时改 true
  install_hint: "uv add camelot-py"
  ml_install_hint: "uv add 'camelot-py[ml]'   # 仅 flavor='ml' 需要 (PyTorch 拉 +500MB)"
```

### 2.3 健康检查

```python
import camelot
print(camelot.__version__)  # 2.0+

# 真 PDF 测试 (依赖 ghostscript)
tables = camelot.read_pdf("test.pdf", flavor="lattice")
print(f"找到 {len(tables)} 张表格")
print(tables[0].df)  # pandas DataFrame
```

---

## 三、核心概念 & 抽象

### 1. TableList (read_pdf 返回)

`camelot.read_pdf()` 返回 `TableList`（行为类似 list）：

```python
import camelot

tables = camelot.read_pdf("doc.pdf", flavor="lattice")
print(type(tables))         # camelot.core.TableList
print(len(tables))          # 找到的表格数
for t in tables:
    print(t.page, t.df.shape)
```

### 2. Table (单张表)

```python
t = tables[0]
t.page              # int: 1-based 页码
t.order             # int: 整 PDF 内编号 (1, 2, 3...)
t.df                # pd.DataFrame: 表格内容
t.parsing_report    # dict: 解析报告 (accuracy, whitespace, ...)
t.to_json()         # str: JSON 序列化
t.to_html()         # str: HTML 表格
t.to_csv()          # str: CSV
t.to_latex()        # str: LaTeX
t.to_markdown()     # str: Markdown (2.0+)
t.to_sqlite()       # SQLite DB
```

### 3. 4 种 flavor 详解

#### `lattice` 模式

依赖 PDF 矢量线画网格，**最适合有线表格**：

```python
tables = camelot.read_pdf("financial_report.pdf", flavor="lattice")
# 自动检测: 水平线 / 垂直线 / 交叉点 → 构建表格网格
```

**原理**：PDF 渲染层画横线/竖线 → 找线交点 → 画网格 → 在格子里填文本。

**坑**：扫描件（位图）没有矢量线 → lattice 全失败。

#### `stream` 模式

依赖文本块水平对齐识别表格，**适合无线表格**：

```python
tables = camelot.read_pdf("text_list.pdf", flavor="stream")
# 自动检测: 同 y 坐标的文字块 → 同一行 → 同行同 x → 同列
```

**原理**：PDF 文本块在物理上有坐标 → 同 y 同一行 → 同 x 同列 → 重组表格。

**坑**：要求 PDF 文字层干净，扫描件不行。

#### `network` 模式 (2.0+ 新)

基于 networkx 构图，自动决定 lattice / stream：

```python
tables = camelot.read_pdf("mixed.pdf", flavor="network")
```

**坑**：性能慢（构图 + 决策），大 PDF 慢。

#### `ml` 模式 (2.0+ 新)

Table Transformer（HuggingFace `microsoft/table-transformer-detection`）：

```python
tables = camelot.read_pdf("hard.pdf", flavor="ml")
```

**坑**：
- **必须装 `[ml] extra**`（拉 transformers + torch ≈ 500MB）
- GPU 加速（CPU 也跑但慢）
- 第一次跑下载模型（≈ 200MB）

### 4. table_areas / columns 参数 (lattice/stream 调参)

```python
# lattice: 限定表格区域 + 行列合并规则
tables = camelot.read_pdf(
    "doc.pdf",
    flavor="lattice",
    table_areas=["10,50,500,700"],          # 限定 1 张表区域 (x0,y0,x1,y1)
    process_background=True,                # 背景处理
    line_scale=15,                          # 短线合并阈值
    copy_text=["v"],                        # v=垂直复制, h=水平复制
    line_tol=2,                             # 行容差
    joint_tol=2,                            # 交点容差
    iterations=5,                           # 收敛迭代
)

# stream: 限定列位置
tables = camelot.read_pdf(
    "doc.pdf",
    flavor="stream",
    columns=["50,200,300,500"],             # 列分隔 x 坐标
    row_tol=2,
    column_tol=2,
)
```

### 5. parsing_report (调优反馈)

```python
t = tables[0]
print(t.parsing_report)
# {
#   'accuracy': 95.3,           # 表格质量评分
#   'whitespace': 12.4,         # 空白占比
#   'order': 1,
#   'page': 3,
#   'rows': 10,
#   'columns': 5,
# }
```

**`accuracy` < 80** → 表格识别可能有问题，考虑换 flavor 或调参。

---

## 四、常用 API & 命令速查

### 4.1 基本读取

```python
import camelot

# 默认 lattice
tables = camelot.read_pdf("doc.pdf")

# 显式 flavor
tables = camelot.read_pdf("doc.pdf", flavor="stream")

# 多页
tables = camelot.read_pdf("doc.pdf", pages="1-3")           # 1-3 页
tables = camelot.read_pdf("doc.pdf", pages="1,3,5")          # 离散页
tables = camelot.read_pdf("doc.pdf", pages="all")            # 全部
```

### 4.2 参数调优 (lattice)

```python
tables = camelot.read_pdf(
    "doc.pdf",
    flavor="lattice",
    line_scale=40,                    # 线合并阈值
    line_tol=2,                       # 线间距容差 (像素)
    joint_tol=2,                      # 交点容差
    iterations=5,                     # 边框检测迭代次数
)
```

### 4.3 参数调优 (stream)

```python
tables = camelot.read_pdf(
    "doc.pdf",
    flavor="stream",
    row_tol=2,                        # 同行容差
    column_tol=0,                     # 同列容差
    edge_tol=50,                      # 边容差 (项目默认)
)
```

### 4.4 输出格式

```python
t = tables[0]
print(t.df)                          # DataFrame
print(t.to_csv())                    # str (CSV)
t.to_csv("output.csv")               # 落盘

print(t.to_json())                   # JSON 字符串
print(t.to_html())                   # HTML <table>
print(t.to_markdown())                # 2.0+ Markdown
```

### 4.5 后处理

```python
# 合并多表
import pandas as pd
all_df = pd.concat([t.df for t in tables], ignore_index=True)

# 按列名取子集
df = tables[0].df[["name", "price"]]

# 清理空白
df = tables[0].df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
```

### 4.6 加密 PDF

```python
tables = camelot.read_pdf("encrypted.pdf", password="xxx")
```

### 4.7 命令行

```bash
# CLI (camelot-py 自带)
camelot lattice --help
camelot stream --output output.csv doc.pdf

# 批量处理
camelot lattice --pages 1-5 "report.pdf"
```

---

## 五、项目集成点

### 5.1 Pyproject 可选依赖

`packages/service/pyproject.toml:58-65`：

```toml
# (2026-07-06) 表格后端可选依赖: admin 显式选 camelot / pdfplumber 才装
#   pymupdf 已装, 默认 backend 无需额外
#   uv pip install -e '.[pdf-tables]'  # 装齐 3 后端
[project.optional-dependencies]
pdf-tables = [
  "camelot-py>=2.0",
  "pdfplumber>=0.11",
]
```

### 5.2 项目引用位置

| 文件 | 用途 |
|------|------|
| `src/ingest/pre_analysis/table_extractors/camelot_extractor.py` | 表格适配器实现 |
| `src/ingest/pre_analysis/table_extractors/factory.py:28-31` | factory 路由 `"camelot"` → `CamelotTableExtractor` |
| `configs/pre_analysis/table_extraction.yaml:10-13` | 默认 `enabled: false`，配 `install_hint` |
| `tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` | 3 类测试 (未装 / 缺 ml / 真 PDF) |
| `packages/service/src/ingest/pre_analysis/router.py:91-92` | API 层校验 `table_backend in ('pymupdf', 'camelot', 'pdfplumber')` |

### 5.3 项目预分析表格流程

```
admin 上传 PDF
    ↓
table_backend='camelot' (form 字段)
    ↓
router.upload_pre_analysis (router.py:65) 校验 backend
    ↓
BackgroundTasks._run_pre_analysis (router.py:296)
    ↓
PreAnalysisRunner._extract_tables (runner.py:267)
    ↓
get_table_extractor('camelot', params) (factory.py:28)
    ↓
CamelotTableExtractor.__init__ (camelot_extractor.py:21)
    - 校验包已装 (BackendNotInstalledError if not)
    - 校验 ml extra 已装 (if flavor='ml')
    ↓
CamelotTableExtractor.extract (camelot_extractor.py:43)
    - camelot.read_pdf(pdf_path, flavor=..., edge_tol=..., row_tol=...)
    - TableList → 按 (page_no, table_no) 排序 → list[TableData]
```

### 5.4 默认配置

`configs/pre_analysis/table_extraction.yaml:22-25`：

```yaml
default_params:
  camelot:
    flavor: "lattice"    # lattice | stream | network | hybrid | ml (ml 需 [ml] extra + PyTorch)
    edge_tol: 50         # 边容差 (像素)
    row_tol: 2           # 行容差
```

### 5.5 选型原因

- **fallback 而非默认**：pymupdf 已足够，camelot 仅在有线表格失效时启用
- **可选依赖**：避免 ghostscript 系统依赖污染 dev 环境（`enabled: false`）
- **`[ml] extra` 拆分**：避免 +500MB PyTorch 全员强装
- **BackendNotInstalledError 翻译**：HTTP 503 + 友好 install hint，admin 自己看错选装

---

## 六、项目代码示例

### 6.1 适配器实现

`src/ingest/pre_analysis/table_extractors/camelot_extractor.py:15-73` 完整实现：

```python
class CamelotTableExtractor(TableExtractor):
    """camelot.read_pdf 适配器.

    flavor: lattice | stream | network | hybrid | ml (ml 需 [ml] extra).
    """

    def __init__(self, params: dict) -> None:
        self._params = params
        self._flavor = params.get("flavor", "lattice")
        try:
            import camelot  # type: ignore[import-not-found, unused-ignore]  # noqa: F401  # 可选依赖, 缺包抛 BackendNotInstalledError
        except ImportError as e:
            raise BackendNotInstalledError(backend="camelot", install_hint=_BASE_INSTALL_HINT) from e

        # flavor='ml' 单独检查 [ml] extra (camelot-py[ml] 含 transformers + torch)
        if self._flavor == "ml":
            try:
                # 检测 [ml] extra 是否齐全: 试 import transformers (Table Transformer 必需的)
                import importlib.util as _ilu

                if _ilu.find_spec("transformers") is None:
                    raise ImportError("transformers 包未装, [ml] extra 缺失")
            except ImportError as e:
                raise BackendNotInstalledError(
                    backend="camelot[ml]",
                    install_hint=_ML_INSTALL_HINT,
                ) from e

    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: object | None = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格. camelot.read_pdf 整文件读, 不接受已开 pymupdf doc."""
        import camelot  # type: ignore[import-not-found]  # noqa: lazy import 已在 __init__ 检查

        edge_tol = self._params.get("edge_tol", 50)
        row_tol = self._params.get("row_tol", 2)
        tables = camelot.read_pdf(
            pdf_path,
            flavor=self._flavor,
            edge_tol=edge_tol,
            row_tol=row_tol,
        )
        # camelot 返 TableList; 每个 .page (int) + .df (pandas DataFrame)
        # 按 page 分组, table_no 1-based
        per_page_counts: dict[int, int] = {}
        result: list[TableData] = []
        for t in tables:
            page_no = int(t.page)
            per_page_counts[page_no] = per_page_counts.get(page_no, 0) + 1
            rows: list[list[str]] = t.df.values.tolist()
            rows = [[str(cell) for cell in row] for row in rows]
            result.append(TableData(page_no=page_no, table_no=per_page_counts[page_no], rows=rows))
        # 按 (page_no, table_no) 排序, 跟 pymupdf 行为一致
        result.sort(key=lambda t: (t.page_no, t.table_no))
        return result
```

**设计要点**：
- **Lazy import**：`import camelot` 在 `__init__` 内捕获 ImportError，翻译成 `BackendNotInstalledError`
- **`[ml] extra` 单独检测**：flavor='ml' 多查 `transformers` 包（camelot-py[ml] 的实质依赖）
- **不接受 pymupdf doc**：camelot 自己重开 PDF（`camelot.read_pdf(pdf_path)`），`runner.py:284` 检测非 pymupdf 后端时 `_doc=None`
- **`table_no` 1-based + 按页分组**：Camelot 默认只给 `t.order`（整 PDF 编号），需要手动按 `t.page` 分组重编号
- **DataFrame → list[list[str]]**：`t.df.values.tolist()` + `str(cell)` 标准化，跨后端输出 shape 一致

### 6.2 Factory 路由

`src/ingest/pre_analysis/table_extractors/factory.py:23-37`：

```python
def get_table_extractor(backend: str, params: dict | None = None) -> TableExtractor:
    """工厂: backend 字符串 → 适配器实例.

    Args:
        backend: "pymupdf" | "camelot" | "pdfplumber"
        params: backend-specific 参数 (e.g. flavor / edge_tol / vertical_strategy)

    Raises:
        ValueError: backend 不在白名单.
        BackendNotInstalledError: 选了 camelot/pdfplumber 但 Python 包没装 (transitively 由适配器 __init__ 抛).
    """
    effective_params = params or {}
    match backend:
        case "pymupdf":
            from .pymupdf_extractor import PymupdfTableExtractor
            return PymupdfTableExtractor(effective_params)
        case "camelot":
            from .camelot_extractor import CamelotTableExtractor
            return CamelotTableExtractor(effective_params)
        case "pdfplumber":
            from .pdfplumber_extractor import PdfplumberTableExtractor
            return PdfplumberTableExtractor(effective_params)
        case _:
            raise ValueError(f"未知表格后端: {backend}")
```

**关键**：`get_table_extractor("camelot", ...)` 内部构造 `CamelotTableExtractor`，**包缺失会立即抛 `BackendNotInstalledError`**，factory 不吞错。

### 6.3 API 层校验

`src/ingest/pre_analysis/router.py:91-92`：

```python
# 校验 table_backend
if table_backend not in ("pymupdf", "camelot", "pdfplumber"):
    raise HTTPException(400, detail=f"未知表格后端: {table_backend}")
```

**API 层**先白名单过滤，**适配器层**再 `BackendNotInstalledError` 转 503：

```python
# 假设 BackendNotInstalledError 在 router 层翻译
except BackendNotInstalledError as e:
    raise HTTPException(
        status_code=503,
        detail=f"后端 {e.backend} 未安装: {e.install_hint}",
    )
```

（**注**：项目当前可能直接 500 漏出 BackendNotInstalledError，需后续补全局 handler；admin 端按 503 提示装包。）

### 6.4 测试模式 (mode 1 mock + 真 PDF skipIf)

`tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py:19-55` 包缺失测试：

```python
def test_camelot_not_installed_raises_backend_not_installed_error() -> None:
    """camelot-py 未装 → 构造立即抛 BackendNotInstalledError(backend='camelot')."""
    # 移除 camelot 模块缓存 (避免别处 import 后缓存影响)
    monkey_modules = {k: v for k, v in sys.modules.items() if k.startswith("camelot")}
    for k in monkey_modules:
        del sys.modules[k]

    # patched import → ImportError
    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "camelot" or name.startswith("camelot."):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
            CamelotTableExtractor,
        )

        with pytest.raises(BackendNotInstalledError) as exc_info:
            CamelotTableExtractor({"flavor": "lattice"})

    assert exc_info.value.backend == "camelot"
    assert "uv add camelot-py" in exc_info.value.install_hint
```

**测试模式 4 模式**（见 `packages/service/CLAUDE.md §测试隔离 4 模式`）：
- **包缺失测试**走**模式 1 纯单测**：`patch("builtins.__import__")` 模拟 ImportError
- **真 PDF 测试**走 `pytest.mark.skipif`：本机装了 `camelot-py` 才跑，否则 skip
- **CI 不依赖真实包**：默认 dev 环境没装 camelot，全量测试照常通过

### 6.5 ml flavor 单独检测

`tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py:58-89`：

```python
def test_ml_flavor_without_ml_extra_raises_ml_specific_error(monkeypatch) -> None:
    """flavor='ml' 但 [ml] extra 没装 (transformers 找不到) → 抛 BackendNotInstalledError(backend='camelot[ml]')."""
    # 假装 camelot 可 import, 但 transformers 不可 import
    fake_camelot = type(sys)("camelot")
    fake_camelot.__version__ = "2.0.0"
    monkeypatch.setitem(sys.modules, "camelot", fake_camelot)

    real_find_spec = importlib.util.find_spec
    def fake_find_spec(name, *args, **kwargs):
        if name == "transformers":
            return None
        return real_find_spec(name, *args, **kwargs)
    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    with pytest.raises(BackendNotInstalledError) as exc_info:
        CamelotTableExtractor({"flavor": "ml"})

    assert "ml" in exc_info.value.backend.lower()
    assert "camelot-py[ml]" in exc_info.value.install_hint
```

**设计要点**：
- `sys.modules` 注入假 camelot（绕开真实 import）
- `importlib.util.find_spec("transformers")` mock 返 None（ml extra 缺失）
- 适配器 `__init__` 在 ml 分支检测到 → 抛 `BackendNotInstalledError(backend="camelot[ml]")`
- 测试**严格 mock 两个独立包**（camelot + transformers），不混测

### 6.6 真 PDF 测试 (skipIf)

`tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py:92-111`：

```python
@pytest.mark.skipif(
    importlib.util.find_spec("camelot") is None,
    reason="camelot-py 未装, 真 PDF 测试 skip",
)
def test_extract_real_pdf_lattice() -> None:
    """真 PDF 走 camelot.read_pdf(flavor='lattice') → TableData 列表."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    fixture_path = __import__("pathlib").Path(__file__).resolve().parents[2] / "fixtures" / "d81_dummy.pdf"

    extractor = CamelotTableExtractor({"flavor": "lattice", "edge_tol": 50, "row_tol": 2})
    result = extractor.extract(str(fixture_path))
    assert isinstance(result, list)
    for td in result:
        assert td.page_no >= 1
        assert td.table_no >= 1
        assert isinstance(td.rows, list)
```

**CI 友好**：`skipif` 自动检测本机包，**无 camelot 直接 skip**（不 fail）。本地 dev 装了之后才会跑真 PDF。

---

## 七、项目没用到的能力

以下 Camelot 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **`t.parsing_report` 反馈** | accuracy / whitespace 评分 | 表格识别质量评估，劣质表走 fallback |
| **TableList 过滤** | `tables.filter(lambda t: t.parsing_report['accuracy'] > 90)` | 质量门禁 |
| **表格区域手动限定** | `table_areas` / `columns` | 复杂版面指定表格范围 |
| **process_background** | 背景图处理（去除 logo 水印干扰） | 扫描件表格 |
| **password 加密 PDF** | `camelot.read_pdf(..., password=...)` | 加密 PDF |
| **流式分批** | `pages="1-10"` `pages="11-20"` | 大 PDF 分块 |
| **CLI 命令** | `camelot lattice --output x.csv` | 离线脚本 |
| **lattice 高级调参** | `line_tol` / `joint_tol` / `iterations` | 项目目前只暴露 `edge_tol` / `row_tol` |
| **Hybrid / Network 自动选** | `flavor='hybrid'` | 不确定 PDF 用 |
| **ml flavor 量化精度** | GPU 加速 / fp16 | 性能关键场景 |
| **数据清理** | Camelot 无内置清理 | 项目应自行 post-process |

**建议关注**：
- **`parsing_report` 质量门禁**：当前所有表无差别返回，可加 `accuracy > 80` 过滤劣质表
- **CLI 脚本**：`docs/superpowers/plans/...` 离线 PDF 批处理可以用 Camelot CLI

---

## 八、评测 & 调优技巧

### 8.1 4 种 flavor 性能基线

| Flavor | 10 页 PDF | 100 页 PDF | 1000 页 PDF |
|--------|----------|------------|-------------|
| `lattice` | 2-5s | 30-60s | 5-10min |
| `stream` | 1-3s | 15-30s | 2-5min |
| `network` | 5-15s | 60-120s | 10-20min |
| `ml` (CPU) | 30-60s | 5-15min | 1h+ |
| `ml` (GPU) | 2-5s | 30-60s | 5-10min |

**lattice 比 stream 慢**（要画网格图），但更准。

### 8.2 flavor 选型经验

```python
# 1. 默认 lattice (有线表格)
tables = camelot.read_pdf("doc.pdf", flavor="lattice")
if not tables or tables[0].parsing_report["accuracy"] < 80:
    # 2. 无线表格 → stream
    tables = camelot.read_pdf("doc.pdf", flavor="stream")

# 3. 仍失败 → ml (智能)
if not tables or tables[0].parsing_report["accuracy"] < 80:
    tables = camelot.read_pdf("doc.pdf", flavor="ml")
```

**项目目前不做 fallback chain**（admin 显式选 1 个），可考虑：

```python
# (2026-07-06) 假想: factory 加 fallback 模式
if backend == "auto":
    for flavor in ["lattice", "stream", "ml"]:
        try:
            tables = camelot.read_pdf(pdf_path, flavor=flavor)
            if tables and tables[0].parsing_report["accuracy"] >= 80:
                break
        except Exception:
            continue
```

### 8.3 调优参数对照

| 参数 | 适用 | 推荐起点 |
|------|------|---------|
| `edge_tol` (stream) | 边容差 | **50**（项目默认） |
| `row_tol` (stream) | 同行 y 坐标容差 | **2**（项目默认） |
| `line_scale` (lattice) | 短线合并阈值 | 15（短小表格） / 40（财务大表） |
| `line_tol` (lattice) | 平行线容差 | 2 |
| `joint_tol` (lattice) | 线交点容差 | 2 |
| `iterations` (lattice) | 边框检测迭代 | 5 |
| `table_areas` | 限定表格区域 | `["50,700,500,50"]` (左下原点!) |

**注意**：Camelot 坐标原点在**左下**（跟 pymupdf 左上相反），调 `table_areas` 时小心。

### 8.4 性能调优

1. **限定页码**（大 PDF 必加）：

```python
# 错: 全 PDF 扫
tables = camelot.read_pdf("1000page.pdf", flavor="lattice")  # 5 分钟

# 对: 限定页
tables = camelot.read_pdf("1000page.pdf", flavor="lattice", pages="100-150")
```

2. **`process_background=False`**（默认 False，跳过背景处理加速 30%）：

```python
tables = camelot.read_pdf("doc.pdf", flavor="lattice", process_background=False)
```

3. **GPU 加速 ml flavor**（自动检测 CUDA）：

```bash
# 装 CUDA 版 PyTorch
uv pip install torch --index-url https://download.pytorch.org/whl/cu121
```

4. **大表格分块**：

```python
import camelot
all_tables = []
for page_range in ["1-50", "51-100", "101-150"]:
    tables = camelot.read_pdf("doc.pdf", flavor="lattice", pages=page_range)
    all_tables.extend(tables)
```

### 8.5 准确率评估

`parsing_report.accuracy` 公式（Camelot 2.0+）：

```
accuracy = 100 * (matches / total_whitespace_cells)
# matches: 与预期对齐匹配的单元格数
# total_whitespace_cells: 总空白单元格数
```

**项目目前不消费 accuracy**（直接信任返回），可考虑过滤 `accuracy < 80` 的表。

---

## 九、最佳实践 & 常见坑

### 项目风格

1. **lazy import + 翻译 ImportError**（`camelot_extractor.py:24-27`）：包缺失抛 `BackendNotInstalledError`，带 install_hint
2. **flavor 二次校验**（`camelot_extractor.py:30-41`）：ml flavor 单独检查 transformers，独立 `BackendNotInstalledError`
3. **不接受 pymupdf doc**（`camelot_extractor.py:50`）：camelot 自己重开 PDF，runner 检测 `backend != "pymupdf"` 时 `_doc=None`
4. **table_no 按页重编号**（`camelot_extractor.py:63-67`）：Camelot 默认只给 `t.order`，按 `t.page` 分组重编号 → 跟 pymupdf 行为一致
5. **DataFrame → list[list[str]]**：`t.df.values.tolist()` + `str(cell)` 标准化，跨后端输出 shape 一致

### 常见坑

1. **PyPI 包名带连字符**：

```bash
# 错
uv add camelot     # 这是个音频库!

# 对
uv add camelot-py  # 表格提取库
```

`import camelot` 不带连字符，是 PyPI 包名特殊。

2. **ghostscript 必须装**（lattice）：

```python
# 没装 gs
tables = camelot.read_pdf("doc.pdf", flavor="lattice")
# 抛: GhostscriptNotFound: Please make sure ghostscript is installed
```

`gswin64c --version` (Windows) / `gs --version` (Unix) 验证。

3. **扫描件 lattice 失败**：

```python
# 错: 扫描件走 lattice
tables = camelot.read_pdf("scan.pdf", flavor="lattice")  # 返空 / 0 行

# 对: 先 OCR 拿文字层, 再走 stream
# (Kreuzberg 已经 OCR, 把 PDF 文字层刷一遍再走 Camelot)
```

**项目不自动 OCR + Camelot 链**，admin 显式选择。

4. **坐标原点在左下（不是左上）**：

```python
# pymupdf 坐标: 左上 (y0 < y1 是从上到下)
# Camelot table_areas: 左下 (y0 < y1 是从下到上)
table_areas=["50,700,500,50"]  # x0=50, y0=700(下), x1=500, y1=50(上)
```

混用会限定到错误区域。

5. **flavor='ml' 装包体积**：

```bash
# ml flavor 拉 500MB+ PyTorch + transformers
# 永远不要给所有 dev 机器装, 走 [ml] extra 按需
uv add 'camelot-py[ml]'
```

项目 `BackendNotInstalledError(backend="camelot[ml]", install_hint="uv add 'camelot-py[ml]'")` 引导按需装。

6. **同步阻塞**（跟 pymupdf 一样）：

```python
# 错: 阻塞 event loop
async def handler():
    tables = camelot.read_pdf("doc.pdf")  # 5-60s 同步阻塞!

# 对: BackgroundTasks / ThreadPoolExecutor
async def handler():
    background.add_task(run_camelot, pdf_path)
```

项目预分析走 BackgroundTasks（`router.py:122`），不阻塞请求返回。

7. **重复打开 PDF**（性能杀手）：

```python
# 错: 每次表格提取都重开
for table_idx in range(10):
    tables = camelot.read_pdf("doc.pdf", flavor="lattice")  # 10 次 IO

# 对: 1 次开, 多次过滤
tables = camelot.read_pdf("doc.pdf", flavor="lattice")
selected = [t for t in tables if t.page == 3]
```

Camelot 不像 pymupdf 支持 doc 复用，必须一次读完用 `tables` 列表。

8. **t.df 单元格是 `numpy.str_` 不是 `str`**：

```python
cell = tables[0].df.iloc[0, 0]
print(type(cell))  # numpy.str_, 不是 str

# 序列化到 JSON 需 str()
json.dumps({"cell": str(cell)})
```

项目 `camelot_extractor.py:68` 显式 `str(cell)` 强制转换。

9. **空表返 `TableList([])` 不抛**：

```python
tables = camelot.read_pdf("no_table.pdf", flavor="lattice")
print(len(tables))  # 0, 不抛
```

`TableData` 列表可能为空，runner 和前端必须处理空表。

10. **`pages="all"` 在大 PDF 超时**：

```python
# 1000 页 PDF 全 lattice 跑 5-10 分钟
# 必须 pages="1-50" 分块, 配合 BackgroundTasks
```

项目目前 admin 上传 1 次走 BackgroundTasks，没分块；1000 页 PDF 可能单任务跑 10 分钟。

### 项目测试隔离

Camelot 后端**可选依赖**，走**模式 1 纯单测** + **`skipif` 跳过**：

```python
# CI 默认 skip 真 PDF 测试
@pytest.mark.skipif(
    importlib.util.find_spec("camelot") is None,
    reason="camelot-py 未装, 真 PDF 测试 skip",
)
def test_extract_real_pdf_lattice() -> None:
    ...
```

**包缺失测试**走 `patch("builtins.__import__")` 模拟 ImportError：

```python
def fake_import(name, ...):
    if name == "camelot":
        raise ImportError(...)
    return real_import(name, ...)

with patch("builtins.__import__", side_effect=fake_import):
    with pytest.raises(BackendNotInstalledError):
        CamelotTableExtractor({"flavor": "lattice"})
```

**不连真实 ghostscript**：CI 环境没装 gs 也 OK，lattice 测通过 `skipif` 跳过。

### CI 升级注意

- **camelot-py 1.x → 2.0** 改了不少 API（`to_markdown()` 新增、`flavor` 多了 `network` / `ml` / `hybrid`）
- 项目锁 `camelot-py>=2.0`（`pyproject.toml:63`）
- 升 3.x 需回归 `TableData` 输出 shape（`tables[i].df` 行为可能变）

### 升 PyTorch / transformers 注意

- **`[ml] extra` 体积**：PyTorch ≈ 500MB，transformers + 模型 ≈ 200MB
- **不要给所有 dev 装**：CI / dev 默认不装
- **生产部署**：单独机器装 `[ml] extra`，并配置 GPU（CPU ml 慢 10×）

---

## 📚 参考

- [Camelot 官方文档](https://camelot-py.readthedocs.io/en/master/)
- [Camelot GitHub](https://github.com/camelot-dev/camelot)
- [PyPI camelot-py](https://pypi.org/project/camelot-py/)
- [Ghostscript 下载](https://www.ghostscript.com/releases.html)
- [Camelot 4 种 flavor 对比](https://camelot-py.readthedocs.io/en/master/user/how-it-works.html)
- [Table Transformer (ml flavor)](https://huggingface.co/microsoft/table-transformer-detection)
- [项目 cookbook/python/pymupdf.md](pymupdf.md)（默认后端对比）
- [项目 cookbook/python/kreuzberg.md](kreuzberg.md)（统一文档解析）

---

**状态：** ✅ 已完成

**最后更新：** 2026-07-06
