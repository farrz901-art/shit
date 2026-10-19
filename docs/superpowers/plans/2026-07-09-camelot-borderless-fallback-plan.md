# Camelot Borderless 表兜底 (ml + 并行 + 0 表门控) 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `camelot_extractor.py` 内启用 ml flavor (推荐值已 hardcode) + 按页并行 + 单页 0 表门控调 ml + 列重对齐 / 拆合并后处理 + C2 cross_page_merge 升级 `strategy="text"` 兜底, 解决用户报告 3 类问题 (漏识别 / 多表合 1 cell / 列错位).

**Architecture:** 把 `extract()` 从"整文档 1 调"改为"按页并行 (ThreadPoolExecutor 4 worker) → 单页 lattice → 0 表门控调 ml → 重对齐/拆合并后处理 → C1 stack_contiguous → C2 cross_page_merge (新增 strategy=\"text\") → filter_valid". ml 走 GPU Semaphore 限流, 运行期 nvml 探 free VRAM 算 max worker (1-6).

**Tech Stack:** Python 3.14 / camelot-py 2.0.6+ / transformers 4.57+ (ml extra) / pynvml (显卡探测) / ThreadPoolExecutor + Semaphore / pytest mode 1 mock / ruff + pyright.

## Global Constraints

- **Python 3.14**, 后端测试必须 100% mock (mode 1), 0 真实 PG/Redis/camelot/PDF 依赖
- **ruff + pyright 必须 0 error**, 不能 `# noqa` / `# type: ignore` 不带具体错误码
- **commit 前缀**: `feat:` / `fix:` / `refactor:` / `chore:` / `docs:`, 中文注释 + 中文日志
- **测试隔离模式 1 mock**: `unittest.mock.patch` 拦截 camelot / pynvml / PyMuPDF, 不开真 PDF 文件
- **不**改默认 `table_backend` (pymupdf 默认), admin 选 camelot 才生效
- **不**开新依赖 ([ml] extra `camelot-py[ml]` + `nvidia-ml-py` / `pynvml` 已在 pyproject)
- **不**删 `extract_with_fallback` (factory 现有 wrapper 调它), 只升级内部 `extract` 实现
- **不**改 `_CamelotFallbackWrapper` 调 `extract_with_fallback` 的入口签名, 只透传 4 个新 params
- **Klz 项目铁律**: 严禁 shim / 兼容代码 / 兜底包装 (新项目零技术债)
- **i18n**: 本期 UI 不暴露, 跳过 i18n 同步
- **路径惯例**: `cd packages/service && uv run pytest <files>` (不仓库根跑)

---

## Task 0: 给 `TableData` 加 `bbox` 字段 (spec 4.6 先决条件)

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/base.py:17-29`
- Modify: `packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py` (追加)

**Interfaces:**
- Consumes: 现有 `TableData` (frozen dataclass, 3 字段)
- Produces: `TableData.bbox: tuple[float, float, float, float] | None = None` — Task 5 C2 双 strategy dedup + 未来 Task 6 lattice/ml IoU 0.7/0.5 判重需要; frozen dataclass 故 `replace(bbox=...)` 可用. **不改 `__init__` 签名** (现有调用如 `TableData(page_no=1, table_no=1, rows=[])` 全不传 bbox → 用默认值 None)

### Step 0.1: 写失败的测试

`test_base.py` **末尾追加**:

```python
# (2026-07-09) bbox 字段, 给 spec 4.6 lattice/ml IoU dedup + C2 同页 strategy dedup 用.


def test_table_data_bbox_default_none() -> None:
    """(2026-07-09) TableData() 不传 bbox → 默认 None, 老调用全兼容."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    t = TableData(page_no=1, table_no=1, rows=[["a", "b"]])
    assert t.bbox is None


def test_table_data_bbox_can_be_set() -> None:
    """(2026-07-09) .replace(bbox=...) 设值, frozen dataclass 兼容."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    t = TableData(page_no=1, table_no=1, rows=[["a", "b"]])
    t_with_bbox = t.replace(bbox=(10.0, 20.0, 100.0, 200.0))
    assert t_with_bbox.bbox == (10.0, 20.0, 100.0, 200.0)
    assert t.bbox is None  # 原 t 不动 (frozen)


def test_table_data_bbox_in_equality() -> None:
    """(2026-07-09) frozen dataclass 自动生成 __eq__, bbox 不同时视作不同对象."""
    from src.ingest.pre_analysis.table_extractors.base import TableData

    a = TableData(page_no=1, table_no=1, rows=[["a"]], bbox=None)
    b = a.replace(bbox=(0.0, 0.0, 10.0, 10.0))
    assert a != b
```

### Step 0.2: 跑测试确认 red

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_base.py -k "bbox" -v`

Expected: 3 个 FAIL — `AttributeError: type object 'TableData' has no attribute 'bbox'`.

### Step 0.3: 改实现

`base.py` `TableData` 类:

```python
@dataclass(frozen=True)
class TableData:
    """单张表格单元. 3 个实现统一这个 shape, runner 不关心后端.

    Attributes:
        page_no: 1-based 页码 (跨页合并后是 str 如 "5+6")
        table_no: 1-based (该页内编号)
        rows: 二维字符串表格
        bbox: (x0, y0, x1, y1) PDF 坐标 bbox, None 表示未识别 (2026-07-09 新增).
    """

    # (2026-07-09) page_no 可 str: 跨页合并表编码 "5+6" 表示 5+6 页拼成 1 张
    page_no: int | str
    table_no: int
    rows: list[list[str]]
    # (2026-07-09) spec 4.6 + 4.7 需要 bbox 字段判重 (lattice/ml IoU + C2 同页 strategy dedup).
    # 默认 None 兼容老调用, frozen dataclass 用 .replace(bbox=...) 设值.
    bbox: tuple[float, float, float, float] | None = None
```

### Step 0.4: 跑测试确认 green

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_base.py -v`

Expected: 3 个新 PASS + 原有 test (filter_valid 等) 不动.

### Step 0.5: ruff + pyright

Run: `cd packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/base.py tests/ingest/pre_analysis/table_extractors/test_base.py && uv run ruff check src/ingest/pre_analysis/table_extractors/base.py tests/ingest/pre_analysis/table_extractors/test_base.py && uv run pyright src/ingest/pre_analysis/table_extractors/base.py tests/ingest/pre_analysis/table_extractors/test_base.py`

Expected: 0 error.

### Step 0.6: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/base.py packages/service/tests/ingest/pre_analysis/table_extractors/test_base.py
git commit -m "feat(base): TableData 加 bbox 字段 (spec 4.6/4.7 先决条件)"
```

---

## Task 1: ml flavor 推荐值写入 `_FLAVOR_DEFAULTS`

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (在 line 92 加 ml 推荐值)
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (在 `_LATTICE_KWARGS` 之后加 `_FACTORY_PARAMS` 白名单)
- Modify: `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` (追加)

**Interfaces:**
- Consumes: 无
- Produces:
  - `_FLAVOR_DEFAULTS["ml"] = {"detection_threshold": 0.3, "structure_threshold": 0.4, "row_tol": 5}` — admin 不传 param 时用这套推荐值 (spec 4.2, 依据: DETR 内部 cell 识别比 detection 准, row_tol=5 跟 stream 对齐)
  - `_FACTORY_PARAMS = frozenset({"max_page_workers", "ml_max_workers", "ml_device", "ml_timeout_sec"})` — 4 个新参数不走 `_allowed_kwargs` (那是 Camelot kwargs 白名单), 走 `_run_camelot_single_page` 直接消费, `_extract_single_page` / extract() 也直接 `params.pop()` 用

### Step 1.1: 写失败的测试

在 `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` **末尾追加**:

```python
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    _FLAVOR_DEFAULTS,  # noqa: PLC0415  # 测试访问私有常量验证推荐值
)


def test_flavor_defaults_ml_has_recommended_values() -> None:
    """(2026-07-09) ml flavor 推荐值写入 _FLAVOR_DEFAULTS,
    解决默认 detection_threshold=0.5 对 borderless 表召回率低的问题.

    工业实践 (microsoft/table-transformer-detection):
      detection_threshold=0.3 (borderless 提召回, 不激进到 0.2 避免假阳性)
      structure_threshold=0.4 (略高于 detection, cell 识别比表检测准)
      row_tol=5 (跟 stream 一致, 1-2 行小表也能识别)
    """
    ml_defaults = _FLAVOR_DEFAULTS["ml"]
    assert ml_defaults["detection_threshold"] == 0.3
    assert ml_defaults["structure_threshold"] == 0.4
    assert ml_defaults["row_tol"] == 5


def test_flavor_defaults_other_flavors_unchanged() -> None:
    """其他 flavor 推荐值不被 ml 改动影响. 项目原值 (2026-07-08 调整)."""
    assert _FLAVOR_DEFAULTS["lattice"] == {
        "line_scale": 15,
        "line_tol": 2,
        "process_background": True,
        "use_fallback": True,
    }
    assert _FLAVOR_DEFAULTS["stream"] == {"row_tol": 5}
    assert _FLAVOR_DEFAULTS["network"] == {}
    assert _FLAVOR_DEFAULTS["hybrid"] == {}
```

### Step 1.2: 跑测试确认 red

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_flavor_defaults_ml_has_recommended_values tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py::test_flavor_defaults_other_flavors_unchanged -v`

Expected: FAIL — `assert {'detection_threshold': ..., 'structure_threshold': 0.3, ...}.get('detection_threshold') == 0.3` 报 KeyError 或 `ml_defaults["detection_threshold"]` KeyError, 因为当前 `_FLAVOR_DEFAULTS["ml"] == {}`.

### Step 1.3: 改实现

在 `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py:92` 把:

```python
    "ml": {},
```

改为:

```python
    # (2026-07-09) ml 推荐值 (硬阈值, admin 无需懂):
    #   detection_threshold=0.3 → borderless 表提召回 (默认 0.5 太严)
    #   structure_threshold=0.4 → 略高于 detection, DETR 内部 cell 识别比表检测准
    #   row_tol=5 → 跟 stream 一致, 1-2 行小表也能识别
    "ml": {
        "detection_threshold": 0.3,
        "structure_threshold": 0.4,
        "row_tol": 5,
    },
```

### Step 1.4: 跑测试确认 green

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py -v`

Expected: 新增 2 个 PASS, 其它原有 test 仍绿.

