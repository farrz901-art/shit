"""统一时区: 数据库存储用中国香港时间 (UTC+8)"""

from datetime import timedelta, timezone

# 中国香港时区 UTC+8
HKT = timezone(timedelta(hours=8))
