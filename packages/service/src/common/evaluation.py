"""RAG 评估指标 dataclass 和报告

RAGAMetrics / EvaluationReport / generate_evaluation_dataset.
评估逻辑: eval/deepeval_eval.py (DeepEval 5 metric, 2026-06-29 接入)
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RAGAMetrics:
    """RAG 评估指标 dataclass - 5 指标 (2026-06-29 加 Hallucination)"""

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    hallucination: float | None = None  # ← 新 (DeepEval HallucinationMetric)
    context_entity_precision: float | None = None  # 保留兼容, 不进 avg_score
    raw_result: dict | None = None

    def to_dict(self) -> dict:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "hallucination": self.hallucination,
            "context_entity_precision": self.context_entity_precision,
        }

    @property
    def avg_score(self) -> float | None:
        # 5-key 平均 (None 过滤), 老样本 (无 hallucination) 退化 4-key
        values = [
            v
            for v in [
                self.faithfulness,
                self.answer_relevancy,
                self.context_precision,
                self.context_recall,
                self.hallucination,
            ]
            if v is not None
        ]
        return sum(values) / len(values) if values else None

    def summary(self) -> str:
        lines = ["评估结果："]
        for metric, value in self.to_dict().items():
            lines.append(f"  {metric}: {value:.4f}" if value is not None else f"  {metric}: N/A")
        return "\n".join(lines)


@dataclass
class EvaluationReport:
    """批量评估报告"""

    total_samples: int
    metrics: RAGAMetrics
    per_sample_results: list[RAGAMetrics] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_samples": self.total_samples,
            "avg_metrics": self.metrics.to_dict(),
            "duration_seconds": self.duration_seconds,
        }

    def summary(self) -> str:
        avg = self.metrics.avg_score
        return f"评估报告：{self.total_samples} 个样本，平均分 {avg:.4f}" if avg else "评估报告：无有效指标"

    def pass_rate(self, threshold: float = 0.6) -> float:
        if not self.per_sample_results:
            return 0.0
        passed = sum(1 for r in self.per_sample_results if r.avg_score is not None and r.avg_score >= threshold)
        return passed / len(self.per_sample_results)


def generate_evaluation_dataset(qa_pairs: list[dict]) -> Any:
    """从 qa_pairs 生成评估 Dataset（需要 datasets 库）"""
    try:
        # 重依赖 lazy: datasets 启动慢 (~800ms), 仅评估场景需要
        from datasets import Dataset  # noqa: E402
    except ImportError:
        raise ImportError("datasets 未安装。请运行: pip install datasets") from None
    data: dict[str, list] = {
        "user_input": [p["question"] for p in qa_pairs],
        "response": [p.get("answer", "") for p in qa_pairs],
        "retrieved_contexts": [p.get("contexts", []) for p in qa_pairs],
    }
    if any(p.get("ground_truth") for p in qa_pairs):
        data["reference"] = [p.get("ground_truth", "") for p in qa_pairs]
    return Dataset.from_dict(data)
