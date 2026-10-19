# DeepEval 替换 LlamaIndex 评估 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `LlamaIndexEvaluator` (4 metric) with `DeepEvalEvaluator` (5 metric, add Hallucination), extend `RAGAMetrics` dataclass with `hallucination` field, swap error prefix `LlamaIndexEvalError` → `DeepEvalError`, and delete dead-code `/api/v1/evaluate` handler + Pydantic schemas + tests.

**Architecture:** New `src/eval/deepeval_eval.py` (~140 行) wraps DeepEval 5 RAG metrics with a custom `DeepSeekJudge` (OpenAI-compatible). Downstream `evaluate_single(question, answer, contexts, ground_truth) -> RAGAMetrics` contract stays, returns 5 fields now. Runner updates error prefix + `_METRIC_KEYS` tuple. Dead code deleted atomically (handler + Pydantic + tests in 1 commit).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, DeepEval 3.x, DeepSeek (OpenAI-compatible LLM judge, no new cloud key)

**Spec:** [docs/superpowers/specs/2026-06-16-deepeval-replace-llamaindex-design.md](../specs/2026-06-16-deepeval-replace-llamaindex-design.md) (commit `4d9e5d9`)

---

## File Structure

**New files:**
- `packages/service/src/eval/deepeval_eval.py` (~140 行) — `DeepEvalError` + `DeepSeekJudge` + `DeepEvalEvaluator`
- `packages/service/tests/eval/test_deepeval_eval.py` (~100 行) — 5 metric contract + error path + DeepEvalError 包装

**Modified files:**
- `packages/service/src/common/evaluation.py:11-49` — RAGAMetrics 加 `hallucination` 字段 + 5-key `to_dict` + 5-key `avg_score`
- `packages/service/src/eval/router.py:30,140` — import 改 `DeepEvalEvaluator`
- `packages/service/src/eval/runner.py:19,25,76` — import `DeepEvalError` + `_METRIC_KEYS` 加 `hallucination` + 错误前缀改 `DeepEvalError:`
- `packages/service/tests/common/test_evaluation.py` — 加 `hallucination` 字段相关测试
- `packages/service/tests/eval/test_runner.py:41-63,150-156` — `_mock_evaluator` 返 5-key + `avg_metrics` 断言改 5-key
- `packages/service/pyproject.toml` — `uv add deepeval` 自动加

**Deleted files / sections:**
- `packages/service/src/eval/llama_eval.py` (整文件 192 行)
- `packages/service/src/api/routes.py:7-15,42-65` (handler + import 块)
- `packages/service/src/api/schemas.py:24-36` (`EvaluateRequest` + `EvaluateResponse`)
- `packages/service/src/api/__init__.py:4-12,19-20` (re-export + `__all__`)
- `packages/service/tests/api/test_routes.py:3,20-22` (import + `test_evaluate_request_schema`)
- `packages/service/tests/api/test_schemas.py:66-91` (3 个 evaluate 测试)

---

## Task 1: Install deepeval

**Files:**
- Modify: `packages/service/pyproject.toml`
- Modify: `packages/service/uv.lock`

- [ ] **Step 1: Add deepeval dependency**

Run from `packages/service`:
```bash
cd packages/service
uv add deepeval
```

- [ ] **Step 2: Verify deepeval is installed**

```bash
cd packages/service
uv run python -c "import deepeval; from deepeval.metrics import FaithfulnessMetric, HallucinationMetric; print('ok', deepeval.__version__)"
```

Expected output: `ok 3.x.x` (具体版本号, 3.0+)

- [ ] **Step 3: Verify DeepEvalBaseLLM import path**

```bash
cd packages/service
uv run python -c "from deepeval.models.base_model import DeepEvalBaseLLM; print(DeepEvalBaseLLM)"
```

Expected output: `<class 'deepeval.models.base_model.DeepEvalBaseLLM'>` (确认 import 路径正确)

如果 import 路径不同 (DeepEval 版本差异), 调整 Task 3 第 4 步的 import 路径, 记录实际路径.

- [ ] **Step 4: Commit**

```bash
cd /c/doc/Code/rag
git add packages/service/pyproject.toml packages/service/uv.lock
git commit -m "chore(deps): add deepeval>=3.x for RAG 评估"
```

---

## Task 2: Extend RAGAMetrics with hallucination field (TDD)

**Files:**
- Modify: `packages/service/src/common/evaluation.py:11-49`
- Modify: `packages/service/tests/common/test_evaluation.py`

- [ ] **Step 1: Read current RAGAMetrics and tests**

Read `packages/service/src/common/evaluation.py:11-49` (RAGAMetrics dataclass) and `packages/service/tests/common/test_evaluation.py` (现有 5 个测试, 4 个跟 RAGAMetrics 有关).

- [ ] **Step 2: Write failing test for hallucination field**

