"""字典 enum 镜像测试: 验证 5 个 enum 的 value/成员/registry 都跟 yaml 对得上.

模式 1 (mock): 不连 PG/Redis, 直接 import 编译产物.
跟 T1/T2 test 一致, 10ms/test 跑完.
"""

from __future__ import annotations

import pytest

from src.common.dictionaries_enum import (
    ENUM_REGISTRY,
    ApprovalApplyStatusEnum,
    ApprovalKindEnum,
    ApprovalReviewStatusEnum,
    PageKeyEnum,
    RejectReasonEnum,
    _verify_against_yaml,
)


def test_enum_values_match_yaml_approval_review_status():
    """ApprovalReviewStatusEnum 3 个值 = yaml 里的 3 个 key."""
    assert {e.value for e in ApprovalReviewStatusEnum} == {"pending", "approved", "rejected"}
    # 同时校验 member name (UPPER) 跟 value 映射对得上
    assert ApprovalReviewStatusEnum.PENDING.value == "pending"
    assert ApprovalReviewStatusEnum.APPROVED.value == "approved"
    assert ApprovalReviewStatusEnum.REJECTED.value == "rejected"


def test_enum_values_match_yaml_approval_apply_status():
    """ApprovalApplyStatusEnum 3 个值 = yaml 里的 3 个 key."""
    assert {e.value for e in ApprovalApplyStatusEnum} == {"none", "applied", "failed"}
    assert ApprovalApplyStatusEnum.NONE.value == "none"
    assert ApprovalApplyStatusEnum.APPLIED.value == "applied"
    assert ApprovalApplyStatusEnum.FAILED.value == "failed"


def test_enum_values_match_yaml_approval_kind():
    """ApprovalKindEnum 5 个值 = yaml 里的 5 个 key."""
    assert {e.value for e in ApprovalKindEnum} == {"qa", "triple", "batch", "optimize", "like"}


def test_enum_values_match_yaml_reject_reason():
    """RejectReasonEnum 6 个值 = yaml 里的 6 个 key."""
    assert {e.value for e in RejectReasonEnum} == {
        "duplicate",
        "low_quality",
        "incomplete",
        "wrong_category",
        "format_issue",
        "other",
    }


def test_enum_values_match_yaml_page_key():
    """PageKeyEnum 值 ⊆ yaml page_key 字典 items.key. 加 page 时同步两处.

    (2026-06-23) 不再硬编码 8 个 page key 期望, 改用 yaml 实际值 (get_seed_dict)
    + 双向 subset 校验: 加 page 只需在 yaml + enum 各加一处, test 自动 catch 一处漏加.
    """
    from src.common.dictionaries_loader import get_seed_dict

    page_key_dict = get_seed_dict("page_key")
    assert page_key_dict is not None, "yaml page_key 字典不存在"
    yaml_page_keys = {item["key"] for item in page_key_dict["items"]}
    enum_keys = {e.value for e in PageKeyEnum}
    assert enum_keys.issubset(yaml_page_keys), f"enum 多出 yaml 没有的 page: {enum_keys - yaml_page_keys}"
    assert yaml_page_keys.issubset(enum_keys), f"yaml 多出 enum 没覆盖的 page: {yaml_page_keys - enum_keys}"


def test_enum_is_str_subclass():
    """StrEnum 必须可当 str 用 (Pydantic / JSON 序列化兼容)."""
    # 直接 == 比较
    assert ApprovalReviewStatusEnum.PENDING == "pending"
    assert ApprovalReviewStatusEnum.REJECTED == "rejected"
    # 拼字符串 (str 子类)
    assert f"status={ApprovalReviewStatusEnum.PENDING}" == "status=pending"
    # isinstance 校验
    assert isinstance(ApprovalReviewStatusEnum.PENDING, str)


def test_enum_registry_keys_present():
    """ENUM_REGISTRY 含 5 个 enum_name, 跟规范一致."""
    expected = {
        "ApprovalReviewStatusEnum",
        "ApprovalApplyStatusEnum",
        "ApprovalKindEnum",
        "RejectReasonEnum",
        "PageKeyEnum",
    }
    assert set(ENUM_REGISTRY.keys()) == expected


def test_enum_registry_values_match_dict_codes():
    """ENUM_REGISTRY value 跟 yaml dict_code 一一对应 (供 check_dictionary_refs 用)."""
    assert ENUM_REGISTRY["ApprovalReviewStatusEnum"] == "approval_review_status"
    assert ENUM_REGISTRY["ApprovalApplyStatusEnum"] == "approval_apply_status"
    assert ENUM_REGISTRY["ApprovalKindEnum"] == "approval_kind"
    assert ENUM_REGISTRY["RejectReasonEnum"] == "reject_reason"
    assert ENUM_REGISTRY["PageKeyEnum"] == "page_key"


def test_enum_names_match_class_names():
    """ENUM_REGISTRY 的 key 跟模块里实际类名一致 (防改名/漏改)."""
    import src.common.dictionaries_enum as mod

    for enum_name in ENUM_REGISTRY:
        assert hasattr(mod, enum_name), f"模块缺 {enum_name}"
        cls = getattr(mod, enum_name)
        # 验证是 StrEnum 子类
        from enum import StrEnum as _StrEnum

        assert isinstance(cls, type) and issubclass(cls, _StrEnum)


def test_verify_against_yaml_raises_for_missing_code():
    """_verify_against_yaml 对不存在的 code 抛 ValueError (fail-fast, yaml 拼错立即发现)."""
    with pytest.raises(ValueError, match="找不到字典"):
        _verify_against_yaml(ApprovalReviewStatusEnum, "nonexistent_dict_code_xyz")


def test_all_enum_values_unique():
    """防御: 5 个 enum 的 value 互相不能撞 (虽然 enum 间不冲突, 但兜底).

    (2026-06-23) 不再硬编码 3+3+5+6+8=25, 改动态算 (yaml 里每个 dict 的 items 数).
    加 enum value 时不需要改 test.
    """
    from src.common.dictionaries_loader import get_seed_dict

    all_enum_values = (
        {e.value for e in ApprovalReviewStatusEnum}
        | {e.value for e in ApprovalApplyStatusEnum}
        | {e.value for e in ApprovalKindEnum}
        | {e.value for e in RejectReasonEnum}
        | {e.value for e in PageKeyEnum}
    )
    # yaml 里 5 个字典的 items 总数 = 期望值
    expected_total = 0
    for code in ENUM_REGISTRY.values():
        d = get_seed_dict(code)
        assert d is not None, f"yaml 缺字典: {code}"
        expected_total += len(d["items"])
    assert len(all_enum_values) == expected_total
    # 5 个 enum value 互不重叠
    assert len(all_enum_values) == (
        len({e.value for e in ApprovalReviewStatusEnum})
        + len({e.value for e in ApprovalApplyStatusEnum})
        + len({e.value for e in ApprovalKindEnum})
        + len({e.value for e in RejectReasonEnum})
        + len({e.value for e in PageKeyEnum})
    )
