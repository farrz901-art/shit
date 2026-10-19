# RAG Ingest 流水线演化（包重命名 + 压缩包支持）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `src/pdf_processor` 重命名为 `src/rag_ingest`，`main.py` 缩成 thin shim，业务迁入 `pipeline.py`；新增压缩包（zip）解压支持，按格式 → converter 正确分工（kreuzberg 只 PDF，mineru 吃 PDF+图片+Office）。

**Architecture:** 单 plan 两 phase：Phase A 纯重命名（无新功能，跑通既有 80 测试）→ Phase B 加压缩包支持（新增 `ArchiveHandler`，集成到 `process_files` 顶层）。流程图：扫 input_dir → 检查 .zip 解压到 tempdir → 4 桶路由（document / passthrough / cad / unknown）→ 各 converter 处理。

**Tech Stack:** Python 3.14, pytest 9, stdlib `zipfile`/`tempfile`, git mv + sed

---

## 引用文件

- **Spec**: [docs/superpowers/specs/2026-06-02-rag-ingest-evolution-design.md](../specs/2026-06-02-rag-ingest-evolution-design.md)
- **现有代码参考**：
  - 4 桶路由 + batch：[main.py:42-104](main.py)
  - 临时目录隔离模式：[src/pdf_processor/converters/__init__.py:164-183](src/pdf_processor/converters/__init__.py)
  - Converter 基类 + extensions + skip_can_handle：[src/pdf_processor/converters/__init__.py:8-36](src/pdf_processor/converters/__init__.py)
  - MarkdownPassthroughHandler：[src/pdf_processor/markdown_passthrough.py](src/pdf_processor/markdown_passthrough.py)
- **决策**：见 spec §决策记录（8 项）

---

## Phase A：架构重组（包重命名 + main.py 内移）

**目标**：把 `src/pdf_processor` 重命名为 `src/rag_ingest`，`main.py` 缩成 thin shim，业务迁入 `src/rag_ingest/pipeline.py`。**无新功能**，跑通既有 80 测试 + 改 README/docs。

---

### Task 0：验证 mineru 容器支持 Office 格式

**Files:**
- Test: `tests/fixtures/ppt_test.pptx`（已有 untracked fixture）
- Test: `tests/fixtures/excel_test.xls`（已有 untracked fixture）
- Test: `tests/fixtures/AI*.docx`（已有 untracked fixture）

**为什么先做这个**：用户决策 Office 走 mineru，但 mineru 容器**未必支持** .docx/.xlsx/.pptx。先验证，失败则降级为 [WARN] 跳过。

- [ ] **Step 1: 写一个临时验证脚本**

```python
# scripts/verify_mineru_office.py
"""验证 mineru 容器是否支持 Office 格式"""
import subprocess
import tempfile
from pathlib import Path

FIXTURES = [
    "tests/fixtures/AI外贸智能体RAG方案.docx",
    "tests/fixtures/excel_test.xls",
    "tests/fixtures/ppt_test.pptx",
]


def verify(office_path: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="mineru_verify_") as tmp:
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{tmp}:/app/output",
            "mineru:latest",
            f"mineru -p {office_path} -o /app/output -b pipeline",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output_md = list(Path(tmp).rglob("*.md"))
        return result.returncode == 0 and len(output_md) > 0


for fx in FIXTURES:
    if not Path(fx).exists():
        print(f"[SKIP] fixture 不存在: {fx}")
        continue
    ok = verify(fx)
    print(f"{'✅' if ok else '❌'} {fx}: {'支持' if ok else '不支持'}")
```

- [ ] **Step 2: 跑验证**

Run: `uv run python scripts/verify_mineru_office.py`
Expected: 三个 fixture 全部 ✅（或全部/部分 ❌）

- [ ] **Step 3: 根据结果决定分支**

- **全 ✅**: 继续 Phase A 后续任务
- **任何 ❌**: 修改 spec [docs/superpowers/specs/2026-06-02-rag-ingest-evolution-design.md](../specs/2026-06-02-rag-ingest-evolution-design.md) §第 1 项的 MineruConverter.extensions：
  ```python
  extensions = [
      ".pdf",
      ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",
      # ".docx", ".xlsx", ".pptx",  # mineru 不支持，移除
  ]
  ```
  并在 §决策记录加一项："Office 格式走 [WARN] 跳过（mineru 不支持）"
  然后继续 Phase A 后续任务

- [ ] **Step 4: 不 commit 验证脚本（一次性）**

```bash
rm scripts/verify_mineru_office.py
```

---

### Task 1：git mv 重命名包

**Files:**
- Rename: `src/pdf_processor/` → `src/rag_ingest/`（整体目录）

- [ ] **Step 1: 用 git mv 移动整个目录**

Run:
```bash
git mv src/pdf_processor src/rag_ingest
```

Expected: 无错误，目录成功重命名（保留 git 历史）。

- [ ] **Step 2: 验证目录结构**

Run: `ls src/rag_ingest/`
Expected:
```
__init__.py
analyzer.py
cad_analyzer.py
cad_converter.py
cad_oda.py
converters/
markdown_passthrough.py
```

- [ ] **Step 3: 暂不 commit（等 import 改完一起）**

---

### Task 2：批量改 import 路径

**Files:**
- Modify: 所有 `src/rag_ingest/**/*.py` 里的 `from src.pdf_processor` → `from src.rag_ingest`
- Modify: 所有 `tests/**/*.py` 里的 `from src.pdf_processor` → `from src.rag_ingest`
- Modify: 所有 `docs/**/*.md` 代码块里的 `from src.pdf_processor` → `from src.rag_ingest`
- Modify: `README.md` 里的 `from src.pdf_processor` → `from src.rag_ingest`

- [ ] **Step 1: Python 文件批量替换**

