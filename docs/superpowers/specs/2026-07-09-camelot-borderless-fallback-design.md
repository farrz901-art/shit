# 2026-07-09 Camelot Borderless 表兜底 (ml flavor + 并行) 设计

> Brainstorming 沉淀. 用户报告 3 类问题:
> 1. 很多无竖线表格未识别
> 2. 多个表格被合并到 1 个单元格
> 3. 单元格列错位
>
> 本 spec 在现有 Camelot 适配器内**启用 ml flavor + 单页并行 + 0 表门控 + 后处理兜底**,
> 改动局限在 `camelot_extractor.py` + `base.py`, 不开新依赖 (ml extra 实际已装).

## 1. 背景

用户场景: 几百页 Siemens D81.1 PDF (D 81.1 · 09/2023), 其中包含大量
borderless 表 (有横线无竖线, 列靠文本对齐) 和跨页续表.

### 1.1 现状 (代码已确认)

`packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py:87-99`:

```python
_FLAVOR_DEFAULTS: dict[str, dict[str, int | float | bool]] = {
    "lattice": {"line_scale": 15, "line_tol": 2, "process_background": True, "use_fallback": True},
    "stream": {"row_tol": 5},
    "network": {},
    "hybrid": {},
    "ml": {},  # ← 空 dict, 没推荐值
}

_FALLBACK_CHAIN: tuple[str, ...] = ("lattice", "network", "stream", "ml")
```

代码已有 ml 支持, 但:

1. **ml 推荐值空**: `_FLAVOR_DEFAULTS["ml"]` 是 `{}`, 实际跑用 Camelot 2.0 默认 `detection_threshold=0.5`, 对 borderless 召回率低
2. **fallback chain 是文档级**: `extract_with_fallback` 整文档 0 表才降级下一档; 几百页 PDF 总有表, chain 永远停在 lattice
3. **单页粒度缺失**: 用户实际场景里某些页 0 表(纯文本页 / borderless 表页) 跟"整本 0 表"语义不同
4. **ml 实际未启用**: `uv run python -c "import transformers"` 已 OK (4.57.6), 但 `extract_with_fallback` 走的是文档级 0 表 chain, 几百页 PDF 永远不会触发到 ml 这一档

### 1.2 用户报告的 3 类问题

| 问题 | 根因 |
|---|---|
| 漏识别 | lattice 依赖横竖线, borderless 表无竖线 → 0 表; network/stream 走文本对齐但 row_tol 不当; ml 0 表门控失效 |
| 多表合成 1 cell | stream 在 row_tol=5 时把多行当作 1 cell, 没有"空行分隔"启发式 |
| 列错位 | Camelot 各 flavor 输出列数不固定, 没有"按表头列宽重对齐"步骤 |

## 2. 目标

- **0 表门控到单页粒度**: 某页 lattice 0 表 → 立刻调 ml 该页, 不等整本结束
- **ml 默认参数项目适配**: 写到 `_FLAVOR_DEFAULTS["ml"]`, admin 无需懂
- **多 flavor 结果去重**: lattice + ml 同页并行跑, bbox 重叠 > 50% 留 lattice (线检测准)
- **列重对齐**: 按表头列宽补空列 / 合多余 cell
- **拆合并**: 1×N 假表 (长文本) 调 ml 重识别该页
- **页间并发加速**: ThreadPoolExecutor 4 worker, 墙钟 ≈ 总页数/4

## 3. 非目标

- **不**改默认 `table_backend` (项目保持 pymupdf 默认, admin 选 camelot 才生效)
- **不**调 Camelot flavor 优先级 (lattice 仍第一, ml 第二)
- **不**删 stream/network (作为 3/4 级 fallback)
- **不**改前端 UI / BFF / API
- **不**写新依赖 (transformers + torch 已在 [ml] extra)
- **不**改 C1 stack_contiguous + C2 cross_page_merge 现有逻辑 (只在前后加步骤)

