"""buyer_profile: 买家结构化画像系统 (2026-06-22)

独立于 mem0 运行. 对话结束后 LLM 自动提取结构化画像字段,
存储在 buyer_profiles JSONB 中, 支持查询/编辑/变更通知.

模块组成:
- field_config.py: 画像字段定义 CRUD
- extractor.py:    LLM 提取引擎
- service.py:      核心业务逻辑
- change_notifier.py: 字段变更检测 + 通知
- schemas.py:      Pydantic 模型
- router.py:       HTTP 端点
"""

from .schemas import (
    BuyerProfileListResponse,
    BuyerProfileResponse,
    BuyerProfileUpdate,
    ChangeLogResponse,
    ProfileFieldConfigCreate,
    ProfileFieldConfigResponse,
    ProfileFieldConfigUpdate,
)

__all__ = [
    "BuyerProfileListResponse",
    "BuyerProfileResponse",
    "BuyerProfileUpdate",
    "ChangeLogResponse",
    "ProfileFieldConfigCreate",
    "ProfileFieldConfigResponse",
    "ProfileFieldConfigUpdate",
]
