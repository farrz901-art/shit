"""字典 enum 镜像: 明文声明 StrEnum + 启动时校验跟 yaml 一致.

用途:
- schema Literal / 业务代码类型提示 (approvals/models.py 改从这导入)
- DB 是运行时事实源, yaml 是种子, 本文件是 pyright 友好的明文镜像
- 新增/删除 enum key 必须三处同步: yaml + 本文件 + DB seed

为什么不用 functional API (StrEnum(name, names)):
- pyright 看不到动态生成的成员 (报 70 个 reportAttributeAccessIssue)
- 改用明文 class 声明 + _verify_against_yaml() 启动校验, 防漂移

启动校验失败时抛 ValueError, fail-fast (避免下游拿到错枚举).
"""

from __future__ import annotations

from enum import StrEnum

from .dictionaries_loader import get_seed_dict

# ===== 明文 StrEnum 声明 (pyright 友好) =====


class ApprovalReviewStatusEnum(StrEnum):
    """审核 review 状态轴 (跟 yaml approval_review_status 一致)"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalApplyStatusEnum(StrEnum):
    """审核 apply (写入 Dify/Neo4j) 状态轴 (跟 yaml approval_apply_status 一致)"""

    NONE = "none"
    APPLIED = "applied"
    FAILED = "failed"


class ApprovalKindEnum(StrEnum):
    """审核类型 (跟 yaml approval_kind 一致)"""

    QA = "qa"
    TRIPLE = "triple"
    BATCH = "batch"
    OPTIMIZE = "optimize"
    LIKE = "like"


class RejectReasonEnum(StrEnum):
    """拒绝原因 (跟 yaml reject_reason 一致)"""

    DUPLICATE = "duplicate"
    LOW_QUALITY = "low_quality"
    INCOMPLETE = "incomplete"
    WRONG_CATEGORY = "wrong_category"
    FORMAT_ISSUE = "format_issue"
    OTHER = "other"


class PageKeyEnum(StrEnum):
    """页面权限 key (跟 yaml page_key 一致)"""

    ADMIN = "admin"
    CHAT = "chat"
    OUTPUT = "output"
    KNOWLEDGE = "knowledge"
    EVALUATE = "evaluate"
    SUBMISSIONS = "submissions"
    DECODE = "decode"
    HEALTH = "health"
    BUYERS = "buyers"
    KNOWLEDGE_EXTRACT = "knowledge_extract"
    ADMIN_USERS = "admin_users"
    ADMIN_INVITES = "admin_invites"
    ADMIN_PERMISSIONS = "admin_permissions"
    ADMIN_DICTS = "admin_dicts"
    ADMIN_PROFILE_FIELDS = "admin_profile_fields"
    ADMIN_PRE_ANALYSIS = "admin_pre_analysis"


# ===== 启动校验: enum 跟 yaml 必须 1:1 一致 =====


def _verify_against_yaml(enum_cls: type[StrEnum], code: str) -> None:
    """校验 enum 成员 == yaml items 的 key 集合 (1:1 严格一致)

    任何漂移 (yaml 加新 key 没改 enum, 或反之) 抛 ValueError, 启动 fail-fast.
    """
    d = get_seed_dict(code)
    if d is None:
        raise ValueError(f"seed yaml 找不到字典: {code}")
    yaml_keys = {item["key"] for item in d.get("items", [])}
    enum_keys = {e.value for e in enum_cls}
    if yaml_keys != enum_keys:
        missing_in_enum = yaml_keys - enum_keys
        missing_in_yaml = enum_keys - yaml_keys
        msg = f"字典 {code} 漂移:"
        if missing_in_enum:
            msg += f" yaml 有但 enum 缺={missing_in_enum}"
        if missing_in_yaml:
            msg += f" enum 有但 yaml 缺={missing_in_yaml}"
        raise ValueError(msg)


# 启动时跑一次 (import 时即触发, 漂移即崩)
_verify_against_yaml(ApprovalReviewStatusEnum, "approval_review_status")
_verify_against_yaml(ApprovalApplyStatusEnum, "approval_apply_status")
_verify_against_yaml(ApprovalKindEnum, "approval_kind")
_verify_against_yaml(RejectReasonEnum, "reject_reason")
_verify_against_yaml(PageKeyEnum, "page_key")


# ===== ENUM_REGISTRY: enum 类名 → dict_code =====
# 供 check_dictionary_refs.py 启动校验 enum ⊆ DB items
ENUM_REGISTRY: dict[str, str] = {
    "ApprovalReviewStatusEnum": "approval_review_status",
    "ApprovalApplyStatusEnum": "approval_apply_status",
    "ApprovalKindEnum": "approval_kind",
    "RejectReasonEnum": "reject_reason",
    "PageKeyEnum": "page_key",
}


__all__ = [
    "ENUM_REGISTRY",
    "ApprovalApplyStatusEnum",
    "ApprovalKindEnum",
    "ApprovalReviewStatusEnum",
    "PageKeyEnum",
    "RejectReasonEnum",
]
