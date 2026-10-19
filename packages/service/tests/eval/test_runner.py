"""异步评估运行器测试 (2026-06-16 重写 100% mock, 5 tests)

跑 run_evaluation 走完整流: 创 evaluation + 落 sample + 聚合状态.
mock 两层:
1. src.eval.runner.session_scope 替 mock (所有 DB 操作落 mock)
2. dify / evaluator 由 caller 注入 (跟 runner 设计一致, 本身就需要)
3. (2026-06-18) dify_query_cache 替 no-op mock, 避免连真 Redis

0 真实 DB 连接, 0 dev DB writes.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.eval.models import Evaluation, EvaluationSample
from src.eval.runner import run_evaluation
from src.integrations.dify_client import DifyAPIError


@pytest.fixture(autouse=True)
def _mock_dify_query_cache(monkeypatch):
    """(2026-06-18 redis) 测试不连真 Redis: 把 chat cache 替 no-op.

    get 永远 None (当 miss) → 跑原 dify.achat (已经 mock)
    cache 永远 no-op → 写不进 Redis, 不影响测试结果
    """

    async def fake_get_cached_chat_response(query: str):
        return None

    async def fake_cache_chat_response(query: str, response: dict):
        return None

    monkeypatch.setattr(
        "src.eval.runner._dify_achat_with_cache.__wrapped__"
        if False
        else "src.core.dify_query_cache.get_cached_chat_response",
        fake_get_cached_chat_response,
    )
    monkeypatch.setattr(
        "src.core.dify_query_cache.cache_chat_response",
        fake_cache_chat_response,
    )


# ---------------- helpers ----------------


def _mock_dify_client(answer_fmt: str = "答: {q}", error_for: str | None = None) -> MagicMock:
    """mock DifyClient: 每题返 answer/contexts; 某题 (question=error_for) 抛 DifyAPIError"""
    dify = MagicMock()

    async def achat(q):
        if error_for and q == error_for:
            raise DifyAPIError("dify down")
        return {
            "answer": answer_fmt.format(q=q),
            "contexts": [f"ctx-for-{q}"],
            "conversation_id": "",
            "raw": {},
        }

    dify.achat = AsyncMock(side_effect=achat)
    return dify


def _mock_evaluator(error_for: str | None = None) -> MagicMock:
    """mock RAGAS evaluator: 4 指标都给 0.8; 某题 (question 含 error_for 子串) 抛 RuntimeError

    evaluate_single 必须 async (runner 调 `await evaluator.evaluate_single(...)`).
    """
    ev = MagicMock()

    async def evaluate_single(**kwargs):
        if error_for and error_for in kwargs.get("question", ""):
            raise RuntimeError(f"ragas broke on {error_for}")
        m = MagicMock()
        m.to_dict = MagicMock(
            return_value={
                "faithfulness": 0.8,
                "answer_relevancy": 0.8,
                "context_precision": 0.8,
                "context_recall": 0.8,
            }
        )
        return m

    ev.evaluate_single = AsyncMock(side_effect=evaluate_single)
    return ev


class _SessionScopePatch:
    """mock session_scope 包装: 所有 with block 走同一个 mock_session

    flush() 副作用: 把 add() 的对象设上 id (模拟 autoincrement)
    """

    def __init__(self):
        self.session = MagicMock()
        self.evaluations: dict[int, Evaluation | MagicMock] = {}
        self._next_eval_id = 1
        self._session_scope_call_count = 0

        def fake_flush():
            if self.session.add.called:
                added_obj = self.session.add.call_args_list[-1][0][0]
                if isinstance(added_obj, Evaluation) and getattr(added_obj, "id", None) is None:
                    added_obj.id = self._next_eval_id
                    self.evaluations[self._next_eval_id] = added_obj
                    self._next_eval_id += 1

        self.session.flush.side_effect = fake_flush

        # get_one(Evaluation, id) -> 返之前创的 eval
        def get_one(model, id_):
            if model is Evaluation:
                return self.evaluations.get(id_) or MagicMock(spec=Evaluation)
            return MagicMock(spec=model)

        self.session.get_one.side_effect = get_one
        self.session.get.side_effect = get_one

    def __enter__(self):
        self._patcher = patch("src.eval.runner.session_scope")
        p = self._patcher.__enter__()

        def counting_enter():
            self._session_scope_call_count += 1
            return self.session

        p.return_value.__enter__.side_effect = counting_enter
        p.return_value.__exit__.return_value = False
        return self

    def __exit__(self, *args):
        return self._patcher.__exit__(*args)


# ---------------- tests ----------------


def test_run_evaluation_creates_evaluation_and_samples():
    """跑 2 题 -> 1 evaluation + 2 samples, status=completed, avg_metrics 4 指标"""
    dataset = [
        {"question": "Q1", "ground_truth": "A1"},
        {"question": "Q2", "ground_truth": "A2"},
    ]
    with _SessionScopePatch() as sp:
        result_id = asyncio.run(
            run_evaluation(
                user_id=1,
                dataset_name="test.csv",
                dataset=dataset,
                concurrency=2,
                dify=_mock_dify_client(),
                evaluator=_mock_evaluator(),
            )
        )

    assert result_id == 1
    # 1 evaluation + 2 samples 落库
    eval_calls = [c for c in sp.session.add.call_args_list if isinstance(c[0][0], Evaluation)]
    sample_calls = [c for c in sp.session.add.call_args_list if isinstance(c[0][0], EvaluationSample)]
    assert len(eval_calls) == 1
    assert len(sample_calls) == 2

    # final state 在 mock eval 上
    e = sp.evaluations[1]
    assert e.status == "completed"
    assert e.total_samples == 2
    assert e.successful == 2
    assert e.failed == 0
    assert e.user_id == 1
    assert e.dataset_name == "test.csv"
    assert e.avg_metrics == {
        "faithfulness": 0.8,
        "answer_relevancy": 0.8,
        "context_precision": 0.8,
        "context_recall": 0.8,
        "hallucination": None,
    }
    assert e.duration_seconds is not None
    assert e.finished_at is not None

    # samples: 顺序按 index 0, 1
    s0 = sample_calls[0][0][0]
    s1 = sample_calls[1][0][0]
    assert s0.index == 0
    assert s0.question == "Q1"
    assert s0.answer == "答: Q1"
    assert s0.contexts == ["ctx-for-Q1"]
    assert s0.error is None
    assert s1.index == 1
    assert s1.question == "Q2"
    assert s1.answer == "答: Q2"


def test_run_evaluation_continues_on_dify_error():
    """Dify 失败时: 该 sample 写 error, 其他 sample 正常, status=completed"""
    dataset = [
        {"question": "GOOD1", "ground_truth": "a"},
        {"question": "BAD", "ground_truth": "b"},
        {"question": "GOOD2", "ground_truth": "c"},
    ]
    with _SessionScopePatch() as sp:
        asyncio.run(
            run_evaluation(
                user_id=1,
                dataset_name="t.csv",
                dataset=dataset,
                concurrency=1,
                dify=_mock_dify_client(error_for="BAD"),
                evaluator=_mock_evaluator(),
            )
        )

    e = sp.evaluations[1]
    assert e.status == "completed"
    assert e.successful == 2
    assert e.failed == 1

    sample_calls = [c for c in sp.session.add.call_args_list if isinstance(c[0][0], EvaluationSample)]
    bad = [c[0][0] for c in sample_calls if c[0][0].question == "BAD"][0]
    assert bad.metrics is None
    assert bad.answer is None
    assert "DifyAPIError" in (bad.error or "")


def test_run_evaluation_continues_on_ragas_error():
    """RAGAS 失败时: 落 answer/contexts, metrics=None, error 含 RAGASError"""
    dataset = [
        {"question": "ok-q", "ground_truth": None},
        {"question": "fail-me", "ground_truth": None},
    ]
    with _SessionScopePatch() as sp:
        asyncio.run(
            run_evaluation(
                user_id=1,
                dataset_name="t.csv",
                dataset=dataset,
                concurrency=1,
                dify=_mock_dify_client(),
                evaluator=_mock_evaluator(error_for="fail-me"),
            )
        )

    e = sp.evaluations[1]
    assert e.successful == 1
    assert e.failed == 1

    sample_calls = [c for c in sp.session.add.call_args_list if isinstance(c[0][0], EvaluationSample)]
    bad = [c[0][0] for c in sample_calls if c[0][0].question == "fail-me"][0]
    assert bad.answer == "答: fail-me"  # Dify OK, answer 已写入
    assert "ragas broke" in (bad.error or "")


def test_run_evaluation_persists_cancelled_status():
    """传入 cancelled event -> 第 1 题前检测, 跳出, status=cancelled, 0 samples"""
    event = asyncio.Event()
    event.set()  # 提前 set, 模拟"用户取消"

    dataset = [{"question": f"Q{i}", "ground_truth": None} for i in range(3)]
    with _SessionScopePatch() as sp:
        result_id = asyncio.run(
            run_evaluation(
                user_id=1,
                dataset_name="t.csv",
                dataset=dataset,
                concurrency=1,
                dify=_mock_dify_client(),
                evaluator=_mock_evaluator(),
                cancel_event=event,
            )
        )

    e = sp.evaluations[result_id]
    assert e.status == "cancelled"
    # cancel 提前跳出 -> 没生成 sample
    sample_calls = [c for c in sp.session.add.call_args_list if isinstance(c[0][0], EvaluationSample)]
    assert len(sample_calls) == 0


def test_run_evaluation_status_runs_through_states():
    """正常完成: 走过 running -> completed, 聚合 successful=2"""
    dataset = [{"question": f"Q{i}", "ground_truth": None} for i in range(2)]
    with _SessionScopePatch() as sp:
        asyncio.run(
            run_evaluation(
                user_id=1,
                dataset_name="t.csv",
                dataset=dataset,
                concurrency=1,
                dify=_mock_dify_client(),
                evaluator=_mock_evaluator(),
            )
        )

    e = sp.evaluations[1]
    # final state
    assert e.status == "completed"
    assert e.total_samples == 2
    assert e.successful == 2
    assert e.failed == 0
    # runner 调了多次 session_scope() (pending -> running -> sample落库 -> completed)
    # 至少 3 次 session_scope (init eval + running + final update)
    assert sp._session_scope_call_count >= 3
