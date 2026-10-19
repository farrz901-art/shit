"""dictionaries_seed.yaml 加载器 (启动时 + 测试 fixture 用)

约定:
- yaml 顶级是 dictionaries 列表
- 每项有 code + items (items 可空)
- 提供 load_seed() / get_seed_dict(code) 两个入口

调用方:
- scripts/seed_dictionaries.py: 启动 seed
- src.common.dictionaries_enum (Task 3): 编译 StrEnum
- scripts.check_dictionary_refs.py (Task 7): 启动 fail-fast 校验
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import yaml


class SeedItem(TypedDict):
    """yaml 中 item 的 schema (必须字段齐, optional 字段显式声明为 None)."""

    key: str
    label_zh: str
    label_en: str
    sort: int
    description: str | None
    metadata_json: dict | None


class SeedDict(TypedDict):
    """yaml 中字典的 schema (items 列表至少为空 list)."""

    code: str
    label_zh: str
    label_en: str
    description: str | None
    items: list[SeedItem]


# yaml 路径: src/common/dictionaries_loader.py 上溯到 configs/dictionaries_seed.yaml
# (2026-06-23) 从 src/common/ 移到 config/, 跟 product_decoders 配置同层
SEED_PATH: Path = Path(__file__).resolve().parent.parent.parent / "configs" / "dictionaries_seed.yaml"


def load_seed() -> list[SeedDict]:
    """读 yaml, 返字典列表.

    空文件 / 缺 dictionaries 键 → 返 [], 不抛 (启动期不应因 yaml 缺失直接崩).
    """
    with open(SEED_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "dictionaries" not in data:
        return []
    return data["dictionaries"]


def get_seed_dict(code: str) -> SeedDict | None:
    """按 code 查单个字典, 找不到返 None.

    用于 dictionaries_enum 编译 / check_dictionary_refs 校验.
    """
    for d in load_seed():
        if d["code"] == code:
            return d
    return None
