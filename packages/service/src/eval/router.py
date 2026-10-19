"""/api/evaluate/* 路由: 评估批的 CRUD + 异步启动

- GET    /api/evaluate/runs          列表 (admin 看全部, 普通看自己)
- POST   /api/evaluate/runs          上传 CSV, 启动后台 task, 返回 {id, status}
- GET    /api/evaluate/runs/{id}     详情 + samples
- POST   /api/evaluate/runs/{id}/cancel  取消 running
- GET    /api/evaluate/template      下载 CSV 模板 (无需鉴权)

⚠️ admin 虚拟 user (id=0) 在 users 表里不存在, 所以 admin 列表用 is_admin 短路.

(2026-06-17) v2 RBAC: 走 require_page('evaluate') 鉴权 (page-level), user / admin / super_admin 矩阵
由 permission_cache 决定. 普通用户可看自己 evaluation (user_id 过滤仍保留).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..core.audit import audited
from ..generation.llm import OpenAILLM
from ..integrations.dify_client import DifyClient
from ..middleware.auth import CurrentUser
from ..permissions.guards import require_page
from ..storage.object_store import get_object_store
from ..storage.session import get_session, session_scope
from ..utils.timezone import HKT
from . import runner, runner_registry
from .csv_parser import CSVParsingError, parse_eval_csv
from .deepeval_eval import DeepEvalEvaluator
from .models import Evaluation
from .template import build_eval_template_csv

router = APIRouter(prefix="/api/evaluate", tags=["evaluate"])

DATASETS_DIR = Path("data/eval_datasets")


def _eval_to_dict(e: Evaluation) -> dict:
    """Evaluation + samples → dict (供 router 返回)"""
    return {
        "id": e.id,
        "user_id": e.user_id,
        "dataset_name": e.dataset_name,
        "dataset_path": e.dataset_path,
        "status": e.status,
        "total_samples": e.total_samples,
        "successful": e.successful,
        "failed": e.failed,
        "concurrency": e.concurrency,
        "avg_metrics": e.avg_metrics,
        "duration_seconds": e.duration_seconds,
        "error_message": e.error_message,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "finished_at": e.finished_at.isoformat() if e.finished_at else None,
        "samples": [
            {
                "id": s.id,
                "index": s.index,
                "question": s.question,
                "ground_truth": s.ground_truth,
                "answer": s.answer,
                "contexts": s.contexts,
                "sources": s.sources,  # (2026-06-11 Task C)
                "metrics": s.metrics,
                "error": s.error,
                "duration_ms": s.duration_ms,
            }
            for s in sorted(e.samples, key=lambda x: x.index)
        ],
    }


# ---- 端点 ----
@router.get(
    "/template",
    summary="下载 CSV 模板",
    description=(
        "## 用途\n\n"
        "下载评估用的 CSV 模板 (含表头 + 示例行), 前端供用户填好后上传到 `/api/evaluate/runs`.\n\n"
        "## 鉴权\n\n"
        "无需鉴权. 模板里没有数据, 仅字段说明.\n\n"
        "## 行为\n\n"
        "返 `text/csv; charset=utf-8`, 触发浏览器下载 `eval_template.csv`."
    ),
    responses={
        200: {"description": "CSV 模板内容"},
    },
)
def get_template() -> PlainTextResponse:
    return PlainTextResponse(
        content=build_eval_template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": 'attachment; filename="eval_template.csv"'},
    )


@router.get(
    "/runs",
    summary="列历史评估",
    description=(
        "## 用途\n\n"
        "列出当前用户的历史评估批次, 前端「评估」页用.\n\n"
        "## 鉴权\n\n"
        '`require_page("evaluate")` 守卫: 仅拥有 evaluate 页面权限的角色可访问.\n\n'
        "## 行为\n\n"
        "admin 看全部记录, 普通用户自动按 `user_id` 过滤只返自己. 按 `created_at` 倒序."
    ),
    responses={
        200: {"description": "评估列表 (按 created_at DESC)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "evaluate")'},
    },
)
def list_runs(
    current: CurrentUser = Depends(require_page("evaluate")),
    db: Session = Depends(get_session),
):
    q = db.query(Evaluation)
    if not current.is_admin:
        q = q.filter(Evaluation.user_id == current.id)
    return [_eval_to_dict(e) for e in q.order_by(Evaluation.created_at.desc()).all()]


@router.post(
    "/runs",
    summary="上传 CSV 启动评估",
    description=(
        "## 用途\n\n"
        "上传评估 CSV, 落库后由 BackgroundTask 异步执行 Dify + LLM-as-judge 评估.\n\n"
        "## 鉴权\n\n"
        '`require_page("evaluate")` 守卫.\n\n'
        "## 行为\n\n"
        "1. 解析并校验 CSV (1-200 行).\n"
        "2. 写 ABC `s3://{bucket}/eval/{run_uuid}/dataset.csv` (local 后端走 `local://` 前缀).\n"
        "3. 落 Evaluation 行 (status=`pending`).\n"
        "4. `BackgroundTasks` 启动 `_run_eval_background`: 构造 DifyClient / OpenAILLM / DeepEvalEvaluator, 调 `runner.run_evaluation()`.\n"
        "5. 立即返 `{id, status: pending}`, 前端用 id 轮询 `/api/evaluate/runs/{id}`."
    ),
    responses={
        200: {"description": "{id, status: pending}"},
        400: {"description": "CSV 解析失败 (列缺失 / 行数超限 / 编码错误)"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "evaluate")'},
        413: {"description": "文件 > 5MB"},
        422: {"description": "Pydantic 校验失败 (concurrency 越界等)"},
    },
)
@audited("evaluation.run", target_type="evaluation")
async def upload_run(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(..., description="CSV 文件, ≤ 5MB, 1-200 行"),
    concurrency: int = Form(5, ge=1, le=10),
    current: CurrentUser = Depends(require_page("evaluate")),
):
    request.state.audit_ctx.set(
        target_id="pending",
    )
    content = await file.read()

    # 1. 解析 + 校验
    try:
        rows = parse_eval_csv(content, filename=file.filename or "upload.csv")
    except CSVParsingError as e:
        raise HTTPException(400, str(e)) from e

    # 2. (2026-06-16) 走 ABC 写 dataset_uri (用 uuid4 hex 作 dataset 路径)
    run_uuid = uuid.uuid4().hex
    store = get_object_store()
    if store.backend_name() == "minio":
        bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
        dataset_uri = f"s3://{bucket}/eval/{run_uuid}/dataset.csv"
    else:
        dataset_uri = f"local://eval/{run_uuid}/dataset.csv"
    store.put_bytes(dataset_uri, content, mime="text/csv")
    dataset_name = file.filename or "upload.csv"

    # 3. 落 Evaluation 行 (pending)
    with session_scope() as s:
        e = Evaluation(
            user_id=current.id,
            dataset_name=dataset_name,
            dataset_uri=dataset_uri,
            dataset_path=None,  # (2026-06-16) 旧字段不再设
            status="pending",
            total_samples=len(rows),
            concurrency=concurrency,
        )
        s.add(e)
        s.flush()
        evaluation_id = e.id

    # 4. (2026-06-16) 用 BackgroundTasks 启动后台 task (替代 asyncio.create_task)
    background.add_task(
        _run_eval_background,
        evaluation_id=evaluation_id,
        dataset_uri=dataset_uri,
        dataset_name=dataset_name,
        concurrency=concurrency,
        user_id=current.id,
    )

    return {"id": evaluation_id, "status": "pending"}


async def _run_eval_background(
    evaluation_id: int,
    dataset_uri: str,
    dataset_name: str,
    concurrency: int,
    user_id: int,
) -> None:
    """后台 task: 构造依赖 + 调 run_evaluation (传 dataset_uri).

    (2026-06-16) runner 自己从 URI 读 CSV, 不再收 dataset=[...].
    """
    cancel_event = asyncio.Event()
    runner_registry.register_cancel_event(evaluation_id, cancel_event)
    try:
        dify = DifyClient()
        judge_llm = OpenAILLM().llm
        evaluator = DeepEvalEvaluator(llm=judge_llm)
        await runner.run_evaluation(
            user_id=user_id,
            dataset_name=dataset_name,
            dataset_uri=dataset_uri,  # (2026-06-16) 传 URI 替代 dataset=[]
            concurrency=concurrency,
            dify=dify,
            evaluator=evaluator,
            evaluation_id=evaluation_id,
            cancel_event=cancel_event,
        )
    except Exception as exc:
        # 只在 "running" 状态下才把行翻成 failed: 启动期构造依赖失败时
        # 行还停在 "pending", 留给上层重试或人工干预, 避免误标 failed
        with session_scope() as s:
            ee = s.get_one(Evaluation, evaluation_id)
            if ee.status == "running":
                ee.status = "failed"
                ee.error_message = f"runner crash: {exc}"
                ee.finished_at = datetime.now(HKT)
            else:
                ee.error_message = f"startup error: {exc}"
    finally:
        runner_registry.unregister_cancel_event(evaluation_id)


@router.get(
    "/runs/{run_id}",
    summary="查单次评估详情",
    description=(
        "## 用途\n\n"
        "查询某次评估的完整状态 + 全部 sample (含 question / ground_truth / answer / contexts / sources / metrics).\n\n"
        "## 鉴权\n\n"
        '`require_page("evaluate")` 守卫.\n\n'
        "## 行为\n\n"
        "admin 可查任何 evaluation. 普通用户只能查自己的; 别人的 evaluation 统一返 404 (防 ID 探测 / 泄露). "
        "返回字典含 `samples[]` 数组 (按 `index` 升序)."
    ),
    responses={
        200: {"description": "评估详情 + samples[]"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "evaluate")'},
        404: {"description": "evaluation 不存在 (含别人的 evaluation, 防泄露)"},
    },
)
def get_run(
    run_id: int,
    current: CurrentUser = Depends(require_page("evaluate")),
    db: Session = Depends(get_session),
):
    e = db.get(Evaluation, run_id)
    if e is None:
        raise HTTPException(404, f"evaluation {run_id} 不存在")
    if not current.is_admin and e.user_id != current.id:
        raise HTTPException(404, f"evaluation {run_id} 不存在")  # 避免泄露
    return _eval_to_dict(e)


@router.post(
    "/runs/{run_id}/cancel",
    summary="取消评估",
    description=(
        "## 用途\n\n"
        "向正在跑的后台 task 发送取消信号. 已结束 / 已失败的任务返 `cancelled=False`.\n\n"
        "## 鉴权\n\n"
        '`require_page("evaluate")` 守卫.\n\n'
        "## 行为\n\n"
        "取消不依赖 DB 行的存在: 任务可能已完成/失败被清理, 但仍可尝试触发取消信号. "
        "admin 可取消任何 evaluation, 普通用户仅自己; 别人的 evaluation → 404 (防泄露). "
        "返 `{cancelled: bool}`: True 表示后台 task 还在跑并已收到信号, False 表示已结束 / 从未注册."
    ),
    responses={
        200: {"description": "{cancelled: bool}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "evaluate")'},
        404: {"description": "别人的 evaluation (防泄露)"},
    },
)
@audited("evaluation.cancel", target_type="evaluation")
async def cancel_run(
    request: Request,
    run_id: int,
    current: CurrentUser = Depends(require_page("evaluate")),
    db: Session = Depends(get_session),
):
    request.state.audit_ctx.set(
        target_id=str(run_id),
    )
    e = db.get(Evaluation, run_id)
    if e is not None and not current.is_admin and e.user_id != current.id:
        # 别人的 evaluation → 404 (避免泄露)
        raise HTTPException(404, f"evaluation {run_id} 不存在")
    cancelled = runner_registry.request_cancel(run_id)
    return {"cancelled": cancelled}