## 4. 设计

### 4.1 整体流程 (新 `extract`)

```python
def extract(self, pdf_path, *, _pymupdf_doc=None, **params):
    pymupdf_page_count = _get_page_count(_pymupdf_doc or pymupdf.open(pdf_path))

    # (1) 单页并行: 每页 lattice → 0 表 gate → ml
    with ThreadPoolExecutor(max_workers=max(1, params.get("max_page_workers", 4))) as ex:
        futures = {
            ex.submit(_extract_single_page, pdf_path, page, self._params): page
            for page in range(1, pymupdf_page_count + 1)
        }
        per_page_tables: dict[int, list[TableData]] = {}
        for fut in as_completed(futures):
            page = futures[fut]
            per_page_tables[page] = fut.result()

    # (2) 累加 + 排序
    result: list[TableData] = []
    for page in sorted(per_page_tables):
        for table_no, t in enumerate(per_page_tables[page], start=1):
            result.append(TableData(page_no=page, table_no=table_no, rows=t.rows))

    # (3) 现有 C1 stack_contiguous
    result = _stack_contiguous_in_flavor(result)

    # (4) 现有 C2 cross_page_merge (略调, 见 4.6)
    result = CrossPageMerger().merge(pdf_path, _pymupdf_doc, result)

    # (5) filter_valid (现有)
    return TableData.filter_valid(result, backend_name="camelot")


def _extract_single_page(pdf_path, page, params) -> list[TableData]:
    """单页提取. lattice → 0 表 gate → ml → 都 0 表 → network/stream."""
    log = _get_logger()
    tables = _run_camelot_single_page(pdf_path, page, "lattice", params)
    if tables:
        return tables
    log.info("camelot lattice page={} 0 表, 调 ml 兜底", page)
    tables = _run_camelot_single_page(pdf_path, page, "ml", params)
    if tables:
        return _merge_dedup_lattice_ml(tables)  # 此时只有 ml, noop
    log.info("camelot ml page={} 仍 0 表, 降级 network/stream", page)
    tables = _run_camelot_single_page(pdf_path, page, "network", params)
    if tables:
        return tables
    return _run_camelot_single_page(pdf_path, page, "stream", params)
```

**关键变化**:
- 取代 `pages="all"` 整文件调, 改为 `pages=str(page)` 单页调
- 4 worker 并发, 每页独立, 互不干扰 (PDF 文件只读不写, 文件锁 advisory)
- 0 表门控在单页级, 不在文档级
- **GPU 利用率** (2026-07-09 用户 RTX 5070 Ti 16G 调整): 4 个 lattice worker 走 CPU 满载; ml 0 表触发时进 Semaphore 拿 token, **运行期 nvml 探测 free VRAM 算最大 worker** (空载可撑 6 worker × 1.75GB = 10.5GB), admin 可 `ml_max_workers` 覆盖

### 4.2 ml 参数调优 (写到 `_FLAVOR_DEFAULTS`)

```python
# camelot_extractor.py
_FLAVOR_DEFAULTS: dict[str, dict[str, int | float | bool]] = {
    "lattice": {"line_scale": 15, "line_tol": 2, "process_background": True, "use_fallback": True},
    "stream": {"row_tol": 5},
    "network": {},
    "hybrid": {},
    # (2026-07-09) ml 推荐值: 阈值降到 0.3 提召回 (borderless 表),
    # row_tol=5 跟 stream 对齐, 检测少行表
    "ml": {
        "detection_threshold": 0.3,
        "structure_threshold": 0.4,  # 略高于 detection: cell 结构识别比表检测准 (DETR 内部)
        "row_tol": 5,
    },
}
```

