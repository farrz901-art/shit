"""utils/timezone.py 单元测试"""

from datetime import timedelta

from src.utils.timezone import HKT


def test_hkt_offset():
    assert HKT.utcoffset(None) == timedelta(hours=8)
