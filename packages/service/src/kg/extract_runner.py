"""抽取 pipeline: ObjectStore → splitter → extractor → PG kg_extract_items (2026-07-01 v3)

后台跑 (FastAPI BackgroundTasks), 状态写 TaskStore.

v3 关键: 加 dataset 参数透传到 KgClient + PG INSERT (kg_extract_items.dataset 列)

失败处理:
- extractor 整批失败 (error 字段) → TaskStore.mark_failed, 不 INSERT
- 单 chunk 失败 → errors[] 累积, 继续 (tenacity 内部 retry, 外部不管)
- ObjectStore / splitter 抛错 → TaskStore.mark_failed, 整 task 失败

状态机: queued → running → done (全部成功) / partial (部分失败) / failed (整批失败)

使用方式:
    background_tasks.add_task(
        run_extraction,
        task_id=task_id, dataset=dataset, source_uri=uri,
        extractor=extractor, splitter=splitter,
    )
"""

from __future__ import annotations

import time

from loguru import logger
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from src.storage import session_scope
from src.storage.object_store import ObjectStore, get_object_store

from .datasets import validate_dataset
from .tasks import TaskStore

# JSONB 写入 mode A: CAST(:p AS jsonb) + bindparam(type_=JSONB)
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
    """后台 pipeline 入口

    Args:
        task_id: TaskStore 已 submit 的 task_id
        dataset: 8 字符 user 隔离 hash 改为 dataset label (v3, env 白名单)
        source_uri: ObjectStore URI (e.g. "local://inputs/abc/source.md" 或 "s3://rag-extract/inputs/...")
        extractor: 注入的 BaseExtractor 实例 (支持 Protocol, 测试可传 MagicMock)
        splitter: 注入的 BaseSplitter 实例
        extractor_id: 抽取器 ID (e.g. "spacy_rule")
        splitter_id: 切片器 ID (e.g. "heading")
        object_store: 注入的 ObjectStore (默认 get_object_store())
        task_store: 注入的 TaskStore (默认全局单例)

    Raises:
        不抛异常给调用方: 所有异常在函数内 catch → mark_failed
    """
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
                session.execute(
                    _INSERT_ENTITY_SQL,
                    {
                        "tid": task_id,
                        "ds": dataset,
                        "ext": extractor_id,
                        "spl": splitter_id,
                        "cid": ent.chunk_id,
                        "p": {
                            "text": ent.text,
                            "label": ent.label,
                            "char_span": list(ent.char_span),
                            "confidence": ent.confidence,
                        },
                    },
                )
            for rel in result.relations:
                session.execute(
                    _INSERT_RELATION_SQL,
                    {
                        "tid": task_id,
                        "ds": dataset,
                        "ext": extractor_id,
                        "spl": splitter_id,
                        "cid": rel.chunk_id,
                        "p": {
                            "head": rel.head,
                            "rel_type": rel.tail,
                            "tail": rel.tail,
                            "rule_type": rel.rule_type,
                            "confidence": rel.confidence,
                        },
                    },
                )

        elapsed_ms = int((time.time() - started) * 1000)
        task_store.mark_done(
            task_id,
            success=len(result.entities) + len(result.relations),
        )
        logger.info("kg_extract done task={} dataset={} elapsed_ms={}", task_id, dataset, elapsed_ms)

    except Exception as e:
        logger.opt(exception=True).error("kg_extract failed task={} dataset={}", task_id, dataset)
        task_store.mark_failed(task_id, str(e)[:500])