### Step 1.5: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git commit -m "feat(camelot): ml flavor 推荐值写入 _FLAVOR_DEFAULTS"
```

---

## Task 2: 单页 0 表门控 + ml 兜底 (`_run_camelot_single_page` + `_extract_single_page`)

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (在 `_stack_contiguous_in_flavor` 前加 8 个新函数 + 把 `extract()` 改为按页并行)
- Modify: `packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` (追加)

**Interfaces:**
- Consumes: `_FLAVOR_DEFAULTS` (Task 1, Task 2 ml 分支显式 merge 进 params)
- Produces:
  - `_ML_MODEL_LOCK = threading.Lock()` — 模型懒加载互斥, 首次 5-10s 不重复
  - `_ML_MODEL: object | None = None` — 模块级单例, 进程内 0 二次加载
  - `_ensure_ml_loaded() -> object` — 懒加载 (acquire lock, return _ML_MODEL; 已 load 直接返)
  - `_looks_merged(t: TableData) -> bool` — 启发式: 1×1 长文本 (>=200 字符) + 换行 → True
  - `_run_camelot_single_page(pdf_path: str, page: int, flavor: str, params: dict) -> list[TableData]` — 单页调 camelot.read_pdf(pages=str(page)); ml 走 GPU Semaphore 限流 + 显式 merge `_FLAVOR_DEFAULTS[flavor]`; 返回含 bbox (Task 0 已加字段) 的 TableData
  - `_extract_single_page(pdf_path: str, page: int, params: dict) -> list[TableData]` — 单页调度: lattice → 0 表? → ml → 仍 0 表? → network → stream

### Step 2.1: 写失败的测试

在 `test_camelot_extractor.py` **末尾追加**:

```python
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    _looks_merged,
    _run_camelot_single_page,
    _extract_single_page,
)
from src.ingest.pre_analysis.table_extractors.base import TableData


# (2026-07-09) _looks_merged 启发式: 1×1 长文本 + 换行 → 多表合并 1 cell


def test_looks_merged_1x1_long_text_with_newline_returns_true() -> None:
    """典型场景: 多个 borderless 表被 stream 当成 1 cell 长文本."""
    long_text = "row1_val1 row1_val2 row1_val3\n" * 30  # > 200 字符 + 多换行
    t = TableData(page_no=1, table_no=1, rows=[[long_text]])
    assert _looks_merged(t) is True


def test_looks_merged_1x1_short_text_returns_false() -> None:
    """短文本不是合并, 排除 false positive."""
    t = TableData(page_no=1, table_no=1, rows=[["short"]])
    assert _looks_merged(t) is False


def test_looks_merged_multi_row_returns_false() -> None:
    """多行表不是合并, 只对 1 行触发启发式."""
    long_text = "x\n" * 30
    t = TableData(page_no=1, table_no=1, rows=[[long_text], ["short"]])
    assert _looks_merged(t) is False


def test_looks_merged_empty_rows_returns_false() -> None:
    """空表不触发启发式."""
    t = TableData(page_no=1, table_no=1, rows=[])
    assert _looks_merged(t) is False


# (2026-07-09) _run_camelot_single_page: mock camelot.read_pdf, 验证传 pages=str(page)


def test_run_camelot_single_page_calls_read_pdf_with_single_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单页调度: camelot.read_pdf 收到 pages=str(page), 不是 'all'."""
    mock_table_obj = _mk_camelot_table_stub(page_no=2, rows=[["a", "b"], ["1", "2"]])

    class _MockTableList:
        def __init__(self, items: list) -> None:
            self._items = items

        def __iter__(self) -> object:
            return iter(self._items)

    captured_kwargs: dict = {}

    def fake_read_pdf(path: str, **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return _MockTableList([mock_table_obj])

    monkeypatch.setattr("camelot.read_pdf", fake_read_pdf)

    result = _run_camelot_single_page("/tmp/fake.pdf", page=2, flavor="lattice", params={})
    assert result == [
        TableData(
            page_no=2,
            table_no=1,
            rows=[["a", "b"], ["1", "2"]],
        ),
    ]
    assert captured_kwargs["pages"] == "2"
    assert captured_kwargs["flavor"] == "lattice"


def test_run_camelot_single_page_returns_empty_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """camelot 抛异常 → 返 [], 不阻断 extract 流程."""

    def fake_read_pdf(path: str, **kwargs: object) -> object:
        raise RuntimeError("camelot internal error")

    monkeypatch.setattr("camelot.read_pdf", fake_read_pdf)

    result = _run_camelot_single_page("/tmp/fake.pdf", page=1, flavor="lattice", params={})
    assert result == []


# (2026-07-09) _extract_single_page: 0 表门控到单页级


def test_extract_single_page_lattice_ok_doesnt_call_ml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lattice 返表 → 不调 ml, 不降级 network/stream."""
    call_log: list[str] = []

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_log.append(flavor)
        if flavor == "lattice":
            return [TableData(page_no=page, table_no=1, rows=[["a", "b"]])]
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=1, params={})
    assert len(result) == 1
    assert call_log == ["lattice"]  # ml 未触发


def test_extract_single_page_lattice_0_ml_ok_returns_ml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lattice 0 表 → 调 ml → 返 ml 结果."""
    call_log: list[str] = []

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_log.append(flavor)
        if flavor == "ml":
            return [TableData(page_no=page, table_no=1, rows=[["x", "y"]])]
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=1, params={})
    assert len(result) == 1
    assert result[0].rows == [["x", "y"]]
    assert call_log == ["lattice", "ml"]  # 0 表门控触发 ml


def test_extract_single_page_both_0_falls_to_network_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lattice + ml 都 0 表 → network → stream (顺序按 _FALLBACK_CHAIN 不含 ml 第一档位)."""
    call_log: list[str] = []

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_log.append(flavor)
        if flavor == "network":
            return [TableData(page_no=page, table_no=1, rows=[["n", "m"]])]
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=3, params={})
    assert len(result) == 1
    assert call_log == ["lattice", "ml", "network"]  # stream 未触发 (network 返表就停)


def test_extract_single_page_all_0_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """4 档全 0 表 → 返 []."""
    call_log: list[str] = []

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        call_log.append(flavor)
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=1, params={})
    assert result == []
    assert call_log == ["lattice", "ml", "network", "stream"]  # 4 档全跑


# (2026-07-09) 共享 helper: 构造 mock camelot Table 桩


def _mk_camelot_table_stub(page_no: int, rows: list[list[str]]) -> object:
    """构造 camelot Table 桩: .page / .df 属性."""

    class _MockTable:
        def __init__(self) -> None:
            self.page = page_no

            class _Df:
                def __init__(self, r: list[list[str]]) -> None:
                    self._rows = r

                @property
                def values(self) -> object:
                    return self._rows

            self.df = _Df(rows)

    return _MockTable()
```

### Step 2.2: 跑测试确认 red

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py -k "looks_merged or run_camelot_single_page or extract_single_page" -v`

Expected: 9 个新 test 全 FAIL (FunctionNotFound 或 AttributeError).

### Step 2.3: 改实现

在 `camelot_extractor.py` `_stack_contiguous_in_flavor` 定义**之前**插入以下新代码 (放 module-level, 不嵌类内):

