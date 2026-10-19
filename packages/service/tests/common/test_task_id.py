"""task_id 生成器单测 (模式 1: 纯函数, 0 PG 依赖)"""

import re
from datetime import datetime

from src.common.task_id import (
    TASK_PREFIX_INGEST,
    TASK_PREFIX_KG_BATCH,
    TASK_PREFIX_KG_EXTRACT,
    TASK_PREFIX_PRE_ANALYSIS,
    make_task_id,
)
from src.utils.timezone import HKT

# 完整格式: {prefix}_{14位数字}_{6位hex}
_PATTERN = re.compile(r"^(pa|ig|kge|kgb)_\d{14}_[0-9a-f]{6}$")


def test_format_matches_spec():
    """pa 前缀生成结果符合 {prefix}_{YYYYMMDD}{HHMMSS}_{6hex}"""
    tid = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    assert _PATTERN.match(tid), f"格式不符: {tid}"
    assert tid.startswith("pa_")


def test_all_prefixes_wired():
    """4 个前缀常量各自拼到 ID 开头"""
    assert make_task_id(TASK_PREFIX_PRE_ANALYSIS).startswith("pa_")
    assert make_task_id(TASK_PREFIX_INGEST).startswith("ig_")
    assert make_task_id(TASK_PREFIX_KG_EXTRACT).startswith("kge_")
    assert make_task_id(TASK_PREFIX_KG_BATCH).startswith("kgb_")


def test_timestamp_parseable():
    """中间 14 位可被 strptime 解回"""
    tid = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    ts_str = tid.split("_")[1]
    parsed = datetime.strptime(ts_str, "%Y%m%d%H%M%S")  # 不抛即通过
    assert parsed.year >= 2026


def test_uses_hkt_timezone(monkeypatch):
    """时间戳用香港时区 HKT, 不用 UTC/本地"""
    fixed = datetime(2026, 7, 8, 14, 30, 12, tzinfo=HKT)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # 断言调用方确实传了 HKT
            assert tz == HKT, f"应传 HKT, 实传 {tz}"
            return fixed

    monkeypatch.setattr("src.common.task_id.datetime", _FrozenDatetime)
    tid = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    assert tid.startswith("pa_20260708143012_")


def test_uniqueness_same_second(monkeypatch):
    """同一秒内连生成随机段不同 (secrets 部分变化)"""
    fixed = datetime(2026, 7, 8, 14, 30, 12, tzinfo=HKT)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr("src.common.task_id.datetime", _FrozenDatetime)
    ids = {make_task_id(TASK_PREFIX_PRE_ANALYSIS) for _ in range(50)}
    # 时间戳全相同, 靠随机段区分; 50 个 24bit 随机基本不撞
    assert len(ids) == 50


def test_length_stable():
    """pa 前缀总长稳定 24 字符"""
    tid = make_task_id(TASK_PREFIX_PRE_ANALYSIS)
    assert len(tid) == 24  # pa(2) + _(1) + 14 + _(1) + 6 = 24