Add to `packages/service/tests/common/test_evaluation.py` (文件末尾):

```python
def test_ragametrics_hallucination_in_to_dict():
    """5th 字段 hallucination 进 to_dict (2026-06-16 加)"""
    from src.common.evaluation import RAGAMetrics
    m = RAGAMetrics(
        faithfulness=0.9, answer_relevancy=0.8,
        context_precision=0.7, context_recall=0.6,
        hallucination=0.5,
    )
    d = m.to_dict()
    assert d == {
        "faithfulness": 0.9,
        "answer_relevancy": 0.8,
        "context_precision": 0.7,
        "context_recall": 0.6,
        "hallucination": 0.5,
        "context_entity_precision": None,
    }


def test_ragametrics_avg_score_includes_hallucination():
    """5-key avg (含 hallucination), 老 4-key 退化"""
    from src.common.evaluation import RAGAMetrics
    # 5 字段全填 → 5 平均
    m = RAGAMetrics(
        faithfulness=1.0, answer_relevancy=0.8,
        context_precision=0.6, context_recall=0.4,
        hallucination=0.2,
    )
    assert m.avg_score == (1.0 + 0.8 + 0.6 + 0.4 + 0.2) / 5
    # 4 字段 + hallucination=None → 4 平均 (老样本兼容)
    m2 = RAGAMetrics(faithfulness=0.8, answer_relevancy=0.6, context_precision=0.4, context_recall=0.2)
    assert m2.avg_score == (0.8 + 0.6 + 0.4 + 0.2) / 4
```

- [ ] **Step 3: Run new tests to verify they fail**

```bash
cd packages/service
uv run pytest tests/common/test_evaluation.py::test_ragametrics_hallucination_in_to_dict tests/common/test_evaluation.py::test_ragametrics_avg_score_includes_hallucination -v
```

Expected: 2 tests FAIL with `TypeError: __init__() got an unexpected keyword argument 'hallucination'`

- [ ] **Step 4: Add hallucination field to RAGAMetrics**

Modify `packages/service/src/common/evaluation.py:11-49`, replace RAGAMetrics class:

```python
@dataclass
class RAGAMetrics:
    """RAG 评估指标 dataclass — 5 指标 (2026-06-16 加 Hallucination)"""
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    hallucination: float | None = None         # (2026-06-16) DeepEval HallucinationMetric
    context_entity_precision: float | None = None  # 保留兼容, 不进 avg_score
    raw_result: dict | None = None

    def to_dict(self) -> dict:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "hallucination": self.hallucination,                       # (2026-06-16) 新
            "context_entity_precision": self.context_entity_precision,  # 保留
        }

    @property
    def avg_score(self) -> float | None:
        # 5-key 平均 (None 过滤, 动态维度) — 老样本 (无 hallucination) 退化为 4-key 平均
        values = [
            v for v in [
                self.faithfulness,
                self.answer_relevancy,
                self.context_precision,
                self.context_recall,
                self.hallucination,
            ] if v is not None
        ]
        return sum(values) / len(values) if values else None
```

- [ ] **Step 5: Run new tests to verify they pass**

```bash
cd packages/service
uv run pytest tests/common/test_evaluation.py::test_ragametrics_hallucination_in_to_dict tests/common/test_evaluation.py::test_ragametrics_avg_score_includes_hallucination -v
```

Expected: 2 tests PASS

- [ ] **Step 6: Verify existing tests still pass**

```bash
cd packages/service
uv run pytest tests/common/test_evaluation.py -v
```

Expected: 7 tests PASS (5 existing + 2 new). 注意: 现有 `test_ragametrics_avg_score` (line 4) 期望 `(1.0 + 0.8 + 0.6 + 0.4) / 4`, 因为它**不传** hallucination, 默认 None, None 过滤后是 4-key 平均, 仍然等于 `(1.0+0.8+0.6+0.4)/4` = 0.7. 通过.

- [ ] **Step 7: Commit**

```bash
cd /c/doc/Code/rag
git add packages/service/src/common/evaluation.py packages/service/tests/common/test_evaluation.py
git commit -m "feat(eval): RAGAMetrics 加 hallucination 字段 (5 metric 兼容老 4-key)"
```

---

## Task 3: Create deepeval_eval.py with DeepEvalError + DeepSeekJudge + DeepEvalEvaluator (TDD)

**Files:**
- Create: `packages/service/src/eval/deepeval_eval.py`
- Create: `packages/service/tests/eval/test_deepeval_eval.py`

- [ ] **Step 1: Write failing test file**

Create `packages/service/tests/eval/test_deepeval_eval.py`:

```python
"""DeepEval 评估器单元测试 (2026-06-16 替代 LlamaIndex 4 指标)

5 metric 契约 + error 路径 + DeepEvalError 包装.
mock DeepEval metric, 不连真实 LLM.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.common.evaluation import RAGAMetrics
from src.eval.deepeval_eval import DeepEvalError, DeepEvalEvaluator, DeepSeekJudge


def _make_mock_metric(score: float | None = None, raises: Exception | None = None) -> MagicMock:
    """mock deepeval Metric: a_measure 设 score 或抛"""
    m = MagicMock()
    if raises:
        m.a_measure = AsyncMock(side_effect=raises)
    else:
        m.a_measure = AsyncMock()
        m.score = score
    return m


@pytest.fixture
def mock_judge() -> MagicMock:
    """mock DeepEvalBaseLLM judge (spec=True 只暴露 DeepSeekJudge 的 public 方法)"""
    j = MagicMock(spec=DeepSeekJudge)
    return j


def test_default_metrics_includes_hallucination():
    """默认 5 metric 含 hallucination (2026-06-16 新增)"""
    ev = DeepEvalEvaluator(llm=MagicMock())
    assert "hallucination" in ev.DEFAULT_METRICS
    assert len(ev.DEFAULT_METRICS) == 5


def test_unknown_metric_raises_value_error(mock_judge):
    """_build_metric 未知名抛 ValueError"""
    ev = DeepEvalEvaluator(llm=mock_judge)
    with pytest.raises(ValueError, match="未知指标"):
        ev._build_metric("bogus_metric")


def test_constructor_uses_deepseek_judge_when_llm_not_basellm():
    """未传 DeepEvalBaseLLM 时, 默认用 DeepSeekJudge"""
    ev = DeepEvalEvaluator(llm=MagicMock())  # MagicMock 不是 DeepEvalBaseLLM 实例
    assert isinstance(ev._judge, DeepSeekJudge)


def test_constructor_keeps_basellm_when_provided(mock_judge):
    """传 DeepEvalBaseLLM 实例时, 直接用 (兼容接口)"""
    ev = DeepEvalEvaluator(llm=mock_judge)
    assert ev._judge is mock_judge


async def test_evaluate_single_returns_5_metric_ragametrics(mock_judge):
    """evaluate_single 返 RAGAMetrics 5 字段全填"""
    ev = DeepEvalEvaluator(llm=mock_judge)
    with patch.object(ev, "_build_metric", return_value=_make_mock_metric(score=0.8)):
        result = await ev.evaluate_single(
            question="Q?", answer="A", contexts=["C1", "C2"], ground_truth="GT",
        )
    assert isinstance(result, RAGAMetrics)
    assert result.faithfulness == 0.8
    assert result.answer_relevancy == 0.8
    assert result.context_precision == 0.8
    assert result.context_recall == 0.8
    assert result.hallucination == 0.8


async def test_evaluate_single_skips_context_recall_without_ground_truth(mock_judge):
    """缺 ground_truth 时 context_recall 返 None (不调 LLM)"""
    ev = DeepEvalEvaluator(llm=mock_judge)
    metric_calls: list[str] = []

    def track(name: str) -> MagicMock:
        metric_calls.append(name)
        return _make_mock_metric(score=0.7)

    with patch.object(ev, "_build_metric", side_effect=track):
        result = await ev.evaluate_single(
            question="Q?", answer="A", contexts=["C1"], ground_truth=None,
        )
    assert "context_recall" not in metric_calls
    assert result.context_recall is None
    # hallucination 不依赖 ground_truth, 应该跑
    assert "hallucination" in metric_calls
    assert result.hallucination == 0.7


async def test_evaluate_single_returns_none_on_metric_failure(mock_judge):
    """metric 抛异常时该指标返 None (不阻断其他)"""
    ev = DeepEvalEvaluator(llm=mock_judge)

    def fail_on_hallucination(name: str) -> MagicMock:
        if name == "hallucination":
            return _make_mock_metric(raises=RuntimeError("LLM down"))
        return _make_mock_metric(score=0.5)

    with patch.object(ev, "_build_metric", side_effect=fail_on_hallucination):
        result = await ev.evaluate_single(
            question="Q?", answer="A", contexts=["C1"], ground_truth="GT",
        )
    assert result.faithfulness == 0.5
    assert result.hallucination is None


def test_deepeval_error_inherits_runtime_error():
    """DeepEvalError 继承 RuntimeError (跟原 LlamaIndexEvalError 兼容)"""
    assert issubclass(DeepEvalError, RuntimeError)
    err = DeepEvalError("test")
    assert isinstance(err, RuntimeError)
    assert str(err) == "test"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/service
uv run pytest tests/eval/test_deepeval_eval.py -v
```

Expected: 9 tests FAIL with `ModuleNotFoundError: No module named 'src.eval.deepeval_eval'`

- [ ] **Step 3: Create deepeval_eval.py**

Create `packages/service/src/eval/deepeval_eval.py`:

```python
"""DeepEval 评估器 (2026-06-16 替代 LlamaIndex 4 指标 → DeepEval 5 指标)

5 个 RAG 指标:
- faithfulness, answer_relevancy, context_precision, context_recall: DeepEval 内置
- hallucination: 新增 (跟 faithfulness 互补: faithfulness = claim 被 context 支持, hallucination = answer 包含 context 外的虚假信息)

Judge LLM: DeepSeekJudge 走 OpenAI 兼容 API (复刻原 _get_judge_llm 行为)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
    HallucinationMetric,
)
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from openai import OpenAI

from ..common.evaluation import RAGAMetrics


class DeepEvalError(RuntimeError):
    """DeepEval 评估失败 (替代原 LlamaIndexEvalError, 仍继承 RuntimeError 保持兼容)"""


class DeepSeekJudge(DeepEvalBaseLLM):
    """DeepSeek via OpenAI-compatible API, 走 DeepEvalBaseLLM 抽象.

    复刻原 LlamaIndexEvaluator._get_judge_llm() 行为:
    - base_url 默认 https://api.deepseek.com, DeepSeek 时自动追加 /beta
    - 温度 0.0, 无 function calling
    """

    def __init__(self) -> None:
        self.model_name = os.getenv("LLM_MODEL", "deepseek-chat")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        if "deepseek" in base_url and not base_url.endswith("/beta"):
            base_url = base_url.rstrip("/") + "/beta"
        self.base_url = base_url
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    def load_model(self) -> OpenAI:
        return OpenAI(base_url=self.base_url, api_key=self.api_key)

    def generate(self, prompt: str) -> str:
        client = self.load_model()
        resp = client.chat.completions.create(
            model=self.model_name,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

    async def a_generate(self, prompt: str) -> str:
        # deepeval 的 async_mode=True 走 a_generate()
        return await asyncio.to_thread(self.generate, prompt)


class DeepEvalEvaluator:
    """DeepEval 评估器 — 5 个 RAG 指标, 替代 LlamaIndexEvaluator."""

    DEFAULT_METRICS: tuple[str, ...] = (
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "hallucination",
    )

    def __init__(self, llm: Any = None, metrics: list[str] | None = None) -> None:
        # llm 参数保留为兼容接口 (router 里传 OpenAILLM().llm), 内部统一用 DeepSeekJudge
        # 因为 deepeval metric 需要 DeepEvalBaseLLM 实例, 不是 llama_index 的 LLM 包装
        self._judge = llm if isinstance(llm, DeepEvalBaseLLM) else DeepSeekJudge()
        self._metric_names = list(metrics) if metrics else list(self.DEFAULT_METRICS)

    def _build_test_case(
        self, question: str, answer: str, contexts: list[str], ground_truth: str | None,
    ) -> LLMTestCase:
        return LLMTestCase(
            input=question,
            actual_output=answer,
            retrieval_context=contexts or [],
            expected_output=ground_truth,  # ContextualRecallMetric 需要
        )

    def _build_metric(self, name: str) -> Any:
        # 每个 metric 单独实例, threshold=0.0 (我们不卡阈值, 只取分数)
        kwargs: dict[str, Any] = {
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
        test_case = self._build_test_case(question, answer, contexts, ground_truth)

        async def _run(name: str) -> float | None:
            if name not in self._metric_names:
                return None
            # context_recall 需要 expected_output, 缺则跳过 (跟原实现一致)
            if name == "context_recall" and not ground_truth:
                return None
            try:
                metric = self._build_metric(name)
                await metric.a_measure(test_case)
                return float(metric.score) if metric.score is not None else None
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"evaluator[{name}] 失败: {e}")
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd packages/service
uv run pytest tests/eval/test_deepeval_eval.py -v
```

Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /c/doc/Code/rag
git add packages/service/src/eval/deepeval_eval.py packages/service/tests/eval/test_deepeval_eval.py
git commit -m "feat(eval): DeepEval 评估器 (5 metric + DeepSeekJudge + DeepEvalError)"
```

---

## Task 4: Wire DeepEvalEvaluator into router + runner (replace import + error prefix + _METRIC_KEYS)

**Files:**
- Modify: `packages/service/src/eval/router.py:30,140`
- Modify: `packages/service/src/eval/runner.py:19,25,76`
- Modify: `packages/service/tests/eval/test_runner.py:41-63,150-156`

- [ ] **Step 1: Read current router.py imports and runner.py imports**

```bash
cd /c/doc/Code/rag
head -35 packages/service/src/eval/router.py
sed -n '19,30p' packages/service/src/eval/runner.py
sed -n '70,80p' packages/service/src/eval/runner.py
```

确认要改的位置: router.py:30 import, router.py:140 instantiation, runner.py:19 (DifyAPIError import 旁), runner.py:25 (`_METRIC_KEYS`), runner.py:76 (错误前缀).

- [ ] **Step 2: Update router.py to use DeepEvalEvaluator**

Edit `packages/service/src/eval/router.py:30`:
- Find: `from .llama_eval import LlamaIndexEvaluator`
- Replace: `from .deepeval_eval import DeepEvalEvaluator`

Edit `packages/service/src/eval/router.py:140`:
- Find: `evaluator = LlamaIndexEvaluator(llm=judge_llm)`
- Replace: `evaluator = DeepEvalEvaluator(llm=judge_llm)`

- [ ] **Step 3: Update runner.py to use DeepEvalError + 5-key _METRIC_KEYS**

Edit `packages/service/src/eval/runner.py:19` (在 `from ..integrations.dify_client import DifyAPIError` 后**新增一行**):
- Find:
  ```python
  from ..integrations.dify_client import DifyAPIError
  from ..storage.session import session_scope
  ```
- Replace:
  ```python
  from ..integrations.dify_client import DifyAPIError
  from .deepeval_eval import DeepEvalError
  from ..storage.session import session_scope
  ```

Edit `packages/service/src/eval/runner.py:24-25` (更新 metric 注释 + tuple):
- Find:
  ```python
  # 评估结果落库的 4 个指标 key (跟 RAGAMetrics.to_dict 对齐)
  _METRIC_KEYS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
  ```
- Replace:
  ```python
  # 评估结果落库的 5 个指标 key (跟 RAGAMetrics.to_dict 对齐, 2026-06-16 加 hallucination)
  _METRIC_KEYS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall", "hallucination")
  ```

Edit `packages/service/src/eval/runner.py:76` (错误前缀):
- Find: `"error": f"LlamaIndexEvalError: {e}",`
- Replace: `"error": f"DeepEvalError: {e}",`

- [ ] **Step 4: Update test_runner.py _mock_evaluator to return 5-key + assertion to 5-key**

Edit `packages/service/tests/eval/test_runner.py:52-58` (mock to_dict 返 5-key):
- Find:
  ```python
          m.to_dict = MagicMock(
              return_value={
                  "faithfulness": 0.8,
                  "answer_relevancy": 0.8,
                  "context_precision": 0.8,
                  "context_recall": 0.8,
              }
          )
  ```
- Replace:
  ```python
          m.to_dict = MagicMock(
              return_value={
                  "faithfulness": 0.8,
                  "answer_relevancy": 0.8,
                  "context_precision": 0.8,
                  "context_recall": 0.8,
                  "hallucination": 0.8,  # (2026-06-16) 5th metric
              }
          )
  ```

Edit `packages/service/tests/eval/test_runner.py` (avg_metrics 断言) — 先 grep 找位置:
```bash
cd /c/doc/Code/rag
grep -n "avg_metrics ==" packages/service/tests/eval/test_runner.py
```

找到的 line (应该在 150 附近), 编辑:
- Find: `e.avg_metrics == {\n        "faithfulness": 0.8, "answer_relevancy": 0.8, "context_precision": 0.8, "context_recall": 0.8, \n    }`
- Replace: `e.avg_metrics == {\n        "faithfulness": 0.8, "answer_relevancy": 0.8, "context_precision": 0.8, "context_recall": 0.8, "hallucination": 0.8, \n    }`

如果 grep 找到 1 个以上的 avg_metrics 断言, **全部** 加 `"hallucination": 0.8,` 行.

- [ ] **Step 5: Run eval tests to verify all pass**

```bash
cd packages/service
uv run pytest tests/eval/ -v
```

Expected: 47 tests PASS (5 runner + 12 router + 4 registry + 4 model + 9 csv_parser + 4 template + 9 deepeval_eval). 

如果 fail: 检查 (a) `tests/eval/test_runner.py:227` 的 `"ragas broke" in (bad.error or "")` 仍通过 (因为它检查 error 消息的子串, 不是前缀, 前缀改 `DeepEvalError:` 不影响此断言). (b) `_mock_evaluator` 已返 5-key.

- [ ] **Step 6: Commit**

```bash
cd /c/doc/Code/rag
git add packages/service/src/eval/router.py packages/service/src/eval/runner.py packages/service/tests/eval/test_runner.py
git commit -m "feat(eval): 切换到 DeepEvalEvaluator + 5-key _METRIC_KEYS + DeepEvalError 前缀"
```

---

## Task 5: Verify contract test (no /api/v1/evaluate reference) — prerequisite for dead code deletion

**Files:** (read-only verification, no code change)

- [ ] **Step 1: Grep FRONTEND_EXPECTS for /api/v1/evaluate references**

```bash
cd /c/doc/Code/rag
grep -E "/api/v1/evaluate|EvaluateRequest|EvaluateResponse" packages/service/tests/test_api_contract.py
```

Expected: 0 hit (空输出). 

如果有 hit, **不能继续**, 报告用户. (per project CLAUDE.md "删 BFF route 前必须跑契约测试".)

- [ ] **Step 2: Run contract test**

```bash
cd packages/service
uv run pytest tests/test_api_contract.py -v
```

Expected: 1 test PASS (或所有 contract tests 绿). 这是删 dead code 的前提.

- [ ] **Step 3: No commit needed**

这是 verification 步, 不改代码.

---

## Task 6: Delete dead code (handler + Pydantic + tests)

**Files:**
- Modify: `packages/service/src/api/routes.py` (删 lines 7-15, 42-65)
- Modify: `packages/service/src/api/schemas.py` (删 lines 24-36)
- Modify: `packages/service/src/api/__init__.py` (删 lines 4-12, 19-20)
- Modify: `packages/service/tests/api/test_routes.py` (删 lines 3, 20-22)
- Modify: `packages/service/tests/api/test_schemas.py` (删 lines 66-91)

- [ ] **Step 1: Delete handler + lazy import + schemas import from routes.py**

Edit `packages/service/src/api/routes.py`:

**Edit A** (line 7-15, 从 schemas import 块删 EvaluateRequest/EvaluateResponse):
- Find:
  ```python
  from .schemas import (
      EvaluateRequest,
      EvaluateResponse,
      IngestRequest,
      IngestResponse,
      QueryRequest,
      QueryResponse,
      SourceNode,
  )
  ```
- Replace:
  ```python
  from .schemas import (
      IngestRequest,
      IngestResponse,
      QueryRequest,
      QueryResponse,
      SourceNode,
  )
  ```

**Edit B** (lines 42-65, 整个 evaluate_endpoint + lazy import):
- Find:
  ```python
  @router.post("/evaluate", response_model=EvaluateResponse)
  async def evaluate_endpoint(req: EvaluateRequest):
      """LlamaIndex 评估 (替代原 RAGAS, 解决 Windows 安装问题)"""
      try:
          from ..eval.llama_eval import LlamaIndexEvaluator
          from ..generation.llm import OpenAILLM

          llm = OpenAILLM().llm
          evaluator = LlamaIndexEvaluator(llm=llm)
          metrics = await evaluator.evaluate_single(
              question=req.question,
              answer=req.answer,
              contexts=req.contexts,
              ground_truth=req.ground_truth,
          )
          return EvaluateResponse(
              faithfulness=metrics.faithfulness,
              answer_relevancy=metrics.answer_relevancy,
              context_precision=metrics.context_precision,
              context_recall=metrics.context_recall,
              avg_score=metrics.avg_score,
          )
      except Exception as e:
          raise HTTPException(status_code=500, detail=str(e)) from e
  ```
- Replace: `` (空, 整段删)

- [ ] **Step 2: Delete EvaluateRequest + EvaluateResponse from schemas.py**

Edit `packages/service/src/api/schemas.py:24-36`:
- Find:
  ```python
  class EvaluateRequest(BaseModel):
      question: str
      answer: str
      contexts: list[str]
      ground_truth: str | None = None


  class EvaluateResponse(BaseModel):
      faithfulness: float | None = None
      answer_relevancy: float | None = None
      context_precision: float | None = None
      context_recall: float | None = None
      avg_score: float | None = None
  ```
- Replace: `` (空, 整段删, 保留前后 1 空行)

- [ ] **Step 3: Delete re-exports + __all__ entries from __init__.py**

Edit `packages/service/src/api/__init__.py:4-12`:
- Find:
  ```python
  from .routes import router
  from .schemas import (
      EvaluateRequest,
      EvaluateResponse,
      IngestRequest,
      IngestResponse,
      QueryRequest,
      QueryResponse,
      SourceNode,
  )
  ```
- Replace:
  ```python
  from .routes import router
  from .schemas import (
      IngestRequest,
      IngestResponse,
      QueryRequest,
      QueryResponse,
      SourceNode,
  )
  ```

Edit `packages/service/src/api/__init__.py:19-20`:
- Find:
  ```python
      "EvaluateRequest",
      "EvaluateResponse",
  ```
- Replace: `` (空, 整段删)

- [ ] **Step 4: Delete test_evaluate_request_schema from test_routes.py**

Edit `packages/service/tests/api/test_routes.py`:
**Edit A** (line 3, import 删 EvaluateRequest):
- Find: `from src.api.schemas import EvaluateRequest, IngestRequest, QueryRequest`
- Replace: `from src.api.schemas import IngestRequest, QueryRequest`

**Edit B** (lines 20-22, 整个 test_evaluate_request_schema):
- Find:
  ```python
  def test_evaluate_request_schema():
      req = EvaluateRequest(question="Q", answer="A", contexts=["C1", "C2"])
      assert len(req.contexts) == 2
  ```
- Replace: `` (空, 整段删, 保留前后 1 空行)

- [ ] **Step 5: Delete 3 evaluate tests from test_schemas.py**

Edit `packages/service/tests/api/test_schemas.py:66-91`:
- Find:
  ```python
  def test_evaluate_request_all_fields(schemas):
      """EvaluateRequest 全部字段"""
      req = schemas.EvaluateRequest(question="q?", answer="a", contexts=["c1", "c2"], ground_truth="gt")
      assert req.question == "q?"
      assert req.answer == "a"
      assert req.contexts == ["c1", "c2"]
      assert req.ground_truth == "gt"


  def test_evaluate_response_all_none(schemas):
      """EvaluateResponse 可以全部为 None"""
      resp = schemas.EvaluateResponse()
      assert resp.faithfulness is None
      assert resp.answer_relevancy is None
      assert resp.context_precision is None
      assert resp.context_recall is None
      assert resp.avg_score is None


  def test_evaluate_response_with_scores(schemas):
      """EvaluateResponse 带评分"""
      resp = schemas.EvaluateResponse(
          faithfulness=0.9, answer_relevancy=0.8, context_precision=0.85, context_recall=0.75, avg_score=0.825
      )
      assert resp.faithfulness == 0.9
      assert resp.avg_score == 0.825


  ```
- Replace: `` (空, 整段删)

- [ ] **Step 6: Run tests/api/ to verify only non-evaluate tests remain**

```bash
cd packages/service
uv run pytest tests/api/ -v
```

Expected: 11 tests PASS (3 test_routes + 8 test_schemas — 全部非 evaluate). 

如果 fail: 检查 (a) `from src.api.schemas import` 没有 `EvaluateRequest`, (b) `test_schemas.py` 的 3 个 evaluate 测试都删了.

- [ ] **Step 7: Verify contract test still passes**

```bash
cd packages/service
uv run pytest tests/test_api_contract.py -v
```

Expected: PASS (route 不存在, 不影响契约).

- [ ] **Step 8: Commit**

```bash
cd /c/doc/Code/rag
git add packages/service/src/api/routes.py packages/service/src/api/schemas.py packages/service/src/api/__init__.py packages/service/tests/api/test_routes.py packages/service/tests/api/test_schemas.py
git commit -m "refactor(api): 删 /api/v1/evaluate dead code (handler + Pydantic + 4 tests)"
```

---

## Task 7: Delete llama_eval.py + final verification

**Files:**
- Delete: `packages/service/src/eval/llama_eval.py`

- [ ] **Step 1: Verify no references to llama_eval remain**

```bash
cd /c/doc/Code/rag
grep -rn "llama_eval\|LlamaIndexEvalError" packages/service/src/ packages/service/tests/ 2>&1 | grep -v "Binary file"
```

Expected: 0 hit. 

如果有 hit, **不能继续**, 找出来手动修.

- [ ] **Step 2: Delete llama_eval.py**

```bash
cd /c/doc/Code/rag
git rm packages/service/src/eval/llama_eval.py
```

- [ ] **Step 3: Run full eval + api + contract test suite**

```bash
cd packages/service
uv run pytest tests/eval/ tests/api/ tests/test_api_contract.py tests/common/ -v
```

Expected: 85+ tests PASS (47 eval + 11 api + 1+ contract + 7 common).

- [ ] **Step 4: Run ruff + mypy**

```bash
cd packages/service
uv run ruff check src tests
uv run mypy src
```

Expected: 0 新 warning/error. (Pre-existing warnings 忽略.)

- [ ] **Step 5: Verify no .pyc / __pycache__ orphans**

```bash
cd packages/service
find src/eval -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find src/api -name "__pycache__" -exec rm -rf {} + 2>/dev/null
```

- [ ] **Step 6: Commit**

```bash
cd /c/doc/Code/rag
git commit -m "refactor(eval): 删 llama_eval.py (净删 192 行, 5 metric 迁移完成)"
```

---

## Task 8: End-to-end manual verification (optional, requires dev DB + Dify)

**Files:** (no code change, manual verification only)

- [ ] **Step 1: Start service**

```bash
cd packages/service
# 确保 .env.local 的 PG_PASSWORD 是真密码 (见 500 错误排查)
uv run uvicorn src.product_decoders.app:create_app --factory --reload --port 8000
```

确认 listen `http://0.0.0.0:8000` 无 error.

