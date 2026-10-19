"""pre_analysis HTTP API — PDF 预分析路由 (2026-07-06 从 api.py 拆出)."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from loguru import logger
from sqlalchemy import select

from ...common.task_id import TASK_PREFIX_PRE_ANALYSIS, make_task_id
from ...core.audit import audited
from ...middleware.auth import CurrentUser
from ...permissions.guards import require_super_admin
from ...storage import session_scope
from ...storage.object_store import get_object_store

# 共享辅助函数 (来自 pdf_processing/router.py)
from ..common import _check_token, _uri_for_backend, user_hash_for
from .stage_models import PreAnalysisStage  # noqa: F401  # 间接供 alembic 反射 ORM
from .stage_store import PreAnalysisStageStore
from .store import (
    PreAnalysisTaskStore,
)
from .store import (
    list_user_tasks as pa_list_user_tasks,
)
from .store import (
    load_task as pa_load_task,
)
from .store import (
    save_task as pa_save_task,
)
from .table_view import build_table_page_response, extract_table_pages, parse_table_filename

_logger = logger  # 别名, 跟 pdf_processing/router.py 风格一致

pre_analysis_router = APIRouter(prefix="/api/pre-analysis", tags=["PDF 预分析"])


@pre_analysis_router.post(
    "/upload",
    summary="上传 PDF 触发预分析",
    description=(
        "## 用途\n\n"
        "super_admin 上传 1 个 PDF, 后台异步跑 pymupdf 预分析, 4 类产物写 ObjectStore.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫.\n\n"
        "## 行为\n\n"
        "1. 1 个 .pdf 文件, ≤ 100MB; 否则 413.\n"
        "2. 写入 ObjectStore: `s3://{bucket}/pre_analysis_inputs/{task_id}/input/{file}` 或 local 等价.\n"
        "3. 创建 pre_analysis_tasks 行 (state=pending).\n"
        "4. `BackgroundTasks.add_task(_run_pre_analysis, task_id)` 异步跑.\n"
    ),
    response_model=None,
    responses={
        200: {"description": "{task_id, state: pending, pdf_filename}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
        413: {"description": "PDF > 100MB"},
    },
)
async def upload_pre_analysis(
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_super_admin),
    file: UploadFile = File(...),
    table_backend: str = Form("pymupdf"),
    table_params: str = Form("{}"),
    chapter_config_json: str = Form(
        "{}",
        description='章节配置 JSON, 形如 \'{"max_level": 3, "enable_llm_refinement": false}\'. 留空走默认. 字段见 ChapterExtractionConfig.',
    ),
) -> dict:
    """上传 PDF, 调度后台预分析. table_backend/table_params (2026-07-06 支持 config).

    (2026-07-09 PDF 章节树状化+LLM增强) chapter_config_json 章节配置 (max_level/LLM 开关等).

    Args:
        background: FastAPI BackgroundTasks (调度后台 runner).
        user: super_admin (Depends).
        file: PDF 文件 (≤100MB).
        table_backend: 表格提取后端 (pymupdf | camelot | pdfplumber, 默认 pymupdf).
        table_params: JSON 字符串, backend-specific 参数.
        chapter_config_json: 章节配置 JSON, 字段见 ChapterExtractionConfig.
    """
    token = _check_token(user)
    uhash = user_hash_for(token)

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 100 * 1024 * 1024:
        raise HTTPException(413, detail="PDF > 100MB")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="只接受 .pdf 文件")

    # 校验 table_backend
    if table_backend not in ("pymupdf", "camelot", "pdfplumber"):
        raise HTTPException(400, detail=f"未知表格后端: {table_backend}")

    # 解析 table_params JSON
    try:
        params = json.loads(table_params) if table_params else {}
    except json.JSONDecodeError as e:
        raise HTTPException(400, detail=f"table_params JSON 非法: {e}") from e

    # (2026-07-09) 解析 chapter_config_json (ChapterExtractionConfig.from_form 内部 raise ValueError → HTTP 400)
    from .chapter_extractors.chapter_config import ChapterExtractionConfig  # noqa: PLC0415

    try:
        chapter_cfg = ChapterExtractionConfig.from_form(chapter_config_json)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e

    store = get_object_store()
    task_id = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    pdf_filename = Path(file.filename).name
    input_key = f"pre_analysis_inputs/{task_id}/input/{pdf_filename}"
    workdir_uri = _uri_for_backend(store.backend_name(), input_key)
    store.put_bytes(workdir_uri, pdf_bytes, mime="application/pdf")

    # (2026-07-09) task_config_json 同时存 table + chapter (后续 retry 读这里)
    full_task_config = {
        "table_backend": table_backend,
        "table_params": params,
        "chapter": chapter_cfg.to_dict(),
    }

    pa_save_task(
        {
            "id": task_id,
            "user_hash": uhash,
            "state": "pending",
            "pdf_filename": pdf_filename,
            "pdf_uri": workdir_uri,
            "started_at": datetime.now(UTC),
        },
        task_config=full_task_config,
    )

    background.add_task(_run_pre_analysis, task_id, full_task_config)
    _logger.info(
        "pre_analysis upload task=%s pdf=%s backend=%s chapter_max_level=%s llm=%s",
        task_id,
        pdf_filename,
        table_backend,
        chapter_cfg.chapter_max_level_for_display,
        chapter_cfg.enable_llm_refinement,
    )
    return {"task_id": task_id, "state": "pending", "pdf_filename": pdf_filename}


@pre_analysis_router.get(
    "/tasks",
    summary="列 super_admin 的所有预分析任务",
    response_model=None,
)
async def list_pre_analysis_tasks(
    limit: int = 50,
    offset: int = 0,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """列任务 (按 started_at DESC)."""
    token = _check_token(user)
    uhash = user_hash_for(token)
    tasks = pa_list_user_tasks(uhash, limit=limit, offset=offset)
    return {"tasks": tasks}


@pre_analysis_router.get(
    "/tasks/{task_id}",
    summary="查单条预分析任务详情",
    response_model=None,
)
async def get_pre_analysis_task(
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """查 task 元数据 + 产物清单."""
    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    return task


@pre_analysis_router.get(
    "/tasks/{task_id}/download",
    summary="下载预分析产物 zip 包",
    response_model=None,
    responses={
        200: {"content": {"application/zip": {}}, "description": "zip 流"},
        404: {"description": "任务不存在或产物缺失"},
    },
)
@audited("pre_analysis.download", target_type="pre_analysis_task")
async def download_pre_analysis_zip(
    request: Request,
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> Response:
    """StreamingResponse 流式 zip, 不 load 全文件进内存."""
    request.state.audit_ctx.set(
        target_id=task_id,
    )

    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    if task["state"] != "completed":
        raise HTTPException(409, detail=f"task 状态错误: {task['state']}")

    store = get_object_store()
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in task["output_files"]:
            try:
                data = store.get_bytes(f["uri"])
            except Exception:  # noqa: BLE001  # 单文件缺失跳过, 不阻断整包
                continue
            zf.writestr(f["filename"], data)

    zip_buf.seek(0)
    filename = f"{task['pdf_filename'].rsplit('.', 1)[0]}_pre_analysis_{task_id}.zip"
    return Response(
        content=zip_buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@pre_analysis_router.get(
    "/tasks/{task_id}/files/{filename}",
    summary="下载单个预分析产物",
    response_model=None,
    responses={
        200: {"description": "单文件二进制流"},
        404: {"description": "任务不存在或文件不在产物清单里"},
    },
)
@audited("pre_analysis.download_file", target_type="pre_analysis_file")
async def download_pre_analysis_file(
    request: Request,
    task_id: str,
    filename: str,
    user: CurrentUser = Depends(require_super_admin),
) -> Response:
    """(2026-07-06) 单文件下载: 按 filename 找 output_files 里的 uri, 流式回.

    - 必须在 task.output_files 列表里 (防 path traversal, 只取列表内真实 uri).
    - running 中也可下载 (阶段化产物已落 ObjectStore).
    """
    request.state.audit_ctx.set(
        target_id=f"{task_id}/{filename}",
    )
    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    target = next((f for f in task["output_files"] if f["filename"] == filename), None)
    if target is None:
        raise HTTPException(404, detail=f"产物文件不在清单里: {filename}")

    store = get_object_store()
    try:
        data = store.get_bytes(target["uri"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(404, detail=f"产物文件读取失败: {e}") from e

    # mime: 按 kind 推测; 没匹配走 application/octet-stream (通用下载)
    mime_map = {
        "chapter_structure": "application/json",
        "flagged_paragraphs": "application/json",
        "table": "application/json",
        "index": "application/json",
    }
    media_type = mime_map.get(target.get("kind", ""), "application/octet-stream")
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@pre_analysis_router.get(
    "/tasks/{task_id}/tables/pages",
    summary="列出有表格的 PDF 页号 (用于前端 pagination)",
    description=(
        "## 用途\n\n"
        "返回当前任务中所有含表格的 PDF 页号 (升序去重) + 表格文件总数.\n"
        "前端 tables viewer 用此构建 pagination 条.\n\n"
        "## 性能\n\n"
        "只读 output_files_json DB 字段, 不读 ObjectStore, 几十毫秒级.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫."
    ),
    response_model=None,
    responses={
        200: {"description": "{pages: number[], total: number}"},
        401: {"description": "未登录"},
        403: {"description": "非 super_admin"},
        404: {"description": "任务不存在"},
    },
)
async def list_table_pages(
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """(2026-07-09 tables viewer) 列出有表格的 PDF 页号.

    Args:
        task_id: 预分析任务 ID.
        user: super_admin (Depends).

    Returns:
        {"pages": [3, 9, 12, ...], "total": 12}.
    """
    _check_token(user)  # 一致性: 现有端点都过 token check, 即使 require_super_admin 已挡
    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    pages, total = extract_table_pages(task["output_files"])
    return {"pages": pages, "total": total}


@pre_analysis_router.get(
    "/tasks/{task_id}/tables/page/{page_num}",
    summary="获取指定 PDF 页的表格数据 (含 CSV → JSON 解析)",
    description=(
        "## 用途\n\n"
        "返回指定页所有表格的解析数据 (columns + rows JSON), 避免前端解析 CSV.\n"
        "前端 tables viewer 按 ?page=N 查询, 单页通常 1-3 张表.\n\n"
        "## 性能\n\n"
        "读取该页 N 个 CSV 文件从 ObjectStore + csv.DictReader 解析, 一般 < 100ms.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫."
    ),
    response_model=None,
    responses={
        200: {"description": "{page: number, tables: TableItem[]}"},
        401: {"description": "未登录"},
        403: {"description": "非 super_admin"},
        404: {"description": "任务不存在 或 该页无表格"},
    },
)
async def get_table_page(
    task_id: str,
    page_num: int,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """(2026-07-09 tables viewer) 查指定页所有表格的解析数据.

    Args:
        task_id: 预分析任务 ID.
        page_num: PDF 页号 (1-based).
        user: super_admin (Depends).

    Returns:
        {"page": int, "tables": [{"table_index", "filename", "size_bytes", "columns", "rows"}, ...]}.

    Raises:
        HTTPException 404: 任务不存在 或 该页无表格.
    """
    _check_token(user)  # 一致性: 现有端点都过 token check
    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")

    # 收集该页 filename → uri
    page_files: dict[str, str] = {}
    for f in task["output_files"]:
        if f.get("kind") != "table":
            continue
        try:
            f_page, _ = parse_table_filename(f["filename"])
        except ValueError:
            continue
        if f_page == page_num:
            page_files[f["filename"]] = f["uri"]

    if not page_files:
        raise HTTPException(404, detail=f"页 {page_num} 无表格")

    # 从 ObjectStore 读所有该页 CSV
    store = get_object_store()
    csv_contents: dict[str, bytes] = {}
    for filename, uri in page_files.items():
        try:
            csv_contents[filename] = store.get_bytes(uri)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(404, detail=f"产物文件 {filename} 读取失败: {e}") from e

    try:
        return build_table_page_response(task, page_num, csv_contents)
    except KeyError as e:
        raise HTTPException(404, detail=str(e)) from e


@pre_analysis_router.get(
    "/tasks/{task_id}/stages",
    summary="查 task 的所有 detail stage",
    response_model=None,
)
async def list_pre_analysis_stages(
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """列 task 的 5 个 detail stage 进度 (按 started_at ASC)."""
    task = pa_load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    rows = PreAnalysisStageStore().list_stages(task_id)
    return {
        "stages": [
            {
                "stage": r.stage,
                "status": r.status,
                "progress": r.progress,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "message": r.message,
            }
            for r in rows
        ]
    }


@pre_analysis_router.post(
    "/tasks/{task_id}/retry",
    summary="重试失败任务",
    description=(
        "## 用途\n\n"
        "将 failed 状态 task 重置为 pending, 重新调度后台预分析.\n\n"
        "## 行为\n\n"
        "1. PG FOR UPDATE 锁 task 行, 防并发重试.\n"
        "2. state != failed → 409 (幂等拒绝).\n"
        "3. UPDATE task: state=pending, error=NULL, finished_at=NULL, output_files_json='[]', summary_json='{}', started_at=NOW(), current_stage=NULL.\n"
        "4. DELETE FROM pre_analysis_task_stages WHERE task_id=:id.\n"
        "5. background.add_task(_run_pre_analysis, id).\n"
        "6. 返 200 {task_id, state: pending}."
    ),
    response_model=None,
    responses={
        200: {"description": "{task_id, state: pending}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
        404: {"description": "任务不存在"},
        409: {"description": "task 状态非 failed (已在跑 / 已完成 / 已 pending)"},
    },
)
async def retry_pre_analysis_task(
    background: BackgroundTasks,
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """重置 task + 清 stages + 重调度."""
    _check_token(user)  # noqa: F841  # 鉴权守卫已覆盖, 仅保留 user 引用
    from .models import PreAnalysisTask as ORMPreAnalysisTask  # noqa: E402

    original_config: dict = {}
    with session_scope() as s:
        task = s.execute(
            select(ORMPreAnalysisTask).where(ORMPreAnalysisTask.id == task_id).with_for_update()
        ).scalar_one_or_none()
        if task is None:
            raise HTTPException(404, detail="任务不存在或已过期")
        if task.state != "failed":
            raise HTTPException(409, detail=f"task 状态错误: {task.state}, 只有 failed 可重试")

        # 读取原始 task_config_json (含 table + chapter, 2026-07-09 后结构变更)
        original_config = json.loads(task.task_config_json or "{}") if hasattr(task, "task_config_json") else {}

        # 重置 task
        task.state = "pending"
        task.error = None
        task.finished_at = None
        task.started_at = datetime.now(UTC)
        task.current_stage = None
        task.output_files_json = "[]"
        task.summary_json = "{}"
        # task_config_json 保留不动 (原始配置)

    # 清 stages (在事务外调 session_scope 是因为 retry 不用原子, 删 stage 容忍失败)
    PreAnalysisStageStore().delete_stages_for_retry(task_id)

    # (2026-07-09) 把 full_task_config 传给 runner; 老 task 只有 table_backend/table_params 字段, 缺 chapter
    # 回退用 from_form("{}") 给 default
    if "chapter" not in (original_config or {}):
        original_config = {**(original_config or {}), "chapter": {}}  # default

    background.add_task(_run_pre_analysis, task_id, original_config or None)

    return {"task_id": task_id, "state": "pending"}


# --- 后台 runner 调度 ---


def _run_pre_analysis(task_id: str, task_config: dict | None = None) -> None:
    """BackgroundTasks 调度入口. (2026-07-06) 接受后端配置.

    (2026-07-09 PDF 章节树状化) task_config 含 {table_backend, table_params, chapter: {...}}.

    Args:
        task_id: 业务 UUID.
        task_config: 完整 task 配置 (table + chapter), None → 走默认.
    """
    from .chapter_extractors.chapter_config import ChapterExtractionConfig  # noqa: PLC0415
    from .runner import PreAnalysisRunner

    task = pa_load_task(task_id)
    if task is None:
        _logger.error("_run_pre_analysis task %s not found", task_id)
        return

    # 拆分 task_config → table_config + chapter_config
    cfg = task_config or {}
    table_config = {
        "table_backend": cfg.get("table_backend", "pymupdf"),
        "table_params": cfg.get("table_params", {}),
    }
    chapter_dict = cfg.get("chapter") or {}
    chapter_config = ChapterExtractionConfig.from_form(json.dumps(chapter_dict))

    # (2026-07-09) 抽 stage 后删 keyword_config_path / project_root, prepare_input 走 env RULE_KEYWORDS_PATH 自己找
    runner = PreAnalysisRunner(
        object_store=get_object_store(),
        task_store=PreAnalysisTaskStore(),
        stage_store=PreAnalysisStageStore(),
    )
    try:
        runner.run(
            task_id=task_id,
            pdf_uri=task["pdf_uri"],
            table_extraction_config=table_config,
            chapter_config=chapter_config,
        )
    except Exception as e:
        _logger.exception("_run_pre_analysis task=%s failed", task_id)
        PreAnalysisTaskStore().mark_failed(
            task_id,
            f"runner exception: {e}",
            stages_provider=PreAnalysisStageStore().list_stages,
        )


def _orphan_cleanup_pre_analysis_tasks(threshold_minutes: int = 5) -> int:
    """(2026-07-03) 启动时扫: state IN (pending, running) 且 started_at 老于阈值 → mark_failed.

    解决: 后端 session 重启后, BackgroundTasks 已死, task 永远卡 running.
    Returns: 更新行数.
    """
    from .models import PreAnalysisTask as ORMPreAnalysisTask  # noqa: E402

    threshold = datetime.now(UTC) - timedelta(minutes=threshold_minutes)
    error_msg = "服务重启导致中断"
    with session_scope() as s:
        rows = (
            s.query(ORMPreAnalysisTask)
            .filter(ORMPreAnalysisTask.state.in_(("pending", "running")), ORMPreAnalysisTask.started_at < threshold)
            .all()
        )
        for r in rows:
            r.state = "failed"
            r.error = error_msg
            r.finished_at = datetime.now(UTC)
            r.current_stage = None
        return len(rows)
