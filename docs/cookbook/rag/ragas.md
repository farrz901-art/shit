# RAGAS 教程

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

RAGAS（Retrieval-Augmented Generation Assessment）是专为 RAG 系统设计的开源评估框架，提供 4 个核心指标：Faithfulness、Answer Relevancy、Context Precision、Context Recall。它不需要 ground truth 答案（部分指标），让 RAG 评估门槛大幅降低。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **RAGAS** | RAG 专项评估 | 4 核心指标 + 无 ground truth 评估 |
| **DeepEval** | 综合 LLM 评估 | 50+ 指标（详见 `rag/deepeval.md`） |
| **TruLens** | LLM 评估 + tracing | 跟 LangSmith 类似 |
| **Phoenix（Arize）** | LLM tracing + 评估 | 自部署稍复杂 |
| **Langfuse 评估** | tracing + 简单评估 | 集成在 Langfuse |

**RAGAS 解决的核心问题**：
- **RAG 核心 4 指标**：faithfulness / answer relevancy / context precision / context recall
- **无 ground truth 评估**：部分指标只需要问题 + context + 答案
- **客观对比**：不同 retriever / LLM / prompt 的客观打分
- **CI 集成**：能跑测试脚本，PR 自动跑评估

---

## 二、安装 & 初始化

### 2.1 安装

```bash
uv add ragas datasets
# 项目相关包：
# "datasets>=5.0.0", # HuggingFace datasets, 给 RAG 评估管线构造标准评测集
# ragas 需要这个
```

### 2.2 环境变量

```bash
# OpenAI 兼容（评估用 LLM 当 judge）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com  # 项目用 DeepSeek 当 judge

# 如果跑 experiment 自动上传到 RAGAS dashboard
RAGAS_APP_TOKEN=rga_xxx
```

### 2.3 项目 LLM 配置

`src/common/evaluation.py`（推测）：

```python
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI
import os

def get_evaluator_llm():
    return LangchainLLMWrapper(
        ChatOpenAI(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            temperature=0,
        )
    )
```

---

## 三、核心概念 & 抽象

### 3.1 4 大核心指标

| 指标 | 输入 | 输出 | 含义 |
|------|------|------|------|
| **Faithfulness** | question + answer + contexts | 0-1 | 答案是否忠于检索内容（无幻觉）|
| **Answer Relevancy** | question + answer + contexts | 0-1 | 答案是否切题 |
| **Context Precision** | question + contexts + ground_truth | 0-1 | 检索结果排序质量（高 rank 的相关度）|
| **Context Recall** | question + contexts + ground_truth | 0-1 | 检索结果覆盖率（ground truth 涉及的事实是否被召回）|

### 3.2 SingleTurnSample（单轮样本）

```python
from ragas.dataset_schema import SingleTurnSample

sample = SingleTurnSample(
    user_input="什么是 RAG?",
    response="RAG 是检索增强生成...",
    retrieved_contexts=["文档1: ...", "文档2: ..."],
    reference="RAG (Retrieval-Augmented Generation) 是...",
)
```

### 3.3 EvaluationDataset（数据集）

```python
from ragas.dataset_schema import EvaluationDataset

dataset = EvaluationDataset(samples=[sample_1, sample_2, ...])
```

### 3.4 metrics vs metrics_llm

RAGAS 0.2+ 用 `metrics` + `metric.llm` 注入 LLM：

```python
from ragas.metrics import Faithfulness

metric = Faithfulness()
metric.llm = get_evaluator_llm()  # 注入 LLM 当 judge
```

### 3.5 evaluate() 函数

```python
from ragas import evaluate

result = evaluate(
    dataset=dataset,
    metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()],
)
print(result)  # 指标 dict
```

---

## 四、常用 API & 命令速查

### 4.1 单指标评估

```python
from ragas.metrics import Faithfulness
from ragas.dataset_schema import SingleTurnSample

sample = SingleTurnSample(
    user_input="法国的首都是什么？",
    response="巴黎。",
    retrieved_contexts=["法国，首都是巴黎。"],
)

metric = Faithfulness()
metric.llm = get_evaluator_llm()
score = await metric.single_turn_ascore(sample)
print(score)  # 0.95
```

### 4.2 批量评估

