"""评估 CSV 模板生成"""

from __future__ import annotations

from src.eval.template import build_eval_template_csv


def test_template_has_csv_header():
    """模板首行是表头, 含 question + ground_truth"""
    csv_text = build_eval_template_csv()
    first_line = csv_text.splitlines()[0]
    assert first_line == "question,ground_truth"


def test_template_has_at_least_one_example():
    """模板至少 1 条示例 (给用户参考格式)"""
    csv_text = build_eval_template_csv()
    lines = csv_text.strip().splitlines()
    assert len(lines) >= 2  # 表头 + 至少 1 行


def test_template_uses_utf8_encodable_chinese():
    """模板含中文示例, 能 UTF-8 编码"""
    csv_text = build_eval_template_csv()
    encoded = csv_text.encode("utf-8")
    assert b"\xe8\xa5\xbf\xe9\x97\xa8\xe5\xad\x90" in encoded  # 西门子


def test_template_is_valid_csv():
    """模板内容能被 csv.DictReader 解析"""
    import csv
    import io

    csv_text = build_eval_template_csv()
    reader = csv.DictReader(io.StringIO(csv_text))
    assert "question" in (reader.fieldnames or [])
    rows = list(reader)
    assert len(rows) >= 1
    for r in rows:
        assert r.get("question"), f"示例行 question 为空: {r}"