**参数依据** (2026-07-09 工业实践, see web search):
- `detection_threshold` Camelot 默认 0.5: 太严, borderless 表 (无明显视觉边界) 检测不到
- `detection_threshold=0.3`: 折中, 召回提升 (D81 复杂背景文档), 假阳性可控
  - 0.2 太激进: 假阳性 30%+, 需 PyMuPDF verify 二次过滤 (本期不过滤, 留 v2)
- `structure_threshold=0.4`: 略高于 detection, DETR 内部 cell 结构识别比表检测准 (model v1.1 训练更稳)
- `row_tol=5`: 跟 stream 一致, 1-2 行小表也能识别
- `device="cuda"` 默认: GPU 部署, ml 在 GPU 跑 ~0.2-0.5s/页, CPU 5-10x 慢

**TableTransformer 工业实践** (microsoft/table-transformer-detection + structure-recognition-v1.1-all):
- 复杂背景文档 (设计文档/工业手册): 0.3-0.4
- 简单打印文档: 0.7-0.9
- borderless / 无竖线 (本 spec 场景): 0.3 detection + 0.4 structure 起步
- 0.2 detection 极度激进, 不推荐 (假阳性爆, 当前不过滤)

**注**: ml 真正使用的 `TableTransformer` 模型由 camelot 内部默认, 项目不直接调; 阈值 + 设备通过 camelot 公开参数传.

### 4.3 列重对齐 (realign_columns)

```python
def realign_columns(t: TableData) -> TableData:
    """(2026-07-09) 按表头列宽补空列 / 合多余 cell.
    
    算法:
      1. 找表头 (第 1 行) 列数 header_cols
      2. 遍历 body 行:
         - len(row) < header_cols → 末尾补空字符串
         - len(row) > header_cols → 多余 cell 拼到第 header_cols-1 个 (右侧末尾)
      3. 表头为空时, header_cols = max(len(r) for r in t.rows)
    
    Args:
        t: 单张 TableData.
    Returns:
        新 TableData, rows 已重对齐. frozen dataclass 故 replace.
    """
    if not t.rows:
        return t
    # 表头: 第 1 行非空且 len > 0; 否则用 max
    header = t.rows[0] if t.rows and any(c.strip() for c in t.rows[0]) else None
    if header is not None and header:
        header_cols = len(header)
    else:
        header_cols = max((len(r) for r in t.rows), default=1)
    if header_cols < 2:
        return t  # 1 列表, 不重对齐 (filter_valid 会过滤)
    new_rows: list[list[str]] = []
    for idx, row in enumerate(t.rows):
        if len(row) < header_cols:
            row = row + [""] * (header_cols - len(row))
        elif len(row) > header_cols:
            extra = " ".join(row[header_cols - 1 :])
            row = row[: header_cols - 1] + [extra]
        new_rows.append(row)
    return t.replace(rows=new_rows)
```

**触发位置**: `_extract_single_page` 返回后, `_merge_dedup_lattice_ml` 之前 (per-table 后处理).

### 4.4 拆合并 (ml 重识别该页)

```python
# 启发式: 1 cell 长文本 + 换行 → 高度疑似多表合并
def _looks_merged(t: TableData) -> bool:
    if not t.rows:
        return False
    if len(t.rows) == 1 and len(t.rows[0]) == 1:
        text = t.rows[0][0]
        return len(text) > 200 and "\n" in text  # 长文本 + 换行
    return False


def _unmerge_combined_with_ml(pdf_path, page, current_tables) -> list[TableData]:
    """(2026-07-09) 启发式: 1 cell 长文本 → 调 ml 重识别该页.
    
    Args:
        pdf_path: PDF 路径.
        page: 该页号 (1-based).
        current_tables: 当前页所有表.
    Returns:
        - 触发 ml 且 ml 有结果: ml 结果 (替换 current_tables)
        - 不触发或 ml 无结果: current_tables 原样
    """
    if not any(_looks_merged(t) for t in current_tables):
        return current_tables
    log = _get_logger()
    log.info("camelot page={} 检测到合并 1-cell 表, 调 ml 重识别", page)
    ml_tables = _run_camelot_single_page(pdf_path, page, "ml", params={...})
    return ml_tables if ml_tables else current_tables
```

