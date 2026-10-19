# Oversize Files Audit (2026-07-10) — 全项目 >300 行文件扫描

> Skill: `oversize-files-audit` v2 (7 段格式 + 库依赖验证 + 骨架伪代码 + verifier 反驳)
> 扫描日期: 2026-07-10
> 文件数: **42** (18669 行总)
> verifier 阶段: **42 验证** (27 通过 / 15 反驳)
> 输出目录: `docs/audit/2026-07-10/oversize-files-audit/`

## 顶部汇总表 (按行数降序)

| # | 路径 | 行数 | 语种 | verified | confidence | 拆后目标 |
|---|---|---|---|---|---|---|
| 1 | `kg/router.py` | 1040 | PY | [X] | high | ~280 |
| 2 | `ingest/pre_analysis/table_extractors/camelot_extractor.py` | 999 | PY | [OK] | high | ~200 |
| 3 | `ingest/pdf_processing/router.py` | 743 | PY | [OK] | high | ~220 |
| 4 | `storage/object_store.py` | 598 | PY | [X] | high | ~100 |
| 5 | `lib/api/pre-analysis.ts` | 585 | TS | [X] | high | ~? |
| 6 | `ingest/pre_analysis/router.py` | 568 | PY | [OK] | high | ~80 |
| 7 | `lookups/admin_router.py` | 562 | PY | [OK] | high | ~80 |
| 8 | `ingest/pdf_processing/converters/cad.py` | 512 | PY | [X] | medium | ~130 |
| 9 | `lib/api/knowledge.ts` | 502 | TS | [X] | high | ~? |
| 10 | `packages/service/scripts/neo4j_import.py` | 499 | PY | [X] | high | ~180 |
| 11 | `...cale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` | 479 | TSX | [X] | high | ~? |
| 12 | `auth/auth_admin_router.py` | 464 | PY | [OK] | high | ~80 |
| 13 | `approvals/router.py` | 459 | PY | [OK] | high | ~280 |
| 14 | `lookups/service.py` | 450 | PY | [OK] | high | ~280 |
| 15 | `lib/date.ts` | 450 | TS | [OK] | high | ~? |
| 16 | `ingest/pdf_processing/pipeline.py` | 448 | PY | [X] | high | ~280 |
| 17 | `app/[locale]/admin/users/_components/admin-users-table.tsx` | 438 | TSX | [OK] | high | ~? |
| 18 | `app/[locale]/_actions/account.ts` | 435 | TS | [X] | medium | ~7 |
| 19 | `auth/account_settings_router.py` | 424 | PY | [OK] | high | ~50 |
| 20 | `app/[locale]/_actions/account-settings.ts` | 418 | TS | [OK] | high | ~5 |
| 21 | `chat_share/router.py` | 413 | PY | [OK] | high | ~130 |
| 22 | `auth/auth_account_router.py` | 402 | PY | [OK] | high | ~80 |
| 23 | `...analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx` | 400 | TSX | [OK] | high | ~? |
| 24 | `chat/service.py` | 398 | PY | [OK] | high | ~280 |
| 25 | `product_decoders/engine.py` | 390 | PY | [OK] | high | ~200 |
| 26 | `config/settings.py` | 384 | PY | [X] | high | ~120 |
| 27 | `components/chat/memory-management-dialog.tsx` | 378 | TSX | [X] | high | ~? |
| 28 | `permissions/router.py` | 370 | PY | [OK] | high | ~60 |
| 29 | `memory/service.py` | 340 | PY | [OK] | high | ~200 |
| 30 | `app/[locale]/admin/dicts/_components/admin-dicts-client.tsx` | 334 | TSX | [OK] | high | ~? |
| 31 | `app/[locale]/knowledge/triples/_components/triples-form.tsx` | 331 | TSX | [OK] | high | ~? |
| 32 | `lib/chat/use-chat-state.ts` | 331 | TS | [OK] | high | ~? |
| 33 | `eval/router.py` | 323 | PY | [OK] | high | ~220 |
| 34 | `components/theme-provider.tsx` | 322 | TSX | [OK] | high | ~? |
| 35 | `retrieval/vector_store.py` | 317 | PY | [X] | high | ~220 |
| 36 | `health/checks.py` | 316 | PY | [OK] | high | ~60 |
| 37 | `app/[locale]/decode/page.tsx` | 312 | TSX | [OK] | high | ~? |
| 38 | `app/[locale]/_actions/knowledge.ts` | 311 | TS | [X] | high | ~5 |
| 39 | `components/common/table/data-table.tsx` | 308 | TSX | [X] | high | ~? |
| 40 | `auth/account_settings_service.py` | 307 | PY | [X] | high | ~50 |
| 41 | `chat/router.py` | 305 | PY | [OK] | medium | ~200 |
| 42 | `app/[locale]/output/[task_id]/_components/task-detail-client.tsx` | 304 | TSX | [OK] | medium | ~? |

## 关键发现

- **3 个 agent 派发**: A1 Python (25 py, 11659 行), A2 TS Page (13 tsx, 4867 行), A3 TS Hook/Util (4 ts, 1868 行)
- **42 个 verifier 派发**: 27 通过, 15 反驳
- **refuted 集中在"行号错"+"reduction 虚高"**: kg_router (line numbers off, -73% → -8%), object_store (598→100 是误导), config/settings.py (拆分破坏 lazy reload 契约), account_settings_service.py (拆分破坏 8 测试 mock 路径)
- **库基线 (已装, 无新增安装需求)**: pyproject.toml 装 pydantic/sqlalchemy/fastapi/loguru/camelot-py/ezdxf 等; package.json 装 es-toolkit/react-use/zod/@js-temporal/dexie/sonner 等

## 按文件 7 段详情 (含 verifier 反驳标记)

### `packages/service/src/kg/router.py` (1040 行) — **REFUTED**

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

**verified**: False
**confidence**: high
**refuted_reason**: KG router: 拆点行号错 (L90-181 错位). 1040→280 (-73%) 虚高: 5 个新模块各加 ~25 行 boilerplate, 实际拆完总行数 ~1060 行不降反升. 跨段共享 _audit_store / _task_store / _REPO_ROOT 3 个 singleton 拆 sub-module 时每个新文件都要 re-import 或改用 facade, 引入耦合. L124-134 已用 sum(...), finding 误说累加可改 sum; L597 frozenset 跟 tuple 同长度; L615-636 if 替 dict-comp 不可行. 拆分有助可读性, 但 reduction 73% 是凭空虚构, 实际预期 1040→950 (~ -8%) 才合理.

---

### `packages/service/src/ingest/pre_analysis/table_extractors/camelot_extractor.py` (999 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/ingest/pdf_processing/router.py` (743 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/storage/object_store.py` (598 行) — **REFUTED**

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

**verified**: False
**confidence**: high
**refuted_reason**: object_store: 598→100 reduction 是误导, total LOC 保持 ~555. 文件已用 # ===== markers 干净分段, ABC + impls 分离好, factory 3 分支不值得 dict lookup. 拆 14-method ABC 跨 5 模块加 ~50 行 import boilerplate, 没减复杂度. boto3 lazy import 已做 (L301), 主要动机已解决.

---

### `packages/web/lib/api/pre-analysis.ts` (585 行) — **REFUTED**

**1. 拆分点**:
- L10-136 13 个 interface (Summary/OutputFile/TaskState/OverallStage/DetailStage/StageStatus/StageItem/StagesResponse/RetryResponse/TaskItem/TaskDetail/UploadResponse/ListResponse) -> `pre-analysis-types.ts` (~127 行)
- L138-146 `handleError` 内部 helper -> 已经在 lib/api/config.ts 里有, 复用 `handleFetchError` (lib/api/errors.ts) -> 删本地实现
- L148-176 `TableExtractionConfig` + `ChapterExtractionConfig` 2 config interface -> `pre-analysis-config.ts` (~30 行)
- L178-315 上传/列表/详情/下载/stages/retry 6 个 fetch wrapper (含 FormData / apiFetch) -> `pre-analysis-tasks.ts` (~138 行)
- L317-321 章节树常量 (CHAPTER_JSON_FILENAME / FLAG_CSV_FILENAME / ZERO / EMPTY_STRING / ROW_INDEX_BASE) -> 留 pre-analysis-types.ts 或 const/
- L322-327 数字/字符串兜底常量 (ZERO / EMPTY_STRING / ROW_INDEX_BASE) -> 用 const/index.ts 的 ZERO / 提取本地 const
- L329-403 `ChapterTreeNode` / `ChapterStructurePayload` / `FlaggedParagraphRow` 3 个 viewer interface -> `pre-analysis-viewer-types.ts` (~75 行)
- L405-480 `fetchPreAnalysisFile` + `getPreAnalysisChapterStructure` + `getPreAnalysisFlaggedParagraphs` 3 个 chapter/flag 解析 -> `pre-analysis-viewer.ts` (~75 行)
- L482-585 `TablePagesResponse` / `TablePageItem` / `TablePageResponse` 3 个 table interface + `parseTableFilename` + `getPreAnalysisTablePages` + `getPreAnalysisTablePage` -> `pre-analysis-tables.ts` (~104 行)

**2. 纯函数/hook 化**: 可拆
- `parseTableFilename` 已是 pure func (regex exec + 数值转换), 无副作用
- `getPreAnalysisFlaggedParagraphs` 内 `parsed.data.map(...)` 行转换可拆 `mapFlaggedRow(raw: Record<string, string>, idx: number): FlaggedParagraphRow` pure func, 13 个 `?? EMPTY_STRING` / `Number() ?? ZERO` 字段映射清晰
- `getPreAnalysisChapterStructure` 内 `if (!Array.isArray(parsed.chapters)) throw` 可拆 `assertChaptersArray(parsed: unknown): asserts parsed is ChapterStructurePayload`
- `handleError` 删本地, 复用 lib/api/errors.ts

**3. 库替代**: ✅
- es-toolkit `pick` 已装 (package.json:62) — 不适用本文件 (无字段 pick 场景)
- es-toolkit `omit` — 不适用
- react-use 已装 (package.json:72) — 不适用 (无 useAsyncFn / useMount 等 hook 需求)
- zod 已装 (package.json:80) — 可替手写 `if (!Array.isArray(parsed.chapters))` 类型守卫, 但本文件只 1 处断言, 引入 zod 收益低, 不强推
- 无 dayjs / moment — 本文件不用日期格式化

**4. 对象替 if**: 无
- L439-444 `if (!Array.isArray(parsed.chapters)) throw` — 单点断言, 不构成 if/else 链, 不可替 Map 查找
- L463-479 `parsed.data.map(...)` 内 13 字段全用 `?? EMPTY_STRING` / `Number(...) ?? ZERO` 默认值, 风格统一无 if/else 嵌套
- L540-547 `parseTableFilename` 内 `if (!match) throw` — 同上单点

**5. 数组迭代替循环**: 无
- L463-479 `parsed.data.map((raw, idx) => ({...}))` 已用 map, 不需换
- 无 for / forEach / while 显式循环

**6. 预计减少**: 585 -> ~150 (主文件, 仅留 facade re-export), 拆分后单文件最大 ~138 行 (-74%)

**7. 骨架伪代码**:

- `pre-analysis-types.ts`:
```ts
// imports: 只列需要的 import
export interface PreAnalysisSummary;
export interface PreAnalysisOutputFile;
export type PreAnalysisTaskState;
export type PreAnalysisOverallStage;
export type PreAnalysisDetailStage;
export type PreAnalysisStageStatus;
export interface PreAnalysisStageItem;
export interface PreAnalysisStagesResponse;
export interface PreAnalysisRetryResponse;
export interface PreAnalysisTaskItem;
export interface PreAnalysisTaskDetail;
export interface PreAnalysisUploadResponse;
export interface PreAnalysisListResponse;
```

- `pre-analysis-config.ts`:
```ts
export interface TableExtractionConfig;
export interface ChapterExtractionConfig;
```