```python
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy

result = evaluate(
    dataset,
    metrics=[Faithfulness(), AnswerRelevancy()],
    llm=get_evaluator_llm(),
)
print(result)
# {"faithfulness": 0.85, "answer_relevancy": 0.92}
```

### 4.3 Test Data 生成

RAGAS 0.2+ 用 TestsetGenerator 自动生成测试集（需要 documents）：

```python
from ragas.testset import TestsetGenerator

generator = TestsetGenerator(llm=get_evaluator_llm(), embedding_model=get_embedder())
testset = generator.generate_with_langchain_docs(documents, testset_size=10)
# 生成 10 个测试用例（question + ground_truth + contexts）
```

### 4.4 HuggingFace datasets 集成

```python
from datasets import load_dataset
from ragas.dataset_schema import EvaluationDataset

# 加载项目 CSV / HF 数据集
dataset = EvaluationDataset.from_huggingface(load_dataset("my_eval_set"))
```

### 4.5 CLI

```bash
# 跑实验 + 上传 dashboard
ragas evaluate \
  --dataset ./eval_data.jsonl \
  --metrics faithfulness answer_relevancy context_precision context_recall \
  --llm deepseek-chat \
  --upload
```

---

## 五、项目集成点

### 5.1 项目**当前使用 LlamaIndex 评估**

`src/eval/router.py:23` + `src/eval/llama_eval.py:41` 用 LlamaIndex 4 指标：
- `FaithfulnessEvaluator`
- `RelevancyEvaluator`
- `CorrectnessEvaluator`
- `SimilarityEvaluator`

### 5.2 项目**已装** HuggingFace datasets

`pyproject.toml:30`：

```toml
"datasets>=5.0.0", # HuggingFace datasets, 给 RAG 评估管线构造标准评测集 (src/common/evaluation.py)
```

RAGAS 跟 `datasets` 深度集成，项目已经预留接入位置。

### 5.3 集成方案

`src/common/evaluation.py`（推测已存在）：

```python
from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from langchain_openai import ChatOpenAI
import os

def build_ragas_dataset(csv_path: str) -> EvaluationDataset:
    """读 CSV → RAGAS dataset"""
    import csv
    samples = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append(SingleTurnSample(
                user_input=row["question"],
                response=row["actual_answer"],
                retrieved_contexts=row["context"].split("\n") if row.get("context") else [],
                reference=row["expected_answer"],
            ))
    return EvaluationDataset(samples=samples)

def run_ragas_eval(dataset: EvaluationDataset) -> dict:
    """跑 RAGAS 4 指标"""
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    metrics = [Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()]
    for m in metrics:
        m.llm = llm
    return evaluate(dataset, metrics=metrics)
```

### 5.4 与 LlamaIndex 评估对比

| 维度 | LlamaIndex | RAGAS |
|------|-----------|-------|
| 指标数 | 4 个 | 4 个核心 + 自定义 |
| 评估对象 | `BaseEvaluator` | `Metric` 类 |
| LLM 注入 | 构造时 `llm=` | `metric.llm =` |
| 评估数据集 | `EvalDataset` | `EvaluationDataset` |
| 无 ground truth | 部分支持 | 部分指标（如 faithfulness）不需要 |
| 社区 | 中 | 大（arXiv 2024 论文） |

---

## 六、项目代码示例

### 6.1 项目评估入口

`src/eval/router.py:23`（推测）：

```python
@router.post("/api/evaluate")
async def run_evaluation(
    file: UploadFile = File(...),
    metrics: list[str] = Form(["faithfulness", "answer_relevancy"]),
    user: CurrentUser = Depends(...),
):
    # 保存 CSV 到 MinIO
    csv_path = save_csv_to_minio(file)

    # 跑评估（异步）
    background_tasks.add_task(run_eval_async, csv_path, metrics)

    return {"task_id": "running"}
```

### 6.2 RAGAS 集成实现

