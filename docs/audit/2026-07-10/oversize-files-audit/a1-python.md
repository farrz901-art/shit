# A1 Python Oversize Files Audit (2026-07-10)

> 25 个 .py 文件扫描, 总 11659 行. 按行数降序排列.
> 只读扫描, 不修业务代码, 仅给 7 段拆分建议 + 骨架伪代码.
> pyproject.toml 已装库: pydantic (48), sqlalchemy (10), fastapi (12), loguru (20), httpx (39), neo4j (28), langchain-core (50), langchain-postgres (52), camelot-py (56), ezdxf (33), pymupdf (31), psycopg (26), asyncpg (27), deepeval (55), pillow (62).

---

### `packages/service/src/kg/router.py` (1040 行)

**1. 拆分点**: L90-181 `stats/health/datasets/segments` (Dify 代理层) -> `dify_proxy.py` (module); L272-404 `nodes/relationships/products/schemas` (Neo4j dataset 隔离列表层) -> `neo4j_list.py` (module); L569-636 `extract/datasets + extract/tasks` 列表 + L640-649 `extract/extractors/splitters` 白名单 -> `extract_meta.py` (module); L665-697 `extract/upload` + L707-739 `_build_extractor/splitter` 工厂 -> `extract_upload.py` (module); L742-1032 4 端点 `start/preview/items/commit/export` -> `extract_workflow.py` (module).
**2. 纯函数/类化**: 可拆 — `_serialize_task` (L615-636), `_build_extractor` (L707-728), `_build_splitter` (L731-739), `_escape` (L1035-1040) 都是 stateless 纯函数; dataclass schema `TripleRowIn/TriplesRequest/TriplesResponse/BatchItem/BatchRequest/BatchResponse/StartExtractRequest/PatchItem/PatchItemsRequest` (L55-89, L700-704, L864-871) 适合抽 `kg_schemas.py`.
**3. 库替代**: pydantic `BaseModel` 已装 (pyproject.toml:48), L55-89/L700-704/L864-871 已是 pydantic 写法; 无其他替换.
**4. 对象替 if**: L598-612 `list_extract_tasks` 中 `kind in ("kg_extract", "kg_batch", "all")` 守卫 -> `_EXTRACT_TASK_KINDS: frozenset = frozenset({"kg_extract", "kg_batch", "all"})` + `if kind not in _EXTRACT_TASK_KINDS: raise HTTPException(422, ...)`; L615-636 `_serialize_task` 中 `if t.kind == "kg_extract"` -> `_KG_EXTRACT_PAYLOAD_KEYS = ("dataset", "extractor", "splitter", "uri")` dict-comprehension.
**5. 数组迭代替循环**: L124-134 累加 `dify["documents"]` -> `sum(d.get("document_count", 0) for d in data)` (已是); L337-341 解析 schema yaml 文件名 -> `[{domain, file} for f in files for domain in [Path(f).stem.replace("-schema", "")]]` 列表推导.
**6. 预计减少**: 1040 -> 280 (-73%, 主 router 留路由挂载 + 几个跨模块共享 helper).
**7. 骨架伪代码**:
- `dify_proxy.py`:
```python
# imports: 只列需要的
import os
import requests
from fastapi import APIRouter, Depends
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_page

def _dify_health() -> dict:
    """GET DIFY_BASE_URL/datasets?limit=1, 返 {ok, error?}"""
    pass  # 5xx 降级, 不抛

def _dify_datasets() -> dict:
    """代理 Dify /datasets?limit=100, 降级返 {data: []}"""
    pass

def _dify_segments(dataset_id: str, document_id: str) -> dict:
    """代理 Dify segments, 缺参降级返 {data: []}"""
    pass
```
- `extract_meta.py`:
```python
from typing import Literal
from pydantic import BaseModel, Field

_EXTRACT_TASK_KINDS: frozenset = frozenset({"kg_extract", "kg_batch", "all"})

def list_kg_datasets() -> list[dict]:
    """列 env 白名单 dataset labels (公开读)"""
    pass

def list_extractors() -> list[dict]:
    """白名单 spacy_rule / llm_pydantic"""
    pass

def list_splitters() -> list[dict]:
    """3 个白名单 splitter + chunk_size range"""
    pass
```

---

### `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (999 行)

**1. 拆分点**: L89-122 `_FLAVOR_DEFAULTS / _FACTORY_PARAMS / _FALLBACK_CHAIN` 配置常量 -> `camelot_config.py` (module); L125-335 `CamelotTableExtractor` 类 (init + extract + extract_with_fallback) -> `camelot_extractor_class.py` (module); L342-456 `_ensure_ml_loaded / _detect_max_ml_workers / _get_ml_inference_sem` ML 资源管理层 -> `camelot_ml_runtime.py` (module); L477-562 `_run_camelot_single_page / _call_camelot` 单页调度层 -> `camelot_page_runner.py` (module); L596-635 `realign_columns` + L638-662 `_unmerge_combined_with_ml` + L674-728 `_merge_dedup_lattice_ml` + L731-775 `_stack_contiguous_in_flavor` 后处理工具层 -> `camelot_postprocess.py` (module); L778-866 `CrossPageMergerConfig + _bbox_overlap + _align_consecutive_pages` 跨页合并器基础 -> `camelot_cross_page.py` (module); L869-999 `CrossPageMerger` 类 -> `camelot_cross_page.py` (同 module, 续).
**2. 纯函数/类化**: 可拆 — `realign_columns` (L596-635) 纯函数; `_looks_merged` (L457-474) 纯函数; `_stack_contiguous_in_flavor` (L731-775) 纯函数; `_bbox_overlap` (L800-824) 纯函数; `_align_consecutive_pages` (L827-866) 纯函数; `CrossPageMergerConfig` (L778-792) 已是 frozen dataclass, 适合独立 module; `CamelotTableExtractor._allowed_kwargs` (L153-172) 静态方法可保留.
**3. 库替代**: dataclass 已用 (pyproject.toml:62 装 dev 隐式; 标准库 dataclass); pydantic 不适合 (这些都是 frozen 数据容器, dataclass 语义更准); 无其他替换.
**4. 对象替 if**: L164-172 `_allowed_kwargs` 中 `if flavor == "lattice" / if flavor in {"stream", "network"} / if flavor == "hybrid" / if flavor == "ml"` -> 查表 `_FLAVOR_KWARG_SETS: dict[str, frozenset[str]] = {"lattice": _LATTICE_KWARGS | _COMMON_KWARGS, "stream": ..., "network": ..., "hybrid": ..., "ml": ...}` + `_FLAVOR_KWARG_SETS.get(flavor) or _raise_unknown_flavor(flavor)`.
**5. 数组迭代替循环**: L752-775 `_stack_contiguous_in_flavor` for curr in tables 累加合并 -> `itertools.reduce` 或 while + index (但 reduce 反而难读, 当前 25 行可保留); L817-824 `_bbox_overlap` 计算 union/intersect -> 抽 `_rect_intersect` helper.
**6. 预计减少**: 999 -> 200 (主入口 extractor class + 路由); 6 个辅助 module 各 80-150 行.
**7. 骨架伪代码**:
- `camelot_extractor_class.py`:
```python
# imports: 只列需要的
from .base import BackendNotInstalledError, TableData, TableExtractor

class CamelotTableExtractor(TableExtractor):
    """camelot.read_pdf 适配器. 5 flavor 支持 + fallback 链."""

    def __init__(self, params: dict) -> None:
        """验包 + [ml] extra 检查"""

    @staticmethod
    def _allowed_kwargs(flavor: str) -> frozenset[str]:
        """按 flavor 返 Camelot kwargs 白名单"""

    def extract(self, pdf_path: str, **params) -> list[TableData]:
        """按页并行 + 后处理 + cross-page merge"""

    @staticmethod
    def extract_with_fallback(pdf_path: str, **kwargs) -> list[TableData]:
        """首选 flavor 0 表 → 试链上下一个 flavor"""
```
- `camelot_ml_runtime.py`:
```python
# imports: threading
import threading

_ML_MODEL: object | None = None
_ML_MODEL_LOCK = threading.Lock()

def _ensure_ml_loaded() -> object:
    """ml 模型懒加载单例, 首次 acquire Lock 加载 5-10s"""

def _detect_max_ml_workers(device: str) -> int:
    """nvml 探测可用 VRAM → 算 ml 并发 worker 数 (1-6)"""

def _get_ml_inference_sem(device: str, user_max: int | None) -> threading.Semaphore:
    """懒初始化 ml inference Semaphore, 进程级单例"""
```

---

### `packages/service/src/ingest/pdf_processing/router.py` (743 行)

