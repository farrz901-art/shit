"""Neo4j dataset label 索引初始化 (2026-07-01 PR1, v3, M2)

用法:
    uv run python -m packages.service.scripts.init_neo4j_dataset_indexes --dataset motor  # 真跑
    uv run python -m packages.service.scripts.init_neo4j_dataset_indexes --dataset motor --dry-run  # 只 print

行为:
    读 src/kg/migrations/neo4j_init.cypher, 过滤出 CREATE INDEX for current dataset,
    --dry-run 只 print, 否则连 Neo4j 执行.

v3 设计: 不加 (label,key) 唯一约束, 因为不同 dataset 同一 key 可合法存在
(例: motor dataset 的 Product model="1LE0001" + plc dataset 的 Product model="1LE0001").
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Neo4j dataset label 索引初始化")
    parser.add_argument("--dataset", required=True, help="dataset label, 如 motor/plc/sensor")
    parser.add_argument("--dry-run", action="store_true", help="只 print cypher, 不连 Neo4j")
    args = parser.parse_args()

    ds = args.dataset
    if not ds.isidentifier():
        logger.error("dataset 必须是合法 identifier: {}", ds)
        return 1

    cypher_file = Path(__file__).resolve().parents[1] / "src" / "kg" / "migrations" / "neo4j_init.cypher"
    cypher_text = cypher_file.read_text(encoding="utf-8")
    # 按行过滤: 跳过纯注释行, 保留含 CREATE INDEX/DROP INDEX 等 DDL 行
    # 同时按 ds 子串过滤 (--dataset=motor 只返 motor_*_idx)
    ds_lower = ds.lower()
    statements = [
        line.strip()
        for line in cypher_text.splitlines()
        if line.strip()
        and not line.strip().startswith("--")
        and ds_lower in line.lower()
        and ("CREATE" in line.upper() or "DROP" in line.upper())
    ]

    if args.dry_run:
        for s in statements:
            print(s + ";")
        return 0

    # 真跑: 连 Neo4j
    from src.kg.neo4j import Neo4jStore

    store = Neo4jStore()
    for s in statements:
        logger.info("执行 cypher: {}", s[:80])
        store.execute(s, {})
    logger.info("Neo4j dataset label 索引初始化完成 (dataset={}, statements={})", ds, len(statements))
    return 0


if __name__ == "__main__":
    sys.exit(main())