- `pre-analysis-tasks.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";
import { handleFetchError } from "@/lib/api/errors";
import type { PreAnalysisTaskDetail, PreAnalysisTaskItem, ... } from "./pre-analysis-types";
import type { TableExtractionConfig, ChapterExtractionConfig } from "./pre-analysis-config";

export const preAnalysisUpload: (file: File, config?: TableExtractionConfig, chapterConfig?: ChapterExtractionConfig) => Promise<PreAnalysisUploadResponse>;
export const listPreAnalysisTasks: (params?: { limit?: number; offset?: number }) => Promise<PreAnalysisListResponse>;
export const getPreAnalysisTask: (id: string) => Promise<PreAnalysisTaskDetail>;
export const downloadPreAnalysisZip: (id: string) => Promise<Blob>;
export const downloadPreAnalysisFile: (taskId: string, filename: string) => Promise<Blob>;
export const listPreAnalysisStages: (id: string) => Promise<PreAnalysisStagesResponse>;
export const retryPreAnalysisTask: (id: string) => Promise<PreAnalysisRetryResponse>;
```

- `pre-analysis-viewer-types.ts`:
```ts
export interface ChapterTreeNode;
export interface ChapterStructurePayload;
export interface FlaggedParagraphRow;
```

- `pre-analysis-viewer.ts`:
```ts
// imports: 只列需要的 import
import { parse } from "papaparse";
import { ROW_INDEX_BASE, ZERO, EMPTY_STRING } from "@/const";
import type { FlaggedParagraphRow, ChapterStructurePayload } from "./pre-analysis-viewer-types";

const mapFlaggedRow: (raw: Record<string, string>, idx: number) => FlaggedParagraphRow;
const assertChaptersArray: (parsed: unknown) => asserts parsed is ChapterStructurePayload;
const fetchPreAnalysisFile: (taskId: string, filename: string) => Promise<string>;
export const getPreAnalysisChapterStructure: (taskId: string) => Promise<ChapterStructurePayload>;
export const getPreAnalysisFlaggedParagraphs: (taskId: string) => Promise<FlaggedParagraphRow[]>;
```

- `pre-analysis-tables.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";
import type { TablePageItem, TablePageResponse, TablePagesResponse } from "./pre-analysis-viewer-types";

const TABLE_FILENAME_PATTERN: RegExp;
export const parseTableFilename: (filename: string) => { pageNumber: number; tableIndex: number };
export const getPreAnalysisTablePages: (taskId: string) => Promise<TablePagesResponse>;
export const getPreAnalysisTablePage: (taskId: string, pageNum: number) => Promise<TablePageResponse>;
```

---

**verified**: False
**confidence**: high
**refuted_reason**: pre-analysis.ts: audit 提到复用 handleFetchError (lib/api/errors.ts), 但实际 lib/api/errors.ts 只导出 ApiError/NetworkError/getErrorMessage 三个符号, handleFetchError 不存在. L317-327 5 个本地 const 被算法塞到 2 组, 但 L317-319 跟 L320-321 是局部辅助常量, L323-327 是兜底常量, 两个用途不该合并. L463-479 字段映射 13 处 ?? EMPTY_STRING / Number() ?? ZERO, 把 ZERO/EMPTY_STRING 提 const/index.ts 全局常量会污染命名空间. 585 → ~150 (-74%) 估算乐观, 实际收益打 6-7 折.

---

### `packages/service/src/ingest/pre_analysis/router.py` (568 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/lookups/admin_router.py` (562 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/ingest/pdf_processing/converters/cad.py` (512 行) — **REFUTED**

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

**verified**: False
**confidence**: medium
**refuted_reason**: cad.py: L1 拆点行号基本准确, 但提议把 6 个 _record_* 方法 (L366-454) 拆到独立 module 忽略耦合成本: 这些方法都通过 self._xy() 拿坐标 helper (L456-463), 拆出去要么让 _xy 变成 free function + 加 import, 要么改 @staticmethod + 全签名拼 _xy_func 参数. L121 _apply_oda_path_from_config() 是模块导入时副作用 (写 ezdxf.options 全局), ODA path 拆到独立 module 后这个 import-time 调用仍然要留着. L328-364 _extract_text 的 6 分支 elif 链提议查表派发但 _record_dimension / _record_leader 签名不一致, 没法做 dict[type, callable] 查表. 综上预计 -75% 减幅虚高, 实际只能 -55% 左右.

---

### `packages/web/lib/api/knowledge.ts` (502 行) — **REFUTED**

**1. 拆分点**:
- L20-22 3 个 import (KnowledgeSchema type / THREE / apiFetch) — 拆后多文件需分别 import
- L24-171 11 个 knowledge 域 interface (StatsResponse / DatasetRow / QAListResponse / RetrieveRecord / RetrieveResult / UploadResult / NodeRow / RelationRow / TripleRowInput / TriplesInput / TriplesResponse / BatchInput / BatchState) -> `knowledge-types.ts` (~140 行)
- L173-272 16 个 CRUD wrapper (createTriples / fetchBatchStatus / fetchDatasets / fetchHealth / fetchNodes / fetchRelations / fetchSchema / fetchSchemas / fetchSegments / fetchStats / retrieveQA / startBatch / uploadDocument) -> `knowledge-crud.ts` (~100 行)
- L273-454 (2026-07-01 markdown extract KG spec) 12 个 type + 6 个 wrapper + 2 helper (buildExportUrl / triggerBlobDownload) + triggerExportDownload -> `knowledge-extract.ts` (~180 行)
- L456-502 (2026-07-03) ExtractTaskRow / ExtractTaskList + fetchExtractTasks -> `knowledge-tasks.ts` (~46 行)

**2. 纯函数/hook 化**: 可拆
- L429-432 `buildExportUrl(args)` 已是 pure func (URL 拼接), 可独立单测
- L435-442 `triggerBlobDownload(blob, filename)` 已是 pure side-effect func (DOM 节点创建 + click), 可独立单测 + mock document
- L175-179 `createTriples` 已是 one-liner wrapper, 无业务逻辑可拆
- L239-244 `fetchStats` 内 `params.toString()` + `queryString = ""; if (qs) queryString = "?${qs}";` 三元表达改成 `?${qs}` 一行 (oxlint 禁嵌套三元, 现状已是 if/else 写法, 但变量 queryString 冗余)
- L494-501 `fetchExtractTasks` 内 URLSearchParams 构造已是标准 pattern, 无需拆

**3. 库替代**: ✅
- es-toolkit 已装 (package.json:62) — 不适用本文件 (无 pick/omit/chunk/groupBy 场景)
- react-use 已装 (package.json:72) — `useAsync` / `useMount` 不适用 (本文件全是一过式 fetch wrapper, 非 React hook)
- zod 已装 (package.json:80) — 本文件 type 字段都从后端响应来, 解析校验是 server action 责任, 不在前端重复
- 无 URLSearchParams 替代库 — es-toolkit 1.49 不带 URL util, 保留原生

**4. 对象替 if**: 无
- L239-244 `fetchStats` 内 `if (qs) { queryString = "?${qs}"; }` 三元表达式 (oxlint 禁嵌套三元, 现状 if/else 写法符合规范), 不构成 if/else 链, 不需替
- 无 `if (kind === "kg_extract") ... else if (...)` 这种 dispatch, 不需 Map

**5. 数组迭代替循环**: 无
- 全文件无 for / forEach / while
- L494-501 URLSearchParams set/get 是 builder pattern, 不算数组迭代

**6. 预计减少**: 502 -> ~100 (主文件, 仅 facade re-export), 拆分后单文件最大 ~180 行 (-80%)

**7. 骨架伪代码**:

- `knowledge-types.ts`:
```ts
// imports: 只列需要的 import
import type { KnowledgeSchema } from "@/lib/schema-types";

export interface StatsResponse;
export interface DatasetRow;
export interface QAListResponse;
export interface RetrieveRecord;
export interface RetrieveResult;
export interface UploadResult;
export interface NodeRow;
export interface RelationRow;
export interface TripleRowInput;
export interface TriplesInput;
export interface TriplesResponse;
export interface BatchInput;
export interface BatchState;
```

- `knowledge-crud.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";
import { THREE } from "@/const";
import type { KnowledgeSchema } from "@/lib/schema-types";
import type { ... } from "./knowledge-types";

export const createTriples: (input: TriplesInput, headers?: Record<string, string>) => Promise<TriplesResponse>;
export const fetchBatchStatus: (taskId: string) => Promise<BatchState>;
export const fetchDatasets: () => Promise<DatasetRow[]>;
export const fetchHealth: () => Promise<{ ok: boolean }>;
export const fetchNodes: (limit?: number) => Promise<NodeRow[]>;
export const fetchRelations: (limit?: number) => Promise<RelationRow[]>;
export const fetchSchema: (domain: string) => Promise<KnowledgeSchema>;
export const fetchSchemas: () => Promise<{ schemas: { name: string }[] }>;
export const fetchSegments: () => Promise<{ items: { id: string; content: string }[] }>;
export const fetchStats: (type?: string, domain?: string) => Promise<StatsResponse>;
export const retrieveQA: (question: string, datasetId: string, topK?: number) => Promise<RetrieveResult>;
export const startBatch: (input: BatchInput) => Promise<{ task_id: string }>;
export const uploadDocument: (file: File, datasetId: string) => Promise<UploadResult>;
```

- `knowledge-extract.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";
import type { ... } from "./knowledge-types";

export type DatasetEntry;
export type ExtractorInfo;
export type SplitterInfo;
export type ExtractTaskState;
export type ExtractPreviewEntity;
export type ExtractPreviewRelation;
export type ExtractPreview;
export type PatchItemInput;
export type ExtractUploadResult;
export const fetchExtractDatasets: () => Promise<DatasetEntry[]>;
export const fetchExtractors: () => Promise<ExtractorInfo[]>;
export const fetchSplitters: () => Promise<SplitterInfo[]>;
export const uploadExtractFile: (file: File, dataset: string) => Promise<ExtractUploadResult>;
export const startExtract: (req: {...}) => Promise<{ task_id: string; state: string }>;
export const fetchExtractTask: (taskId: string) => Promise<ExtractTaskState>;
export const fetchExtractPreview: (taskId: string, dataset: string) => Promise<ExtractPreview>;
export const patchExtractItems: (taskId: string, dataset: string, items: PatchItemInput[]) => Promise<{ updated: number }>;
export const commitExtract: (taskId: string, dataset: string) => Promise<{ success: number; failed: number; errors: string[] }>;
export type ExportArgs;
const buildExportUrl: (args: ExportArgs) => string;
const triggerBlobDownload: (blob: Blob, filename: string) => void;
export const triggerExportDownload: (args: ExportArgs) => Promise<void>;
```

- `knowledge-tasks.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";

export type ExtractTaskRow;
export type ExtractTaskList;
export const fetchExtractTasks: (params: { kind: "kg_extract" | "kg_batch"; limit?: number; offset?: number }) => Promise<ExtractTaskList>;
```

---

**verified**: False
**confidence**: high
**refuted_reason**: knowledge.ts: audit 提到复用 handleFetchError (lib/api/errors.ts), 但实际 lib/api/errors.ts (全 50 行) 只导出 ApiError/NetworkError/getErrorMessage 三个符号, handleFetchError 不存在; 复用前提不成立. 另 knowledge.ts (L1-502) 根本没有 local handleError 函数, audit 错把 pre-analysis.ts 的 handleError 套到 knowledge.ts 上了. 此外 CRUD wrapper count 是 13, 不是 finding 说的 16. fetchStats 的简化建议 (改 ?${qs}) 会产生非法 URL (空 query 留下 ?).

---

### `packages/service/scripts/neo4j_import.py` (499 行) — **REFUTED**

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

