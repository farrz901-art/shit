# Markdown Extract KG — PR3: 抽取 pipeline + API + cron (M6 + M7, v3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 后台抽取 pipeline (ObjectStore → splitter → extractor → PG `kg_extract_items`) + 9 端点 + 7d cron 清理。**v3 调整**: 所有端点加 `dataset` query param, 走 env 白名单。

**Scope (5 commits + 收尾, ~8h):**
- Task 14 (M6): extract_runner 后台 pipeline (dataset 透传 + mock 测全路径)
- Task 15 (M7): 5 端点 list_extractors/list_splitters/upload/start/tasks (含 dataset)
- Task 16 (M7): 4 端点 preview/items PATCH/commit/export (@audited 4 处 + dataset)
- Task 17 (M7): 7d cron 清理
- Task 18 (收尾): 后端全量测试 + ruff + pyright

**v3 关键**:
- 9 端点全部接 `dataset` query param (业务侧必传)
- `extract_runner` 注入 dataset 到 `KgClient(dataset=dataset)` 和 `kg_extract_items.dataset`
- commit 走 `KgClient(dataset=dataset).batch_upsert_triples(rows)` 写入对应 dataset
- export cypher 不需要 `USE motor` (单 DB) 但要在 cypher 加 `:Motor` label

## 项目规约 (PR3 必须遵守)

1. **测试 100% mock**: mock ObjectStore / TaskStore / extractor / splitter / session_scope
2. **@audited 4 处**: start/items/commit/export
3. **JSONB 写入**: `CAST(:p AS jsonb)` + `json.dumps(dict_value)` (mode A, 跟 buyer_profile 一致)
4. **loguru**: `logger.info("kg_extract done task={}", task_id)`
5. **dataset 强校验**: 每个端点入口 `validate_dataset(dataset)`, 不在白名单 → 422

---

## Task 14: extract_runner 后台 pipeline

**Files:**
- Create: `packages/service/src/kg/extract_runner.py`
- Test: `packages/service/tests/kg/test_extract_runner.py` (3 个 test)

```python
# packages/service/src/kg/extract_runner.py
"""抽取 pipeline: ObjectStore → splitter → extractor → PG kg_extract_items (v3)

v3: 加 dataset 参数透传到 KgClient + PG INSERT
"""
from __future__ import annotations

import json
import time

from loguru import logger
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from src.storage import session_scope
from src.storage.object_store import ObjectStore, get_object_store
from .tasks import TaskStore
from .datasets import validate_dataset


_INSERT_ENTITY_SQL = text("""
    INSERT INTO kg_extract_items (task_id, dataset, extractor, splitter, kind, payload, chunk_id)
    VALUES (:tid, :ds, :ext, :spl, 'entity', CAST(:p AS jsonb), :cid)
""").bindparams(bindparam("p", type_=JSONB))


_INSERT_RELATION_SQL = text("""
    INSERT INTO kg_extract_items (task_id, dataset, extractor, splitter, kind, payload, chunk_id)
    VALUES (:tid, :ds, :ext, :spl, 'relation', CAST(:p AS jsonb), :cid)
""").bindparams(bindparam("p", type_=JSONB))


def run_extraction(
    task_id: str,
    dataset: str,
    source_uri: str,
    extractor,
    splitter,
    extractor_id: str = "",
    splitter_id: str = "",
    object_store: ObjectStore | None = None,
    task_store: TaskStore | None = None,
) -> None:
    validate_dataset(dataset)
    object_store = object_store or get_object_store()
    task_store = task_store or TaskStore()
    started = time.time()

    try:
        task_store.mark_running(task_id)
        text_bytes = object_store.get_bytes(source_uri)
        text_content = text_bytes.decode("utf-8")

        chunks = splitter.split(text_content, source_uri)
        logger.info("kg_extract split task={} dataset={} chunks={}", task_id, dataset, len(chunks))

        result = extractor.extract(chunks)
        if result.error:
            task_store.mark_failed(task_id, result.error)
            return

        with session_scope() as session:
            for ent in result.entities:
                session.execute(_INSERT_ENTITY_SQL, {
                    "tid": task_id, "ds": dataset,
                    "ext": extractor_id, "spl": splitter_id,
                    "cid": ent.chunk_id,
                    "p": {
                        "text": ent.text, "label": ent.label,
                        "char_span": list(ent.char_span),
                        "confidence": ent.confidence,
                    },
                })
            for rel in result.relations:
                session.execute(_INSERT_RELATION_SQL, {
                    "tid": task_id, "ds": dataset,
                    "ext": extractor_id, "spl": splitter_id,
                    "cid": rel.chunk_id,
                    "p": {
                        "head": rel.head, "rel_type": rel.rel_type, "tail": rel.tail,
                        "rule_type": rel.rule_type, "confidence": rel.confidence,
                    },
                })

        elapsed_ms = int((time.time() - started) * 1000)
        task_store.mark_done(
            task_id, success=len(result.entities) + len(result.relations),
        )
        logger.info("kg_extract done task={} dataset={} elapsed_ms={}", task_id, dataset, elapsed_ms)

    except Exception as e:
        logger.opt(exception=True).error("kg_extract failed task={} dataset={}", task_id, dataset)
        task_store.mark_failed(task_id, str(e)[:500])
```

