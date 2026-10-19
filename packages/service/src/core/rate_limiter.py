"""IP 限流 (2026-06-18 redis spec §5.3)

login 5 次/15min, reset_password 3 次/1h, dict_admin 60 次/1min (2026-06-19 lookup spec §四).
- login / reset: 按 IP 维度 (防爆破)
- dict_admin: 按 user.id 维度 (super_admin CRUD 字典, 防止 admin 自己刷爆 DB)
Redis 挂时 fail-open (放行, 不阻断请求).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from loguru import logger

from .redis_client import safe_incr


@dataclass(frozen=True)
class RateLimitRule:
    """单条限流规则. frozen=True 防运行期误改."""

    name: str
    window_seconds: int
    threshold: int


# 默认规则 (env 可覆盖)
RULES: dict[str, RateLimitRule] = {
    "login": RateLimitRule(
        name="login",
        window_seconds=int(os.getenv("RL_LOGIN_WINDOW", "900")),  # 15min
        threshold=int(os.getenv("RL_LOGIN_THRESHOLD", "5")),
    ),
    "forgot_password": RateLimitRule(
        name="forgot_password",
        window_seconds=int(os.getenv("RL_FORGOT_PASSWORD_WINDOW", "900")),  # 15min
        threshold=int(os.getenv("RL_FORGOT_PASSWORD_THRESHOLD", "5")),
    ),
    "reset": RateLimitRule(
        name="reset",
        window_seconds=int(os.getenv("RL_RESET_WINDOW", "3600")),  # 1h
        threshold=int(os.getenv("RL_RESET_THRESHOLD", "3")),
    ),
    # (2026-06-19 lookup spec §四/§五) dict_admin: super_admin 字典 CRUD 限流, 60/min/user.
    # 注意: 用 user.id 作 key (不是 IP), 因为字典管理可能从多 IP 触发但应按账号计.
    # rate_limiter 的 _key() 会拼成 rag:rl:dict_admin:<id>, Redis 挂了 fail-open.
    "dict_admin": RateLimitRule(
        name="dict_admin",
        window_seconds=int(os.getenv("RL_DICT_ADMIN_WINDOW", "60")),  # 1min
        threshold=int(os.getenv("RL_DICT_ADMIN_THRESHOLD", "60")),
    ),
}


def _key(op: str, ip: str) -> str:
    """拼 Redis key: rag:rl:{op}:{ip}"""
    return f"rag:rl:{op}:{ip}"


async def check_and_increment(op: str, ip: str) -> tuple[bool, int]:
    """检查 + 递增计数. 返 (allowed, current_count).

    Args:
        op: 操作名, 必须命中 RULES 的 key (login / reset)
        ip: 客户端 IP, 通常 request.client.host

    Returns:
        (allowed, current_count)
        - allowed=True: 未超阈值, 放行
        - allowed=False: 超阈值, 业务侧应返 429
        - count: 当前计数 (含本次)

    Fail-open: Redis 挂 → allowed=True (放行, 宁可被拤不要拒服务).
    """
    rule = RULES.get(op)
    if rule is None:
        logger.warning("rate limit rule 不存在 op={}", op)
        return True, 0

    key = _key(op, ip)
    count = await safe_incr(key, ex_seconds=rule.window_seconds)
    if count is None:
        return True, 0  # fail-open (Redis 挂)
    if count > rule.threshold:
        return False, count
    return True, count