**触发位置**: `_extract_single_page` 内, 4 层 fallback 之后; 若 ml 已用过(0 表门控那档), 不重复跑.

### 4.5 ml 模型缓存 + GPU 并发 (运行期动态)

```python
import threading
from typing import Optional

# 模块级: lazy init
_ML_MODEL: object | None = None
_ML_MODEL_LOCK = threading.Lock()  # 模型加载互斥
_ML_INFERENCE_SEM: Optional[threading.Semaphore] = None  # 限流, lazy
_ML_SEM_LOCK = threading.Lock()

# (2026-07-09) ml 单实例显存预算 (fp16 + 推理峰)
# 模型权重 ~1GB (TableTransformer fp16, microsoft/table-transformer-detection)
# 推理中间激活 + KV cache ~0.75GB/实例
_ML_MODEL_VRAM_MB = 1024
_ML_INFERENCE_OVERHEAD_MB = 768
_ML_SINGLE_INSTANCE_MB = _ML_MODEL_VRAM_MB + _ML_INFERENCE_OVERHEAD_MB  # 1792
_ML_RESERVE_MB = 1024  # 1GB 给 OS / CUDA context / 浏览器 / IDE
_ML_MAX_WORKERS_CLAMP = 6  # 6 worker × 1.75GB = 10.5GB, 不超过 12GB 可用


def _detect_max_ml_workers(device: str) -> int:
    """(2026-07-09) 运行期探测可用显存 → 算最大 ml 并发数.

    逻辑:
      free_mb = nvmlDeviceGetMemoryInfo().free // 1MB
      available = max(0, free_mb - RESERVE)
      workers = available // SINGLE_INSTANCE
      clamp [1, ML_MAX_WORKERS_CLAMP]

    Returns:
        int: 推荐 worker 数. 探测失败返 1 (保守).
    """
    if device != "cuda":
        return 1
    try:
        import pynvml  # 项目已用, 2026-06 nvidia-ml-py 切换
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        free_mb = mem_info.free // (1024 * 1024)
    except Exception as e:
        log.warning("ml 显存探测失败, fallback workers=1: {}", e)
        return 1
    available = max(0, free_mb - _ML_RESERVE_MB)
    workers = available // _ML_SINGLE_INSTANCE_MB
    return max(1, min(_ML_MAX_WORKERS_CLAMP, workers))


def _get_ml_inference_sem(device: str, user_max: int | None) -> threading.Semaphore:
    """(2026-07-09) 懒初始化 Semaphore. 优先级: user_max > 探测值 > 1.

    模块级单例, 进程内只创建一次.
    """
    global _ML_INFERENCE_SEM
    with _ML_SEM_LOCK:
        if _ML_INFERENCE_SEM is not None:
            return _ML_INFERENCE_SEM
        if user_max is not None and user_max > 0:
            workers = user_max
        else:
            workers = _detect_max_ml_workers(device)
        log.info("ml inference Semaphore 初始化 workers={} device={} (按 free VRAM 探测)", workers, device)
        _ML_INFERENCE_SEM = threading.Semaphore(workers)
        return _ML_INFERENCE_SEM


def _run_camelot_single_page(pdf_path, page, flavor, params) -> list[TableData]:
    """调 camelot.read_pdf 单页. ml 走 GPU Semaphore 限流."""
    if flavor == "ml":
        device = params.get("ml_device", "cuda")
        user_max = params.get("ml_max_workers")  # None = 自动探测
        sem = _get_ml_inference_sem(device, user_max)
        with sem:  # 限流 GPU 并发
            return _do_run_camelot(pdf_path, page, flavor, params)
    return _do_run_camelot(pdf_path, page, flavor, params)


def _do_run_camelot(pdf_path, page, flavor, params) -> list[TableData]:
    """实际调 camelot.read_pdf, 加 timeout 30s 防单页 hang."""
    import camelot
    try:
        tables = camelot.read_pdf(
            pdf_path,
            flavor=flavor,
            pages=str(page),
            **params,
        )
    except Exception as e:
        log.warning("camelot flavor={} page={} 失败: {}", flavor, page, e)
        return []
    return _camelot_to_table_data(tables)
```