**verified**: False
**confidence**: high
**refuted_reason**: neo4j_import.py: 这是一个 scripts/ 下的一次性 CLI 脚本 (uv run python scripts/neo4j_import.py import), 不会被其它模块 import, 拆 module 不带来复用收益. Neo4jClient._connect() 内部调 _normalize_uri_for_ssl_context, audit 自己说保留在 client 但又把 Neo4jClient 整体拆出去, 自相矛盾. 减少 % 虚高: audit 说 499 → 180 (-64%), 但仅 yaml_to_graph_data + dedup + load_yamls 就 170 行 (L67-236), 加上 cmd_import/cmd_check/main 实际剩余 280+ 行, 真实减幅约 -44%. 单 class (Neo4jClient) 拆独立 module 在 90 行规模属 Python 反模式.

---

### `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` (479 行) — **REFUTED**

**1. 拆分点**:
- L1-184 `useUploadState` 状态子 hook (8 state + reset effect + paramKeys 计算) -> `_hooks/use-upload-state.ts` (hook)
- L186-257 `useUploadHandlers` handler 子 hook (open/clear/upload + reset + toast) -> `_hooks/use-upload-handlers.ts` (hook)
- L259-296 `renderParamInput` 当前未用, export 保留 -> `_lib/render-param-input.tsx` (纯函数) [2026-07-09 注: UI 隐藏但导出保留, 拆走便于后续放开时单测]
- L298-478 `PreAnalysisUploadDialog` 主组件 (3 段式 JSX: dropzone/file-info/advanced-options) -> 留当前文件 (主组件, 已靠 hook 抽瘦)
- 副组件拆: L381-475 高级选项区 (backend radio + flavor description + chapter config L432-475) -> `advanced-options-section.tsx` (component)
- 副组件拆: L450-474 LLM 增强开关 -> `llm-refinement-toggle.tsx` (component)

**2. 纯函数/hook 化**:
- 可拆:
  - `getCamelotParamKeys(flavor)` L79-92 已模块级纯函数, OK
  - `BACKEND_OPTIONS` / `FLAVOR_OPTIONS` / `STRATEGY_OPTIONS` / `LEVEL_OPTIONS` 常量字典 L40-124 模块级, OK
  - `useUploadState` L145-183 已抽 hook, OK
  - `useUploadHandlers` L189-257 已抽 hook, OK
- 不可拆: 无 (主组件 JSX 已经被 3 段拼装, 但每段都可单独抽小组件)

**3. 库替代**:
- shadcn `<Table>` 已装 (components/ui/table) 但本文件没用 table, 用 Form/Dialog/Select/RadioGroup
- 无 — 表单 + Dialog + RadioGroup 都是现成的, 项目封装 AppDialog / AppRadioGroup / AppSelect / AppTooltip / FileDropzone / Switch / Label / Input 已 100% 用

**4. 对象替 if**:
- L104-115 `FLAVOR_OPTIONS` / L110-115 `STRATEGY_OPTIONS` / L118-124 `LEVEL_OPTIONS` 已是数组, OK
- L79-92 `getCamelotParamKeys` if 链 -> 可改 `flavorParamKeyMap: Record<string, string[]>` + `flavorParamKeyMap[flavor] ?? baseKeys`, 但链只有 4 分支, ROI 低, 留 if 链

**5. 数组替循环**:
- 无显式 for 循环, 已 .map() / .filter() / 数组迭代

**6. 预计减少**: 479 -> 主文件 ~250 (-48%); 拆到 5 个文件: use-upload-state.ts (~50), use-upload-handlers.ts (~80), render-param-input.tsx (~50), advanced-options-section.tsx (~110), llm-refinement-toggle.tsx (~40)

**7. 骨架伪代码**:
- `_hooks/use-upload-state.ts`:
```ts
import { useState, useEffect } from "react";
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";

export const useUploadState = (): {
  pickedFile: File | null;
  setPickedFile: (file: File | null) => void;
  isUploading: boolean;
  setIsUploading: (val: boolean) => void;
  uploadError: string | null;
  setUploadError: (val: string | null) => void;
  backend: TableBackend;
  setBackend: (val: TableBackend) => void;
  params: Record<string, string | number>;
  setParams: (val: Record<string, string | number>) => void;
  paramKeys: string[];
  chapterMaxLevel: number;
  setChapterMaxLevel: (val: number) => void;
  enableLlmRefinement: boolean;
  setEnableLlmRefinement: (val: boolean) => void;
} => { /* 当前 L146-183 内容 */ };
```

- `advanced-options-section.tsx`:
```tsx
import { Label } from "@/components/ui/label";
import { AppRadioGroup } from "@/components/common/input";
import { AppSelect } from "@/components/common/input";
import { Switch } from "@/components/ui/switch";
import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import { HelpCircle } from "lucide-react";

export function AdvancedOptionsSection(props: {
  backend: TableBackend;
  onBackendChange: (val: TableBackend) => void;
  chapterMaxLevel: number;
  onChapterMaxLevelChange: (val: number) => void;
  enableLlmRefinement: boolean;
  onEnableLlmRefinementChange: (val: boolean) => void;
  translate: (key: string, params?: Record<string, string | number>) => string;
}): JSX.Element;
```

---

**verified**: False
**confidence**: high
**refuted_reason**: upload-dialog: audit 错误声称 renderParamInput 当前未用, 但 L427 实际在调用 (在 JSX 注释块里, 但函数被引用). L1-184 useUploadState 不对, 实际 L145-183. useUploadHandlers 不在 L186-257, 实际 L189-257. chapter config L432-475 错, 实际 L431 起. split yields only -48% (479→250), leaves main at 250 lines still over 200-line threshold.

---

### `packages/service/src/auth/auth_admin_router.py` (464 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/approvals/router.py` (459 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/lookups/service.py` (450 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/lib/date.ts` (450 行) — **PASS**

**1. 拆分点**:
- L1-13 imports + L19 HOURS_PER_DAY 常量 (项目 const/index.ts:36 已有 HOURS_PER_DAY = 24) -> 删本地 HOURS_PER_DAY, 复用 const/
- L15-65 `DateInput` type + `toInstant` 输入归一化 + `InstantUnit` internal type -> `date-instant.ts` (~55 行)
- L66-90 `nowInstant` / `nowMs` / `nowIso` 3 个当前时间 -> `date-now.ts` (~30 行)
- L92-159 5 个 differenceIn (Milliseconds / Seconds / Minutes / Hours / Days) + `durationOf` internal -> `date-difference.ts` (~70 行)
- L161-227 5 个 add (Days / Hours / Minutes / Seconds / Milliseconds) + `shift` internal -> `date-add.ts` (~70 行)
- L229-270 3 个比较 (isAfter / isBefore / isEqual) + `instantOf` internal -> `date-compare.ts` (~45 行)
- L272-304 2 个格式化 (formatDate / formatDateTime) -> `date-format.ts` (~35 行)
- L306-356 2 个相对时间 (fmtRelativeTime / formatRelativeTime) -> `date-relative.ts` (~55 行)
- L358-450 4 个耗时格式化 (`MILLIS_PER_HOUR` / `MILLIS_PER_MINUTE` / `DURATION_DASH` / `tryParseMs` / `formatElapsedMs` / `formatDurationMs` / `formatRange`) -> `date-duration.ts` (~95 行)
- 主文件 `date.ts` 仅留 facade barrel re-export (~30 行)

**2. 纯函数/hook 化**: 可拆
- 所有 export 函数已是 pure (Temporal.Instant 输入 → 数值/字符串输出), 无 hook
- `toInstant` / `durationOf` / `shift` / `instantOf` / `tryParseMs` / `formatRange` 都是 internal helper, 已标注 @internal
- `nowInstant` / `nowMs` / `nowIso` 是当前时间 getter, 测试可注入 `Temporal.Now` mock (现 date.test.ts 用 Temporal.Now.instant() 真实值)

**3. 库替代**: ✅
- @js-temporal/polyfill 已装 (package.json:32) — 本文件核心依赖, 保留
- es-toolkit 已装 (package.json:62) — 不适用 (无 pick/omit 场景)
- date-fns — 项目无依赖 (CLAUDE.md 规定用 lib/date), 不引
- dayjs — 项目无依赖 (CLAUDE.md 禁止 moment, 同源不引 dayjs)
- react-use 已装 (package.json:72) — 不适用 (本文件全 pure func)
- zod 已装 (package.json:80) — 不适用 (无 input schema 校验)

**4. 对象替 if**: 部分可替
- L322-333 `fmtRelativeTime` 内 4 个 if-else 链 (`if (diff < SECONDS_PER_MINUTE) ... else if (diff < SECONDS_PER_HOUR) ... else if (diff < SECONDS_PER_DAY) ...`) — 经典档位查找, 可替 `const RELATIVE_THRESHOLDS: Array<{ max: number; unit: number; suffix: string }> = [...]` 然后 `find()`
- L345-355 `formatRelativeTime` 内 4 个 if-else 链 (同上), 同上可替
- L425-430 `formatDurationMs` 内 `if (end === null) { liveMs < MILLIS_PER_MINUTE ? ... : ... } else { formatRange(...) }` — 二分支 (end 是否 null) 不可替 Map
- L436-450 `formatRange` 内 4 个 if-else 链 (同上 ms 档位查找), 可替 `const DURATION_RANGES: Array<{ max: number; format: (ms: number) => string }> = [...]`

**5. 数组迭代替循环**: 无
- 全文件无 for / forEach / while
- `if-else` 链可用 `find` 替, 不算数组迭代

**6. 预计减少**: 450 -> ~120 (单文件 facade), 拆分后单文件最大 ~95 行 (-73%)

**7. 骨架伪代码**:

- `date.ts` (facade barrel):
```ts
// imports: 只列需要的 import
export type { DateInput } from "./date-instant";
export { toInstant } from "./date-instant";
export { nowInstant, nowMs, nowIso } from "./date-now";
export {
  differenceInMilliseconds,
  differenceInSeconds,
  differenceInMinutes,
  differenceInHours,
  differenceInDays,
} from "./date-difference";
export { addDays, addHours, addMinutes, addSeconds, addMilliseconds } from "./date-add";
export { isAfter, isBefore, isEqual } from "./date-compare";
export { formatDate, formatDateTime } from "./date-format";
export { fmtRelativeTime, formatRelativeTime } from "./date-relative";
export { formatElapsedMs, formatDurationMs } from "./date-duration";
```

- `date-instant.ts`:
```ts
// imports: 只列需要的 import
import { Temporal } from "@js-temporal/polyfill";
export type DateInput = string | number | Date | Temporal.Instant;
type InstantUnit = ...;
export const toInstant: (input: DateInput) => Temporal.Instant;
```

- `date-difference.ts`:
```ts
import { toInstant } from "./date-instant";
import { HOURS_PER_DAY } from "@/const";
const durationOf: (later: DateInput, earlier: DateInput, largestUnit: InstantUnit) => Temporal.Duration;
export const differenceInMilliseconds: (later: DateInput, earlier: DateInput) => number;
export const differenceInSeconds: (later: DateInput, earlier: DateInput) => number;
export const differenceInMinutes: (later: DateInput, earlier: DateInput) => number;
export const differenceInHours: (later: DateInput, earlier: DateInput) => number;
export const differenceInDays: (later: DateInput, earlier: DateInput) => number;
```

- `date-relative.ts`:
```ts
import { nowMs } from "./date-now";
import { MS_PER_SECOND, SECONDS_PER_MINUTE, SECONDS_PER_HOUR, SECONDS_PER_DAY, HOURS_PER_DAY, ZERO } from "@/const";
const RELATIVE_THRESHOLDS: Array<{ max: number; divisor: number; suffix: string }>;
export const fmtRelativeTime: (epoch: number, now?: number) => string;
export const formatRelativeTime: (timestamp: number) => string;
```

