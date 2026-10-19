"""/api/lookups/* — 字典读 API (2026-06-19 lookup spec §4.1, Task 5)

3 个 GET 端点, 任何登录用户可调:
- GET /api/lookups                    — 列出全部字典概要
- GET /api/lookups/{dict_code}        — 查单字典 + items (?only_active & ?lang)
- GET /api/lookups/{dict_code}/{key}  — 查单个 item

鉴权: 全部走 `Depends(resolve_user)`, 401 由 FastAPI 依赖层处理.
业务异常: LookupNotFoundError → 404 (字典或 item 不存在, 防 ID 探测).
约束:
- 全部 async def (跟 T4 LookupService 异步 API 一致)
- 业务走 LookupService 静态方法, router 不直接查 DB
- LookupCache 失效在写路径 (admin_router) 处理, 读路径仅消费 cache
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.lookups.exceptions import LookupNotFoundError
from src.lookups.schemas import (
    DictionaryListResponse,
    DictionaryResponse,
    LookupItemResponse,
)
from src.lookups.service import LookupService
from src.middleware.auth import CurrentUser, resolve_user

router = APIRouter(prefix="/api/lookups", tags=["lookups"])


@router.get(
    "",
    response_model=DictionaryListResponse,
    summary="列出全部字典概要",
    description=(
        "## 用途\n\n"
        "返系统全部字典的概要信息 (不含 items, 仅字典元数据), "
        "供前端初始化字典中心下拉 / 字典管理页左边栏. "
        "数据走 `LookupService.list_all_dicts` → LookupCache (L1/L2) → DB 三级回源.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫, 必须登录 (任何角色, 不限 super_admin).\n\n"
        "## 行为\n\n"
        "返 `dictionaries: [{code, label_zh, label_en, version, is_active}, ...]`. "
        "空时返 `{dictionaries: []}` (不返 404, 前端可正常拉空列表)."
    ),
    responses={
        200: {"description": "返字典概要列表 (空时 `dictionaries: []`)"},
        401: {"description": "未登录 / token 无效"},
    },
)
async def list_all_dicts(
    current_user: CurrentUser = Depends(resolve_user),  # noqa: ARG001 (鉴权守卫, 函数体未用)
):
    """列出全部字典概要 (不含 items)."""
    dicts = await LookupService.list_all_dicts()
    return {"dictionaries": dicts}


@router.get(
    "/{dict_code}",
    response_model=DictionaryResponse,
    summary="查单字典 + items",
    description=(
        "## 用途\n\n"
        "返单字典的元数据 + items 列表, 供前端渲染下拉选项 / 表格. "
        "支持 `?only_active` 过滤已弃用项, `?lang` 控制中英 label 输出.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫, 必须登录.\n\n"
        "## 行为\n\n"
        "- `?only_active=true` (默认): 只返 is_active=true 的 item, deprecated 的隐藏\n"
        "- `?only_active=false`: 含 deprecated item (供 admin UI 看历史)\n"
        "- `?lang=zh` | `en` | `both` (默认 both): 控制 label_zh/label_en 字段\n"
        "- 字典不存在 → 404, detail 含 `dictionary '<code>' not found`"
    ),
    responses={
        200: {"description": "返字典 + items"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "字典不存在"},
    },
)
async def get_dict(
    dict_code: str,
    only_active: bool = Query(True, description="是否只返 is_active=true 的 item (默认 true)"),
    lang: str = Query(
        "both",
        pattern="^(zh|en|both)$",
        description="label 语言: zh=只返 label_zh, en=只返 label_en, both=都返 (默认)",
    ),
    current_user: CurrentUser = Depends(resolve_user),  # noqa: ARG001
):
    """查单字典 + items (?only_active + ?lang)."""
    try:
        return await LookupService.get(dict_code, only_active=only_active, lang=lang)
    except LookupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/{dict_code}/{key}",
    response_model=LookupItemResponse,
    summary="查单个 item",
    description=(
        "## 用途\n\n"
        "返单个字典项 (e.g. `reject_reason/duplicate`), 供前端校验 / 单点查询.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫, 必须登录.\n\n"
        "## 行为\n\n"
        "- 字典或 item 不存在 → 404, detail 含 `dictionary '<code>' not found` "
        "或 `item '<code>:<key>' not found`\n"
        "- 不受 `?only_active` 过滤影响 (单点查询含已弃用项, 跟 spec §4.1 一致)"
    ),
    responses={
        200: {"description": "返 item"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "字典或 item 不存在"},
    },
)
async def get_one_item(
    dict_code: str,
    key: str,
    current_user: CurrentUser = Depends(resolve_user),  # noqa: ARG001
):
    """查单个 item."""
    try:
        return await LookupService.get_one(dict_code, key)
    except LookupNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
