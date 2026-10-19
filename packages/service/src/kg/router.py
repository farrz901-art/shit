"""知识图谱 FastAPI 路由

所有端点统一在 /api/kg 前缀下
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.core.audit import audited
from src.ingest.chunkers import HeadingSplitter, SemanticSplitter, TokenSplitter
from src.storage import session_scope
from src.storage.object_store import build_uri, get_object_store

from ..middleware.auth import CurrentUser
from ..permissions.guards import require_page
from . import audit as _audit
from . import datasets as _kg_datasets
from . import schema as _kg_pkg_schema
from . import templates as _templates
from .client import KgClient, TripleRow
from .config_loader import list_extractor_ids
from .exceptions import TaskNotFoundError
from .extract_runner import run_extraction
from .extractors.llm_pydantic.extractor import LlmPydanticExtractor
from .extractors.spacy_rule.extractor import SpacyRuleExtractor
from .tasks import TaskStore

# 仓库根目录 (src/kg/router.py → 上溯 2 层 = packages/service/)
_REPO_ROOT = Path(__file__).resolve().parents[2]

# TODO: 加 @audited("kg_node.delete", target_type="kg_node") 当 DELETE 节点端点实现后
# TODO: 加 @audited("kg_relation.delete", target_type="kg_relation") 当 DELETE 关系端点实现后

# 单例 audit store; 数据落 data/kg_audit.db
_audit_store = _audit.AuditStore("data/kg_audit.db")

router = APIRouter(prefix="/api/kg", tags=["kg"])

# 单例: dev server 重启时丢任务 (v1 接受)
_task_store = TaskStore()


class TripleRowIn(BaseModel):
    from_label: str = Field(..., description="起点节点 label, 例: 'Product' / 'Series' / 'Spec'")
    from_key: str = Field(..., description="起点节点匹配字段, 例: 'model'")
    from_value: str = Field(..., description="起点节点匹配值, 例: '1LE0001-1AA42-1AA4'")
    rel_type: str = Field(..., description="关系类型, 自由字符串, 例: 'HAS_SPEC' / 'BELONGS_TO' / 'MATCHES'")
    to_label: str = Field(..., description="终点节点 label")
    to_key: str = Field(..., description="终点节点匹配字段")
    to_value: str = Field(..., description="终点节点匹配值")
    properties: dict = Field(default_factory=dict, description="关系附加属性, 自由 JSON")


class TriplesRequest(BaseModel):
    rows: list[TripleRowIn] = Field(..., description="三元组列表, 整批事务提交")


class TriplesResponse(BaseModel):
    success: int = Field(..., description="成功条数")
    failed: int = Field(..., description="失败条数")
    errors: list[str] = Field(default_factory=list, description="错误描述列表, 与 rows 顺序对应")


class BatchItem(BaseModel):
    target: Literal["dify", "neo4j"] = Field(..., description="'dify' = 推 Dify 知识库, 'neo4j' = 推 Neo4j 知识图谱")
    type: str = Field(..., description="操作类型, 例: 'document' / 'triple' (由 executor 解释)")
    payload: dict = Field(..., description="操作 payload, schema 由 type 决定")


class BatchRequest(BaseModel):
    items: list[BatchItem] = Field(..., description="批量操作列表")


class BatchResponse(BaseModel):
    task_id: str = Field(..., description="后台 task ID, 调 GET /api/kg/tasks/{task_id} 查状态")


@router.get(
    "/stats",
    summary="知识图谱统计",
    description=(
        "## 用途\n\n"
        "聚合 Dify 数据集 + Neo4j 节点/关系计数, 供前端 dashboard 概览; **type 决定范围** (dify / neo4j / all).\n\n"
        "## 鉴权\n\n"
        '`require_page("kg")` 守卫: 需登录 + 拥有 `kg` 页面权限 (super_admin 短路放行).\n\n'
        "## 行为\n\n"
        "`type=dify` → `{datasets, documents}`. "
        "`type=neo4j` → `{nodes, relations}`. "
        "`type=all` (默认) → `{neo4j: {...}, dify: {...}}`. "
        "**降级**: DIFY_DATASET_API_KEY 缺失 / Neo4j 不可达 / 请求超时, 对应子项返零计数 (空 dict), 不抛 500. "
        "`domain` 参数当前未使用, 保留作后续 schema-domain 维度聚合."
    ),
    responses={
        200: {"description": "返 type 维度的统计 dict; 不可达子项返零计数"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "kg")'},
    },
)
def stats(
    type: str = "all",
    domain: str = "knowledge",
    _user: CurrentUser = Depends(require_page("kg")),
) -> dict:
    result = {}

    if type in ("dify", "all"):
        base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
        api_key = os.getenv("DIFY_DATASET_API_KEY", "")
        dify = {"datasets": 0, "documents": 0}
        if api_key:
            try:
                r = requests.get(
                    f"{base_url}/datasets?limit=100",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
                if r.ok:
                    data = r.json().get("data", [])
                    dify["datasets"] = len(data)
                    dify["documents"] = sum(d.get("document_count", 0) for d in data)
            except Exception:
                pass
        if type == "dify":
            return dify
        result["dify"] = dify

    if type in ("neo4j", "all"):
        neo4j = {"nodes": 0, "relations": 0}
        try:
            neo4j = KgClient().counts()
        except Exception:
            pass
        if type == "neo4j":
            return neo4j
        result["neo4j"] = neo4j

    return result


@router.get(
    "/health",
    summary="Dify 监控检查",
    description=(
        "## 用途\n\n"
        "探测 Dify API 是否可达, 返 `{ok: bool, error?: str}` 给前端状态指示器.\n\n"
        "## 鉴权\n\n"
        '`require_page("kg")` 守卫: 需登录 + 拥有 `kg` 页面权限 (跟 `/stats` 保持一致).\n\n'
        "## 行为\n\n"
        "DIFY_DATASET_API_KEY 缺失 → `ok=False, error='DIFY_DATASET_API_KEY 未配置'`. "
        "有 key 时 GET `${DIFY_BASE_URL}/datasets?limit=1` 试探, 2xx 返 `ok=True`; "
        "非 2xx / 网络异常 → `ok=False, error=str(e)`. "
        "绝不抛 5xx; timeout=5s."
    ),
    responses={
        200: {"description": "返 `{ok, error?}`; ok=False 时仍 200 (语义上是 '监控检查本身成功')"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": '权限不足 (require_page "kg")'},
    },
)
def health(_user: CurrentUser = Depends(require_page("kg"))):
    base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
    api_key = os.getenv("DIFY_DATASET_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "DIFY_DATASET_API_KEY 未配置"}
    try:
        r = requests.get(f"{base_url}/datasets?limit=1", headers={"Authorization": f"Bearer {api_key}"}, timeout=5)
        return {"ok": r.ok}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get(
    "/datasets",
    summary="Dify 数据集列表",
    description=(
        "## 用途\n\n"
        "代理 Dify `GET /datasets?limit=100`, 供前端 KG 页面 dataset 树渲染.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        "DIFY_DATASET_API_KEY 缺失 → 直接返 `{data: []}` (避免前端判空逻辑报错). "
        "有 key 时调 Dify, 透传 response JSON; 非 2xx / 异常 → 同样降级为 `{data: []}`. "
        "timeout=10s."
    ),
    responses={
        200: {"description": "返 Dify 数据集 list (data[]) 或降级空 `{data: []}`"},
    },
)
def list_datasets():
    base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
    api_key = os.getenv("DIFY_DATASET_API_KEY", "")
    if not api_key:
        return {"data": []}
    try:
        r = requests.get(f"{base_url}/datasets?limit=100", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        if r.ok:
            return r.json()
        return {"data": []}
    except Exception:
        return {"data": []}


@router.get(
    "/segments",
    summary="Dify segments 列表",
    description=(
        "## 用途\n\n"
        "代理 Dify `GET /datasets/{dataset_id}/documents/{document_id}/segments?limit=10` — "
        "供前端 KG 页面 chunks 预览面板用.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        "**必填**: `dataset_id` + `document_id` (query param). 缺任一 → 直接返 `{data: []}`. "
        "DIFY_DATASET_API_KEY 缺失 / Dify 不可达 → 同样降级为 `{data: []}`. "
        "成功时透传 Dify response JSON. timeout=10s."
    ),
    responses={
        200: {"description": "返 Dify segments (data[]) 或降级空 `{data: []}`"},
    },
)
def list_segments(dataset_id: str = "", document_id: str = ""):
    base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
    api_key = os.getenv("DIFY_DATASET_API_KEY", "")
    if not api_key or not dataset_id or not document_id:
        return {"data": []}
    try:
        r = requests.get(
            f"{base_url}/datasets/{dataset_id}/documents/{document_id}/segments?limit=10",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if r.ok:
            return r.json()
        return {"data": []}
    except Exception:
        return {"data": []}


@router.get(
    "/nodes",
    summary="列 Neo4j 节点 (按 dataset 隔离)",
    description=(
        "## 用途\n\n"
        "从 Neo4j 拉节点列表 — 按当前指定 dataset label 过滤.\n\n"
        "**2026-07-01 v3 加 dataset 隔离**: cypher 必含 `WHERE n:\\`<Dataset>\\`` 防跨 dataset 泄露. "
        "dataset 必须在 env `KG_ALLOWED_DATASETS` 白名单内, 否则 422.\n\n"
        "**降级**: Neo4j 不可达 → 返空 list `[]` (跟 `/stats` 的 graceful 行为一致), "
        "**不挂整页**. 不抛 5xx.\n\n"
        "## 鉴权\n\n"
        '`require_page("kg")` 守卫: 需登录 + 拥有 `kg` 页面权限 (super_admin 短路放行).\n\n'
        "## 行为\n\n"
        "分页 `skip` / `limit` (limit 默认 100). "
        "每个元素 `{id, label, props}`."
    ),
    responses={
        200: {"description": "返节点 list (`{id, label, props}`) 或降级空 list"},
        403: {"description": "权限不足 (require_page kg)"},
        422: {"description": "dataset 不在白名单"},
    },
)
def list_nodes(
    dataset: str = "motor",  # 2026-07-01 v3: 加 dataset
    skip: int = 0,
    limit: int = 100,
    _user: CurrentUser = Depends(require_page("kg")),  # 2026-07-01 v3: 加 admin 守卫
) -> list[dict]:
    """列本 dataset 节点 (admin + kg 页面权限)"""
    _kg_datasets.validate_dataset(dataset)
    try:
        return KgClient(dataset=dataset).list_nodes(skip=skip, limit=limit)
    except Exception:
        return []


@router.get(
    "/relationships",
    summary="列 Neo4j 关系 (按 dataset 隔离)",
    description=(
        "## 用途\n\n"
        "从 Neo4j 拉关系列表 — 按当前指定 dataset label 过滤.\n\n"
        '**鉴权**: `require_page("kg")` 守卫.\n\n'
        "## 行为\n\n"
        "分页 `skip` / `limit` (limit 默认 100). "
        "Cypher 用 endpoint 双向 `\\`<Dataset>\\`` 过滤防跨 dataset 泄露.\n\n"
        "每个元素 `{src, src_label, type, dst, dst_label, props}`."
    ),
    responses={
        200: {"description": "返关系 list 或降级空 list"},
        403: {"description": "权限不足"},
        422: {"description": "dataset 不在白名单"},
    },
)
def list_relationships(
    dataset: str = "motor",
    skip: int = 0,
    limit: int = 100,
    _user: CurrentUser = Depends(require_page("kg")),
) -> list[dict]:
    _kg_datasets.validate_dataset(dataset)
    try:
        return KgClient(dataset=dataset).list_relationships(skip=skip, limit=limit)
    except Exception:
        return []


@router.get(
    "/schemas",
    summary="列可用 schema domain",
    description=(
        "## 用途\n\n"
        "扫 `configs/*-schema.yaml` 列出所有可用 schema domain — 供前端 KG 页面 domain 下拉框 + 模板生成器选 domain.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        "glob 模式 `configs/*-schema.yaml`, 提取文件名 stem 去掉 `-schema` 后缀作为 domain. "
        "返 `[{domain, file}, ...]`. 无文件时返空 list. 不读 yaml 内容, 纯列举."
    ),
    responses={
        200: {"description": "返 schema 列表 (无文件时为空 list)"},
    },
)
def list_schemas() -> list[dict]:
    pattern = str(_REPO_ROOT / "configs" / "*-schema.yaml")
    files = glob.glob(pattern)
    schemas = []
    for f in files:
        name = Path(f).stem.replace("-schema", "")
        schemas.append({"domain": name, "file": str(f)})
    return schemas


@router.get(
    "/schema",
    summary="读 schema yaml",
    description=(
        "## 用途\n\n"
        "读 `configs/{domain}-schema.yaml` 并把内容 parse 成 dict 返给前端; 给 BFF / 前端做表单字段映射.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        "`domain` query param 选 schema 文件 (默认 `motor`). "
        "**降级**: 指定 domain 文件不存在 → fallback 到 `configs/` 下任意第一个 schema yaml; "
        "如果连一个 schema yaml 都没有 → 404 `无可用 schema: {domain}`. "
        "成功返 schema dict (具体 shape 跟 yaml 内容一致)."
    ),
    responses={
        200: {"description": "返 schema 解析后的 dict"},
        404: {"description": "无任何可用 schema yaml"},
    },
)
def get_schema(domain: str = "motor") -> dict:
    schema_file = _REPO_ROOT / "configs" / f"{domain}-schema.yaml"
    if not schema_file.exists():
        files = glob.glob(str(_REPO_ROOT / "configs" / "*-schema.yaml"))
        if not files:
            raise HTTPException(status_code=404, detail=f"无可用 schema: {domain}")
        schema_file = Path(files[0])
    return _kg_pkg_schema.load_schema(str(schema_file))


@router.get(
    "/products",
    summary="列 Product 节点 (按 dataset 隔离)",
    description=(
        "## 用途\n\n"
        "从 Neo4j 拉 `Product` 节点列表 — 供前端 QA tab 的 combobox 选品用. "
        "**2026-07-01 v3 加 dataset 隔离 + require_page 鉴权**.\n\n"
        "## 行为\n\n"
        "Cypher: `MATCH (n:Product:`<Dataset>`) WHERE $q = '' OR n.model CONTAINS $q OR n.name CONTAINS $q "
        "RETURN id(n), n.model, n.name LIMIT $limit`."
    ),
    responses={
        200: {"description": "返 Product 节点 list (`{id, model, name}`)"},
        403: {"description": "权限不足"},
        422: {"description": "dataset 不在白名单"},
    },
)
def list_products(
    dataset: str = "motor",
    q: str = "",
    limit: int = 50,
    _user: CurrentUser = Depends(require_page("kg")),
) -> list[dict]:
    _kg_datasets.validate_dataset(dataset)
    cypher = (
        f"MATCH (n:Product:`{dataset}`) "
        "WHERE ($q = '' OR n.model CONTAINS $q OR n.name CONTAINS $q) "
        "RETURN id(n) AS id, n.model AS model, n.name AS name "
        "LIMIT $limit"
    )
    rows = KgClient(dataset=dataset)._store.execute_and_fetch(cypher, {"q": q, "limit": limit})
    return [{"id": str(r["id"]), "model": r["model"], "name": r["name"]} for r in rows]


@router.get(
    "/templates/excel",
    summary="下载 Excel QA 模板",
    description=(
        "## 用途\n\n"
        "下发空白的 Excel QA 模板 (含表头 + 示例列), 给用户下载回去填 QA 三元组 / 产品 QA 对, 再通过 Excel 导入流程回灌.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        "流式返 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, "
        "filename=`qa-template.xlsx`. 模板里无业务数据, 仅表头; 由 `kg.templates.build_qa_excel` 构造."
    ),
    responses={
        200: {
            "description": "Excel 文件流 (.xlsx)",
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
        },
    },
)
def download_excel_template():
    buf = _templates.build_qa_excel()
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="qa-template.xlsx"'},
    )


@router.post(
    "/triples",
    response_model=TriplesResponse,
    summary="提交三元组 (事务)",
    description=(
        "## 用途\n\n"
        "前端一次性提交一批 (from, rel, to) 三元组到 Neo4j; 整批在一次 batch_upsert 里处理, **不是 SQL 事务**, 失败明细返 `errors[]`.\n\n"
        "## 鉴权\n\n"
        '`require_page("kg")` 守卫 (2026-07-01 v3 修复: 之前**无鉴权**, 任何登录用户可调).\n\n'
        "## 行为\n\n"
        "body: `{rows: [{from_label, from_key, from_value, rel_type, to_label, to_key, to_value, properties?}, ...]}`. "
        "**dataset 从 query param 注入** (强校验 env `KG_ALLOWED_DATASETS` 白名单). "
        "调 `KgClient(dataset=dataset).batch_upsert_triples(rows)`. "
        "**审计**: 写 `data/kg_audit.db` (action=`kg.submit_triples`, "
        "actor=current_user.email, actor_id=current_user.id — 2026-07-01 v3 修复)."
    ),
    responses={
        200: {"description": "返 `{success, failed, errors[]}`; 部分失败也返 200"},
        403: {"description": "权限不足 (require_page kg)"},
        422: {"description": "Pydantic 校验失败 (rows 字段类型) 或 dataset 不在白名单"},
    },
)
def submit_triples(
    req: TriplesRequest,
    dataset: str = "motor",
    current_user: CurrentUser = Depends(require_page("kg")),
) -> TriplesResponse:
    """提交三元组 (事务, admin + kg 页面权限)"""
    _kg_datasets.validate_dataset(dataset)
    rows = [
        TripleRow(
            from_label=r.from_label,
            from_key=r.from_key,
            from_value=r.from_value,
            rel_type=r.rel_type,
            to_label=r.to_label,
            to_key=r.to_key,
            to_value=r.to_value,
            properties=r.properties,
        )
        for r in req.rows
    ]
    kg = KgClient(dataset=dataset)
    result = kg.batch_upsert_triples(rows)
    _audit_store.record(
        action="kg.submit_triples",
        actor=current_user.email,
        target=f"{len(req.rows)} rows",
        result="ok" if result.failed == 0 else "partial",
        detail={
            "success": result.success,
            "failed": result.failed,
            "errors": result.errors,
            "dataset": dataset,
            "actor_id": current_user.id,
        },
    )
    return TriplesResponse(success=result.success, failed=result.failed, errors=result.errors)


@router.post(
    "/batch",
    response_model=BatchResponse,
    summary="大批量提交 (后台 task)",
    description=(
        "## 用途\n\n"
        "大批量混合 items 异步提交 — 适合 Excel 导入 / 一次性数据回灌; 同步路径 `/triples` 超时场景走这边.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        "body: `{items: [{target: 'dify'|'neo4j', type: str, payload: dict}, ...]}`. "
        "**立即** 返 `{task_id}` (201), 不等待执行结果. "
        "执行走 `TaskStore` 后台 task (v1 单实例, dev server 重启任务丢失). "
        "前端轮询用 `GET /api/kg/tasks/{task_id}` 查状态 (state / success / failed / errors)."
    ),
    responses={
        200: {"description": "返 `{task_id}`; 后台异步执行"},
        422: {"description": "Pydantic 校验失败 (target 不在枚举)"},
    },
)
def submit_batch(req: BatchRequest) -> BatchResponse:
    task_id = _task_store.submit("kg_batch", req.model_dump())
    return BatchResponse(task_id=task_id)


@router.get(
    "/tasks/{task_id}",
    summary="查任务状态",
    description=(
        "## 用途\n\n"
        "轮询查 `POST /api/kg/batch` 提交的后台任务状态 — 供前端进度条 / 失败重试 UI.\n\n"
        "## 鉴权\n\n"
        "无.\n\n"
        "## 行为\n\n"
        "`task_id` 由 `/batch` 返回. 返 `{task_id, kind, state, success, failed, errors, created_at, finished_at}`. "
        "`state`: `pending` / `running` / `succeeded` / `failed`. "
        "task_id 不存在 (e.g. dev server 重启过, in-memory store 丢失) → 404 `任务不存在: {task_id}`."
    ),
    responses={
        200: {"description": "返 task 状态 dict"},
        404: {"description": "task_id 不存在 (store 丢失)"},
    },
)
def get_task(task_id: str) -> dict:
    try:
        status = _task_store.get(task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return {
        "task_id": status.task_id,
        "kind": status.kind,
        "state": status.state,
        "success": status.success,
        "failed": status.failed,
        "errors": status.errors,
        "created_at": status.created_at,
        "finished_at": status.finished_at,
    }


@router.get(
    "/extract/datasets",
    summary="列允许的 KG dataset labels (env 白名单)",
    description=(
        "## 用途\n\n"
        "返 env `KG_ALLOWED_DATASETS` 配置的 dataset label 白名单 — "
        "前端 KG 抽取页 dataset 下拉框渲染用 (跟 /datasets Dify 列表区分).\n\n"
        "## 鉴权\n\n"
        "无 (公开端点, 仅返 env 白名单, 无敏感数据).\n\n"
        "## 行为\n\n"
        "返 `[{label: str}, ...]`, 跟 env 配置一致. "
        "运行时修改 env 需重启服务 (Python 启动时固化)."
    ),
)
def list_kg_datasets() -> list[dict]:
    """列 env 白名单 dataset labels (公开读)"""
    return [{"label": d} for d in _kg_datasets.list_datasets()]


# ============== 任务列表 (2026-07-03 列表页) ==============


@router.get(
    "/extract/tasks",
    summary="列抽取任务",
    description=(
        "列出 TaskStore 中的后台任务 — 支持 kind 过滤 (kg_extract / kg_batch / all) + 分页 (limit/offset). "
        '鉴权: require_page("knowledge").'
    ),
    responses={
        200: {"description": "返 {items, total, total_success, total_failed, limit, offset}"},
        422: {"description": "kind 不在枚举"},
        403: {"description": "权限不足"},
    },
)
def list_extract_tasks(
    kind: str = "kg_extract",
    limit: int = 20,
    offset: int = 0,
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    """列本知识库后台任务 (kg_extract + kg_batch), 支持 kind 过滤 + limit/offset 分页"""
    if kind not in ("kg_extract", "kg_batch", "all"):
        raise HTTPException(422, "kind 必须在 [kg_extract, kg_batch, all]")
    # 拿 200 条 in-memory 全集做 kind 过滤 + offset 切割
    all_tasks = _task_store.list_recent(limit=200)
    if kind != "all":
        all_tasks = [t for t in all_tasks if t.kind == kind]
    total = len(all_tasks)
    page = all_tasks[offset : offset + limit]
    return {
        "items": [_serialize_task(t) for t in page],
        "total": total,
        "total_success": sum(t.success for t in all_tasks),
        "total_failed": sum(t.failed for t in all_tasks),
        "limit": limit,
        "offset": offset,
    }


def _serialize_task(t) -> dict:
    """把 TaskStatus 序列化成 API 响应; kg_extract 摊平 payload 里的 dataset/extractor/splitter/uri"""
    base = {
        "task_id": t.task_id,
        "kind": t.kind,
        "state": t.state,
        "success": t.success,
        "failed": t.failed,
        "created_at": t.created_at,
        "started_at": t.started_at,
        "finished_at": t.finished_at,
    }
    if t.kind == "kg_extract":
        base.update(
            {
                "dataset": t.payload.get("dataset"),
                "extractor": t.payload.get("extractor"),
                "splitter": t.payload.get("splitter"),
                "uri": t.payload.get("uri"),
            }
        )
    return base


# ============== 抽取 API (extract/...) ==============


@router.get(
    "/extract/extractors",
    summary="列可用抽取器",
    description=("返 2 个白名单: spacy_rule / llm_pydantic. 公开端点, 不鉴权. (hanlp/rebel 已删除, 见 PR2 Task 12)"),
)
def list_extractors() -> list[dict]:
    """白名单 (公开)"""
    return [{"id": eid, "available": True} for eid in list_extractor_ids()]


@router.get(
    "/extract/splitters",
    summary="列可用切片器",
    description="返 3 个白名单: heading / token / semantic + 每种的 chunk_size range.",
)
def list_splitters() -> list[dict]:
    return [
        {"id": "heading", "chunk_size_range": [100, 5000]},
        {"id": "token", "chunk_size_range": [128, 2048]},
        {"id": "semantic", "chunk_size_range": [200, 2000]},
    ]


@router.post(
    "/extract/upload",
    summary="上传 Markdown 文件到 ObjectStore",
    description=(
        "前端上传 .md 文件到 ObjectStore (local:// or s3://). "
        "**文件限制**: ≤5MB. **返回**: `{uri, file_id, dataset}` — uri 给 /start 端点. "
        '鉴权: require_page("knowledge").'
    ),
    responses={
        200: {"description": "成功, 返 `{uri, file_id, dataset}`"},
        413: {"description": "文件超过 5MB"},
        403: {"description": "权限不足 (require_page knowledge)"},
        422: {"description": "dataset 不在白名单"},
    },
)
async def upload_extract_file(
    file: UploadFile = File(...),
    dataset: str = "motor",  # v3: dataset 必传
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    _kg_datasets.validate_dataset(dataset)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "文件超过 5MB 限制")
    file_id = uuid4().hex[:12]
    key = f"inputs/{dataset}/{file_id}/source.md"  # v3: key 含 dataset
    store = get_object_store()
    if store.backend_name() == "minio":
        uri = build_uri("s3", key, "rag-extract")
    else:
        uri = build_uri("local", key)
    store.put_bytes(uri, content, mime="text/markdown")
    return {"uri": uri, "file_id": file_id, "dataset": dataset}


class StartExtractRequest(BaseModel):
    uri: str = Field(..., description="ObjectStore URI")
    dataset: str = Field(..., description="Neo4j dataset label (env 白名单)")
    extractor: Literal["spacy_rule", "llm_pydantic"] = Field(...)
    splitter: Literal["heading", "token", "semantic"] = Field(...)


def _build_extractor(extractor_id: str):
    """工厂函数: extractor_id → BaseExtractor 实例

    spacy_rule 懒加载 spaCy 模型 (避免启动期 slow load), 加载失败抛 HTTPException 503
    提示用户安装命令, 符合"业务侧 0 静默降级"原则.
    """
    if extractor_id == "spacy_rule":
        # 重依赖 lazy: spacy 模型加载 ~1s, 非 spacy_rule extractor 路径不需要
        from src.core.spacy_manager import get_spacy_model  # noqa: E402

        try:
            nlp = get_spacy_model("zh_core_web_sm")
        except RuntimeError as e:
            # spacy 模型未下载 → 503 明确提示, 不静默降级返 None
            raise HTTPException(
                status_code=503,
                detail=str(e),
            ) from e
        return SpacyRuleExtractor(nlp=nlp)
    if extractor_id == "llm_pydantic":
        return LlmPydanticExtractor(llm=None)
    raise ValueError(f"未知 extractor_id: {extractor_id}")


def _build_splitter(splitter_id: str):
    """工厂函数: splitter_id → BaseSplitter 实例"""
    if splitter_id == "heading":
        return HeadingSplitter()
    if splitter_id == "token":
        return TokenSplitter(chunk_size=512, overlap=32)
    if splitter_id == "semantic":
        return SemanticSplitter(embedder=None)  # v1: None → 降级 heading
    raise ValueError(f"未知 splitter_id: {splitter_id}")


@router.post(
    "/extract/start",
    summary="启动后台抽取",
    description=(
        "接收 /upload 返回的 uri + 选定的 extractor/splitter + dataset → "
        "BackgroundTasks 后台跑 run_extraction. "
        '**返回**: `{task_id, state: "queued"}` — 前端轮询 GET /tasks/{id}. '
        '鉴权: require_page("knowledge") + @audited("kg.extract.start").'
    ),
    responses={
        200: {"description": "返 `{task_id, state}`"},
        422: {"description": "Pydantic 校验失败 (extractor/splitter 不在白名单) 或 dataset 不在白名单"},
    },
)
@audited("kg.extract.start", target_type="kg_extract_task")
def start_extract(
    request: Request,
    req: StartExtractRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    _kg_datasets.validate_dataset(req.dataset)
    task_id = _task_store.submit(
        "kg_extract",
        {
            "dataset": req.dataset,
            "uri": req.uri,
            "extractor": req.extractor,
            "splitter": req.splitter,
        },
    )
    extractor = _build_extractor(req.extractor)
    splitter = _build_splitter(req.splitter)

    background_tasks.add_task(
        run_extraction,
        task_id=task_id,
        dataset=req.dataset,
        source_uri=req.uri,
        extractor=extractor,
        splitter=splitter,
        extractor_id=req.extractor,
        splitter_id=req.splitter,
    )

    request.state.audit_ctx.set(
        target_id=task_id,
        dataset=req.dataset,
        extractor=req.extractor,
        splitter=req.splitter,
    )
    return {"task_id": task_id, "state": "queued"}


@router.get(
    "/extract/tasks/{task_id}",
    summary="查任务状态",
    description=("前端轮询用 (1s 间隔). 返 state / success / failed / errors. **404**: task_id 不存在."),
    responses={
        200: {"description": "返 TaskStatus"},
        404: {"description": "任务不存在"},
    },
)
def get_extract_task(
    task_id: str,
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    try:
        t = _task_store.get(task_id)
    except TaskNotFoundError:
        raise HTTPException(404, f"任务不存在: {task_id}")
    return {
        "task_id": t.task_id,
        "state": t.state,
        "success": t.success,
        "failed": t.failed,
        "errors": t.errors,
    }


# ============== 4 端点 preview/items PATCH/commit/export ==============


@router.get(
    "/extract/tasks/{task_id}/preview",
    summary="预览抽取结果",
    description=(
        "从 kg_extract_items 读当前 dataset + task_id 的 entity/relation 列表. "
        "**返**: `{entities: [{id, text, label, selected, chunk_id, ...}], relations: [...]}`. "
        "payload 是 dict (psycopg3 JSONB 自动反序列化)."
    ),
)
def get_extract_preview(
    task_id: str,
    dataset: str = "motor",
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    _kg_datasets.validate_dataset(dataset)
    with session_scope() as session:
        rows = session.execute(
            text("""
            SELECT id, kind, payload, selected, chunk_id
            FROM kg_extract_items
            WHERE task_id = :tid AND dataset = :ds
            ORDER BY id
        """),
            {"tid": task_id, "ds": dataset},
        ).fetchall()
    entities = []
    relations = []
    for r in rows:
        item = dict(r[2])  # payload 是 dict (psycopg3 JSONB)
        item["id"] = r[0]
        item["selected"] = r[3]
        item["chunk_id"] = r[4]
        if r[1] == "entity":
            entities.append(item)
        else:
            relations.append(item)
    return {"entities": entities, "relations": relations}


class PatchItem(BaseModel):
    id: int = Field(..., description="kg_extract_items.id")
    selected: bool = Field(...)
    corrected_payload: dict | None = Field(None, description="用户编辑后的 payload, NULL=未改")


class PatchItemsRequest(BaseModel):
    items: list[PatchItem]


@router.patch(
    "/extract/tasks/{task_id}/items",
    summary="保存用户编辑 (勾选 + 修正)",
    description=(
        "前端预览页每行可勾选/取消勾选, 可编辑文本. "
        "PATCH 提交后写入 corrected_payload + confirmed_at. "
        '鉴权: require_page("knowledge") + @audited("kg.extract.items.update").'
    ),
)
@audited("kg.extract.items.update", target_type="kg_extract_task")
def patch_extract_items(
    request: Request,
    task_id: str,
    req: PatchItemsRequest,
    dataset: str = "motor",
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    _kg_datasets.validate_dataset(dataset)
    with session_scope() as session:
        for item in req.items:
            cp = item.corrected_payload or {}
            session.execute(
                text("""
                UPDATE kg_extract_items
                SET selected = :sel,
                    corrected_payload = CAST(:cp AS jsonb),
                    confirmed_at = NOW()
                WHERE id = :id AND task_id = :tid AND dataset = :ds
            """),
                {
                    "sel": item.selected,
                    "cp": json.dumps(cp, ensure_ascii=False),
                    "id": item.id,
                    "tid": task_id,
                    "ds": dataset,
                },
            )
    request.state.audit_ctx.set(target_id=task_id, dataset=dataset, updated=len(req.items))
    return {"updated": len(req.items)}


@router.post(
    "/extract/tasks/{task_id}/commit",
    summary="将选中结果写入 Neo4j",
    description=(
        "读 kg_extract_items 中 kind='relation' AND selected=true 的行 → "
        "构 TripleRow → KgClient(dataset=dataset).batch_upsert_triples → 写 Neo4j + audit_log. "
        '鉴权: require_page("knowledge") + @audited("kg.extract.commit").'
    ),
)
@audited("kg.extract.commit", target_type="kg_extract_task")
def commit_extract(
    request: Request,
    task_id: str,
    dataset: str = "motor",
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    _kg_datasets.validate_dataset(dataset)
    rows: list[TripleRow] = []

    with session_scope() as session:
        items = session.execute(
            text("""
            SELECT corrected_payload, payload FROM kg_extract_items
            WHERE task_id = :tid AND dataset = :ds
              AND kind = 'relation' AND selected = true
        """),
            {"tid": task_id, "ds": dataset},
        ).fetchall()

    for r in items:
        rel = r[0] or r[1]
        if not rel:
            continue
        rows.append(
            TripleRow(
                from_label=rel.get("from_label", "Entity"),
                from_key="name",
                from_value=rel["head"],
                rel_type=rel["rel_type"],
                to_label=rel.get("to_label", "Entity"),
                to_key="name",
                to_value=rel["tail"],
                properties={
                    "rule_type": rel.get("rule_type", "factual"),
                    "source_chunk": rel.get("chunk_id"),
                },
            )
        )

    # v3: KgClient(dataset=dataset) 注入 dataset label
    result = KgClient(dataset=dataset).batch_upsert_triples(rows)
    request.state.audit_ctx.set(
        target_id=task_id,
        dataset=dataset,
        after={"success": result.success, "failed": result.failed, "errors": result.errors},
    )
    return {"success": result.success, "failed": result.failed, "errors": result.errors}


@router.get(
    "/extract/tasks/{task_id}/export",
    summary="导出 JSONL / Cypher",
    description=(
        "2 种格式: `?format=jsonl` → application/x-ndjson, `?format=cypher` → text/plain. "
        "只导出 selected=true 的行. "
        '鉴权: require_page("knowledge") + @audited("kg.extract.export").'
    ),
)
@audited("kg.extract.export", target_type="kg_extract_task")
def export_extract(
    request: Request,
    task_id: str,
    format: Literal["jsonl", "cypher"] = "jsonl",
    dataset: str = "motor",
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> StreamingResponse:
    _kg_datasets.validate_dataset(dataset)

    with session_scope() as session:
        items = session.execute(
            text("""
            SELECT corrected_payload, payload
            FROM kg_extract_items
            WHERE task_id = :tid AND dataset = :ds AND selected = true
        """),
            {"tid": task_id, "ds": dataset},
        ).fetchall()

    request.state.audit_ctx.set(target_id=task_id, dataset=dataset, format=format)

    if format == "jsonl":
        body = "\n".join(json.dumps(r[0] or r[1], ensure_ascii=False) for r in items).encode("utf-8")
        return StreamingResponse(
            iter([body]),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="kg-{dataset}-{task_id}.jsonl"'},
        )

    # cypher: v3 用 :<Dataset> label 字面量, 单 DB 不需要 USE motor
    stmts: list[str] = []
    for r in items:
        data = r[0] or r[1]
        if not data or "rel_type" not in data:
            continue
        head = _escape(data["head"])
        tail = _escape(data["tail"])
        rel = _escape(data["rel_type"])
        stmts.append(
            f"MERGE (a:`{data.get('from_label', 'Entity')}`:`{dataset}` {{name: '{head}'}}) "
            f"MERGE (b:`{data.get('to_label', 'Entity')}`:`{dataset}` {{name: '{tail}'}}) "
            f"MERGE (a)-[r:`{rel}`]->(b);"
        )
    body = "\n".join(stmts).encode("utf-8")
    return StreamingResponse(
        iter([body]),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="kg-{dataset}-{task_id}.cypher"'},
    )


def _escape(s: str) -> str:
    r"""Cypher 字符串转义 (单引号 + 反斜杠 + 换行符)

    v1 简化版: 只转义 ' \ \n. 生产环境应走 Neo4j 参数化.
    """
    return s.replace("\\", "\\\\").replace("'", r"\'").replace("\n", r"\n")
