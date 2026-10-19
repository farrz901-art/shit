"""启动时一致性校验: yaml 字典 ⊆ DB 字典, enum 镜像值 ⊆ DB items (2026-06-19 lookup spec §7.2)

校验 3 件事:
1. yaml 字典 (configs/dictionaries_seed.yaml) ⊆ DB 字典
   (DB 是超集, yaml 是种子, DB 缺 yaml 字典 → seed 没跑过, 启动 fail-fast)
2. ENUM_REGISTRY (dictionaries_enum 暴露的 enum 类 → dict_code 映射) 每个 enum 类的 value ⊆ DB items
   (enum 是启动期类型提示 + 反向校验, DB 缺 enum 值 → yaml 拼错, 启动 fail-fast)
3. ENUM_REGISTRY 指向的 dict_code 必须存在 (否则 dict 没 seed 进 DB)

设计:
- check_consistency_async() 内部直接 await async LookupService (供 FastAPI lifespan / main.py 调)
- check_consistency() 是同步入口, 内部用 asyncio.run 调 async 版 (供 CLI / 测试调)
- 测试 mock LookupService.list_all_dicts / LookupService.get, 用 AsyncMock 替换,
  调用 async 版用 asyncio.run 也能正常调度返 mock 值
- 不一致 raise RuntimeError, 启动 fail-fast

用法:
  python -m scripts.check_dictionary_refs         # CLI: 校验 + 打印结果, 失败 exit 1
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

# scripts/ 子目录脚本需要 sys.path 注入 src.* (跟 main.py 不一样, main.py 走包路径自动)
# 项目约定: packages/service/scripts/*.py 顶部加 _ensure_src_on_path 即可
_SRC_PARENT = str(Path(__file__).resolve().parent.parent)
if _SRC_PARENT not in sys.path:
    sys.path.insert(0, _SRC_PARENT)

from src.common.dictionaries_enum import ENUM_REGISTRY  # noqa: E402
from src.common.dictionaries_loader import load_seed  # noqa: E402


async def _fetch_db_dicts_async():
    """从 LookupService.list_all_dicts() 拉全部字典 code 列表 (async 入口).

    LookupService.list_all_dicts 是 async, 内部走 Redis L2 → DB.
    失败 (LookupService 没注册 / Redis 挂) 抛异常, 调用方决定如何处理.

    (2026-06-23) 拆出 async 版: FastAPI lifespan 在 running event loop 里,
    不能再用 asyncio.run 包同步入口 (RuntimeError: cannot be called from a running loop).
    """
    from src.lookups.service import LookupService

    return await LookupService.list_all_dicts()


async def _fetch_db_items_async(dict_code: str, only_active: bool = True):
    """从 LookupService.get(code) 拉字典 + items (async 入口)."""
    from src.lookups.service import LookupService

    return await LookupService.get(dict_code, only_active=only_active)


async def check_consistency_async() -> None:
    """启动时 fail-fast 校验: yaml ⊆ DB, enum ⊆ DB. (async 版)

    供 FastAPI lifespan / main.py 在已有 event loop 上下文里调, 不会触发
    'asyncio.run() cannot be called from a running event loop' 错误.

    Raises:
        RuntimeError: 不一致时抛, 启动失败.
    """
    # ---- 1. yaml 字典 ⊆ DB 字典 ----
    yaml_dicts = {d["code"] for d in load_seed()}
    db_dicts_summary = await _fetch_db_dicts_async()
    db_dicts = {d["code"] for d in db_dicts_summary}
    missing = yaml_dicts - db_dicts
    if missing:
        raise RuntimeError(f"DB missing dictionaries: {sorted(missing)}. 运行: python -m scripts.seed_dictionaries")

    # ---- 2 & 3. ENUM_REGISTRY 每个 enum 类的 value ⊆ DB items, dict_code 必须存在 ----
    enums_module = importlib.import_module("src.common.dictionaries_enum")
    for enum_name, dict_code in ENUM_REGISTRY.items():
        try:
            d = await _fetch_db_items_async(dict_code, only_active=False)
        except Exception as e:
            # 字典没 seed / LookupNotFoundError / Redis 挂
            raise RuntimeError(f"ENUM_REGISTRY 指向的字典 '{dict_code}' 无法读取 (enum={enum_name}): {e}") from e
        db_keys = {item["key"] for item in d.get("items", [])}
        enum_cls = getattr(enums_module, enum_name)
        enum_keys = {e.value for e in enum_cls}
        if not enum_keys.issubset(db_keys):
            extra = enum_keys - db_keys
            raise RuntimeError(
                f"enum {enum_name} (dict_code={dict_code}) 有 yaml 中存在但 DB 缺失的 keys: {sorted(extra)}. "
                f"运行: python -m scripts.seed_dictionaries"
            )


def check_consistency() -> None:
    """启动时 fail-fast 校验: yaml ⊆ DB, enum ⊆ DB. (同步版, 内部 asyncio.run)

    CLI 入口 / 测试同步场景用. 在已有 event loop 里调会 RuntimeError
    ('asyncio.run() cannot be called from a running event loop'),
    那种场景请用 check_consistency_async().

    Raises:
        RuntimeError: 不一致时抛, 启动失败.
    """
    asyncio.run(check_consistency_async())


def main() -> int:
    """CLI 入口: 跑 check_consistency, 打印中文结果, 失败 exit 1."""
    try:
        check_consistency()
        print("字典一致性校验通过 (yaml ⊆ DB, enum ⊆ DB items)")
        return 0
    except RuntimeError as e:
        print(f"字典一致性校验失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
