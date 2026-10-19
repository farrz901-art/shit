"""Dictionary / DictionaryItem SQLAlchemy 模型 (2026-06-19 lookup spec §3.1)

- dictionaries: 字典定义 (一行 = 一个字典, code 是 PK).
- dictionary_items: 字典项 (一行 = 一个枚举值, UNIQUE(dict_code, key) 约束).

跟 spec §3.1 一致; 索引 / 约束由 Alembic migration 20260619_120000 落库.

(2026-06-23) 加 __init__: SQLAlchemy 2.0 mapped_column(default=...) 默认只在 INSERT 时
生效, instance 构造后属性还是 None. 业务测试期望构造时就生效 (test_models.py
直接用 `Dictionary(...)` 验证), 所以在 __init__ 显式 set mapped_column 的
Python default 到 instance. server_default 走 DB 层, 不重复.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.base import Base


class Dictionary(Base):
    """字典定义 (一行 = 一个字典, e.g. approval_review_status / reject_reason / page_key).

    字段对应 spec §3.1:
    - code (PK): 字典唯一标识
    - label_zh / label_en: 双语显示名
    - version: 字典 schema 版本号 (add/remove item 时 +1, 触发缓存失效)
    - is_active: 紧急下线开关
    - is_readonly: 单字典级只读 (比 env 全局逃生口细粒度)
    - effective_at / deprecated_at: 灰度上下线时间
    """

    __tablename__ = "dictionaries"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    label_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    label_en: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_readonly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __init__(self, **kwargs: object) -> None:
        """(2026-06-23) 应用 mapped_column 的 Python default 到 instance 属性.

        SA 2.0 default= 只在 INSERT 时触发; 业务上期望 `Dictionary(code, ...)` 构造后
        `d.is_active` 就是 True, 不需要 flush. 这里把 mapped_column 上有 default 的列
        兜底 set, 业务层不依赖 flush 时机.
        """
        super().__init__(**kwargs)
        if self.is_active is None:
            self.is_active = True
        if self.is_readonly is None:
            self.is_readonly = False
        if self.version is None:
            self.version = 1


class DictionaryItem(Base):
    """字典项 (一行 = 一个枚举值).

    字段对应 spec §3.1:
    - (dict_code, key) UNIQUE → 业务代码 key 不变 (schema Literal 引用安全)
    - metadata_json: 扩展位 (颜色/图标/路径等, 业务自定义)
    - is_active + deprecated_at 配合 → 软删除语义 (GET 默认只返 active)
    """

    __tablename__ = "dictionary_items"
    __table_args__ = (UniqueConstraint("dict_code", "key", name="uq_dictionary_items_dict_code_key"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dict_code: Mapped[str] = mapped_column(
        String(64), ForeignKey("dictionaries.code", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    label_en: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __init__(self, **kwargs: object) -> None:
        """(2026-06-23) 同 Dictionary.__init__: 应用 mapped_column Python default."""
        super().__init__(**kwargs)
        if self.is_active is None:
            self.is_active = True
        if self.sort is None:
            self.sort = 0
