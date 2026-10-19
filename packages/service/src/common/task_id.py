"""任务 ID 统一生成: {prefix}_{YYYYMMDD}{HHMMSS}_{6hex}

散落各处的 uuid.uuid4().hex[:12] 无可读性, 本模块提供唯一中央生成器.
所有任务型 ID (pre_analysis / ingest / kg) 必须走 make_task_id, 禁止 inline 生成.
"""

import secrets
from datetime import datetime

from src.utils.timezone import HKT

# 任务类型前缀常量 (唯一事实源, 调用方勿传字面量)
TASK_PREFIX_PRE_ANALYSIS = "pa"
TASK_PREFIX_INGEST = "ig"
TASK_PREFIX_KG_EXTRACT = "kge"
TASK_PREFIX_KG_BATCH = "kgb"


def make_task_id(prefix: str) -> str:
    """生成可读任务 ID: {prefix}_{YYYYMMDD}{HHMMSS}_{6hex}

    入参:
        prefix: 类型前缀, 用本模块 TASK_PREFIX_* 常量 (勿传字面量)
    回参:
        str, 例 'pa_20260708143012_a1b2c3' (pa 前缀时 24 字符)
    """
    # 香港时区时间戳, 跟 DB 存储一致; 14 位可读又可字典序排序
    ts = datetime.now(HKT).strftime("%Y%m%d%H%M%S")
    # 24 bit 随机, 同秒内防碰撞
    rand = secrets.token_hex(3)
    return f"{prefix}_{ts}_{rand}"
