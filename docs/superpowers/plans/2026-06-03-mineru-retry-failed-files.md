# Mineru 失败重试 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `MineruConverter.convert_batch()` 在 docker 容器抛 `ContainerError` 时，先用磁盘上的 md 真相源分类哪些成功/哪些失败，再把失败文件**逐个单独**喂给 mineru 重跑 1 次，避免整批被一个文件拖垮。

**Architecture:** 把 `convert_batch` 拆成两层 —— 底层 `_run_mineru(paths, out)` 只负责"跑一次 docker mineru"（抛 ContainerError 原样上传）；编排层 `convert_batch` 跑完后扫磁盘分类成功/失败，失败的逐个调 `_run_mineru([single_file], out)` 重试 1 次，仍失败则把 `[ERROR] ...` 写进 results 字典。stderr 解析仅作日志诊断。

**Tech Stack:** Python 3.14, docker-py 7.1+, pytest 9, mineru:latest Docker 镜像（GPU pipeline backend）。

**Spec:** [docs/superpowers/specs/2026-06-03-mineru-retry-failed-files-design.md](../specs/2026-06-03-mineru-retry-failed-files-design.md)

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `src/rag_ingest/converters/__init__.py:145-198` | 改 | `MineruConverter`：新增 `_parse_failed_files`（纯函数）+ 抽出 `_run_mineru` + 改写 `convert_batch` 加 1 次重试 |
| `tests/test_converters.py` | 改 | 末尾追加 `TestMineruParseFailedFiles` 类（4 个 stderr 解析单测） |
| `tests/integration/__init__.py` | 新建 | 空包标记，让 pytest 识别 |
| `tests/integration/test_mineru_retry_e2e.py` | 新建 | 集成测试：8 文件复现实验 D 场景，期望全成功 |
| `tests/_debug_in/`、`tests/_debug_out/`、`tests/_debug_concurrency_out/`、`tests/_debug_mineru_concurrency.py` | 删 | 调试期临时产物，由集成测试取代 |

**Files that change together**：`converters/__init__.py` 跟两个测试文件强相关；删除 debug 文件作为独立 task（避免跟实现混提交）。

---

## Task 1: `_parse_failed_files` 纯函数（TDD 红→绿）

**Files:**
- Test: `tests/test_converters.py`（末尾追加 `TestMineruParseFailedFiles` 类）
- Modify: `src/rag_ingest/converters/__init__.py`（`MineruConverter` 内新增静态方法 `_parse_failed_files`）

- [ ] **Step 1: 写 4 个失败单元测试**

在 `tests/test_converters.py` 文件末尾追加：

```python
class TestMineruParseFailedFiles:
    """MineruConverter._parse_failed_files —— 从 mineru stderr 解析失败的文件 stem（仅日志诊断用）"""

    def test_parse_failed_files_single(self):
        """单个 task 失败：解析出对应 stem"""
        stderr = (
            "INFO some startup line\n"
            "Error: 1 task(s) failed while processing documents:\n"
            "- task#1 (1LE1): All connection attempts failed\n"
        )
        assert MineruConverter._parse_failed_files(stderr) == {"1LE1"}

    def test_parse_failed_files_multiple(self):
        """多个 task 失败：全部 stem 都拿到"""
        stderr = (
            "Error: 2 task(s) failed while processing documents:\n"
            "- task#1 (1LE1): All connection attempts failed\n"
            "- task#3 (complex_pdf_test): some other error\n"
        )
        assert MineruConverter._parse_failed_files(stderr) == {"1LE1", "complex_pdf_test"}

    def test_parse_failed_files_no_match(self):
        """stderr 不含 task# 行（镜像缺失场景）→ 空集合"""
        stderr = "docker: Error response from daemon: pull access denied"
        assert MineruConverter._parse_failed_files(stderr) == set()

    def test_parse_failed_files_chinese_stem(self):
        """中文文件名 stem 能解析"""
        stderr = "- task#3 (定制服务器05-26): All connection attempts failed\n"
        assert MineruConverter._parse_failed_files(stderr) == {"定制服务器05-26"}
```

