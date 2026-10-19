# DeepEval 替代 LlamaIndex 评估 (2026-06-16)

> Status: **DRAFT v2 — 等审批**
> 目标: 把 `packages/service/src/eval/llama_eval.py` (LlamaIndex 4 指标) 换成 DeepEval 5 指标,
> 解决 Windows 安装 / API 难用 / 维护差问题, 顺手删 dead-code `/api/v1/evaluate` 路由.
>
> 外部契约 (4 metric key 名字 + 分数范围 + RAGAMetrics 字段顺序) **保持稳定**, 仅新增第 5 个 key.

## 1. 背景与动机

`src/eval/llama_eval.py` 当前用 LlamaIndex 4 个 evaluator 做 RAG 评估. 文件头注释明确说"替代 RAGAS, 解决 Windows 安装问题" — **LlamaIndex 本身就是个过渡方案**.

LlamaIndex 评估器的实际问题 (从 inventory 报告 + 经验总结):

| 问题 | 表现 |
|------|------|
| Windows 安装脆弱 | `llama-index-core` + `llama-index-llms-openai-like` 装包链路长, Python 3.14 上偶发 wheel 缺 |
| API 难用 | `aevaluate(query=, response=, contexts=)` 跟 DeepEval/RAGAS 主流 API 不一致 |
| 4 指标得各 import 各 | 懒加载 + 自实现 `_ContextRecallJudge` (claim-level 拆解) 160 行, 维护成本高 |
| 文档稀疏 | 4 个 evaluator 行为差异无单一权威文档, 出错排查耗时 |
| 不能并发 | `asyncio.gather` + `run_in_executor` 是 hack 出来的并发 (一个 ThreadPoolExecutor/max_workers=1) |

**DeepEval** 一次解决:
- 单包 `pip install deepeval` (Pypi 主流, 社区活跃)
- 5 个 RAG 指标是**同类 API** (`LLMTestCase` + `metric.measure(test_case)` / `a_measure`)
- `async_mode=True` 内置并发
- 自定义 LLM 走 `DeepEvalBaseLLM` 抽象, 跟 `OpenAILike` 一样支持 DeepSeek
- 本地优先: `runs evaluations locally on your environment. Confident AI is optional.` (我们不需要 confident-ai.com)

## 2. 目标 (in-scope)

1. **完全替换** `LlamaIndexEvaluator` 为 `DeepEvalEvaluator`, 5 个 metric (4 旧 + 1 新 Hallucination) 名字 / 分数范围 (0-1) / 语义保持一致
2. **下游契约扩展**: `RAGAMetrics` 新增 `hallucination: float | None` 字段 (5th key, 在 context_recall 之后, context_entity_precision 之前). `to_dict()` / `avg_score` 同步扩
3. **存储不变**: `EvaluationSample.metrics` 是 JSON 列, 5-key dict 自动适配, 无 alembic migration
4. **测试不破**: 现有 4 个 eval 测试文件 (test_runner / test_router / test_runner_registry / test_models) 仅 hard-code 字符串改 1 处, 0 行为变化
5. **LLM judge 一致**: 仍走 DeepSeek (`OPENAI_BASE_URL` + `OPENAI_API_KEY` + `LLM_MODEL`), 不引入新云服务
6. **删 dead code**: `src/api/routes.py:42-65` 整个 `/api/v1/evaluate` handler + `src/api/__init__.py:3` re-export + `tests/api/test_routes.py:20-22` 同步删. 跑契约测试验证 0 影响

## 3. 非目标 (out-of-scope, YAGNI)

- **不** 引入 Confident AI cloud dashboard / dataset 管理 (本地运行即可)
- **不** 改 metric 集合 (本次新增 1 个 Hallucination, **不**加 Bias / Toxicity / PII / G-Eval / Summarization 等)
- **不** 写 DeepEval 的 metric unit test (DeepEval 官方已覆盖, 我们只测集成路径)
- **不** 改 `context_entity_precision` 字段 (保持兼容, avg_score 跳过它)
- **不** override DeepEval 内置英文 `evaluation_template` (跟原 LlamaIndex 行为对齐 — 后续可独立 P1 follow-up)