**设计要点** (2026-07-09 运行期动态并发):
- **不是写死 max_ml_workers=2**, 而是在首次 ml 调用时 `nvmlDeviceGetMemoryInfo` 探 free VRAM, 算出最大 worker 数
- 用户显式传 `ml_max_workers=4` → 强制覆盖探测值 (admin / CI 场景)
- 探测失败 (pynvml 缺 / nvmlInit 失败) → 保守用 1 worker
- 进程内 Semaphore 单例, 后续调用复用 (不会重新探测, 避免抖动)

**timeout**: 用 `signal.alarm` / `camelot.read_pdf` 内部有 30s; 不可中断时 wrap 进 `concurrent.futures` future 加 `future.result(timeout=30)`.

**配置** (2026-07-09 用户硬件 RTX 5070 Ti 16G 调整):
- `params.get("max_page_workers", 4)` — 页间并发数 (lattice 走 CPU, 无显存压力)
- `params.get("ml_max_workers", None)` — ml 并发数显式覆盖; None = 探测
- `params.get("ml_device", "cuda")` — 默认走 GPU, 无 GPU 环境 fallback "cpu"
- `params.get("ml_timeout_sec", 30)` — ml 单页超时

**实际探测场景** (RTX 5070 Ti 16G, 16303 MiB total, 当前空载):
- 跑 spec 时空载: free=15744 MiB, available=14720, workers = 14720/1792 = 8 → clamp 6
- 同时跑 Chrome + IDE: free≈10000, workers ≈ 5
- CI 共享 GPU (2 进程): free≈8000, workers ≈ 3
- 探测失败 (pynvml 缺): workers = 1 (最保守)

**CPU 环境 fallback**:
- 无 CUDA: `ml_device="cpu"` 返 1 worker (避免 4×CPU 抢资源)
- 自动检测: `torch.cuda.is_available()` False → `ml_device="cpu"`

### 4.6 bbox 去重 (lattice ∪ ml)

Camelot `TableList` 元素有 `.bbox` 属性 (x0, y0, x1, y1 in PDF 坐标). 利用:

```python
def _bbox_overlap(b1, b2) -> float:
    """IoU (Intersection over Union) of 2 bboxes."""
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


def _merge_dedup_lattice_ml(
    lattice_tables: list[TableData],
    ml_tables: list[TableData] | None = None,
) -> list[TableData]:
    """(2026-07-09) bbox IoU 双档判重, 留 lattice.
    
    阈值 (COCO NMS 工业标准 0.5 起步, 表格场景调档):
      - IoU > 0.7: 高置信重复 → 直接丢 ml (同表 lattice 跟 ml 几乎重叠)
      - IoU > 0.5: 判重 → 丢 ml, log warning (可能漏, 但保守)
      - IoU < 0.5: 不判重 → ml 留 (新表 / 不同位置)
    
    Args:
        lattice_tables: lattice 识别的表 (含 _bbox 字段).
        ml_tables: ml 识别的表 (含 _bbox 字段). None → 当 [].
    Returns:
        合并去重后的表列表.
    """
    if not ml_tables:
        return lattice_tables
    result = list(lattice_tables)
    log = _get_logger()
    for ml_t in ml_tables:
        ml_bbox = getattr(ml_t, "_bbox", None)
        if ml_bbox is None:
            result.append(ml_t)
            continue
        is_dup = False
        for lat_t in lattice_tables:
            lat_bbox = getattr(lat_t, "_bbox", None)
            if lat_bbox is None:
                continue
            iou = _bbox_overlap(ml_bbox, lat_bbox)
            if iou > 0.7:
                # 高置信重复: 直接丢, 不打日志
                is_dup = True
                break
            if iou > 0.5:
                # 判重线: 丢 ml, log warning 方便后续调参
                log.warning(
                    "camelot bbox 判重 page={} lattice 跟 ml IoU={:.2f}, 保留 lattice",
                    getattr(ml_t, "page_no", "?"),
                    iou,
                )
                is_dup = True
                break
        if not is_dup:
            result.append(ml_t)
    return result
```

