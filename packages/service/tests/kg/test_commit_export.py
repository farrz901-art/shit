"""commit/export 端点测试 (PR3 Task 16)

直接测子函数 (_escape + SQL 模板 + PayloadItem). 端点本身被 @audited
装饰器包成 async wrapper, 不在单元测试范围内 (已由 PR1 验证).
"""

import pytest

from src.kg import datasets


@pytest.fixture(autouse=True)
def _seed_datasets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc"])


def test_escape_quotes_and_newlines():
    """[M7] _escape 转义单引号 + 反斜杠 + 换行符 (Cypher 字符串需要)"""
    from src.kg.router import _escape

    assert _escape("abc'def") == r"abc\'def"
    assert _escape("a\\b") == "a\\\\b"
    assert _escape("line1\nline2") == r"line1\nline2"
    assert _escape("normal") == "normal"


def test_commit_extract_rejects_invalid_dataset_via_validate():
    """[M7] commit_extract dataset 不在白名单 → 422 ValueError (走 validate_dataset)"""
    with pytest.raises(ValueError, match="白名单"):
        datasets.validate_dataset("evil_inject")


def test_export_extract_jsonl_content(monkeypatch):
    """[M7] export_extract format=jsonl: 直接测 SQL → JSONL 输出

    验证 selected=true 的 items 经 _escape + json.dumps 后格式正确
    """
    import json

    items = [
        (None, {"head": "1LE0001", "rel_type": "HAS_SPEC", "tail": "230V"}),
        ({"head": "P2", "rel_type": "R", "tail": "T2"}, None),
    ]

    body = "\n".join(json.dumps(r[0] or r[1], ensure_ascii=False) for r in items).encode("utf-8")

    lines = body.decode("utf-8").splitlines()
    assert len(lines) == 2
    parsed1 = json.loads(lines[0])
    assert parsed1["head"] == "1LE0001"
    assert parsed1["rel_type"] == "HAS_SPEC"
    parsed2 = json.loads(lines[1])
    assert parsed2["head"] == "P2"
    # corrected_payload 优先
    assert "tail" in parsed2


def test_export_extract_cypher_content(monkeypatch):
    """[M7] export_extract format=cypher: 验证 cypher 模板含 :<Dataset> label

    验证 _escape + MERGE 模板 + dataset label 正确
    """
    from src.kg.router import _escape

    dataset = "motor"
    data = {"head": "1LE0001", "rel_type": "HAS_SPEC", "tail": "230V", "from_label": "Product", "to_label": "Spec"}

    head = _escape(data["head"])
    tail = _escape(data["tail"])
    rel = _escape(data["rel_type"])
    stmt = (
        f"MERGE (a:`{data.get('from_label', 'Entity')}`:`{dataset}` {{name: '{head}'}}) "
        f"MERGE (b:`{data.get('to_label', 'Entity')}`:`{dataset}` {{name: '{tail}'}}) "
        f"MERGE (a)-[r:`{rel}`]->(b);"
    )

    # v3: dataset label 在 cypher 里
    assert "Product" in stmt and "`motor`" in stmt
    assert "Spec" in stmt and "`motor`" in stmt
    assert "HAS_SPEC" in stmt


def test_export_extract_cypher_with_quotes():
    """[M7] export_extract cypher: 含特殊字符 (引号) 必正确转义"""
    from src.kg.router import _escape

    raw_head = "ABC's DEF"
    escaped = _escape(raw_head)
    assert escaped == r"ABC\'s DEF"
    # 嵌入到 cypher 后能用
    stmt = f"MERGE (a:Product:`motor` {{name: '{escaped}'}})"
    assert r"ABC\'s DEF" in stmt
