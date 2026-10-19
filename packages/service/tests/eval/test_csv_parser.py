"""CSV 评估集解析 / 校验"""

from __future__ import annotations

import pytest

from src.eval.csv_parser import CSVParsingError, parse_eval_csv


def test_parse_valid_csv_with_ground_truth():
    """标准 CSV: question + ground_truth, 全部非空"""
    content = b"question,ground_truth\n1LE0001,siemens\n3RT2026,contactor\n"
    rows = parse_eval_csv(content, filename="test.csv")
    assert len(rows) == 2
    assert rows[0] == {"question": "1LE0001", "ground_truth": "siemens"}


def test_parse_valid_csv_without_ground_truth():
    """question 列必填, ground_truth 可选"""
    content = b"question\nq1\nq2\n"
    rows = parse_eval_csv(content, filename="t.csv")
    assert len(rows) == 2
    assert rows[0] == {"question": "q1", "ground_truth": None}


def test_parse_rejects_missing_question_column():
    """没有 question 列 → 报错"""
    content = b"prompt,answer\nq1,a1\n"
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="bad.csv")
    assert "question" in str(exc.value)


def test_parse_rejects_empty_question():
    """某行 question 是空串 → 报错 (行号提示)"""
    content = b"question,ground_truth\nq1,ok\n,q2\n"
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="bad.csv")
    assert "第 3 行" in str(exc.value)


def test_parse_rejects_oversize_file():
    """> 5MB → 报错"""
    content = b"question\n" + b"x" * (5 * 1024 * 1024 + 1) + b"\n"
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="big.csv")
    assert "5MB" in str(exc.value)


def test_parse_rejects_too_many_rows():
    """> 200 行 → 报错"""
    content = "question\n" + "\n".join(f"q{i}" for i in range(201))
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content.encode("utf-8"), filename="huge.csv")
    assert "200" in str(exc.value)


def test_parse_rejects_too_few_rows():
    """0 行 (只有表头) → 报错"""
    content = b"question,ground_truth\n"
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="empty.csv")
    assert "1" in str(exc.value)  # "至少 1 行"


def test_parse_rejects_bad_encoding():
    """非 UTF-8 → 报错"""
    content = b"question\n\xb1\xfe"  # 非法 UTF-8 序列
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="gbk.csv")
    assert "UTF-8" in str(exc.value)


def test_parse_strips_whitespace():
    """question 周围空白自动 trim"""
    content = b"question\n  q1  \nq2\t\n"
    rows = parse_eval_csv(content, filename="t.csv")
    assert rows[0]["question"] == "q1"
    assert rows[1]["question"] == "q2"