**1. 拆分点**: L84-130 `_dict_to_task / _save / _load / _list_user / _new_task_id` 任务持久化 + 进程 cache 包装层 -> `task_persistence.py` (module); L131-189 `OutputFile / InputFile / IngestTask` 3 个 dataclass + `to_dict` -> `task_models.py` (module); L192-205 `_MIME_MAP / _mime_for` MIME 推断 -> `mime_helper.py` (module); L217-242 `_collect_output_files_legacy / _find_output_file` Path 模式产物收集 -> `path_mode_collect.py` (module); L385-407 `_collect_output_files / _mime_for_name` ABC 模式产物收集 -> `uri_mode_collect.py` (module); L702-743 `_zip_iter_uri / _zip_iter` zip 流生成器 -> `zip_stream.py` (module); L289-487 路由 handler `presign_upload / finalize_upload / upload / _run_ingest` -> 主 router 留挂载.
**2. 纯函数/类化**: 可拆 — `_dict_to_task` (L84-99) 纯函数; `_mime_for` / `_mime_for_name` (L204-205, L404-407) 纯函数; `_find_output_file` (L233-242) 纯函数; `OutputFile.to_dict` / `InputFile.to_dict` / `IngestTask.to_dict` 已是方法.
**3. 库替代**: pydantic `BaseModel` 已装 (pyproject.toml:48), 3 个 dataclass (L131-189) 适合改 pydantic `BaseModel` 拿 `model_dump()` 替代手写 `to_dict`; 评估: 项目其他 router 多用 dataclass, 一致性保留.
**4. 对象替 if**: L622-625 `read_task_file` 中 `".." in name / name.startswith("/") / not SAFE_NAME.match(name)` 三连校验 -> `_validate_safe_name(name: str) -> None` helper raise HTTPException; L500-501 `_run_ingest` 中 `isinstance(work_dir, str) and "://" in work_dir` URI 模式判断 -> `_URI_PREFIX = "://"` 守卫 helper.
**5. 数组迭代替循环**: L702-712 `_zip_iter_uri` 内 `for meta in store.list_prefix(out_prefix): ... zf.writestr(...)` -> `[zf.writestr(meta.uri.replace(out_prefix, ""), Path(lp).read_bytes()) for meta in store.list_prefix(out_prefix) for lp in [store.open_local_ctx(meta.uri).__enter__()]]` (但 generator 闭包更清晰, 保留).
**6. 预计减少**: 743 -> 220 (-70%, 主 router 留 handler + model 定义 + 路由挂载).
**7. 骨架伪代码**:
- `task_models.py`:
```python
# imports: 只列需要的
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

@dataclass
class OutputFile:
    """产物文件描述 (内存 + JSON)"""
    name: str
    size: int
    mime: str
    error: str | None = None
    uri: str = ""

@dataclass
class InputFile:
    """(2026-06-11) 用户上传的原始文件描述"""
    name: str
    size: int
    mime: str
    uri: str = ""

@dataclass
class IngestTask:
    """任务状态 (内存, v1)"""
    id: str
    user_hash: str
    state: Literal["queued", "running", "completed", "failed"]
    total_files: int
    processed: int = 0
    failed: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None
    error: str | None = None
    input_files: list[InputFile] = field(default_factory=list)
    output_files: list[OutputFile] = field(default_factory=list)
    work_dir: str | Path | None = None
```
- `task_persistence.py`:
```python
# imports: datetime, Path
from .store import _store as _store
from .models import IngestTask as ORMIngestTask

def _save(t: IngestTask) -> None:
    """写穿到 SQLite + 更新进程内 cache"""
    pass

def _load(task_id: str) -> IngestTask | None:
    """先看进程内 cache, 没了再从 store 拉"""
    pass

def _list_user(uhash: str) -> list[IngestTask]:
    """列用户任务, 按 started_at DESC"""
    pass
```

---

### `packages/service/src/storage/object_store.py` (598 行)

**1. 拆分点**: L44-49 `ObjectStoreError / ObjectNotFound` 异常类 -> 保留; L55-94 `parse_uri / build_uri` URI helper -> `object_store_uri.py` (module); L100-160 `ObjectStore` ABC + 14 抽象方法 -> `object_store_abc.py` (module); L166-261 `LocalFSObjectStore` impl -> `object_store_local.py` (module); L267-550 `MinioObjectStore` impl -> `object_store_minio.py` (module); L553-598 `_object_store_singleton / get_object_store / _reset_object_store` 单例工厂 -> `object_store_factory.py` (module).
**2. 纯函数/类化**: 可拆 — `parse_uri` (L61-79) 纯函数; `build_uri` (L82-94) 纯函数; `_get_ml_inference_sem` 同模式; `ObjectStore.open_local_ctx` (L138-144) 已是 @contextmanager 抽象方法, 实现跟 L138 一致.
**3. 库替代**: pydantic `BaseModel` 已装, `ObjectMeta` (L100-107) dataclass 可改 pydantic; urllib.parse `urlparse` 已用 (L67); 无其他替换.
**4. 对象替 if**: L67-79 `parse_uri` 中 `if p.scheme not in (_LOCAL_SCHEME, _S3_SCHEME) / if p.scheme == _S3_SCHEME and not p.netloc / if p.scheme == _S3_SCHEME` 三段 if -> 查表 `_SCHEME_KEY_EXTRACTORS: dict[str, Callable[[str], str]] = {"s3": lambda p: p.path.lstrip("/"), "local": lambda p: (p.netloc + p.path).lstrip("/")}` + `extract = _SCHEME_KEY_EXTRACTORS.get(p.scheme) or _raise_unknown_scheme(p.scheme)`.
**5. 数组迭代替循环**: L222-240 `list_prefix` for p in sorted(prefix.rglob("*")) 累加 ObjectMeta -> `[ObjectMeta(...) for p in sorted(prefix.rglob("*")) if p.is_file() and p.exists()]` 列表推导 (但 try/except ValueError 难嵌入, 保留).
**6. 预计减少**: 598 -> 100 (主 module 留 import + 公开 API re-export); ABC 60 行, LocalFS 95 行, Minio 285 行, factory 45 行, URI 35 行, exceptions 8 行.
**7. 骨架伪代码**:
- `object_store_abc.py`:
```python
# imports: abc, contextmanager
import abc
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import BinaryIO

@dataclass(frozen=True)
class ObjectMeta:
    """元数据 (不读 body)"""
    uri: str
    size: int
    mime: str | None = None
    last_modified: float | None = None

class ObjectStore(abc.ABC):
    """对象存储 ABC. 14 抽象方法."""

    @abc.abstractmethod
    def backend_name(self) -> str: ...

    @abc.abstractmethod
    def put_bytes(self, uri: str, data: bytes, mime: str | None = None) -> None: ...

    # ... 共 14 个抽象方法
```
- `object_store_local.py`:
```python
# imports: pathlib, shutil
from .object_store_abc import ObjectStore, ObjectMeta, ObjectNotFound

class LocalFSObjectStore(ObjectStore):
    """LocalFS impl: 写本地 FS, key 直接当 LOCAL_ROOT 下相对路径."""
    def __init__(self, local_root: str | Path = "./ingest_uploads"):
        pass

    def backend_name(self) -> str: ...
    def put_bytes(self, uri: str, data: bytes, mime: str | None = None) -> None: ...
    # ... 14 个方法全实现
```

---

### `packages/service/src/ingest/pre_analysis/router.py` (568 行)

**1. 拆分点**: L67-152 `upload_pre_analysis` 上传 + 校验 + 写 PG + 调度 -> `pre_analysis_upload.py` (module); L155-185 `list_pre_analysis_tasks / get_pre_analysis_task` 元数据查询 -> `pre_analysis_query.py` (module); L188-230 `download_pre_analysis_zip` 整包下载 -> `pre_analysis_download.py` (module); L233-282 `download_pre_analysis_file` 单文件下载 -> `pre_analysis_download.py` (续); L285-396 `list_table_pages / get_table_page` tables viewer -> `pre_analysis_tables.py` (module); L399-425 `list_pre_analysis_stages` stage 进度 -> `pre_analysis_stages.py` (module); L428-493 `retry_pre_analysis_task` 重试 -> `pre_analysis_retry.py` (module); L499-544 `_run_pre_analysis` 后台 runner 调度 -> `pre_analysis_runner_dispatch.py` (module); L547-568 `_orphan_cleanup_pre_analysis_tasks` 启动清理 -> `pre_analysis_orphan.py` (module).
**2. 纯函数/类化**: 可拆 — `_run_pre_analysis` (L499-544) 可抽 helper, 但目前已只调用 runner.run; `_orphan_cleanup_pre_analysis_tasks` (L547-568) 纯函数.
**3. 库替代**: pydantic `BaseModel` 已装, 无新 dataclass; loguru 已用.
**4. 对象替 if**: L100-101 `if table_backend not in ("pymupdf", "camelot", "pdfplumber")` -> `_ALLOWED_TABLE_BACKENDS: frozenset = frozenset({"pymupdf", "camelot", "pdfplumber"})` + 守卫; L375-379 `get_table_page` 中 `if f.get("kind") != "table": continue / if f_page == page_num:` 双层 for -> 列表推导 `[(f["filename"], f["uri"]) for f in task["output_files"] if f.get("kind") == "table" and _parse_page(f["filename"]) == page_num]`.
**5. 数组迭代替循环**: L560-568 `_orphan_cleanup_pre_analysis_tasks` 累加 count -> `[r for r in rows if r.state in ("pending", "running")]` 推导 + `len()`.
**6. 预计减少**: 568 -> 80 (主 router 留 8 个挂载); 9 个 module 各 40-60 行.
**7. 骨架伪代码**:
- `pre_analysis_upload.py`:
```python
# imports: io, json, datetime
from datetime import UTC, datetime
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pathlib import Path

_ALLOWED_TABLE_BACKENDS: frozenset = frozenset({"pymupdf", "camelot", "pdfplumber"})

async def upload_pre_analysis(
    background: BackgroundTasks, file: UploadFile, table_backend: str, table_params: str,
    chapter_config_json: str,
) -> dict:
    """上传 PDF, 调度后台预分析. table_backend/table_params (2026-07-06 支持 config)."""
    pass  # 100MB 校验, parse chapter_cfg, 写 ObjectStore, 调度 _run_pre_analysis
```
- `pre_analysis_tables.py`:
```python
from fastapi import APIRouter, HTTPException
from ...middleware.auth import CurrentUser
from .table_view import build_table_page_response, extract_table_pages, parse_table_filename

async def list_table_pages(task_id: str, user: CurrentUser) -> dict:
    """(2026-07-09 tables viewer) 列出有表格的 PDF 页号."""
    pass  # 调 extract_table_pages

async def get_table_page(task_id: str, page_num: int, user: CurrentUser) -> dict:
    """(2026-07-09) 查指定页所有表格的解析数据 (含 CSV → JSON 解析)."""
    pass  # 拉 page_files, 读 CSV, build_table_page_response
```

---

### `packages/service/src/lookups/admin_router.py` (562 行)

