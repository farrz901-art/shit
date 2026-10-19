"""字典模块异常 (2026-06-19 lookup spec §四 + §五)

两类:
- LookupSafetyError: SafetyGuard 拒绝时抛. code 映射 HTTP status, 5 层防御 4xx 统一表达.
- LookupNotFoundError: 字典 / item 不存在 → 404.
"""

from __future__ import annotations


class LookupSafetyError(Exception):
    """SafetyGuard 拒绝时抛. http_status 映射到 HTTP 响应码 (403/404/409/412/429).

    router 层捕获后 raise HTTPException(http_status, detail=detail).
    """

    def __init__(self, http_status: int, detail: str):
        self.http_status = http_status
        self.detail = detail
        super().__init__(detail)


class LookupNotFoundError(Exception):
    """字典 / item 不存在 → 404."""
