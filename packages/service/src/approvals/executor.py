"""executor — apply_approval 按 kind dispatch 调 Dify/Neo4j, try/except 捕获写回状态.

复用原则: DifyDatasets (src.integrations.dify_datasets) 跟 KgClient (src.kg.client)
的调用方式跟现有 server action 完全一致, 不引入新逻辑.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from ..integrations.dify_datasets import DifyDatasets
from ..kg.client import KgClient, TripleRow
from .models import ApprovalKind
from .service import ApprovalService


async def apply_approval(
    approval_id: int,
    svc: ApprovalService,
    *,
    repo: Any,  # ApprovalRepo, 不 import 避免循环
) -> None:
    """同步执行, 失败捕获. 成功 → svc.mark_applied; 异常 → svc.mark_failed(error_msg=前 1000 字符)."""
    approval = await repo.get(approval_id)
    if approval is None:
        return  # 防御: 不该发生 (svc 校验过)
    payload = json.loads(approval.payload)

    try:
        if approval.kind == ApprovalKind.QA.value:
            text = f"Q: {payload['question']}\nA: {payload['answer']}"
            if payload.get("tags"):
                text += f"\nTags: {', '.join(payload['tags'])}"
            name = f"qa-{approval_id}-{payload.get('dataset_id', '')}"
            await DifyDatasets.createDocumentByText(
                payload["dataset_id"],
                name,
                text,
                "high_quality",
            )
            # 可选: 同步 Neo4j QAPair + ABOUT 关系 (失败不阻塞)
            if payload.get("sync_to_neo4j") and payload.get("tags"):
                try:
                    client = KgClient()
                    client.batch_upsert_triples(
                        [
                            TripleRow(
                                from_label="QAPair",
                                from_key="question",
                                from_value=payload["question"],
                                rel_type="ABOUT",
                                to_label="Product",
                                to_key="model",
                                to_value=payload["tags"][0],
                                properties={"answer": payload["answer"], "tags": payload["tags"]},
                            )
                        ]
                    )
                except Exception:
                    logger.exception("Neo4j 同步失败, approval_id={}", approval_id)
                    raise

        elif approval.kind == ApprovalKind.TRIPLE.value:
            client = KgClient()
            client.batch_upsert_triples([TripleRow(**r) for r in payload["rows"]])

        elif approval.kind == ApprovalKind.BATCH.value:
            for r in payload["rows"]:
                text = f"Q: {r['question']}\nA: {r['answer']}"
                if r.get("tags"):
                    text += f"\nTags: {r['tags']}"
                name = f"qa-{approval_id}-{payload['dataset_id']}"
                await DifyDatasets.createDocumentByText(
                    payload["dataset_id"],
                    name,
                    text,
                )

        elif approval.kind == ApprovalKind.OPTIMIZE.value:
            # OPTIMIZE 必传 question + improved_answer, 缺则 KeyError → BGTask 捕获 → apply=failed
            # original_answer / reason 可选 (.get 兜底 OK)
            text = (
                f"Q: {payload['question']}\n"
                f"原: {payload.get('original_answer', '')}\n"
                f"改: {payload['improved_answer']}\n"
                f"原因: {payload.get('reason', '')}"
            )
            name = f"optimize-{approval_id}"
            await DifyDatasets.createDocumentByText(
                payload["dataset_id"],
                name,
                text,
            )

        await svc.mark_applied(approval_id)
    except Exception as e:
        await svc.mark_failed(approval_id, f"{type(e).__name__}: {e}")
