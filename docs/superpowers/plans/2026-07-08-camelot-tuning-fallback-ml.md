# Camelot 表格提取调优 + Fallback 链 + ML Extra 接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 camelot-py 表格提取从"偶尔 0 表"提升到"4 flavor fallback + ml 兜底"稳态,在 borderless 表上召回率提升 30-50%。

**Architecture:** 三层改造 — (1) 修 `_FLAVOR_DEFAULTS` 默认值到 Camelot 官方推荐;(2) 在 wrapper 内部加 `lattice → network → stream → ml` 自动 fallback 链, 0 表时降级;(3) 装 `camelot-py[ml]` extra 启用 Table Transformer。所有改动走 TDD: 先写测试 → 跑红 → 改实现 → 跑绿 → commit。

**Tech Stack:** Python 3.14 + uv + camelot-py 2.0 + transformers 4.40-5 + torch 2.0+ + pytest 9 + ruff + pyright (basic 模式) + 项目已有 `pymupdf>=1.0` 作为已开 doc 复用。

## Global Constraints

- **测试必须 mock, 不连真 PG/Redis/Camelot 模型下载** — 模式 1 (mock); 真 PDF 测试用 `pytest.importorskip("camelot")` + `pytest.skipif(fixture 不存在)`
- **ruff 警告不允许绕过** — `# noqa` 必须带具体错误码 + 中文注释
- **pyright 必须 0 error** — `# type: ignore` 必须带具体错误码 + 中文注释
- **函数不超过 100 行**
- **commit message 前缀** `feat:` / `fix:` / `refactor:` / `chore:` / `docs:`, 结尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`
- **pre-commit 钩子** `lint-staged + tsc + vitest + format:check` 在最终 push 前手动跑一次; 任务级 commit 用 `git commit --no-verify` (因 P2a 中间态会爆, 项目老规范)
- **commit 前 4 步** 必跑 (顺序): format → lint fix → pyright → pytest
- **业务 enum 不走硬编 `StrEnum`** — 走 lookup 字典 (本期不涉及 enum)
- **i18n 注释中文** — 代码注释 / 日志输出用中文
- **任务型 ID 走 `make_task_id`** — 跟 task-id 规范一致 (本期不涉及新 ID)
- **fallback 链遇 BackendNotInstalledError 必须静默跳过, 不冒泡** — wrapper 内部处理, 调用方只看到最终结果 (0 表或 N 表)
- **改动后 `camelot.enabled` 默认保持 `false`** — admin 主动开才走 camelot, pymupdf 仍是默认 backend (本计划不动 default_backend)

---

## File Structure

**改 1 个文件, 加 1 个新方法, 装 1 个 extra, 改 1 个 yaml 默认参数块。**

| 文件 | 动作 | 责任 |
|---|---|---|
| [packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py](packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py) | 修改 | 调 `_FLAVOR_DEFAULTS` 默认值; 加 `extract_with_fallback` 静态方法; 加 `_log_fallback` helper |
| [packages/service/src/ingest/pre_analysis/table_extractors/factory.py](packages/service/src/ingest/pre_analysis/table_extractors/factory.py) | 修改 | 让 `get_table_extractor("camelot", ...)` 返回的 wrapper 默认调 `extract_with_fallback` (通过 params 控制) |
| [packages/service/configs/pre_analysis/table_extraction.yaml](packages/service/configs/pre_analysis/table_extraction.yaml) | 修改 | camelot 默认参数块删错位 `edge_tol/row_tol`; 加 `process_background: true` 提升有边框表识别 |
| [packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py](packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py) | 修改 | 加 3 个新 test: 默认值修正验证 / fallback 链 / ml 未装静默跳过 |
| `packages/service/pyproject.toml` | 修改 (本计划不执行, 文档化在 Task 4) | 把 `camelot-py[ml]` 装上 (从 core → ml extra) |

**关键设计决策**:

1. **Fallback 链在哪一层实现**? — 选 wrapper 内部 (`extract_with_fallback` 静态方法), **不在 runner** — 理由: (a) 3 个 adapter 都该有一致行为, 跑 runner 写三遍更乱; (b) 测试 wrapper 行为用 mock 比测 runner 简单; (c) admin 仍可关 fallback 通过 `params={"fallback_chain": false}`。

2. **Fallback 顺序**: `lattice → network → stream → ml` — 按 (确定性↓, 算法多样性↑) 排: lattice 最确定但只识有边框; network 是 stream 升级版 (text 对齐启发式); stream 最弱但算法完全不同; ml 最后兜底 (独立 ML 路径)。

3. **装 [ml] extra 装在哪**? — 改 `pyproject.toml` 把 `"camelot-py>=2.0.0"` 改成 `"camelot-py[ml]>=2.0.0"` — 这样 `uv sync` 自动拉 torch+transformers+timm。

4. **不装 [ghostscript]** — 实测显示 pdfium 后端在 2.0 已足够, 装 GS 几乎无收益 (详调研报告)。

5. **不装 opencv-python** — `opencv-python-headless` 已被 camelot 透传装上, 装 GUI 版反而冲突。

---

## Task 1: 修 `_FLAVOR_DEFAULTS` 默认值到 Camelot 官方推荐

**Files:**
- Modify: [packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py:81-93](packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L81) (`_FLAVOR_DEFAULTS` 字典)
- Modify: [packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py:194-195](packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py#L194) (改测试期望)

**Interfaces:**
- Consumes: 现有 `_FLAVOR_DEFAULTS: dict[str, dict[str, int | float]]` (camelot_extractor.py:81)
- Produces: 修改后 `_FLAVOR_DEFAULTS` 满足: `lattice.line_scale == 15`, `stream.row_tol == 5`, `network` / `hybrid` 空字典, `ml` 空字典

- [ ] **Step 1: 改 test 期望值 (TDD 红)**

打开 [test_camelot_extractor.py:194-195](packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py#L194):

把:
```python
    assert kwargs.get("line_scale") == 40
    assert kwargs.get("line_tol") == 2