## 4. 现状 (in 192 行)

### 4.1 4 个 metric 当前实现

| Metric | LlamaIndex 类 | 文件:行 | 说明 |
|--------|--------------|---------|------|
| faithfulness | `FaithfulnessEvaluator` | `llama_eval.py:60-63` | 1 行 lazy import |
| answer_relevancy | `AnswerRelevancyEvaluator` | `llama_eval.py:65-67` | 1 行 lazy import |
| context_precision | `ContextRelevancyEvaluator` | `llama_eval.py:69-71` | ⚠️ LlamaIndex 内部名是 ContextRelevancy, 跟 RAGAS 主流的 ContextualPrecision 不一致 |
| context_recall | `_ContextRecallJudge` (自实现) | `llama_eval.py:152-185` | claim-level LLM judge, 160 行手写 |

### 4.2 调用点 (2 处)

| 位置 | 用途 | 状态 |
|------|------|------|
| `src/eval/router.py:30,140` | bulk async batch eval (live, mounted at `/api/evaluate/runs`) | active |
| `src/api/routes.py:42-65` | single-shot `/api/v1/evaluate` | ⚠️ **dead code, router 未 mount, 本次删** |

### 4.3 测试 (4 文件 + 1 待删, 全部 mock 路径)

`tests/eval/test_runner.py:41-63` 关键契约:
- `evaluator.evaluate_single(**kwargs) -> object` 有 `.to_dict()` 返回 dict (现 4-key, 改后 5-key)
- 错误字符串前缀 `LlamaIndexEvalError:` (line 227 hard-coded) ← **替换为 `DeepEvalError:`**

`tests/api/test_routes.py:20-22` 测的是 unmounted 路由, **本次同步删**.

### 4.4 依赖 (pyproject.toml)

- `llama-index>=0.14.22` ← **保留** (retrieval/embedder/llm 还用, 见 §8.2 风险)
- `llama-index-llms-openai-like>=0.7.2` ← **保留** (retrieval/embedder/llm 用)
- `llama-index-core.evaluation` (sub-module) ← 替换后不再需要, 删 import 即可
- **新增** `deepeval>=3.x`

## 5. 设计

### 5.1 API 保持兼容 (零下游变化, 1 字段扩展)

```python
# 现在 (LlamaIndex)
evaluator = LlamaIndexEvaluator(llm=judge_llm)
metrics = await evaluator.evaluate_single(
    question=q, answer=a, contexts=ctxs, ground_truth=gt,
)  # -> RAGAMetrics (4 metric)

# 替换后 (DeepEval) — 调用方代码 0 改动
evaluator = DeepEvalEvaluator(llm=judge_llm)
metrics = await evaluator.evaluate_single(...)  # -> RAGAMetrics (5 metric, 多 hallucination)
```

### 5.2 `RAGAMetrics` 扩展 (1 字段插入)

`src/common/evaluation.py:11-19` 改:

```python
@dataclass
class RAGAMetrics:
    """RAG 评估指标 dataclass — 5 指标 (2026-06-16 加 Hallucination)"""
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    hallucination: float | None = None         # ← 新 (5th, DeepEval HallucinationMetric)
    context_entity_precision: float | None = None  # 保留兼容, 不进 avg_score
    raw_result: dict | None = None

    def to_dict(self) -> dict:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "hallucination": self.hallucination,                       # ← 新
            "context_entity_precision": self.context_entity_precision,  # 保留
        }

    @property
    def avg_score(self) -> float | None:
        # 5-key 平均 (None 过滤, 动态 0-5 维度) — 老样本 (无 hallucination) 退化为 4-key 平均
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

### 5.3 `DeepEvalEvaluator` 实现 (新文件)

```python
# src/eval/deepeval_eval.py (新文件, 替代 llama_eval.py)
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    HallucinationMetric,            # ← 新
)
from deepeval.test_case import LLMTestCase
from deepeval.models.base_model import DeepEvalBaseLLM
from ..common.evaluation import RAGAMetrics


