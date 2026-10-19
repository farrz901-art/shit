# DeepEval 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 初始化](#二安装--初始化)
- [三、核心概念 & 抽象](#三核心概念--抽象)
- [四、常用 API & 命令速查](#四常用-api--命令速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、评测 & 调优技巧](#八评测--调优技巧)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

DeepEval 是一个开源的 LLM 评估框架，提供 50+ 预置评估指标（faithfulness、hallucination、answer relevancy、contextual precision/recall 等），既支持基于规则 + Embedding 的快速评估，也支持 LLM-as-judge 复杂评估。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **DeepEval** | 综合 LLM 评估框架 | 50+ 指标，Pytest 风格，跟 CI 集成好 |
| **RAGAS** | RAG 专项评估 | 4-5 个核心指标，DeepEval 已包含 |
| **Langfuse** | LLM 可观测 + 简单评估 | 适合 tracing，深度评估用 DeepEval |
| **Braintrust** | 全套 LLM 工具（含评估） | 商业产品 |
| **OpenAI Evals** | OpenAI 官方 | 偏研究 / 学术 |

**DeepEval 解决的核心问题**：
- **RAG 质量量化**：检索到的内容是否真的有用？生成的答案是否基于检索？有没有幻觉？
- **回归测试**：每次改 prompt / 模型，检查所有指标不退化
- **指标比较**：不同 LLM / embedding 模型的客观对比

---

## 二、安装 & 初始化

### 2.1 安装

```bash
uv add deepeval
# 或
pip install deepeval
```

### 2.2 登录 Confident AI（可选）

```bash
deepeval login
# 浏览器打开 https://app.confident-ai.com 拿 API key
```

不登录也能用，只是没法同步到云端 dashboard。

### 2.3 环境变量

```bash
# OpenAI（评估默认用 GPT-4o 当 judge）
OPENAI_API_KEY=sk-xxx

# 自定义 judge 模型
DEEPEVAL_DEFAULT_JUDGE_MODEL=openai:deepseek-chat
DEEPEVAL_DEFAULT_JUDGE_BASE_URL=https://api.deepseek.com
```

---

## 三、核心概念 & 抽象

### 3.1 Metric（评估指标）

DeepEval 的核心抽象。每种指标是一个类，定义"如何打分"。

**RAG 核心指标：**

| 指标 | 含义 | 范围 |
|------|------|------|
| `Faithfulness` | 答案是否忠于检索内容（无幻觉） | 0-1 |
| `AnswerRelevancy` | 答案是否切题 | 0-1 |
| `ContextualPrecision` | 检索结果排序质量 | 0-1 |
| `ContextualRecall` | 检索结果覆盖率 | 0-1 |
| `ContextualRelevancy` | 检索内容跟问题的相关度 | 0-1 |
| `Hallucination` | 是否含幻觉 | 0-1（越低越好） |

**通用指标：**

| 指标 | 用途 |
|------|------|
| `GEval` | 自定义 LLM-as-judge（用自然语言描述评估标准） |
| `Toxicity` | 内容安全性 |
| `Bias` | 偏见检测 |
| `Summarization` | 摘要质量 |

### 3.2 Test Case（测试用例）

```python
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(
    input="什么是 RAG?",
    actual_output="RAG 是检索增强生成...",
    expected_output="RAG (Retrieval-Augmented Generation)...",
    retrieval_context=["文档 1: ...", "文档 2: ..."],
    context=["文档 1: ...", "文档 2: ..."],
)
```

### 3.3 Dataset（数据集）

```python
from deepeval.dataset import EvaluationDataset

dataset = EvaluationDataset(test_cases=[test_case_1, test_case_2, ...])
```

### 3.4 LLM-as-Judge

DeepEval 默认用 GPT-4o 当 judge，给每个指标打分。也可以自定义 judge 模型。

---

## 四、常用 API & 命令速查

### 4.1 单指标评估

```python
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(
    input="法国的首都是什么？",
    actual_output="巴黎。",
    retrieval_context=["法国，首都是巴黎。"],
)

metric = FaithfulnessMetric(threshold=0.7)
metric.measure(test_case)
print(metric.score, metric.reason)
```

### 4.2 批量评估

```python
from deepeval import evaluate

results = evaluate(
    test_cases=[test_case_1, test_case_2, test_case_3],
    metrics=[FaithfulnessMetric(), AnswerRelevancyMetric()],
)
print(results)
# {"Faithfulness": 0.85, "AnswerRelevancy": 0.92, ...}
```

### 4.3 Pytest 风格

```python
# tests/test_rag_quality.py
import pytest
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric
from deepeval import assert_test

def test_rag_faithfulness():
    test_case = LLMTestCase(
        input="...",
        actual_output=get_rag_answer("..."),    # 调项目 RAG
        retrieval_context=get_retrieval_context("..."),
    )
    metric = FaithfulnessMetric(threshold=0.7)
    assert_test(test_case, [metric])
```

### 4.4 自定义指标

```python
from deepeval.metrics import GEval

custom_metric = GEval(
    name="Domain-Specific Quality",
    criteria="回答必须使用项目专有术语，且提供具体例子。",
    threshold=0.6,
)
```

### 4.5 CLI

```bash
deepeval test run tests/test_rag_quality.py    # 跑测试
deepeval view                                 # 开 dashboard
```

---

## 五、项目集成点

### 5.1 项目当前使用 LlamaIndex 自带评估

`src/eval/router.py:23` + `src/eval/llama_eval.py:41`（推测）用 LlamaIndex 内置评估器（`FaithfulnessEvaluator` / `RelevancyEvaluator`），DeepEval 还没集成。

### 5.2 项目评估现状

```bash
# 上传评估数据集
POST /api/evaluate
# 上传 CSV，列：question, expected_answer, context
# 后台跑 LlamaIndex 4 指标：Faithfulness / Relevancy / Correctness / Similarity
```

输出：每条 query 的分数 + 总报告（JSON / CSV）。

### 5.3 DeepEval 集成建议

如果团队对评估指标数量 / 灵活性有更高要求，DeepEval 是升级路径：
- 复用现有 CSV 数据集（`expected_answer`、`context`、`actual_output`）
- 替换 LlamaIndex evaluator 为 DeepEval metric
- 评估报告走 Confident AI dashboard

---

## 六、项目代码示例

### 6.1 项目当前评估入口

`src/eval/router.py:23`（推测）：

```python
from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile

router = APIRouter(prefix="/api/evaluate", tags=["evaluate"])

@router.post("/", summary="上传评估 CSV 跑 LlamaIndex 评估")
async def upload_eval_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(...),
):
    # 保存 CSV 到 MinIO
    # 后台 worker 跑 LlamaIndex 4 指标
    return {"task_id": "..."}
```

### 6.2 DeepEval 集成示例

把 LlamaIndex 评估换成 DeepEval：

```python
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric, ContextualPrecisionMetric
from deepeval import evaluate
import csv

def run_deepeval_eval(csv_path: str, project_rag_fn) -> dict:
    """读 CSV → 调项目 RAG → DeepEval 评估"""
    test_cases = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            actual = project_rag_fn(row["question"])
            contexts = project_rag_retrieval(row["question"])
            test_cases.append(LLMTestCase(
                input=row["question"],
                actual_output=actual,
                expected_output=row.get("expected_answer"),
                retrieval_context=contexts,
            ))

    metrics = [
        FaithfulnessMetric(threshold=0.7),
        AnswerRelevancyMetric(threshold=0.7),
        ContextualPrecisionMetric(threshold=0.7),
    ]
    return evaluate(test_cases, metrics)
```

### 6.3 项目 RAG 函数（包装）

复用项目现有 `SimpleRAGWorkflow`：

```python
# packages/service/src/orchestration/simple_rag.py:8-29
from src.orchestration.simple_rag import SimpleRAGWorkflow

workflow = SimpleRAGWorkflow(
    vector_store=get_vector_store(),
    embedder=get_embedder(),
    llm=get_llm(),
    top_k=5,
)

async def project_rag_fn(question: str) -> str:
    event = await workflow.arun(question)
    return event.response

async def project_rag_retrieval(question: str) -> list[str]:
    event = await workflow.arun(question)
    return [n.text for n in event.source_nodes]
```

### 6.4 GEval 自定义业务指标

`src/eval/custom_metrics.py`（新建）：

```python
from deepeval.metrics import GEval

rag_accuracy = GEval(
    name="RAG 业务准确度",
    criteria=(
        "判断 RAG 答案是否：\n"
        "1. 优先使用项目专有术语（如 'pgvector'、'Presigned URL'）\n"
        "2. 引用至少一个具体步骤或代码示例\n"
        "3. 避免泛泛而谈（如'你可以使用数据库'）"
    ),
    threshold=0.6,
)
```

---

## 七、项目没用到的能力

以下 DeepEval 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Confident AI Dashboard** | 云端 dashboard | 团队协作评估报告 |
| **50+ 预置指标** | 全面评估 | 评估要求高时使用 |
| **Custom GEval** | 业务定制指标 | 业务术语 / 风格检查 |
| **Multi-turn Conversation 评估** | 整段对话质量 | 聊天产品评估 |
| **Agent 路径评估** | 工具调用链分析 | Deep Agents / LangGraph 项目 |
| **Hallucination Detection** | 幻觉检查 | 关键业务必须用 |
| **Red Teaming** | 对抗测试 | 安全性测试 |
| **CI 集成** | PR 拦截 | GitHub Actions 自动跑 |

**建议关注**：Hallucination + Faithfulness 是 RAG 系统的命门，建议指标化。

---

## 八、评测 & 调优技巧

### 8.1 指标选型

| 业务关注 | 推荐指标 |
|---------|---------|
| 内容真实（无幻觉）| `Faithfulness`, `Hallucination` |
| 内容切题 | `AnswerRelevancy` |
| 检索质量 | `ContextualPrecision`, `ContextualRecall` |
| 内容安全 | `Toxicity`, `Bias` |
| 业务风格 | 自定义 `GEval` |

### 8.2 评估基线

第一次评估时记录所有指标分值，作为基线。后续迭代对比基线：

```python
BASELINE = {
    "Faithfulness": 0.85,
    "AnswerRelevancy": 0.78,
    "ContextualPrecision": 0.72,
}
# 任何指标掉 5% 报警
```

### 8.3 调优方向

| 低分指标 | 调优方向 |
|---------|---------|
| Faithfulness < 0.7 | prompt 强化"只基于上下文回答"、降低 temperature |
| AnswerRelevancy < 0.7 | prompt 强化"针对问题回答"、改 query 改写 |
| ContextualPrecision < 0.6 | 改 embedding 模型、加 rerank、top_k 调整 |
| ContextualRecall < 0.6 | 扩大 top_k、检查 chunk 大小 |

### 8.4 Judge 模型选择

- **GPT-4o**：评估最准但贵（$0.01/次）
- **GPT-4o-mini**：便宜 10x，精度略低
- **DeepSeek / Qwen**：开源，部署本地，0 成本但慢
- **项目推荐**：开发用 GPT-4o，CI 跑批量用 GPT-4o-mini

---

## 九、最佳实践 & 常见坑

### 1. 评估数据标注质量

评估指标上限 = 数据标注质量。低质量 expected_answer 会让 ContextualRecall 失真。

### 2. 不要只用一个指标

Faithfulness 高 + AnswerRelevancy 低 = 答案不切题；反之可能幻觉。多指标组合判断。

### 3. CI 集成

```yaml
# .github/workflows/eval.yml
- name: Run DeepEval
  run: deepeval test run tests/test_rag_quality.py
- name: Upload results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: eval-report
    path: reports/eval.json
```

### 4. Judge API 限流

DeepEval 每条 case 调 judge 模型 1-3 次。100 条 case = 100-300 次 API 调用。要么加 retry + backoff，要么用 GPT-4o-mini。

### 5. 成本估算

| 数据集 | GPT-4o 成本 | GPT-4o-mini 成本 |
|--------|------------|------------------|
| 100 cases × 4 指标 | $4 | $0.4 |
| 1000 cases × 4 指标 | $40 | $4 |

生产数据评估一次 ~$10-$50。

### 6. 评估数据漂移

业务 prompt / embedding 模型改了，老数据集可能不再代表真实用户问题。每月补充一次新 case。

### 7. 项目测试隔离规范

项目 `service/CLAUDE.md` 强制测试 mock，**不要**让 DeepEval 在 CI 中连真实数据库。DeepEval 评估 RAG 函数时，应该用 `unittest.mock.patch` mock RAG 调用。

---

## 📚 参考

- [DeepEval 官方文档](https://docs.confident-ai.com/)
- [DeepEval GitHub](https://github.com/confident-ai/deepeval)
- [Confident AI Dashboard](https://app.confident-ai.com/)
- [DeepEval 指标列表](https://docs.confident-ai.com/docs/metrics-introduction)
- [RAGAS 框架](https://docs.ragas.io/)（同类对比）
- [Langfuse 评估](https://langfuse.com/docs/scores/overview)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