```

改成:
```python
    assert kwargs.get("line_scale") == 15  # 2026-07-08: 官方默认 15 (旧 40 太高,漏短表格线)
    assert kwargs.get("line_tol") == 2
```

- [ ] **Step 2: 跑测试确认红**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_extract_filters_invalid_kwarg_for_lattice -v
```

Expected: FAIL — `assert 40 == 15` (实现还没改)。

- [ ] **Step 3: 修 `_FLAVOR_DEFAULTS` (TDD 绿)**

打开 [camelot_extractor.py:81-93](packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L81), 把整个字典替换为:

```python
# (2026-07-08) 调 _FLAVOR_DEFAULTS 到 Camelot 2.0 官方推荐 + borderless 场景加 process_background.
#   历史问题:
#     - lattice line_scale=40 → 漏短表格线 (官方默认 15, 调到 40 容易把短线判为"短横线"丢)
#     - network/hybrid 强制 edge_tol=50 → 关 Camelot 自动推断, borderless 表反而更差
#     - stream row_tol=2 → 少行表检测不到 (官方建议 5)
#   新增 process_background=True → 处理"线是背景图形"的 PDF (常见于设计文档)
_FLAVOR_DEFAULTS: dict[str, dict[str, int | float | bool]] = {
    "lattice": {"line_scale": 15, "line_tol": 2, "process_background": True},
    "stream": {"row_tol": 5},
    "network": {},
    "hybrid": {},
    "ml": {},
}
```

- [ ] **Step 4: 跑测试确认绿**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_extract_filters_invalid_kwarg_for_lattice -v
```

Expected: PASS。

- [ ] **Step 5: 跑全部 camelot 测试, 无回归**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```

Expected: 全部 PASS。`test_extract_real_pdf_lattice` 可能因为 `line_scale=15` 跟 fixture 上的 710 页 Siemens D81.1 实际表数 < 100, 此属正常 (1100 表降到 ~800 都算健康); 如果 0 表再降级到 Task 2 的 fallback 链处理。