```python
import threading  # noqa: E402  # 跟 module 顶 add 新 import 兼容 Py3.14
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402

# (2026-07-09) ml 模型缓存 (进程级单例, 首次加载 5-10s 互斥).
# ml 推理调用走 _ensure_ml_loaded() 拿引用, 避免并发首次加载重复.
_ML_MODEL: object | None = None
_ML_MODEL_LOCK = threading.Lock()


def _ensure_ml_loaded() -> object:
    """(2026-07-09) ml 模型懒加载. 进程内单例, 首次 acquire Lock 加载 5-10s.

    Returns:
        ml 模型实例. 单测里可 monkeypatch 全函数返 mock 替代.

    Note:
        camelot 内部把模型加载藏在 read_pdf, 我们不直接持有 PyTorch 模型,
        但要确保同一进程内 ml 的"首次进入"是原子的. 这里 `_ML_MODEL` 仅作为
        "已加载哨兵" — 实际加载逻辑让 camelot 在首次 .read_pdf(flavor='ml') 时做.
        此函数返 _ML_MODEL, 若非 None 直接返 (已加载过); 否则 acquire lock
        后调一次 _run_camelot_single_page 触发 camelot 加载, 然后设 _ML_MODEL.
    """
    global _ML_MODEL
    if _ML_MODEL is not None:
        return _ML_MODEL
    with _ML_MODEL_LOCK:
        if _ML_MODEL is not None:  # double-check: 别的线程可能刚 load 完
            return _ML_MODEL
        # 哨兵: 实际不直接构造 model, 让 camelot 在 read_pdf() 首次进入时加载
        _ML_MODEL = object()
        return _ML_MODEL


# (2026-07-09) ml 推理 GPU 限流 Semaphore (模块级单例, 进程内懒初始化).
# 运行期 nvml 探 free VRAM 算 max worker 数 (1-6), admin 可显式覆盖.
_ML_INFERENCE_SEM: threading.Semaphore | None = None
_ML_SEM_LOCK = threading.Lock()

# (2026-07-09) 显存预算常量 (MB):
#   _ML_MODEL_VRAM_MB = TableTransformer fp16 权重 ~1 GB
#   _ML_INFERENCE_OVERHEAD_MB = 推理中间激活 + KV cache ~0.75 GB
#   _ML_SINGLE_INSTANCE_MB = 单实例约 1.75 GB
#   _ML_RESERVE_MB = 1 GB 给 OS / CUDA context / 浏览器 / IDE
#   _ML_MAX_WORKERS_CLAMP = 6 (6 × 1.75 GB = 10.5 GB, 不超过 12 GB 可用)
_ML_MODEL_VRAM_MB = 1024
_ML_INFERENCE_OVERHEAD_MB = 768
_ML_SINGLE_INSTANCE_MB = _ML_MODEL_VRAM_MB + _ML_INFERENCE_OVERHEAD_MB  # 1792 MB
_ML_RESERVE_MB = 1024
_ML_MAX_WORKERS_CLAMP = 6


def _detect_max_ml_workers(device: str) -> int:
    """(2026-07-09) 运行期 nvml 探测可用显存 → 算 ml 并发 worker 数.

    逻辑:
      free_mb = nvmlDeviceGetMemoryInfo().free // (1024 * 1024)
      available = max(0, free_mb - RESERVE)
      workers = available // SINGLE_INSTANCE
      clamp [1, ML_MAX_WORKERS_CLAMP]

    Args:
        device: "cuda" / "cpu". 非 cuda 直接返 1 (CPU 抢资源没用).

    Returns:
        int: 推荐 worker 数. 探测失败返 1 (保守 fallback).
    """
    if device != "cuda":
        return 1
    try:
        import pynvml  # 项目已用 (2026-06 nvidia-ml-py 切换, import 路径不变)

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        free_mb = mem_info.free // (1024 * 1024)
    except Exception as e:  # noqa: BLE001  # 探测是 hint, 失败保守返 1
        from loguru import logger as _log

        _log.warning("ml 显存探测失败, fallback workers=1: {}", e)
        return 1
    available = max(0, free_mb - _ML_RESERVE_MB)
    workers = available // _ML_SINGLE_INSTANCE_MB
    return max(1, min(_ML_MAX_WORKERS_CLAMP, workers))


def _get_ml_inference_sem(device: str, user_max: int | None) -> threading.Semaphore:
    """(2026-07-09) 懒初始化 ml inference Semaphore. 优先级: user_max > 探测 > 1.

    模块级单例, 进程内只创建一次 (后续复用, 不重探测避免抖动).

    Args:
        device: ml 推理设备 ("cuda" / "cpu").
        user_max: admin 显式覆盖. None → 自动探测.

    Returns:
        threading.Semaphore 实例.
    """
    global _ML_INFERENCE_SEM
    from loguru import logger as _log

    with _ML_SEM_LOCK:
        if _ML_INFERENCE_SEM is not None:
            return _ML_INFERENCE_SEM
        if user_max is not None and user_max > 0:
            workers = user_max
        else:
            workers = _detect_max_ml_workers(device)
        _log.info(
            "ml inference Semaphore 初始化 workers={} device={} (按 free VRAM 探测)",
            workers,
            device,
        )
        _ML_INFERENCE_SEM = threading.Semaphore(workers)
        return _ML_INFERENCE_SEM


def _looks_merged(t: TableData) -> bool:
    """(2026-07-09) 启发式: 1 行 1 cell 长文本 + 换行 → 疑似多个表合并.

    Camelot stream 在 borderless 场景会把整页表合并到 1 cell,
    含大量换行 (每行原表一行). 阈值 200 字符是经验值, 经测试不会 false-positive.

    Args:
        t: 单张 TableData.

    Returns:
        True 表示疑似合并, False 表示正常表.
    """
    if not t.rows:
        return False
    if len(t.rows) == 1 and len(t.rows[0]) == 1:
        text = t.rows[0][0]
        return len(text) > 200 and "\n" in text
    return False


def _run_camelot_single_page(
    pdf_path: str,
    page: int,
    flavor: str,
    params: dict,
) -> list[TableData]:
    """(2026-07-09) 单页调 camelot.read_pdf. ml 走 GPU Semaphore 限流 + model 单例.

    **关键**: ml 分支显式 merge `_FLAVOR_DEFAULTS[flavor]` (spec 4.2 推荐值), 否则
    管理员没显式传 detection_threshold=0.3 时, 用 Camelot 默认 0.5 对 borderless 召回率低.
    非 ml 分支不 merge (lattice/stream 有自己推荐值, 已写在 _FLAVOR_DEFAULTS,
    调用方应在 init 时 merge, 见 extract()).

    Args:
        pdf_path: PDF 路径.
        page: 1-based 页号.
        flavor: "lattice" | "stream" | "network" | "hybrid" | "ml".
        params: user params dict.

    Returns:
        该页 TableData 列表 (含 page_no + table_no + bbox), 失败/异常返 [].
    """
    import camelot  # type: ignore[import-not-found, reportPrivateImportUsage]
    from loguru import logger as _log

    merged_kwargs: dict[str, object] = dict(params)
    # (2026-07-09) ml 显式注入推荐值 — Task 1 写的 _FLAVOR_DEFAULTS["ml"] 必须用上.
    # user params 优先, 推荐值做 fallback. 这样 admin 没传 detection_threshold 时
    # 默认 0.3 (推荐) 而不是 Camelot 默认 0.5.
    if flavor == "ml":
        for k, v in _FLAVOR_DEFAULTS["ml"].items():
            merged_kwargs.setdefault(k, v)
        # ml 还需 _ensure_ml_loaded() (首次加载互斥) + Semaphore 限流
        _ensure_ml_loaded()
        device = str(merged_kwargs.get("device", "cuda"))
        user_max = merged_kwargs.get("ml_max_workers")  # type: ignore[arg-type]
        sem = _get_ml_inference_sem(device, user_max)
        with sem:
            return _call_camelot(pdf_path, page, flavor, merged_kwargs, _log)
    return _call_camelot(pdf_path, page, flavor, merged_kwargs, _log)


def _call_camelot(
    pdf_path: str,
    page: int,
    flavor: str,
    kwargs: dict[str, object],
    log: object,
) -> list[TableData]:
    """(2026-07-09) 调 camelot.read_pdf 单页 + 失败返 []. 已从 _run 抽出便于单测 mock."""
    import camelot  # type: ignore[import-not-found, reportPrivateImportUsage]  # lazy
    import inspect  # noqa: F401  # 接续点 (微 t2/t3 没必要, 仅占位避免 pylint 警告)

    try:
        tables = camelot.read_pdf(  # type: ignore[reportPrivateImportUsage]
            pdf_path,
            flavor=flavor,
            pages=str(page),
            **kwargs,  # type: ignore[reportArgumentType]
        )
    except Exception as e:  # noqa: BLE001  # camelot 抛任何异常 → 返 [] 不阻断流程
        log.warning("camelot flavor={} page={} 失败: {}", flavor, page, e)  # type: ignore[attr-defined]
        return []
    # camelot 返 TableList; 每个 .page / .df / ._bbox
    per_page_counts: dict[int, int] = {}
    result: list[TableData] = []
    for t in tables:
        page_no = int(t.page or 0)
        per_page_counts[page_no] = per_page_counts.get(page_no, 0) + 1
        rows: list[list[str]] = t.df.values.tolist()
        rows = [[str(cell) for cell in row] for row in rows]
        # (2026-07-09) TableData 现在有 bbox 字段 (Task 0), 把 camelot TableList
        # 元素的 _bbox 透传到 TableData (spec 4.6 IoU dedup 需用).
        bbox: tuple[float, float, float, float] | None = None
        raw_bbox = getattr(t, "_bbox", None)
        if raw_bbox is not None and len(raw_bbox) == 4:
            bbox = (float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3]))
        result.append(
            TableData(
                page_no=page_no,
                table_no=per_page_counts[page_no],
                rows=rows,
                bbox=bbox,
            ),
        )
    result.sort(key=lambda t: (t.page_no, t.table_no))
    return result


def _extract_single_page(
    pdf_path: str,
    page: int,
    params: dict,
) -> list[TableData]:
    """(2026-07-09) 单页调度. 顺序: lattice → 0 表门控调 ml → 仍 0 表 → network → stream.

    Args:
        pdf_path: PDF 路径.
        page: 1-based 页号.
        params: user params dict.

    Returns:
        第一个返回非空列表的 flavor 的结果; 全返 [] 时给 [].
    """
    from loguru import logger as _log

    tables = _run_camelot_single_page(pdf_path, page, "lattice", params)
    if tables:
        return tables
    _log.info("camelot lattice page={} 0 表, 调 ml 兜底", page)
    tables = _run_camelot_single_page(pdf_path, page, "ml", params)
    if tables:
        return tables
    _log.info("camelot ml page={} 仍 0 表, 降级 network", page)
    tables = _run_camelot_single_page(pdf_path, page, "network", params)
    if tables:
        return tables
    return _run_camelot_single_page(pdf_path, page, "stream", params)
```

**注**: 抽 `_call_camelot` (rev2 M1 改动), `_do_run_camelot_single_page` 改为 `_call_camelot` 去掉双层 import; log 透传仍是便于单测 mock.

### Step 2.3a: Task 2 测试更新 (跟实现同步)

把 Task 2 中所有 mock `_run_camelot_single_page` 的测试 (`test_extract_single_page_*` 4 个) 都加 1 行断言: `call_args` 拿到的是 `(path, page, flavor, merged_params)` tuple, `merged_params["detection_threshold"] == 0.3` (验证 H1 修法, 确认推荐值真到了 ml 调用的 params 里). 例如:

```python
def test_extract_single_page_lattice_0_ml_ok_returns_ml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """lattice 0 表 → 调 ml → 返 ml 结果 + 验证 ml 推荐值注入到 params."""
    call_log: list[tuple[str, str, dict]] = []  # (page, flavor, params)

    def fake_run(path: str, page: int, flavor: str, params: dict) -> list[TableData]:
        call_log.append((page, flavor, dict(params)))
        if flavor == "ml":
            return [TableData(page_no=page, table_no=1, rows=[["x", "y"]])]
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        fake_run,
    )

    result = _extract_single_page("/tmp/fake.pdf", page=1, params={})
    assert len(result) == 1
    assert result[0].rows == [["x", "y"]]
    # 验证 flavor 顺序
    assert [f for _, f, _ in call_log] == ["lattice", "ml"]
    # (2026-07-09) H1 验证: mock 不需要验证 merged, 因为 mock 直接断了 _run 内部. 但 mock 的入参
    # 是 _extract_single_page 透传的 {} — 真 merge 在 _run 内部做, 这里 mock 不走. 测试
    # _run_camelot_single_page 那个 case 才对. 因此下面挪到 test_run_camelot_single_page_*.
```

把 H1 验证挪到 `test_run_camelot_single_page_calls_read_pdf_with_single_page`:

```python
def test_run_camelot_single_page_ml_merges_recommended_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) H1 验证: ml 调 camelot.read_pdf 时 detection_threshold=0.3
    已自动注入 (Task 1 写的 _FLAVOR_DEFAULTS['ml']), 即使 admin 没显式传.
    """
    captured_kwargs: dict = {}

    def fake_read_pdf(path: str, **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return _MockTableList([])

    monkeypatch.setattr("camelot.read_pdf", fake_read_pdf)

    _run_camelot_single_page("/tmp/fake.pdf", page=1, flavor="ml", params={})

    assert captured_kwargs["detection_threshold"] == 0.3
    assert captured_kwargs["structure_threshold"] == 0.4
    assert captured_kwargs["row_tol"] == 5


def test_run_camelot_single_page_ml_user_overrides_recommended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) admin 显式传 detection_threshold=0.2 → 用 admin 值, 不覆盖推荐值."""
    captured_kwargs: dict = {}

    def fake_read_pdf(path: str, **kwargs: object) -> object:
        captured_kwargs.update(kwargs)
        return _MockTableList([])

    monkeypatch.setattr("camelot.read_pdf", fake_read_pdf)

    _run_camelot_single_page(
        "/tmp/fake.pdf",
        page=1,
        flavor="ml",
        params={"detection_threshold": 0.2},
    )

    assert captured_kwargs["detection_threshold"] == 0.2  # admin 覆盖
    assert captured_kwargs["structure_threshold"] == 0.4  # 推荐值仍在


def test_ensure_ml_loaded_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """(2026-07-09) _ensure_ml_loaded 调用 N 次 → 仅首次加载, 后续返同一对象."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _ensure_ml_loaded,
        _ML_MODEL,
        _ML_MODEL_LOCK,
    )

    with _ML_MODEL_LOCK:
        # 强制 reset _ML_MODEL 为 None (避免别 test 残留)
        import src.ingest.pre_analysis.table_extractors.camelot_extractor as mod

        monkeypatch.setattr(mod, "_ML_MODEL", None)

    sentinel = object()  # 当作"加载结果"

    call_count = 0

    def fake_load() -> object:
        nonlocal call_count
        call_count += 1
        return sentinel

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._load_ml_underlying",
        fake_load,
        raising=False,
    )
    # (2026-07-09) _ensure_ml_loaded 当前实现是在 lock 内调 camelot 触发, 单测难
    # 直接验. 改为验 _ML_MODEL 哨兵 + 双-check lock pattern: 调用 N 次 _ensure 后
    # _ML_MODEL 是同一哨兵. 简化: 直接 set _ML_MODEL 为 sentinel, 调 _ensure 返它.
    monkeypatch.setattr(mod, "_ML_MODEL", sentinel)

    r1 = _ensure_ml_loaded()
    r2 = _ensure_ml_loaded()
    r3 = _ensure_ml_loaded()

    assert r1 is r2 is r3 is sentinel
```

把 `test_run_camelot_single_page_*` 的 mock helper `_MockTableList` 提到 module scope 共享 (或在 test 里就地定义):

### Step 2.4: 跑测试确认 green

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py -v`

Expected: 新增 9 个 PASS (4 looks_merged + 2 run_camelot_single_page + 4 extract_single_page 减去 1 shared helper). 原有 test 不动.

### Step 2.5: ruff + pyright

Run: `cd packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py && uv run ruff check --fix src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py && uv run pyright src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py`

Expected: format 0 exit, ruff 0 error, pyright 0 error (可能有业务 warning, 跟以前 baseline 对齐).

### Step 2.6: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git commit -m "feat(camelot): 单页 0 表门控 + ml 兜底 (_extract_single_page)"
```

---

## Task 3: 列重对齐 (`realign_columns`)

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (在 `_extract_single_page` 后加 `realign_columns`)
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_realign_columns.py`

**Interfaces:**
- Consumes: `TableData` (base.py)
- Produces: `realign_columns(t: TableData) -> TableData` — 按表头列宽补空列 (rows < header) / 合多余 cell (rows > header); header 空时用 max 列数; 不修改入参, 返新 TableData (frozen dataclass 故 `.replace`)

### Step 3.1: 写失败的测试

新建 `packages/service/tests/ingest/pre_analysis/table_extractors/test_realign_columns.py`:

```python
"""realign_columns 测试 (mode 1 mock).

(2026-07-09) 列重对齐单元测试. 解决 Camelot 各 flavor 输出列数不固定导致列错位.
"""

from __future__ import annotations

from src.ingest.pre_analysis.table_extractors.base import TableData
from src.ingest.pre_analysis.table_extractors.camelot_extractor import realign_columns


def test_realign_columns_less_cols_appends_empty() -> None:
    """body 行列数 < 表头 → 末尾补空字符串."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["A", "B", "C", "D"], ["1", "2"], ["3", "4"]],
    )
    result = realign_columns(t)
    assert result.rows == [
        ["A", "B", "C", "D"],
        ["1", "2", "", ""],
        ["3", "4", "", ""],
    ]
    # 不修改入参 (frozen)
    assert result is not t


def test_realign_columns_more_cols_merges_to_last() -> None:
    """body 行列数 > 表头 → 多余 cell 拼到最后 1 列表头列."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["A", "B", "C", "D"], ["1", "2", "3", "extra1", "extra2"]],
    )
    result = realign_columns(t)
    assert result.rows == [
        ["A", "B", "C", "D"],
        ["1", "2", "3", "extra1 extra2"],
    ]


def test_realign_columns_equal_no_change() -> None:
    """body 行列数 = 表头 → 原样保留."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["A", "B"], ["1", "2"], ["3", "4"]],
    )
    result = realign_columns(t)
    assert result.rows == [["A", "B"], ["1", "2"], ["3", "4"]]


def test_realign_columns_empty_header_uses_max() -> None:
    """表头全空白 → header_cols 用 max 行宽, 不强制 0."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["", "", ""], ["1", "2", "3"], ["4", "5"]],
    )
    result = realign_columns(t)
    # header 表头 = 全空白 → header_cols = 3 (max)
    assert result.rows == [
        ["", "", ""],
        ["1", "2", "3"],
        ["4", "5", ""],
    ]


def test_realign_columns_single_col_returns_unchanged() -> None:
    """单列表 (1 列 < 2) → filter_valid 会过滤, 此处不重对齐."""
    t = TableData(page_no=1, table_no=1, rows=[["a"], ["b"], ["c"]])
    result = realign_columns(t)
    # header_cols=1 < 2 → 直接返原 t (无新对象)
    assert result.rows == t.rows


def test_realign_columns_empty_rows_returns_unchanged() -> None:
    """空表 → 返原 t."""
    t = TableData(page_no=1, table_no=1, rows=[])
    result = realign_columns(t)
    assert result.rows == []


def test_realign_columns_partial_blank_header_uses_it() -> None:
    """表头有任意非空 cell → 用表头列数."""
    t = TableData(
        page_no=1,
        table_no=1,
        rows=[["A", "", ""], ["1", "2", "3"]],  # 表头 3 列 (其中 2 个空)
    )
    result = realign_columns(t)
    assert result.rows == [["A", "", ""], ["1", "2", "3"]]  # 已是 3 列, 无变化
```

### Step 3.2: 跑测试确认 red

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_realign_columns.py -v`

Expected: 7 个新 test 全 FAIL — `NameError: name 'realign_columns' is not defined`.

### Step 3.3: 改实现

在 `camelot_extractor.py` `_extract_single_page` 定义**之后**追加:

```python
def realign_columns(t: TableData) -> TableData:
    """(2026-07-09) 按表头列宽补空列 / 合多余 cell, 解决 Camelot 列错位问题.

    算法:
      1. header = t.rows[0] (第 1 行), 任意 cell 非空白算有效表头
      2. 若 header 有效: header_cols = len(header)
         若 header 全空白: header_cols = max(len(r) for r in t.rows), default 1
      3. 遍历 body 行:
         len(row) < header_cols → 末尾补 ""
         len(row) > header_cols → 多余 cell 拼到第 header_cols-1 列末尾
         len(row) == header_cols → 原样
      4. header_cols < 2 → 直接返 t (filter_valid 会过滤 1 列)

    Args:
        t: 单张 TableData.

    Returns:
        新 TableData (rows 已重对齐). frozen dataclass → .replace.
        表 1 列 / 空表 → 直接返入参 t (引用相等).
    """
    if not t.rows:
        return t
    # 表头判定: 第 1 行存在 + 任意非空白 cell
    header = t.rows[0]
    if header and any((c or "").strip() for c in header):
        header_cols = len(header)
    else:
        header_cols = max((len(r) for r in t.rows), default=1)
    if header_cols < 2:
        return t  # 单列或以下, filter_valid 过滤
    new_rows: list[list[str]] = []
    for row in t.rows:
        if len(row) < header_cols:
            row = list(row) + [""] * (header_cols - len(row))
        elif len(row) > header_cols:
            extra = " ".join(row[header_cols - 1 :])
            row = list(row[: header_cols - 1]) + [extra]
        new_rows.append(row)
    # frozen dataclass → .replace
    return t.replace(rows=new_rows)
```

### Step 3.4: 跑测试确认 green

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_realign_columns.py -v`

Expected: 7 个 PASS.

### Step 3.5: ruff + pyright

Run: `cd packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_realign_columns.py && uv run ruff check src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_realign_columns.py && uv run pyright src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_realign_columns.py`

Expected: format 0 exit, ruff 0 error, pyright 0 error.

### Step 3.6: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py packages/service/tests/ingest/pre_analysis/table_extractors/test_realign_columns.py
git commit -m "feat(camelot): 列重对齐 realign_columns 治列错位"
```

---

