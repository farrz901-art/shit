"""禁止 raw SQL INSERT/UPDATE jsonb 列时传裸 :param (json-jsonb spec Task C2).

测试模式 1 (mock, regex): 0 PG 依赖.

扫 src/ 下所有 .py, 找 text("INSERT/UPDATE ... :ctx|:meta|:before|:after|:context|:metadata|:payload"),
断言上下文 (前后 5 行) 含 CAST / ::jsonb / bindparam(.*JSONB) / json.dumps(.

不是 100% 严密 (regex 静态扫), 但能拦最常见的 "裸传 dict" 模式.
"""

from __future__ import annotations

import re
from pathlib import Path

# JSONB 列名族 (项目里 JSONB 列的典型命名)
JSONB_COL_NAMES = ("ctx", "context", "meta", "metadata", "before", "after", "payload", "merge", "data")

# 安全模式 (出现任一即放过)
SAFE_PATTERNS = [
    re.compile(r"CAST\s*\(\s*:[a-z_]+\s+AS\s+jsonb\s*\)", re.IGNORECASE),  # CAST(:p AS jsonb)
    re.compile(r"::jsonb\b"),  # :p::jsonb / col::jsonb
    re.compile(r"bindparam\s*\(\s*[\"'][a-z_]+[\"']\s*,\s*type_\s*=\s*JSONB"),  # bindparam("p", type_=JSONB)
    re.compile(r"json\.dumps\s*\("),  # 预序列化为字符串再传
]


def _src_dir() -> Path:
    return Path(__file__).parent.parent.parent / "src"


def _scan_file_for_jsonb_writes(py: Path) -> list[tuple[int, str, str]]:
    """返回 [(lineno, line, neighborhood)] 命中需要检查的位置."""
    text = py.read_text(encoding="utf-8")
    lines = text.splitlines()
    hits: list[tuple[int, str, str]] = []

    # 找含 INSERT/UPDATE + JSONB 列名族 + :param 的位置
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not re.search(r"\bINSERT\b", stripped, re.IGNORECASE) and not re.search(
            r"\bUPDATE\b", stripped, re.IGNORECASE
        ):
            continue
        for col in JSONB_COL_NAMES:
            # 简陋判断 = SQL 里出现该列名 (作为列名引用)
            if re.search(rf"\b{re.escape(col)}\b", line):
                # 看上下文 ±10 行内有没有 :param 跟这列绑
                start = max(0, i - 10)
                end = min(len(lines), i + 11)
                neighborhood = "\n".join(lines[start:end])
                if re.search(r":[a-z_]+", neighborhood):
                    hits.append((i + 1, line.strip(), neighborhood))
                break  # 一条 SQL 一行只看一次
    return hits


def test_jsonb_raw_sql_writes_have_cast_or_bindparam():
    """所有 raw SQL 写 JSONB 列的位置, 必须有 CAST/::jsonb/bindparam JSONB/json.dumps."""
    src = _src_dir()
    assert src.exists()

    violations: list[str] = []
    for py in src.rglob("*.py"):
        if "__pycache__" in py.parts or "tests" in py.parts:
            continue
        hits = _scan_file_for_jsonb_writes(py)
        for lineno, line, neighborhood in hits:
            # 上下文里命中任一安全模式 → 放过
            if any(p.search(neighborhood) for p in SAFE_PATTERNS):
                continue
            rel = py.relative_to(src.parent.parent.parent)
            violations.append(
                f"{rel}:{lineno} 写 JSONB 列裸 :param, 缺 CAST/::jsonb/bindparam JSONB/json.dumps\n  {line}"
            )

    assert not violations, "\n\n".join(violations)