```python
# src/eval/ragas_eval.py (项目风格)
from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
from ragas import evaluate
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
import os
from loguru import logger

METRIC_MAP = {
    "faithfulness": Faithfulness,
    "answer_relevancy": AnswerRelevancy,
    "context_precision": ContextPrecision,
    "context_recall": ContextRecall,
}

def get_ragas_llm():
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        temperature=0,
    )

def get_ragas_embeddings():
    return OpenAIEmbeddings(
        model=os.getenv("EMBED_MODEL", "BAAI/bge-m3"),
        api_key=os.getenv("EMBED_API_KEY"),
        base_url=os.getenv("EMBED_BASE_URL"),
    )

async def run_ragas_eval(csv_path: str, metric_names: list[str]) -> dict:
    """跑 RAGAS 评估，返 {metric_name: avg_score, ...}"""
    import csv
    samples = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            samples.append(SingleTurnSample(
                user_input=row["question"],
                response=row["actual_answer"],
                retrieved_contexts=row.get("context", "").split("\n") if row.get("context") else [],
                reference=row.get("expected_answer"),
            ))
    dataset = EvaluationDataset(samples=samples)

    llm = get_ragas_llm()
    metrics = [METRIC_MAP[name]() for name in metric_names if name in METRIC_MAP]
    for m in metrics:
        m.llm = llm

    logger.info("Running RAGAS eval samples={} metrics={}", len(samples), [m.name for m in metrics])
    result = evaluate(dataset, metrics=metrics)
    return dict(result)
```

### 6.3 混合使用 LlamaIndex + RAGAS

```python
from llama_index.core.evaluation import CorrectnessEvaluator
from ragas.metrics import Faithfulness, AnswerRelevancy

async def hybrid_eval(question, response, contexts, expected):
    """LlamaIndex 4 指标 + RAGAS 2 指标 = 6 个"""
    judge_llm = get_ragas_llm()

    # RAGAS 部分
    ragas_sample = SingleTurnSample(
        user_input=question, response=response,
        retrieved_contexts=contexts, reference=expected,
    )
    faith = Faithfulness(); faith.llm = judge_llm
    rel = AnswerRelevancy(); rel.llm = judge_llm

    # LlamaIndex 部分
    li_correctness = CorrectnessEvaluator(llm=judge_llm)
    li_relevancy = RelevancyEvaluator(llm=judge_llm)

    return {
        "ragas_faithfulness": await faith.single_turn_ascore(ragas_sample),
        "ragas_answer_relevancy": await rel.single_turn_ascore(ragas_sample),
        "llama_correctness": li_correctness.evaluate(query=question, response=response, reference=expected).score,
        "llama_relevancy": li_relevancy.evaluate(query=question, response=response, contexts=contexts).score,
    }
```

### 6.4 测试集自动生成

```python
# 项目未来扩展：用 TestsetGenerator 从项目文档生成测试集
from ragas.testset import TestsetGenerator

def generate_testset(documents, testset_size: int = 50):
    """从项目 PDF / Markdown 生成 50 条测试用例"""
    generator = TestsetGenerator(
        llm=get_ragas_llm(),
        embedding_model=get_ragas_embeddings(),
    )
    testset = generator.generate_with_langchain_docs(documents, testset_size=testset_size)
    # 自动构造 question + ground_truth + contexts
    return testset
```

### 6.5 单条 metric 评估（开发调试）

```python
# 开发者手动验证某条记录
async def debug_eval(question: str, response: str, contexts: list[str]):
    sample = SingleTurnSample(
        user_input=question, response=response, retrieved_contexts=contexts,
    )
    faith = Faithfulness(); faith.llm = get_ragas_llm()
    score = await faith.single_turn_ascore(sample)
    return {"faithfulness": score}
```

---

## 七、项目没用到的能力

以下 RAGAS 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **TestsetGenerator** | 自动生成测试集 | 项目文档库成熟后启用 |
| **Custom Metric** | 业务自定义指标 | 业务特定评估 |
| **RAGAS Dashboard** | 云端实验管理 | 团队协作评估 |
| **Async Evaluation** | 并行跑指标 | 评估数据集大时 |
| **HF Datasets 集成** | 公开数据集评测 | 标准化评测 |
| **Experiment Tracking** | 实验历史对比 | A/B 评估场景 |
| **Custom Critique** | 业务特定维度 | 风格 / 合规检查 |

**建议关注**：TestsetGenerator 从项目文档自动生成测试集，省人工标注。

---

## 八、评测 & 调优技巧

### 8.1 指标选型