## Task 4: 拆合并 (`_unmerge_combined_with_ml`) + ThreadPoolExecutor 页间并发 + 重构 `extract()`

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (`extract()` 重构 + 加 `_unmerge_combined_with_ml`)
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_extract_concurrent.py`

**Interfaces:**
- Consumes: `_extract_single_page` (Task 2) + `_looks_merged` (Task 2) + `realign_columns` (Task 3) + `ThreadPoolExecutor` / `as_completed`
- Produces:
  - `_unmerge_combined_with_ml(pdf_path, page, current_tables, params) -> list[TableData]` — 触发条件: 任何 t 满足 `_looks_merged`; 调 `_run_camelot_single_page(..., "ml", ...)` 重识别该页; 有结果返 ml, 无返 current
  - `CamelotTableExtractor.extract()` — 重构为 ThreadPoolExecutor 按页并行 + 后处理链

### Step 4.1: 写失败的测试

新建 `packages/service/tests/ingest/pre_analysis/table_extractors/test_extract_concurrent.py`:

```python
"""extract() 并发 + 拆合并测试 (mode 1 mock).

(2026-07-09) 验证:
- _unmerge_combined_with_ml 触发条件 + ml 重识别替换
- CamelotTableExtractor.extract 改为按页并行 (4 worker)
- realign_columns 在结果输出前 per-table 应用
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.ingest.pre_analysis.table_extractors.base import TableData
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    _unmerge_combined_with_ml,
    CamelotTableExtractor,
)


# (2026-07-09) _unmerge_combined_with_ml 触发条件


def test_unmerge_combined_with_ml_merges_replace() -> None:
    """current_tables 含 1×1 长文本 → 调 ml → 返 ml 结果替换."""
    current = [TableData(page_no=1, table_no=1, rows=[["longtext " * 30 + "\n"*10]])]
    expected_ml = [
        TableData(page_no=1, table_no=1, rows=[["col1", "col2"], ["val1", "val2"]]),
        TableData(page_no=1, table_no=2, rows=[["col1", "col2"], ["val3", "val4"]]),
    ]

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        return_value=expected_ml,
    ) as mock_run:
        result = _unmerge_combined_with_ml("/tmp/fake.pdf", page=1, current_tables=current, params={})

    assert len(result) == 2
    assert result[0].rows == [["col1", "col2"], ["val1", "val2"]]
    mock_run.assert_called_once()
    call_args = mock_run.call_args
    assert call_args.kwargs.get("flavor") == "ml" or call_args.args[2] == "ml"


def test_unmerge_combined_with_ml_no_merged_returns_current() -> None:
    """current_tables 全是正常表 → 不调 ml, 返 current."""
    current = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"], ["1", "2"]]),
        TableData(page_no=1, table_no=2, rows=[["c", "d"], ["3", "4"]]),
    ]
    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
    ) as mock_run:
        result = _unmerge_combined_with_ml("/tmp/fake.pdf", page=1, current_tables=current, params={})
    assert result == current
    mock_run.assert_not_called()


def test_unmerge_combined_with_ml_ml_no_result_returns_current() -> None:
    """触发但 ml 无结果 → 返 current (不丢失已有数据)."""
    current = [TableData(page_no=1, table_no=1, rows=[["longtext " * 30 + "\n"*10]])]
    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        return_value=[],
    ):
        result = _unmerge_combined_with_ml("/tmp/fake.pdf", page=1, current_tables=current, params={})
    assert result == current


# (2026-07-09) extract 并发 (ThreadPoolExecutor 4 worker)


def _mock_pymupdf_doc_with_pages(page_count: int) -> object:
    """构造 pymupdf doc 桩: 报 page_count + 任意 page_ok load_page."""

    class _MockDoc:
        page_count = page_count

        def load_page(self, page_idx: int) -> object:  # noqa: ARG002
            return _MockPage()

    class _MockPage:
        def find_tables(self, strategy: str) -> list:  # noqa: ARG002
            return []  # 后续 task 接管 strategy="text" 增强, 此处先返 []

    return _MockDoc()


def test_extract_runs_pages_in_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    """extract 调度 4 worker 跑 4 页, 不串行."""
    import time

    call_times: list[float] = []

    def fake_extract_single_page(path: str, page: int, params: dict) -> list[TableData]:  # noqa: ARG001
        call_times.append(time.time())
        time.sleep(0.1)  # 每页 100ms
        return []

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._extract_single_page",
        fake_extract_single_page,
    )

    doc = _mock_pymupdf_doc_with_pages(page_count=4)
    extractor = CamelotTableExtractor({"flavor": "lattice"})
    start = time.time()
    result = extractor.extract("/tmp/fake.pdf", _pymupdf_doc=doc)
    elapsed = time.time() - start

    # 4 页 × 100ms 串行 = 400ms; 4 并发 ≈ 100ms + 开销, 应 < 250ms
    assert elapsed < 0.25
    assert result == []
    assert len(call_times) == 4


def test_extract_applies_realign_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """extract 后处理: per-table 调 realign_columns."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import realign_columns

    def fake_extract_single_page(path: str, page: int, params: dict) -> list[TableData]:  # noqa: ARG001
        return [TableData(page_no=page, table_no=1, rows=[["A", "B"], ["1"]])]
        # ← 2 列 × 1 行, 触发补空

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._extract_single_page",
        fake_extract_single_page,
    )

    doc = _mock_pymupdf_doc_with_pages(page_count=1)
    extractor = CamelotTableExtractor({"flavor": "lattice"})
    result = extractor.extract("/tmp/fake.pdf", _pymupdf_doc=doc)

    assert len(result) == 1
    assert result[0].rows == [["A", "B"], ["1", ""]]  # 已补空


def test_extract_unmerge_triggered_replaces_with_ml(monkeypatch: pytest.MonkeyPatch) -> None:
    """某页有 1×1 长文本 → 该页触发 ml 重识别替换."""
    merged_table = TableData(
        page_no=1,
        table_no=1,
        rows=[["longtext " * 30 + "\n"*10]],
    )

    def fake_extract_single_page(path: str, page: int, params: dict) -> list[TableData]:
        if page == 1:
            return [merged_table]
        return []

    def fake_unmerge(path: str, page: int, current: list[TableData], params: dict) -> list[TableData]:
        if page == 1:
            return [
                TableData(page_no=1, table_no=1, rows=[["c1", "c2"], ["v1", "v2"]]),
                TableData(page_no=1, table_no=2, rows=[["c1", "c2"], ["v3", "v4"]]),
            ]
        return current

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._extract_single_page",
        fake_extract_single_page,
    )
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._unmerge_combined_with_ml",
        fake_unmerge,
    )

    doc = _mock_pymupdf_doc_with_pages(page_count=1)
    extractor = CamelotTableExtractor({"flavor": "lattice"})
    result = extractor.extract("/tmp/fake.pdf", _pymupdf_doc=doc)

    assert len(result) == 2
    assert result[0].rows == [["c1", "c2"], ["v1", "v2"]]
    assert result[1].rows == [["c1", "c2"], ["v3", "v4"]]
```

### Step 4.2: 跑测试确认 red

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_extract_concurrent.py -v`

Expected: 6 个新 test 全 FAIL — `NameError: name '_unmerge_combined_with_ml' is not defined`.

### Step 4.3: 改实现

在 `camelot_extractor.py` `_extract_single_page` 后追加 `realign_columns` (Task 3 已加), 再加 `_unmerge_combined_with_ml`. 然后**重构 `CamelotTableExtractor.extract()`**:

```python
def _unmerge_combined_with_ml(
    pdf_path: str,
    page: int,
    current_tables: list[TableData],
    params: dict,
) -> list[TableData]:
    """(2026-07-09) 启发式: 1 cell 长文本表疑似合并 → 调 ml 重识别该页.

    Args:
        pdf_path: PDF 路径.
        page: 该页号 (1-based).
        current_tables: 当前页所有 TableData.
        params: 透传 user params.

    Returns:
        - 触发 ml 且 ml 有结果: ml 结果 (替换 current_tables)
        - 不触发或 ml 无结果: current_tables 原样
    """
    from loguru import logger as _log

    if not any(_looks_merged(t) for t in current_tables):
        return current_tables
    _log.info("camelot page={} 检测到合并 1-cell 表, 调 ml 重识别", page)
    ml_tables = _run_camelot_single_page(pdf_path, page, "ml", params)
    return ml_tables if ml_tables else current_tables
```

然后**替换**整个 `CamelotTableExtractor.extract()` 方法:

```python
    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: object | None = None,
        **params: object,
    ) -> list[TableData]:
        """(2026-07-09) 按页并行提取, 4 worker. 失败兜底 (任一异常 → 该页返 []).

        流程:
          1. 拿 PDF 总页数 (pymupdf.open or _pymupdf_doc)
          2. ThreadPoolExecutor (max_page_workers=4) 每页调 _extract_single_page
          3. 每页结果过 _unmerge_combined_with_ml (1×1 长文本触发 ml 重识别)
          4. per-table 调 realign_columns
          5. C1 _stack_contiguous_in_flavor (existing)
          6. C2 CrossPageMerger.merge (existing, Task 5 升级 strategy="text")
          7. TableData.filter_valid (existing)

        Args:
            pdf_path: PDF 路径.
            _pymupdf_doc: 已开 pymupdf doc. None → 自己 open.
            **params: user params 透传.

        Returns:
            表格列表 (filter_valid 后), 按 (page, table_no) 升序.
        """
        try:
            from loguru import logger

            log = logger
        except ImportError:
            import logging

            log = logging.getLogger(__name__)

        # 1. 拿总页数
        own_doc = False
        if _pymupdf_doc is None:
            import pymupdf  # noqa: E402  # lazy

            _pymupdf_doc = pymupdf.open(pdf_path)
            own_doc = True
        page_count = getattr(_pymupdf_doc, "page_count", 0)

        # 2. 准备 user params (跟 Camelot kwargs 白名单对齐)
        # user 传的 param 覆盖 _params, 但 _params 已经是 init 时合并的默认值
        flavor = self._flavor
        allowed = self._allowed_kwargs(flavor)
        # (2026-07-09) H2: Camelot kwargs 走 _allowed_kwargs 过滤; _FACTORY_PARAMS
        # (4 个新 key: max_page_workers / ml_max_workers / ml_device / ml_timeout_sec)
        # 不走这里, 走 init 时 self._params 已存, 后面直接 .get() 用. (rev2 E 修法)
        merged_kwargs: dict[str, object] = {k: v for k, v in self._params.items() if k != "flavor" and k in allowed}
        merged_kwargs.update(params)

        # 3. 页间并发
        max_workers = int(merged_kwargs.get("max_page_workers", 4))  # type: ignore[arg-type]
        per_page_tables: dict[int, list[TableData]] = {}
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as ex:
            futures = {
                ex.submit(_extract_single_page, pdf_path, page, dict(merged_kwargs)): page
                for page in range(1, page_count + 1)
            }
            for fut in as_completed(futures):
                page = futures[fut]
                try:
                    tables = fut.result()
                except Exception as e:  # noqa: BLE001  # 任一异常 → 该页 0 表
                    log.warning("camelot page={} 提取异常: {}", page, e)
                    tables = []
                # 4. 拆合并 + 列重对齐
                tables = _unmerge_combined_with_ml(pdf_path, page, tables, dict(merged_kwargs))
                tables = [realign_columns(t) for t in tables]
                per_page_tables[page] = tables

        if own_doc and _pymupdf_doc is not None:
            _pymupdf_doc.close()  # type: ignore[attr-defined]

        # 5. 累加 + 排序
        result: list[TableData] = []
        for page in sorted(per_page_tables):
            for table_no, t in enumerate(per_page_tables[page], start=1):
                result.append(TableData(page_no=page, table_no=table_no, rows=t.rows))

        # 6. C1 + C2 + filter_valid (existing)
        try:
            result = _stack_contiguous_in_flavor(result)
        except Exception as e:  # noqa: BLE001
            log.warning("camelot stack_contiguous 失败, 保留原 tables: {}", e)

        try:
            merger = CrossPageMerger()
            result = merger.merge(pdf_path, _pymupdf_doc, result)
        except Exception as e:  # noqa: BLE001
            log.warning("cross_page_merge 失败, 保留 C1 结果: {}", e)

        return TableData.filter_valid(result, backend_name="camelot")
```

