"""init_neo4j_dataset_indexes 单元测试 (2026-07-01 PR1, v3)

不走 subprocess (避免 ModuleNotFoundError), 直接 import main() 调 sys.argv mock
"""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest


def test_init_neo4j_dataset_indexes_dry_run_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    """dry-run 必 print motor 索引 cypher, 不连 Neo4j"""
    from scripts.init_neo4j_dataset_indexes import main

    monkeypatch.setattr(sys, "argv", ["init", "--dataset", "motor", "--dry-run"])
    out = io.StringIO()
    with redirect_stdout(out):
        rc = main()
    assert rc == 0
    stdout = out.getvalue()
    assert "CREATE INDEX" in stdout
    assert "Motor" in stdout
    # v3: 不应该包含 (label,key) 唯一约束
    assert "CREATE CONSTRAINT" not in stdout.upper()


def test_init_neo4j_dataset_indexes_rejects_invalid_dataset() -> None:
    """非 identifier dataset → 退出码非 0"""
    from scripts.init_neo4j_dataset_indexes import main

    old_argv = sys.argv
    sys.argv = ["init", "--dataset", "1bad-dataset", "--dry-run"]
    try:
        rc = main()
    except SystemExit:
        rc = 1
    finally:
        sys.argv = old_argv
    assert rc != 0


def test_init_neo4j_dataset_indexes_filters_by_dataset() -> None:
    """--dataset=motor 只返 motor 索引, 不含 plc / sensor

    直接读 cypher 文件, 模仿 main() 内部 filter 逻辑验证
    """
    # tests/kg/<name>.py → parents[2] = packages/service
    cypher_file = Path(__file__).resolve().parents[2] / "src" / "kg" / "migrations" / "neo4j_init.cypher"
    text = cypher_file.read_text(encoding="utf-8")
    ds = "motor"
    ds_lower = ds.lower()

    statements = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and not line.strip().startswith("--")
        and ds_lower in line.lower()
        and ("CREATE" in line.upper() or "DROP" in line.upper())
    ]
    # 4 条 motor 索引 (Product / Spec / Series / Standard)
    assert len(statements) == 4, f"expected 4 motor indexes, got {len(statements)}: {statements}"
    assert "motor_product_idx" in "\n".join(statements)
    # plc / sensor 不应出现
    joined = "\n".join(statements)
    assert "plc_product_idx" not in joined
    assert "sensor_product_idx" not in joined