**1. 拆分点**: L69-76 `_actor_display / _client_ip` helper -> `_guards.py` (module) 已有, 合并; L79-104 `_guard` 6 层防御翻译 helper -> 保留; L110-195 `create_dictionary` (POST) -> `dict_create.py` (module); L198-253 `patch_dictionary` (PATCH) -> `dict_patch.py` (module); L259-317 `create_item` (POST item) -> `item_create.py` (module); L320-383 `patch_item` (PATCH item) -> `item_patch.py` (module); L386-451 `soft_delete_item` (DELETE) -> `item_delete.py` (module); L457-495 `issue_confirm_token` -> `confirm_token.py` (module); L501-562 `get_dictionary_audit` -> `dict_audit.py` (module).
**2. 纯函数/类化**: 可拆 — `_actor_display` (L69-71) 纯函数; `_client_ip` (L74-76) 纯函数; `_guard` (L79-104) async helper.
**3. 库替代**: pydantic `BaseModel` 已装, schema 已在 `src.lookups.schemas`; 无新增.
**4. 对象替 if**: L598 (注: 本文件无此行) — 改看 L121-129 `create_dictionary` 中 `if existing: raise LookupSafetyError(409, ...)` -> 查表 `_DICT_CONFLICT_HTTP: dict[ConflictKind, int] = {"exists": 409, "readonly": 403}` 配合 Exception; 实际 L186-188 `if req.role == "super_admin"` (在 admin_router.py 的 patch_user, 本文件无) — 本文件 L155-180 `create_dictionary` 内的 422 错误码用 `_HTTP_BY_REASON: dict[str, int] = {"code_invalid": 422, "readonly": 403, "exists": 409}`.
**5. 数组迭代替循环**: L546-561 `get_dictionary_audit` for row in rows 累加 AuditLogEntry -> 列表推导 `[AuditLogEntry(...) for row in rows]` (已是).
**6. 预计减少**: 562 -> 80 (主 router 留 7 个 endpoint 挂载 + 共享 helper import); 7 个 module 各 50-80 行.
**7. 骨架伪代码**:
- `_guards.py` (共享 helper):
```python
# imports: datetime, hashlib
import hashlib
from datetime import UTC, datetime, timedelta
from fastapi import HTTPException, Request
from .exceptions import LookupSafetyError

def _actor_display(user) -> str:
    """提取 audit_log 友好显示名 (email 优先, fallback public_token)"""
    pass

def _client_ip(request: Request) -> str | None:
    """提取客户端 IP (request.client.host)"""
    pass

async def _guard(*, action, dict_code, key, user, confirm_token, payload, force=False) -> None:
    """跑 SafetyGuard 6 层防御, 失败 raise HTTPException"""
    pass
```
- `item_patch.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from ...core.audit import audited
from ...lookups.schemas import LookupItemPatchRequest, LookupItemResponse
from ...lookups.service import LookupService
from ...middleware.auth import CurrentUser
from ...permissions.cache import invalidate_page_keys_cache, rewarm_page_keys_cache
from ...permissions.guards import require_super_admin
from ._guards import _guard

@router.patch("/{dict_code}/items/{key}", response_model=LookupItemResponse)
@audited("admin.dict.item.patch", target_type="dictionary_item")
async def patch_item(request, dict_code, key, body, user):
    """改 item (super_admin)."""
    pass
```

---

### `packages/service/src/ingest/pdf_processing/converters/cad.py` (512 行)

**1. 拆分点**: L27-117 ODA 路径解析 (`_read_oda_path_from_env_or_config / _apply_oda_path_from_config / _resolve_oda_exec_path`) -> `cad_oda_path.py` (module); L124-172 `read_cad_with_oda + OdaNotInstalledError` ODA 转换 + 异常 -> `cad_oda_reader.py` (module); L180-265 `CadConvertResult + EzdxfConverter.convert` 顶层 convert -> 保留; L267-272 `_read` DWG/DXF 分流 -> 保留; L274-326 `_render_svgs + _page_from_modelspace` SVG 渲染 -> `cad_svg_renderer.py` (module); L328-364 `_extract_text` 文本提取主循环 -> `cad_text_extractor.py` (module); L366-454 `_record_text / _record_mtext / _record_dimension / _record_leader / _record_tolerance / _record_insert_attribs` 6 个 record 函数 -> 合并 `cad_text_records.py` (module); L456-463 `_xy` 坐标 helper -> 合并进 records module; L465-512 `_text_to_markdown` markdown 渲染 -> `cad_markdown_writer.py` (module).
**2. 纯函数/类化**: 可拆 — `_read_oda_path_from_env_or_config` (L50-60) 纯函数; `_resolve_oda_exec_path` (L89-117) 纯函数; `_page_from_modelspace` (L312-326) 纯函数; `_xy` (L456-463) 纯函数; 6 个 `_record_*` 纯函数.
**3. 库替代**: dataclass 已用 (L180-188 `CadConvertResult`); pydantic 不适合 (二进制 DTO, dataclass 够用); ezdxf (pyproject.toml:33) 已是 CAD 解析库, 无其他替换.
**4. 对象替 if**: L107-117 `_resolve_oda_exec_path` 中 `if platform == "win" / else` 双分支 -> 查表 `_ODA_EXEC_BUILDER: dict[str, Callable[[Path], Path]] = {"win": _add_exe_suffix, "unix": _add_unix_name}` + `_ODA_EXEC_BUILDER[platform](p)`; L340-364 `_extract_text` 主循环 `if t == "TEXT" / elif t == "MTEXT" / ...` 6 个分支 -> 查表 `_TEXT_RECORDERS: dict[str, Callable] = {"TEXT": _record_text, "MTEXT": _record_mtext, ...}` + `_TEXT_RECORDERS[t](entity, layout_name, t) or None`.
**5. 数组迭代替循环**: L337-364 `_extract_text` 累加 records -> 双重列表推导 `[r for layout_name in doc.layouts.names() for entity in doc.layouts.get(layout_name) for r in [_extract_one(entity, t, layout_name, doc)] if r is not None]` (难读, 保留 for); L450-454 `_record_insert_attribs` 累加 recs -> `[self._record_attrib(a, entity, layout_name) for a in attribs if not except]` 列表推导.
**6. 预计减少**: 512 -> 130 (主 module 留 import + class EzdxfConverter 入口); ODA path 95 行, SVG renderer 60 行, text records 110 行, markdown writer 50 行.
**7. 骨架伪代码**:
- `cad_oda_reader.py`:
```python
# imports: ezdxf.addons.odafc
from pathlib import Path
import platform

class OdaNotInstalledError(RuntimeError):
    """ODA File Converter 未安装时抛"""
    pass

def read_cad_with_oda(dwg_path: str | Path, audit: bool = True):
    """用 ODA File Converter 把 DWG 转成 DXF, 再用 ezdxf 读. 失败抛友好 RuntimeError."""
    pass
```
- `cad_text_records.py`:
```python
from ezdxf import ...

def _record_text(entity, layout_name: str, t: str) -> dict:
    """TEXT 实体记录"""
    pass

def _record_mtext(entity, layout_name: str, t: str) -> dict:
    """MTEXT 实体记录"""
    pass

def _record_dimension(entity, layout_name: str, t: str) -> dict | None:
    """DIMENSION 实体记录; 文字为空且 measurement 不可读返 None"""
    pass
```

---

### `packages/service/scripts/neo4j_import.py` (499 行)

**1. 拆分点**: L54-61 `load_yamls` YAML 加载 -> 保留 (小); L67-206 `yaml_to_graph_data` 业务转换 (产品系列 + 技术参数 + 参数值 + 产品型号 4 类节点 + 4 类关系) -> 保留 (核心业务); L209-236 `dedup_against_neo4j` 去重过滤 -> 保留; L242-332 `Neo4jClient` 类 (4 env 读取 + lazy connect + APOC 验证 + label 查询 + cypher 执行) -> `neo4j_client.py` (module); L335-350 `_normalize_uri_for_ssl_context` URI scheme 改写 -> 保留在 client; L353-376 `build_cypher` apoc.merge.cypher 模板 -> 保留; L379-403 `format_props / render_node_table / render_rel_table` 表格渲染 -> `neo4j_import_render.py` (module); L406-440 `cmd_import` -> 保留; L443-453 `cmd_check` -> 保留; L456-499 `main` argparse + dotenv 加载 -> 保留.
**2. 纯函数/类化**: 可拆 — `load_yamls` (L54-61) 纯函数; `yaml_to_graph_data` (L67-206) 纯函数 (无副作用); `dedup_against_neo4j` (L209-236) 纯函数; `_normalize_uri_for_ssl_context` (L335-350) 纯函数; `build_cypher` (L353-376) 纯函数; `format_props` (L379-383) 纯函数; `render_node_table` (L386-393) 纯函数; `render_rel_table` (L396-403) 纯函数.
**3. 库替代**: yaml (pyproject.toml:36), tabulate (pyproject.toml:37) 已装; 无替换.
**4. 对象替 if**: L97-98 `if pos.get("type") != "enum": continue` 简单 continue 不需替换; L120-129 `if isinstance(decoded, dict): ... else: ...` 决定 value_props 形状 -> 查表 `_DECODED_VALUE_BUILDERS: list[Callable] = [_build_dict_value, _build_scalar_value]`.
**5. 数组迭代替循环**: L75-91 累加 series_node + L94-114 enum_positions + L117-133 参数值节点 + L137-195 4 类关系 -> 这都是单次 for 累加, 适合保留 for; L198-204 节点去重 `if n["name"] in seen: continue / seen.add / unique_nodes.append` -> 查表 `{n["name"]: n for n in nodes}` dict-comprehension (namedtuple 拿第一个).
**6. 预计减少**: 499 -> 180 (-64%, 留 main + cmd_import + cmd_check + yaml_to_graph_data + dedup); Neo4jClient 90 行, render 25 行.
**7. 骨架伪代码**:
- `neo4j_client.py`:
```python
# imports: os, ssl, certifi, neo4j
import os
import ssl
import certifi
from neo4j import GraphDatabase

_SCHEME_MAP: dict[str, str] = {
    "neo4j+s://": "neo4j://",
    "neo4j+ssc://": "neo4j://",
    "bolt+s://": "bolt://",
    "bolt+ssc://": "bolt://",
}

def _normalize_uri_for_ssl_context(uri: str) -> str:
    """neo4j+s://X / bolt+s://X → neo4j://X / bolt://X"""
    pass

class Neo4jClient:
    """封装 neo4j driver, 4 个 env var 缺一报错."""

    def __init__(self, uri, user, password, database, driver=None):
        pass

    @classmethod
    def from_env(cls) -> Neo4jClient:
        """从 NEO4J_* env var 构造, 缺一报 RuntimeError"""
        pass

    def _connect(self):
        """懒连接, ssl_context 配 certifi CA 跨平台"""
        pass

    def check_apoc(self) -> str:
        """验 APOC 可用, 返回版本号"""
        pass

    def existing_node_names(self, label: str) -> set[str]:
        """查指定 label 下所有节点的 name"""
        pass

    def count_nodes_by_label(self, label: str) -> int:
        """查指定 label 的节点数"""
        pass

    def run_cypher(self, cypher: str, params: dict) -> None:
        """执行 cypher, 失败透传 Neo4jError"""
        pass
```

---

### `packages/service/src/auth/auth_admin_router.py` (464 行)

