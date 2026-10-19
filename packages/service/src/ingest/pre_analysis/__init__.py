"""pre_analysis 子包 — PDF 预分析模块独立化 (2026-07-06).

包内文件命名不带 `pre_analysis_` 前缀, 因为子包名承担命名空间.
后续 M2 会在此包下加 table_extractors/ 子包.
"""

from __future__ import annotations

from .models import PreAnalysisTask  # noqa: F401  # 间接供 alembic 反射 ORM
from .router import (
    pre_analysis_router,  # noqa: F401  # 路由注册用 (2026-07-06) 直接 import router 不会循环, 因为 router 不走 __init__ 重导出
)
from .runner import PreAnalysisResult, PreAnalysisRunner
from .stage_models import PreAnalysisStage  # noqa: F401  # 间接供 alembic 反射 ORM
from .stage_store import PreAnalysisStageStore
from .store import (
    PreAnalysisTaskStore,
    list_user_tasks,
    load_task,
    save_task,
)

# 同 api.py 历史用法一致: 在子包内重命名为 pa_* 别名 (legacy 调用兼容)
pa_list_user_tasks = list_user_tasks
pa_load_task = load_task
pa_save_task = save_task

__all__ = [
    "PreAnalysisTask",
    "PreAnalysisResult",
    "PreAnalysisRunner",
    "PreAnalysisStage",
    "PreAnalysisStageStore",
    "PreAnalysisTaskStore",
    "save_task",
    "load_task",
    "list_user_tasks",
    "pa_save_task",
    "pa_load_task",
    "pa_list_user_tasks",
    "pre_analysis_router",
]