class DeepSeekJudge(DeepEvalBaseLLM):
    """DeepSeek via OpenAI-compatible API, 走 DeepEvalBaseLLM 抽象.

    复刻原 _get_judge_llm() 行为:
    - base_url 默认 https://api.deepseek.com, DeepSeek 时自动追加 /beta
    - 温度 0.0, 无 function calling
    """
    def __init__(self):
        self.model_name = os.getenv("LLM_MODEL", "deepseek-chat")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        if "deepseek" in base_url and not base_url.endswith("/beta"):
            base_url = base_url.rstrip("/") + "/beta"
        self.base_url = base_url
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    def load_model(self):
        return OpenAI(base_url=self.base_url, api_key=self.api_key)

    def generate(self, prompt: str) -> str:
        client = self.load_model()
        resp = client.chat.completions.create(
            model=self.model_name, temperature=0.0, messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content

    async def a_generate(self, prompt: str) -> str:
        # deepeval 的 async_mode=True 走 a_generate()
        return await asyncio.to_thread(self.generate, prompt)


class DeepEvalEvaluator:
    """DeepEval 评估器 — 5 个 RAG 指标, 替代 LlamaIndexEvaluator."""

    DEFAULT_METRICS = (
        "faithfulness", "answer_relevancy", "context_precision",
        "context_recall", "hallucination",
    )

    def __init__(self, llm: Any = None, metrics: list[str] | None = None):
        # llm 参数保留为兼容接口 (router 里传 OpenAILLM().llm), 内部统一用 DeepSeekJudge
        # 因为 deepeval metric 需要 DeepEvalBaseLLM 实例, 不是 llama_index 的 LLM 包装
        self._judge = llm if isinstance(llm, DeepEvalBaseLLM) else DeepSeekJudge()
        self._metric_names = metrics or list(self.DEFAULT_METRICS)

    def _build_test_case(self, question, answer, contexts, ground_truth):
        return LLMTestCase(
            input=question,
            actual_output=answer,
            retrieval_context=contexts or [],
            expected_output=ground_truth,  # ContextualRecallMetric 需要
        )

    def _build_metric(self, name: str) -> Any:
        # 每个 metric 单独实例, threshold=0.0 (我们不卡阈值, 只取分数)
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

    async def evaluate_single(self, question, answer, contexts, ground_truth=None) -> RAGAMetrics:
        test_case = self._build_test_case(question, answer, contexts, ground_truth)

        async def _run(name: str) -> float | None:
            if name not in self._metric_names:
                return None
            # context_recall / hallucination 都需要 reference/ground_truth, 缺则跳过
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
            hallucination=results[4],         # ← 新
            raw_result=None,
        )
```

### 5.4 错误前缀统一改 `DeepEvalError:`

`runner.py:76` 抛 `f"LlamaIndexEvalError: {e}"` → 改为 `f"DeepEvalError: {e}"`. `test_runner.py:227` hard-coded 字符串同步改.

**`DeepEvalError` class 位置**: 在新文件 `src/eval/deepeval_eval.py` 顶部定义, 简单继承 `RuntimeError` 即可:

```python
class DeepEvalError(RuntimeError):
    """DeepEval 评估失败 (替代原 LlamaIndexEvalError)"""