- `date-duration.ts`:
```ts
import { nowMs } from "./date-now";
import { MS_PER_SECOND, SECONDS_PER_MINUTE, SECONDS_PER_HOUR, ZERO } from "@/const";
const MILLIS_PER_HOUR: number;
const MILLIS_PER_MINUTE: number;
const DURATION_DASH: string;
const tryParseMs: (iso: string) => number;
const DURATION_RANGES: Array<{ max: number; format: (ms: number) => string }>;
const formatRange: (ms: number) => string;
export const formatElapsedMs: (ms: number) => string;
export const formatDurationMs: (start: string, end: string | null) => string;
```

---

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/ingest/pdf_processing/pipeline.py` (448 行) — **REFUTED**

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

**verified**: False
**confidence**: high
**refuted_reason**: pipeline.py: finding 自身在 7 段全部标保留, 唯一提议拆的只是 _run_bucket helper (L211-236 三个 bucket 调度块), 实际能 DRY 掉的仅 ~30 行重复 (logger.banner + 调 process_*_files), 远不到 168 行 (-37%). process_uri (L60-93) 跟 process_files 共享 tempfile/ArchiveHandler/process_files() 调用链, 仅 35 行 wrapper, 充其量再省 30 行. 448 行文件中 ~50 行是 docstring + imports + __main__, 真正业务逻辑 ~400 行, 即使把 _run_bucket + process_uri 全提出也只到 ~340 行 (-14%). 实际 -37% 目标需要结构性拆分, 但 finding 没给这套拆分方案.

---

### `packages/web/app/[locale]/admin/users/_components/admin-users-table.tsx` (438 行) — **PASS**

**1. 拆分点**:
- L43-55 `buildRoleOptions` 纯函数 (48% 是这个组件辅助) -> 留, 模块级小函数, 可挪到 `_lib/role-options.ts`
- L57-62 `getAdminActionLabel` 纯函数 (提权/降权) -> `_lib/action-labels.ts`
- L63-68 `getActiveActionLabel` 纯函数 (启用/禁用) -> `_lib/action-labels.ts`
- L86-96 `renderRoleSelect` 渲染角色下拉 (4 props) -> `role-select.tsx` (component)
- L98-115 `renderKindBadge` 渲染账号/anon Badge (3 props) -> `kind-badge.tsx` (component)
- L117-134 `renderActiveBadge` 渲染启用/禁用 Badge (3 props) -> `active-badge.tsx` (component)
- L136-194 `renderActionButtons` 渲染 3 个操作按钮 (7 props, 39 行) -> `action-buttons.tsx` (component)
- L196-206 `getResetDescription` 纯函数 -> `_lib/reset-description.ts`
- L208-295 `buildColumns` 列定义 (88 行, 7 列) -> 留当前文件, 太耦合 props
- 副组件: L385-437 `AdminUsersTable` 主组件 JSX -> 留, 已经较瘦
- 子组件: `UserFilters` 已经抽到独立文件 `user-filters.tsx`, OK

**2. 纯函数/hook 化**:
- 可拆:
  - L43-55 `buildRoleOptions` -> 模块级, 已 OK
  - L57-68 两个 label getter -> 模块级, 已 OK
  - L196-206 `getResetDescription` -> 模块级, 已 OK
- 不可拆: 列定义 (L208-295) 需要 7 props, 拆出去 props 传递成本 > 模块内

**3. 库替代**:
- shadcn `<Table>` 已装 (components/ui/table), 已经用项目封装 `DataTable<T>` + `DataEmpty`
- shadcn `<Badge>` 已装 (components/ui/badge.tsx), 已用
- 项目封装 `AppConfirm` (components/common/confirm) 已用, OK
- 项目封装 `AppSelect` (components/common/input) 已用, OK
- 项目封装 `ErrorBanner` (components/common/feedback) 已用, OK
- 无

**4. 对象替 if**:
- L103-114 `renderKindBadge` 内 if/else 串 badgeVariant + label -> 可改 `KIND_LABEL: Record<AdminUser["kind"], { label, variant }>` 查表
- L122-133 `renderActiveBadge` 同模式 -> `ACTIVE_LABEL: Record<boolean, { label, variant }>` 查表
- L57-62 `role === "admin" ? "降权" : "提权"` 可改 `ACTION_LABEL_BY_ROLE: Record<string, string>` 查表
- L63-68 `isActive ? "禁用" : "启用"` 可改 `ACTIVE_TOGGLE_LABEL[isActive]` 查表

**5. 数组替循环**:
- 无 for, 已 .map()

**6. 预计减少**: 438 -> 主文件 ~210 (-52%); 拆到 7 个文件: role-select.tsx (~30), kind-badge.tsx (~25), active-badge.tsx (~30), action-buttons.tsx (~80), `_lib/action-labels.ts` (~30), `_lib/role-options.ts` (~20), `_lib/reset-description.ts` (~20)

**7. 骨架伪代码**:
- `_lib/action-labels.ts`:
```ts
export const ADMIN_ACTION_LABEL: Record<string, string> = {
  admin: "降权",
  default: "提权",
};
export const ACTIVE_TOGGLE_LABEL: Record<boolean, string> = {
  true: "禁用",
  false: "启用",
};
```

- `kind-badge.tsx`:
```tsx
import { Badge } from "@/components/ui/badge";
import type { AdminUser } from "@/lib/api/users";

const KIND_META: Record<AdminUser["kind"], { label: string; variant: "default" | "secondary" }> = {
  account: { label: "账号", variant: "default" },
  default: { label: "anon", variant: "secondary" },
};

export function KindBadge({ kind }: { kind: AdminUser["kind"] }): JSX.Element {
  const meta = KIND_META[kind] ?? KIND_META.default;
  return <Badge variant={meta.variant}>{meta.label}</Badge>;
}
```

- `action-buttons.tsx`:
```tsx
import { Button } from "@/components/ui/button";
import type { AdminUser } from "@/lib/api/users";
import { ADMIN_ACTION_LABEL, ACTIVE_TOGGLE_LABEL } from "../_lib/action-labels";

interface ActionButtonsProps {
  currentUserId: number;
  pending: boolean;
  user: AdminUser;
  onToggleAdmin: (user: AdminUser) => void;
  onToggleActive: (user: AdminUser) => void;
  onResetPassword: (user: AdminUser) => void;
}
export function ActionButtons(props: ActionButtonsProps): JSX.Element { /* L157-194 */ }
```

---

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/app/[locale]/_actions/account.ts` (435 行) — **REFUTED**

**1. 拆分点**:
- L40-129 `loginAction` + helpers (`getLoginCredentials` L50-60, `loginApiCall` L68-86, `setLoginCookie` L92-102) -> `actions/account/login.ts` (server-only module)
- L131-165 `forgotPasswordAction` -> `actions/account/forgot-password.ts`
- L167-226 `resetPasswordAction` + helpers (`validateResetPasswordInput` L184-200) -> `actions/account/reset-password.ts`
- L228-340 `acceptInviteAction` + helpers (`getAcceptInviteFields` L245-257, `validateAcceptInviteInput` L263-280, `acceptInviteApiCall` L289-307) -> `actions/account/accept-invite.ts`
- L342-378 `resetPasswordAdminAction` -> `actions/account/reset-password-admin.ts`
- L380-420 `createInviteAction` -> `actions/account/create-invite.ts`
- L422-435 `logoutAction` -> `actions/account/logout.ts`
- 留: 当前文件只剩 barrel re-export `export * from "./login"`, 极薄壳

**2. 纯函数/hook 化**:
- 可拆:
  - `getLoginCredentials` L50-60 -> 模块级纯函数, 已 OK
  - `loginApiCall` L68-86 -> async 纯函数, 已 OK
  - `setLoginCookie` L92-102 -> async 纯函数, 已 OK
  - `validateResetPasswordInput` L184-200 -> 模块级纯函数, 已 OK
  - `getAcceptInviteFields` L245-257 -> 模块级纯函数, 已 OK
  - `validateAcceptInviteInput` L263-280 -> 模块级纯函数, 已 OK
  - `acceptInviteApiCall` L289-307 -> async 纯函数, 已 OK
- 不可拆: 无

**3. 库替代**:
- 无 — server actions 走原 fetch (serverAuthHeaders + apiFetch) 是必然, 项目无更高层封装
- `/i18n/navigation` `redirect` 已用 OK

**4. 对象替 if**:
- L184-200 校验函数内 if 链 (token / password length / confirm) -> 不可拆为查表, 是有顺序的验证链
- L263-280 同模式, 同结论
- L218-225 `catch` 内 if/else (ApiError vs unknown) -> 已用 `actionError(error)` 工具函数, OK

**5. 数组替循环**:
- 无

**6. 预计减少**: 435 -> 7 个 actions 每个 ~50-80 行; current 文件留 shell ~15 行 (-97%)

**7. 骨架伪代码**:
- `_actions/account/login.ts`:
```ts
"use server";
import { ApiError, NetworkError } from "@/lib/api/errors";
import { login } from "@/lib/api/account";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { cookies } from "next/headers";
import { redirect } from "@/i18n/navigation";
import { getLocale } from "next-intl/server";
import { revalidatePath } from "next/cache";
import { COOKIE_USER_TOKEN, HOURS_PER_DAY, HTTP_UNAUTHORIZED, MINUTES_PER_HOUR, SECONDS_PER_MINUTE } from "@/const";

export interface LoginState { ok: boolean; error: string | null; }

const COOKIE_MAX_AGE = 7 * HOURS_PER_DAY * MINUTES_PER_HOUR * SECONDS_PER_MINUTE;
const getLoginCredentials = (formData: FormData) => { /* L50-60 */ };
const loginApiCall = async (email: string, password: string) => { /* L68-86 */ };
const setLoginCookie = async (token: string) => { /* L92-102 */ };

export const loginAction = async (_prev: LoginState, formData: FormData): Promise<LoginState> => { /* L110-129 */ };
```

- `_actions/account/index.ts` (barrel):
```ts
export * from "./login";
export * from "./forgot-password";
export * from "./reset-password";
export * from "./accept-invite";
export * from "./reset-password-admin";
export * from "./create-invite";
export * from "./logout";
```

---

**verified**: False
**confidence**: medium
**refuted_reason**: account.ts: Line ranges 准确, 7-action split 准确. 但 -97% reduction 虚高: 7 个新文件各有 use server + ~8 共享 imports (cookies, getLocale, redirect, revalidatePath, serverAuthHeaders, ApiError, actionError, MIN_PASSWORD_LENGTH, COOKIE_USER_TOKEN, time constants) 约 70 行重复 boilerplate, 累计 post-split total 约 420-455 行, 超过原 435 - 净减少约 0%. 此外 setLoginCookie (L92-102) 被 loginAction (L122) 和 acceptInviteAction (L336) 共享, 拆 sub-file 产生 cross-file 依赖, audit 没解决.

---

### `packages/service/src/auth/account_settings_router.py` (424 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/app/[locale]/_actions/account-settings.ts` (418 行) — **PASS**

**1. 拆分点**:
- L31-78 `updateProfileAction` + helper `handleProfileError` L47-55 -> `actions/account-settings/profile.ts` (server-only)
- L80-165 Avatar actions (`uploadAvatarAction` + `deleteAvatarAction` + helpers `validateAvatarFile` L99-110, `handleUploadError` L116-127) -> `actions/account-settings/avatar.ts`
- L167-225 `requestEmailChangeAction` + helper `handleEmailError` L186-194 -> `actions/account-settings/email.ts`
- L227-301 `changePasswordAction` + helpers `validatePasswords` L246-261, `handlePasswordError` L267-272 -> `actions/account-settings/password.ts`
- L303-418 Deletion actions (`requestDeletionAction` + `cancelDeletionAction` + helper `handleDeletionError` L324-333) -> `actions/account-settings/deletion.ts`
- 留: 当前文件只剩 barrel, 极薄