**注**: 需给 `TableData` 加可选 `_bbox` 字段; `base.py` TableData 已是 frozen dataclass, 加 `bbox: tuple | None = None`.

**IoU 阈值依据** (2026-07-09 工业实践):
- COCO NMS 默认 0.5 (mAP@0.5), 文档表格场景略低 (0.4-0.5)
- 双档: 0.7 高置信直接丢, 0.5 判重打日志 (后续调参可见)
- 表格特征: 同表 lattice vs ml 通常 IoU > 0.7, 同页 2 个不同表 IoU < 0.3
- 不用首行文本相似度 fallback (TextFuzzy 慢, 跟 bbox 比无优势)

### 4.7 PyMuPDF strategy="text" 补 cross_page_merge

现有 `CrossPageMerger.merge` (line 466-469):

```python
for t in page.find_tables(strategy="lines"):  # ← 只识别有线
```

**问题**: ml 补出来的 borderless 跨页续表, PyMuPDF `strategy="lines"` 找不到 bbox → C2 merge 失效.

**修法**: 加 `strategy="text"` 作为兜底:

```python
pymupdf_tables: list = []
for page_idx in range(page_count_attr):
    page = load_page(page_idx)
    for t in page.find_tables(strategy="lines"):
        t.page = page_idx + 1
        t.strategy = "lines"
        pymupdf_tables.append(t)
    # (2026-07-09) 兜底 borderless: strategy="text" 也跑, 给 ml 补的表用
    for t in page.find_tables(strategy="text"):
        t.page = page_idx + 1
        t.strategy = "text"
        pymupdf_tables.append(t)
```

后处理: `_align_consecutive_pages` 内按 strategy 分组判断(避免 lines 表跟 text 表误判重叠).

### 4.8 错误处理

| 失败模式 | 处理 |
|---|---|
| ml extra 缺 (transformers/torch) | `BackendNotInstalledError` 在 `CamelotTableExtractor.__init__` 抛, fallback chain 静默跳过, 降级 network/stream |
| ml 单页超时 (30s) | `future.result(timeout=30)` raise TimeoutError, log warning, 该页降级 network/stream |
| 整页 ml OOM | 进程级单例 + 2 worker Semaphore (4.5), 单次 OOM 进程崩, 上层 runner 兜底 (mark_stage_failed) |
| 并发读 PDF 文件锁 | 同一文件多次 open (camelot 内部用 pdfplumber + ghostscript) 走 advisory lock, 不冲突; Windows 文件锁可能撞, 加 retry |
| 跨页续表 (C2 merge) 失效 | 4.7 加 strategy="text" 兜底 |
| bbox 字段缺失 (老 camelot 版本) | 4.6 fallback 用 (page_no, table_no) 位置 + 首行文本相似度判重 |

### 4.9 进度可见

加 loguru 进度 (per-page, 不刷屏):

```python
log.info("camelot extract 进度 {}/{} pages (ml 触发 {} 页)", done, total, ml_triggered_count)
```

## 5. 改动范围

### 5.1 源文件 (3 个)

- `packages/service/src/ingest/pre_analysis/table_extractors/base.py`
  - `TableData` 加 `bbox: tuple | None = None` 字段 (frozen dataclass)
