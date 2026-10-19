"""Neo4j dataset label 白名单管理 (2026-07-01 markdown extract KG spec PR1, v3)

v3 设计: 项目用 Neo4j Community Edition (1 database only), 用 dataset label 隔离
不同数据集. env KG_ALLOWED_DATASETS 单源白名单, 业务侧严禁任意字符串当 label
(类似 SQL 注入防御).

为什么不走 StrEnum / lookup 字典:
- dataset 列表由 DBA 在 env 配置, 业务代码无新增需求
- env 是唯一源头, 启动时固化一次, 业务代码读模块级 ALLOWED_DATASETS
- 用 lookup 字典的话要加字典表 + 缓存失效逻辑, ROI 为负
"""

from __future__ import annotations

import os

from loguru import logger

# 模块级白名单 (启动时由 main.py 调 load_from_env() 固化)
# 业务代码严禁修改本变量, 应只读
ALLOWED_DATASETS: list[str] = []


def load_from_env(env_var: str = "KG_ALLOWED_DATASETS") -> list[str]:
    """从 env 读 comma-separated dataset 列表

    Args:
        env_var: env 变量名 (默认 KG_ALLOWED_DATASETS)
                 测试时可换名隔离

    Returns:
        list[str], 排序无关, 已 strip, 跳空 token

    默认值 "motor" 兜底: 不让无 env 启动失败, 业务侧启动后看 logger warning.
    """
    raw = os.getenv(env_var, "motor")
    datasets = [d.strip() for d in raw.split(",") if d.strip()]
    return datasets


def list_datasets() -> list[str]:
    """返模块级 ALLOWED_DATASETS snapshot

    业务侧 (router API / 前端下拉框) 调这个拿白名单, 不要读模块级变量
    避免测试隔离问题.
    """
    return list(ALLOWED_DATASETS)


def validate_dataset(dataset: str) -> None:
    """校验 dataset 在白名单内 + 是合法 Cypher identifier

    Raises:
        ValueError: 白名单外 / 非法 identifier / 空字符串

    业务侧 (KgClient 构造 / router 接收 query param) 必调本函数.
    Cypher label 注入防御: 不校验会导致 cypher 语法错或潜在注入.
    """
    if not dataset:
        raise ValueError("dataset 不能为空字符串")
    if not dataset.isidentifier():
        raise ValueError(f"Neo4j dataset label 必须是合法 identifier (字母数字下划线, 不以数字开头): {dataset!r}")
    if dataset not in ALLOWED_DATASETS:
        raise ValueError(f"Neo4j dataset label 不在白名单: {dataset!r} (allowed={ALLOWED_DATASETS})")


def bootstrap() -> list[str]:
    """main.py 启动时调一次, 固化模块级 ALLOWED_DATASETS

    同时 log INFO 让运维确认启动状态.

    Returns:
        固化的白名单 (供 main.py log 用)
    """
    global ALLOWED_DATASETS
    ALLOWED_DATASETS = load_from_env()
    logger.info("KG datasets 白名单已加载, allowed={}", ALLOWED_DATASETS)
    return ALLOWED_DATASETS
