"""Approval model + 3 enum (review/apply/reject reason) + ApprovalKind.

状态拆 2 字段 (review + apply), 跟 spec 一致.

(2026-06-19 lookup spec §3.5 迁移兼容期):
- 旧 enum 名 (ApprovalReviewStatus / ApprovalApplyStatus) 保留为 alias,
  外部仍可 `from src.approvals.models import ApprovalReviewStatus`
- 真正的 enum 成员从 `src.common.dictionaries_enum` 拉 (启动时由 yaml 编译)
- DB 是运行时事实源, yaml 是出厂种子
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.common.dictionaries_enum import (
    ApprovalApplyStatusEnum,
    ApprovalKindEnum,
    ApprovalReviewStatusEnum,
    RejectReasonEnum,
)

from ..storage import Base
from ..utils.timezone import HKT

# 旧 enum 名 (ApprovalReviewStatus / ApprovalApplyStatus / ApprovalKind / RejectReason)
# 改用 alias 引用 dictionaries_enum, 保证旧 import 路径不断.
# 外部仍可 `from src.approvals.models import ApprovalReviewStatus`,
# 拿到 ApprovalReviewStatusEnum 类, 成员 (PENDING / APPROVED / ...) 的 value 仍为原字符串.
# 注: alias 后类型标注丢失具体成员, 类内部直接用 ApprovalReviewStatusEnum 取成员.
ApprovalReviewStatus = ApprovalReviewStatusEnum
ApprovalApplyStatus = ApprovalApplyStatusEnum
ApprovalKind = ApprovalKindEnum
RejectReason = RejectReasonEnum


class Approval(Base):
    """审核项 — 1 次提交 = 1 条"""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON 字符串
    # 2 个状态轴 (关键). dictionaries_enum 已改明文 StrEnum 声明, pyright 看得到成员.
    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ApprovalReviewStatusEnum.PENDING.value,
        index=True,
    )
    apply_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ApprovalApplyStatusEnum.NONE.value,
        index=True,
    )
    submitter_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # 拒绝: 预设原因 key + 选 other 时的补充
    rejection_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 写库失败: 错误消息
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(HKT),
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_approvals_review_created", "review_status", "created_at"),
        Index("idx_approvals_apply_created", "apply_status", "created_at"),
        Index("idx_approvals_submitter_created", "submitter_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Approval id={self.id} kind={self.kind} review={self.review_status} apply={self.apply_status}>"