- `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py`
  - `_FLAVOR_DEFAULTS["ml"]` 加推荐值
  - 加 `_extract_single_page` / `_run_camelot_single_page` / `_do_run_camelot` / `_ML_MODEL_LOCK`
  - 加 `realign_columns` / `_looks_merged` / `_unmerge_combined_with_ml`
  - 加 `_bbox_overlap` / `_merge_dedup_lattice_ml`
  - `CamelotTableExtractor.extract` 改为按页并行
  - `CrossPageMerger.merge` 内 `find_tables` 加 `strategy="text"`
- `packages/service/src/ingest/pre_analysis/table_extractors/factory.py`
  - `_CamelotFallbackWrapper` 透传新 params (max_page_workers / max_ml_workers / ml_timeout_sec)

### 5.2 测试文件 (4 个新增 + 1 修改)

- 新增 `tests/ingest/pre_analysis/table_extractors/test_realign_columns.py` — 8 case
- 新增 `tests/ingest/pre_analysis/table_extractors/test_unmerge_combined.py` — 5 case (启发式 + ml mock)
- 新增 `tests/ingest/pre_analysis/table_extractors/test_bbox_dedup.py` — 6 case (IoU 计算 + 判重)
- 新增 `tests/ingest/pre_analysis/table_extractors/test_extract_single_page.py` — 集成 mock (lattice→ml 0 表门控 / ml→network fallback / 并发调度)
- 修改 `tests/ingest/pre_analysis/table_extractors/test_camelot_extractor.py` (已有)
  - 补单页并行 case (4 worker mock)
  - 补 ml 推荐参数存在

## 6. 测试覆盖

| 测试 | 模式 | 验证 |
|---|---|---|
| `test_realign_columns_less_cols` | 1 mock | 3 列 → 4 列补 1 空 |
| `test_realign_columns_more_cols` | 1 mock | 5 列 → 4 列合多余到末尾 |
| `test_realign_columns_empty_header` | 1 mock | 表头空时用 max |
| `test_realign_columns_single_col` | 1 mock | 1 列不重对齐 |
| `test_unmerge_looks_merged` | 1 mock | 1×1 长文本 + 换行 → True |
| `test_unmerge_not_merged` | 1 mock | 多行 → False |
| `test_unmerge_ml_replace` | 1 mock | 触发后 ml 结果替换 current |
| `test_unmerge_ml_no_result` | 1 mock | ml 0 表 → 返 current |
| `test_bbox_overlap_full` | 1 mock | 2 个全等 bbox → 1.0 |
| `test_bbox_overlap_partial` | 1 mock | 50% 重叠 → 0.5 |
| `test_bbox_overlap_none` | 1 mock | 不重叠 → 0.0 |
| `test_dedup_lattice_ml` | 1 mock | 1 lattice + 1 ml 重叠 → 只留 lattice |
| `test_dedup_lattice_ml_distinct` | 1 mock | 1 lattice + 1 ml 不重叠 → 都留 |
| `test_extract_lattice_ok` | 1 mock | lattice 返表, 不调 ml |
| `test_extract_lattice_0_ml_ok` | 1 mock | lattice 0 表 → 调 ml → 返 ml |
| `test_extract_lattice_0_ml_0_network` | 1 mock | 双 0 表 → network 兜底 |
| `test_extract_unmerge_triggered` | 1 mock | 1 cell 长文本 → ml 重识别 |
| `test_extract_parallelism` | 1 mock | 4 worker 跑 4 页, 时间 < 串行 |

