# Mineru 失败重试：磁盘真相源 + 逐文件单独重跑

**日期**: 2026-06-03
**状态**: 待批准

## Context

当前 `MineruConverter.convert_batch()` 在 docker mineru 容器抛 `ContainerError` 时，整批 N 个文件全部被标失败，即使 mineru 内部实际成功处理了一部分。

### 实测复现的失败链（实验 D，2026-06-03）

8 个文件的批处理（1LE1.pdf 96 页 + 7 个小文件 18 页）：

```
T+0s    mineru CLI 拆 2 batch 并发：
        batch 1 = task#1 [1LE1]              ← 大文档独占
        batch 2 = task#2 [其它 7 个]          ← 小文档凑批
T+57s   Completed batch 2/2: 18/114 pages | task#2 finished
        ← batch 2 写盘 7 个 md
T+227s  Processing pages 64/96 | task#1
        ← 1LE1 第一个 64 页 window 完成，要切换第二个 32 页 window
        Error: task#1 (1LE1): All connection attempts failed
        ← mineru CLI 跟本地 FastAPI 服务连接断了，重试全失败
T+227s  容器 exit 1
        ↓
        docker-py 抛 ContainerError
        ↓
Python  现有 convert_batch 没读磁盘就直接传到 pipeline.py
        ↓ pipeline.py 的 except Exception 把 8 个文件全标失败
        ↓ "成功: 0 | 失败: 8"
```

### 关键观察