```bash
git add packages/service/src/kg/extract_runner.py packages/service/tests/kg/test_extract_runner.py
git commit -m "feat(kg): extract_runner 后台 pipeline (ObjectStore → splitter → extractor → PG, dataset 透传)"
```

---

## Task 15: 5 个 API 端点 (list_extractors / list_splitters / upload / start / tasks)

**Files:**
- Modify: `packages/service/src/kg/router.py`
- Test: `packages/service/tests/kg/test_router_extract.py`

**v3 调整**: upload/start 必传 `dataset`, 调 `run_extraction` 时透传

```python
# 追加到 packages/service/src/kg/router.py 末尾
from fastapi import BackgroundTasks, File, UploadFile
from uuid import uuid4
from .extract_runner import run_extraction
from .config_loader import list_extractor_ids
from .extractors.llm_pydantic.extractor import LlmPydanticExtractor
from .extractors.spacy_rule.extractor import SpacyRuleExtractor
from .splitters.heading import HeadingSplitter
from .splitters.token import TokenSplitter
from .splitters.semantic import SemanticSplitter
from src.core.audit import audited
from src.storage.object_store import build_uri, get_object_store


@router.get("/extract/extractors", ...)
def list_extractors() -> list[dict]:
    """白名单 (公开)"""
    return [{"id": eid, "available": True} for eid in list_extractor_ids()]


@router.get("/extract/splitters", ...)
def list_splitters() -> list[dict]:
    return [
        {"id": "heading", "chunk_size_range": [100, 5000]},
        {"id": "token", "chunk_size_range": [128, 2048]},
        {"id": "semantic", "chunk_size_range": [200, 2000]},
    ]


@router.post("/extract/upload", ...)
async def upload_extract_file(
    request: Request,
    file: UploadFile = File(...),
    dataset: str = "motor",  # v3: 加 dataset
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    _kg_datasets.validate_dataset(dataset)
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(413, "文件超过 5MB 限制")
    body = await file.read()
    file_id = uuid4().hex[:12]
    key = f"inputs/{dataset}/{file_id}/source.md"  # v3: key 含 dataset
    store = get_object_store()
    if store.backend_name() == "minio":
        uri = build_uri("s3", key, "rag-extract")
    else:
        uri = build_uri("local", key)
    store.put_bytes(uri, body, mime="text/markdown")
    return {"uri": uri, "file_id": file_id, "dataset": dataset}


class StartExtractRequest(BaseModel):
    uri: str = Field(..., description="ObjectStore URI")
    dataset: str = Field(..., description="Neo4j dataset label (env 白名单)")
    extractor: Literal["spacy_rule", "llm_pydantic"] = Field(...)
    splitter: Literal["heading", "token", "semantic"] = Field(...)


def _build_extractor(extractor_id: str):
    if extractor_id == "spacy_rule":
        return SpacyRuleExtractor(nlp=None)
    if extractor_id == "llm_pydantic":
        return LlmPydanticExtractor(llm=None)
    raise ValueError(f"未知 extractor_id: {extractor_id}")


def _build_splitter(splitter_id: str):
    if splitter_id == "heading":
        return HeadingSplitter()
    if splitter_id == "token":
        return TokenSplitter(chunk_size=512, overlap=32)
    if splitter_id == "semantic":
        return SemanticSplitter(embedder=None)
    raise ValueError(f"未知 splitter_id: {splitter_id}")


@router.post("/extract/start", ...)
@audited("kg.extract.start", target_type="kg_extract_task")
def start_extract(
    request: Request,
    req: StartExtractRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    _kg_datasets.validate_dataset(req.dataset)
    task_id = _task_store.submit("kg_extract", {
        "dataset": req.dataset,
        "uri": req.uri,
        "extractor": req.extractor,
        "splitter": req.splitter,
    })
    extractor = _build_extractor(req.extractor)
    splitter = _build_splitter(req.splitter)

    background_tasks.add_task(
        run_extraction,
        task_id=task_id, dataset=req.dataset,
        source_uri=req.uri,
        extractor=extractor, splitter=splitter,
        extractor_id=req.extractor, splitter_id=req.splitter,
    )

    request.state.audit_ctx.set(
        target_id=task_id,
        dataset=req.dataset,
        extractor=req.extractor,
        splitter=req.splitter,
    )
    return {"task_id": task_id, "state": "queued"}


@router.get("/extract/tasks/{task_id}", ...)
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
```

```bash
git add packages/service/src/kg/router.py packages/service/tests/kg/test_router_extract.py
git commit -m "feat(kg): 5 端点 list_extractors/list_splitters/upload/start/tasks + BackgroundTasks + dataset 透传"
```