- [ ] **Step 2: Create 5-sample test CSV**

```bash
cat > /tmp/test_eval.csv << 'EOF'
question,ground_truth
什么是 1LE0001 电机?,1LE0001 是西门子低压电机系列
1FK7 是什么?,1FK7 是西门子伺服电机系列
3RT2026 接触器用途?,3RT2026 是西门子接触器
6SE70 变频器特点?,6SE70 是西门子老款变频器
G120 跟 S120 区别?,G120 是通用型 S120 是高端型
EOF
```

- [ ] **Step 3: Upload CSV via curl + check response**

```bash
# 先 login 拿 admin token (用之前 seed 的 admin 账号)
ADMIN_TOKEN=$(grep RAG_ADMIN_TOKEN packages/service/.env.local | cut -d= -f2)

curl -X POST http://localhost:8000/api/evaluate/runs \
  -H "x-admin-token: $ADMIN_TOKEN" \
  -F "file=@/tmp/test_eval.csv"
```

Expected: `{"id": <eval_id>, "status": "pending"}`

- [ ] **Step 4: Wait for completion + check results**

```bash
# 轮询直到 status=completed (或 cancelled/failed)
for i in {1..30}; do
  STATUS=$(curl -s -H "x-admin-token: $ADMIN_TOKEN" \
    "http://localhost:8000/api/evaluate/runs/<eval_id>" | python -c "import sys, json; print(json.load(sys.stdin)['status'])")
  echo "attempt $i: $STATUS"
  [ "$STATUS" = "completed" ] && break
  sleep 5
done
```

