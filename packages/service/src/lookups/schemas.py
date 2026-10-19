"""字典模块 Pydantic schema (2026-06-19 lookup spec §4.6)

读 API 返参的 3 个 model, 跟 spec §4.1 一致:
- LookupItemResponse: 单个字典项
- DictionaryResponse: 单字典 + items[]
- DictionaryListResponse: 全部字典概要列表

写 API 的 4 个 model (T6 admin_router 用):
- DictionaryCreateRequest: 新建字典 body
- DictionaryPatchRequest: 改字典 metadata body
- LookupItemCreateRequest: 新增 item body
- LookupItemPatchRequest: 改 item body (含 expected_version 乐观锁)
- ConfirmTokenResponse: confirm-token 端点返参
- AuditLogEntry: 审计日志条目

约束:
- 字段命名跟 LookupService 返回 dict 完全一致 (snake_case)
- 字段 nullable 跟 SQLAlchemy model 一致 (metadata_json / effective_at /
  deprecated_at 可 None)
- 写 request 用 pattern / ge / le 严校验, 422 错误在 router 前捕获
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LookupItemResponse(BaseModel):
    """单个字典项 (对应 dictionary_items 表 1 行)"""

    model_config = ConfigDict(from_attributes=True)

    key: str = Field(..., description="枚举值, 业务代码里用的字符串 key")
    label_zh: str = Field(..., description="中文 label")
    label_en: str = Field(..., description="英文 label")
    sort: int = Field(..., description="显示顺序, 升序")
    is_active: bool = Field(..., description="项级开关: True=启用, False=已弃用")
    description: str | None = Field(default=None, description="项说明")
    metadata_json: dict | None = Field(default=None, description="扩展位 (颜色/图标/URL 等)")
    effective_at: datetime | None = Field(default=None, description="生效时间")
    deprecated_at: datetime | None = Field(default=None, description="弃用时间")


class DictionaryResponse(BaseModel):
    """单字典 (含 items 列表)"""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(..., description="字典唯一标识, e.g. 'approval_review_status'")
    label_zh: str = Field(..., description="字典中文名")
    label_en: str = Field(..., description="字典英文名")
    version: int = Field(..., description="字典 schema 版本号 (add/remove item 时 +1)")
    items: list[LookupItemResponse] = Field(
        default_factory=list, description="字典项列表 (按 sort 升序, only_active 过滤后)"
    )


class DictionarySummaryResponse(BaseModel):
    """字典概要 (不含 items, 给 GET /api/lookups 用 + 写端点返参)"""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(..., description="字典唯一标识")
    label_zh: str = Field(..., description="字典中文名")
    label_en: str = Field(..., description="字典英文名")
    version: int = Field(..., description="字典 schema 版本号")
    is_active: bool = Field(..., description="字典是否启用 (紧急下线用)")
    description: str | None = Field(default=None, description="字典说明")
    is_readonly: bool = Field(default=False, description="字典级只读")


class DictionaryListResponse(BaseModel):
    """全部字典概要列表 (GET /api/lookups 返参)"""

    dictionaries: list[DictionarySummaryResponse] = Field(default_factory=list, description="字典概要列表")


# ---- 写 API: 字典级 (T6 admin_router) ----


class DictionaryCreateRequest(BaseModel):
    """POST /api/admin/dicts body — 新建字典"""

    code: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]{1,63}$",
        description="字典 code (小写字母开头, 字母数字下划线, 2-64 字符)",
    )
    label_zh: str = Field(..., min_length=1, max_length=128, description="中文名")
    label_en: str = Field(..., min_length=1, max_length=128, description="英文名")
    description: str | None = Field(default=None, description="字典说明")


class DictionaryPatchRequest(BaseModel):
    """PATCH /api/admin/dicts/{dict_code} body — 改字典 metadata.

    code 不可改 (URL path 决定). 其他字段 nullable, None 表示不改.
    """

    label_zh: str | None = Field(default=None, min_length=1, max_length=128, description="中文名 (None=不改)")
    label_en: str | None = Field(default=None, min_length=1, max_length=128, description="英文名 (None=不改)")
    description: str | None = Field(default=None, description="字典说明 (None=不改)")
    is_active: bool | None = Field(default=None, description="字典级开关 (紧急下线用)")
    is_readonly: bool | None = Field(default=None, description="字典级只读 (比 env 细粒度)")


# ---- 写 API: item 级 (T6 admin_router) ----


class LookupItemCreateRequest(BaseModel):
    """POST /api/admin/dicts/{dict_code}/items body — 新增 item"""

    key: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]{0,63}$",
        description="枚举 key (小写字母开头, 字母数字下划线, 1-64 字符)",
    )
    label_zh: str = Field(..., min_length=1, max_length=128, description="中文 label")
    label_en: str = Field(..., min_length=1, max_length=128, description="英文 label")
    sort: int = Field(default=0, ge=0, le=9999, description="显示顺序")
    description: str | None = Field(default=None, max_length=2000, description="项说明")
    metadata_json: dict | None = Field(default=None, description="扩展位 (颜色/图标/URL 等)")


class LookupItemPatchRequest(BaseModel):
    """PATCH /api/admin/dicts/{dict_code}/items/{key} body — 改 item.

    key 不可改 (rename 需 POST 新 + migrate + DELETE 旧).
    expected_version 显式传才校验乐观锁.
    """

    label_zh: str | None = Field(default=None, min_length=1, max_length=128, description="中文 label (None=不改)")
    label_en: str | None = Field(default=None, min_length=1, max_length=128, description="英文 label (None=不改)")
    sort: int | None = Field(default=None, ge=0, le=9999, description="显示顺序 (None=不改)")
    description: str | None = Field(default=None, max_length=2000, description="项说明 (None=不改)")
    is_active: bool | None = Field(default=None, description="启用开关 (None=不改)")
    metadata_json: dict | None = Field(default=None, description="扩展元数据 (None=不改)")
    expected_version: int | None = Field(default=None, description="乐观锁, 跟服务端不一致 → 412")


# ---- Confirm Token (T6 admin_router) ----


class ConfirmTokenResponse(BaseModel):
    """POST /api/admin/dicts/confirm-token 返参 — 删除二次确认 token.

    token 1 小时有效 (sha256("<user_id>:YYYYMMDDHH")[:16]).
    前端拿到 token 后在 DELETE 请求 header X-Confirm-Token 传.
    """

    token: str = Field(..., description="16 字符 hex token, 1 小时有效 (小时桶)")
    valid_until: datetime = Field(..., description="token 失效时间 (ISO 8601, 当前小时末)")


class SoftDeleteItemResponse(BaseModel):
    """DELETE /api/admin/dicts/{code}/items/{key} 返参 — 软删结果.

    只含关键 3 字段 (key/is_active/deprecated_at), 跟 LookupItemResponse 区分.
    """

    key: str = Field(..., description="被软删的 item key")
    is_active: bool = Field(..., description="软删后永远 False")
    deprecated_at: datetime = Field(..., description="软删时间 ISO 8601")
    forced: bool = Field(default=False, description="force=true 跳过引用检查")


# ---- 审计日志 (T6 admin_router GET audit) ----


class AuditLogEntry(BaseModel):
    """GET /api/admin/dicts/{dict_code}/audit 返参 — 单条审计记录"""

    id: int = Field(..., description="audit_logs.id")
    ts: datetime = Field(..., description="变更时间")
    actor_id: int = Field(..., description="操作人 user.id")
    actor_display: str | None = Field(default=None, description="操作人 email / public_token")
    action: str = Field(..., description="e.g. 'dictionary.item.delete.forced'")
    target_id: str = Field(..., description="e.g. 'reject_reason:duplicate'")
    before: dict | None = Field(default=None, description="变更前快照")
    after: dict | None = Field(default=None, description="变更后快照")
    ip: str | None = Field(default=None, description="客户端 IP")


class AuditLogListResponse(BaseModel):
    """GET /api/admin/dicts/{dict_code}/audit 返参 — 审计列表"""

    entries: list[AuditLogEntry] = Field(default_factory=list)
    total: int = Field(default=0, description="条目数")