`docker.errors.ContainerError` 抛出时，**磁盘上 batch 2 的 7 个 md 已经写好了**（mineru 是流式落盘，每个文档处理完就 flush）。只是现有代码 [src/rag_ingest/converters/__init__.py:173-198](../../../src/rag_ingest/converters/__init__.py#L173-L198) 在异常路径下完全不读磁盘，所有产出被丢弃。

### 用户决策

1. 用**磁盘上的 md 文件存在与否**作为成功/失败的真相源（不依赖 mineru stderr 格式解析）
2. 失败的文件**逐个单独重跑**（单文件不会触发 mineru 内部 batch 并发）
3. 重试**只做 1 次**——单文件单独跑还失败，就把 `[ERROR] ...` 写入 results 字典对应位置（不抛异常，由 pipeline.py 上层用现有的 `startswith("[ERROR]")` 判断处理）
4. mineru stderr 解析保留**仅作日志**，不作为决策依据

## 关键设计

### 1. 抽出 `_run_mineru()`，convert_batch 改为编排层

当前 [src/rag_ingest/converters/__init__.py:145-198](../../../src/rag_ingest/converters/__init__.py#L145-L198) 一个 `convert_batch` 同时管 "起 docker + 读磁盘"。拆分：

```python
class MineruConverter(Converter):
    # ...
    def _run_mineru(self, pdf_paths: list[str], output_dir: str) -> None:
        """跑一次 docker mineru 容器；ContainerError 原样抛出"""
        # 现有 convert_batch 里 "复制 → docker run" 那段
        # 注意：不再读 md，只负责"让 mineru 跑一遍"

    def convert_batch(self, pdf_paths: list[str], output_dir: str) -> dict[str, str]:
        """带 1 次重试的编排逻辑"""
        if not pdf_paths:
            return {}
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # 第 1 轮：批量跑
        run_error = None
        try:
            self._run_mineru(pdf_paths, output_dir)
        except docker.errors.ContainerError as e:
            run_error = e
            stderr = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            failed_hint = self._parse_failed_files(stderr)  # 仅作日志
            print(f"  [WARN] mineru 批处理报错（exit {e.exit_status}），从 stderr 解析疑似失败: {failed_hint}")

        # 用磁盘真相源分类
        results: dict[str, str] = {}
        retry_targets: list[str] = []
        for pdf_path in pdf_paths:
            md_path = self.resolve_md_path(pdf_path, output_dir, method="auto")
            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    results[pdf_path] = f.read()
            else:
                # 兜底走 _find_md_in_subdirs（兼容 office/auto 目录差异）
                content = self._find_md_in_subdirs(output_dir, Path(pdf_path).stem)
                if content:
                    results[pdf_path] = content
                else:
                    retry_targets.append(pdf_path)

        # 第 1 轮全成功 → 直接返回
        if not retry_targets:
            return results

        # 第 2 轮：失败文件逐个单独跑
        print(f"  [INFO] mineru 第 1 轮缺 {len(retry_targets)} 个文件输出，单独重试：{[Path(p).name for p in retry_targets]}")
        for failed_path in retry_targets:
            try:
                self._run_mineru([failed_path], output_dir)
            except docker.errors.ContainerError as retry_err:
                stderr = retry_err.stderr.decode("utf-8", errors="replace") if isinstance(retry_err.stderr, bytes) else (retry_err.stderr or "")
                results[failed_path] = f"[ERROR] mineru 单独重试仍失败 (exit {retry_err.exit_status}): {stderr[-500:]}"
                continue
            # 重试成功了，从磁盘读 md
            md_path = self.resolve_md_path(failed_path, output_dir, method="auto")
            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    results[failed_path] = f.read()
            else:
                content = self._find_md_in_subdirs(output_dir, Path(failed_path).stem)
                results[failed_path] = content or "[ERROR] mineru 单独重试容器成功但无 md 输出"

        return results
```

### 2. 新增 `_parse_failed_files(stderr) -> set[str]`（仅日志用）

```python
@staticmethod
def _parse_failed_files(stderr: str) -> set[str]:
    """从 mineru stderr 解析失败的文件 stem

    匹配格式：'- task#1 (1LE1): All connection attempts failed'
    返回 set[stem]；解析失败返回空集合（不影响决策）。
    """
    import re
    pattern = re.compile(r"- task#\d+ \((.+?)\):")
    return set(pattern.findall(stderr))
```

### 3. 不动的部分

- `resolve_md_path()` / `_find_md_in_subdirs()`：直接复用
- mineru docker 命令行（`mineru -p /app/input -o /app/output -b pipeline`）不变
- `DEFAULT_BACKEND = "pipeline"` 不变
- 调用方（`pipeline.py` 的 `process_documents`）不变，照样调 `converter.convert_batch(paths, output_dir)`，对 `results` 字典里 `[ERROR]` 开头的内容已有 `if content and not content.startswith("[ERROR]")` 判断

### 4. 行为变化对比

| 场景 | 现状 | 改后 |
|---|---|---|
| 一批 8 个全成功 | 8 个 md 全收 | 一致 |
| 一批 8 个，mineru 容器 exit 1，磁盘有 7 个 md | results = {}，上层标 8 个失败 | 7 个直接读盘 + 1 个单独重跑（成功率 100%） |
| 一批中某文件 mineru 真的处理不了（损坏 PDF） | results = {}，上层标 8 个失败 | 7 个成功 + 1 个 `[ERROR]`（标记失败的文件名清晰） |
| docker 镜像不存在 | 抛 `ImageNotFound`，不在本设计变更范围 | 一致 |
| GPU 不可用，容器秒退 | exit 1，磁盘 0 个 md，重试每个还是 exit 1 → 所有标 `[ERROR]` | 一致（不引入新坑，错误信息更细） |

## 测试设计

按 [feedback-no-mock-for-external-systems](../../../../../.claude/projects/c--Users-abcuc-Desktop-rag/memory/feedback-no-mock-for-external-systems.md) **不 mock docker**。

### 单元测试（快，无依赖，进 CI）

| 测试函数 | 输入 | 期望 |
|---|---|---|
| `test_parse_failed_files_single` | stderr 含 `- task#1 (1LE1): All connection attempts failed` | `{"1LE1"}` |
| `test_parse_failed_files_multiple` | stderr 含多个 task# 失败行 | 全部 stem |
| `test_parse_failed_files_no_match` | stderr 无 task# 行 | 空集合 |
| `test_parse_failed_files_chinese_stem` | stderr 含 `- task#3 (定制服务器05-26):` | `{"定制服务器05-26"}` |

### 集成测试（慢，~5 分钟，手动跑/标 `slow` marker）

`tests/integration/test_mineru_retry_e2e.py`：

| 测试 | 步骤 | 期望 |
|---|---|---|
| `test_mineru_retry_e2e` | 调 `MineruConverter().convert_batch([1LE1.pdf, jpg, png, complex, docx, pptx, xlsx, 定制服务器05-26.pdf], out_dir)` | `len(results) == 8`，每个 value 都不为空且不以 `[ERROR]` 开头 |

复用现有 [tests/_debug_mineru_concurrency.py](../../../tests/_debug_mineru_concurrency.py) 思路改造，断言 8 个文件全成功。

## 实施步骤

1. **TDD 红**：写 4 个 `test_parse_failed_files_*` 单测——此时 `_parse_failed_files` 还不存在，全部失败
2. **TDD 绿**：实现 `_parse_failed_files`，单测全过
3. **重构 `_run_mineru`**：把现有 docker 调用代码抽出来，原有 `convert_batch` 暂时调它，行为不变（确认现有用例不挂）
4. **改写 `convert_batch`**：加 try/except + 磁盘扫描 + 单文件重试
5. **集成测试红**：编写 `test_mineru_retry_e2e`（标 `@pytest.mark.slow`）——现有代码会失败
6. **集成测试绿**：跑集成测试，确认 8 个文件全成功
7. **清理临时文件**：`tests/_debug_in/`、`tests/_debug_out/`、`tests/_debug_concurrency_out/`、`tests/_debug_mineru_concurrency.py`（脚本已被集成测试取代）

## 不在本次范围

- mineru 容器 batch 并发的根本修复（需要改 mineru 源码或换 backend）
- pipeline.py 里 `print(f"  ✓ ...")` 的 GBK 编码报错（独立 bug，单独 PR）
- mineru output 目录布局重整（`<stem>/auto/<stem>.md` vs `<stem>/office/<stem>.md`）
- 多次 retry / 指数退避（YAGNI——已知 retry 1 次足够 cover 这次的并发问题）
