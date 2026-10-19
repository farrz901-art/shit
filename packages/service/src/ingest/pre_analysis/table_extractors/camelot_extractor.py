"""CamelotTableExtractor (2026-07-06).

Camelot 2.0 适配器. Lazy import: 包缺失抛 BackendNotInstalledError.
flavor='ml' 额外检查 [ml] extra 装了.
(2026-07-07) 按 flavor 路由 kwargs — 跟 Camelot 实际 flavor_to_kwargs 对齐:
  - lattice → line_tol / joint_tol / line_scale / process_background ...
  - stream  → edge_tol / row_tol / column_tol
  - network → 同 stream
  - hybrid  → stream ∪ lattice
  - ml      → device / structure_model / detection_model ...
历史 bug: 之前给 lattice/network/hybrid/ml 透传 row_tol → Camelot 内部
validate_input raise "row_tol cannot be used with flavor='lattice'".
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .base import BackendNotInstalledError, TableData, TableExtractor

_BASE_INSTALL_HINT = "uv add camelot-py"
_ML_INSTALL_HINT = "uv add 'camelot-py[ml]'"

# (2026-07-07) 按 flavor 拆参数:
#   LATTICE_KWARGS — 走 _Lattice parser, 用线检测 (line_tol / joint_tol / line_scale ...)
#   STREAM_KWARGS  — 走 _Stream parser, 用空白间距 (edge_tol / row_tol / column_tol)
#   ML_KWARGS      — 走 ml backend, 用 Table Transformer
# hybrid = LATTICE ∪ STREAM, network = STREAM.
_LATTICE_KWARGS = frozenset(
    {
        "line_tol",
        "joint_tol",
        "line_scale",
        "process_background",
        "copy_text",
        "shift_text",
        "threshold_blocksize",
        "threshold_constant",
        "iterations",
        "erode_iterations",
        "resolution",
        "use_fallback",
        "engine",
    }
)
_STREAM_KWARGS = frozenset({"edge_tol", "row_tol", "column_tol", "columns"})
_ML_KWARGS = frozenset(
    {
        "device",
        "structure_model",
        "detection_model",
        "detection_threshold",
        "structure_threshold",
        "crop_padding",
        "ocr",
        # (2026-07-07) 这 4 个 lattice 也有, 但 ml 独立列在 flavor_to_kwargs['ml'],
        # 不在 lattice_kwargs, 所以 ml 需要自己再列一遍
        "copy_text",
        "resolution",
        "shift_text",
        "use_fallback",
    }
)

# (2026-07-07) camelot 5 种 flavor 都接受的通用 kwargs (从 flavor_to_kwargs 看).
# 这些不暴露给前端 UI (table_areas / table_regions / margins 等是高级),
# 但白名单要接住, 防止前端误传被 wrapper 静默丢.
_COMMON_KWARGS = frozenset(
    {
        "backend",
        "flag_size",
        "margins",
        "replace_text",
        "split_text",
        "strip_text",
        "table_areas",
        "table_regions",
    }
)

# (2026-07-08) 调 _FLAVOR_DEFAULTS 到 Camelot 2.0 官方推荐 + borderless 场景加 process_background.
#   历史问题:
#     - lattice line_scale=40 → 漏短表格线 (官方默认 15, 调到 40 容易把短线判为"短横线"丢)
#     - network/hybrid 强制 edge_tol=50 → 关 Camelot 自动推断, borderless 表反而更差
#     - stream row_tol=2 → 少行表检测不到 (官方建议 5)
#   新增 process_background=True → 处理"线是背景图形"的 PDF (常见于设计文档)
_FLAVOR_DEFAULTS: dict[str, dict[str, int | float | bool]] = {
    "lattice": {"line_scale": 15, "line_tol": 2, "process_background": True, "use_fallback": True},
    "stream": {"row_tol": 5},
    "network": {},
    "hybrid": {},
    # (2026-07-09) ml 推荐值 (硬阈值, admin 无需懂):
    #   detection_threshold=0.3 → borderless 表提召回 (默认 0.5 太严)
    #   structure_threshold=0.4 → 略高于 detection, DETR 内部 cell 识别比表检测准
    #   row_tol=5 → 跟 stream 一致, 1-2 行小表也能识别
    "ml": {
        "detection_threshold": 0.3,
        "structure_threshold": 0.4,
        "row_tol": 5,
    },
}

# (2026-07-09) 工厂参数白名单: 4 个新参数不走 _allowed_kwargs (那是 Camelot kwargs 白名单),
# 走 _run_camelot_single_page 直接消费, _extract_single_page / extract() 也直接 params.pop() 用.
# 命名跟 spec 4.3 一致: max_page_workers (页级并发) / ml_max_workers (ml 内部并发) /
# ml_device (torch device) / ml_timeout_sec (单页超时).
_FACTORY_PARAMS: frozenset[str] = frozenset(
    {
        "max_page_workers",
        "ml_max_workers",
        "ml_device",
        "ml_timeout_sec",
    }
)

# (2026-07-08) Fallback 链: lattice 找不到表 → 试 network → 试 stream → 试 ml.
#   顺序按"算法多样性"排: lattice 是线检测, network/stream 是文本对齐, ml 是 ML 路径.
#   任意一档找到表就停. ml 缺失 ([ml] extra 没装) 静默跳过.
#   admin 可通过 params={"fallback_chain": false} 关掉, 只用首选 flavor.
_FALLBACK_CHAIN: tuple[str, ...] = ("lattice", "network", "stream", "ml")


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

    @staticmethod
    def _allowed_kwargs(flavor: str) -> frozenset[str]:
        """(2026-07-07) 返回 flavor 允许的 Camelot kwargs 白名单.

        跟 camelot.utils.flavor_to_kwargs 对齐:
          - lattice → _LATTICE_KWARGS ∪ _COMMON_KWARGS
          - stream/network → _STREAM_KWARGS ∪ _COMMON_KWARGS
          - hybrid → _LATTICE_KWARGS ∪ _STREAM_KWARGS ∪ _COMMON_KWARGS
          - ml → _ML_KWARGS ∪ _COMMON_KWARGS
        所有 flavor 都接 common_kwargs (backend / margins / table_areas 等)
        """
        if flavor == "lattice":
            return _LATTICE_KWARGS | _COMMON_KWARGS
        if flavor in {"stream", "network"}:
            return _STREAM_KWARGS | _COMMON_KWARGS
        if flavor == "hybrid":
            return _LATTICE_KWARGS | _STREAM_KWARGS | _COMMON_KWARGS
        if flavor == "ml":
            return _ML_KWARGS | _COMMON_KWARGS
        raise ValueError(f"camelot 不支持的 flavor: {flavor!r} (应为 lattice/stream/network/hybrid/ml)")

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
            # 重依赖 lazy: pymupdf 加载 50ms+, 非路径不浪费
            import pymupdf  # noqa: E402  # 重依赖 lazy

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

    @staticmethod
    def extract_with_fallback(
        pdf_path: str,
        *,
        flavor: str = "lattice",
        params: dict | None = None,
        _pymupdf_doc: object | None = None,
        fallback_chain: bool = True,
    ) -> list[TableData]:
        """(2026-07-08) 带 fallback 的 extract. 首选 flavor 找不到表 → 试链上下一个 flavor.

        Args:
            pdf_path: PDF 文件路径.
            flavor: 首选 flavor. 默认 "lattice".
            params: 传给所有 flavor 的共用 params (例 line_scale, edge_tol, ml 模型等).
            _pymupdf_doc: 已开 pymupdf doc (本期 camelot 不复用, 保留接口对齐 base.TableExtractor).
            fallback_chain: True (默认) → 0 表时按 _FALLBACK_CHAIN 降级;
                            False → 只跑首选 flavor, 0 表直接返 [].

        Returns:
            list[TableData] — 第一个返回非空列表的 flavor 的结果; 全返 [] 时给 [].
        """
        # 软依赖: loguru 不一定装 (test 模式可能用 stdlib), 用 stderr fallback
        try:
            from loguru import logger

            log = logger
        except ImportError:
            import logging

            log = logging.getLogger(__name__)

        user_params = dict(params or {})
        flavors_to_try: tuple[str, ...] = _FALLBACK_CHAIN if fallback_chain else (flavor,)
        # 把首选 flavor 放最前 (如果它在链里); 不在链里 (罕见) 单独跑
        if flavor in flavors_to_try:
            ordered_flavors: list[str] = [flavor] + [f for f in flavors_to_try if f != flavor]
        else:
            ordered_flavors = [flavor]

        for try_flavor in ordered_flavors:
            try:
                wrapper = CamelotTableExtractor({**user_params, "flavor": try_flavor})
            except BackendNotInstalledError as e:
                # ml 没装 → 静默跳过, 不阻断链路
                log.info("camelot fallback 跳过 flavor={} ({})", try_flavor, e.install_hint)
                continue
            try:
                tables = wrapper.extract(pdf_path, _pymupdf_doc=_pymupdf_doc)
            except Exception as e:  # noqa: BLE001  # 业务故意 broad: 任何解析异常降级到下一档
                log.warning("camelot flavor={} 解析失败, 降级下一档: {}", try_flavor, e)
                continue
            if tables:
                if try_flavor != flavor:
                    log.info(
                        "camelot fallback 命中: 首选 {} 0 表 → flavor={} 返 {} 张",
                        flavor,
                        try_flavor,
                        len(tables),
                    )
                return tables
        # 全 0 表, 返空
        return []


# ---------------------------------------------------------------------------
# (2026-07-09) Task 2: 单页 0 表门控 + ml 兜底
# ---------------------------------------------------------------------------


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
        # type: ignore[operator]  # pynvml stub 把 .free 推到 str|bytes|Any 联合类型, 实际是 int
        free_mb = int(mem_info.free) // (1024 * 1024)
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
        raw_user_max = merged_kwargs.get("ml_max_workers")
        user_max: int | None = int(raw_user_max) if isinstance(raw_user_max, (int, float)) else None
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

    双档 IoU 阈值:
      - > 0.7 高置信: 静默丢 ml
      - > 0.5 灰区: 丢 ml + log.warning (保留可观察性)
      - < 0.5 / ml 无 bbox: 都留

    Args:
        lattice_tables: lattice 识别结果 (含 bbox).
        ml_tables: ml 识别结果 (含 bbox). None 当 [].

    Returns:
        去重合并列表. lattice 优先, ml 仅在新位置 / 低重叠时留.

    Note:
        本期 (2026-07-09) **不集成到 extract 流程**, 仅作为 helper 落地供未来 v2 集成.
        当前调度是 lattice→ml 顺序, lattice+ml 并行 + 调本 helper 需重设计.
    """
    from loguru import logger as _log

    if not ml_tables:
        return list(lattice_tables)
    result: list[TableData] = list(lattice_tables)
    for ml_t in ml_tables:
        ml_bbox = ml_t.bbox
        if ml_bbox is None:
            # (2026-07-09) ml 没 bbox → 保守全留, 不丢 (无法判重)
            result.append(ml_t)
            continue
        is_dup = False
        for lat_t in lattice_tables:
            lat_bbox = lat_t.bbox
            if lat_bbox is None:
                continue
            iou = _bbox_overlap(ml_bbox, lat_bbox)
            if iou > _DEDUP_IOU_HIGH:
                # (2026-07-09) 高置信重复 → 静默丢 ml, 不打 log
                is_dup = True
                break
            if iou > _DEDUP_IOU_LOW:
                # (2026-07-09) 灰区 → 丢 ml + log.warning (留 trace)
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