**1. 拆分点**: L40-58 `UserItem / UserListResponse` schema + L85-134 `list_users` GET -> `admin_users_list.py` (module); L140-222 `CreateInviteRequest / CreateInviteResponse` schema + L181-222 `create_invite` POST -> `admin_invite_create.py` (module); L228-313 `PatchUserRequest` schema + L265-313 `patch_user` PATCH -> `admin_user_patch.py` (module); L319-356 `reset_user_password` POST -> `admin_password_reset.py` (module); L362-428 `InviteItem / InviteListResponse` schema + L401-428 `list_invites` GET -> `admin_invite_list.py` (module); L434-464 `delete_invite` DELETE -> `admin_invite_delete.py` (module).
**2. 纯函数/类化**: 全部 endpoint 都是路由 handler, 无 stateless helper 抽; L34 `require_admin = require_super_admin` 别名保留.
**3. 库替代**: pydantic `BaseModel` 已装, 4 个 schema (L40-58, L140-153, L228-233, L362-374) 全 pydantic 写法, 无替换.
**4. 对象替 if**: L96-108 `list_users` 中 `if kind == "account" / elif kind == "anon"` + `if is_active is True / elif is_active is False` -> 拼 SQL 过滤条件查表; 适合抽 `_user_filter_clauses(search, kind, is_active) -> list[ColumnElement]` builder; L99-108 多 OR 拼装难改 if 链; L186-203 `create_invite` 中 `if req.role == "super_admin" / if not s.query(Role).filter_by(name=req.role).first() / if email 已注册 / if 已有未用 invite` 4 连守卫 -> `_validate_invite_request(req, admin) -> None` helper raise HTTPException.
**5. 数组迭代替循环**: L116-133 `list_users` 累加 UserItem -> 列表推导 `UserItem(...) for u, a in rows` (已是); L190-203 `create_invite` 4 连守卫 -> `[check_1, check_2, check_3, check_4]` 守卫 list `for check in guards: check()`.
**6. 预计减少**: 464 -> 80 (主 router 留 6 个 endpoint 挂载); 6 个 module 各 50-70 行.
**7. 骨架伪代码**:
- `admin_users_list.py`:
```python
# imports: fastapi, pydantic, sqlalchemy
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from ..auth.account_models import Account
from ..auth.models import User
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_super_admin
from ..storage.session import session_scope

class UserItem(BaseModel):
    id: int
    email: str | None
    display_name: str | None
    role: str
    is_admin: bool
    is_active: bool
    kind: str  # "account" | "anon"
    account_id: int | None
    created_at: datetime
    last_seen_at: datetime
    last_login_at: datetime | None

class UserListResponse(BaseModel):
    items: list[UserItem]
    total: int
    page: int
    page_size: int

@router.get("/users", response_model=UserListResponse)
def list_users(user, search, kind, is_active, page, page_size):
    """列所有用户 + 搜索/分页/过滤."""
    pass
```

---

### `packages/service/src/approvals/router.py` (459 行)

**1. 拆分点**: L37-75 `_resolve_user / _current_user_cls / require_login / require_admin` 鉴权依赖层 -> `approvals_auth.py` (module); L78-128 `_to_async_url / _get_async_engine / _make_async_sessionmaker / _get_session / _get_repo / _get_svc` 异步 DB session + repo 工厂链 -> `approvals_deps.py` (module); L131-145 `RejectBody / SubmitBody` 2 个 request schema -> 保留 (各 endpoint 引用); L151-182 `submit` POST -> 保留; L185-214 `list_all` GET admin -> 保留; L217-250 `list_mine` GET me -> 保留; L253-280 `stats` GET admin -> 保留; L283-313 `get_detail` GET -> 保留; L316-356 `approve` POST -> 保留; L359-396 `reject` POST -> 保留; L399-435 `retry` POST -> 保留; L441-459 `_serialize` Approval → dict helper -> 保留.
**2. 纯函数/类化**: 可拆 — `_to_async_url` (L81-85) 纯函数; `_serialize` (L441-459) 纯函数; `_make_async_sessionmaker` (L106-108) 纯函数.
**3. 库替代**: pydantic `BaseModel` 已装, 2 个 schema (L134-145) 全 pydantic; 无替换.
**4. 对象替 if**: L388-389 `if body.reason == RejectReason.OTHER and not body.note: raise HTTPException(422, ...)` -> 查表 `_REJECT_REQUIRES_NOTE: frozenset = frozenset({RejectReason.OTHER})` + 守卫; L71-74 `if not isinstance(user, CU) or not user.is_admin` -> 鉴权装饰器 `_require_role("admin")`.
**5. 数组迭代替循环**: L213-214 `[_serialize(a) for a in items]` (已是); L243-250 `list_mine` 同样; L277-280 `stats` 3 次 repo.list -> 适合并行 `asyncio.gather` 但项目无 asyncio.gather 用法, 保留.
**6. 预计减少**: 459 -> 280 (-39%); 拆出 2 个 module 各 30-50 行.
**7. 骨架伪代码**:
- `approvals_auth.py`:
```python
# imports: fastapi, typing
from fastapi import APIRouter, Depends, HTTPException
from typing import Any

def _resolve_user(request) -> Any:
    """FastAPI 鉴权依赖 — lazy import 拿 src.middleware.auth.resolve_user."""
    pass

def _current_user_cls():
    """lazy import 拿 CurrentUser 类型 (用于 isinstance 守卫)."""
    pass

def require_login(user: Any = Depends(_resolve_user)) -> Any:
    """任意登录用户 (resolve_user 失败时已 401)."""
    pass

def require_admin(user: Any = Depends(_resolve_user)) -> Any:
    """admin-only: 拿不到 admin 身份 → 403."""
    pass
```
- `approvals_deps.py`:
```python
# imports: sqlalchemy.ext.asyncio
from collections.abc import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ..common.db_url import get_rag_db_url
from .repo import SqlAlchemyApprovalRepo
from .service import ApprovalService

def _to_async_url(url: str) -> str:
    """PG-only: sync URL (psycopg) → async URL (asyncpg)."""
    pass

async def _get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI Depends: 每个请求一个 AsyncSession, 用完 close."""
    pass

async def _get_repo(session: AsyncSession = Depends(_get_session)) -> SqlAlchemyApprovalRepo:
    """构造 repo (绑定本请求 session)."""
    pass

async def _get_svc(repo: SqlAlchemyApprovalRepo = Depends(_get_repo)) -> ApprovalService:
    """构造 service (绑定本请求 repo)."""
    pass
```

---

### `packages/service/src/lookups/service.py` (450 行)

**1. 拆分点**: L20-41 `_parse_meta` helper (注: 本文件无, 在 chat/service.py) — 此文件无 _parse_meta; L44-64 `list_all_dicts` 读 -> 保留; L66-108 `get` 读 -> 保留; L110-130 `get_one` 读 -> 保留; L134-205 `create_item` 写 -> 保留; L207-278 `patch_dict` 写 -> 保留; L280-350 `patch_item` 写 -> 保留; L352-407 `soft_delete_item` 写 -> 保留; L411-450 `_load_all_from_db` DB load helper -> 保留 (核心).
**2. 纯函数/类化**: `LookupService` 全静态方法, 无 class state; `_load_all_from_db` (L411-450) 纯函数; 适合拆 `read.py` (list_all/get/get_one/_load) + `write.py` (create/patch/soft_delete).
**3. 库替代**: pydantic `BaseModel` 已装, 但本文件无 schema (都在 schemas.py); 无替换.
**4. 对象替 if**: L97-100 `if only_active: items = [i for i in items if i.get("is_active", True)] / if lang == "zh": items = [...]` -> 抽 `_filter_items(items, only_active, lang) -> list[dict]` helper; L316-326 `for field in allowed_fields: if field in payload and payload[field] is not None: setattr(item, field, payload[field])` -> 抽 `_apply_patch(item, allowed_fields, payload) -> None`.
**5. 数组迭代替循环**: L426-449 `_load_all_from_db` 累加 result + items 装入 dict -> 双重 for 改 dict 构造 + 列表推导 `[item_data for item in items if item.dict_code in result]`.
**6. 预计减少**: 450 -> 280 (-38%); 拆 2 个 read/write module.
**7. 骨架伪代码**:
- `read.py`:
```python
# imports: sqlalchemy
from sqlalchemy import select
from src.lookups.cache import lookup_cache
from src.lookups.exceptions import LookupNotFoundError

class LookupReadService:
    """读路径: cache → DB fallback."""

    @staticmethod
    async def list_all_dicts() -> list[dict]:
        """列出全部字典概要 (字典级, 不含 items)."""
        pass

    @staticmethod
    async def get(dict_code: str, *, only_active: bool = True, lang: str = "both") -> dict:
        """查单字典 + items. only_active 控制 is_active 过滤, lang 控制 label 字段."""
        pass

    @staticmethod
    async def get_one(dict_code: str, key: str) -> dict:
        """查单个 item. raise LookupNotFoundError."""
        pass
```
- `write.py`:
```python
# imports: sqlalchemy, datetime
from datetime import UTC, datetime
from sqlalchemy import select
from src.lookups.audit import log_dict_change
from src.lookups.cache import lookup_cache
from src.lookups.exceptions import LookupNotFoundError, LookupSafetyError

class LookupWriteService:
    """写路径: DB 事务 → cache.invalidate → audit_log."""

    @staticmethod
    async def create_item(dict_code, payload, *, actor, actor_id, ip) -> dict:
        """新增 item."""
        pass

    @staticmethod
    async def patch_dict(dict_code, payload, *, actor, actor_id, ip) -> dict:
        """改字典 metadata."""
        pass

    @staticmethod
    async def patch_item(dict_code, key, payload, *, actor, actor_id, ip) -> dict:
        """改 item."""
        pass

    @staticmethod
    async def soft_delete_item(dict_code, key, *, actor, actor_id, ip, force=False) -> dict:
        """软删 item."""
        pass
```

---

### `packages/service/src/ingest/pdf_processing/pipeline.py` (448 行)