## 7. 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| ml 在 CPU 慢 (~1-2s/页 × 几百页 = 5-15 分钟) | GPU (cuda) ~0.2-0.5s/页, 运行期动态 1-6 worker + 5070 Ti 16G, 几百页估 30s-3 分钟; 0 表 gate 触发, 实测 lattice 0 表页比例 < 20% |
| ml 模型首次加载 5-10s, 1GB 显存 (fp16) | 进程级单例, `_ML_MODEL_LOCK` 互斥, 后续 0 成本 |
| GPU 显存被其他程序占用 | 运行期 `pynvml.nvmlDeviceGetMemoryInfo` 探测 free VRAM → 动态算 worker 数; 不会撑爆 |
| ml threshold=0.3 假阳性 | PyMuPDF verify bbox (C2 merge 现有); filter_valid 兜底 |
| ml threshold=0.3 假阳性 | PyMuPDF verify bbox (C2 merge 现有); filter_valid 兜底 |
| 列重对齐误改 | 启发式保守: 头 = 第 1 行非空; 空表头用 max; 只补 / 合到 header_cols |
| 拆合并 ml 重跑 | 只对 _looks_merged 触发 (1×1 长文本 + 换行), 不滥触发 |
| 并发读 PDF 文件锁 (Windows) | advisory lock 不冲突; 仍有问题: 加 `concurrent.futures` 退避 retry |

## 8. 实施步骤 (2 阶段)

### 阶段 1: ml 启用 + 单页调度 + 并发 + 后处理 (3-5 天)
- `_FLAVOR_DEFAULTS["ml"]` 加推荐值 (detection=0.3, structure=0.4, row_tol=5)
- `extract` 改为按页循环 (`pages=str(page)`)
- 0 表门控: lattice 0 表 → ml → 仍 0 表 → network/stream
- ThreadPoolExecutor 加 `max_page_workers=4`
- `realign_columns` per-table 后处理
- `_unmerge_combined_with_ml` 启发式触发 (1×1 长文本 + 换行)
- `_get_ml_inference_sem` 运行期 nvml 探测 free VRAM 算 max workers
- `_ML_MODEL_LOCK` 进程级单例 + 首次加载 5-10s
- 单元 + 集成测试 (lattice 0 表 gate 触发 ml, 并发调度, realign, unmerge)

### 阶段 2: bbox 去重 + cross_page_merge 升级 (1-2 天)
- `TableData.bbox` 字段 (frozen dataclass 加 `bbox: tuple | None = None`)
- `_bbox_overlap` IoU 计算
- `_merge_dedup_lattice_ml` 双档判重 (0.7 高置信 / 0.5 log warning)
- `CrossPageMerger.merge` 内 `find_tables` 加 `strategy="text"` 兜底 borderless 跨页
- 端到端测试 (用 D81.1 真 PDF 跑, 验漏识别率 + 列错位修复)

每阶段独立 commit + 单测全绿才进下一阶段. 阶段 1 完成后 admin 就能选 camelot 跑新流程 (无 ml 也工作); 阶段 2 优化跨页续表 + 重复检测.

## 9. 文档更新

- `docs/superpowers/specs/2026-07-09-camelot-degenerate-table-filter-design.md` 后续补 cross-ref
- `packages/service/CLAUDE.md` 章节 §"表格提取" 补 ml 推荐参数 + 并发默认值
- `packages/web/messages/{zh,en}.json` 补 "ml 兜底" / "列重对齐" 文案 (本期不暴露 UI, 留 commit 备注)

## 10. 未来工作 (本期不做)

- LLM 判 ml 输出是否为真表 (假阳性治理)
- PDF 渲染图 → image-based ML (Tesseract OCR + TableNet)
- 表格类型分类 (catalog / spec / data) → 路由到不同提取器

## 11. 反模式 (本次避免)

- ❌ **不**改默认 `table_backend` (项目保持 pymupdf 默认)
- ❌ **不**开新依赖 (transformers + torch 已在 [ml] extra)
- ❌ **不**改 C1/C2 现有逻辑的核心 (只在前后加步骤)
- ❌ **不**调 Camelot 5 flavor 顺序 (lattice 仍第一)
- ❌ **不**删 stream/network fallback
- ❌ **不**写 shim 兼容层 (项目零技术债原则)