- [ ] **Step 2: 跑测试看 4 个全红**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py::TestMineruParseFailedFiles -v
```

期望：4 个测试全 FAIL，错误是 `AttributeError: type object 'MineruConverter' has no attribute '_parse_failed_files'`

- [ ] **Step 3: 实现 `_parse_failed_files`**

在 [src/rag_ingest/converters/__init__.py](../../../src/rag_ingest/converters/__init__.py) 文件顶部的 `import` 区加：

```python
import re
```

在 `MineruConverter` 类内 `_find_md_in_subdirs` 方法**上方**（即 `convert_batch` 方法之后、`_find_md_in_subdirs` 之前）添加：

```python
    @staticmethod
    def _parse_failed_files(stderr: str) -> set[str]:
        """从 mineru stderr 解析失败的文件 stem（仅日志用，不作为重试决策依据）

        匹配格式：'- task#1 (1LE1): All connection attempts failed'

        Args:
            stderr: mineru 容器 stderr 文本

        Returns:
            失败的 stem 集合；无匹配返回空集合
        """
        pattern = re.compile(r"- task#\d+ \((.+?)\):")
        return set(pattern.findall(stderr))
```

- [ ] **Step 4: 跑测试看 4 个全绿**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py::TestMineruParseFailedFiles -v
```

期望：4 个测试全 PASS。

- [ ] **Step 5: 跑全套 test_converters.py 看没回归**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py -v
```

期望：所有测试 PASS（既有 + 新加的 4 个）。

- [ ] **Step 6: Commit**

```bash
git add tests/test_converters.py src/rag_ingest/converters/__init__.py
git commit -m "feat(mineru): _parse_failed_files 从 stderr 解析失败文件 stem（仅日志）"
```

---

## Task 2: 抽出 `_run_mineru`（纯重构，行为不变）

**Files:**
- Modify: `src/rag_ingest/converters/__init__.py:145-198`（`MineruConverter.convert_batch`）

**目标**：把现有 `convert_batch` 里"复制到隔离目录 + docker run"这段抽到 `_run_mineru` 私有方法；`convert_batch` 暂时**只调一次 `_run_mineru` + 原样读 md**，外部行为完全不变。这一步只重构，方便 Task 3 加重试。

- [ ] **Step 1: 替换 `convert_batch` 整段实现**

在 [src/rag_ingest/converters/__init__.py:145-198](../../../src/rag_ingest/converters/__init__.py#L145-L198)，用下面整段替换现有的 `convert_batch` 方法体（包含 docstring）：

```python
    def convert_batch(self, pdf_paths: list[str], output_dir: str) -> dict[str, str]:
        """mineru 批量处理：一次处理所有 PDF。

        Task 2 重构：拆出 _run_mineru 子方法，本方法只负责调用 + 读 md。
        外部行为不变（Task 3 会加重试）。
        """
        if not pdf_paths:
            return {}

        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        self._run_mineru(pdf_paths, output_dir)

        # 读取所有生成的 markdown 文件
        results = {}
        for pdf_path in pdf_paths:
            md_path = self.resolve_md_path(pdf_path, output_dir, method="auto")
            if os.path.exists(md_path):
                with open(md_path, 'r', encoding='utf-8') as f:
                    results[pdf_path] = f.read()
            else:
                # 兜底：在 output_dir 下递归搜索同名 md，兼容 mineru 未来目录变更
                results[pdf_path] = self._find_md_in_subdirs(output_dir, Path(pdf_path).stem)
        return results
```

- [ ] **Step 2: 在 `convert_batch` 上方新增 `_run_mineru` 方法**

紧挨着 `convert_batch` 上方（即 `DEFAULT_BACKEND = "pipeline"` 常量之后、`convert_batch` 之前）添加：

```python
    def _run_mineru(self, pdf_paths: list[str], output_dir: str) -> None:
        """跑一次 docker mineru 容器；ContainerError 原样抛出。

        关键约束：mineru 命令扫整个 -p 输入目录，所以不能把用户的 input_dir
        直接挂进容器（会越界处理不属于本批的 PDF）。
        修法：建临时目录，只把本批 PDF 复制进去，容器只看到这批。
        """
        import docker
        from docker.types import DeviceRequest

        client = docker.from_env()
        try:
            with tempfile.TemporaryDirectory(prefix="mineru_input_") as isolated_input:
                # 复制本批 PDF 到隔离目录
                # 用 shutil.copy 而不是 link：跨文件系统 link 容易失败，copy 更稳
                for pdf_path in pdf_paths:
                    shutil.copy(pdf_path, isolated_input)

                # 关键：必须显式请求 GPU 设备，否则容器内 CUDA 不可用
                # （docker-py SDK 默认不传 GPU，等价于 docker run 没加 --gpus all）
                gpu_request = DeviceRequest(count=-1, capabilities=[["gpu"]])
                client.containers.run(
                    "mineru:latest",
                    f"mineru -p /app/input -o /app/output -b {self.DEFAULT_BACKEND}",
                    volumes={
                        isolated_input: {"bind": "/app/input", "mode": "ro"},
                        output_dir: {"bind": "/app/output", "mode": "rw"}
                    },
                    device_requests=[gpu_request],
                    remove=True
                )
            # 临时目录自动清掉
        finally:
            client.close()
