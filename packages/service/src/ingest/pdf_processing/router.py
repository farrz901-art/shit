"""Ingest HTTP API (2026-06-10)

为前端 /output 页提供上传 + 后台转换 + 产物查询 + zip 下载。
复用 process_path() 业务层零改动。
"""

# ruff: noqa: E402  # 故意: `from . import store as _store` 放在 dataclass/IngestTask 定义之后 (避免循环)
from __future__ import annotations

import io
import logging
import re
import traceback
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from ...common.task_id import TASK_PREFIX_INGEST, make_task_id
from ...core.audit import audited
from ...middleware.auth import CurrentUser, resolve_user  # noqa: F401  # resolve_user 留作依赖回退
from ...permissions.guards import (  # noqa: F401  # (2026-06-17) v2 RBAC 走 page-level 鉴权
    require_page,
    require_super_admin,
)
from ...storage.object_store import get_object_store
from .pipeline import process_path, process_uri
from .schemas_presign import (
    FinalizeUploadRequest,
    FinalizeUploadResponse,
    PresignUploadItem,
    PresignUploadRequest,
    PresignUploadResponse,
)

_logger = logging.getLogger(__name__)

# 仓库根: src/ingest/pdf_processing/router.py 上溯 3 层 (python 项目根 = packages/service/)
_REPO_ROOT = Path(__file__).resolve().parents[3]

# 上传工作区根 (跟 output/ pdfs/ data/ 同级, 在 .gitignore)
UPLOAD_ROOT = _REPO_ROOT / "ingest_uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# 路径白名单 (跟 pipeline.py 业务层保持一致)
ALLOWED_EXTS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".webp",
    ".docx",
    ".xlsx",
    ".pptx",
    ".html",
    ".htm",
    ".dxf",
    ".dwg",
    ".zip",
}
MAX_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MB / task
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB / file

# name 白名单 (跟 src/rag/product_decoders/output_api.py 一致)
SAFE_NAME = re.compile(r"^[a-zA-Z0-9._/-]+$")

# (2026-06-11) task 持久化改 SQLite (src/rag/ingest/store.py), 重启不丢; 旧 in-memory
# `tasks: dict` 保留作进程内 cache, 写入/读取都走 store + 这个 cache 兜底
from sqlalchemy import select

from ...storage import session_scope
from ..common import _check_token, _uri_for_backend, user_hash_for
from . import store as _store
from .models import IngestTask as ORMIngestTask

tasks: dict[str, IngestTask] = {}


def _dict_to_task(d: dict) -> IngestTask:
    """store.load_task_dict 输出 → IngestTask. datetime / Path / 子 dataclass 重建."""
    return IngestTask(
        id=d["id"],
        user_hash=d["user_hash"],
        state=d["state"],
        total_files=d["total_files"],
        processed=d["processed"],
        failed=d["failed"],
        started_at=datetime.fromisoformat(d["started_at"]),
        finished_at=datetime.fromisoformat(d["finished_at"]) if d["finished_at"] else None,
        error=d["error"],
        work_dir=Path(d["work_dir"]) if d["work_dir"] else None,
        input_files=[InputFile(**f) for f in d.get("input_files", [])],
        output_files=[OutputFile(**f) for f in d.get("output_files", [])],
    )


def _save(t: IngestTask) -> None:
    """写穿到 SQLite + 更新进程内 cache"""
    _store.save_task_dict(t.to_dict())
    tasks[t.id] = t


def _load(task_id: str) -> IngestTask | None:
    """先看进程内 cache, 没了再从 store 拉"""
    t = tasks.get(task_id)
    if t is not None:
        return t
    d = _store.load_task_dict(task_id)
    if d is None:
        return None
    t = _dict_to_task(d)
    tasks[task_id] = t
    return t


def _list_user(uhash: str) -> list[IngestTask]:
    """列用户任务, 按 started_at DESC. store 是真源, 进程内 cache 仅热路径用"""
    return [_dict_to_task(d) for d in _store.list_user_task_dicts(uhash)]


