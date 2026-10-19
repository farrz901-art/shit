"""Health check subsystem (2026-06-11)

5 个 check 函数 + 后台 5s 轮询 cache + admin-only /api/health/system 端点.
"""

from .cache import start_health_loop, stop_health_loop

__all__ = ["start_health_loop", "stop_health_loop"]