```

- [ ] **Step 3: 跑全套 test_converters.py 看没回归**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py -v
```

期望：所有测试 PASS（重构不改外部行为）。

- [ ] **Step 4: Commit**

```bash
git add src/rag_ingest/converters/__init__.py
git commit -m "refactor(mineru): 抽出 _run_mineru 私有方法，convert_batch 暂保留单跑行为"
```

---

## Task 3: `convert_batch` 加磁盘扫描 + 1 次重试

**Files:**
- Modify: `src/rag_ingest/converters/__init__.py`（`MineruConverter.convert_batch`）

**目标**：把 Task 2 重构后的 `convert_batch` 改成 spec 里的"先批量跑 → 扫盘分类 → 失败逐个重试"编排。

- [ ] **Step 1: 用下面整段替换 Task 2 写的 `convert_batch`**

整段替换 `convert_batch` 方法体：

```python
    def convert_batch(self, pdf_paths: list[str], output_dir: str) -> dict[str, str]:
        """mineru 批量处理：失败时按磁盘真相源分类，失败文件逐个单独重跑 1 次。

        流程：
        1. 跑一次 mineru 批处理（不管成功/失败都继续往下）
        2. 用 resolve_md_path 扫每个 pdf_path 在 output_dir 下的 md
           - 存在 → 加入 results
           - 不存在 → 加入 retry_targets
        3. retry_targets 非空时，逐个调 _run_mineru([single_file])
           - 重试成功 → 读盘加入 results
           - 重试仍失败 → results[path] = "[ERROR] ..."
        """
        import docker

        if not pdf_paths:
            return {}

        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # 第 1 轮：批量跑（ContainerError 不让中断，磁盘真相源会兜住）
        try:
            self._run_mineru(pdf_paths, output_dir)
        except docker.errors.ContainerError as e:
            stderr = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            failed_hint = self._parse_failed_files(stderr)
            print(f"  [WARN] mineru 批处理 exit {e.exit_status}，stderr 解析疑似失败: {failed_hint}")

        # 用磁盘真相源分类
        results: dict[str, str] = {}
        retry_targets: list[str] = []
        for pdf_path in pdf_paths:
            md_path = self.resolve_md_path(pdf_path, output_dir, method="auto")
            if os.path.exists(md_path):
                with open(md_path, 'r', encoding='utf-8') as f:
                    results[pdf_path] = f.read()
            else:
                content = self._find_md_in_subdirs(output_dir, Path(pdf_path).stem)
                if content:
                    results[pdf_path] = content
                else:
                    retry_targets.append(pdf_path)

        # 第 1 轮全成功 → 直接返回
        if not retry_targets:
            return results

        # 第 2 轮：失败文件逐个单独跑（单文件不会触发 mineru 内部 batch 并发）
        retry_names = [Path(p).name for p in retry_targets]
        print(f"  [INFO] mineru 第 1 轮缺 {len(retry_targets)} 个文件输出，单独重试: {retry_names}")

        for failed_path in retry_targets:
            try:
                self._run_mineru([failed_path], output_dir)
            except docker.errors.ContainerError as retry_err:
                stderr = retry_err.stderr.decode("utf-8", errors="replace") if isinstance(retry_err.stderr, bytes) else (retry_err.stderr or "")
                results[failed_path] = f"[ERROR] mineru 单独重试仍失败 (exit {retry_err.exit_status}): {stderr[-500:]}"
                continue

            # 重试容器成功，读盘
            md_path = self.resolve_md_path(failed_path, output_dir, method="auto")
            if os.path.exists(md_path):
                with open(md_path, 'r', encoding='utf-8') as f:
                    results[failed_path] = f.read()
            else:
                content = self._find_md_in_subdirs(output_dir, Path(failed_path).stem)
                results[failed_path] = content or "[ERROR] mineru 单独重试容器成功但无 md 输出"

        return results
```