def _stack_contiguous_in_flavor(tables: list[TableData]) -> list[TableData]:
    """(2026-07-09) C1: 单 flavor 内按列数 + 页号相邻做 stack_contiguous 合并.

    评审调整 #4: camelot 2.0 TableList.stack_contiguous() API 存在性未在本机验证,
    自实现对 list[TableData] 做列数匹配合并, 不依赖 camelot API.

    合并规则 (相邻 2 张表同时满足):
      1. curr.page_no == prev.page_no + 1  (页号严格相邻)
      2. len(curr.rows[0]) == len(prev.rows[0])  (列数严格相等)
      3. prev.rows 和 curr.rows 都非空

    合并后 page_no = f"{prev.page_no}+{curr.page_no}" (str, 跨页编码).

    Args:
        tables: 单 flavor 内已排序的 TableData 列表 (按 (page_no, table_no) 升序)

    Returns:
        合并后的 list[TableData], 未匹配相邻规则的表原样保留.
    """
    if not tables:
        return tables
    merged: list[TableData] = []
    for curr in tables:
        if not merged:
            merged.append(curr)
            continue
        prev = merged[-1]
        # 只对 int page_no 做合并 (str 表示已合并过, 跳过避免 "1+2+3")
        if (
            isinstance(prev.page_no, int)
            and isinstance(curr.page_no, int)
            and curr.page_no == prev.page_no + 1
            and prev.rows
            and curr.rows
            and len(prev.rows[0]) == len(curr.rows[0])
        ):
            new_page_no: int | str = f"{prev.page_no}+{curr.page_no}"
            merged[-1] = TableData(
                page_no=new_page_no,
                table_no=prev.table_no,
                rows=prev.rows + curr.rows,
            )
        else:
            merged.append(curr)
    return merged