- [ ] **Step 5: Verify 5 metric scores in avg_metrics**

```bash
curl -s -H "x-admin-token: $ADMIN_TOKEN" \
  "http://localhost:8000/api/evaluate/runs/<eval_id>" | \
  python -m json.tool | grep -A 10 avg_metrics
```

Expected:
```json
"avg_metrics": {
    "faithfulness": 0.X,
    "answer_relevancy": 0.X,
    "context_precision": 0.X,
    "context_recall": 0.X,
    "hallucination": 0.X
}
```

5 个分数都在 0-1 之间. 如果 hallucination 是 None, 检查 ground_truth 是否传 (答: 不影响 hallucination, 应该跑).

- [ ] **Step 6: Sample-level: verify per-sample metrics 也含 hallucination**

```bash
curl -s -H "x-admin-token: $ADMIN_TOKEN" \
  "http://localhost:8000/api/evaluate/runs/<eval_id>" | \
  python -c "import sys, json; d=json.load(sys.stdin); s=d['samples'][0]; print(json.dumps(s['metrics'], indent=2, ensure_ascii=False))"
```

Expected: 5-key dict (含 hallucination).

- [ ] **Step 7: (Optional) Compare with old LlamaIndex scores**

如要对比, checkout 旧 commit (`1eb52ab` 或之前), 跑同样 5 sample, 记录分数. 偏差 < 0.15 算可接受, 写进 P0 follow-up 文档.