**1. 拆分点**: L26-57 `process_path` 三路分发 -> 保留 (核心入口); L60-93 `process_uri` URI 模式 (借出 inputs + 跑 pipeline + 回传 outputs) -> 保留; L96-119 `_process_single_file` 单文件扩展名路由 -> 保留; L122-242 `process_files` 主入口 (递归扫 + 解压 + 分桶 + 三流水线调度) -> 保留; L245-340 `process_documents` Document 流水线 (analyze + 分类 + 分组批量转换) -> 保留; L343-406 `process_cad_files` CAD 流水线 -> 保留; L409-444 `process_passthrough` Markdown 直通 -> 保留.
**2. 纯函数/类化**: `process_files` 太长 (120 行), 但内部都是命令式; `_process_single_file` (L96-119) 纯函数; 3 个 bucket 调度器 (L211-236) 适合抽 `_run_bucket(bucket_name, files, output_path) -> dict` helper.
**3. 库替代**: 无; pydantic 不适合 (内部 IO 流水线).
**4. 对象替 if**: L114-115 `_process_single_file` 中 `if ext in MarkdownPassthroughHandler.extensions / if ext in EzdxfConverter.extensions / if any(ext in c.extensions for c in CONVERTERS.values())` 三路分发 -> 查表 `_EXTENSION_ROUTERS: list[tuple[Callable, str, Callable]]` priority-sorted.
**5. 数组迭代替循环**: L158-159 `all_files = [f for f in input_path.rglob("*") if f.is_file()]` (已是); L162-204 多 for 嵌套 (archives 抽 + pool 收集 + unknown 警告) -> 保留 (顺序敏感).
**6. 预计减少**: 448 -> 280 (-37%); 抽 `_run_bucket` helper 后降重复.
**7. 骨架伪代码**:
- `bucket_runner.py`:
```python
# imports: loguru, pathlib
from loguru import logger
from pathlib import Path

def _run_bucket(bucket_name: str, files: list[Path], output_path: Path) -> dict:
    """统一调度 1 个桶 (passthrough / cad / document) + 结果收集.

    Returns:
        dict 形如 {"processed": [...], "errors": [...]}
    """
    pass  # 走对应 process_*_files, 记 log
```

---

### `packages/service/src/auth/account_settings_router.py` (424 行)

**1. 拆分点**: L30-44 `_to_out` Account → AccountOutExtended mapper -> 保留 (跟其他 endpoint 共享); L47-76 `patch_profile` PATCH profile -> `profile.py` (module); L79-114 `post_avatar / L117-145 delete_avatar / L148-178 get_avatar` 3 avatar 端点 -> `avatar.py` (module); L181-221 `patch_email` PATCH email -> `email_change.py` (module); L224-258 `post_email_verify` POST verify -> `email_verify.py` (module); L261-306 `patch_password` PATCH password -> `password_change.py` (module); L309-333 `get_deletion` GET status -> `deletion_status.py` (module); L336-384 `post_deletion` POST request -> `deletion_request.py` (module); L387-424 `delete_deletion` DELETE cancel -> `deletion_cancel.py` (module).
**2. 纯函数/类化**: 可拆 — `_to_out` (L30-44) 纯函数; 9 个 endpoint 都是单职责; 适合每个端点独立 module.
**3. 库替代**: pydantic `BaseModel` 已装, schema 已在 `account_settings_schemas.py`; 无替换.
**4. 对象替 if**: L30-44 `_to_out` 中 `if account.is_pending_deletion and account.deletion_requested_at is not None: deletion_expires_at = ...` -> 抽 `_compute_deletion_expires_at(account) -> datetime | None` helper.
**5. 数组迭代替循环**: 无明显 for 累加; endpoint 内单条操作.
**6. 预计减少**: 424 -> 50 (主 router 留 9 个 endpoint 挂载 + 共享 import); 9 个 module 各 20-40 行.
**7. 骨架伪代码**:
- `profile.py`:
```python
# imports: fastapi, pydantic
from fastapi import APIRouter, Depends, HTTPException
from ..auth.account_models import Account
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_active_account
from ..storage.session import session_scope
from . import account_settings_service as svc
from ._to_out import _to_out
from .account_settings_schemas import AccountOutExtended, ProfileUpdate

@router.patch("/profile")
def patch_profile(req: ProfileUpdate, user: CurrentUser = Depends(require_active_account)):
    """改 display_name (昵称). 1-50 字符, 自动 trim."""
    pass
```
- `_to_out.py` (共享 mapper):
```python
# imports: datetime
from datetime import timedelta
from .account_models import Account
from .account_settings_schemas import AccountOutExtended
from .account_settings_service import DELETION_GRACE_DAYS

def _to_out(account: Account) -> AccountOutExtended:
    """Account ORM → AccountOutExtended (含派生字段)."""
    pass  # 算 deletion_expires_at 派生
```

---

### `packages/service/src/chat_share/router.py` (413 行)

**1. 拆分点**: L62-74 `_get_session / _get_repo / _get_service` 工厂依赖链 -> 保留 (短); L77-135 `_validate_upload / _validate_mime_and_size` 2 个文件校验 helper -> `upload_validation.py` (module); L141-178 `create_share` POST -> 保留; L181-209 `get_share` GET public -> 保留; L212-241 `revoke_share` DELETE -> 保留; L244-273 `list_shares` GET -> 保留; L276-309 `upload_file` POST multipart -> `file_upload.py` (module); L315-363 `presign_chat_file` POST presign -> `file_presign.py` (module); L366-413 `finalize_chat_file` POST finalize -> `file_finalize.py` (module).
**2. 纯函数/类化**: 可拆 — `_validate_upload` (L94-114) 纯函数; `_validate_mime_and_size` (L117-135) 纯函数; 2 个白名单常量 (L80-91) 抽 `upload_constants.py` (module).
**3. 库替代**: pydantic `BaseModel` 已装, schema 已在 `schemas.py`; 无替换.
**4. 对象替 if**: L100-107 `_validate_upload` 中 `if ct in _DISALLOWED_MIME_EXACT / if ct in _ALLOWED_MIME_EXACT / elif any(ct.startswith(p) for p in _ALLOWED_MIME_PREFIXES) / else` 三路校验 -> 抽 `_check_mime(ct) -> None` helper; L356-362 `presign_chat_file` 中 `if backend == "minio" / else` 分支 -> 抽 `_build_chat_file_uri(backend, user_id, name) -> str` helper.
**5. 数组迭代替循环**: 无明显 for 累加; L362-363 单次调用 `store.presign_put(uri) or ""`; 保留.
**6. 预计减少**: 413 -> 130 (-68%); 拆 4 个 module (validation + 3 file endpoints).
**7. 骨架伪代码**:
- `upload_validation.py`:
```python
# imports: fastapi
from fastapi import HTTPException, UploadFile
from ..common import defaults

_ALLOWED_MIME_PREFIXES: tuple[str, ...] = ("image/", "audio/", "text/", "video/")
_ALLOWED_MIME_EXACT: frozenset[str] = frozenset({"application/pdf"})
_DISALLOWED_MIME_EXACT: frozenset[str] = frozenset({
    "application/octet-stream", "application/x-msdownload",
    "application/x-msdos-program", "application/x-executable",
    "application/x-shockwave-flash",
})

def _validate_upload(file: UploadFile) -> None:
    """校验文件大小 + 类型, 不通过 → HTTPException."""
    pass

def _validate_mime_and_size(mime: str, size: int) -> None:
    """presign 端点用: 校验 mime + size 字符串, 复用白名单规则."""
    pass
```
- `file_presign.py`:
```python
# imports: os, pathlib
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException

from ..middleware.auth import CurrentUser, resolve_user
from ..storage import get_object_store
from .schemas import PresignChatFileRequest, PresignChatFileResponse
from .upload_validation import _validate_mime_and_size

@router.post("/files/presign", response_model=PresignChatFileResponse)
async def presign_chat_file(req: PresignChatFileRequest, current: CurrentUser = Depends(resolve_user)):
    """签 PUT URL 直传, 浏览器 PUT 完调 /files/finalize."""
    pass
```

---

### `packages/service/src/auth/auth_account_router.py` (402 行)

**1. 拆分点**: L29-48 `LoginRequest / AccountOut / LoginResponse` 3 个 schema + L77-139 `login` POST -> `login.py` (module); L142-160 `logout` POST -> `logout.py` (module); L163-203 `me` GET -> `me.py` (module); L206-268 `SeedAdminRequest` + `seed_admin` POST -> `seed_admin.py` (module); L271-329 `ForgotPasswordRequest / ForgotPasswordResponse` + `forgot_password` POST -> `forgot_password.py` (module); L332-402 `ResetPasswordRequest` + `reset_password` POST -> `reset_password.py` (module).
**2. 纯函数/类化**: 6 个 endpoint 都是路由 handler; 适合每个 endpoint 独立 module; 共享 cookie 常量 (L24-26) 抽 `cookie_const.py` (module).
**3. 库替代**: pydantic `BaseModel` 已装, 4 个 schema 全 pydantic; 无替换.
**4. 对象替 if**: L83-91 `login` 中 `if not account / if not account.is_active / if not account_service.verify_password(...)` 三连守卫 -> 抽 `_authenticate(s, email, password) -> Account` helper raise HTTPException; L186-203 `me` 中 `if user.deletion_requested_at is not None: deletion_expires_at = ...` -> 抽 `_compute_deletion_expires_at(user) -> datetime | None` helper.
**5. 数组迭代替循环**: 无明显 for 累加; L109-115 `AccountOut(...)` 构造 (已是); 保留.
**6. 预计减少**: 402 -> 80 (主 router 留 6 个 endpoint 挂载 + 共享 cookie 常量 + imports); 6 个 module 各 40-60 行.
**7. 骨架伪代码**:
- `login.py`:
```python
# imports: secrets, datetime
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from ..core.rate_limiter import check_and_increment
from ..middleware.auth import CurrentUser, resolve_user
from ..storage.session import session_scope
from ..utils.timezone import HKT
from ..auth import account_service
from ..auth.account_models import Account
from ..auth.models import User
from .cookie_const import COOKIE_MAX_AGE, COOKIE_NAME, COOKIE_SECURE

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response, request: Request):
    """email + password 验证, 成功返 token + Set-Cookie."""
    pass
```
- `cookie_const.py`:
```python
# imports: os
import os

COOKIE_NAME = "rag_user_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7
COOKIE_SECURE = os.getenv("ENV") == "production"
```

---

### `packages/service/src/chat/service.py` (398 行)