@dataclass(frozen=True)
class CrossPageMergerConfig:
    """(2026-07-09) C2 跨页合并器配置.

    Attributes:
        llm_model: LLM 模型名. None → env LLM_TRIM_HEADER_MODEL / LLM_MODEL.
        cache_enabled: LLM 判 header 是否重复的 LRU cache 开关.
        min_column_match: bbox 对齐时列数匹配度阈值.
        max_vertical_gap_px: bbox 对齐时上下页 y 坐标连续性阈值 (像素).
    """

    llm_model: str | None = None
    cache_enabled: bool = True
    min_column_match: float = 0.8
    max_vertical_gap_px: int = 20


# (2026-07-09) spec 4.6: bbox IoU helper, 给 lattice/ml 跨 flavor dedup + C2 同页 lines/text dedup 用.
# 表格场景典型阈值:
#   > 0.7 → 同表高置信重复 (lattice vs ml, lines vs text 同区域)
#   < 0.3 → 不同表, 都保留
# None 输入返 0.0, 缺 bbox 没法判重时保守按"不重叠"处理.
def _bbox_overlap(
    b1: tuple[float, float, float, float] | None,
    b2: tuple[float, float, float, float] | None,
) -> float:
    """(2026-07-09) IoU (Intersection over Union) of 2 bboxes (PDF 坐标 (x0, y0, x1, y1)).

    Args:
        b1, b2: (x0, y0, x1, y1) 或 None.

    Returns:
        IoU ∈ [0.0, 1.0]. 0 表示无重叠或任一为 None.
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


def _align_consecutive_pages(
    tables: list[TableData],
    pymupdf_tables: list,
) -> list[tuple[int, int]]:
    """(2026-07-09) C2 bbox 启发式对齐 → 候选续表对 [(prev_idx, curr_idx)].

    启发式 (同时满足):
      1. 页号相邻: curr.page_no == prev.page_no + 1
      2. y 连续: curr.bbox.y0 - prev.bbox.y1 < max_vertical_gap_px
      3. 列数 ≥ 80% 一致: len(curr.rows[0]) / len(prev.rows[0]) >= min_column_match
    """
    # 用 pymupdf bbox 建 (page_no -> bbox) 索引
    bbox_by_page: dict[int, tuple] = {}
    for pt in pymupdf_tables:
        bbox_by_page[pt.page] = pt.bbox

    pairs: list[tuple[int, int]] = []
    for i in range(len(tables) - 1):
        prev = tables[i]
        curr = tables[i + 1]
        if not (isinstance(prev.page_no, int) and isinstance(curr.page_no, int)):
            continue
        if curr.page_no != prev.page_no + 1:
            continue
        if prev.page_no not in bbox_by_page or curr.page_no not in bbox_by_page:
            continue
        prev_bbox = bbox_by_page[prev.page_no]
        curr_bbox = bbox_by_page[curr.page_no]
        # y 连续 (bbox 格式 (x0, y0, x1, y1))
        if curr_bbox[1] - prev_bbox[3] >= 20:  # max_vertical_gap_px=20
            continue
        # 列数匹配
        if not (prev.rows and curr.rows):
            continue
        prev_cols = len(prev.rows[0])
        curr_cols = len(curr.rows[0])
        if prev_cols == 0 or curr_cols / prev_cols < 0.8:
            continue
        pairs.append((i, i + 1))
    return pairs


class CrossPageMerger:
    """(2026-07-09) C2 跨页续表合并器 (PyMuPDF bbox + LLM 裁 header + 行拼接).

    数据流:
      1. PyMuPDF Page.find_tables() 逐页拿 bbox (PyMuPDF 无 Document.find_tables)
      2. bbox 启发式对齐 → 候选续表对
      3. LLM 判重复 header (LRU cache)
      4. 行拼接, page_no 编码 "5+6"
      5. 失败兜底 (LLM / bbox 失败 → 返原 tables + log warning)
    """

    def __init__(self, config: CrossPageMergerConfig | None = None) -> None:
        self._config = config or CrossPageMergerConfig()

    def _llm_trim_header(
        self,
        prev: TableData,
        curr: TableData,
    ) -> tuple[bool, int]:
        """(2026-07-09) 调 LLM 判 curr header 是否重复. mock 入口给测试用."""
        # 重依赖 lazy: llm_helper 含客户端初始化, 不在 import 期加载
        from src.core.llm_helper import trim_repeated_header  # noqa: E402

        return trim_repeated_header(
            prev.rows,
            curr.rows,
            page_a=int(prev.page_no) if isinstance(prev.page_no, int) else 0,
            page_b=int(curr.page_no) if isinstance(curr.page_no, int) else 0,
            llm_model=self._config.llm_model,
        )

    def merge(
        self,
        pdf_path: str,
        pymupdf_doc: object | None = None,  # pymupdf.Document, 类型 lazy import
        base_tables: list[TableData] | None = None,
    ) -> list[TableData]:
        """合并跨页表. 失败时返 base_tables 不变 + log warning.

        Args:
            pdf_path: PDF 路径 (pymupdf_doc=None 时自己开).
            pymupdf_doc: 已开 PyMuPDF doc. None → 自己 pymupdf.open(pdf_path).
            base_tables: C1 stack_contiguous 后结果. None → [].

        Returns:
            合并后的 list[TableData].
        """
        try:
            from loguru import logger

            log = logger
        except ImportError:
            import logging

            log = logging.getLogger(__name__)

        if not base_tables:
            return base_tables or []

        # 评审调整 #8: pymupdf_doc=None 时自己开
        own_doc = False
        try:
            if pymupdf_doc is None:
                import pymupdf  # noqa: E402  # 重依赖 lazy

                pymupdf_doc = pymupdf.open(pdf_path)  # type: ignore[arg-type]  # pymupdf.Document 跟 object 兼容, 业务只调 load_page / find_tables
                own_doc = True

            # 1. PyMuPDF Page.find_tables() 逐页拿 bbox
            pymupdf_tables: list = []
            doc = pymupdf_doc
            page_count_attr = getattr(doc, "page_count", None)
            load_page = getattr(doc, "load_page", None)
            if page_count_attr is None or load_page is None:
                log.warning("cross_page_merge pymupdf_doc 无 page_count/load_page, 返 base_tables 不变")
                return base_tables
            for page_idx in range(page_count_attr):
                page = load_page(page_idx)
                # (2026-07-09) spec 4.7: 同页双 strategy, lines 兜底 + text 补 borderless.
                # 跟 spec 4.6 跨 flavor dedup 区别: 这里 dedup 是 lines+text 同区域重复.
                seen_bboxes: list[tuple[float, float, float, float]] = []
                for strategy in ("lines", "text"):
                    for t in page.find_tables(strategy=strategy):  # type: ignore[union-attr]  # page 是 pymupdf.Page
                        t.page = page_idx + 1  # 1-based 对齐 camelot
                        t.strategy = strategy  # 标 strategy 给 _align_consecutive_pages 分组
                        bbox = getattr(t, "bbox", None)
                        # IoU > 0.7 视作同表重复 (lines + text 同一区域) → 跳过
                        if bbox is not None and any(_bbox_overlap(bbox, sb) > 0.7 for sb in seen_bboxes):
                            continue
                        pymupdf_tables.append(t)
                        if bbox is not None:
                            seen_bboxes.append(bbox)

            # 2. bbox 启发式对齐
            pairs = _align_consecutive_pages(base_tables, pymupdf_tables)

            # 3+4. 对每对候选调 LLM + 行拼接 (从后往前, 避免 index 偏移)
            merged: list[TableData] = list(base_tables)
            for prev_idx, curr_idx in reversed(pairs):
                prev = merged[prev_idx]
                curr = merged[curr_idx]
                try:
                    is_repeated, rows_to_skip = self._llm_trim_header(prev, curr)
                except Exception as e:  # noqa: BLE001  # 业务故意 broad: LLM 失败兜底
                    log.warning(
                        "cross_page_merge LLM 失败, 跳过 pair ({}, {}): {}",
                        prev_idx,
                        curr_idx,
                        e,
                    )
                    continue
                if not is_repeated:
                    continue
                # 行拼接: prev.rows + curr.rows[rows_to_skip:]
                new_page_no: int | str = f"{prev.page_no}+{curr.page_no}"
                new_table = TableData(
                    page_no=new_page_no,
                    table_no=prev.table_no,
                    rows=prev.rows + curr.rows[rows_to_skip:],
                )
                # 替换 prev + 删除 curr
                merged[prev_idx] = new_table
                del merged[curr_idx]

            return merged
        except Exception as e:  # noqa: BLE001  # 业务故意 broad: 任何异常兜底返 base_tables
            log.warning("cross_page_merge 整体失败, 返 base_tables 不变: {}", e)
            return base_tables
        finally:
            if own_doc and pymupdf_doc is not None:
                pymupdf_doc.close()  # type: ignore[attr-defined]  # own_doc=True 时 pymupdf_doc 必是 pymupdf.Document