def _new_task_id() -> str:
    """任务 ID: 走中央 make_task_id, 格式 ig_{YYYYMMDD}{HHMMSS}_{6hex}"""
    return make_task_id(TASK_PREFIX_INGEST)


@dataclass
class OutputFile:
    """产物文件描述 (内存 + JSON)"""

    name: str
    size: int
    mime: str
    error: str | None = None
    uri: str = ""  # (2026-06-16) 新增, ABC 拼出

    def to_dict(self) -> dict:
        return {"name": self.name, "size": self.size, "mime": self.mime, "error": self.error, "uri": self.uri}


@dataclass
class InputFile:
    """(2026-06-11) 用户上传的原始文件描述 — 跟 OutputFile 区分, 供前端 /output 列表展示「上传的文件名」"""

    name: str
    size: int
    mime: str
    uri: str = ""  # (2026-06-16) 新增, ABC 拼出

    def to_dict(self) -> dict:
        return {"name": self.name, "size": self.size, "mime": self.mime, "uri": self.uri}


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
    input_files: list[InputFile] = field(default_factory=list)  # (2026-06-11) 新增
    output_files: list[OutputFile] = field(default_factory=list)
    work_dir: str | Path | None = None  # 测试要用, 别忘了. (2026-06-16) 也接 URI 字符串 (s3:// / local://)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_hash": self.user_hash,
            "state": self.state,
            "total_files": self.total_files,
            "processed": self.processed,
            "failed": self.failed,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
            "work_dir": str(self.work_dir) if self.work_dir else None,
            "input_files": [f.to_dict() for f in self.input_files],
            "output_files": [f.to_dict() for f in self.output_files],
        }


# MIME 推断
_MIME_MAP = {
    ".md": "text/markdown",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".txt": "text/plain",
    ".pdf": "application/pdf",
}


def _mime_for(path: Path) -> str:
    return _MIME_MAP.get(path.suffix.lower(), "application/octet-stream")


def _resolve_task(task_id: str, user_hash: str) -> IngestTask:
    """查 task + 跨用户 404. 走 _load (cache + store) 而非直接 tasks.get,
    保证重启后旧任务 (cache miss, store hit) 也能查到"""
    t = _load(task_id)
    if t is None or t.user_hash != user_hash:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return t


def _collect_output_files_legacy(output_dir: Path) -> list[OutputFile]:
    """(2026-06-16) 旧 Path-based 实现保留给 T4.3 重构前的过渡代码用.
    (2026-06-11) name 用 rel.name (裸文件名) 而非 str(rel) (含路径分隔符)
    原因: pipeline 把产物写到 output/{input_stem}/ 子目录, str(rel) 在 Windows 上是
    'easy_pdf_test\\\\easy_pdf_test.md' 含反斜杠, 前端 URL 编码后变 %5C, 后端 SAFE_NAME 拒绝
    改用裸文件名 + read endpoint 按 basename 递归搜, 让前端用干净的文件名查"""
    if not output_dir.exists():
        return []
    out: list[OutputFile] = []
    for p in sorted(output_dir.rglob("*")):
        if not p.is_file():
            continue
        out.append(OutputFile(name=p.name, size=p.stat().st_size, mime=_mime_for(p)))
    return out


def _find_output_file(output_dir: Path, name: str) -> Path | None:
    """按 basename 在 output_dir 下递归找第一个匹配的文件
    (2026-06-11) 配合 _collect_output_files 用 rel.name 存名, 这里按裸名搜
    多个同名 → 返回第一个 (sorted 顺序, 可重现)
    安全: 验 match 实际在 output_dir 之下, 防 rglob('..') 越权"""
    output_dir = output_dir.resolve()
    for p in sorted(output_dir.rglob(name)):
        if p.is_file() and p.is_relative_to(output_dir):
            return p
    return None


