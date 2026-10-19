"""/api/health/system FastAPI router (2026-06-11)

(2026-06-17) v2 RBAC: 改用 require_super_admin guard (更严), 不再用 is_admin 派生判断.
读 in-memory cache (后台 5s 任务持续刷新).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..middleware.auth import CurrentUser
from ..permissions.guards import require_super_admin
from . import cache as _cache

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get(
    "/system",
    summary="查询系统监控状态",
    description=(
        "## 用途\n\n"
        "返回系统 5 类核心组件的聚合监控状态 (DB / MinIO / Dify / LLM / Mem0), 供管理后台的「监控」页展示.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫: 仅 super_admin 角色可访问.\n\n"
        "## 行为\n\n"
        "读 in-memory cache (后台 5s 任务持续刷新), 不阻塞当前请求. "
        "若缓存尚未填充 (启动后前 5s) 会同步计算一次首份快照."
    ),
    responses={
        200: {"description": "5 类检查的聚合结果"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin (权限不足)"},
    },
)
def health_system(_user: CurrentUser = Depends(require_super_admin)):
    return _cache.get_cached_health()
