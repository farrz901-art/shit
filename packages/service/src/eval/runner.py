"""异步评估运行器: 跑 Dify + DeepEval Evaluation, 落 Evaluation + EvaluationSample

设计要点 (从 scripts/batch_rag_eval.py 复盘):
1. Dify 异步调用 + 整体限并发 (之前漏 sem 块导致 6 个 achat 全开)
2. DeepEval 5 指标 (faithfulness / answer_relevancy / context_precision / context_recall / hallucination), 全 async API
3. sample 按 index 入库, 详情页查得有序
4. 任何题失败不影响其他题, 最终聚合 successful/failed
5. 取消机制: cancel_event (asyncio.Event) 在每题前检查
6. 状态机: pending (行级 INSERT) → running → completed | failed | cancelled
7. (2026-06-18) Dify chat 响应加 Redis 10min 缓存: 重复 query 10min 内 0 Dify LLM 调用
8. (2026-06-29) 评估后端切换到 DeepEval 5 指标 (T7 of LC 替换)
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..integrations.dify_client import DifyAPIError
from ..storage.object_store import get_object_store
from ..storage.session import session_scope
from ..utils.timezone import HKT
from .csv_parser import parse_eval_csv
from .models import Evaluation, EvaluationSample

# 评估结果落库的 5 个指标 key (跟 RAGAMetrics.to_dict 对齐, 2026-06-29 加 hallucination)
_METRIC_KEYS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall", "hallucination")


async def _dify_achat_with_cache(dify: Any, query: str) -> dict[str, Any]:
    """Dify chat 调用前查 Redis 缓存 (2026-06-18 redis spec §5.5).

    hit: 返 cached dict (跳过 Dify LLM 调用, 0 token 消耗)
    miss: 调 dify.achat + fire-and-forget 写 cache
    fail-open: Redis 挂 → cached 返 None, 业务侧直调 Dify (跟 spec 一样)

    Args:
        dify: DifyClient 实例
        query: 用户问题

    Returns:
        dify.achat() 形状的 dict (含 answer/contexts/sources/raw/...)
    """
    # 防循环: 顶层 from ..core.dify_query_cache 触发 src.core.dify_query_cache 模块装载链
    # (core.redis_client 等), eval 模块加载时不需要付出这层开销
    from ..core.dify_query_cache import cache_chat_response, get_cached_chat_response  # noqa: E402

    cached = await get_cached_chat_response(query)
    if cached is not None:
        return cached

    # miss: 调 Dify
    result = await dify.achat(query)

    # fire-and-forget 写 cache: 失败不阻塞主流程
    # 用 create_task 而非 await, 让 Dify 响应先返回给 caller
    asyncio.create_task(cache_chat_response(query, result))
    return result


async def _evaluate_one(
    index: int,
    item: dict,
    dify: Any,
    evaluator: Any,
    sem: asyncio.Semaphore,
) -> dict:
    """单题评估, 返回结果 dict (不直接落库, 由 caller 决定)"""
    question = item["question"]
    ground_truth = item.get("ground_truth")

    async with sem:
        # 1. 调 Dify (2026-06-18 加 chat 缓存包装, 重复 query 10min 内 0 Dify LLM)
        try:
            dify_resp = await _dify_achat_with_cache(dify, question)
        except DifyAPIError as e:
            return {
                "index": index,
                "question": question,
                "ground_truth": ground_truth,
                "answer": None,
                "contexts": None,
                "sources": None,
                "metrics": None,
                "error": f"DifyAPIError: {e}",
            }
        answer = dify_resp.get("answer", "")
        contexts = dify_resp.get("contexts", [])
        # (2026-06-11 Task C) sources 透传到 sample, 供前端表格展示「召回到」
        sources = dify_resp.get("sources", [])

        # 2. 调评估器 (async API)
        try:
            metrics_obj = await evaluator.evaluate_single(
                question=question,
                answer=answer,
                contexts=contexts,
                ground_truth=ground_truth,
            )
        except Exception as e:
            return {
                "index": index,
                "question": question,
                "ground_truth": ground_truth,
                "answer": answer,
                "contexts": contexts,
                "sources": sources,
                "metrics": None,
                "error": f"DeepEvalError: {e}",
            }

    return {
        "index": index,
        "question": question,
        "ground_truth": ground_truth,
        "answer": answer,
        "contexts": contexts,
        "sources": sources,
        "metrics": metrics_obj.to_dict(),
        "error": None,
    }


async def run_evaluation(
    user_id: int,
    dataset_name: str,
    concurrency: int,
    dify: Any,
    evaluator: Any,
    evaluation_id: int | None = None,
    cancel_event: asyncio.Event | None = None,
    dataset: list[dict] | None = None,
    dataset_uri: str | None = None,
) -> int:
    """跑一次评估, 落库; 返回 evaluation.id

    Args:
        user_id: 发起评估的用户 id
        dataset_name: 数据集名 (CSV 文件名)
        concurrency: 同时跑多少题
        dify: DifyClient 实例
        evaluator: DeepEvalEvaluator 实例 (async API)
        evaluation_id: 已存在的 Evaluation.id (重启恢复场景), 默认新建
        cancel_event: 取消信号, set 后跳出循环
        dataset: [{question, ground_truth}, ...] 兼容旧调用方, 优先用 dataset_uri.
        dataset_uri: (2026-06-16) 对象存储 URI, 优先从 ABC 读 CSV.
                      旧 record (None) 走本地 DATASETS_DIR/{evaluation_id}.csv fallback.

    解析顺序:
    1. 若 dataset 已传 → 直接用
    2. 若 dataset_uri 给 → 走 ABC 读 bytes + parse_eval_csv
    3. 否则 → 走本地 fallback (F1 决策, 旧 record 兼容)

    Returns:
        evaluation.id (int)
    """
    sem = asyncio.Semaphore(concurrency)
    start = time.perf_counter()

    # 0. (2026-06-16) 决定 dataset 来源: 显式 dataset > URI > 本地 fallback
    if not dataset:
        if dataset_uri:
            store = get_object_store()
            content = store.get_bytes(dataset_uri)
            dataset = parse_eval_csv(content, filename=dataset_uri)
        elif evaluation_id is not None:
            # 旧 record: 走本地 fallback (F1 决策)
            dataset_path = Path(f"data/eval_datasets/{evaluation_id}.csv")
            if dataset_path.exists():
                dataset = parse_eval_csv(dataset_path.read_bytes(), filename=str(dataset_path))

    if not dataset:
        raise FileNotFoundError(f"Eval 无 dataset (无 URI 也无本地 fallback, evaluation_id={evaluation_id})")

    # 1. 落 Evaluation 行 (status=pending) + 立刻翻 running
    with session_scope() as s:
        if evaluation_id is None:
            e = Evaluation(
                user_id=user_id,
                dataset_name=dataset_name,
                status="pending",
                total_samples=len(dataset),
                concurrency=concurrency,
            )
            s.add(e)
            s.flush()
            evaluation_id = e.id
        else:
            e = s.get_one(Evaluation, evaluation_id)
            e.status = "running"
            e.total_samples = len(dataset)

    # 2. 检查 DB 中的 cancel_requested_at (进程重启恢复场景)
    if cancel_event is not None:
        with session_scope() as s:
            e = s.get_one(Evaluation, evaluation_id)
            if e.cancel_requested_at is not None:
                cancel_event.set()

    # 3. 检查取消
    if cancel_event is not None and cancel_event.is_set():
        with session_scope() as s:
            e = s.get_one(Evaluation, evaluation_id)
            e.status = "cancelled"
            e.cancel_requested_at = datetime.now(HKT)
            e.finished_at = datetime.now(HKT)
        return evaluation_id

    # 4. 切 running
    with session_scope() as s:
        e = s.get_one(Evaluation, evaluation_id)
        e.status = "running"

    # 5. 异步跑题 (边完成边落 sample)
    sample_results: list[dict] = []

    async def run_with_cancel_check(idx: int, item: dict) -> dict | None:
        if cancel_event is not None and cancel_event.is_set():
            return None
        result = await _evaluate_one(idx, item, dify, evaluator, sem)
        # 完成一条立刻落 sample
        with session_scope() as s:
            sample = EvaluationSample(
                evaluation_id=evaluation_id,
                index=result["index"],
                question=result["question"],
                ground_truth=result["ground_truth"],
                answer=result["answer"],
                contexts=result["contexts"],
                sources=result.get("sources"),  # (2026-06-11 Task C)
                metrics=result["metrics"],
                error=result["error"],
            )
            s.add(sample)
        return result

    tasks = [run_with_cancel_check(i, item) for i, item in enumerate(dataset)]
    results = await asyncio.gather(*tasks)

    # 5. 取消 → 终止 (results 里 None 是被取消的)
    if cancel_event is not None and cancel_event.is_set():
        sample_results = [r for r in results if r is not None]
        with session_scope() as s:
            e = s.get_one(Evaluation, evaluation_id)
            e.status = "cancelled"
            e.cancel_requested_at = datetime.now(HKT)
            e.successful = sum(1 for r in sample_results if r["error"] is None)
            e.failed = sum(1 for r in sample_results if r["error"] is not None)
            e.finished_at = datetime.now(HKT)
            e.duration_seconds = time.perf_counter() - start
        return evaluation_id

    # 6. 正常完成 → 聚合
    sample_results = [r for r in results if r is not None]
    valid_metrics = [r["metrics"] for r in sample_results if r["metrics"]]
    avg: dict[str, float | None] = {k: None for k in _METRIC_KEYS}
    for k in _METRIC_KEYS:
        vals = [m[k] for m in valid_metrics if m.get(k) is not None]
        avg[k] = sum(vals) / len(vals) if vals else None

    successful = sum(1 for r in sample_results if r["error"] is None)
    failed = sum(1 for r in sample_results if r["error"] is not None)

    with session_scope() as s:
        e = s.get_one(Evaluation, evaluation_id)
        e.status = "completed"
        e.successful = successful
        e.failed = failed
        e.avg_metrics = avg
        e.duration_seconds = time.perf_counter() - start
        e.finished_at = datetime.now(HKT)

    return evaluation_id