# ---------- 路由 ----------

ingest_router = APIRouter(prefix="/api/ingest", tags=["ingest"])


# ============== (2026-06-16) presign / finalize 端点 ==============


def _build_workdir_uri(uhash: str, task_id: str, backend: str) -> str:
    """task work_dir URI. backend 决定 scheme.
    - local: local://inputs/{task_id}/
    - s3 (含 minio impl): s3://{bucket}/inputs/{task_id}/

    注意: backend 名跟 ObjectStore URI scheme 不一一对应.
    MinioObjectStore.backend_name() 返 'minio', 但 URI scheme 必须是 's3' + bucket.
    任何业务拼 URI 都应走 _uri_for_backend 或本 helper, 禁止直拼.
    """
    return _uri_for_backend(backend, f"inputs/{task_id}/")


@ingest_router.post(
    "/upload/presign",
    response_model=PresignUploadResponse,
    summary="签上传 PUT URL",
    description=(
        "## 用途\n\n"
        "为前端直传 MinIO / S3 签发一组 PUT URL, 拿到 URL 后前端绕过 backend 直接上传 bytes, 节省后端带宽.\n\n"
        "## 鉴权\n\n"
        '`require_page("output")` 守卫.\n\n'
        "## 行为\n\n"
        "1. 校验每个文件: 扩展名必须在 `ALLOWED_EXTS` 内 (pdf/jpg/png/docx/xlsx/pptx/html/dxf/dwg/zip 等), 单文件 ≤ 50MB.\n"
        "2. 校验总大小: 任务总 ≤ 200MB. 超过任一上限 → 413.\n"
        "3. 创建 IngestTask (state=queued), `work_dir` 走 ABC: `s3://{bucket}/inputs/{task_id}/` 或 `local://inputs/{task_id}/`.\n"
        "4. 对每个文件签发 presigned PUT URL, 写入 `uploads[]`."
    ),
    responses={
        200: {"description": "{task_id, uploads: [{name, uri, put_url, mime}, ...]}"},
        400: {"description": "扩展名不在白名单"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "output")'},
        413: {"description": "单文件 > 50MB 或任务总 > 200MB"},
        422: {"description": "Pydantic 校验失败"},
    },
)
async def presign_upload(
    req: PresignUploadRequest,
    current: CurrentUser = Depends(require_page("output")),
) -> PresignUploadResponse:
    token = _check_token(current)
    uhash = user_hash_for(token)

    total_size = 0
    for f in req.files:
        ext = Path(f.name).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(400, detail=f"不支持的格式: {ext or '(无扩展名)'}")
        if f.size > MAX_FILE_SIZE:
            raise HTTPException(413, detail=f"文件太大: {f.name} 超过 {MAX_FILE_SIZE // (1024 * 1024)} MB")
        total_size += f.size
    if total_size > MAX_UPLOAD_SIZE:
        raise HTTPException(413, detail=f"任务总大小超限 ({MAX_UPLOAD_SIZE // (1024 * 1024)} MB)")

    store = get_object_store()
    task_id = _new_task_id()
    workdir_uri = _build_workdir_uri(uhash, task_id, store.backend_name())
    task = IngestTask(
        id=task_id,
        user_hash=uhash,
        state="queued",
        total_files=len(req.files),
        work_dir=workdir_uri,
    )
    _save(task)

    uploads: list[PresignUploadItem] = []
    for f in req.files:
        uri = f"{workdir_uri}input/{Path(f.name).name}"
        put_url = store.presign_put(uri)
        uploads.append(PresignUploadItem(name=f.name, uri=uri, put_url=put_url, mime=f.mime))

    return PresignUploadResponse(task_id=task_id, uploads=uploads)


