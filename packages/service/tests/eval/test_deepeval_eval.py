"""测试 DeepEvalEvaluator (5 metrics, mock 所有 DeepEval 内部)"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.eval.deepeval_eval import DeepEvalError, DeepEvalEvaluator, DeepSeekJudge


def test_deepseek_judge_is_deepeval_basellm():
    """DeepSeekJudge 必须继承 DeepEvalBaseLLM, 才能传给 deepeval metric (不抛 TypeError).

    根因 (2026-06-30): DeepSeekJudge 是普通 class, initialize_model() 走 isinstance 检查
    DeepEvalBaseLLM 失败 → TypeError. 修法: 继承 DeepEvalBaseLLM + 满足 abstractmethod 签名.
    """
    from deepeval.models import DeepEvalBaseLLM

    assert issubclass(DeepSeekJudge, DeepEvalBaseLLM)


def test_deepseek_judge_init_signature_compatible():
    """abstractmethod 签名约束: load_model / get_model_name 接受 *args, **kwargs."""
    import inspect

    load_model_sig = inspect.signature(DeepSeekJudge.load_model)
    get_model_name_sig = inspect.signature(DeepSeekJudge.get_model_name)
    # 必须能接 *args, **kwargs (基类契约)
    assert "args" in load_model_sig.parameters or any(
        p.kind is inspect.Parameter.VAR_POSITIONAL for p in load_model_sig.parameters.values()
    )
    assert "args" in get_model_name_sig.parameters or any(
        p.kind is inspect.Parameter.VAR_POSITIONAL for p in get_model_name_sig.parameters.values()
    )


def test_deepseek_judge_default_construction_does_not_raise():
    """不带 llm 参数构造 DeepEvalEvaluator 时, 内部 _judge 应是 DeepSeekJudge 实例."""
    evaluator = DeepEvalEvaluator()
    assert isinstance(evaluator._judge, DeepSeekJudge)


@pytest.mark.asyncio
async def test_evaluator_5_metrics_all_pass():
    """5 metric 全跑通, 返 RAGAMetrics 5 字段都有分数"""
    mock_judge = MagicMock()
    evaluator = DeepEvalEvaluator(llm=mock_judge)

    with patch.object(evaluator, "_build_metric") as mock_build:
        mock_metric = MagicMock()
        mock_metric.score = 0.85
        mock_metric.a_measure = AsyncMock()
        mock_build.return_value = mock_metric

        result = await evaluator.evaluate_single(
            question="q?",
            answer="a",
            contexts=["c1"],
            ground_truth="gt",
        )

        assert result.faithfulness == 0.85
        assert result.answer_relevancy == 0.85
        assert result.context_precision == 0.85
        assert result.context_recall == 0.85
        assert result.hallucination == 0.85


@pytest.mark.asyncio
async def test_evaluator_single_metric_fail():
    """单 metric 失败, 该字段 None, 其他正常"""
    mock_judge = MagicMock()
    evaluator = DeepEvalEvaluator(llm=mock_judge)

    def mock_build_metric(name):
        m = MagicMock()
        m.score = 0.7

        async def measure_or_fail(_):
            if name == "faithfulness":
                raise RuntimeError("LLM error")

        m.a_measure = measure_or_fail
        return m

    with patch.object(evaluator, "_build_metric", side_effect=mock_build_metric):
        result = await evaluator.evaluate_single(question="q?", answer="a", contexts=["c1"], ground_truth="gt")
        assert result.faithfulness is None
        assert result.answer_relevancy == 0.7


@pytest.mark.asyncio
async def test_evaluator_context_recall_no_ground_truth():
    """没传 ground_truth, context_recall 返 None (不抛)"""
    mock_judge = MagicMock()
    evaluator = DeepEvalEvaluator(llm=mock_judge)

    with patch.object(evaluator, "_build_metric") as mock_build:
        mock_metric = MagicMock()
        mock_metric.score = 0.9
        mock_metric.a_measure = AsyncMock()
        mock_build.return_value = mock_metric

        result = await evaluator.evaluate_single(question="q?", answer="a", contexts=["c1"], ground_truth=None)
        assert result.context_recall is None
        assert result.faithfulness == 0.9


def test_build_test_case():
    """LLMTestCase 字段映射"""
    evaluator = DeepEvalEvaluator(llm=MagicMock())
    tc = evaluator._build_test_case("q?", "a", ["c1"], "gt")
    assert tc.input == "q?"
    assert tc.actual_output == "a"
    assert tc.retrieval_context == ["c1"]
    assert tc.expected_output == "gt"
    # HallucinationMetric 需要 context, 不是 retrieval_context
    assert tc.context == ["c1"]


def test_build_metric_unknown_raises():
    evaluator = DeepEvalEvaluator(llm=MagicMock())
    with pytest.raises(ValueError, match="未知指标"):
        evaluator._build_metric("nonexistent")


def test_deepeval_error_is_runtime_error():
    e = DeepEvalError("test")
    assert isinstance(e, RuntimeError)


@pytest.mark.asyncio
async def test_evaluator_all_metrics_fail_returns_all_none():
    """全部 metric 失败, 5 字段全 None"""
    mock_judge = MagicMock()
    evaluator = DeepEvalEvaluator(llm=mock_judge)

    def mock_build_metric(name):
        m = MagicMock()

        async def fail(_):
            raise RuntimeError("all fail")

        m.a_measure = fail
        return m

    with patch.object(evaluator, "_build_metric", side_effect=mock_build_metric):
        result = await evaluator.evaluate_single(question="q?", answer="a", contexts=["c1"], ground_truth="gt")
        assert result.faithfulness is None
        assert result.answer_relevancy is None
        assert result.context_precision is None
        assert result.context_recall is None
        assert result.hallucination is None