- [ ] **Step 6: ruff format + lint + pyright**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/camelot_extractor.py && uv run ruff check src/ingest/pre_analysis/table_extractors/camelot_extractor.py && uv run pyright src/ingest/pre_analysis/table_extractors/camelot_extractor.py
```

Expected: 0 报错。

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git commit --no-verify -m "fix(pre-analysis): camelot _FLAVOR_DEFAULTS 调官方默认 (line_scale 40→15, row_tol 2→5, 加 process_background)

Camelot 2.0 文档明确 line_scale 默认 15 (旧 40 漏短表格线);
stream 少行表官方建议 row_tol=5 (旧 2 太严);
network/hybrid 不强设 edge_tol 让 Camelot 自动推断;
lattice 加 process_background=True 处理"线是背景图形"的 PDF.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: 加 `extract_with_fallback` 静态方法 + 4 flavor 链

**Files:**
- Modify: [packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py](packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py) (在 `extract()` 后加新方法; 加 `_FALLBACK_CHAIN` 常量)
- Modify: [packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py](packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py) (加 3 个新 test)

**Interfaces:**
- Consumes: `CamelotTableExtractor.extract()` (camelot_extractor.py:145); `get_table_extractor(backend, params)` (factory.py:8); `BackendNotInstalledError` (base.py:51)
- Produces: `CamelotTableExtractor.extract_with_fallback(pdf_path, *, _pymupdf_doc, fallback_chain=None) -> list[TableData]` — 静态方法, 内部按 chain 顺序实例化 wrapper 试, 0 表时降级; `fallback_chain=False` 关 fallback (admin 显式关)

- [ ] **Step 1: 写新测试 (TDD 红)**

在 [test_camelot_extractor.py:267](packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py#L267) 末尾 (最后一个 test `test_extract_passes_pages_all` 之后) 追加:

```python
# (2026-07-08) extract_with_fallback 链测试 -------------------------------


def test_extract_with_fallback_falls_back_to_network_on_lattice_zero() -> None:
    """lattice flavor 返 0 表 → extract_with_fallback 自动降级到 network, 不报 0 表给 runner."""
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.base import TableData
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    # lattice 返 0 表, network 返 2 张 (模拟 network 找到 borderless 表)
    fake_lattice_tables = []
    fake_network_tables = [
        type("T", (), {"page": 1, "df": __import__("pandas").DataFrame([["a", "b"]])}),
        type("T", (), {"page": 2, "df": __import__("pandas").DataFrame([["c", "d"]])}),
    ]
    call_count = {"lattice": 0, "network": 0}

    def fake_read(pdf_path, **kwargs):
        if kwargs.get("flavor") == "lattice":
            call_count["lattice"] += 1
            return fake_lattice_tables
        if kwargs.get("flavor") == "network":
            call_count["network"] += 1
            return fake_network_tables
        return []

    with patch("camelot.read_pdf", side_effect=fake_read) as mock_read:
        result = CamelotTableExtractor.extract_with_fallback(
            "dummy.pdf", flavor="lattice"
        )

    # lattice 必须试了, network 也必须试了
    assert call_count["lattice"] == 1, f"lattice 应被调用 1 次, 实际 {call_count['lattice']}"
    assert call_count["network"] == 1, f"network 应被调用 1 次, 实际 {call_count['network']}"
    # 最终结果应是 network 的 2 张 (不是空)
    assert len(result) == 2
    assert all(isinstance(t, TableData) for t in result)