@ingest_router.post(
    "/upload/finalize",
    response_model=FinalizeUploadResponse,
    summary="启动 Ingest 后台任务",
    description=(
        "## 用途\n\n"
        "前端用 `/upload/presign` 拿到的 URL 把所有文件 PUT 到 MinIO/S3 完成后, 调此端点启动 Ingest 后台处理.\n\n"
        "## 鉴权\n\n"
        '`require_page("output")` 守卫.\n\n'
        "## 行为\n\n"
        "1. 校验 task 存在且归当前用户 (跨用户 404).\n"
        "2. 校验 task state 必须是 `queued`; 其他状态 (running/completed/failed) → 409.\n"
        "3. `BackgroundTasks` 调度 `_run_ingest`: 走 ABC `process_uri()` 跑 pipeline (extraction / chunking / embedding / graph 写入等).\n"
        "4. 立即返 `{task_id, state: running}`; 前端轮询 `/api/ingest/tasks/{id}` 看进度."
    ),
    responses={
        200: {"description": "{task_id, state: running}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "output")'},
        404: {"description": "task 不存在或非当前用户"},
        409: {"description": "task 状态非 queued (已在跑 / 已完成 / 已失败)"},
        422: {"description": "Pydantic 校验失败"},
    },
)
async def finalize_upload(
    req: FinalizeUploadRequest,
    current: CurrentUser = Depends(require_page("output")),
    background: BackgroundTasks = BackgroundTasks(),  # FastAPI 注入
) -> FinalizeUploadResponse:
    token = _check_token(current)
    uhash = user_hash_for(token)

    # 原子锁: PG row-level lock 防并发重复 add_task
    with session_scope() as s:
        task = s.execute(
            select(ORMIngestTask)
            .where(ORMIngestTask.id == req.task_id, ORMIngestTask.user_hash == uhash)
            .with_for_update()
        ).scalar_one_or_none()

        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")

        if task.state != "queued":
            raise HTTPException(409, detail=f"task 状态错误: {task.state}")

        workdir_uri = task.work_dir
        assert workdir_uri is not None

        # 原子改状态, 释放锁前已写 DB, 并发方读不到 "queued"
        task.state = "running"
        # session_scope exit -> commit -> 释放 FOR UPDATE 锁

    background.add_task(_run_ingest, task.id, workdir_uri)
    return FinalizeUploadResponse(task_id=task.id, state="running")


def _collect_output_files(workdir_uri: str, store) -> list[OutputFile]:
    """(2026-06-16) 列 ABC 下 outputs/ prefix 的 object. 跳过 .tmp / 隐藏文件."""
    out_prefix = f"{workdir_uri.rstrip('/')}/output/"
    out: list[OutputFile] = []
    for meta in store.list_prefix(out_prefix):
        name = meta.uri.rsplit("/", 1)[-1]
        if name.startswith("."):
            continue
        out.append(
            OutputFile(
                name=name,
                size=meta.size,
                mime=_mime_for_name(name),
                uri=meta.uri,
            )
        )
    return out


def _mime_for_name(name: str) -> str:
    """按扩展名推 MIME. (跟旧 _mime_for(Path) 行为一致)"""
    ext = Path(name).suffix.lower()
    return _MIME_MAP.get(ext, "application/octet-stream")


@ingest_router.post(
    "/upload",
    summary="上传 fallback (multipart 透传)",
    description=(
        "## 用途\n\n"
        "浏览器无 presign 能力 (或后端 ABC 暂时不可用) 时的兜底入口: 走 backend multipart 接收, 直接 `store.put_stream` 写入 ABC.\n\n"
        "## 鉴权\n\n"
        '`require_page("output")` 守卫.\n\n'
        "## 行为\n\n"
        "1. 至少 1 个文件; 否则 400.\n"
        "2. 边读边校验: 单文件 ≤ 50MB, 任务总 ≤ 200MB; 超过任一上限 → 413.\n"
        "3. 写入 ABC: `s3://{bucket}/inputs/{task_id}/input/{name}` 或 `local://` 等价路径.\n"
        "4. 创建 IngestTask, 立即 `BackgroundTasks` 调度 `_run_ingest`."
    ),
    responses={
        200: {"description": "{task_id, state: queued, total_files}"},
        400: {"description": "未提供文件 / 扩展名不在白名单"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "output")'},
        413: {"description": "单文件 > 50MB 或任务总 > 200MB"},
        422: {"description": "Pydantic 校验失败"},
    },
)
async def upload(
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_page("output")),
    files: list[UploadFile] = File(...),
):
    token = _check_token(user)
    uhash = user_hash_for(token)

    if not files:
        raise HTTPException(400, detail="未提供文件")

    store = get_object_store()
    task_id = _new_task_id()
    workdir_uri = _build_workdir_uri(uhash, task_id, store.backend_name())

    total_size = 0
    input_records: list[InputFile] = []
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(400, detail=f"不支持的格式: {ext or '(无扩展名)'}")
        input_key = f"input/{Path(f.filename or 'unnamed').name}"
        input_uri = f"{workdir_uri}{input_key}"
        size = 0
        stream = io.BytesIO()
        while chunk := await f.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                raise HTTPException(413, detail=f"文件太大: {f.filename} 超过 {MAX_FILE_SIZE // (1024 * 1024)} MB")
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_SIZE:
                raise HTTPException(413, detail=f"任务总大小超限 ({MAX_UPLOAD_SIZE // (1024 * 1024)} MB)")
            stream.write(chunk)
        stream.seek(0)
        store.put_stream(input_uri, stream, mime=f.content_type)
        input_records.append(
            InputFile(
                name=Path(f.filename or "unnamed").name,
                size=size,
                mime=f.content_type or "application/octet-stream",
                uri=input_uri,
            )
        )

    task = IngestTask(
        id=task_id,
        user_hash=uhash,
        state="queued",
        total_files=len(files),
        work_dir=workdir_uri,
        input_files=input_records,
    )
    _save(task)
    background.add_task(_run_ingest, task_id, workdir_uri)
    return {"task_id": task_id, "state": "queued", "total_files": len(files)}