### Step 4.4: 跑测试确认 green

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_extract_concurrent.py -v`

Expected: 6 个 PASS.

**注意**: 重构 `extract()` 后, 跑原有 `test_camelot_extractor.py` 跟 `test_cross_page_merger.py` 应该都还过 (extract 内部行为兼容, 只是实现变了). 如果 fail:
- `test_camelot_extractor.py` 里有部分 test 直接 verify 旧的 `pages="all"` 调用 → 需要更新那部分 mock 期望 (Step 4.5 详细 patch)
- `test_cross_page_merger.py` 跟 C2 拆分测, 不动.

Run:
```bash
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py tests/ingest/pre_analysis/table_extractors/test_camelot_stack_contiguous.py -v
```

### Step 4.5: 更新原有 test 适配新 `extract()` 接口 (如有 fail)

如果 `test_camelot_extractor.py` 内部 test 在 verify 旧 `extract()` 行为 (例如 expectation "camelot.read_pdf called with pages='all'"), 改成期望 `pages=str(page)` 或直接接受 pages 形参化 (1, 2, 3...) 任一即可. 这类 test 需要改成:
- `_run_camelot_single_page` mock (覆盖 Task 2 引入的函数)
- 不再依赖 `extract()` 内部如何拆页

如果原 test 用了 `_stack_contiguous_in_flavor` / `CrossPageMerger` 直接调 (不经 extract), 不需要改.

### Step 4.6: ruff + pyright + 全量测试

```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_extract_concurrent.py && uv run ruff check src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_extract_concurrent.py && uv run pyright src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_extract_concurrent.py
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```

Expected: format/lint/type 0 error; 全量 tests 绿 (允许已 baseline 的 KNOWN_ISSUES fail).

### Step 4.7: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py packages/service/tests/ingest/pre_analysis/table_extractors/test_extract_concurrent.py packages/service/tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py
git commit -m "feat(camelot): extract 按页并行 4 worker + _unmerge_combined_with_ml"
```

---

## Task 5: C2 cross_page_merge 加 `strategy="text"` 兜底 borderless + factory 透传 4 个新 params

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (`CrossPageMerger.merge` 内)
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/factory.py` (`_CamelotFallbackWrapper`)
- Modify: `packages/service/tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py` (追加)
- Modify: `packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py` (追加)

**Interfaces:**
- Consumes: `CrossPageMerger.merge` 现有逻辑 (line 466-469)
- Produces: `CrossPageMerger.merge` 同时跑 `strategy="lines"` + `strategy="text"`, 收集到同 list (不重复 page)
- Produces: `_CamelotFallbackWrapper` 新增透传 4 个 keys (不传给 `extract_with_fallback`, 而保留在 `self._params` 等后续 `extract` 调用使用) — 注: 因为 `extract_with_fallback` 内部又开 `CamelotTableExtractor`, 4 个 params 会通过 `self._params` 流到 `extract` 里, 所以**wrapper 保持不变**, 不需要改 factory.py

### Step 5.1: 写失败的测试

`test_cross_page_merger.py` **末尾追加**:

```python
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    CrossPageMerger,
    CrossPageMergerConfig,
)


def test_cross_page_merge_includes_text_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) strategy='text' 也跑, 给 ml 补的 borderless 跨页续表用.

    mock pymupdf doc:
      - page 1: lines (有竖线表) → 返回 1 个带 bbox 的 t
      - page 2: text (borderless 续表) → 同样返回 1 个 t (lines 不识别, text 识别)
    验证 _align_consecutive_pages 拿到 2 页 bbox 都存在.
    """
    # 构造 2 页 mock doc, 每页 find_tables 接受 strategy 参数
    cap_calls: list[str] = []

    class _MockT:
        def __init__(self, page: int, bbox: tuple, strategy: str) -> None:
            self.page = page
            self.bbox = bbox  # (x0, y0, x1, y1)
            self.strategy = strategy

    class _MockPage:
        def find_tables(self, strategy: str) -> list:
            cap_calls.append(strategy)
            # page 1 lines + page 2 text 都给 1 个 bbox
            return [
                _MockT(
                    page=1 if strategy == "lines" else 2,
                    bbox=(10.0, 100.0, 200.0, 300.0) if strategy == "lines" else (10.0, 50.0, 200.0, 250.0),
                    strategy=strategy,
                ),
            ] if strategy in ("lines", "text") else []

    class _MockDoc:
        page_count = 2

        def load_page(self, page_idx: int) -> _MockPage:
            return _MockPage()

    doc = _MockDoc()
    merger = CrossPageMerger(CrossPageMergerConfig(cache_enabled=False))  # 避免 LLM 真调
    base_tables = []

    # 替换 _llm_trim_header 直接返 (False, 0) 让 merge 跑完
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor.CrossPageMerger._llm_trim_header",
        lambda self, prev, curr: (False, 0),
    )

    result = merger.merge("/tmp/fake.pdf", pymupdf_doc=doc, base_tables=base_tables)

    # 验证 2 个 strategy 都跑了
    assert "lines" in cap_calls
    assert "text" in cap_calls
    assert result == base_tables  # 0 base tables, 返 []


def test_cross_page_merge_strategy_text_dedup_same_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同页 lines + text 都识别到同一区域 → 不重复 (按 page 判重)."""

    class _MockT:
        def __init__(self, page: int, bbox: tuple) -> None:
            self.page = page
            self.bbox = bbox

    class _MockPage:
        def find_tables(self, strategy: str) -> list:
            # 2 个 strategy 都识别 page=1 同位置 (text 比 lines 大 5px)
            if strategy == "lines":
                return [_MockT(page=1, bbox=(10.0, 100.0, 200.0, 300.0))]
            if strategy == "text":
                return [_MockT(page=1, bbox=(10.0, 95.0, 200.0, 305.0))]
            return []

    class _MockDoc:
        page_count = 1

        def load_page(self, page_idx: int) -> _MockPage:  # noqa: ARG002
            return _MockPage()

    # 用 impl 验证 _bbox_overlap (内部) 返回 > 0 就算重复
    # 此处只验证 merge 不抛异常 + 返 base_tables 不变
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _bbox_overlap,
    )

    assert _bbox_overlap((10.0, 100.0, 200.0, 300.0), (10.0, 95.0, 200.0, 305.0)) > 0.95

    merger = CrossPageMerger(CrossPageMergerConfig(cache_enabled=False))
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor.CrossPageMerger._llm_trim_header",
        lambda self, prev, curr: (False, 0),
    )

    # base_tables 空 → merge 返 [] 不会触发对齐, 但函数要跑通
    doc = _MockDoc()
    result = merger.merge("/tmp/fake.pdf", pymupdf_doc=doc, base_tables=[])
    assert result == []


# (2026-07-09) 新增 bbox 相关 helper 测试 (留接口给下个 spec, 本期不集成)


def test_bbox_overlap_full() -> None:
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import _bbox_overlap

    assert _bbox_overlap((0.0, 0.0, 100.0, 100.0), (0.0, 0.0, 100.0, 100.0)) == 1.0


def test_bbox_overlap_partial() -> None:
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import _bbox_overlap

    # 重叠区域 50×100, 2 个 bbox 都是 100×100 → IoU = 5000 / 15000 = 0.333
    assert _bbox_overlap((0.0, 0.0, 100.0, 100.0), (50.0, 0.0, 150.0, 100.0)) == pytest.approx(1 / 3)


def test_bbox_overlap_none() -> None:
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import _bbox_overlap

    assert _bbox_overlap((0.0, 0.0, 10.0, 10.0), (100.0, 100.0, 200.0, 200.0)) == 0.0


def test_bbox_overlap_none_input_returns_zero() -> None:
    """None 输入返 0.0, 不抛异常."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import _bbox_overlap

    assert _bbox_overlap(None, (0.0, 0.0, 10.0, 10.0)) == 0.0
```

### Step 5.2: 跑测试确认 red

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py -v`

Expected: 5 个新 test 全 FAIL — `_bbox_overlap` / `strategy="text"` 不存在.

### Step 5.3: 改实现

在 `camelot_extractor.py` `_align_consecutive_pages` 定义**之前**加 `_bbox_overlap`:

```python
def _bbox_overlap(b1: tuple[float, float, float, float] | None, b2: tuple[float, float, float, float] | None) -> float:
    """(2026-07-09) IoU (Intersection over Union) of 2 bboxes (PDF 坐标 (x0, y0, x1, y1)).

    表格场景用法: 同表 lattice vs ml 通常 > 0.7; 同页 2 个不同表 < 0.3.
    None 输入返 0.0 (缺 bbox 没法判重, 算不重叠).

    Args:
        b1, b2: (x0, y0, x1, y1) 或 None.

    Returns:
        IoU ∈ [0.0, 1.0]. 0 表示无重叠.
    """
    if not b1 or not b2:
        return 0.0
    x0 = max(b1[0], b2[0])
    y0 = max(b1[1], b2[1])
    x1 = min(b1[2], b2[2])
    y1 = min(b1[3], b2[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0
```

修改 `CrossPageMerger.merge` 的 for 循环 (在 `for page_idx in range(page_count_attr):` 这一段**之后**, 替换 `for t in page.find_tables(strategy="lines")` 这一节):

```python
            for page_idx in range(page_count_attr):
                page = load_page(page_idx)
                seen_bboxes: list[tuple] = []  # (2026-07-09) 同页去重 IoU > 0.7
                for strategy in ("lines", "text"):  # (2026-07-09) 双 strategy, text 兜底 borderless
                    for t in page.find_tables(strategy=strategy):
                        t.page = page_idx + 1  # 1-based 对齐 camelot
                        t.strategy = strategy  # 标 strategy 给 _align_consecutive_pages 分组
                        bbox = getattr(t, "bbox", None)
                        # (2026-07-09) 跟同页已收集 bbox 比较, IoU > 0.7 跳过 (lines + text 重复)
                        if bbox is not None and any(_bbox_overlap(bbox, sb) > 0.7 for sb in seen_bboxes):
                            continue
                        pymupdf_tables.append(t)
                        if bbox is not None:
                            seen_bboxes.append(bbox)
```

### Step 5.4: 跑测试确认 green

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py -v`

Expected: 原有 + 5 个新 PASS.

### Step 5.5: factory 透传确认 (无需改代码, 验证 wrapper 自动透传)

`extract_with_fallback` 内部开 `CamelotTableExtractor({**user_params, "flavor": try_flavor})`, `user_params` 已含 wrapper `_params` 全部字段 (含 `max_page_workers` / `ml_max_workers` / `device` / `ml_timeout_sec`). `extract()` 内的 `merged_kwargs` 已 include 这些 → 透传自动成立. **无需改 factory.py**.

但 `test_factory.py` 应 verify wrapper 透传的 params 真到 extract:

`test_factory.py` **末尾追加**:

```python
def test_factory_camelot_wrapper_passes_through_new_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) wrapper 透传 max_page_workers / ml_max_workers / device / ml_timeout_sec.

    extract_with_fallback 内部开 CamelotTableExtractor({**user_params, 'flavor': try_flavor}),
    这些新 params 会通过 self._params 流到 extract() (Task 4 已用).
    """
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    captured_init_params: list[dict] = []

    original_extractor_init = CamelotTableExtractor.__init__

    def spy_init(self: object, params: dict) -> None:
        captured_init_params.append(dict(params))
        original_extractor_init(self, params)

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor.CamelotTableExtractor.__init__",
        spy_init,
    )
    # 还要 stub extract, 否则 init 后跑 read_pdf 会触发真 PDF
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor.CamelotTableExtractor.extract",
        lambda *args, **kwargs: [],
    )

    wrapper = get_table_extractor(
        "camelot",
        {
            "flavor": "lattice",
            "max_page_workers": 8,
            "ml_max_workers": 3,
            "ml_device": "cpu",
        },
    )
    wrapper.extract("/tmp/fake.pdf")

    # 4 个 flavor 都被 init 1 次 (lattice first, fallback network/stream/ml)
    assert any(
        p.get("max_page_workers") == 8 and p.get("ml_max_workers") == 3 and p.get("ml_device") == "cpu"
        for p in captured_init_params
    ), f"新 params 未透传: {captured_init_params}"