```

runner.py:19 改成 `from .deepeval_eval import DeepEvalError` (替换原 `from ..integrations.dify_client import DifyAPIError` 旁边的 import 块, 或新增一行).

### 5.5 删 dead code (`/api/v1/evaluate` + 相关 Pydantic schemas + 测试)

dead code 包含 handler + 它的 Pydantic 输入输出 + 它们的测试, 全链路删:

| 文件 | 删什么 | 行号 |
|------|--------|------|
| `src/api/routes.py` | `evaluate_endpoint` 整个 handler (含 `@router.post("/evaluate")` 装饰器) | 42-65 |
| `src/api/routes.py` | 内部 lazy import `LlamaIndexEvaluator` | 46 |
| `src/api/routes.py` | `from .schemas import (...)` 多行 import 中的 `EvaluateRequest, EvaluateResponse` | 7-15 |
| `src/api/schemas.py` | `class EvaluateRequest` + `class EvaluateResponse` | 24-36 |
| `src/api/__init__.py` | re-export 块中 `EvaluateRequest, EvaluateResponse` | 4-12 |
| `src/api/__init__.py` | `__all__` 列表中 `"EvaluateRequest", "EvaluateResponse"` 2 行 | 19-20 |
| `tests/api/test_routes.py` | `from src.api.schemas import EvaluateRequest` + `test_evaluate_request_schema` | 3, 20-22 |
| `tests/api/test_schemas.py` | `test_evaluate_request_all_fields` + `test_evaluate_response_all_none` + `test_evaluate_response_with_scores` | 66-91 |

**前置 (步骤 5)**: 跑 `pytest tests/test_api_contract.py -v` + `grep -E "/api/v1/evaluate|EvaluateRequest" tests/test_api_contract.py` 验证 FRONTEND_EXPECTS 不引用 (本次 grep 已确认 0 hit). 红了不能删 (project CLAUDE.md "删 BFF 路由前必须跑契约测试").

**删后影响**: `src/api/router` (从 `src/api/routes`) 仍被 `src/api/__init__.py:3` re-export 但**未 mount** (只有 `eval_router` mounted, 见 `src/__init__.py:32,40`). 测试 38 → 34 (-1 routes + -3 schemas = -4).

## 6. 关键决策 (已用户审批)

| # | 决策 | 答案 | 原因 |
|---|------|------|------|
| D1 | 替换范围 | **5 metric (4 旧 + 1 新 Hallucination)** | Hallucination 跟 Faithfulness 互补 (faithfulness = claim 被 context 支持, hallucination = answer 包含 context 外的虚假信息) |
| D2 | LLM judge | **DeepSeek** (复用现有 OPENAI_API_KEY/BASE_URL/MODEL) | 零新云服务, 跟原 OpenAILike 路径一致 |
| D3 | dead code `/api/v1/evaluate` | **这次一并删** | 跟项目"删 BFF 前跑契约测试"规范走 |
| D4 | Confident AI cloud | **不用** (默认本地) | 官方明确 optional, 我们不需 dashboard |
| D5 | metric threshold | **0.0** (不卡阈值, 只取分数入库) | 跟 `RAGAMetrics.avg_score` 现有行为一致 |
| D6 | `avg_score` 计算维度 | **5-key 平均** (None 过滤动态) | 老样本 (4-key, hallucination=None) 退化为 4 平均, 不破坏历史 |

## 7. 实施 (7 个原子步骤)

| # | 内容 | 验证 |
|---|------|------|
| 1 | `uv add deepeval` 装包 | `uv sync` OK, `python -c "import deepeval; print(deepeval.__version__)"` 成功 |
| 2 | 新建 `src/eval/deepeval_eval.py` (含 `DeepSeekJudge` + `DeepEvalEvaluator` + 5 metric) | 文件语法 OK, import 不报缺包 |
| 3 | 改 `src/common/evaluation.py:11-49` RAGAMetrics 加 `hallucination` 字段 + `to_dict` + `avg_score` 5-key | `python -c "from src.common.evaluation import RAGAMetrics; print(RAGAMetrics.__dataclass_fields__.keys())"` 含 `hallucination` |
| 4 | 改 `src/eval/router.py:30,140` 引用 `LlamaIndexEvaluator` → `DeepEvalEvaluator`; 改 `runner.py:76` 错误前缀 → `DeepEvalError` (顺手 `runner.py:19` import 改 `from .deepeval_eval import DeepEvalError`); 改 `test_runner.py:227` hard-code 字符串 | `pytest tests/eval/ -v` 全绿 (5 runner + 12 router + 4 registry + 4 model + 9 csv_parser + 4 template) |
| 5 | 跑 `pytest tests/test_api_contract.py -v` + `grep -E "/api/v1/evaluate\|EvaluateRequest" tests/test_api_contract.py` 确认 0 hit (已确认) | 0 hit, 可删 |
| 6 | 删 dead code: `src/api/routes.py` 整个 handler (42-65) + lazy import (46) + schemas import (7-15) + `src/api/schemas.py` 两个类 (24-36) + `src/api/__init__.py` re-export + `__all__` + `tests/api/test_routes.py:3,20-22` + `tests/api/test_schemas.py:66-91` 3 个 test | `pytest tests/api/ -v` 剩非 evaluate 部分 (test_query*, test_ingest*, test_source_*) 绿 |
| 7 | 删 `src/eval/llama_eval.py` (净删 192 行) | `grep -r "llama_eval" src/ tests/` 0 hit, `grep -r "LlamaIndexEvalError" src/ tests/` 0 hit, 整体 `pytest + typecheck + lint` 绿 |

**风险** (commit 顺序约束):
- 步骤 4 不能跟步骤 3 拆, 步骤 3 改 `RAGAMetrics` 后 `test_runner.py` 才不报多余字段
- 步骤 5 必须**先** 步骤 6, 红了不能删
- 步骤 7 最后, 不先删 (避免 lint-staged 把其它 subagent 改动卷进来)

## 8. 风险与缓解

### 8.1 中文 judge prompt 行为差异 (中)

DeepEval 内置 prompt 是英文模板 ("Your task is to evaluate..."). 在中文 RAG (西门子领域) 上分数可能跟 LlamaIndex 中文 prompt 不同. **缓解**:
- 端到端验收时跑 5 条 ground-truth 样本, 对比旧 LlamaIndex 分数, 偏差 < 0.15 算可接受
- 不行再 override `evaluation_template` 传中文 prompt (P3 follow-up)

### 8.2 死代码删除顺序 (低)

未 mount 路由删除风险低 (不影响生产路径), 但 `test_routes.py` + `test_schemas.py` 依赖 unmounted handler + 它的 Pydantic schemas. **缓解**: 步骤 5 跑契约测试确认 0 hit, 步骤 6 同 commit 删 handler + Pydantic 类 + 测试, 跑 `pytest tests/api/` 验证.

### 8.3 5-key 兼容性 (低-中)

历史 `EvaluationSample.metrics` 是 4-key dict, 改后前端 / 报表读 `.hallucination` 字段会拿到 `KeyError` (如果用 dict 访问) 或 `None` (如果用 .get). **缓解**:
- 前端读 JSON 用 `metrics.get("hallucination")` 安全访问, 不存在返 None
- 验收加 1 条: 启动 service 读 1 个老样本 (4-key), `.hallucination` 返 None 不崩

### 8.4 `LLM_MODEL` 环境变量命名歧义 (低)

DeepEval 的 `metric.model="gpt-4.1"` 字符串对应 OpenAI 模型. 我们用 `DeepSeekJudge` 自定义, 不走这个字段, 风险 0.

### 8.5 并发模型变化 (低)

原实现用 `run_in_executor` hack 1 worker 并发, 新实现走 deepeval `async_mode=True` + `asyncio.gather`. 并发上限从 1 → 5 (5 个 metric 并发). 单样本评估时间从 ~30s → ~8-12s (5 metric 同步走完). 评估 100 样本 bulk run 估 15-25 分钟 (concurrency=4 跑, 跟现有一样).

## 9. 验收

- [ ] `uv sync` 后 `python -c "import deepeval; print(deepeval.__version__)"` 成功
- [ ] `RAGAMetrics.__dataclass_fields__` 包含 `hallucination` (5th)
- [ ] `uv run pytest tests/eval/ -v` 6 文件 / 38 测试全绿 (5 runner + 12 router + 4 registry + 4 model + 9 csv_parser + 4 template)
- [ ] `uv run pytest tests/api/ -v` 删后剩非 evaluate 部分绿 (11 个: 3 routes + 8 schemas)
- [ ] `uv run pytest tests/test_api_contract.py -v` 仍绿 (跟 eval 路由契约未变)
- [ ] `uv run ruff check src tests` 0 新 warning
- [ ] `uv run mypy src` 0 新 error
- [ ] `grep -r "llama_eval" src/ tests/` 0 hit
- [ ] `grep -r "LlamaIndexEvalError" src/ tests/` 0 hit
- [ ] 端到端: 启动 service, `POST /api/evaluate/runs` 上传 5 条 CSV (含 ground_truth), 完成后:
  - [ ] `avg_metrics` 5 key 全有分数
  - [ ] 5 分数范围 0-1
  - [ ] 5 分数跟替换前 (LlamaIndex 旧实现) 偏差 < 0.15 (或文字说明差异原因)
- [ ] 老样本兼容: 读 1 个旧 4-key 样本, `.hallucination` 返 None 不崩

## 10. 关键决策记录 (避免重新讨论)

- ✅ 5 metric 替换 (4 旧 + 1 新 Hallucination)
- ✅ LLM judge 走 DeepSeek (不引入 GPT-4o)
- ✅ 纯本地运行, 不连 Confident AI cloud
- ✅ `RAGAMetrics` 加 `hallucination` 字段 (5th), 字段位置 = context_recall 之后, context_entity_precision 之前
- ✅ `avg_score` 改 5-key 平均 (None 过滤, 动态维度)
- ✅ 错误前缀 `LlamaIndexEvalError` → `DeepEvalError` 同步改
- ✅ 这次一并删 dead code `/api/v1/evaluate` (走 project CLAUDE.md 删 BFF 流程)
- ✅ `pyproject.toml` 保留 `llama-index*` (retrieval/embedder/llm 还在用)
- ✅ 删 `llama_eval.py` 是最后一步, 不先删
- ✅ threshold=0.0 (不卡阈值, 只取分数)

## 11. 关联文件

| 文件 | 改动 |
|------|------|
| `src/eval/llama_eval.py` | **删** (192 行) |
| `src/eval/deepeval_eval.py` | **新建** (~140 行, 含 `DeepEvalError` + `DeepSeekJudge` + `DeepEvalEvaluator`) |
| `src/common/evaluation.py` | **改** RAGAMetrics 加 `hallucination` 字段 + to_dict + avg_score (5-key) |
| `src/eval/router.py` | **改** import + 引用 (lines 30, 140) |
| `src/eval/runner.py` | **改** 错误前缀 (line 76) + import `DeepEvalError` |
| `src/api/routes.py` | **删** evaluate_endpoint (42-65) + lazy import (46) + 清理 schemas import (7-15) |
| `src/api/schemas.py` | **删** `EvaluateRequest` + `EvaluateResponse` (24-36) |
| `src/api/__init__.py` | **删** re-export 块中 `EvaluateRequest, EvaluateResponse` (4-12) + `__all__` 2 行 (19-20) |
| `tests/eval/test_runner.py` | **改** line 227 hard-code 字符串 |
| `tests/api/test_routes.py` | **删** import (3) + `test_evaluate_request_schema` (20-22) |
| `tests/api/test_schemas.py` | **删** `test_evaluate_request_all_fields` + `test_evaluate_response_all_none` + `test_evaluate_response_with_scores` (66-91) |
| `pyproject.toml` | **加** `deepeval>=3.x` |

## 12. Follow-up (不在本 spec)

- **P0**: 跑 5 条样本对比新旧分数偏差 (跟验收对齐)
- **P1**: 中英 RAG 场景下 override `evaluation_template` 提升 DeepEval 中文 judge 稳定性
- **P2**: 加更多 DeepEval 指标 (Bias, Toxicity, Summarization) — 需扩 schema
- **P3**: 引入 Confident AI cloud 跑 batch eval dashboard