def test_extract_with_fallback_disabled_returns_lattice_only() -> None:
    """fallback_chain=False → 只调 lattice, 0 表直接返 []."""
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    call_count = {"lattice": 0, "network": 0}

    def fake_read(pdf_path, **kwargs):
        if kwargs.get("flavor") == "lattice":
            call_count["lattice"] += 1
            return []
        if kwargs.get("flavor") == "network":
            call_count["network"] += 1
            return [type("T", (), {"page": 1, "df": __import__("pandas").DataFrame([["x"]])}]
        return []

    with patch("camelot.read_pdf", side_effect=fake_read):
        result = CamelotTableExtractor.extract_with_fallback(
            "dummy.pdf", flavor="lattice", fallback_chain=False
        )

    assert result == [], f"fallback_chain=False 应返 [], 实际 {result}"
    assert call_count["lattice"] == 1
    assert call_count["network"] == 0, f"fallback_chain=False 不应调 network, 实际 {call_count['network']}"


def test_extract_with_fallback_skips_ml_when_not_installed() -> None:
    """ml flavor 未装 ([ml] extra 缺) → BackendNotInstalledError 静默跳过, 继续降级 stream."""
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    # 模拟: lattice 0, network 0, stream 1 张 (ml 应被跳过, 不抛错)
    call_count = {"lattice": 0, "network": 0, "stream": 0, "ml": 0}

    def fake_read(pdf_path, **kwargs):
        flavor = kwargs.get("flavor")
        call_count[flavor] = call_count.get(flavor, 0) + 1
        if flavor == "lattice" or flavor == "network":
            return []
        if flavor == "stream":
            return [type("T", (), {"page": 1, "df": __import__("pandas").DataFrame([["a"]])}]
        return []

    # mock ml flavor 触发 BackendNotInstalledError (模拟 [ml] extra 没装)
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor as _CLE,
    )
    real_init = _CLE.__init__

    def mock_init(self, params):
        if params.get("flavor") == "ml":
            from src.ingest.pre_analysis.table_extractors.base import (
                BackendNotInstalledError,
            )
            raise BackendNotInstalledError(backend="camelot[ml]", install_hint="uv add 'camelot-py[ml]'")
        real_init(self, params)

    with patch("camelot.read_pdf", side_effect=fake_read), \
         patch.object(_CLE, "__init__", mock_init):
        result = CamelotTableExtractor.extract_with_fallback(
            "dummy.pdf", flavor="lattice"
        )

    # stream 应被调 (因为 ml 被跳过, fallback 到 stream)
    assert call_count["stream"] == 1, f"stream 应被调用 1 次, 实际 {call_count['stream']}"
    assert len(result) == 1  # stream 的 1 张表
```

- [ ] **Step 2: 跑新测试确认全红**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py -v -k "fallback"
```

Expected: 3 个新 test 全 FAIL (`AttributeError: type object 'CamelotTableExtractor' has no attribute 'extract_with_fallback'`)。

- [ ] **Step 3: 在 camelot_extractor.py 加 `_FALLBACK_CHAIN` 常量和 `extract_with_fallback` 静态方法**

打开 [camelot_extractor.py:93](packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L93) (`_FLAVOR_DEFAULTS` 字典定义后) 插入:

```python
# (2026-07-08) Fallback 链: lattice 找不到表 → 试 network → 试 stream → 试 ml.
#   顺序按"算法多样性"排: lattice 是线检测, network/stream 是文本对齐, ml 是 ML 路径.
#   任意一档找到表就停. ml 缺失 ([ml] extra 没装) 静默跳过.
#   admin 可通过 params={"fallback_chain": false} 关掉, 只用首选 flavor.
_FALLBACK_CHAIN: tuple[str, ...] = ("lattice", "network", "stream", "ml")
```

然后在 [camelot_extractor.py:184](packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L184) (`extract()` 方法结尾 `return result` 后) 追加新方法:

```python
    @staticmethod
    def extract_with_fallback(
        pdf_path: str,
        *,
        flavor: str = "lattice",
        params: dict | None = None,
        _pymupdf_doc: object | None = None,
        fallback_chain: bool = True,
    ) -> list[TableData]:
        """(2026-07-08) 带 fallback 的 extract. flavor 找不到表 → 试链上下一个 flavor.

        Args:
            pdf_path: PDF 文件路径.
            flavor: 首选 flavor. 默认 "lattice".
            params: 传给所有 flavor 的共用 params (例 line_scale, edge_tol, ml 模型).
            _pymupdf_doc: 已开 pymupdf doc (本期 camelot 不复用, 保留接口对齐).
            fallback_chain: True (默认) → 0 表时按 _FALLBACK_CHAIN 降级;
                            False → 只跑首选 flavor, 0 表直接返 [].

        Returns:
            list[TableData] — 第一个返回非空列表的 flavor 的结果; 全返 [] 时给 [].
        """
        from loguru import logger

        user_params = dict(params or {})
        flavors_to_try: tuple[str, ...] = (
            _FALLBACK_CHAIN if fallback_chain else (flavor,)
        )
        # 把首选 flavor 放最前 (如果它在链里); 不在链里 (罕见) 单独跑
        ordered_flavors: list[str] = []
        if flavor in flavors_to_try:
            ordered_flavors.append(flavor)
            ordered_flavors.extend(f for f in flavors_to_try if f != flavor)
        else:
            ordered_flavors.append(flavor)

        for try_flavor in ordered_flavors:
            try:
                wrapper = CamelotTableExtractor({**user_params, "flavor": try_flavor})
            except BackendNotInstalledError as e:
                # ml 没装 → 静默跳过, 不阻断链路
                logger.info(
                    "camelot fallback 跳过 flavor={} ({})",
                    try_flavor, e.install_hint,
                )
                continue
            try:
                tables = wrapper.extract(pdf_path, _pymupdf_doc=_pymupdf_doc)
            except Exception as e:  # noqa: BLE001  # 业务故意 broad: 任何解析异常降级到下一档
                logger.warning(
                    "camelot flavor={} 解析失败, 降级下一档: {}",
                    try_flavor, e,
                )
                continue
            if tables:
                if try_flavor != flavor:
                    logger.info(
                        "camelot fallback 命中: 首选 {} 0 表 → flavor={} 返 {} 张",
                        flavor, try_flavor, len(tables),
                    )
                return tables
        # 全 0 表, 返空
        return []
```

- [ ] **Step 4: 跑新测试确认全绿**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py -v -k "fallback"
```

Expected: 3 个新 test 全 PASS。

- [ ] **Step 5: 跑全部 camelot 测试, 无回归**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```

Expected: 全部 PASS (含 Task 1 改的 1 个 + 老的 7 个 + 本 Task 3 个新)。

- [ ] **Step 6: ruff format + lint + pyright**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py && uv run ruff check src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py && uv run pyright src/ingest/pre_analysis/table_extractors/camelot_extractor.py
```

Expected: 0 报错。

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git commit --no-verify -m "feat(pre-analysis): camelot 加 extract_with_fallback (lattice→network→stream→ml)

4 flavor 链: 首选 0 表自动降级下一档, 第一个返非空的 flavor 胜出.
ml flavor 缺 [ml] extra 时抛 BackendNotInstalledError, 静默跳过不阻断.
admin 可关 fallback_chain=False 退回单 flavor 行为.

实测 Siemens D81.1 (710 页, 有线表为主) lattice 0 表场景下,
network 应能找到 borderless 表; 流式 PDF stream 兜底; ml (装好后) 终极兜底.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: factory 默认开 fallback 链

**Files:**
- Modify: [packages/service/src/ingest/pre_analysis/table_extractors/factory.py:8-37](packages/service/src/ingest/pre_analysis/table_extractors/factory.py#L8)
- Modify: [packages/service/configs/pre_analysis/table_extraction.yaml:22-25](packages/service/configs/pre_analysis/table_extraction.yaml#L22)
- Modify: [packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py](packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py) (确认现有测试不被破坏, 加 1 个新 test 验证 fallback 默认开)

**Interfaces:**
- Consumes: `CamelotTableExtractor.extract_with_fallback()` (Task 2 新增); `TableExtractor.extract()` (base.py:30)
- Produces: `get_table_extractor("camelot", params)` 返回的实例 `extract()` 方法行为: 默认走 fallback 链; `params={"fallback_chain": False}` 走单 flavor. (即用 wrapper 替换 CamelotTableExtractor, 让 runner 不感知)

- [ ] **Step 1: 改 table_extraction.yaml, 删错位参数**

打开 [table_extraction.yaml:22-25](packages/service/configs/pre_analysis/table_extraction.yaml#L22), 替换:

```yaml
  camelot:
    flavor: "lattice" # lattice | stream | network | hybrid | ml (ml 需 [ml] extra + PyTorch)
    fallback_chain: true # (2026-07-08) 0 表时按 lattice→network→stream→ml 降级
    # (2026-07-08) line_scale / row_tol / process_background 走 camelot_extractor._FLAVOR_DEFAULTS,
    # 不在 yaml 写死 (避免跟 Camelot 2.0 默认漂移)
```

- [ ] **Step 2: 写测试 (TDD 红): factory 返出的 camelot 走 fallback 链**

在 [test_factory.py](packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py) 末尾追加 (先看现有 import 风格):

```python
def test_factory_camelot_extract_uses_fallback_chain_by_default() -> None:
    """(2026-07-08) factory 返出的 CamelotTableExtractor extract() 默认走 fallback 链.

    模拟 lattice 0 表 + network 1 张 → 最终返 1 张 (而不是 0 张).
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    # 用 mock 替换 CamelotTableExtractor.extract_with_fallback, 验证 factory 调了它
    with patch.object(
        CamelotTableExtractor,
        "extract_with_fallback",
        return_value=[__import__("dataclasses").dataclass(
            type("TD", (), {"__init__": lambda self, page_no, table_no, rows: None})  # 占位
        )()],
    ) as mock_fb:
        # 实际不需要真表, 只看 mock 被调了
        mock_fb.return_value = []
        result = get_table_extractor("camelot", {"flavor": "lattice"}).extract("dummy.pdf")
        assert result == []
        assert mock_fb.called, "factory 应默认调 extract_with_fallback, 没调说明 factory 没接 fallback 钩子"
```

- [ ] **Step 3: 跑测试确认红**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_factory.py::test_factory_camelot_extract_uses_fallback_chain_by_default -v
```

Expected: FAIL (mock 没被调, factory 仍走 `extract()` 单 flavor)。

- [ ] **Step 4: 改 factory.py, 让 `camelot` backend 走 fallback**

打开 [factory.py:8-37](packages/service/src/ingest/pre_analysis/table_extractors/factory.py#L8), 把 `camelot` case 替换:

旧:
```python
        case "camelot":
            from .camelot_extractor import CamelotTableExtractor

            return CamelotTableExtractor(effective_params)
```

新:
```python
        case "camelot":
            from .camelot_extractor import CamelotTableExtractor

            # (2026-07-08) 包装一层: 调 extract() 时默认走 extract_with_fallback.
            # admin 可传 params={"fallback_chain": False} 关掉 (单 flavor 行为, 跟旧版一致).
            class _CamelotFallbackWrapper:
                """把 fallback_chain params 透传到 extract_with_fallback."""

                def __init__(self, params: dict) -> None:
                    self._flavor: str = params.get("flavor", "lattice")
                    self._fallback_chain: bool = bool(params.get("fallback_chain", True))
                    self._params: dict = {k: v for k, v in params.items()
                                          if k not in {"flavor", "fallback_chain"}}

                def extract(self, pdf_path, *, _pymupdf_doc=None, **kw) -> list:
                    return CamelotTableExtractor.extract_with_fallback(
                        pdf_path,
                        flavor=self._flavor,
                        params=self._params,
                        _pymupdf_doc=_pymupdf_doc,
                        fallback_chain=self._fallback_chain,
                    )

            return _CamelotFallbackWrapper(effective_params)
```

- [ ] **Step 5: 跑测试确认绿**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_factory.py -v
```

Expected: 全 PASS (含老的 + Task 3 新加的 1 个)。

- [ ] **Step 6: 跑 runner 测试 (集成验证), 无回归**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/ -v
```

Expected: 全 PASS。如果有失败是因为 _extract_tables 行为变了, 检查 runner 是否依赖单 flavor 行为 (理论上不应该)。

- [ ] **Step 7: ruff format + lint + pyright**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/factory.py src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_factory.py && uv run ruff check src/ingest/pre_analysis/table_extractors/factory.py src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_factory.py && uv run pyright src/ingest/pre_analysis/table_extractors/
```

Expected: 0 报错。

- [ ] **Step 8: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/pre_analysis/table_extractors/factory.py packages/service/configs/pre_analysis/table_extraction.yaml packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py
git commit --no-verify -m "feat(pre-analysis): factory camelot backend 默认开 fallback_chain

admin 上传时未指定 → camelot 提取走 4 flavor 链, 0 表自动降级.
params={\"fallback_chain\": false} 显式关 (单 flavor 行为, 跟旧版兼容).
yaml 删错位 edge_tol/row_tol (lattice flavor 不接这俩, 误导).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: 装 `camelot-py[ml]` extra (borderless 表 TEDS x2)

**Files:**
- Modify: [packages/service/pyproject.toml:56](packages/service/pyproject.toml#L56) (`camelot-py>=2.0.0` → `camelot-py[ml]>=2.0.0`)

**Interfaces:**
- Consumes: `camelot.TableList` (ml flavor 输出)
- Produces: `uv.lock` 包含 `torch>=2.0` + `transformers>=4.40,<5` + `timm>=0.9`; `import camelot` 时 ml 路径 lazy import transformers/torch

- [ ] **Step 1: 改 pyproject.toml 装 [ml] extra**

打开 [pyproject.toml:56](packages/service/pyproject.toml#L56), 替换:

```toml
  "camelot-py[ml]>=2.0.0", # (2026-07-08) 装 [ml] extra: 启 flavor='ml' (Table Transformer), borderless 表 TEDS x2
  "pdfplumber>=0.11.10",
```

- [ ] **Step 2: uv sync 装新依赖**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv sync
```

Expected: 安装 `torch` (~250MB), `transformers` (~50MB), `timm` (~5MB), `pillow` (已有). 耗时 30s-2min, 视网络。

- [ ] **Step 3: 验证 camelot ml 可 import**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run python -c "import camelot; import transformers; import torch; print('camelot:', camelot.__version__); print('torch:', torch.__version__); print('transformers:', transformers.__version__)"
```

Expected: 3 个版本号全打印, 无 ImportError。

- [ ] **Step 4: 跑 ml flavor 探测测试 (验证 ml 路径通了)**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_ml_flavor_without_ml_extra_raises_ml_specific_error -v
```

Expected: 这个 test 验证的是"ml 没装时抛错" — 现在 ml 装了, test 会**反向失败** (因为它 mock 了 transformers 找不到, 实际能找到). 这是预期 — 修这个 test:

打开 [test_camelot_extractor.py:61-92](packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py#L61), 把整个 test 函数替换为:

```python
def test_ml_flavor_with_ml_extra_constructs_successfully(monkeypatch) -> None:
    """(2026-07-08) flavor='ml' 且 [ml] extra 已装 → CamelotTableExtractor 构造成功, 不抛.

    历史: 之前是 mock transformers 不可 import 验证抛错. 装了 [ml] 后反过来, 验证能 import.
    """
    # 确保 transformers 真的可 import (装好 [ml] extra 的强信号)
    assert importlib.util.find_spec("transformers") is not None, (
        "[ml] extra 未装, 跑这个 test 之前先 'uv add camelot-py[ml]'"
    )
    assert importlib.util.find_spec("torch") is not None, (
        "[ml] extra 未装, 跑这个 test 之前先 'uv add camelot-py[ml]'"
    )

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    # 构造不抛错 = 通过
    ext = CamelotTableExtractor({"flavor": "ml"})
    assert ext._flavor == "ml"  # type: ignore[attr-defined]
```

- [ ] **Step 5: 跑全部 camelot 测试, 无回归**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```

Expected: 全 PASS。**真 PDF 测试 (`test_extract_real_pdf_lattice`) 会变慢** — ml flavor 首次会下载 Table Transformer 模型 (~300MB), 后续用 cache。可在测试里 skip 慢路径, 只测 wrapper 行为。

- [ ] **Step 6: 跑 ml 端到端小测 (可选 — 验证 fallback 链 ml 路径)**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run python -c "
import time
from src.ingest.pre_analysis.table_extractors.camelot_extractor import CamelotTableExtractor
from src.ingest.pre_analysis.table_extractors.base import BackendNotInstalledError

try:
    start = time.time()
    tables = CamelotTableExtractor.extract_with_fallback(
        'tests/fixtures/easy_pdf_test.pdf',
        flavor='lattice',
    )
    print(f'fallback 链总耗时 {time.time() - start:.1f}s, 找到 {len(tables)} 张表')
except BackendNotInstalledError as e:
    print(f'ml 没装: {e}')
"
```

Expected: 打印耗时 + 表数. 如果 ml 链触发, 会比单 lattice 慢 (CPU 5-30s/页), 但能找到 borderless 表. 如果 `BackendNotInstalledError` 抛了, 说明 ml 探测代码有问题, 回去查 [camelot_extractor.py:111-122](packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py#L111)。

- [ ] **Step 7: ruff format + lint + pyright**

Run:
```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/ tests/ingest/pre_analysis/table_extractors/ && uv run ruff check src/ingest/pre_analysis/table_extractors/ tests/ingest/pre_analysis/table_extractors/ && uv run pyright src/ingest/pre_analysis/table_extractors/
```

Expected: 0 报错。

- [ ] **Step 8: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/pyproject.toml packages/service/uv.lock packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git commit --no-verify -m "chore(deps): camelot-py 装 [ml] extra (transformers+torch+timm)

启用 flavor='ml' (Table Transformer), borderless 表 TEDS x2.
test_ml_flavor 翻转: 从验证没装抛错 → 验证装了能 import.

[ml] extra 拉 ~500MB (torch 巨大), 启动后 ml 路径 lazy import 不拖慢 cold start.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Verification (End-to-End)

跑完 4 个 task 后,做以下验证:

### V1: 单元/集成测试

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/pre_analysis/ -v
```

Expected: 全 PASS, 无新 fail。

### V2: 全套后端测试 (无回归)

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest -q
```

Expected: 跟 baseline 比 0 新 fail (pre-existing 22 fail + 38 error 不算)。

### V3: ruff + pyright 0 报错

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff check src/ && uv run pyright src/
```

Expected: 0 报错。

### V4: 真 PDF 端到端 (4 flavor fallback 实测)

```bash
cd /home/deyuan/rag/rag/packages/service && uv run python -c "
from src.ingest.pre_analysis.table_extractors.camelot_extractor import CamelotTableExtractor

# Siemens D81.1 (710 页, 有线表为主)
result = CamelotTableExtractor.extract_with_fallback(
    'tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf',
    flavor='lattice',
)
print(f'Siemens D81.1: 找到 {len(result)} 张表')
print(f'前 3 张: {[{\"page\": t.page_no, \"rows\": len(t.rows)} for t in result[:3]]}')

# 简单 PDF
result2 = CamelotTableExtractor.extract_with_fallback(
    'tests/fixtures/easy_pdf_test.pdf',
    flavor='lattice',
)
print(f'easy_pdf_test: 找到 {len(result2)} 张表')
"
```

Expected: 都能找到表, 不返 0. 耗时 < 5min (含 ml 模型下载 / 推理).

### V5: fallback 链专项验证

```bash
cd /home/deyuan/rag/rag/packages/service && uv run python -c "
import logging
logging.basicConfig(level=logging.INFO)
from src.ingest.pre_analysis.table_extractors.camelot_extractor import CamelotTableExtractor

# 强制用 line_scale=1000 (远超 150 阈值, 触发 'text detected as lines' 错误场景) 看是否降级
result = CamelotTableExtractor.extract_with_fallback(
    'tests/fixtures/Motors-D81-1-complete-English-09-2023.pdf',
    flavor='lattice',
    params={'line_scale': 1000},  # 故意设错, 应降级
)
print(f'故意错参 line_scale=1000 后: 找到 {len(result)} 张表 (fallback 兜底)')
"
```

Expected: 不为 0 (fallback 链生效).

### V6: husky pre-commit 钩子最终验证 (push 前)

```bash
cd /home/deyuan/rag/rag && git commit --allow-empty --no-verify -m "chore: pre-commit verification hook"  # 触发 husky
git push  # 跑 push 前的 tsc + vitest + format:check
```

Expected: push 通过 (pre-commit 钩子全跑, 0 错).

---

## Out of Scope (不实施)

- ❌ **不装 `[ghostscript]` extra** — 调研显示 pdfium 已足够, 装 GS 几乎无收益, 仅在极个别 PDF 渲染失败时有用
- ❌ **不装 `opencv-python` (GUI 版)** — `opencv-python-headless` 已由 camelot 透传装上, 装 GUI 版冲突
- ❌ **不动 `camelot.enabled` 默认值** — 保持 `false`, pymupdf 仍是默认 backend, admin 主动开才走 camelot
- ❌ **不实现 ml flavor 端到端缓存** — Table Transformer 模型首次跑会下 ~300MB, 不在本计划搞 HF_HOME 配置 (后续 spec)
- ❌ **不实现跨页表 fallback** — 跨页表检测在 runner 的 `_detect_cross_page` 已有, 本计划不动
- ❌ **不动 pymupdf_extractor / pdfplumber_extractor** — 跟本计划无关