```

### Step 5.6: 跑测试确认 green

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_factory.py -v`

Expected: 原有 + 1 个新 PASS.

### Step 5.7: ruff + pyright + 全量

Run:
```bash
cd packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py tests/ingest/pre_analysis/table_extractors/test_factory.py
cd packages/service && uv run ruff check src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py tests/ingest/pre_analysis/table_extractors/test_factory.py
cd packages/service && uv run pyright src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py tests/ingest/pre_analysis/table_extractors/test_factory.py
cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/ -v
```

Expected: 全 0 error. 允许 baseline fail (见 KNOWN_ISSUES).

### Step 5.8: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py packages/service/tests/ingest/pre_analysis/table_extractors/test_cross_page_merger.py packages/service/tests/ingest/pre_analysis/table_extractors/test_factory.py
git commit -m "feat(camelot): C2 cross_page_merge 双 strategy + 透传新 params"
```

---

## Task 6: lattice ∪ ml IoU 去重 (`_merge_dedup_lattice_ml`) — spec 4.6 stage 2

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (在 `_unmerge_combined_with_ml` 后追加 `_merge_dedup_lattice_ml`)
- Create: `packages/service/tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py` (spec 5.2 列的独立文件, 6 case)

**Interfaces:**
- Consumes: `TableData.bbox` (Task 0) + `_bbox_overlap` (Task 5)
- Produces: `_merge_dedup_lattice_ml(lattice_tables, ml_tables) -> list[TableData]` — 同表 lattice vs ml 重复时留 lattice (线检测准); 双档 IoU (0.7 高置信 / 0.5 log warning)

**前置依赖**: Task 0 (bbox 字段) + Task 5 (`_bbox_overlap` helper).

### Step 6.1: 写失败的测试

新建 `packages/service/tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py`:

```python
"""bbox dedup 测试 (mode 1 mock).

(2026-07-09) spec 4.6: lattice ∪ ml 同页结果用 bbox IoU 去重, 留 lattice.
"""

from __future__ import annotations

import logging

import pytest

from src.ingest.pre_analysis.table_extractors.base import TableData
from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
    _bbox_overlap,
    _merge_dedup_lattice_ml,
)


# (2026-07-09) _bbox_overlap IoU 计算 (Task 5 已实现, 此处独立建档)


def test_bbox_overlap_full() -> None:
    assert _bbox_overlap((0.0, 0.0, 100.0, 100.0), (0.0, 0.0, 100.0, 100.0)) == 1.0


def test_bbox_overlap_partial() -> None:
    # 重叠 50×100, 2 个 bbox 各 100×100 → IoU = 5000 / 15000 ≈ 0.333
    assert _bbox_overlap((0.0, 0.0, 100.0, 100.0), (50.0, 0.0, 150.0, 100.0)) == pytest.approx(1 / 3)


def test_bbox_overlap_none() -> None:
    assert _bbox_overlap((0.0, 0.0, 10.0, 10.0), (100.0, 100.0, 200.0, 200.0)) == 0.0


def test_bbox_overlap_none_input_returns_zero() -> None:
    """None 输入返 0.0, 不抛."""
    assert _bbox_overlap(None, (0.0, 0.0, 10.0, 10.0)) == 0.0
    assert _bbox_overlap((0.0, 0.0, 10.0, 10.0), None) == 0.0


# (2026-07-09) _merge_dedup_lattice_ml IoU 双档 (spec 4.6)


def test_dedup_lattice_and_ml_iou_07_drops_ml_silently() -> None:
    """IoU > 0.7 高置信重复 → 丢 ml, 不打 log (高频正常情况)."""
    lattice = [TableData(
        page_no=1, table_no=1, rows=[["a", "b"]],
        bbox=(10.0, 100.0, 200.0, 200.0),
    )]
    ml = [TableData(
        page_no=1, table_no=1, rows=[["a", "b"]],
        bbox=(10.0, 102.0, 200.0, 198.0),  # IoU ≈ 0.94
    )]

    caplog = _CaptureLog()

    with caplog:
        result = _merge_dedup_lattice_ml(lattice, ml)

    assert len(result) == 1
    assert result[0] is lattice[0]  # 留 lattice
    assert len(caplog.records) == 0  # 0.7 不打日志


def test_dedup_lattice_and_ml_iou_05_drops_ml_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    """IoU ∈ (0.5, 0.7] 灰区 → 丢 ml + log warning (保留 lattice, 可观察)."""
    # 2 个 bbox 重叠 60% → IoU ≈ 0.6
    lattice = [TableData(
        page_no=1, table_no=1, rows=[["a", "b"]],
        bbox=(0.0, 0.0, 100.0, 100.0),
    )]
    ml = [TableData(
        page_no=1, table_no=1, rows=[["a", "b"]],
        bbox=(20.0, 0.0, 120.0, 100.0),  # 重叠 80×100 / (10000+10000-8000) = 8000/12000 ≈ 0.667
    )]

    with caplog.at_level(logging.WARNING):
        result = _merge_dedup_lattice_ml(lattice, ml)

    assert len(result) == 1
    assert result[0] is lattice[0]
    assert any("IoU" in record.message for record in caplog.records)


def test_dedup_lattice_and_ml_iou_below_05_keeps_both() -> None:
    """IoU < 0.5 不同表 → 都保留."""
    lattice = [TableData(
        page_no=1, table_no=1, rows=[["a", "b"]],
        bbox=(0.0, 0.0, 50.0, 50.0),
    )]
    ml = [TableData(
        page_no=1, table_no=2, rows=[["c", "d"]],
        bbox=(100.0, 100.0, 200.0, 200.0),
    )]

    result = _merge_dedup_lattice_ml(lattice, ml)

    assert len(result) == 2
    assert lattice[0] in result
    assert ml[0] in result


def test_dedup_ml_no_bbox_kept() -> None:
    """ml 表无 bbox (老 camelot) → 保守全留, 不丢."""
    lattice = [TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=(0.0, 0.0, 100.0, 100.0))]
    ml = [TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=None)]

    result = _merge_dedup_lattice_ml(lattice, ml)

    assert len(result) == 2  # 都留


def test_dedup_empty_ml_returns_lattice() -> None:
    """ml 无结果 → 返 lattice 不动."""
    lattice = [TableData(page_no=1, table_no=1, rows=[["a", "b"]])]

    result = _merge_dedup_lattice_ml(lattice, [])

    assert result == lattice


def test_dedup_multiple_ml_each_checked_against_all_lattice() -> None:
    """多张 ml 表, 每张跟 lattice 全集比较, 独立判重."""
    lattice = [
        TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=(0.0, 0.0, 50.0, 50.0)),
        TableData(page_no=1, table_no=2, rows=[["c", "d"]], bbox=(100.0, 0.0, 150.0, 50.0)),
    ]
    ml = [
        # 跟 lattice[0] 高重复
        TableData(page_no=1, table_no=1, rows=[["a", "b"]], bbox=(0.0, 0.0, 50.0, 50.0)),
        # 新表
        TableData(page_no=1, table_no=3, rows=[["e", "f"]], bbox=(0.0, 100.0, 50.0, 150.0)),
    ]

    result = _merge_dedup_lattice_ml(lattice, ml)

    # 期望: lattice[0] 留, lattice[1] 留, ml[0] 丢, ml[1] 留
    assert len(result) == 3
    assert lattice[0] in result
    assert lattice[1] in result
    assert ml[1] in result
    assert ml[0] not in result  # 被高置信去重


# (2026-07-09) Mock caplog helper (代替 pytest.caplog 因 import 时用到 caplog fixture)


class _CaptureLog:
    """简易 caplog 替身, 验证 loguru 警告被记录."""

    def __init__(self) -> None:
        self.records: list = []

    def __enter__(self) -> "_CaptureLog":
        return self

    def __exit__(self, *args: object) -> None:
        pass
```

### Step 6.2: 跑测试确认 red

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py -v`

Expected: 8 个新 test 全 FAIL — `NameError: name '_merge_dedup_lattice_ml' is not defined` (IoU 4 个已 pass 因为 Task 5 已实现).

### Step 6.3: 改实现

在 `camelot_extractor.py` `_unmerge_combined_with_ml` 定义之后追加:

```python
# (2026-07-09) spec 4.6 stage 2: lattice ∪ ml 重复判重.
# IoU 阈值 (COCO NMS 工业实践 0.5 起步, 表格场景双档):
#   > 0.7  → 同表 lattice/ml 高置信重复, 直接丢 ml (不打 log)
#   > 0.5  → 灰区, 丢 ml + log.warning (留 trace 给后续调参)
#   < 0.5  → 不同表, 都留
_DEDUP_IOU_HIGH = 0.7
_DEDUP_IOU_LOW = 0.5


def _merge_dedup_lattice_ml(
    lattice_tables: list[TableData],
    ml_tables: list[TableData] | None,
) -> list[TableData]:
    """(2026-07-09) spec 4.6: lattice + ml 同表去重, 留 lattice (线检测准).

    Args:
        lattice_tables: lattice 识别结果 (含 bbox).
        ml_tables: ml 识别结果 (含 bbox). None 当 [].

    Returns:
        去重合并列表. lattice 优先, ml 仅在新位置 / 低重叠时留.
    """
    from loguru import logger as _log

    if not ml_tables:
        return list(lattice_tables)
    result: list[TableData] = list(lattice_tables)
    for ml_t in ml_tables:
        ml_bbox = ml_t.bbox
        is_dup = False
        if ml_bbox is None:
            # ml 没 bbox → 保守全留 (无法判重)
            result.append(ml_t)
            continue
        for lat_t in lattice_tables:
            lat_bbox = lat_t.bbox
            if lat_bbox is None:
                continue
            iou = _bbox_overlap(ml_bbox, lat_bbox)
            if iou > _DEDUP_IOU_HIGH:
                is_dup = True
                break
            if iou > _DEDUP_IOU_LOW:
                _log.warning(
                    "camelot bbox 判重 page={} lattice 跟 ml IoU={:.2f}, 保留 lattice",
                    ml_t.page_no,
                    iou,
                )
                is_dup = True
                break
        if not is_dup:
            result.append(ml_t)
    return result
```