---

## Acceptance Checklist

- [ ] Task 1-7 全部完成, 0 跳步
- [ ] `uv run pytest tests/eval/ tests/api/ tests/test_api_contract.py tests/common/ -v` 全绿
- [ ] `uv run ruff check src tests` 0 新 warning
- [ ] `uv run mypy src` 0 新 error
- [ ] `grep -rn "llama_eval\|LlamaIndexEvalError" packages/service/src/ packages/service/tests/` 0 hit
- [ ] Task 8 (E2E) 5 分数全有值
- [ ] 工作树干净 (`git status` 只剩 bun.lock 修改)

---

## Self-Review Notes

**Spec coverage (4 大目标):**
- 目标 1: 5 metric 替换 → Task 1, 2, 3 (install + RAGAMetrics + deepeval_eval.py)
- 目标 2: RAGAMetrics 扩展 → Task 2 (hallucination 字段)
- 目标 3: 存储不变 → 不需 alembic, JSON 列自动适配
- 目标 4: 测试不破 → Task 4 step 5 (existing 38 测 + 9 新测 = 47)
- 目标 5: LLM judge 一致 → Task 3 (DeepSeekJudge 复用 env)
- 目标 6: 删 dead code → Task 5, 6, 7

**Placeholder scan:** 无 TBD/TODO, 全部代码完整.

**Type consistency check:**
- `DeepEvalError(RuntimeError)` (Task 3) → `runner.py:19` import 用同一名
- `_METRIC_KEYS` (Task 4) 5 keys 跟 `RAGAMetrics.to_dict()` (Task 2) keys 顺序一致
- `DeepEvalEvaluator.DEFAULT_METRICS` (Task 3) 5 keys 跟 `_METRIC_KEYS` (Task 4) 一致
- `to_dict()` 5 keys 跟 `evaluate_single` 5 个 `_run` 调用 (Task 3) 一致
- mock `to_dict` 5 keys 跟 `to_dict()` 5 keys 一致 (Task 2 vs Task 4)

**Spec gap:** Spec §9 验收说 "tests/api/ 删后剩 8-10 个" → Task 6 step 6 验算为 11 个 (3 routes + 8 schemas), 已修正. ✓