**2. 纯函数/hook 化**:
- 可拆:
  - `handleProfileError` L47-55 -> 模块级纯函数, 已 OK
  - `validateAvatarFile` L99-110 -> 模块级纯函数, 已 OK
  - `handleUploadError` L116-127 -> 模块级纯函数, 已 OK
  - `handleEmailError` L186-194 -> 模块级纯函数, 已 OK
  - `validatePasswords` L246-261 -> 模块级纯函数, 已 OK
  - `handlePasswordError` L267-272 -> 模块级纯函数, 已 OK
  - `handleDeletionError` L324-333 -> 模块级纯函数, 已 OK
- 不可拆: 无

**3. 库替代**:
- 无

**4. 对象替 if**:
- L106 `["image/png", "image/jpeg", "image/webp"].includes(file.type)` -> 已数组, OK
- L186-194 `handleEmailError` 已经是 if(==HTTP_BAD_REQUEST) 链 -> 单分支不值得改
- L267-272 简单 if (ApiError vs unknown) -> 已 OK
- L324-333 同, OK

**5. 数组替循环**:
- 无

**6. 预计减少**: 418 -> 5 个子文件每个 ~60-90 行; current 文件留 barrel ~15 行 (-96%)

**7. 骨架伪代码**:
- `_actions/account-settings/avatar.ts`:
```ts
"use server";
import { ApiError } from "@/lib/api/errors";
import { actionErrorWithFallback } from "@/lib/actions-utils";
import { uploadAvatar, deleteAvatar } from "@/lib/api/account";
import { HTTP_UNPROCESSABLE_ENTITY } from "@/const";

export interface AvatarState { ok: boolean; error: string | null; avatarUrl: string | null; }
const AVATAR_MAX_BYTES = 2_097_152;
const validateAvatarFile = (file: File | null): string | null => { /* L99-110 */ };
const handleUploadError = (error: unknown): AvatarState => { /* L116-127 */ };

export const uploadAvatarAction = async (_prev: AvatarState, formData: FormData): Promise<AvatarState> => { /* L135-151 */ };
export const deleteAvatarAction = async (): Promise<AvatarState> => { /* L157-165 */ };
```

- `_actions/account-settings/index.ts` (barrel):
```ts
export * from "./profile";
export * from "./avatar";
export * from "./email";
export * from "./password";
export * from "./deletion";
```