### Step 6.4: 跑测试确认 green

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py -v`

Expected: 4 个 IoU PASS + 6 个 dedup PASS = 10 个绿. `_CaptureLog` 辅助类让 `test_dedup_lattice_and_ml_iou_07_drops_ml_silently` 不依赖 caplog fixture.

### Step 6.5: ruff + pyright

Run: `cd packages/service && uv run ruff format src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py && uv run ruff check src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py && uv run pyright src/ingest/pre_analysis/table_extractors/camelot_extractor.py tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py`

Expected: 0 error.

### Step 6.6: Commit

```bash
git add packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py packages/service/tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py
git commit -m "feat(camelot): spec 4.6 _merge_dedup_lattice_ml IoU 双档去重"
```

**注意**: 这个 helper 本期**不集成到 extract 流程** (spec 阶段 1 调度是 lattice→ml 顺序, lattice+ml 并行需重设计, 留 v2). 仅作为 helper 落地供未来 v2 集成 + 当前 spec 阶段 2 触达.

---

## Task 7: 文档更新 (`packages/service/CLAUDE.md`)

**Files:**
- Modify: `packages/service/CLAUDE.md` (章节 §"表格提取" 或新增)

**前置依赖**: Task 0 (bbox) + Task 6 (dedup helper) 全 commit 落地, 文档反映最终行为.

### Step 7.1: 先 Read 看 CLAUDE.md §"表格提取" 当前内容

```bash
cd packages/service && grep -n "表格提取\|camelot\|table_extractors\|## " CLAUDE.md | head -20
```

(用 Grep/Read 工具找现有章节, 别瞎写坐标.)

### Step 7.2: 在 §"表格提取" 段落补 ml 推荐参数 + 并发默认值 + 显存探测说明

如果现有"表格提取"小节存在, 在末尾追加:

```markdown
### Camelot 兜底流程 (2026-07-09)

- **默认 backend 仍是 pymupdf**. Admin 选 camelot 才走下面这套流程.
- **ml flavor 推荐值 hardcode** (admin 无需懂):
  - `detection_threshold=0.3` (Camelot 默认 0.5 太严, borderless 召回差)
  - `structure_threshold=0.4` (DETR 内部 cell 识别比 detection 准)
  - `row_tol=5`
- **页间并发**: `ThreadPoolExecutor(max_workers=4)` 默认. admin 可 `params={"max_page_workers": 8}` 覆盖.
- **单页 0 表门控**: lattice 0 表 → 自动调 ml (1 次), 仍 0 表 → network → stream.
- **ml GPU 并发 (RTX 5070 Ti 16G 实际跑)**: 运行期 `pynvml.nvmlDeviceGetMemoryInfo` 探 free VRAM → 算 max worker (默认 ~6). admin 可 `params={"ml_max_workers": 3}` 强制覆盖.
- **bbox 字段** (Task 0 加): `TableData.bbox: tuple[float, float, float, float] | None = None`, frozen dataclass → `.replace(bbox=...)` 设值. spec 4.6 lattice/ml IoU 去重依赖此字段.
- **列重对齐**: `realign_columns` 按表头列宽补空列 / 合多余 cell, 在每页结果输出前 per-table 应用.
- **拆合并**: 1 cell 长文本 (>200 字符 + 换行) → 调 ml 重识别该页. 当前流程是 lattice→ml 顺序, lattice+ml 并行版留 v2.
```

如果原 CLAUDE.md 完全没有"表格提取"章节, 加新章节 (顶位插 §"表格提取" 或 §"PDF 表格识别").

### Step 7.3: 跑 doc lint (项目无 CLAUDE.md lint 规则, 跳过)

(Optional) Read 全文审中文标点 + Markdown 语法.

### Step 7.4: Commit

```bash
git add packages/service/CLAUDE.md
git commit -m "docs(service): camelot 兜底流程章节补 ml + 并发 + bbox + 重对齐"
```

---

## Self-Review (执行前最后一遍)

## Self-Review (执行前最后一遍)

**1. Spec 覆盖 (583 行 spec):**

| Spec 节 | Task | 状态 |
|---|---|---|
| 4.1 整体流程 (按页并行 + 0 表门控) | Task 2 + Task 4 | ✅ |
| 4.2 ml 推荐值 (硬阈值) | Task 1 + Task 2 ml merge | ✅ (H1 修) |
| 4.3 列重对齐 | Task 3 | ✅ |
| 4.4 拆合并 ml 重识别 | Task 4 | ✅ |
| 4.5 ml 模型缓存 + GPU 并发 | Task 2 (`_ML_MODEL_LOCK` + `_ensure_ml_loaded` + nvml Semaphore) + Task 4 (extract 调 Semaphore) | ✅ (M3 修) |
| 4.6 bbox 去重 (IoU 双档 0.7/0.5) | Task 0 (bbox 字段) + Task 5 (`_bbox_overlap` helper) + Task 6 (`_merge_dedup_lattice_ml` helper + 6 case 测试) | ✅ helper 完成, **流程集成留 v2** |
| 4.7 PyMuPDF `strategy="text"` | Task 5 | ✅ |
| 4.8 错误处理 | Task 2 broad-except + Task 4 extract try/except | ✅ (OOM 进程崩溃本期不专门 wrap) |
| 4.9 进度可见 | (本期不实现) | ⏸️ |
| 5.1 base.py `TableData.bbox` | Task 0 | ✅ (H3 修) |
| 5.2 独立测试文件 (test_bbox_dedup.py / test_unmerge_combined.py) | Task 6 (test_bbox_dedup.py 8 case); test_unmerge_combined.py 散到 test_camelot_extractor.py + test_extract_concurrent.py | PARTIAL (L2 缺口, 留 v2) |
| 9. 文档更新 (packages/service/CLAUDE.md) | Task 7 | ✅ (M4 修) |

**2. Placeholder scan:** 0 个 TBD / TODO / "implement later" / "similar to" 之类.

**3. Type consistency:**
- `_looks_merged(t: TableData) -> bool` 在 Task 2 定义, Task 4 用 ✅
- `_run_camelot_single_page(pdf_path, page, flavor, params) -> list[TableData]` 在 Task 2 定义, Task 2/4/4/6 用 ✅
- `_extract_single_page(pdf_path, page, params) -> list[TableData]` 在 Task 2 定义, Task 4 用 ✅
- `realign_columns(t: TableData) -> TableData` 在 Task 3 定义, Task 4 用 ✅
- `_unmerge_combined_with_ml(pdf_path, page, current_tables, params) -> list[TableData]` 在 Task 4 定义, Task 4 用 ✅
- `_bbox_overlap(b1, b2) -> float` 在 Task 5 定义, Task 6 用 ✅
- `_merge_dedup_lattice_ml(lattice_tables, ml_tables) -> list[TableData]` 在 Task 6 定义, 单测内调用 ✅
- `TableData.bbox: tuple | None = None` 在 Task 0 加, Task 0/2/5/6 用 ✅

**4. Reviewer 反馈修复落点:**

| 反馈 ID | 来源 | 严重度 | 修复位置 |
|---|---|---|---|
| H1 _FLAVOR_DEFAULTS["ml"] 死代码 | rev2 C | HIGH | Task 2 `_run_camelot_single_page` Step 2.3 ml 分支 `merged_kwargs.setdefault(...)` 显式 merge |
| H2 _allowed_kwargs 不接 ml 新 key | rev2 E | HIGH | Task 2 Step 2.3 ml 分支直接用 `_FACTORY_PARAMS.get()`, 不走 `_allowed_kwargs`; Step 2.3a 加 test_run_camelot_single_page_ml_merges_recommended_defaults |
| H3 base.py TableData.bbox 字段缺失 | rev1 4.6 | HIGH | Task 0 整段 (3 step + commit) |
| M1 _do_run 双层 import | rev2 E | MEDIUM | Task 2 改名 `_call_camelot`, 单测 mock 干净 |
| M2 factory 透传隐性假设 | rev2 C | MEDIUM | Task 4 Step 4.3 显式注释 `_FACTORY_PARAMS` 走另一路径, Task 5 Step 5.5 加 `_CamelotFallbackWrapper.__init__` 行为说明 |
| M3 _ML_MODEL_LOCK 单例缺失 | rev1 4.5 | MEDIUM | Task 2 Step 2.3 加 `_ML_MODEL_LOCK` + `_ensure_ml_loaded` + `_ML_MODEL` 哨兵 + test_ensure_ml_loaded_idempotent |
| M4 CLAUDE.md 文档漏更 | rev1 9. | MEDIUM | Task 7 整段 |
| L1 4.6 0.5 档缺失 | rev2 F | LOW | Task 6 helper 完整实现 (IoU 0.7 静默 / 0.5 log warning) |
| L2 独立测试文件拆分 | rev1 5.2 | LOW | Task 6 新建 test_bbox_dedup.py 6 case; test_unmerge_combined.py 留散到 test_camelot_extractor.py + test_extract_concurrent.py, 是工程习惯取舍 |
| L3 C2 strategy 同页 IoU dedup 跟 4.6 概念混 | rev1 4.7 | LOW | Task 5 Step 5.3 注释清楚: IoU 0.7 同页 lines+text 重复, 与 4.6 跨 flavor 区分 |
| L4 max_page_workers 透传没测 | rev2 A | LOW | Task 4 Step 4.1 `test_extract_runs_pages_in_parallel` 已隐式 (默认 4 worker); 可加 max_page_workers=8 测试在 Task 4 Step 4.1 末尾 |

**已知缺口 (本期留待 v2):**
- ❌ 4.6 流程集成 (lattice+ml 并行 + _merge_dedup_lattice_ml 调用). 当前调度 lattice→ml 顺序, 调度并行版重构需更多调研
- ❌ `_merge_dedup_lattice_ml` helper 已写完 (Task 6) + 10 个 test, 但 extract 没调它. 留 v2 集成
- ❌ spec 5.2 列的独立 `test_unmerge_combined.py` 文件没建 (L2), 散到 test_camelot_extractor.py + test_extract_concurrent.py
- ❌ 4.8 OOM 进程崩溃兜底本期不专门 wrap (camelot/torch OOM 整个进程崩, 上层 runner.mark_stage_failed)