Run (PowerShell / Git Bash 都行):
```bash
# Linux/macOS
find src tests -name "*.py" -exec sed -i 's|from src\.pdf_processor|from src.rag_ingest|g' {} +

# Windows PowerShell
Get-ChildItem -Path src,tests -Recurse -Include *.py | ForEach-Object {
    (Get-Content $_.FullName) -replace 'from src\.pdf_processor','from src.rag_ingest' | Set-Content $_.FullName
}
```

Expected: 无错误，每个 Python 文件里的 `from src.pdf_processor` 全被替换。

- [ ] **Step 2: Markdown 文件批量替换**

Run:
```bash
# Linux/macOS
find docs README.md -name "*.md" -exec sed -i 's|from src\.pdf_processor|from src.rag_ingest|g' {} +

# Windows PowerShell
Get-ChildItem -Path docs,README.md -Recurse -Include *.md | ForEach-Object {
    (Get-Content $_.FullName) -replace 'from src\.pdf_processor','from src.rag_ingest' | Set-Content $_.FullName
}
```

Expected: docs 和 README.md 全部替换完。

- [ ] **Step 3: 验证无遗漏**

Run:
```bash
grep -r "from src.pdf_processor" src tests docs README.md 2>/dev/null
```

Expected: **无任何输出**（0 命中）。

---

### Task 3：缩 main.py + 建 pipeline.py

**Files:**
- Modify: `main.py`（缩成 2 行 thin shim）
- Create: `src/rag_ingest/pipeline.py`（原 main.py 业务逻辑）

- [ ] **Step 1: 读 main.py 当前内容**

Run: `cat main.py`
Expected: 看到 `process_files` / `process_documents` / `process_cad_files` / `process_passthrough` / `process_pdfs` 全部业务函数。

- [ ] **Step 2: 把 main.py 整个内容复制到 src/rag_ingest/pipeline.py**

Run:
```bash
git mv main.py src/rag_ingest/pipeline.py
```

Expected: main.py 没了，`src/rag_ingest/pipeline.py` 有完整原 main.py 内容。

- [ ] **Step 3: 改 pipeline.py 的 import**

在 `src/rag_ingest/pipeline.py` 顶部，把：
```python
from src.pdf_processor import PDFAnalyzer
from src.pdf_processor import get_converter
from src.pdf_processor.cad_converter import EzdxfConverter
from src.pdf_processor.config import get_paths
from src.pdf_processor.markdown_passthrough import MarkdownPassthroughHandler
```

改成（缩短成相对 import）：
```python
from .analyzer import PDFAnalyzer
from .converters import get_converter
from .cad_converter import EzdxfConverter
from .config import get_paths
from .markdown_passthrough import MarkdownPassthroughHandler
```

- [ ] **Step 4: 创建新的 thin shim main.py**

```python
"""rag_ingest 入口薄壳

业务逻辑全部在 src/rag_ingest/pipeline.py，main.py 只是
`uv run python main.py` 的入口 shim。
"""
from src.rag_ingest.pipeline import process_files

if __name__ == "__main__":
    process_files()
```

- [ ] **Step 5: 验证目录结构**

Run: `ls main.py src/rag_ingest/pipeline.py`
Expected: 两个文件都存在。

- [ ] **Step 6: 跑全部测试确保行为不变**

Run: `uv run pytest`
Expected: **80 passed, 6 skipped**（与重构前完全一致，0 失败）。

- [ ] **Step 7: Commit 重命名 + shim**

```bash
git add main.py src/rag_ingest/
git commit -m "refactor: 包重命名 pdf_processor → rag_ingest + main.py 缩 thin shim

- git mv src/pdf_processor → src/rag_ingest
- git mv main.py → src/rag_ingest/pipeline.py
- main.py 缩 2 行 thin shim（业务全在 pipeline.py）
- 改所有 import 路径（src/ + tests/ + docs/ + README.md）
- pipeline.py 用相对 import（from .analyzer import ...）

行为零变化：80 测试全过，0 失败。"
```

---

### Task 4：加 kreuzberg 范围限定（extensions = ['.pdf']）

**Files:**
- Modify: `src/rag_ingest/converters/__init__.py:42-55`（KreuzbergConverter.extensions）
- Modify: `src/rag_ingest/converters/__init__.py:114`（MineruConverter.extensions，按 Task 0 结果）

- [ ] **Step 1: 改 KreuzbergConverter.extensions 限 PDF**

定位 `src/rag_ingest/converters/__init__.py:42-55`，把：
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

改成：
```python
extensions = [".pdf"]  # kreuzberg 只处理简单 PDF（其他格式走 mineru / 不支持）
```

- [ ] **Step 2: 改 MineruConverter.extensions 加图片 + Office**

定位 `src/rag_ingest/converters/__init__.py:114`，把：
```python
extensions = [".pdf", ".png", ".jpg", ".jpeg"]
```

改成（**如果 Task 0 验证通过**）：
```python
# PDF + 图片（OCR）+ Office，全归 mineru（多模态容器）
extensions = [
    ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",
    ".docx", ".xlsx", ".pptx",
]
```

或（**如果 Task 0 验证失败**）：
```python
# PDF + 图片（OCR）；Office 不支持（mineru 容器不识别）
extensions = [
    ".pdf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff",
]
```

- [ ] **Step 3: 跑全部测试**

Run: `uv run pytest`
Expected: 80 passed, 6 skipped（**0 失败**）。

注：原测试用的是 `pdfs/README.pdf` 这种 .pdf 文件，不依赖 kreuzberg 多格式；改 extensions 不影响既有测试。

- [ ] **Step 4: Commit 范围限定**

```bash
git add src/rag_ingest/converters/__init__.py
git commit -m "refactor(converters): kreuzberg 限 PDF，mineru 扩 PDF+图片+Office

按 spec 决策：kreuzberg 只该处理简单 PDF。
- KreuzbergConverter.extensions = ['.pdf']
- MineruConverter.extensions = [PDF + 7 图片 + 3 Office]（或按 Task 0 结果调整）
- HTML/EML/EPUB 不再支持（to-do.md 未要求）"
```