---

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/chat_share/router.py` (413 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/auth/auth_account_router.py` (402 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx` (400 行) — **PASS**

**1. 拆分点**:
- L33-39 `KIND_LABEL` 常量 -> `_lib/output-labels.ts`
- L52-61 `STATE_LABELS` 常量 -> `_lib/state-labels.ts`
- L66-77 `VIEWABLE_KINDS` + `isViewableKind` -> `_lib/viewable-kinds.ts`
- L89-101 `viewHrefForKind` 纯函数 -> `_lib/view-href.ts`
- L103-135 `formatSize` / `buildZipFilename` 纯函数 -> `_lib/format-size.ts` + `_lib/zip-filename.ts`
- L138-160 `buildStatCardClickHandler` 工厂 -> `_lib/stat-card-click.ts`
- 副组件拆: L274-336 PageHero + 三张 StatCard 区 -> `summary-section.tsx` (component) [重用所有常量 + handler]
- 副组件拆: L348-396 产物表区 (DataTable + action buttons + 下载按钮) -> `output-files-section.tsx` (component)
- L164-400 `AdminPreAnalysisDetailClient` 主组件 -> 留 ~120-150 行

**2. 纯函数/hook 化**:
- 可拆:
  - L115-123 `formatSize` -> 模块级, 已 OK
  - L132-135 `buildZipFilename` -> 模块级, 已 OK
  - L89-101 `viewHrefForKind` -> 模块级, 已 OK
  - L76-77 `isViewableKind` -> 模块级, 已 OK
  - L147-160 `buildStatCardClickHandler` -> 模块级, 已 OK
  - L34-39 `KIND_LABEL` / L57-61 `STATE_LABELS` / L68 `VIEWABLE_KINDS` -> 模块级常量, 已 OK
- 不可拆:
  - L186-202 `handleDownloadZip` 用了 `data.pdf_filename`, 必须留在组件内
  - L209-217 `handleDownloadFile` 同, 必须留在组件内

**3. 库替代**:
- shadcn `<StatCard>` 已封装 (components/common/display/app-stat-card.tsx), 已用
- shadcn `<Button>` 已用 OK
- 项目封装 `<BackLink>` / `<PageHero>` / `<DataTable>` / `<DataEmpty>` / `<ErrorBanner>` 已用 OK
- 无 (lucide-react `Download` / `Eye` / `RefreshCw` 已用, OK)

**4. 对象替 if**:
- L116-123 `if (bytes < ONE_KB) ... else if (bytes < ONE_MB)` -> 可改 size bucket map + 查表
- L33-39 `KIND_LABEL` 是查表, OK
- L57-61 `STATE_LABELS` 是查表, OK

**5. 数组替循环**:
- 无

**6. 预计减少**: 400 -> 主文件 ~150 (-63%); 拆到 7-8 个文件: summary-section.tsx (~80), output-files-section.tsx (~90), `_lib/output-labels.ts` (~15), `_lib/state-labels.ts` (~15), `_lib/view-href.ts` (~25), `_lib/viewable-kinds.ts` (~20), `_lib/format-size.ts` (~15), `_lib/zip-filename.ts` (~10)

**7. 骨架伪代码**:
- `_lib/format-size.ts`:
```ts
import { ONE_KB, ONE_MB } from "@/const";
export const formatSize = (bytes: number): string => { /* L115-123, candidate for size bucket map */ };
```

- `summary-section.tsx`:
```tsx
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { StatCard } from "@/components/common/display/app-stat-card";
import type { PreAnalysisTaskState } from "@/lib/api/pre-analysis";

interface SummarySectionProps {
  taskId: string;
  state: PreAnalysisTaskState;
  elapsedMs: number;
  pdfFilename: string;
  totalTables: number;
  totalChapters: number;
  totalFlagged: number;
  crossPageCandidates: number;
  onTablesClick: () => void;
  onChaptersClick: () => void;
  onFlaggedClick: () => void;
  translate: (key: string, params?: Record<string, string | number>) => string;
}
export function SummarySection(props: SummarySectionProps): JSX.Element { /* L274-336 */ }
```

---

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/chat/service.py` (398 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/product_decoders/engine.py` (390 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/config/settings.py` (384 行) — **REFUTED**

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

**verified**: False
**confidence**: high
**refuted_reason**: config/settings.py: 拆分假设有 3 个反例, 都跟 config dataclass 必须 .from_env() 内存反馈直接冲突: (1) 主 Settings 是 startup 一次性 import, 100+ env 字段以 flat settings.redis_host 形式被 6 个业务文件 24+ 处直接属性访问, 改成 14 个嵌套 frozen dataclass 必须破坏全部调用点改成 settings.redis.host, 而 routing 已是 ARCH-002/003 完整迁移的稳定面, 属高风险无收益重构; (2) 拆分断送 不 reload single instance 的 monkeypatch.setenv 测试契约 - 当前每个字段的 default_factory lambda 每次访问都重读 os.getenv, 让单测 monkeypatch.setenv 立刻生效, 嵌套 dataclass 必须 frozen=True 才能保一致, 但 frozen + 在 from_env 一次性快照后 setenv 失效, 业务文件已稳定依赖 lazy reload 语义 6 个月; (3) L67 Settings 不是 @dataclass(frozen=True) 而是 @dataclass (可变), 14 个嵌套 dataclass 要拆成 frozen=True 才能组嵌, 但 Paths/CadConfig/ArchiveConfig L33/41/53 已显式 frozen=True 说明设计者明知嵌套要 frozen, 当前扁平可变主类是故意留给 lambda runtime reload 用, 不是疏漏.

---

### `packages/web/components/chat/memory-management-dialog.tsx` (378 行) — **REFUTED**

**1. 拆分点**:
- L41-54 `filterMemories` 纯函数 -> 留当前文件 (模块级, 已 OK)
- L62-84 `useMemoryApi` 数据加载 hook -> `_hooks/use-memory-api.ts` (hook)
- L93-98 `useMemoryFilter` 客户端过滤 hook -> `_hooks/use-memory-filter.ts` (hook)
- L106-111 `useMemoryEdit` 编辑状态 hook -> `_hooks/use-memory-edit.ts` (hook)
- L121-140 `MemoryDialogFooter` -> `memory-dialog-footer.tsx` (component) [已单独模块]
- L156-222 `MemoryListItem` 行组件 (单条记忆展示/编辑态切换) -> `memory-list-item.tsx` (component) [已单独模块]
- L239-284 `MemoryListContent` 列表容器 (loading/empty/list) -> `memory-list-content.tsx` (component)
- L286-378 主组件 `MemoryManagementDialog` -> 留 ~80 行

**2. 纯函数/hook 化**:
- 可拆:
  - `useMemoryApi` L64-84 已抽 hook, OK
  - `useMemoryFilter` L94-98 已抽 hook, OK
  - `useMemoryEdit` L107-111 已抽 hook, OK
  - `filterMemories` L48-54 已模块级纯函数, OK
- 不可拆: `saveEdit` / `handleDelete` / `handleClearAll` 用了所有 state + setState, 拆 hook 会切断依赖, 留在主组件

**3. 库替代**:
- shadcn `<Input>` / `<Button>` 已用 OK
- 项目封装 `<AppDialog>` / `<AppConfirm>` 已用 OK
- 无

**4. 对象替 if**:
- L177-198 `isEditing` 时 vs `else` 走两套 JSX, 不可改查表, 因为各自带不同 props (Input vs readonly text)
- 无

**5. 数组替循环**:
- L271-283 `.map((memory) => <MemoryListItem>...)` 已 OK

**6. 预计减少**: 378 -> 主文件 ~80 (-79%); 拆到 7 个文件: use-memory-api.ts (~30), use-memory-filter.ts (~15), use-memory-edit.ts (~15), memory-list-content.tsx (~60), + 已存在的 memory-dialog-footer.tsx / memory-list-item.tsx

**7. 骨架伪代码**:
- `_hooks/use-memory-api.ts`:
```ts
import { useState, useEffect } from "react";
import { useBoolean } from "react-use";
import { type MemoryHit, list } from "@/lib/api/memory";

export function useMemoryApi(open: boolean): {
  memories: MemoryHit[];
  loading: boolean;
  load: () => Promise<void>;
  setMemories: (val: MemoryHit[]) => void;
} { /* L64-84 */ }
```

- `memory-list-content.tsx`:
```tsx
import { useTranslations } from "next-intl";
import { ZERO } from "@/const";
import type { MemoryHit } from "@/lib/api/memory";
import { MemoryListItem } from "./memory-list-item";

interface MemoryListContentProps { /* L240-260 props */ }
export function MemoryListContent(props: MemoryListContentProps): JSX.Element {
  if (props.loading) return <div className="text-muted-foreground text-sm">...</div>;
  if (props.filtered.length === ZERO) return <div ...>{props.translation("还没有记忆...")}</div>;
  return props.filtered.map((memory) => <MemoryListItem key={memory.id} {...props} memory={memory} />);
}
```

---

**verified**: False
**confidence**: high
**refuted_reason**: memory-management-dialog: 审计 拆分点 L121-140 和 L156-222 明确标注 [已单独模块] 声称 memory-dialog-footer.tsx 和 memory-list-item.tsx 已是独立文件, 但 Glob packages/web/components/chat/memory-*.tsx 只返回 memory-management-dialog.tsx 一个源码文件. 这两个组件当前都内联在 dialog 文件内, 不是已拆出. L62-84 / L93-98 / L106-111 声称 useMemoryApi / useMemoryFilter / useMemoryEdit 已抽 hook 也不成立, 实际是内联箭头函数. 预计减少 -79% 是基于这些 已存在 的拆分, 实际拆分后主文件大概率 ~268 行 (~-29%), 减少率虚高约 50 个百分点.

---

### `packages/service/src/permissions/router.py` (370 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/memory/service.py` (340 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/app/[locale]/admin/dicts/_components/admin-dicts-client.tsx` (334 行) — **PASS**

**1. 拆分点**:
- L36-38 常量 `FIRST_INDEX` / `DEFAULT_COUNT` -> `_lib/constants.ts`
- L52-87 `DictPageContent` 内容区 (activeCode -> items -> loading/empty) -> `dict-page-content.tsx` (component)
- L108-110 `extractErrorMsg` 纯函数 -> `_lib/error-utils.ts`
- L117-133 `callWithToast` 包装 toast handler -> `_lib/call-with-toast.ts` (泛型纯函数)
- L139-159 `doPatch` -> `_handlers/do-patch.ts`
- L164-186 `doDelete` -> `_handlers/do-delete.ts`
- L192-214 `doCreate` -> `_handlers/do-create.ts`
- L218-334 `AdminDictsClient` 主组件 -> 留 ~120 行

**2. 纯函数/hook 化**:
- 可拆:
  - `extractErrorMsg` L109-110 -> 模块级, 已 OK
  - `callWithToast` L118-133 -> 泛型 async 纯函数, 已 OK
  - `doPatch` / `doDelete` / `doCreate` L140-214 -> 模块级 async 纯函数, 已 OK
- 不可拆: `handlers` 对象 L238-245 (依赖闭包 setError), 必须留在主组件

**3. 库替代**:
- 项目封装 `<AppSelect>` / `<DataEmpty>` / `<ErrorBanner>` / `<PageHero>` 已用 OK
- shadcn `<PageGuard>` (components/page-guard.tsx) 已用 OK
- 无

**4. 对象替 if**:
- L72-87 `if (activeCode) <DictList/> else if (isLoading) <p/> else <DataEmpty/>` -> 3 个分支 1 渲染, 可改 `switchMap: Record<BranchKey, JSX>`, 但 readability 当前 OK
- L239-245 `handlers` 对象已是查表模式, OK

**5. 数组替循环**:
- L276 `(summaries.data ?? []).map(...)` 已 OK
- 无 for

**6. 预计减少**: 334 -> 主文件 ~120 (-64%); 拆到 7 个文件: dict-page-content.tsx (~50), `_lib/error-utils.ts` (~10), `_lib/call-with-toast.ts` (~25), `_handlers/do-patch.ts` (~30), `_handlers/do-delete.ts` (~30), `_handlers/do-create.ts` (~30)

**7. 骨架伪代码**:
- `_lib/call-with-toast.ts`:
```ts
import { toast } from "sonner";

export const callWithToast = async <TResult,>(
  action: () => Promise<TResult>,
  messages: { success: string; fallback: string },
  onError: (msg: string) => void,
): Promise<boolean> => { /* L118-133 */ };
```

- `dict-page-content.tsx`:
```tsx
import type { LookupItem, LookupItemPatchInput } from "@/lib/api/lookups";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { DictList } from "./dict-list";

interface DictPageContentProps { /* L53-71 props */ }
export function DictPageContent(props: DictPageContentProps): JSX.Element {
  if (props.activeCode) return <DictList {...props} />;
  if (props.isLoading) return <p className="text-sm text-muted-foreground">{props.translate("加载中…")}</p>;
  return <DataEmpty title={props.translate("暂无字典")} variant="page" />;
}
```

---

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/app/[locale]/knowledge/triples/_components/triples-form.tsx` (331 行) — **PASS**

**1. 拆分点**:
- L30-36 常量 / class string -> `_lib/constants.ts`
- L38-152 `useTriplesColumns` 列定义 hook (118 行) -> 留, 强耦合 schema + handlers + trans, 但可拆走 trans 表 `getColumnHeaders` 工厂
- L154-173 `Props` interface + `getSubmitLabel` 纯函数 -> 留
- L176-261 `TriplesForm` 主组件 -> 留 ~80 行
- L263-271 `TriplesResultProps` + L290-310 `TriplesResult` -> `triples-result.tsx` (component) [已分离了渲染]
- L312-331 `TriplesError` -> `triples-error.tsx` (component)
- L273-288 `TriplesHero` -> `triples-hero.tsx` (component) [但小, 可保留主组件内]

**2. 纯函数/hook 化**:
- 可拆:
  - `getSubmitLabel` L168-173 -> 模块级, 已 OK
- 不可拆:
  - `useTriplesColumns` L44-152 强依赖 useTranslations 返回类型 + handlers, 拆走需多传 3 个 props, ROI 低, 留 hook
  - `TriplesForm` JSX 内部用 `useTranslations` + `useRouter` + `useParams` + `useTripleForm` 全栈集成, 拆不出

**3. 库替代**:
- shadcn `<Card>` / `<CardContent>` / `<CardHeader>` / `<CardTitle>` 已用 OK
- shadcn `<Input>` / `<Button>` 已用 OK
- 项目封装 `<AppForm>` / `<AppSubmit>` (components/common/form) 已用 OK
- 项目封装 `<DataTable<T>>` 已用 OK
- 项目封装 `<ErrorBanner>` 已用 OK
- 项目封装 `<PageHero>` 已用 OK
- motion `AnimateUp` / `Reveal` / `AnimatePresence` 已用 OK
- 无

**4. 对象替 if**:
- L168-173 `pending ? "提交中…" : "批量提交"` -> 已三元, 可改 `SUBMIT_LABEL_MAP[pending]` 但太简单
- 无

**5. 数组替循环**:
- 无

**6. 预计减少**: 331 -> 主文件 ~150 (-55%); 拆到 3 个文件: triples-result.tsx (~40), triples-error.tsx (~30), triples-hero.tsx (~30) [可选]

**7. 骨架伪代码**:
- `triples-error.tsx`:
```tsx
import { AnimateUp } from "@/components/motion/animated";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";

export function TriplesError({ message }: { message: string }): JSX.Element {
  return (
    <AnimateUp show enterFromTop className="mt-4">
      <ErrorBanner
        variant="destructive"
        descriptionNode={
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {message.split("; ").map((msg, idx) => <li key={idx}>{msg}</li>)}
          </ul>
        }
        description=""
        dataTestid="triples-error"
      />
    </AnimateUp>
  );
}
```

- `triples-result.tsx`:
```tsx
import { AnimateUp } from "@/components/motion/animated";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

type ReviewStatus = "pending" | "approved" | "rejected";

export function TriplesResult({ approvalId, reviewStatus }: { approvalId: number; reviewStatus: ReviewStatus }): JSX.Element {
  const trans = useTranslations();
  return (
    <AnimateUp
      show
      enterFromTop
      data-testid="triples-result"
      className={cn("mt-4 rounded-lg border p-3 text-base", "border-moss/30 bg-moss/5 text-moss")}
    >
      {trans("已提交审核 #{id} (状态: {status})", { id: approvalId, status: reviewStatus })}
    </AnimateUp>
  );
}
```

---

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/lib/chat/use-chat-state.ts` (331 行) — **PASS**

**1. 拆分点**:
- L1-29 imports + 3 个本地常量 (DRAFT_KEY / ZERO_LEN / FIRST_INDEX) -> 顶部 imports 不拆, DRAFT_KEY 移到 const/
- L30-78 `ChatShellUiState` interface + `useChatShellUiState` hook (5 个 useState + useLocalStorage) -> `use-chat-shell-ui-state.ts` (~60 行)
- L80-136 `ServerDataParams` / `ServerData` interface + `serverConvToClient` helper + `useServerData` hook (5 个 TanStack Query) -> `use-server-data.ts` (~75 行)
- L138-250 `ChatShellChatParams` / `ChatShellChat` interface + `buildInitialMessages` helper + `useChatShellChat` hook (useConversation + useChatWithPersistence + UIMessage → flat Message 转换) -> `use-chat-shell-chat.ts` (~130 行)
- L252-266 兼容旧 API (`useChatShellState` deprecated + `removeConvLocal`) -> 留主文件或 `use-chat-state-compat.ts` (~30 行)
- L268-331 4 个 helper + `deleteConversationLocal` (`createLocalConv` / `pickNextConvId` / `CreateConvResult` interface / `doCreateServerConv` / `deleteConversationLocal`) -> `use-chat-state-helpers.ts` (~75 行)

**2. 纯函数/hook 化**: 可拆
- L103-109 `serverConvToClient` 已是 pure func (字段 mapping + toInstant), 可独立单测
- L166-191 `buildInitialMessages` 已是 pure func (3 个 if 分支), 可独立单测, 无副作用
- L275-285 `createLocalConv` 不是 pure (写 IDB via upsertConversation), 标 client-bff
- L312-323 `doCreateServerConv` 不是 pure (try/catch + mutateAsync), 标 client-bff
- L329-331 `deleteConversationLocal` 不是 pure (调 storageDelete 写 IDB), 标 client-bff

**3. 库替代**: ✅
- react-use 已装 (package.json:72) — L60 已用 `useLocalStorage` (项目既定), 保留
- zustand 已装 (package.json:81) — 不适用 (本文件无全局 store)
- zod 已装 (package.json:80) — 不适用 (无 input schema)
- es-toolkit 已装 (package.json:62) — `pick` 可替 `serverConvToClient` 内 `{ id, title, message_count, created_at, updated_at }` 字段 pick, 但只 5 字段, 显式 mapping 可读性更好, 不强推
- @tanstack/react-query 已装 (package.json:53) — 已用 (L116 `useConversations` 等)

**4. 对象替 if**: 部分可替
- L176-190 `buildInitialMessages` 内 `if (!isAccount || !currentDetail?.messages) return initialMessages; if (initialMessages.length > ZERO_LEN) return initialMessages; return ...map(...)` — 3 分支 (guard return + guard return + map), 前 2 个 guard return 不可替 (短路逻辑), 不构成 dispatch
- L181-183 `if (msg.role !== "system") { ({ role } = msg); }` — 1 行 if-else (三元违规), 简化为 `const role = msg.role === "system" ? "user" : msg.role;` 1 行

**5. 数组迭代替循环**: 部分可拆
- L224-237 `flatMessages = messages.map((uimsg) => {...})` 已用 map, 内部 `parts.filter(...).map(...).join("")` 已链式, 无显式循环
- L179-190 `currentDetail.messages.map((msg) => {...})` 已用 map
- 无 for / forEach / while

**6. 预计减少**: 331 -> ~75 (单文件 facade + 兼容), 拆分后单文件最大 ~130 行 (-77%)

**7. 骨架伪代码**:

- `use-chat-shell-ui-state.ts`:
```ts
// imports: 只列需要的 import
import { useState } from "react";
import { useLocalStorage } from "react-use";
import { DRAFT_KEY } from "@/const";

export interface ChatShellUiState;
export const useChatShellUiState: () => ChatShellUiState;
```

- `use-server-data.ts`:
```ts
// imports: 只列需要的 import
import { useConversations, useCreateConversation, useDeleteConversation, useRenameConversation, useAppendMessage } from "@/lib/chat/api";
import { computeEffectiveConversations } from "@/lib/chat/chat-utils";
import { toInstant } from "@/lib/date";
import type { Conversation } from "@/lib/chat/types";

export interface ServerDataParams;
export interface ServerData;
const serverConvToClient: (server: ServerConversation) => Conversation;
export const useServerData: (params: ServerDataParams) => ServerData;
```

- `use-chat-shell-chat.ts`:
```ts
// imports: 只列需要的 import
import { useConversation } from "@/lib/chat/api";
import { useChatWithPersistence } from "@/lib/chat/use-chat-with-persistence";
import { nowMs, toInstant } from "@/lib/date";
import type { ChatFile, Conversation, Message } from "@/lib/chat/types";
import type { ServerConversationDetail } from "@/lib/chat/api";

export interface ChatShellChatParams;
export interface ChatShellChat;
const buildInitialMessages: (isAccount: boolean, currentDetail: ServerConversationDetail | undefined, initialMessages: Message[]) => Message[];
export const useChatShellChat: (params: ChatShellChatParams) => ChatShellChat;
```

- `use-chat-state-helpers.ts`:
```ts
// imports: 只列需要的 import
import { useCreateConversation } from "@/lib/chat/api";
import { deleteConversation as storageDelete, upsertConversation } from "@/lib/chat/storage";
import { getNextConversationId, newId } from "@/lib/chat/chat-utils";
import { log } from "@/lib/log";
import { nowMs } from "@/lib/date";
import type { Conversation } from "@/lib/chat/types";
import type { ChatShellUiState } from "./use-chat-shell-ui-state";

const TITLE_LEN: number;
const FIRST_INDEX: number;
export const createLocalConv: (text: string) => Conversation;
export const pickNextConvId: (effectiveConversations: Conversation[], deletedId: string) => string | null;
export interface CreateConvResult;
export const doCreateServerConv: (args: {...}) => Promise<CreateConvResult>;
export const deleteConversationLocal: (targetId: string) => void;
```

---

## 汇总

| 文件 | 当前行数 | 拆分目标 | 拆分后最大单文件 | 减幅 |
|------|----------|----------|------------------|------|
| lib/api/pre-analysis.ts | 585 | 5 文件 | ~138 行 | -74% |
| lib/api/knowledge.ts | 502 | 4 文件 | ~180 行 | -80% |
| lib/date.ts | 450 | 8 文件 + 1 facade | ~95 行 | -73% |
| lib/chat/use-chat-state.ts | 331 | 4 文件 + 1 compat | ~130 行 | -77% |
| **总计** | **1868** | **~22 文件** | **~180 行 (最大)** | **平均 -76%** |

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/eval/router.py` (323 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/components/theme-provider.tsx` (322 行) — **PASS**

**1. 拆分点**:
- L33-38 常量 `STORAGE_KEY` / `FOUC_MARKER` / `LIGHT` / `DARK` / `SYSTEM` / `MEDIA` -> 留, 模块级
- L41-50 `ThemeName` type + `ThemeContextValue` interface -> 留 types 段
- L52-62 `ThemeValueContext` + L64-66 `ThemeDispatchContext` createContext -> 留, 强耦合
- L70-88 `Props` interface -> 留
- L92-208 helpers 段 (`getSystemTheme` / `readStored` / `writeStored` / `isServer` / `isValidTheme` / `getInitialTheme` / `resolveTheme` / `applyToHtml` / `isTestEnv` / `injectFoucScript`) -> 拆到 `_lib/theme-storage.ts` (storage helpers: readStored/writeStored/isServer) + `_lib/theme-resolve.ts` (getSystemTheme/resolveTheme/applyToHtml/isValidTheme) + `_lib/fouc-inject.ts` (isTestEnv/injectFoucScript) [3 文件 ~70-100 行]
- L212-312 `ThemeProvider` 主组件 -> 留 ~150 行 (含 hooks + media query + FOUC useEffect)
- L314-322 `useTheme` hook -> 留

**2. 纯函数/hook 化**:
- 可拆:
  - L92-102 `getSystemTheme` -> 模块级, 已 OK
  - L104-110 `readStored` -> 模块级, 已 OK
  - L112-118 `writeStored` -> 模块级, 已 OK
  - L120 `isServer` -> 模块级, 已 OK
  - L131-136 `isValidTheme` -> 模块级, 已 OK
  - L139-148 `getInitialTheme` -> 模块级, 已 OK
  - L151-162 `resolveTheme` -> 模块级, 已 OK
  - L165-171 `applyToHtml` -> 模块级, 已 OK
  - L176-178 `isTestEnv` -> 模块级, 已 OK
  - L181-208 `injectFoucScript` -> 模块级, 已 OK
- 不可拆: `ThemeProvider` 内 setTheme 函数体 / 3 个 useEffect 必须留主组件

**3. 库替代**:
- 无 — 自实现是 project spec [feedback-next-themes-dead-use-self-implement.md] 的强制选择
- 已用 react-use `useEvent` (L291), OK

**4. 对象替 if**:
- L131-136 `if (val === LIGHT || val === DARK) return true; return enableSystem && val === SYSTEM;` 可改 `validators[enableSystem ? "withSystem" : "basic"]`, 但仅 2 分支, ROI 低
- L144-146 `stored === LIGHT || stored === DARK || stored === SYSTEM` 链 -> 不可改 map, 因为是 whitelist guard

**5. 数组替循环**:
- 无

**6. 预计减少**: 322 -> 主文件 ~150 (-53%); 拆到 3 个 lib 文件: theme-storage.ts (~25), theme-resolve.ts (~50), fouc-inject.ts (~45)

**7. 骨架伪代码**:
- `_lib/theme-storage.ts`:
```ts
const STORAGE_KEY = "theme";
const isServer = (): boolean => typeof globalThis === "undefined";
const readStored = (key: string): string | null => { /* L104-110 */ };
const writeStored = (key: string, value: string) => { /* L112-118 */ };
export { readStored, writeStored, isServer, STORAGE_KEY };
```

- `_lib/fouc-inject.ts`:
```ts
const FOUC_MARKER = "data-theme-fouc";
const isTestEnv = (): boolean =>
  typeof process !== "undefined" &&
  (process.env.VITEST === "true" || process.env.NODE_ENV === "test");

export const injectFoucScript = (storageKey: string, enableSystem: boolean) => { /* L181-208 */ };
```

---

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/service/src/retrieval/vector_store.py` (317 行) — **REFUTED**

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

**verified**: False
**confidence**: high
**refuted_reason**: vector_store.py: audit 在 8 段中 7 段标 保留, 真正能拆的仅 _delete_helpers.py (~22 行, L196-217). 即使抽 22 行 + import boilerplate, 实际减少到 ~295 行 (-7%), 远低于声称的 220 行 (-31%). -31% 减幅虚高 4 倍多, 跟 audit 自己逐段 保留 决定矛盾.

---

### `packages/service/src/health/checks.py` (316 行) — **PASS**

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

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/app/[locale]/decode/page.tsx` (312 行) — **PASS**

**1. 拆分点**:
- L22-25 常量 `EXAMPLE` / `JSON_INDENT` -> 留模块级
- L27-46 `DecodeResult` type -> `_lib/types.ts`
- L48-58 `buildCopyText` 纯函数 -> `_lib/build-copy-text.ts`
- L60-72 `filterMainFields` 纯函数 -> `_lib/filter-main-fields.ts`
- L74-84 `formatDecodeError` 纯函数 -> `_lib/format-decode-error.ts`
- L100-151 `useDecodeActions` hook (含 useEvent) -> `_hooks/use-decode-actions.ts` (hook) [已抽 hook, OK]
- L155-166 `DecodePage` default export -> 留
- L168-312 `DecodePageInner` 主组件 -> 留 ~120-150 行
- 副组件: L233-286 结果 Header (name + manufacturer + prefix + view toggle + CopyButton) -> `decode-result-header.tsx` (component)
- 副组件: L289-305 字段网格 / LLM 视图 -> `decode-result-body.tsx` (component)

**2. 纯函数/hook 化**:
- 可拆:
  - `buildCopyText` L54-59 -> 模块级纯函数, 已 OK
  - `filterMainFields` L66-73 -> 模块级纯函数, 已 OK
  - `formatDecodeError` L80-85 -> 模块级纯函数, 已 OK
  - `useDecodeActions` L100-151 -> 已抽 hook, OK
- 不可拆: `useDecodeActions` 内 `copyJSON` 写空函数, 可删 (181 行无操作), UI 逻辑走 CopyButton, ROI 中

**3. 库替代**:
- 项目封装 `<AppToggle>` / `<CopyButton>` / `<ErrorBanner>` / `<PageHero>` / `<GuardClient>` 已用 OK
- react-use `useEvent` / `useLocalStorage` / `useToggle` 已用 OK
- shadcn `<Input>` / `<Button>` 已用 OK (在子组件中)
- 副组件 `<DecodeInputBar>` / `<DecodeField>` / `<SeriesDialog>` 已抽到独立文件, OK
- 无

**4. 对象替 if**:
- L55-58 `if (view === "llm") return ...; return JSON.stringify(...)` 已经是 2 分支, 改 map 可能更乱
- 无

**5. 数组替循环**:
- L291-295 `filterMainFields(result).map(([key, value]) => <StaggerItem>...</StaggerItem>)` 已 OK

**6. 预计减少**: 312 -> 主文件 ~130 (-58%); 拆到 6 个文件: use-decode-actions.ts (~60), `_lib/build-copy-text.ts` (~15), `_lib/filter-main-fields.ts` (~20), `_lib/format-decode-error.ts` (~15), `_lib/types.ts` (~20), decode-result-header.tsx (~60), decode-result-body.tsx (~50)

**7. 骨架伪代码**:
- `_hooks/use-decode-actions.ts`:
```ts
import { useEvent } from "react-use";
import { decode } from "@/lib/api/system";
import { formatDecodeError } from "../_lib/format-decode-error";

interface UseDecodeActionsArgs { /* 8 props */ }
export function useDecodeActions(props: UseDecodeActionsArgs): { submit: () => void; fillExample: () => void; copyJSON: () => Promise<void>; } { /* L100-151 */ }
```

- `decode-result-header.tsx`:
```tsx
import { AppToggle } from "@/components/common/input/app-toggle";
import { CopyButton } from "@/components/common/button/app-copy-button";

export function DecodeResultHeader(props: {
  result: DecodeResult;
  view: "cards" | "llm";
  onViewChange: (next: "cards" | "llm") => void;
  copyText: string;
  translate: (key: string) => string;
}): JSX.Element { /* L246-286 */ }
```

---

**verified**: True
**confidence**: high
**refuted_reason**: null

---

### `packages/web/app/[locale]/_actions/knowledge.ts` (311 行) — **REFUTED**

**1. 拆分点**:
- L14-15 `ActionResult<T>` type -> `_lib/types.ts`
- L17-76 `createQA` (+ 2 interfaces `QAInput` / `QAResult`) -> `_actions/knowledge/create-qa.ts` (server-only)
- L78-142 `createTriples` (+ 2 interfaces) -> `_actions/knowledge/create-triples.ts`
- L144-206 `commitDocuments` (+ 2 interfaces) -> `_actions/knowledge/commit-documents.ts`
- L208-268 `optimizeAnswer` (+ 2 interfaces) -> `_actions/knowledge/optimize-answer.ts`
- L270-311 `likeAnswer` (+ 2 interfaces) -> `_actions/knowledge/like-answer.ts`
- 留: 当前文件只剩 barrel `export * from ...`, 极薄

**2. 纯函数/hook 化**:
- 可拆:
  - 5 个 action 函数都是 `async (input) => { try { submit(...) } catch { actionError(...) }}` 模式, 已模块级, OK
- 不可拆: 都是 server action, 拆分到独立文件以 `_actions/knowledge/` 子目录组织, 不抽 hook (server action 不能 hook)

**3. 库替代**:
- 无 — server actions 没有更高层封装
- `/lib/api/approvals` submit 已用 OK
- `/lib/actions-utils` actionError 已用 OK

**4. 对象替 if**:
- L52 `if (!input.dataset_id || !input.question || !input.answer)` 链 -> 可改 `["dataset_id", "question", "answer"].every(key => input[key])`, ROI 低, 留
- L186 `if (!input.dataset_id || !Array.isArray(input.rows))` 同
- L245 `if (!input.dataset_id || !input.question || !input.improved_answer)` 同
- L297 `if (!input.question || !input.answer || !input.messageId)` 同
- 所有 try/catch 都走 `actionError(error)` 工具, OK

**5. 数组替循环**:
- 无

**6. 预计减少**: 311 -> 5 个子文件每个 ~50-70 行; 当前文件留 barrel ~20 行 (-94%)

**7. 骨架伪代码**:
- `_actions/knowledge/create-qa.ts`:
```ts
"use server";
import { submit } from "@/lib/api/approvals";
import { actionError } from "@/lib/actions-utils";
import { revalidatePath } from "next/cache";
import type { ActionResult } from "./_lib/types";

interface QAInput {
  dataset_id: string;
  question: string;
  answer: string;
  tags?: string[];
  sync_to_neo4j?: boolean;
}
interface QAResult {
  approval_id: number;
  review_status: "pending" | "approved" | "rejected";
  apply_status: "none" | "applied" | "failed";
}

export const createQA = async (input: QAInput): Promise<ActionResult<QAResult>> => { /* L48-76 */ };
```

- `_actions/knowledge/_lib/types.ts`:
```ts
export type ActionResult<TData> = { ok: true; data: TData } | { ok: false; error: string };
```

---

**verified**: False
**confidence**: high
**refuted_reason**: _actions/knowledge.ts: audit 拆分点行号 (L14-15/L17-76/L78-142/L144-206/L208-268/L270-311) 跟实际文件完全对得上, 5 个 action 拆分子目录结构合理. 但 预计减少 311 -> ~20 barrel (-94%) 是错误指标: 拆分到 5 个子文件 + barrel 总 LOC 不会减少, 只会从 311 行分散到 5×~60 + ~15 barrel = ~315 行 (新增 import/use server/JSDoc 头反而略增). -94% 是 当前文件瘦身 而非 总代码减少, 把度量对象偷换了.

---

### `packages/web/components/common/table/data-table.tsx` (308 行) — **REFUTED**

**1. 拆分点**:
- L28-40 `resolveMaxHeight` -> 留 `_lib/max-height.ts`
- L42-98 列宽工具 (`getFlexColStyle` / `getStringColStyle` / `getColStyle`) -> 拆到 `_lib/col-style.ts` [project: 列宽是通用能力, 抽出后 DataTableBody 也可复用]
- L100-109 `TanstackColumnMeta` + L111 `ColumnDef` type alias + L114-151 `DataTableProps` interface -> 留 types 段 L100-151
- L153-208 `buildTableOptions` 纯函数 -> 留, 已抽 OK
- L210-308 `DataTable` 主组件 -> 留 ~100 行

**2. 纯函数/hook 化**:
- 可拆:
  - `resolveMaxHeight` L32-40 -> 模块级纯函数, 已 OK
  - `getFlexColStyle` L58-64 -> 模块级纯函数, 已 OK
  - `getStringColStyle` L71-79 -> 模块级纯函数, 已 OK
  - `getColStyle` L87-98 -> 模块级纯函数, 已 OK
  - `buildTableOptions` L173-208 -> 模块级纯函数, 已 OK
- 不可拆: `DataTable` 内 `handleChangePage` L242-248 用了闭包 `table.setPageIndex`, 必须留主组件

**3. 库替代**:
- @tanstack/react-table `useReactTable` / `getCoreRowModel` / `getPaginationRowModel` / `flexRender` 已用 OK
- shadcn `<Table>` / `<TableBody>` / `<TableHead>` / `<TableHeader>` / `<TableRow>` 已用 OK
- 项目封装 `DataEmpty` / `DataTableBody` / `DataTablePagination` / `apply-pagination-updater` 已用 OK
- 无

**4. 对象替 if**:
- L33-40 `if (!maxHeight || maxHeight === "auto") return undefined; if (typeof === "number") return ...px; return maxHeight;` -> 是 3-branch type 派发, 不可改 map
- L88-98 type 派发, 同
- 无

**5. 数组替循环**:
- L271-290 `.map((headerGroup) => ...)` 已 OK
- L273-288 `.map((header) => ...)` 已 OK
- 无

**6. 预计减少**: 308 -> 主文件 ~140 (-55%); 拆到 2 个 lib 文件: max-height.ts (~15), col-style.ts (~80)

**7. 骨架伪代码**:
- `_lib/col-style.ts`:
```ts
import type { CSSProperties } from "react";
import type { ColumnWidth } from "@/components/common/table/data-table-types";

const getFlexColStyle = (width: { max?: number; min: number }): CSSProperties => { /* L58-64 */ };
const getStringColStyle = (width: string): CSSProperties => { /* L71-79 */ };
export const getColStyle = (width: ColumnWidth | undefined): CSSProperties | undefined => { /* L87-98 */ };
```

- `_lib/max-height.ts`:
```ts
export const resolveMaxHeight = (maxHeight: string | number | undefined): string | undefined => { /* L32-40 */ };
```

---

**verified**: False
**confidence**: high
**refuted_reason**: data-table.tsx: audit 自己列出的留段加起来是 ~208 行 (types L100-151 ~52 + buildTableOptions L153-208 ~56 + DataTable 主组件 L210-308 ~100), 跟声称的主文件 ~140 行差 ~68 行; 实际减少约 -32%, 不是 -55%, 虚高约 23 个百分点. 拆点行号 (L28-40 / L42-98 / L100-151 / L153-208 / L210-308 / L242-248 / L271-290) 全对, 308 行拆 max-height.ts + col-style.ts 2 个 lib 可行, 但减幅估计存在内部算术错误.

---

### `packages/service/src/auth/account_settings_service.py` (307 行) — **REFUTED**

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

**verified**: False
**confidence**: high
**refuted_reason**: account_settings_service.py: 拆分 module 不合理. 12 处 import 必须改路径 + 8 个测试文件的 mock patch 路径全部要改 (每文件平均 5-10 处 mock patch = 40-80 处路径重写). 拆后总行数不降反升: 307 + 6 × module header + 50+ 行 mock patch 改动 约 +30~50 行. finding 第 5 点 数组迭代替循环 是 SQLAlchemy ORM 错建议, setattr + list-comprehension 不会触发 session.flush, 失去 ORM 语义. 当前 307 行结构合理, 函数粒度已经够细, 8 个测试文件 (test_avatar/test_deletion/test_email 等) 已按子域组织, 但 import 都从一个 service 文件 import 是有意为之的 测试按域分组, service 共享入口, 拆 module 破坏稳定结构.

---

### `packages/service/src/chat/router.py` (305 行) — **PASS**

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

**verified**: True
**confidence**: medium
**refuted_reason**: null

---

### `packages/web/app/[locale]/output/[task_id]/_components/task-detail-client.tsx` (304 行) — **PASS**

**1. 拆分点**:
- L28 `POLL_INTERVAL` 常量 -> 留模块级
- L30-40 `extractErrorMessage` 纯函数 -> `_lib/error-utils.ts`
- L42-52 `resolveError` 纯函数 -> `_lib/error-utils.ts` (跟上面一起)
- L62-94 `useTaskDownload` hook -> `_hooks/use-task-download.ts` (hook) [已抽 hook]
- L96-125 `useTaskCancel` hook -> `_hooks/use-task-cancel.ts` (hook) [已抽 hook]
- L183-255 `BodyContentSwitch` (错误/loading/有 task 三分支) -> `body-content-switch.tsx` (component)
- L256-304 `OutputPanel` (产物表 + 取消 + 下载) -> `output-panel.tsx` (component)
- L133-183 `TaskDetailClient` 主组件 -> 留 ~50 行

**2. 纯函数/hook 化**:
- 可拆:
  - `extractErrorMessage` L35-40 -> 模块级纯函数, 已 OK
  - `resolveError` L47-52 -> 模块级纯函数, 已 OK
  - `useTaskDownload` L72-94 -> 已抽 hook, OK
  - `useTaskCancel` L104-125 -> 已抽 hook, OK
- 不可拆: 主组件 `TaskDetailClient` 集成 useQuery + 2 hook + ErrorBanner state, 拆走 ROI 低

**3. 库替代**:
- @tanstack/react-query `useQuery` 已用 OK
- 项目封装 `<BackLink>` / `<ErrorBanner>` 已用 OK
- shadcn `<Card>` / `<CardContent>` / `<Button>` 已用 OK (子组件中)
- motion `FadePresence` / `Reveal` 已用 OK
- 子组件 `<TaskInfo>` / `<TaskFiles>` / `<TaskDownload>` 已经抽到独立文件, OK
- 无

**4. 对象替 if**:
- L140-146 `refetchInterval` 用函数返 `false | number`, 已 OK
- L222-241 `if (displayError) ... else if (!task) ... else <OutputPanel/>` 3 分支, 不可改 map (各自 UI 差异大)
- 无

**5. 数组替循环**:
- 无

**6. 预计减少**: 304 -> 主文件 ~50 (-84%); 拆到 6 个文件: use-task-download.ts (~30), use-task-cancel.ts (~30), `_lib/error-utils.ts` (~30), body-content-switch.tsx (~80), output-panel.tsx (~80)

**7. 骨架伪代码**:
- `_hooks/use-task-cancel.ts`:
```ts
import { useState, useTransition } from "react";
import { cancelTask } from "@/app/[locale]/_actions/output";
import type { useTranslations } from "next-intl";

export function useTaskCancel(taskId: string, translate: ReturnType<typeof useTranslations>, setCancelError: (msg: string | null) => void): {
  cancelPending: boolean;
  cancelling: boolean;
  onCancelSubmit: () => void;
} { /* L104-125 */ }
```

- `body-content-switch.tsx`:
```tsx
import { ErrorBanner } from "@/components/common";
import { Button } from "@/components/ui/button";
import type { IngestTask } from "@/lib/api";
import { OutputPanel } from "./output-panel";

interface BodyContentSwitchProps { /* L199-220 props */ }
export function BodyContentSwitch(props: BodyContentSwitchProps): JSX.Element {
  if (props.displayError) return <ErrorBanner variant="destructive" description={props.displayError} action={<Button onClick={() => { props.setDownloadError(null); props.setCancelError(null); }}>{props.translate("重试")}</Button>} />;
  if (!props.task) return <div className="text-base text-muted-foreground">{props.translate("加载中…")}</div>;
  return <OutputPanel {...props} />;
}
```

---

## 横向总结

**verified**: True
**confidence**: medium
**refuted_reason**: null

---

## 总结与建议

**通过的 27 个文件** 可直接进入 refactor spec, 按优先级排:
1. **P0 (>= 800 行)**: kg/router.py (1040), camelot_extractor.py (999) — 但 kg/router.py 的拆分粒度需调整 (reduction -73% 不可信)
2. **P1 (400-800 行)**: pdf_processing/router.py (743), object_store.py (598) [refuted, 维持现状], pre_analysis/router.py (568), lookups/admin_router.py (562), pdf_processing/cad.py (512) [refuted, -55% 而不是 -75%], pre-analysis.ts (585) [refuted, 删 handleError 不可行], knowledge.ts (502) [refuted, handleError 不存在], neo4j_import.py (499) [refuted, CLI 不应拆]
3. **P2 (300-400 行)**: 17 个, 多数 router 单文件按 endpoint 拆即可

**refuted 的 15 个文件**: 不建议按 audit 提议拆分, 原因各异:
- **行号错 / 函数不存在**: kg/router, knowledge.ts (handleError 错位), upload-dialog (renderParamInput 实际被引用)
- **reduction 虚高**: pipeline (-37% → -14%), data-table (-55% → -32%), vector_store (-31% → -7%), cad (-75% → -55%), account_settings_service (-84% → 净增 30~50 行)
- **破坏既有契约**: config/settings (破坏 lazy reload 单测), knowledge action (-94% 错把度量对象偷换), account_settings (破坏 8 测试 mock 路径)
- **已结构性完成**: object_store (factory 3 分支不值得 dict lookup, lazy import 已做)

## 后续建议

1. 把 `verified=true` 的 27 个文件按优先级排 refactor spec (P0/P1/P2)
2. 对 `verified=false` 的 15 个文件, 重新设计 finding (不删原段, 标 refuted 后由 refactor author 重新审视)
3. 7 段格式 + verifier 阶段保留, 在每次大改动前复跑