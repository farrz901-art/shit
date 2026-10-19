"""evaluation.py 单元测试"""

import pytest

from src.common.evaluation import EvaluationReport, RAGAMetrics


class TestRAGAMetrics:
    def test_default_values(self):
        m = RAGAMetrics()
        assert m.faithfulness is None
        assert m.avg_score is None

    def test_avg_score_with_values(self):
        m = RAGAMetrics(faithfulness=0.8, answer_relevancy=0.6, context_precision=0.7, context_recall=0.9)
        assert m.avg_score == pytest.approx(0.75)

    def test_avg_score_partial(self):
        m = RAGAMetrics(faithfulness=0.8, answer_relevancy=None, context_precision=None, context_recall=None)
        assert m.avg_score == 0.8

    def test_to_dict(self):
        m = RAGAMetrics(faithfulness=0.5)
        d = m.to_dict()
        assert d["faithfulness"] == 0.5
        assert "context_entity_precision" in d

    def test_summary(self):
        m = RAGAMetrics(faithfulness=0.9)
        s = m.summary()
        assert "faithfulness" in s
        assert "0.9000" in s


class TestEvaluationReport:
    def test_pass_rate_empty(self):
        report = EvaluationReport(total_samples=0, metrics=RAGAMetrics())
        assert report.pass_rate() == 0.0

    def test_pass_rate_all_pass(self):
        samples = [RAGAMetrics(faithfulness=0.8) for _ in range(3)]
        report = EvaluationReport(total_samples=3, metrics=RAGAMetrics(), per_sample_results=samples)
        assert report.pass_rate() == 1.0

    def test_pass_rate_some_pass(self):
        samples = [RAGAMetrics(faithfulness=0.8), RAGAMetrics(faithfulness=0.3)]
        report = EvaluationReport(total_samples=2, metrics=RAGAMetrics(), per_sample_results=samples)
        assert report.pass_rate() == 0.5

    def test_summary(self):
        m = RAGAMetrics(faithfulness=0.75)
        report = EvaluationReport(total_samples=5, metrics=m)
        s = report.summary()
        assert "5" in s
        assert "0.7500" in s