def _run_ingest(task_id: str, work_dir: str | Path) -> None:
    """BackgroundTask runner — 调 process_path() (走 ABC + 本地 staging), 更新 task 状态 (写穿 store).
    (2026-06-16) 改走 ABC: work_dir 是 URI 字符串 ('s3://...' / 'local://...'). T4.3 会走 process_uri 适配层.
    """
    t = _load(task_id)
    if t is None:
        return
    t.state = "running"
    _save(t)
    # (2026-06-16) 兼容过渡: URI 字符串 → process_uri; Path → process_path (旧流程)
    try:
        if isinstance(work_dir, str) and ("://" in work_dir):
            store = get_object_store()
            result = process_uri(
                input_prefix=f"{work_dir.rstrip('/')}/input/",
                output_prefix=f"{work_dir.rstrip('/')}/output/",
                store=store,
            )
            t.output_files = _collect_output_files(work_dir, store)
        else:
            work_path = Path(work_dir)
            input_dir = work_path / "input"
            output_dir = work_path / "output"
            result = process_path(path=str(input_dir), output_dir=str(output_dir))
            t.output_files = _collect_output_files_legacy(output_dir)
        # 统计 processed / failed: process_path 返 dict-of-buckets, 每个有 processed/errors
        if isinstance(result, dict):
            processed = 0
            failed = 0
            for bucket in result.values():
                if isinstance(bucket, dict):
                    processed += len(bucket.get("processed", []))
                    failed += len(bucket.get("errors", []))
            t.processed = processed
            t.failed = failed
        t.state = "completed"
    except Exception:
        t.state = "failed"
        t.error = repr(traceback.format_exc())
    finally:
        t.finished_at = datetime.now()
        _save(t)


