"""Seed 客户画像默认字段 — 启动时 / 手动跑

启动时自动检测: 如果 profile_field_configs 完全为空, 插入 7 个常用默认字段.
profile_field_configs 是全局模板, 不按账号隔离, 无需关联 accounts 表.

(2026-06-23) 去掉 account_id: 字段配置是全局模板, 不按账号隔离.

用法 (CLI):
    uv run python -m scripts.seed_profile_fields

启动时 (lifespan.py 自动调 run_seed):
    from scripts.seed_profile_fields import run_seed
    run_seed()
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Windows console 默认 GBK, 强制 UTF-8 防中文乱码
if sys.platform == "win32":
    sys.__stdout__.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]  # noqa: ERA001

# alembic env.py 的同一模式: 脚本独立运行时也需要 .env.local
load_dotenv(f"{_REPO_ROOT}/.env.local", override=False)

from src.storage.session import session_scope  # noqa: E402

# 默认画像字段: code, label, field_type, extraction_prompt, options, sort_order
_DEFAULT_FIELDS = [
    {
        "code": "equipment_type",
        "label": "设备类型",
        "field_type": "text",
        "extraction_prompt": "买家需要什么设备?",
        "options": [],
        "sort_order": 1,
    },
    {
        "code": "budget",
        "label": "预算",
        "field_type": "text",
        "extraction_prompt": "买家的预算是多少?",
        "options": [],
        "sort_order": 2,
    },
    {
        "code": "decision_stage",
        "label": "决策阶段",
        "field_type": "select",
        "extraction_prompt": "买家处于哪个阶段? (询价/比价/样品/下单/售后)",
        "options": ["询价", "比价", "样品", "下单", "售后"],
        "sort_order": 3,
    },
    {
        "code": "contact_person",
        "label": "联系人",
        "field_type": "text",
        "extraction_prompt": "买家联系人姓名?",
        "options": [],
        "sort_order": 4,
    },
    {
        "code": "company",
        "label": "公司名称",
        "field_type": "text",
        "extraction_prompt": "买家所属公司?",
        "options": [],
        "sort_order": 5,
    },
    {
        "code": "country",
        "label": "国家",
        "field_type": "text",
        "extraction_prompt": "买家在哪个国家?",
        "options": [],
        "sort_order": 6,
    },
    {
        "code": "language",
        "label": "语言",
        "field_type": "text",
        "extraction_prompt": "买家使用什么语言?",
        "options": [],
        "sort_order": 7,
    },
]


def _profile_fields_empty() -> bool:
    """profile_field_configs 表是否完全为空."""
    with session_scope() as sess:
        row = sess.execute(text("SELECT 1 FROM profile_field_configs LIMIT 1")).one_or_none()
        return row is None


def run_seed() -> int:
    """Seed 默认画像字段. 返插入的字段数.

    条件: profile_field_configs 表完全为空才插入, 否则静默跳过.
    """
    if not _profile_fields_empty():
        return 0  # 已有字段, 不覆盖

    print("profile_field_configs 为空, seed 默认字段...")

    count = 0
    with session_scope() as sess:
        for f in _DEFAULT_FIELDS:
            exists = sess.execute(
                text("SELECT 1 FROM profile_field_configs WHERE code = :code LIMIT 1"),
                {"code": f["code"]},
            ).one_or_none()
            if exists is not None:
                continue
            # options 是 JSONB 列, 用 json.dumps 序列化避免 psycopg 编码问题
            sess.execute(
                text(
                    "INSERT INTO profile_field_configs "
                    "(code, label, field_type, extraction_prompt, options, sort_order) "
                    "VALUES (:code, :label, :ft, :ep, :opts, :sort)"
                ),
                {
                    "code": f["code"],
                    "label": f["label"],
                    "ft": f["field_type"],
                    "ep": f["extraction_prompt"],
                    "opts": json.dumps(f["options"]),
                    "sort": f["sort_order"],
                },
            )
            count += 1
    print(f"已 seed {count} 个画像字段")
    return count


def main() -> None:
    """CLI 入口."""
    cnt = run_seed()
    if cnt == 0:
        print("profile_field_configs 已有数据, 跳过 (运行中可 UI 修改)")
    else:
        print(f"已 seed {cnt} 个默认画像字段")


if __name__ == "__main__":
    main()