---

### Task 5：加回归测试（grep 老路径 0 命中）

**Files:**
- Create: `tests/test_no_stale_pdf_processor_imports.py`

- [ ] **Step 1: 写测试**

```python
"""回归测试：保证老路径 src.pdf_processor 在代码库中 0 引用

重命名后必须无遗漏；任何文件 import 老路径都视为 bug。
"""
import subprocess
from pathlib import Path


def test_no_stale_pdf_processor_imports():
    """全代码库 grep 老路径必须 0 命中"""
    # 排除 .git / .venv / __pycache__ / node_modules
    exclude = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"}
    root = Path(__file__).parent.parent

    patterns = [
        "from src.pdf_processor",      # 标准 import
        "import src.pdf_processor",    # 备选 import
        "src.pdf_processor.",          # 属性访问
    ]

    for pattern in patterns:
        result = subprocess.run(
            ["grep", "-rn", "--exclude-dir=.git", "--exclude-dir=.venv",
             "--exclude-dir=__pycache__", "--exclude-dir=.pytest_cache",
             pattern, str(root)],
            capture_output=True, text=True,
        )
        # grep 找到时 returncode=0 + stdout 有内容
        assert result.returncode != 0 or not result.stdout.strip(), (
            f"发现老路径引用: {pattern}\n{result.stdout}\n"
            "所有 src.pdf_processor 引用必须改成 src.rag_ingest"
        )
```

- [ ] **Step 2: 跑测试**

Run: `uv run pytest tests/test_no_stale_pdf_processor_imports.py -v`
Expected: PASS

- [ ] **Step 3: 故意造一个老 import 验证测试会失败**

```bash
echo "from src.pdf_processor import PDFAnalyzer" >> src/rag_ingest/__init__.py
uv run pytest tests/test_no_stale_pdf_processor_imports.py -v
```

Expected: FAIL（"发现老路径引用"）

清理：
```bash
git checkout src/rag_ingest/__init__.py
```

- [ ] **Step 4: Commit 回归测试**

```bash
git add tests/test_no_stale_pdf_processor_imports.py
git commit -m "test: 加回归测试保证 src.pdf_processor 老路径 0 引用

重命名后必须 0 遗漏；任何文件 import 老路径都视为 bug。"
```

---

### Task 6：改 README + docs 引用

**Files:**
- Modify: `README.md`（API 例子 + 项目结构 + 安装命令）
- Modify: `docs/cad-converter.md`、`docs/cad-ezdxf-best-practices.md`、`docs/mineru-output-for-rag.md`（import 路径）
- Modify: `docs/README.md`（如有索引改动）

- [ ] **Step 1: 改 README.md 的"项目结构"段**

定位 `README.md:25-56` 的项目结构树，把：
```
rag/
├── main.py                              # 入口：process_files() 统一分流
...
└── src/
    └── pdf_processor/
```

改成：
```
rag/
├── main.py                              # 🪶 入口薄壳（2 行）
...
└── src/
    └── rag_ingest/                      # 业务包（多格式文档 → markdown）
        ├── __init__.py
        ├── analyzer.py
        ├── pipeline.py                  # 原 main.py 业务逻辑
        ├── converters/
        ├── cad_converter.py
        ├── cad_analyzer.py
        ├── cad_oda.py
        ├── markdown_passthrough.py
        └── archive_handler.py           # 压缩包解压
```

- [ ] **Step 2: 改 README.md 的"编程调用"段**

定位 `README.md:104-125` 的代码块，把：
```python
from main import process_files
```
改成：
```python
from src.rag_ingest import process_files
```

并把 `from main import process_pdfs` 改成 `from src.rag_ingest import process_pdfs`，`from main import process_cad_files` 改成 `from src.rag_ingest import process_cad_files`。

