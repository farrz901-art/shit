"""DeepEval 评估器 (5 个 RAG 指标)

5 metric:
- Faithfulness, AnswerRelevancy, ContextualPrecision, ContextualRecall, Hallucination
- LLM judge 走 DeepSeekJudge (OpenAI 兼容协议, 项目通用 base_url)

注: deepeval 4.x API 跟 spec §5.3 (基于 3.x) 类名 / 方法名一致,
LLMTestCase / a_measure / score 接口未变, HallucinationMetric 需要 `context` 字段
(其他 metric 用 `retrieval_context`).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from deepeval.models import DeepEvalBaseLLM
from loguru import logger

from ..common.evaluation import RAGAMetrics


class DeepEvalError(RuntimeError):
    """DeepEval 评估失败 (项目内部 error 类型)"""


class DeepSeekJudge(DeepEvalBaseLLM):
    """DeepEval 自定义 LLM (走 OpenAI 兼容协议, 跟项目主流 base_url 一致).

    实现 DeepEvalBaseLLM 抽象 (load_model / generate / a_generate / get_model_name).
    内部用 openai SDK 直调 (不走 langchain 链路, 因为 deepeval 不接受 LC LLM 实例).
    """

    def __init__(self, model: str | None = None, *args: Any, **kwargs: Any) -> None:
        # 不调 super().__init__: 父类会执行 self.model = self.load_model() 把 OpenAI client
        # 缓存到 self.model (deepeval 期望 self.model 是 LLM instance, 不是 client, 后续
        # 反射调用会拿错类型). 我们自己管理 self.model_name / self.base_url / self.api_key,
        # 每次 generate 现建 client.
        # 重依赖 lazy: defaults 模块加载读 env (side-effect), deepeval 顶层触发后只想 init
        from ..common import defaults  # noqa: E402

        self.model_name = model or os.getenv("LLM_MODEL") or defaults.DEFAULT_LLM_MODEL_OPENAI
        base_url = os.getenv("OPENAI_BASE_URL") or defaults.DEFAULT_OPENAI_BASE_URL
        if base_url and "deepseek" in base_url and not base_url.endswith("/beta"):
            base_url = base_url.rstrip("/") + "/beta"
        self.base_url = base_url
        self.api_key = os.getenv("OPENAI_API_KEY") or defaults.DEFAULT_OPENAI_API_KEY

    def load_model(self, *args: Any, **kwargs: Any) -> Any:
        # 重依赖 lazy: openai SDK 启动慢, deepeval 评测场景独立路径
        from openai import OpenAI  # noqa: E402

        return OpenAI(base_url=self.base_url, api_key=self.api_key)

    def generate(self, prompt: str) -> str:
        client = self.load_model()
        resp = client.chat.completions.create(
            model=self.model_name,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    async def a_generate(self, prompt: str) -> str:
        return await asyncio.to_thread(self.generate, prompt)

    def get_model_name(self, *args: Any, **kwargs: Any) -> str:
        return self.model_name


class DeepEvalEvaluator:
    """DeepEval 评估器, 5 个 RAG 指标.

    threshold=0.0 (不卡阈值, 只取分数). async_mode=True (内置并发).
    """

    DEFAULT_METRICS = (
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "hallucination",
    )

    def __init__(self, llm: Any = None, metrics: list[str] | None = None):
        # llm 参数兼容老 API (router 里传 OpenAILLM().llm), 但 deepeval 实际不接受
        # LC ChatOpenAI 实例, 内部统一用 DeepSeekJudge
        self._judge = llm if isinstance(llm, DeepEvalBaseLLM) else DeepSeekJudge()
        self._metric_names = metrics or list(self.DEFAULT_METRICS)

    def _build_test_case(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None,
    ):
        # 重依赖 lazy: deepeval.test_case 启动慢, 仅评测场景需要
        from deepeval.test_case import LLMTestCase  # noqa: E402

        # HallucinationMetric 需要 `context`, 其他 metric 用 `retrieval_context`
        # 这里两个字段都传 (deepeval 按 metric._required_params 自动取)
        # deepeval 4.x retrieval_context 类型签名是 list[str | RetrievedContextData], 但
        # 实际接受 list[str] (pyright 误判), 用 list(...) 复制避免类型 invariant 报错
        ctx_list: list[str] = list(contexts or [])
        return LLMTestCase(
            input=question,
            actual_output=answer,
            retrieval_context=ctx_list,  # pyright: ignore[reportArgumentType]
            context=ctx_list,
            expected_output=ground_truth,
        )

    def _build_metric(self, name: str) -> Any:
        # 重依赖 lazy: deepeval.metrics 启动慢 (~1s), 仅在 _build_metric 调用时需要
        from deepeval.metrics import (  # noqa: E402
            AnswerRelevancyMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            FaithfulnessMetric,
            HallucinationMetric,
        )

        kwargs = {
            "model": self._judge,
            "threshold": 0.0,
            "async_mode": True,
            "include_reason": False,
        }
        if name == "faithfulness":
            return FaithfulnessMetric(**kwargs)
        if name == "answer_relevancy":
            return AnswerRelevancyMetric(**kwargs)
        if name == "context_precision":
            return ContextualPrecisionMetric(**kwargs)
        if name == "context_recall":
            return ContextualRecallMetric(**kwargs)
        if name == "hallucination":
            return HallucinationMetric(**kwargs)
        raise ValueError(f"未知指标: {name}")

    async def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> RAGAMetrics:
        """5 metric 并发跑, 单 metric 失败该字段 None."""
        test_case = self._build_test_case(question, answer, contexts, ground_truth)

        async def _run(name: str) -> float | None:
            if name not in self._metric_names:
                return None
            if name == "context_recall" and not ground_truth:
                return None
            try:
                metric = self._build_metric(name)
                await metric.a_measure(test_case)
                return float(metric.score) if metric.score is not None else None
            except Exception as exc:
                logger.opt(exception=True).warning("evaluator[{}] 失败: {}", name, str(exc)[:200])
                return None

        results = await asyncio.gather(
            _run("faithfulness"),
            _run("answer_relevancy"),
            _run("context_precision"),
            _run("context_recall"),
            _run("hallucination"),
        )

        return RAGAMetrics(
            faithfulness=results[0],
            answer_relevancy=results[1],
            context_precision=results[2],
            context_recall=results[3],
            hallucination=results[4],
            raw_result=None,
        )