- [ ] **Step 2: 跑全套 test_converters.py 看没回归**

```bash
.venv/Scripts/python -m pytest tests/test_converters.py -v
```

期望：所有测试 PASS。此时单测覆盖的是 `_parse_failed_files`，新的重试逻辑由 Task 4 的集成测试覆盖。

- [ ] **Step 3: Commit**

```bash
git add src/rag_ingest/converters/__init__.py
git commit -m "feat(mineru): convert_batch 加磁盘真相源 + 失败文件逐个重试 1 次"
```

---

## Task 4: 集成测试（e2e 真实跑 docker）

**Files:**
- Create: `tests/integration/__init__.py`（空包标记）
- Create: `tests/integration/test_mineru_retry_e2e.py`

**目标**：用实验 D 的 8 文件场景验证修复确实让 mineru 桶 100% 成功（含 1LE1 走重试路径）。

- [ ] **Step 1: 建集成测试目录和包标记**

```bash
mkdir -p tests/integration
echo "" > tests/integration/__init__.py
```

- [ ] **Step 2: 写集成测试**

新建 `tests/integration/test_mineru_retry_e2e.py`：

```python
"""mineru 失败重试 e2e 集成测试

复现 spec 里的实验 D 场景：1LE1.pdf (96 页) + 7 个小文件一起批处理 →
mineru 内部 batch 并发 → task#1 失败 → 走单独重试路径 → 8 个最终全成功。

跑一次约 5-8 分钟（mineru 模型加载 + 1LE1 处理两次 + 其它 7 个一次）。
默认不跑，需手动指定 marker：
    pytest tests/integration/test_mineru_retry_e2e.py -m slow
"""
import shutil
from pathlib import Path

import pytest

from src.rag_ingest.converters import MineruConverter


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

# 实验 D 复现：8 个文件（mineru 桶）
EXPERIMENT_D_FILES = [
    "1LE1.pdf",                    # 96 页大文件，会被 mineru 拆 batch 独占
    "jpg_test.jpg",
    "png_test.png",
    "complex_pdf_test.pdf",
    "AI外贸智能体RAG方案.docx",
    "ppt_test.pptx",
    "excel_test.xlsx",
    "定制服务器05-26.pdf",
]


@pytest.mark.slow
def test_mineru_retry_e2e_experiment_d(tmp_path):
    """实验 D：8 个文件批处理，1LE1 触发 mineru 内部并发失败 → 走单独重试 → 全成功"""
    # 准备：fixtures 里所有文件都存在
    pdf_paths = []
    for name in EXPERIMENT_D_FILES:
        src = FIXTURES / name
        assert src.exists(), f"fixture 缺失: {src}"
        pdf_paths.append(str(src))

    out_dir = tmp_path / "mineru_out"
    out_dir.mkdir()

    # 跑
    converter = MineruConverter()
    results = converter.convert_batch(pdf_paths, str(out_dir))

    # 断言：返回字典含全部 8 个文件
    assert len(results) == len(EXPERIMENT_D_FILES), \
        f"results 应有 {len(EXPERIMENT_D_FILES)} 项，实际 {len(results)}"

    # 断言：每个文件都有非空、非 [ERROR] 开头的 md 内容
    failed = []
    for path, content in results.items():
        if not content or content.startswith("[ERROR]"):
            failed.append((Path(path).name, content[:200] if content else "<空>"))
    assert not failed, f"以下文件未成功: {failed}"

    # 断言：1LE1 内容长度像样（96 页文档，至少几万字符）
    le1_path = str(FIXTURES / "1LE1.pdf")
    assert len(results[le1_path]) > 50_000, \
        f"1LE1.md 内容过短 ({len(results[le1_path])} 字符)，可能不完整"
```

- [ ] **Step 3: 在 pyproject.toml 注册 `slow` marker**

打开 [pyproject.toml](../../../pyproject.toml)，在文件末尾追加：

