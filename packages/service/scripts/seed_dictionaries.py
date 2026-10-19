"""启动 seed 脚本: 读 yaml, UPSERT 到 DB (默认不覆盖已存在 label, --force-sync 才覆盖)

新增 page_key 时自动补齐 role_permissions 行 (2026-06-23):
- 检测到新 page_key item 插入时, 自动给 admin 角色插 allowed=true, user 插 allowed=false
- 避免每次加页面单独跑 migration

用法:
  python -m scripts.seed_dictionaries               # 启动跑一次, 缺啥补啥
  python -m scripts.seed_dictionaries --force-sync  # 危险: 强制用 yaml 覆盖 DB label

设计要点 (2026-06-19 lookup spec §3.4):
- 默认 (force_sync=False) 行为: 缺啥补啥, 已有不动 (防 super_admin 后台改的 label 被覆盖)
- --force-sync: 显式把 yaml 当成"出厂配置", 覆盖 DB label (审计可追)
- 依赖: src.lookups.models (T4 才建), 用 _import() 懒加载, 本文件 import 阶段不连 DB

输出 (中文, 跟项目其他 seed 脚本保持一致):
  已 seed: 5 个新字典 + 25 个新 item
  已 seed: 0 个新字典 + 0 个新 item (force-sync)
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

# scripts/ 子目录脚本需要 sys.path 注入 src.* (跟 main.py / pytest 不一样)
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.common.dictionaries_loader import load_seed  # noqa: E402
from src.storage.session import session_scope  # noqa: E402


# 延迟 import 避免循环 (LookupService 依赖 models, models 依赖 storage; T4 才建 models)
def _import():
    """懒加载 models, 调用时若 T4 未完成会 ImportError, 预期行为."""
    from src.lookups.models import Dictionary, DictionaryItem  # type: ignore[import-not-found]  # noqa: F401

    return Dictionary, DictionaryItem


def run_seed(force_sync: bool = False) -> tuple[int, int]:
    """跑 seed, 返 (新插入字典数, 新插入 item 数).

    force_sync=False (默认): 已存在不动, 缺啥补啥
    force_sync=True: 已存在的字典/item 也会被 yaml 的 label/sort 覆盖

    兼容期 (DB 表未 migrate): 静默返 (0, 0) + print 提示跑 alembic
    """
    try:
        Dictionary, DictionaryItem = _import()
    except ImportError as e:
        print(f"[WARN] lookup models 未建 (T4 未完成): {e}")
        print("       跳过 dictionaries seed, 业务不影响 (lookup API 还没接)")
        return 0, 0

    data = load_seed()
    dict_count = 0
    item_count = 0
    perm_count = 0
    try:
        with session_scope() as s:
            for d in data:
                # UPSERT dictionary (按 code 唯一)
                existing = s.execute(select(Dictionary).where(Dictionary.code == d["code"])).scalar_one_or_none()
                if existing is None:
                    s.add(
                        Dictionary(
                            code=d["code"],
                            label_zh=d["label_zh"],
                            label_en=d["label_en"],
                            description=d.get("description"),
                        )
                    )
                    dict_count += 1
                elif force_sync:
                    # --force-sync: 用 yaml 覆盖 DB label (危险, 显式 flag)
                    existing.label_zh = d["label_zh"]
                    existing.label_en = d["label_en"]
                    if d.get("description"):
                        existing.description = d["description"]
                for item in d.get("items", []):
                    # UPSERT item (按 (dict_code, key) 唯一)
                    existing_item = s.execute(
                        select(DictionaryItem).where(
                            DictionaryItem.dict_code == d["code"],
                            DictionaryItem.key == item["key"],
                        )
                    ).scalar_one_or_none()
                    if existing_item is None:
                        s.add(
                            DictionaryItem(
                                dict_code=d["code"],
                                key=item["key"],
                                label_zh=item["label_zh"],
                                label_en=item["label_en"],
                                description=item.get("description"),
                                sort=item.get("sort", 0),
                                metadata_json=item.get("metadata_json"),
                            )
                        )
                        item_count += 1
                        # (2026-06-23) 新 page_key 自动补齐角色权限行
                        if d["code"] == "page_key":
                            if _sync_page_key_permissions(s, item["key"]):
                                perm_count += 1
                    elif force_sync:
                        # --force-sync: 覆盖 label + sort (metadata_json 不覆盖, 允许 admin 改)
                        existing_item.label_zh = item["label_zh"]
                        existing_item.label_en = item["label_en"]
                        if "sort" in item:
                            existing_item.sort = item["sort"]
    except Exception as e:
        # 表不存在 / 列不存在 / FK 错误等. 静默返 (0,0) + 提示 (兼容 dev + 升级期)
        print(f"[WARN] dictionaries seed 跳过: {type(e).__name__}: {e}")
        print("       修复: cd packages/service && uv run alembic upgrade head")
        return 0, 0
    if perm_count:
        print(f"已自动补齐 {perm_count} 个新 page_key 的 role_permissions 行")
    return dict_count, item_count


def _sync_page_key_permissions(sess, page_key: str) -> bool:
    """新 page_key 自动给 user/admin 角色插 role_permissions 行.

    user = False (默认不可见), admin = True (默认可见). super_admin 是 meta 豁免, 不入库.
    返 True 表示新插了行.
    """
    try:
        from src.permissions.models import RolePermission
    except ImportError:
        # permissions module 未建, 跳过
        return False
    # (2026-07-08) datetime.utcnow() Python 3.12+ DeprecationWarning, 改 timezone-aware
    now = datetime.now(UTC)
    inserted = False
    for role_name, allowed in [("user", False), ("admin", True)]:
        existing = sess.execute(
            select(RolePermission).where(
                RolePermission.role_name == role_name,
                RolePermission.page_key == page_key,
            )
        ).scalar_one_or_none()
        if existing is None:
            sess.add(
                RolePermission(
                    role_name=role_name,
                    page_key=page_key,
                    allowed=allowed,
                    created_at=now,
                    updated_at=now,
                )
            )
            inserted = True
    return inserted


def main():
    """CLI 入口: parse --force-sync, 跑 seed, 打印中文结果."""
    parser = argparse.ArgumentParser(description="Seed 业务字典到 DB (启动时跑)")
    parser.add_argument(
        "--force-sync",
        action="store_true",
        help="强制用 yaml 覆盖 DB label (危险, 审计可追)",
    )
    args = parser.parse_args()
    d, i = run_seed(force_sync=args.force_sync)
    suffix = " (force-sync)" if args.force_sync else ""
    print(f"已 seed: {d} 个新字典 + {i} 个新 item{suffix}")


if __name__ == "__main__":
    sys.exit(main() or 0)