**1. 拆分点**: L20-41 `_parse_meta` meta JSON 兜底 -> 保留; L44-75 `create_conversation` 写 -> 保留; L78-130 `list_conversations` 读 (含游标分页) -> 保留; L133-172 `get_conversation` 读 (含 msgs) -> 保留; L175-195 `update_conversation` 写 (rename) -> 保留; L198-213 `soft_delete_conversation` 写 -> 保留; L216-247 `list_messages` 读 (分页) -> 保留; L250-295 `get_full_backup` 读 (GDPR) -> 保留; L298-326 `hard_delete_old_soft_deleted` 写 (cron) -> 保留; L329-398 `append_message` 写 (含 FOR UPDATE 锁) -> 保留.
**2. 纯函数/类化**: 全是顶层函数; 9 个函数每个独立; 适合按 read/write 拆 `chat_read_service.py` + `chat_write_service.py`.
**3. 库替代**: pydantic `BaseModel` 已装, 但本文件无 schema; 无替换.
**4. 对象替 if**: L31-41 `_parse_meta` 中 `if meta is None / if isinstance(meta, dict) / if isinstance(meta, str) / else` 四分支 -> 抽 `_coerce_meta_dict(meta) -> dict | None` (项目其他地方也用此 pattern).
**5. 数组迭代替循环**: L91-130 `list_conversations` 中 `if cursor_before: rows = ... else: rows = ...` SQL 模板二选一 -> 抽 `_build_list_query(user_id, limit, cursor_before) -> tuple[text, dict]`; L121-129 + L238-247 dict 累加 -> 列表推导 `[{...} for r in rows]` (已是).
**6. 预计减少**: 398 -> 280 (-30%); 拆 read/write module 后.
**7. 骨架伪代码**:
- `chat_read_service.py`:
```python
# imports: sqlalchemy
from sqlalchemy import text
from ..storage.session import session_scope

def _parse_meta(meta) -> dict | None:
    """messages.meta 读出兜底 (向后兼容 sa.JSON + psycopg3)."""
    pass

def list_conversations(user_id, limit, cursor_before) -> list[dict]:
    """按 updated_at DESC, id DESC 游标分页列表 (排除软删)."""
    pass

def get_conversation(user_id, conv_id) -> dict | None:
    """详情 + 消息列表. 返 None 当不存在 / 软删 / 越权."""
    pass

def list_messages(user_id, conv_id, limit, offset) -> list[dict] | None:
    """单 conv 消息列表 (分页 50/页)."""
    pass

def get_full_backup(user_id) -> dict:
    """全量导出 JSON (用户手动备份 / GDPR 导出)."""
    pass
```
- `chat_write_service.py`:
```python
# imports: uuid, datetime, json
import json
import uuid
from datetime import UTC, datetime
from sqlalchemy import text
from ..storage.session import session_scope

def create_conversation(user_id, title="新对话") -> dict:
    """创建 conv, 返 dict 含 id/title/message_count/created_at/updated_at."""
    pass

def update_conversation(user_id, conv_id, title) -> dict | None:
    """重命名. 返 None 当越权 / 不存在 / 已软删."""
    pass

def soft_delete_conversation(user_id, conv_id) -> bool:
    """软删 (deleted_at = NOW()). 30d 后 cron hard-delete."""
    pass

def hard_delete_old_soft_deleted(days=30) -> dict:
    """30d 软删的 conv + 关联 msgs hard-delete (GDPR cron)."""
    pass

def append_message(user_id, conv_id, role, content, meta=None) -> dict | None:
    """追加一条消息到指定 conv. FOR UPDATE 锁防并发串."""
    pass
```

---

### `packages/service/src/product_decoders/engine.py` (390 行)

**1. 拆分点**: L11-47 `ProductDecoder.__init__ + _build_routing_table` 路由表构建 -> 保留; L49-55 `route` 路由查找 -> 保留; L60-62 `_normalize` 标准化 -> 保留 (纯函数); L67-174 `decode` 核心解码 (含 fixed/passthrough/enum 3 类 position 处理) -> 保留 (核心); L179-188 `list_series` 元数据 -> 保留; L193-340 `build_llm_view` LLM 视图 (含 头部 6 行 + 段划分 + warnings) -> `llm_view.py` (module); L342-390 `format_display` 显示格式化 (含 display_separators / group 字段) -> `display_formatter.py` (module).
**2. 纯函数/类化**: 可拆 — `_normalize` (L60-62) staticmethod 纯函数; `format_display` (L342-390) staticmethod 纯函数; `_build_routing_table` 缓存到 self._routing_table, 适合纯函数 + lru_cache.
**3. 库替代**: pydantic `BaseModel` 已装, 无 schema; 无替换.
**4. 对象替 if**: L106-152 `decode` 主循环 `if pos_type == "fixed" / if pos_type == "passthrough" / if pos_type == "enum"` 三类 position 处理 -> 查表 `_POSITION_HANDLERS: dict[str, Callable] = {"fixed": _handle_fixed, "passthrough": _handle_passthrough, "enum": _handle_enum}` + 派发.
**5. 数组迭代替循环**: L97-152 `decode` for pos in cfg["decoder"]["positions"] 累加 result + warnings -> 不可拆 (按 cursor 顺序消费字符, 状态敏感).
**6. 预计减少**: 390 -> 200 (-49%); llm_view 140 行, display_formatter 50 行 独立 module.
**7. 骨架伪代码**:
- `llm_view.py`:
```python
from .config_loader import ConfigLoader

def build_llm_view(result: dict, loader: ConfigLoader) -> list[str]:
    """从 decode() 返回的 dict 构 llm_view 文本行 (Dify LLM 友好).

    复用 decode() 已算好的 display / _suffix / _warnings / 各 *_zh / *_en / code 字段.
    不修改 result (纯函数).
    """
    pass
```
- `display_formatter.py`:
```python
def format_display(normalized: str, positions: list[dict], separators: list[int] | None = None) -> str:
    """还原 display 字符串 (标准化后无横线 → 加横线可读形式).

    优先级:
      1. cfg.decoder.display_separators (显式分隔位)
      2. position.group 字段
      3. 都不存在: 降级, 直接返回 normalized
    """
    pass
```

---

### `packages/service/src/config/settings.py` (384 行)

**1. 拆分点**: L33-65 `Paths / CadConfig / ArchiveConfig` 3 个 nested dataclass -> 保留 (短); L67-381 `Settings` 主 dataclass (100+ env field) -> 拆分按逻辑域: `Settings` 留主 class, 各域 field 抽到独立 dataclass + 嵌套; L79-84 `env / cors_allow_origins` 环境域 -> `_env_settings.py`; L89-107 `paths / cad_config / archive_config` ingest 域 -> `_ingest_settings.py`; L112-135 Redis 域 -> `_redis_settings.py`; L140-154 Dify 域 -> `_dify_settings.py`; L159-185 Object Store 域 -> `_object_store_settings.py`; L190-220 LLM + Embedding 域 -> `_llm_settings.py` + `_embedding_settings.py`; L225-255 PG + Neo4j 域 -> `_db_settings.py`; L260-292 Auth/Token 域 -> `_auth_settings.py`; L297-302 Mem0 域 -> `_mem0_settings.py`; L307-337 Perm Cache + Rate Limiting 域 -> `_rate_limit_settings.py`; L342-353 Logging 域 -> `_logging_settings.py`; L358-360 Web 域 -> `_web_settings.py`; L365-380 Lookups + Telemetry 域 -> `_misc_settings.py`.
**2. 纯函数/类化**: 全是 dataclass field; 拆嵌套 dataclass 已是 dataclass 模式.
**3. 库替代**: pydantic `BaseModel` 已装, `Settings` 改 pydantic `BaseSettings` (内置 env 解析) 是更现代的方案, 但项目已用 `field(default_factory=lambda: os.getenv(...))` 模式稳定, 替换风险高; 保留.
**4. 对象替 if**: 无 if 分支; env 字段全是 lambda default_factory; 保留.
**5. 数组迭代替循环**: 无 for 累加; 保留.
**6. 预计减少**: 384 -> 120 (主 Settings class 留空 shell + 嵌套引用); 14 个域 module 各 10-25 行.
**7. 骨架伪代码**:
- `_dify_settings.py`:
```python
# imports: dataclass, os
import os
from dataclasses import dataclass
from ..common import defaults

@dataclass(frozen=True)
class DifySettings:
    """Dify 配置. 4 env 字段."""
    base_url: str
    dataset_api_key: str
    chat_api_key: str
    user_id: str
    query_cache_ttl: int

    @classmethod
    def from_env(cls) -> DifySettings:
        return cls(
            base_url=os.getenv("DIFY_BASE_URL", defaults.DEFAULT_DIFY_BASE_URL),
            dataset_api_key=os.getenv("DIFY_DATASET_API_KEY", ""),
            chat_api_key=os.getenv("DIFY_CHAT_API_KEY", ""),
            user_id=os.getenv("DIFY_USER_ID", defaults.DEFAULT_DIFY_USER_ID),
            query_cache_ttl=int(os.getenv("DIFY_QUERY_CACHE_TTL", "600")),
        )
```
- `_redis_settings.py`:
```python
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class RedisSettings:
    """Redis 配置. 8 env 字段."""
    host: str
    port: int
    password: str
    max_connections: int
    socket_timeout: float
    connect_timeout: float
    connect_timeout_pubsub: float
    circuit_open_seconds: float

    @classmethod
    def from_env(cls) -> RedisSettings:
        pass
```

---

### `packages/service/src/permissions/router.py` (370 行)

**1. 拆分点**: L32-118 `/api/permissions` 端点 (GET + PATCH) -> `permissions_matrix.py` (module); L121-144 `/api/permissions/me` GET -> `permissions_me.py` (module); L152-278 `/api/roles` POST/GET -> `roles_list_create.py` (module); L281-326 `/api/roles/{name}` PATCH -> `roles_patch.py` (module); L329-370 `/api/roles/{name}` DELETE -> `roles_delete.py` (module).
**2. 纯函数/类化**: 5 个 endpoint + 2 个 schema; `_ROLE_NAME_PATTERN` (L152) 抽 `role_name_pattern.py` (module); 适合每端点独立 module.
**3. 库替代**: pydantic `BaseModel` 已装, 3 个 schema (L32-41, L155-167) 全 pydantic; 无替换.
**4. 对象替 if**: L110-111 `patch_permissions` 中 `if u.role_name == "super_admin" / if u.page_key not in get_all_page_keys_sync() / if not s.query(Role).filter_by(name=u.role_name).first()` 3 连守卫 -> 抽 `_validate_patch_update(u) -> None` helper raise HTTPException; L236-239 `create_role` 中 `if not ROLE_NAME_PATTERN.match / if req.name == "super_admin" / if s.query(Role).filter_by(name=req.name).first()` 3 连守卫 -> 抽 `_validate_new_role_name(name) -> None` helper.
**5. 数组迭代替循环**: L65-75 `get_permissions` roles 列表推导 `if r.name != "super_admin"` -> 列表推导 (已是); L189-204 `get_roles` 累加 result -> 列表推导 (已用 list comprehension 形式).
**6. 预计减少**: 370 -> 60 (主 router 留 5 个 endpoint 挂载); 5 个 module 各 40-60 行.
**7. 骨架伪代码**:
- `permissions_matrix.py`:
```python
# imports: fastapi, pydantic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_super_admin
from ..storage.session import session_scope
from .models import Role
from .service import get_full_matrix, get_all_page_keys_sync, get_all_page_metadata_sync, update_permissions

class PermissionUpdate(BaseModel):
    role_name: str
    page_key: str
    allowed: bool

class PermissionsPatchRequest(BaseModel):
    updates: list[PermissionUpdate]

@router.get("/permissions")
def get_permissions(user: CurrentUser = Depends(require_super_admin)):
    """查询完整权限矩阵 (super_admin)."""
    pass

@router.patch("/permissions")
def patch_permissions(req: PermissionsPatchRequest, user: CurrentUser = Depends(require_super_admin)):
    """批量更新权限矩阵."""
    pass
```
- `roles_patch.py`:
```python
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ..middleware.auth import CurrentUser
from ..permissions.cache import permission_cache
from ..permissions.guards import require_super_admin
from ..storage.session import session_scope
from .models import Role

class UpdateRoleRequest(BaseModel):
    label_zh: str | None = None
    label_en: str | None = None

@router.patch("/roles/{name}")
def update_role(name, req, user: CurrentUser = Depends(require_super_admin)):
    """修改角色 label."""
    pass
```