```toml
[tool.pytest.ini_options]
markers = [
    "slow: 慢测试（>2 分钟，跑真实 docker / GPU）",
]
```

- [ ] **Step 4: 跑集成测试看绿（约 5-8 分钟）**

```bash
.venv/Scripts/python -m pytest tests/integration/test_mineru_retry_e2e.py -v -m slow --capture=no
```

期望：测试 PASS。日志里能看到：
- `[WARN] mineru 批处理 exit 1, stderr 解析疑似失败: {'1LE1'}`
- `[INFO] mineru 第 1 轮缺 1 个文件输出，单独重试: ['1LE1.pdf']`
- 测试最终 PASS

如果失败，看测试输出确认是 1LE1 没重试成 vs 其它文件丢了 vs assertion 太严格，按需诊断。

- [ ] **Step 5: 确认 -m "not slow" 默认跳过它**

```bash
.venv/Scripts/python -m pytest tests/ -m "not slow" --collect-only -q | tail -5
```

期望：`tests/integration/test_mineru_retry_e2e.py::test_mineru_retry_e2e_experiment_d` **不**在收集结果里（被 slow marker 过滤）。

- [ ] **Step 6: Commit**

```bash
git add tests/integration/__init__.py tests/integration/test_mineru_retry_e2e.py pyproject.toml
git commit -m "test(mineru): 集成测试 e2e 验证 8 文件重试路径全成功（slow marker）"
```

---

## Task 5: 清理调试期临时文件

**Files:**
- Delete: `tests/_debug_in/`、`tests/_debug_out/`、`tests/_debug_concurrency_out/`、`tests/_debug_mineru_concurrency.py`

**目标**：把调试中产生的临时输入输出和一次性脚本删掉，集成测试已经覆盖了它们的用途。

- [ ] **Step 1: 确认要删除的文件清单**

```bash
ls -la tests/_debug_in/ tests/_debug_out/ tests/_debug_concurrency_out/ 2>&1
ls -la tests/_debug_mineru_concurrency.py 2>&1
```

期望：4 个东西都存在（3 个目录 + 1 个脚本）。

- [ ] **Step 2: 删除**

```bash
rm -rf tests/_debug_in tests/_debug_out tests/_debug_concurrency_out tests/_debug_mineru_concurrency.py
```

- [ ] **Step 3: 验证删干净**

```bash
ls tests/_debug* 2>&1 || echo "全部清掉"
```

期望：`全部清掉`。

- [ ] **Step 4: 跑全套测试看没回归**

```bash
.venv/Scripts/python -m pytest tests/ -m "not slow" -v
```

期望：所有非 slow 测试 PASS（包括 Task 1 加的 `_parse_failed_files` 4 个单测）。

- [ ] **Step 5: Commit**

```bash
git add -A tests/
git commit -m "chore(tests): 删调试期临时文件（_debug_in/out/concurrency_out/脚本），由集成测试取代"
```

---

## 完成检查

实施完全部 5 个 task 后，确认：

1. **新分支已 5 个 commit**（spec + 4 个实现 commit + 1 个清理 commit）

   ```bash
   git log --oneline fix/mineru-retry-failed-files ^master
   ```

   期望看到（先后顺序）：
   - `docs: spec for mineru 失败重试设计...`（已存在）
   - `feat(mineru): _parse_failed_files 从 stderr 解析失败文件 stem`
   - `refactor(mineru): 抽出 _run_mineru 私有方法...`
   - `feat(mineru): convert_batch 加磁盘真相源 + 失败文件逐个重试 1 次`
   - `test(mineru): 集成测试 e2e 验证 8 文件重试路径全成功`
   - `chore(tests): 删调试期临时文件...`

2. **全套快速测试通过**：

   ```bash
   .venv/Scripts/python -m pytest tests/ -m "not slow" -v
   ```

3. **集成测试 PASS（手动跑 1 次）**：

   ```bash
   .venv/Scripts/python -m pytest tests/integration/test_mineru_retry_e2e.py -v -m slow --capture=no
   ```

4. **手动 main.py 跑一次验收**：用 `tests/fixtures` 作为 input_dir，期望 `成功: 8 | 失败: 0`（mineru 桶 8 个全成）

   ```bash
   .venv/Scripts/python main.py
   ```