| 业务关注 | 推荐指标 |
|---------|---------|
| 内容真实（无幻觉）| `Faithfulness` |
| 内容切题 | `AnswerRelevancy` |
| 检索质量 | `ContextPrecision`, `ContextRecall` |
| 内容匹配 | `Correctness`（LlamaIndex）|

### 8.2 评估基线

第一次跑记录基线，后续 PR 跟基线对比：

```python
BASELINE = {
    "faithfulness": 0.85,
    "answer_relevancy": 0.78,
    "context_precision": 0.72,
    "context_recall": 0.68,
}
```

### 8.3 调优方向

| 低分 | 调优 |
|------|------|
| Faithfulness < 0.7 | prompt 强化"基于上下文"，temperature=0 |
| AnswerRelevancy < 0.7 | 改 query 改写 / 加 rerank |
| ContextPrecision < 0.6 | 改 embedding / top_k 调整 |
| ContextRecall < 0.6 | 扩大 top_k / 检查 chunk 大小 |

### 8.4 成本

每个 metric 一次评估调 judge LLM 1-3 次：

| 数据集 | GPT-4o | DeepSeek |
|--------|--------|----------|
| 100 cases × 4 指标 | $4 | $0.2 |
| 1000 cases × 4 指标 | $40 | $2 |

项目用 DeepSeek 当 judge 是性价比选择。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **业务 enum 走 lookup**（RAGAS 指标名也可能走 lookup）
2. **测试不连真实 LLM**（CI mock RAGAS）
3. **API Key 不进代码**（用 env）

### 最佳实践

1. **批量评估前注入 LLM**：

```python
metrics = [Faithfulness(), AnswerRelevancy()]
for m in metrics:
    m.llm = get_ragas_llm()  # 先注入，再 evaluate
```

2. **指标顺序不影响结果**：4 个指标独立算

3. **数据集 > 50 条**：才能稳定反映指标

4. **拆指标查看具体 case**：

```python
result = evaluate(dataset, metrics=[Faithfulness()])
# result.scores 是 DataFrame，能 group by case 看分布
df = result.scores
df[df['faithfulness'] < 0.5].to_csv("low_faithfulness_cases.csv")
```

5. **RAGAS 0.2 → 0.3 升级**：API 重大变化，参考 migration guide

### 常见坑

1. **没注入 LLM**：`metric.llm = None` → 报错"LLM not set"

```python
metric = Faithfulness()
metric.llm = get_ragas_llm()  # 必须！
```

2. **retrieved_contexts 是字符串**：

```python
# ❌ 错
retrieved_contexts="文档1内容"

# ✅ 对
retrieved_contexts=["文档1内容", "文档2内容"]
```

3. **ground truth 缺失**：

- `Faithfulness` / `AnswerRelevancy` / `ContextRecall` 需要 reference（ground truth）
- `ContextPrecision` 也需要
- 但 **`Faithfulness` 实际**不需要 reference，只需 contexts + response

4. **Judge 模型能力**：GPT-4o 评估准确 80%+，deepseek 评估准确 70%。项目 deepseek 性价比可接受

5. **同步 / 异步混用**：

```python
# ✅ 对
score = await metric.single_turn_ascore(sample)

# ❌ 错
score = metric.single_turn_ascore(sample)  # 同步方法不存在
```

6. **RAGAS 版本兼容**：0.2 → 0.3 有 breaking change，dataset schema 改了

7. **评估很慢**：4 指标 × 100 cases = 400 次 LLM 调用，并行才好

```python
import asyncio
results = await asyncio.gather(*[metric.single_turn_ascore(s) for s in samples])
```

8. **项目测试隔离**：

```python
from unittest.mock import patch

@patch("src.eval.ragas_eval.run_ragas_eval")
def test_eval_route(mock_run):
    mock_run.return_value = {"faithfulness": 0.9, "answer_relevancy": 0.85}
    # 测试
```

---

## 📚 参考

- [RAGAS 官方文档](https://docs.ragas.io/)
- [RAGAS GitHub](https://github.com/explodinggradients/ragas)
- [RAGAS 论文](https://arxiv.org/abs/2309.15217)
- [RAGAS 指标详解](https://docs.ragas.io/en/latest/concepts/metrics/index.html)
- [HuggingFace datasets](https://huggingface.co/docs/datasets)
- [项目 cookbook/rag/deepeval.md](deepeval.md)（同类对比）

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25