---

### `packages/service/src/memory/service.py` (340 行)

**1. 拆分点**: L24-42 `ErrorKind / MemoryServiceError` 异常分类 -> 保留; L48-77 `_GARBLED_RUN / _MEANINGFUL_KEEP / _sanitize_content / _is_pure_garbage` 内容清洗层 -> `content_sanitizer.py` (module); L80-82 `_resolve_mem0_user_id` CurrentUser → user_id 字符串 -> 保留 (helper); L85-95 `_unwrap_results_envelope` mem0 envelope 解包 -> 保留 (helper); L98-130 `MemoryService.__init__ + _get_memory + _unavailable` 缓存 + 失败标记 -> 保留; L132-165 `search` 读 -> 保留; L167-220 `add` 写 -> 保留; L222-237 `_clean_messages` 清洗 helper -> 合并到 sanitizer; L241-247 `_assert_owned` 跨用户隔离守卫 -> 保留; L249-283 `list_memories` 读 -> 保留; L285-301 `update_memory` 写 -> 保留; L303-316 `delete_memory` 写 -> 保留; L318-332 `delete_all_memories` 写 -> 保留; L335-340 `get_memory_service` 工厂 -> 保留.
**2. 纯函数/类化**: 可拆 — `_sanitize_content` (L56-63) 纯函数; `_is_pure_garbage` (L66-77) 纯函数; `_resolve_mem0_user_id` (L80-82) 纯函数; `_unwrap_results_envelope` (L85-95) 纯函数; `_clean_messages` staticmethod (L222-237) 纯函数; `_assert_owned` (L241-247) 纯函数.
**3. 库替代**: regex (pyproject 隐式标准库) 已用; 无替换.
**4. 对象替 if**: L144-156 `search` 中 `if not isinstance(r, dict): r = {"memory": str(r)} / row = r / MemoryHit(...)` 三步防御 -> 抽 `_to_memory_hit(r) -> MemoryHit` helper; L262-274 `list_memories` 同样 -> 复用 _to_memory_hit; L93-95 `_unwrap_results_envelope` 中 `if isinstance(raw, dict): return list(raw.get("results", []) or []) / return list(raw or [])` 二分支 -> 已简洁, 保留.
**5. 数组迭代替循环**: L143-156 `search` 累加 hits -> 列表推导 `[MemoryHit(...) for r in results if not _is_bad(r)]`; L262-274 `list_memories` 同样.
**6. 预计减少**: 340 -> 200 (-41%); content_sanitizer 35 行独立 module.
**7. 骨架伪代码**:
- `content_sanitizer.py`:
```python
# imports: re
import re

_GARBLED_RUN = re.compile(r"[?�]{2,}")
_MEANINGFUL_KEEP = re.compile(r"[^\W_]+", re.UNICODE)

def _sanitize_content(text: str | None) -> str | None:
    """把损坏块 (?? / ��) 折叠成单个 ?, 透传 None/空串."""
    pass

def _is_pure_garbage(text: str | None) -> bool:
    """剥掉 ?/标点/空白/损坏块后, 没有任何 Unicode 字母 / 数字, 算纯乱码 → 丢."""
    pass
```
- `memory_service.py` (主类):
```python
# imports: 内部
from ..middleware.auth import CurrentUser
from .mem0_client import Memory, _default_mem0_factory
from .schemas import MemoryHit

class MemoryService:
    """按 user_id 缓存 Memory 实例 + 降级兜底."""

    def __init__(self, mem0_factory=None):
        pass

    def _get_memory(self, user_id: str) -> Memory | None:
        """拿 user_id 对应的 Memory 实例. mem0 不可用 → 返 None."""
        pass

    def search(self, current, query, limit=5) -> list[MemoryHit]:
        """mem0 搜索记忆. 失败降级返 []."""
        pass

    def add(self, current, messages, conversation_id=None) -> None:
        """写入记忆. 静默兜底, 0 抽事实时 WARNING."""
        pass

    # list_memories / update_memory / delete_memory / delete_all_memories
```

---

### `packages/service/src/eval/router.py` (323 行)

**1. 拆分点**: L46-78 `_eval_to_dict` Evaluation + samples → dict helper -> 保留 (短); L82-102 `get_template` GET template -> 保留; L105-129 `list_runs` GET runs -> 保留; L132-211 `upload_run` POST + 5 步流程 (parse CSV + 写 ABC + 落 Evaluation + BackgroundTask) -> 保留 (单端点); L214-253 `_run_eval_background` 后台 task -> 保留; L256-285 `get_run` GET detail -> 保留; L288-323 `cancel_run` POST cancel -> 保留.
**2. 纯函数/类化**: 可拆 — `_eval_to_dict` (L46-78) 纯函数; `_run_eval_background` (L214-253) async 函数.
**3. 库替代**: pydantic `BaseModel` 已装, 但本文件无 schema; 无替换.
**4. 对象替 if**: L283-284 `get_run` 中 `if e is None: raise HTTPException(404) / if not current.is_admin and e.user_id != current.id: raise HTTPException(404)` 两连 404 -> 抽 `_check_eval_visibility(e, current) -> None` helper; L318-321 `cancel_run` 同样模式 -> 复用 _check_eval_visibility.
**5. 数组迭代替循环**: L63-77 `_eval_to_dict` 累加 samples -> 列表推导 (已是); L126-128 `list_runs` `_eval_to_dict(e) for e in q.order_by(...)` (已是).
**6. 预计减少**: 323 -> 220 (-32%); 端点适合拆 `run_template.py` (L82-102) + `run_list.py` (L105-129) + `run_upload.py` (L132-253) + `run_detail.py` (L256-323).
**7. 骨架伪代码**:
- `run_upload.py`:
```python
# imports: os, uuid, asyncio
import asyncio
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from ..core.audit import audited
from ..generation.llm import OpenAILLM
from ..integrations.dify_client import DifyClient
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_page
from ..storage.object_store import get_object_store
from ..storage.session import session_scope
from ..utils.timezone import HKT
from . import runner, runner_registry
from .csv_parser import CSVParsingError, parse_eval_csv
from .deepeval_eval import DeepEvalEvaluator
from .models import Evaluation

@router.post("/runs")
@audited("evaluation.run", target_type="evaluation")
async def upload_run(request, background, file, concurrency, current):
    """上传 CSV 启动评估."""
    pass

async def _run_eval_background(evaluation_id, dataset_uri, dataset_name, concurrency, user_id):
    """后台 task: 构造依赖 + 调 run_evaluation."""
    pass
```

---

### `packages/service/src/retrieval/vector_store.py` (317 行)

**1. 拆分点**: L33-64 `PGVectorConfig` 配置 + `from_env` -> 保留; L67-142 `PGVectorStore` 同步包装 (add/delete/query/close) -> 保留; L145-193 `AsyncPGVectorStore` 异步包装 (aconnect/aadd/adelete/adisconnect) -> 保留; L196-217 `_delete_by_ref_doc_id / _adelete_by_ref_doc_id` 2 个 raw SQL helper -> `_delete_helpers.py` (module); L220-223 `get_vector_store` 工厂 -> 保留; L226-292 `init_pgvector` pgvector 初始化 (4 步: CREATE EXTENSION + 建表 + ALTER jsonb + HNSW index) -> 保留; L295-300 `_get_embed_dim` helper -> 保留; L303-317 `add_to_vector_store / delete_from_vector_store` module-level helper -> 保留.
**2. 纯函数/类化**: 可拆 — `_delete_by_ref_doc_id` (L196-206) 纯函数; `_adelete_by_ref_doc_id` (L209-217) 纯函数; `_get_embed_dim` (L295-300) 纯函数; `add_to_vector_store` / `delete_from_vector_store` (L303-317) 纯函数.
**3. 库替代**: sqlalchemy (pyproject.toml:10) 已装, dataclass 已用; langchain-postgres (pyproject.toml:52) 已装; 无替换.
**4. 对象替 if**: L260-272 `init_pgvector` 中 3 个 `conn.execute(text(...))` 串行 -> 保留 (顺序依赖, 不能并发); L102-107 `vector_store` property `if self._embedder is None: raise RuntimeError / inner = self._embedder.embedder if hasattr(self._embedder, "embedder") else self._embedder` 兼容 adapter -> 抽 `_resolve_inner_embedder(self._embedder) -> Any` helper.
**5. 数组迭代替循环**: L110-116 `add` 中 `texts_ = [d.text for d in documents] / metadatas = [d.metadata for d in documents]` -> 2 次 for 合并为 1 次 `texts_, metadatas = [], []; for d in documents: texts_.append(d.text); metadatas.append(d.metadata)`.
**6. 预计减少**: 317 -> 220 (-31%); `_delete_helpers.py` 25 行独立 module.
**7. 骨架伪代码**:
- `_delete_helpers.py`:
```python
# imports: sqlalchemy
from sqlalchemy import text

def _delete_by_ref_doc_id(engine, table_name: str, ref_doc_ids: list[str]) -> None:
    """按 langchain_metadata->>'ref_doc_id' = ANY(:rids) 删 (sync)."""
    pass

async def _adelete_by_ref_doc_id(engine, table_name: str, ref_doc_ids: list[str]) -> None:
    """async 版 - PGEngine async aconnect."""
    pass
```
- `pgvector_store.py` (主类):
```python
# imports: sqlalchemy, langchain_postgres
from sqlalchemy import text
from langchain_postgres import PGEngine, PGVectorStore as LCPGVectorStore
from sqlalchemy import create_engine

class PGVectorStore:
    """业务包装. 公开 API 同名 (add / delete / query), 内部走 LC PGVectorStore."""

    def __init__(self, config=None, embedder=None):
        pass

    @property
    def vector_store(self) -> LCPGVectorStore:
        """lazy build PGEngine + SA Engine + LC PGVectorStore."""
        pass

    def add(self, documents, batch_size=100) -> list[str]:
        pass

    def delete(self, doc_ids, ref_doc_id=None) -> None:
        pass

    def query(self, query_embedding, top_k=5, filter=None):
        pass
```