@ingest_router.get(
    "/tasks",
    summary="列当前用户任务",
    description=(
        "## 用途\n\n"
        "列出当前用户的所有 Ingest 任务, 前端 /output 页用.\n\n"
        "## 鉴权\n\n"
        '`require_page("output")` 守卫.\n\n'
        "## 行为\n\n"
        "按 `started_at` 倒序返: id / state / total_files / processed / failed / input_files / output_files / work_dir 等. "
        "store (SQLite) 是真源, 进程内 cache 仅热路径用."
    ),
    responses={
        200: {"description": "任务列表 (按 started_at DESC)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "output")'},
    },
)
def list_tasks(
    user: CurrentUser = Depends(require_page("output")),
) -> list[dict]:
    token = _check_token(user)
    uhash = user_hash_for(token)
    return [t.to_dict() for t in _list_user(uhash)]


@ingest_router.get(
    "/tasks/{task_id}",
    summary="查单任务 (轮询用)",
    description=(
        "## 用途\n\n"
        "查单任务当前 state / 进度 / 产物列表, 前端轮询用.\n\n"
        "## 鉴权\n\n"
        '`require_page("output")` 守卫.\n\n'
        "## 行为\n\n"
        "跨用户 → 404 (防 ID 探测). 重启后旧任务从 store 重建 (cache miss → store hit)."
    ),
    responses={
        200: {"description": "单任务的完整 dict"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "output")'},
        404: {"description": "task 不存在或非当前用户"},
    },
)
def get_task(
    task_id: str,
    user: CurrentUser = Depends(require_page("output")),
) -> dict:
    token = _check_token(user)
    uhash = user_hash_for(token)
    t = _resolve_task(task_id, uhash)
    return t.to_dict()


@ingest_router.get(
    "/tasks/{task_id}/files/{name:path}",
    summary="读产物文件",
    description=(
        "## 用途\n\n"
        "读任务产物 (output/) 中的某个文件, 前端预览/下载用.\n\n"
        "## 鉴权\n\n"
        '`require_page("output")` 守卫.\n\n'
        "## 行为\n\n"
        "- 跨用户 → 404.\n"
        "- 文件名走 `SAFE_NAME` 白名单 (字母数字 + `._/-`), 含 `..` 或以 `/` 开头 → 400, 防 path traversal.\n"
        "- **URI 模式** (work_dir 是 `s3://` / `local://`): 走 `store.list_prefix` 找 `output/` 下匹配文件, 签发 presigned GET URL, 返 `{name, url, size, mime}`.\n"
        "- **Path 模式** (旧本地工作区): 按 basename 递归 `output/`, 读文本, 返 `{name, content, mime}`."
    ),
    responses={
        200: {"description": "{name, url, size, mime} (URI 模式) 或 {name, content, mime} (Path 模式)"},
        400: {"description": "非法文件名 (含 .. / 开头 / / 越界 / 不在 SAFE_NAME 白名单)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "output")'},
        404: {"description": "task 不存在 / 跨用户 / 文件不存在 / 工作区不存在"},
    },
)
def read_task_file(
    task_id: str,
    name: str,
    user: CurrentUser = Depends(require_page("output")),
) -> dict:
    token = _check_token(user)
    uhash = user_hash_for(token)
    t = _resolve_task(task_id, uhash)
    if t.work_dir is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    # 兼容旧数据: 把旧 str(rel) 留下的 \\ 还原成 /
    name = name.replace("\\", "/")
    if ".." in name or name.startswith("/"):
        raise HTTPException(status_code=400, detail=f"非法文件名: {name!r}")
    if not SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail=f"非法文件名: {name!r}")
    # URI 模式走 store.list_prefix + presigned GET; Path 模式走本地 _find_output_file
    work_dir = t.work_dir
    if isinstance(work_dir, str) and "://" in work_dir:
        store = get_object_store()
        out_prefix = f"{work_dir.rstrip('/')}/output/"
        target_uri: str | None = None
        target_size = 0
        for meta in store.list_prefix(out_prefix):
            if meta.uri.rsplit("/", 1)[-1] == name:
                target_uri = meta.uri
                target_size = meta.size
                break
        if target_uri is None:
            raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
        url = store.presign_get(target_uri)
        return {
            "name": name,
            "url": url,
            "size": target_size,
            "mime": _mime_for_name(name),
        }
    # Path 模式: 旧本地工作区
    work_path = Path(work_dir)
    target = _find_output_file(work_path / "output", name)
    if target is None:
        raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
    return {
        "name": name,
        "content": target.read_text(encoding="utf-8", errors="replace"),
        "mime": _mime_for(target),
    }


@ingest_router.get(
    "/tasks/{task_id}/download",
    summary="下载所有产物 zip",
    description=(
        "## 用途\n\n"
        "把任务产出的全部 output 文件 + 原始 input 文件打成 zip 流式下载, 前端「下载全部」按钮用.\n\n"
        "## 鉴权\n\n"
        '`require_page("output")` 守卫.\n\n'
        "## 行为\n\n"
        "- 跨用户 → 404.\n"
        "- **URI 模式**: 流式 `store.list_prefix` 拉 `outputs/` + `inputs/` 写入 zip (output 在根, input 套 `_input/` 前缀).\n"
        "- **Path 模式**: 旧本地工作区, 同逻辑但走本地 rglob.\n"
        '- `Content-Disposition: attachment; filename="{task_id}.zip"` 触发浏览器下载.'
    ),
    responses={
        200: {"description": "application/zip 流 (Content-Disposition: attachment)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "output")'},
        404: {"description": "task 不存在 / 跨用户 / 工作区不存在"},
    },
)
@audited("files.bulk_download", target_type="file")
async def download_zip(
    request: Request,
    task_id: str,
    user: CurrentUser = Depends(require_page("output")),
) -> StreamingResponse:
    request.state.audit_ctx.set(
        target_id=task_id,
    )
    token = _check_token(user)
    uhash = user_hash_for(token)
    t = _resolve_task(task_id, uhash)
    if t.work_dir is None:
        raise HTTPException(status_code=404, detail="工作区不存在")
    work_dir = t.work_dir

    # URI 模式: 走 ABC list_prefix + open_local_ctx
    if isinstance(work_dir, str) and "://" in work_dir:
        store = get_object_store()
        out_prefix = f"{work_dir.rstrip('/')}/output/"
        in_prefix = f"{work_dir.rstrip('/')}/input/"

        def _zip_iter_uri():
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for meta in store.list_prefix(out_prefix):
                    with store.open_local_ctx(meta.uri) as lp:
                        zf.writestr(meta.uri.replace(out_prefix, ""), Path(lp).read_bytes())
                for meta in store.list_prefix(in_prefix):
                    with store.open_local_ctx(meta.uri) as lp:
                        zf.writestr(f"_input/{meta.uri.replace(in_prefix, '')}", Path(lp).read_bytes())
            buf.seek(0)
            yield buf.read()

        return StreamingResponse(
            _zip_iter_uri(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{task_id}.zip"'},
        )

    # Path 模式: 旧本地工作区
    work_path = Path(work_dir)
    output_dir = work_path / "output"

    def _zip_iter():
        """流式生成 zip — 边生成边 yield, 不一次性占内存"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if output_dir.exists():
                for p in sorted(output_dir.rglob("*")):
                    if p.is_file():
                        zf.writestr(str(p.relative_to(output_dir)), p.read_bytes())
            assert work_path is not None
            for p in sorted((work_path / "input").rglob("*")):
                if p.is_file():
                    zf.writestr(f"_input/{p.relative_to(work_path / 'input')}", p.read_bytes())
        buf.seek(0)
        yield buf.read()

    return StreamingResponse(
        _zip_iter(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{task_id}.zip"'},
    )
