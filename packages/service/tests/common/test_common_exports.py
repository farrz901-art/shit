"""common 子包导出测试"""


def test_chunk_documents_exported():
    from src.common import chunk_documents

    assert callable(chunk_documents)


def test_load_md_files_exported():
    from src.common import load_md_files

    assert callable(load_md_files)


def test_estimate_tokens_exported():
    from src.common import estimate_tokens

    assert estimate_tokens("hello") >= 1


def test_truncate_text_exported():
    from src.common import truncate_text

    assert truncate_text("hello", 10) == "hello"


def test_RAGAMetrics_exported():
    from src.common import RAGAMetrics

    m = RAGAMetrics(faithfulness=0.9)
    assert m.faithfulness == 0.9


def test_EvaluationReport_exported():
    from src.common import EvaluationReport, RAGAMetrics

    report = EvaluationReport(total_samples=1, metrics=RAGAMetrics(faithfulness=0.9))
    assert report.total_samples == 1