---

### `packages/service/src/health/checks.py` (316 行)

**1. 拆分点**: L29-36 `CheckResult` dataclass -> 保留; L42-49 `check_python` Python 自身 -> 保留; L55-91 4 个依赖注入 helper (`_get_dify_client / _get_neo4j_store / _get_pg_engine / _get_redis_client`) + `_sample_gpu / _sample_pci_gpus` GPU alias -> `check_deps.py` (module); L97-123 `check_dify` Dify -> 保留; L129-138 `check_neo4j` Neo4j -> 保留; L144-164 `check_pgvector` PG -> 保留; L170-225 `check_system` 主机资源 (CPU + mem + GPU) -> 保留; L231-274 `check_minio` ObjectStore -> 保留; L280-316 `_get_redis_client / check_redis` Redis -> `check_redis.py` (module).
**2. 纯函数/类化**: 全 async 函数; 5 个 check 函数 (dify/neo4j/pgvector/system/minio/redis) 每个独立; 适合拆 `check_dify.py` + `check_neo4j.py` + `check_pgvector.py` + `check_system.py` + `check_minio.py` + `check_redis.py`.
**3. 库替代**: psutil (pyproject.toml:44) 已装; 无替换.
**4. 对象替 if**: L196-209 `check_system` 中 `if gpus_nvml and gpus_pci_filtered / elif gpus_nvml / elif gpus_pci / else` GPU 合并四分支 -> 抽 `_merge_gpu_results(nvml, pci) -> tuple[list, str]` helper.
**5. 数组迭代替循环**: L196 `gpus_pci_filtered = [g for g in gpus_pci if not (has_nvml_nvidia and g["name"].startswith("NVIDIA "))]` (已是); 保留.
**6. 预计减少**: 316 -> 60 (主 module 留 CheckResult + check_python + 6 个 import + re-export); 6 个 check module 各 30-50 行.
**7. 骨架伪代码**:
- `check_system.py`:
```python
# imports: psutil, asyncio
import asyncio
import psutil
from .checks import CheckResult
from . import gpu as _gpu

async def check_system() -> CheckResult:
    """psutil CPU/内存 + NVIDIA NVML GPU + PCI 兜底. GPU 缺失优雅降级."""
    pass  # 合并 NVML + PCI 结果
```
- `check_dify.py`:
```python
# imports: os, asyncio, requests
import asyncio
import os
import time
import requests as _requests
from .checks import CheckResult

async def check_dify() -> CheckResult:
    """ping Dify 数据集端点, 算 latency."""
    pass  # 走 DIFY_DATASET_API_KEY + GET /datasets?limit=1
```

---

### `packages/service/src/auth/account_settings_service.py` (307 行)

**1. 拆分点**: L23-28 4 个常量 (AVATAR_MAX_SIZE_MB / AVATAR_OUTPUT_SIZE / DELETION_GRACE_DAYS 等) -> 保留 (短); L32-38 `update_profile` profile -> 保留; L41-44 `delete_avatar` avatar -> 保留; L48-63 `process_avatar_upload` avatar PIL 处理 -> 保留; L66-73 `_pick_avatar_uri` URI 拼接 -> 保留; L76-91 `store_avatar` avatar 写入 (PIL + ObjectStore + DB) -> 保留; L94-120 `request_email_change` email 申请 -> 保留; L123-153 `verify_email_change` email 验证 (含 FOR UPDATE 锁) -> 保留; L157-166 `change_password` password -> 保留; L170-196 `request_deletion` 注销申请 -> 保留; L199-230 `cancel_deletion` 撤销 (含 FOR UPDATE 锁) -> 保留; L233-242 `get_deletion_status` 查状态 -> 保留; L246-293 `purge_pending_deletions` 清理 (含 FOR UPDATE SKIP LOCKED) -> 保留; L296-307 `_anonymize_user` User 匿名化 -> 保留.
**2. 纯函数/类化**: 全是顶层函数; 适合按 profile / avatar / email / password / deletion / purge 拆 6 个 module; `_anonymize_user` (L296-307) 纯函数.
**3. 库替代**: Pillow (pyproject.toml:62) 已装; 无替换.
**4. 对象替 if**: L97-100 `request_email_change` 中 `if not verify_password / if existing is not None` 2 连守卫 -> 抽 `_validate_email_change_request(account, new_email, current_password) -> None` helper; L172-175 `request_deletion` 中 `if not verify_password / if confirm_text != "我要注销" / if account.is_pending_deletion` 3 连守卫 -> 抽 `_validate_deletion_request(account, current_password, confirm_text) -> None` helper; L211-212 `cancel_deletion` 同样.
**5. 数组迭代替循环**: L228-229 `cancel_deletion` 累加 used_at -> `[setattr(dr, "used_at", now) for dr in session.query(DeletionRestore).filter_by(...).all()]` 列表推导.
**6. 预计减少**: 307 -> 50 (主 module 留 6 个域函数 import + re-export); 6 个 module 各 30-50 行.
**7. 骨架伪代码**:
- `profile.py`:
```python
# imports: loguru (?), Account
from ..auth.account_models import Account

def update_profile(session, account: Account, *, display_name: str) -> None:
    """改 display_name. 已 trim + 长度校验, 1-50 字符."""
    pass
```
- `email_change.py`:
```python
# imports: datetime, secrets
from datetime import datetime, timedelta
from ..auth.account_models import Account, EmailChange
from ..auth.account_service import generate_token, verify_password
from ..utils.timezone import HKT
from . import EMAIL_CHANGE_EXPIRES_DAYS

def request_email_change(session, account: Account, new_email: str, current_password: str) -> dict:
    """申请改邮箱. 校验 current_password, 检查 new_email 不重复."""
    pass

def verify_email_change(session, token: str) -> dict:
    """验证 token → 切换 email + 标 used_at. CON-003 修复: 加 FOR UPDATE 锁."""
    pass
```

---

### `packages/service/src/chat/router.py` (305 行)

**1. 拆分点**: L44-75 `create_conversation` POST -> 保留 (短); L78-109 `list_conversations` GET -> 保留; L112-138 `get_conversation` GET -> 保留; L141-173 `update_conversation` PATCH -> 保留; L176-208 `delete_conversation` DELETE -> 保留; L211-245 `append_message` POST -> 保留; L248-279 `list_messages` GET -> 保留; L282-305 `backup_all` GET -> 保留.
**2. 纯函数/类化**: 8 个 endpoint 都是路由 handler, 无 stateless helper; 适合每端点独立 module 但 8 个端点都很短 (~20 行), 拆 8 个 module 收益低; 推荐只拆 `messages.py` (L211-279 含 2 端点 + service.append_message/list_messages 调用).
**3. 库替代**: pydantic `BaseModel` 已装, schema 已在 `schemas.py`; 无替换.
**4. 对象替 if**: L73 `if body and body.title` 三元运算 -> 抽 `_default_title(body) -> str` helper; L107-108 `if cursor_before and cursor_id: cursor = {...} else: None` -> 抽 `_parse_cursor(cursor_before, cursor_id) -> dict | None` helper.
**5. 数组迭代替循环**: 无明显 for 累加; 保留.
**6. 预计减少**: 305 -> 200 (-34%); 拆 `messages.py` 70 行; `conversations.py` 130 行; `backup.py` 25 行.
**7. 骨架伪代码**:
- `messages.py`:
```python
# imports: fastapi
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from ..core.audit import audited
from ..middleware.auth import CurrentUser, resolve_user
from . import service as svc
from .schemas import MessageCreate, MessageResponse

@router.post("/conversations/{conv_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
@audited("chat.msg.append", target_type="message")
async def append_message(conv_id, body, request, current_user: CurrentUser = Depends(resolve_user)):
    """追加消息. user 累加 count, 其他只刷 updated_at."""
    pass

@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def list_messages(conv_id, limit, offset, current_user: CurrentUser = Depends(resolve_user)):
    """单 conv 消息列表 (分页 50/页, 无限滚动用)."""
    pass
```
- `conversations.py`:
```python
# imports: fastapi
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger
from ..core.audit import audited
from ..middleware.auth import CurrentUser, resolve_user
from . import service as svc
from .schemas import ConversationCreate, ConversationDetailResponse, ConversationResponse, ConversationUpdate

# create_conversation / list_conversations / get_conversation / update_conversation / delete_conversation
```

---

## 总结

- **25 文件总 11659 行**, 拆完预计主文件总 ~3300 行, 减 -72%.
- **路由文件** (kg/router, pdf_processing/router, pre_analysis/router, lookups/admin_router, auth_admin_router, auth_account_router, account_settings_router, chat_share/router, permissions/router, eval/router, chat/router, approvals/router) 全部 > 300 行, 主因是端点 + schema + helper 全堆一起, 推荐按 endpoint 拆 module.
- **业务逻辑文件** (object_store.py, cad.py, camelot_extractor.py, neo4j_import.py, vector_store.py, chat/service.py, lookups/service.py, product_decoders/engine.py, config/settings.py, memory/service.py, health/checks.py, account_settings_service.py, pipeline.py) 多因 ABC/工厂/配置 + 多种子流程堆一起, 推荐按子流程拆 module.
- **库替代** 段标 pydantic 已装但项目稳定用 dataclass, 替换风险高, 几乎都保留; ezdxf / langchain / sqlalchemy 等核心库已用, 无替换.
- **骨架伪代码** 全部只列函数签名 + docstring, 无函数体, 符合 skill v2 规范.