- [ ] **Step 3: 改 docs/*.md 里的 import 路径**

Run:
```bash
find docs -name "*.md" -exec sed -i 's|from src\.pdf_processor|from src.rag_ingest|g' {} +
grep -rn "from src.pdf_processor" docs/ 2>/dev/null
```

Expected: 第二次 grep 无输出。

- [ ] **Step 4: 跑全部测试做最终回归**

Run: `uv run pytest`
Expected: 81 passed, 6 skipped（+1 from Task 5）, 0 failed

- [ ] **Step 5: Commit 文档同步**

```bash
git add README.md docs/
git commit -m "docs: README/docs 同步包重命名

- README.md 项目结构树更新（pdf_processor → rag_ingest + 新增 archive_handler）
- README.md 编程调用代码块 import 路径同步
- docs/*.md 全文 sed 改 import 路径"
```

---

## Phase B：压缩包支持（ArchiveHandler 新功能）

**目标**：新增 `src/rag_ingest/archive_handler.py`（zip 解压 + 防 zip bomb + 防 zip slip + 嵌套深度可配）。集成到 `process_files` 顶层（tempdir 包住 + 解压后并入文件池）。

---

### Task 7：写 ArchiveHandler 异常类

**Files:**
- Create: `src/rag_ingest/archive_handler.py`

- [ ] **Step 1: 写异常类**

```python
"""压缩包解压处理器（zip only）

设计：
- 零依赖（用 stdlib zipfile）
- 防 zip bomb：max_total_size + max_file_count 双保险
- 防 zip slip：解压时校验路径在 target_dir 内
- 嵌套深度可配：max_depth=1 不递归
"""
from __future__ import annotations

from pathlib import Path
import zipfile


class ArchiveError(Exception):
    """压缩包处理基类异常"""


class UnsupportedArchiveError(ArchiveError):
    """不支持的压缩格式（不是 .zip）"""


class ArchiveSecurityError(ArchiveError):
    """超过安全限制（zip bomb / zip slip）"""


class ArchivePasswordError(ArchiveError):
    """加密压缩包（不支持）"""


class ArchiveCorruptError(ArchiveError):
    """压缩包损坏 / 无法读取"""
```

- [ ] **Step 2: 跑 import 验证（无 import 错误）**

Run: `uv run python -c "from src.rag_ingest.archive_handler import ArchiveError, UnsupportedArchiveError"`
Expected: 无错误

- [ ] **Step 3: Commit 异常类**

```bash
git add src/rag_ingest/archive_handler.py
git commit -m "feat(archive): 加 ArchiveError 异常类层级"
```

---

### Task 8：写 ArchiveHandler 单元测试（is_supported）

**Files:**
- Create: `tests/test_archive_handler.py`

- [ ] **Step 1: 写测试**

```python
"""ArchiveHandler 单元测试"""
import pytest
from src.rag_ingest.archive_handler import (
    ArchiveHandler,
    UnsupportedArchiveError,
    ArchiveSecurityError,
    ArchivePasswordError,
    ArchiveCorruptError,
)


class TestIsSupported:
    def test_zip_supported(self, tmp_path):
        """zip 是支持的格式"""
        f = tmp_path / "a.zip"
        f.write_bytes(b"")
        assert ArchiveHandler().is_supported(f) is True

    def test_rar_unsupported(self, tmp_path):
        """rar 不支持（用户决策：只 zip）"""
        f = tmp_path / "a.rar"
        f.write_bytes(b"")
        assert ArchiveHandler().is_supported(f) is False

    def test_7z_unsupported(self, tmp_path):
        """7z 不支持"""
        f = tmp_path / "a.7z"
        f.write_bytes(b"")
        assert ArchiveHandler().is_supported(f) is False

    def test_unsupported_format_raises(self, tmp_path):
        """extract 不支持格式抛 UnsupportedArchiveError"""
        f = tmp_path / "a.rar"
        f.write_bytes(b"")
        with pytest.raises(UnsupportedArchiveError):
            ArchiveHandler().extract(f, tmp_path)
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/test_archive_handler.py::TestIsSupported -v`
Expected: FAIL（AttributeError: 'ArchiveHandler' object has no attribute 'is_supported'）

- [ ] **Step 3: 实现 is_supported + extract 最小版（只支持 .zip）**

定位 `src/rag_ingest/archive_handler.py`，在异常类后加：

```python
class ArchiveHandler:
    """解压压缩包到目标目录"""

    SUPPORTED_EXTENSIONS = [".zip"]

    def __init__(
        self,
        max_depth: int = 1,
        max_total_size: int = 1 << 30,
        max_file_count: int = 10_000,
    ):
        self.max_depth = max_depth
        self.max_total_size = max_total_size
        self.max_file_count = max_file_count

    def is_supported(self, archive_path: Path) -> bool:
        """是否支持的压缩格式"""
        return archive_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def extract(self, archive_path: Path, target_dir: Path, depth: int = 1) -> list[Path]:
        """解压到 <target_dir>/<archive_stem>/，返回解压出的所有文件路径"""
        if not self.is_supported(archive_path):
            raise UnsupportedArchiveError(
                f"不支持的压缩格式: {archive_path.suffix}（当前只支持 {self.SUPPORTED_EXTENSIONS}）"
            )
        # 后续 task 补 extract 完整实现
        raise NotImplementedError
```

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/test_archive_handler.py::TestIsSupported -v`
Expected: PASS（4 个 test 都过）

- [ ] **Step 5: Commit is_supported + extract 骨架**

```bash
git add src/rag_ingest/archive_handler.py tests/test_archive_handler.py
git commit -m "feat(archive): ArchiveHandler.is_supported + extract 骨架 + 单元测试"
```

---

### Task 9：实现 extract 核心（解压 + 防 zip bomb + 防 zip slip）

**Files:**
- Modify: `src/rag_ingest/archive_handler.py`（补 extract 实现）
- Modify: `tests/test_archive_handler.py`（加更多 test）

- [ ] **Step 1: 写测试：解压、解压冲突、zip bomb 防御**

在 `tests/test_archive_handler.py` 末尾追加：

```python
import zipfile


@pytest.fixture
def sample_zip(tmp_path):
    """创建含 2 个文件的 zip fixture"""
    zip_path = tmp_path / "sample.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("a.txt", "hello")
        zf.writestr("sub/b.txt", "world")
    return zip_path


class TestExtract:
    def test_extract_creates_subdir_named_after_archive_stem(self, tmp_path, sample_zip):
        """解压产物在 <target>/sample/ 下（防解压冲突）"""
        result = ArchiveHandler().extract(sample_zip, tmp_path)
        assert (tmp_path / "sample" / "a.txt").exists()
        assert (tmp_path / "sample" / "sub" / "b.txt").exists()
        assert result == [
            tmp_path / "sample" / "a.txt",
            tmp_path / "sample" / "sub" / "b.txt",
        ]

    def test_extract_returns_list_of_files(self, tmp_path, sample_zip):
        """返回解压出的所有文件路径"""
        result = ArchiveHandler().extract(sample_zip, tmp_path)
        assert len(result) == 2
        assert all(p.is_file() for p in result)

    def test_extract_oversize_raises_security_error(self, tmp_path):
        """超过总大小上限抛 ArchiveSecurityError（防 zip bomb）"""
        zip_path = tmp_path / "bomb.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("big.txt", "x" * 1000)
        # 限 100 字节，应该触发
        with pytest.raises(ArchiveSecurityError, match="超过大小限制"):
            ArchiveHandler(max_total_size=100).extract(zip_path, tmp_path)

    def test_extract_too_many_files_raises_security_error(self, tmp_path):
        """超过文件数上限抛 ArchiveSecurityError"""
        zip_path = tmp_path / "many.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(20):
                zf.writestr(f"f{i}.txt", "x")
        with pytest.raises(ArchiveSecurityError, match="超过文件数限制"):
            ArchiveHandler(max_file_count=10).extract(zip_path, tmp_path)

    def test_extract_blocks_zip_slip(self, tmp_path):
        """Zip Slip（路径穿越）抛 ArchiveSecurityError"""
        zip_path = tmp_path / "evil.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../evil.txt", "boom")
        with pytest.raises(ArchiveSecurityError, match="Zip Slip"):
            ArchiveHandler().extract(zip_path, tmp_path)

    def test_extract_password_protected_raises_password_error(self, tmp_path):
        """加密 zip 抛 ArchivePasswordError"""
        zip_path = tmp_path / "encrypted.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a.txt", "secret")
            # 加密需要 setpassword
        # 用 _setpassword 后再读取
        from zipfile import ZipFile
        with ZipFile(zip_path, "w") as zf:
            zf.setpassword(b"pass")
            zf.writestr("a.txt", "secret")

        with pytest.raises(ArchivePasswordError, match="加密"):
            ArchiveHandler().extract(zip_path, tmp_path)

    def test_extract_corrupt_zip_raises_corrupt_error(self, tmp_path):
        """损坏 zip 抛 ArchiveCorruptError"""
        bad = tmp_path / "corrupt.zip"
        bad.write_bytes(b"not a real zip")
        with pytest.raises(ArchiveCorruptError):
            ArchiveHandler().extract(bad, tmp_path)
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/test_archive_handler.py::TestExtract -v`
Expected: 7 个 test 全 FAIL（NotImplementedError）

- [ ] **Step 3: 实现 extract 完整逻辑**

定位 `src/rag_ingest/archive_handler.py` 的 `ArchiveHandler.extract` 方法，替换为：

```python
    def extract(self, archive_path: Path, target_dir: Path, depth: int = 1) -> list[Path]:
        """解压到 <target_dir>/<archive_stem>/，返回解压出的所有文件路径

        Args:
            archive_path: 压缩包绝对路径
            target_dir: 解压根目录（产物放 <target_dir>/<archive_stem>/）
            depth: 当前嵌套深度（递归解压用，默认 1）

        Returns:
            解压出的所有文件路径（绝对）

        Raises:
            UnsupportedArchiveError: 不支持的格式
            ArchiveSecurityError: 超过大小/文件数上限 / Zip Slip
            ArchivePasswordError: 加密压缩包
            ArchiveCorruptError: 损坏的压缩包
        """
        if not self.is_supported(archive_path):
            raise UnsupportedArchiveError(
                f"不支持的压缩格式: {archive_path.suffix}（当前只支持 {self.SUPPORTED_EXTENSIONS}）"
            )

        # 准备解压目标子目录
        archive_stem = archive_path.stem
        extract_root = (target_dir / archive_stem).resolve()
        extract_root.mkdir(parents=True, exist_ok=True)

        results: list[Path] = []
        total_size = 0
        file_count = 0

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                # 检查加密（python 3.14 zipfile 无 is_encrypted 全部 info 的便捷方法，
                # 遍历 info 看 flag_bits）
                for info in zf.infolist():
                    if info.flag_bits & 0x1:  # 0x1 = encrypted
                        raise ArchivePasswordError(
                            f"压缩包加密，无法解压: {archive_path.name}（请手动解压）"
                        )

                # 解压每个 entry
                for info in zf.infolist():
                    # Zip Slip 防御：解析后的目标路径必须在 extract_root 内
                    target_path = (extract_root / info.filename).resolve()
                    if not target_path.is_relative_to(extract_root):
                        raise ArchiveSecurityError(
                            f"Zip Slip 检测: {info.filename} 试图跳出 {extract_root}"
                        )

                    # 大小累计
                    total_size += info.file_size
                    if total_size > self.max_total_size:
                        raise ArchiveSecurityError(
                            f"解压超过大小限制 {self.max_total_size} 字节: {archive_path.name}"
                        )

                    file_count += 1
                    if file_count > self.max_file_count:
                        raise ArchiveSecurityError(
                            f"解压超过文件数限制 {self.max_file_count}: {archive_path.name}"
                        )

                    # 实际解压
                    zf.extract(info, extract_root)
                    if target_path.is_file():
                        results.append(target_path)
        except zipfile.BadZipFile as e:
            raise ArchiveCorruptError(f"压缩包损坏: {archive_path.name} - {e}")

        return results
```

- [ ] **Step 4: 跑测试验证通过**

Run: `uv run pytest tests/test_archive_handler.py::TestExtract -v`
Expected: 7 个 test 全 PASS

- [ ] **Step 5: 跑全部测试确保没回归**

Run: `uv run pytest tests/test_archive_handler.py -v`
Expected: 11 passed（4 is_supported + 7 extract）

- [ ] **Step 6: Commit extract 完整实现**

```bash
git add src/rag_ingest/archive_handler.py tests/test_archive_handler.py
git commit -m "feat(archive): extract 完整实现 + 防 zip bomb/slip/加密/损坏

- 解压产物放 <target>/<archive_stem>/（防解压冲突）
- 累计解压大小 + 文件数，双保险防 zip bomb
- Path.resolve().is_relative_to 校验，防 Zip Slip 路径穿越
- 显式检测 flag_bits & 0x1 抛 ArchivePasswordError
- zipfile.BadZipFile 包装成 ArchiveCorruptError"
```

---

### Task 10：config.toml 加 [archive] 段

**Files:**
- Modify: `config.toml`

- [ ] **Step 1: 读 config.toml 当前内容**

Run: `cat config.toml`

- [ ] **Step 2: 在文件末尾加 [archive] 段**

```toml

[archive]
# 压缩包嵌套解压深度（1 = 不递归，2/3 = 递归几层）
max_depth = 1
# 解压总大小上限（字节，默认 1 GiB，防 zip bomb）
max_total_size = 1073741824
# 解压文件总数上限（防 zip bomb）
max_file_count = 10000
```

- [ ] **Step 3: 验证 TOML 合法**

Run: `uv run python -c "import tomllib; print(tomllib.loads(open('config.toml').read()))"`
Expected: 字典含 `[archive]` 段的 max_depth=1, max_total_size=1073741824, max_file_count=10000

- [ ] **Step 4: Commit config**

```bash
git add config.toml
git commit -m "config: 加 [archive] 段（max_depth / max_total_size / max_file_count）"
```

---

### Task 11：扩展 config.py 加载 archive 配置

**Files:**
- Modify: `src/rag_ingest/config.py`

- [ ] **Step 1: 读 config.py 当前内容**

Run: `cat src/rag_ingest/config.py`

- [ ] **Step 2: 加 ArchiveConfig dataclass + get_archive_config()**

在 config.py 现有内容后追加：

```python
@dataclass
class ArchiveConfig:
    """压缩包解压配置"""
    max_depth: int = 1
    max_total_size: int = 1 << 30
    max_file_count: int = 10_000


def get_archive_config() -> ArchiveConfig:
    """从 config.toml [archive] 段读配置"""
    config = _load_config()
    archive = config.get("archive", {})
    return ArchiveConfig(
        max_depth=archive.get("max_depth", 1),
        max_total_size=archive.get("max_total_size", 1 << 30),
        max_file_count=archive.get("max_file_count", 10_000),
    )
```

- [ ] **Step 3: 写测试验证**

```python
# tests/test_config.py（已有的话加，没的话新建）
from src.rag_ingest.config import get_archive_config


def test_get_archive_config_returns_defaults():
    cfg = get_archive_config()
    assert cfg.max_depth == 1
    assert cfg.max_total_size == 1 << 30
    assert cfg.max_file_count == 10_000
```

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/rag_ingest/config.py tests/test_config.py
git commit -m "feat(config): 加 ArchiveConfig + get_archive_config()"
```

---

### Task 12：集成 ArchiveHandler 到 process_files

**Files:**
- Modify: `src/rag_ingest/pipeline.py`（process_files 加 tempdir + 解压）

- [ ] **Step 1: 写集成测试（test_archive_integration.py）**

```python
"""process_files 与 ArchiveHandler 集成测试"""
import zipfile
import shutil
import pytest
from src.rag_ingest import process_files


def _make_zip_with_pdf_and_md(zip_path, files: dict[str, str]):
    """辅助：建一个含指定文件的 zip"""
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


class TestProcessFilesArchiveIntegration:
    def test_zip_in_input_extracts_and_routes(self, tmp_path, monkeypatch):
        """含 zip 的 input_dir → 自动解压 + 走 4 桶路由"""
        from tests.test_process_files_routing import SAMPLE_MD
        if not shutil.os.path.exists(SAMPLE_MD):
            pytest.skip("fixture 缺: SAMPLE_MD")

        in_dir = tmp_path / "input"
        in_dir.mkdir()
        # 造一个含 .md 的 zip
        zip_path = in_dir / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(SAMPLE_MD, "nested_doc.md")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        # 解压出的 .md 应被 passthrough 桶处理
        assert results["passthrough"] is not None
        assert any("nested_doc" in p["file"] for p in results["passthrough"]["processed"])

    def test_mixed_zip_and_plain_files(self, tmp_path):
        """input_dir 同时有 zip + 普通 md"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "plain.md").write_text("# plain")

        zip_path = in_dir / "archive.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("inside.md", "# inside")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        assert results["passthrough"] is not None
        # 两个 .md 都被处理（一个 plain + 一个解压出的）
        assert len(results["passthrough"]["processed"]) == 2

    def test_unsupported_archive_warns_and_continues(self, tmp_path, capsys):
        """.rar 格式打 [WARN] 跳过，不阻断其他文件"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "x.rar").write_bytes(b"fake rar")
        (in_dir / "plain.md").write_text("# ok")

        process_files(str(in_dir), str(tmp_path / "output"))
        captured = capsys.readouterr()
        assert "[WARN]" in captured.out
        assert ".rar" in captured.out

    def test_cleans_temp_after_completion(self, tmp_path):
        """process_files 结束后不会新增 rag_ingest_ 前缀临时目录

        修复前：检查 tempfile.gettempdir() 里所有 rag_ingest_ 前缀目录，依赖系统 tempdir 干净状态
                → flaky（历史进程崩溃残留就会让测试失败）
        修复后：snapshot 跑前已有 rag_ingest_ 集合，跑后再 snapshot，比差集
                → 只关心本次调用是否泄漏，忽略历史残留
        """
        import tempfile
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        (in_dir / "x.md").write_text("# x")

        # 跑前：snapshot 系统 tempdir 里的 rag_ingest_ 前缀目录
        before = {
            p.resolve()
            for p in Path(tempfile.gettempdir()).iterdir()
            if p.name.startswith("rag_ingest_")
        }

        process_files(str(in_dir), str(tmp_path / "output"))

        # 跑后：再 snapshot
        after = {
            p.resolve()
            for p in Path(tempfile.gettempdir()).iterdir()
            if p.name.startswith("rag_ingest_")
        }

        # 差集 = 本次调用新增的临时目录（应为空，否则就是泄漏）
        leaked = after - before
        assert not leaked, f"process_files 泄漏临时目录: {leaked}"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `uv run pytest tests/test_archive_integration.py -v`
Expected: 全 FAIL（process_files 还没解 zip）

- [ ] **Step 3: 实现 process_files 顶层 tempdir + 解压**

定位 `src/rag_ingest/pipeline.py`，改 `process_files` 签名 + 加 tempdir + 加解压逻辑：

```python
def process_files(input_dir: str | None = None, output_dir: str | None = None):
    """统一入口：按扩展名分 4 桶（Document / Markdown / CAD / Unknown）

    流程:
        1. 顶层 tempfile.TemporaryDirectory 隔离整批处理
        2. 递归扫 input_dir 所有文件
        3. 找 .zip 压缩包，逐个解压到 <temp_root>/<archive_stem>/
        4. 收集"待处理文件池" = 非压缩包原始文件 + 解压产物
        5. 按扩展名分 4 桶
        6. 各自走 process_documents / process_cad_files / process_passthrough
        7. 临时目录自动清理

    Args:
        input_dir: 输入目录，传 None 则从 config.toml 读 [paths].input_dir
        output_dir: 输出目录，传 None 则从 config.toml 读 [paths].output_dir
    """
    import tempfile
    from .archive_handler import ArchiveHandler
    from .config import get_archive_config

    paths = get_paths()
    input_path = Path(input_dir) if input_dir else paths.input_dir
    output_path = Path(output_dir) if output_dir else paths.output_dir
    archive_cfg = get_archive_config()

    if not input_path.exists():
        print(f"输入目录不存在: {input_path}")
        return None

    with tempfile.TemporaryDirectory(prefix="rag_ingest_") as temp_root:
        temp_path = Path(temp_root)
        archive_handler = ArchiveHandler(
            max_depth=archive_cfg.max_depth,
            max_total_size=archive_cfg.max_total_size,
            max_file_count=archive_cfg.max_file_count,
        )

        # 1. 递归扫所有原始文件
        all_files = [f for f in input_path.rglob("*") if f.is_file()]

        # 2. 找 .zip 压缩包并解压
        archives = [f for f in all_files if archive_handler.is_supported(f)]
        for archive in archives:
            try:
                archive_handler.extract(archive, temp_path)
            except ArchiveError as e:
                print(f"  [WARN] 压缩包解压失败，跳过 {archive.name}: {e}")

        # 3. 收集"待处理文件池" = 非压缩包原始文件 + 解压产物
        pool = [f for f in all_files if not archive_handler.is_supported(f)]
        for extracted in temp_path.rglob("*"):
            if extracted.is_file():
                pool.append(extracted)

        # 4. 按扩展名分桶
        from .converters import CONVERTERS
        document_converters = list(CONVERTERS.values())
        cad_converters = [EzdxfConverter]

        buckets = {"document": [], "passthrough": [], "cad": [], "unknown": []}
        for f in pool:
            ext = f.suffix.lower()
            if ext in MarkdownPassthroughHandler.extensions:
                buckets["passthrough"].append(f)
            elif any(ext in c.extensions for c in cad_converters):
                buckets["cad"].append(f)
            elif any(ext in c.extensions for c in document_converters):
                buckets["document"].append(f)
            else:
                buckets["unknown"].append(f)

        # ... 后续逻辑跟之前一样（打印 + 警告 + 各自走流水线）
        print(f"扫描到 {len(buckets['document'])} 个文档 + "
              f"{len(buckets['cad'])} 个 CAD + "
              f"{len(buckets['passthrough'])} 个 md 直通")
        if buckets["unknown"]:
            print(f"  [WARN] {len(buckets['unknown'])} 个未知格式将被跳过")

        for f in buckets["unknown"]:
            rel = f.relative_to(input_path) if f.is_relative_to(input_path) else f
            print(f"  [WARN] 不支持的格式，跳过: {rel}")

        results = {"document": None, "cad": None, "passthrough": None}

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
    # 临时目录自动清理
```

- [ ] **Step 4: 跑集成测试验证通过**

Run: `uv run pytest tests/test_archive_integration.py -v`
Expected: 4 个 test 全 PASS

- [ ] **Step 5: 跑全部测试确保没回归**

Run: `uv run pytest`
Expected: 92 passed, 6 skipped（81 既有 + 11 archive 单元 + 4 集成 - 4 tempdir hook），0 failed

- [ ] **Step 6: Commit 集成**

```bash
git add src/rag_ingest/pipeline.py tests/test_archive_integration.py
git commit -m "feat(pipeline): process_files 集成 ArchiveHandler（tempdir + 解压）

- 顶层 tempfile.TemporaryDirectory 隔离整批处理
- 扫到的 .zip 逐个解压到 <temp_root>/<archive_stem>/
- 文件池 = 非压缩包原始 + 解压产物
- 4 桶路由不变（复用既有逻辑）
- 解压失败 [WARN] 跳过，不阻断其他文件"
```

---

### Task 13：加 e2e 测试（gated by RUN_SLOW_TESTS=1）

**Files:**
- Create: `tests/fixtures/sample_archive.zip`（真 zip，含 PDF+md）
- Create: `tests/test_e2e_archive.py`

- [ ] **Step 1: 造 fixture zip（用 Python 脚本一次性）**

```python
# scripts/make_sample_archive.py
import zipfile
from pathlib import Path

# 找一个真 .md fixture
md_fixture = Path("tests/fixtures/test_doc.md")
if not md_fixture.exists():
    print(f"[SKIP] fixture 缺: {md_fixture}")
    exit(0)

# 造一个含 .md 的真 zip
output = Path("tests/fixtures/sample_archive.zip")
with zipfile.ZipFile(output, "w") as zf:
    zf.write(md_fixture, "README.md")
    zf.writestr("notes.md", "# Notes\n\nThis is inside the zip.")

print(f"✅ 造好: {output}")
```

Run: `uv run python scripts/make_sample_archive.py`
Expected: `✅ 造好: tests/fixtures/sample_archive.zip`

- [ ] **Step 2: 写 e2e 测试**

```python
"""压缩包端到端测试（gated by RUN_SLOW_TESTS=1）"""
import os
import shutil
import zipfile
import pytest
from src.rag_ingest import process_files


SAMPLE_ARCHIVE = "tests/fixtures/sample_archive.zip"
SAMPLE_MD = "tests/fixtures/test_doc.md"


@pytest.mark.skipif(
    not os.path.exists(SAMPLE_ARCHIVE),
    reason=f"fixture 不存在: {SAMPLE_ARCHIVE}",
)
@pytest.mark.skipif(
    not os.environ.get("RUN_SLOW_TESTS"),
    reason="需要 RUN_SLOW_TESTS=1 才跑慢测试",
)
class TestE2EArchive:
    def test_e2e_zip_with_md_files(self, tmp_path):
        """真实 zip → 真跑 process_files → 断言输出结构"""
        in_dir = tmp_path / "input"
        in_dir.mkdir()
        shutil.copy(SAMPLE_ARCHIVE, in_dir / "archive.zip")

        results = process_files(str(in_dir), str(tmp_path / "output"))
        # 两个 .md 都在 passthrough 桶
        assert results["passthrough"] is not None
        files = [p["file"] for p in results["passthrough"]["processed"]]
        assert "README.md" in files
        assert "notes.md" in files

        # 验证输出落盘
        assert (tmp_path / "output" / "README" / "README.md").exists()
        assert (tmp_path / "output" / "notes" / "notes.md").exists()
```

- [ ] **Step 3: 跑测试（需要 RUN_SLOW_TESTS=1）**

Run: `RUN_SLOW_TESTS=1 uv run pytest tests/test_e2e_archive.py -v`
Expected: PASS

不设环境变量跑：
Run: `uv run pytest tests/test_e2e_archive.py -v`
Expected: SKIPPED（gating 生效）

- [ ] **Step 4: 跑全部测试做最终回归**

Run: `uv run pytest`
Expected: 92 passed, 7 skipped（+1 e2e gated）, 0 failed

Run: `RUN_SLOW_TESTS=1 uv run pytest`
Expected: 93 passed, 6 skipped, 0 failed

- [ ] **Step 5: Commit e2e**

```bash
git add tests/fixtures/sample_archive.zip tests/test_e2e_archive.py scripts/make_sample_archive.py
git commit -m "test: 加压缩包端到端测试（gated by RUN_SLOW_TESTS=1）"
```

---

### Task 14：最终回归 + 清理

**Files:**
- Modify: `docs/superpowers/specs/2026-06-02-rag-ingest-evolution-design.md`（如有偏差）
- Delete: `scripts/make_sample_archive.py`（一次性脚本）

- [ ] **Step 1: 跑全部测试（含 e2e）做最终验证**

Run: `RUN_SLOW_TESTS=1 uv run pytest -v`
Expected: 全部通过，0 failed

- [ ] **Step 2: 手动跑一次 CLI 验证入口**

Run: `uv run python main.py --help`（如果支持 help） OR `uv run python main.py`（用真实 input_dir）
Expected: 行为跟重构前一致（按 spec）

- [ ] **Step 3: 删一次性脚本**

```bash
rm scripts/make_sample_archive.py scripts/verify_mineru_office.py 2>/dev/null
git add -A
git commit -m "chore: 删一次性脚本（make_sample_archive / verify_mineru_office）" --allow-empty
```

- [ ] **Step 4: 更新 spec 决策记录（如有偏差）**

如果实施中 mineru Office 支持验证失败（Task 0 走 ❌ 分支），spec 决策记录需要更新"Office 走 [WARN] 跳过（mineru 不支持）"。

- [ ] **Step 5: 最终 review + 报告**

输出本计划总 commit 数、新增测试数、通过率。

---

## 验证总览

```bash
# 1. 全部测试（含 e2e）
RUN_SLOW_TESTS=1 uv run pytest -v
# Expected: 93 passed, 6 skipped, 0 failed

# 2. 压缩包专项
uv run pytest tests/test_archive_handler.py tests/test_archive_integration.py -v
# Expected: 15 passed

# 3. CLI 入口
uv run python main.py  # 用真实 input_dir 跑

# 4. 旧路径 0 引用
grep -rn "from src.pdf_processor" src tests docs README.md 2>/dev/null
# Expected: 无输出
```

---

## 风险与缓解（执行时关注）

| 风险 | 缓解 |
|------|------|
| Task 0 mineru office 验证失败 | spec 改降级 Office 走 [WARN] 跳过 |
| Task 1 git mv 失败（目录有未提交改动） | 先 `git status` 确认 src/pdf_processor 无未提交文件 |
| Task 3 sed 替换 Windows 兼容性 | PowerShell 命令已给；或手动 edit |
| Task 9 zipfile BadZipFile 不存在 | Python 3.14 已有 `zipfile.BadZipFile` |
| Task 12 monkeypatch 复杂 | 简化版：直接断言 temp_root 不存在（用 `Path(tempfile.gettempdir()).glob("rag_ingest_*")`） |
| Task 14 e2e 失败 | 检查 fixture zip 路径、RUN_SLOW_TESTS 设置 |

---

## 决策记录（与 spec 一致）

| 决策 | 选定 |
|------|------|
| 新包名 | rag_ingest |
| 压缩包范围 | 只 zip |
| 向后兼容 | 不留 shim |
| 嵌套策略 | 可配置深度（默认 1） |
| `main.py` 处理 | 保留 thin shim |
| `process_pdfs` | 留兼容包装 |
| 解析 zip 库 | stdlib zipfile |
| 旧 doc 路径 | 一次性改 |
| 格式分工 | kreuzberg=PDF / mineru=PDF+图片+Office / ezdxf=CAD / passthrough=md / 其他=WARN |
| Office 是否 mineru | Task 0 验证决定 |