---

## Task 16: 4 端点 preview / items PATCH / commit / export

**Files:**
- Modify: `packages/service/src/kg/router.py`
- Test: `packages/service/tests/kg/test_commit_export.py` (4 个 test)

```python
# 追加到 packages/service/src/kg/router.py
import json as _json
from sqlalchemy import text as _sql_text


@router.get("/extract/tasks/{task_id}/preview", ...)
def get_extract_preview(
    task_id: str,
    dataset: str = "motor",
    current_user: CurrentUser = Depends(require_page("knowledge")),
) -> dict:
    _kg_datasets.validate_dataset(dataset)
    with session_scope() as session:
        rows = session.execute(_sql_text("""
            SELECT id, kind, payload, selected, chunk_id
            FROM kg_extract_items
            WHERE task_id = :tid AND dataset = :ds
            ORDER BY id
        """), {"tid": task_id, "ds": dataset}).fetchall()
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
    id: int
    selected: bool
    corrected_payload: dict | None = None


class PatchItemsRequest(BaseModel):
    items: list[PatchItem]


@router.patch("/extract/tasks/{task_id}/items", ...)
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
            session.execute(_sql_text("""
                UPDATE kg_extract_items
                SET selected = :sel,
                    corrected_payload = CAST(:cp AS jsonb),
                    confirmed_at = NOW()
                WHERE id = :id AND task_id = :tid AND dataset = :ds
            """), {
                "sel": item.selected,
                "cp": _json.dumps(cp, ensure_ascii=False),
                "id": item.id,
                "tid": task_id,
                "ds": dataset,
            })
    request.state.audit_ctx.set(target_id=task_id, dataset=dataset, updated=len(req.items))
    return {"updated": len(req.items)}


@router.post("/extract/tasks/{task_id}/commit", ...)
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
        items = session.execute(_sql_text("""
            SELECT corrected_payload, payload FROM kg_extract_items
            WHERE task_id = :tid AND dataset = :ds
              AND kind = 'relation' AND selected = true
        """), {"tid": task_id, "ds": dataset}).fetchall()

    for r in items:
        rel = r[0] or r[1]
        if not rel:
            continue
        rows.append(TripleRow(
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
        ))

    # v3: KgClient(dataset=dataset) 注入 dataset label
    result = KgClient(dataset=dataset).batch_upsert_triples(rows)
    request.state.audit_ctx.set(
        target_id=task_id, dataset=dataset,
        after={"success": result.success, "failed": result.failed, "errors": result.errors},
    )
    return {"success": result.success, "failed": result.failed, "errors": result.errors}


@router.get("/extract/tasks/{task_id}/export", ...)
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
        items = session.execute(_sql_text("""
            SELECT corrected_payload, payload
            FROM kg_extract_items
            WHERE task_id = :tid AND dataset = :ds AND selected = true
        """), {"tid": task_id, "ds": dataset}).fetchall()

    request.state.audit_ctx.set(target_id=task_id, dataset=dataset, format=format)

    if format == "jsonl":
        body = "\n".join(
            _json.dumps(r[0] or r[1], ensure_ascii=False)
            for r in items
        ).encode("utf-8")
        return StreamingResponse(
            iter([body]),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="kg-{dataset}-{task_id}.jsonl"'},
        )

    # cypher: v3 用 :<Dataset> label 字面量, 不需要 USE motor (单 DB)
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
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
```

```bash
git add packages/service/src/kg/router.py packages/service/tests/kg/test_commit_export.py
git commit -m "feat(kg): 4 端点 preview/items PATCH/commit/export + @audited 4 处 + dataset 透传"
```

---

## Task 17: 7d cron 清理

**Files:**
- Create: `packages/service/src/kg/cron.py`
- Test: `packages/service/tests/kg/test_cron.py`

```python
# packages/service/src/kg/cron.py
from dataclasses import dataclass
from loguru import logger
from sqlalchemy import text
from src.storage import session_scope


@dataclass
class CleanupResult:
    deleted_count: int = 0


def cleanup_old_extract_items(days: int = 7) -> CleanupResult:
    """删除 created_at < NOW() - INTERVAL '{days} days' 的 kg_extract_items"""
    sql = text(f"DELETE FROM kg_extract_items WHERE created_at < NOW() - INTERVAL '{int(days)} days'")
    with session_scope() as session:
        result = session.execute(sql)
        deleted_count = result.rowcount or 0
    logger.info("kg_extract_items cron cleanup days={} deleted={}", days, deleted_count)
    return CleanupResult(deleted_count=deleted_count)
```

```bash
git add packages/service/src/kg/cron.py packages/service/tests/kg/test_cron.py
git commit -m "feat(kg): cron cleanup_old_extract_items (7d hard-delete)"
```

---

## Task 18: PR3 全量验证

```bash
cd packages/service
uv run pytest tests/kg/ -v
uv run ruff format && uv run ruff check --fix && uv run pyright
```