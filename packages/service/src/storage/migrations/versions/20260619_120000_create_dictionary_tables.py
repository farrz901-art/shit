"""create dictionary tables (dictionaries + dictionary_items)

业务字典模块 (2026-06-19 lookup spec §3.1-3.2):
- dictionaries: 字典定义 (一行 = 一个字典), PK = code
- dictionary_items: 字典项 (一行 = 一个枚举值), FK → dictionaries.code ON DELETE CASCADE
- 3 个索引:
  - ix_dictionaries_is_active                                    — 列出可用字典
  - ix_dictionary_items_dict_code_is_active_sort                 — 列表查询主索引
  - ix_dictionary_items_dict_code_key_active (partial)          — key 查询 (仅 active)
- UNIQUE(dict_code, key)                                         — dict 内 key 不重复
- down_revision = "20260619_000000" (chat_soft_delete, 当前 head)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "20260619_120000"
down_revision: str | None = "20260619_000000"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """建 dictionaries + dictionary_items 表 + 3 个索引 + UNIQUE 约束."""
    # dictionaries: 字典定义 (一行 = 一个字典)
    op.create_table(
        "dictionaries",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("label_zh", sa.String(length=128), nullable=False),
        sa.Column("label_en", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_readonly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("effective_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deprecated_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_dictionaries_is_active", "dictionaries", ["is_active"])

    # dictionary_items: 字典项 (一行 = 一个枚举值)
    op.create_table(
        "dictionary_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "dict_code",
            sa.String(length=64),
            sa.ForeignKey("dictionaries.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("label_zh", sa.String(length=128), nullable=False),
        sa.Column("label_en", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deprecated_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("dict_code", "key", name="uq_dictionary_items_dict_code_key"),
    )
    # 列表查询主索引
    op.create_index(
        "ix_dictionary_items_dict_code_is_active_sort",
        "dictionary_items",
        ["dict_code", "is_active", "sort"],
    )
    # key 查询: 仅 active (partial index)
    op.create_index(
        "ix_dictionary_items_dict_code_key_active",
        "dictionary_items",
        ["dict_code", "key"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    """回滚: 删索引 + 删表 (顺序: 删 items → 删 dictionaries)."""
    op.drop_index("ix_dictionary_items_dict_code_key_active", table_name="dictionary_items")
    op.drop_index("ix_dictionary_items_dict_code_is_active_sort", table_name="dictionary_items")
    op.drop_table("dictionary_items")
    op.drop_index("ix_dictionaries_is_active", table_name="dictionaries")
    op.drop_table("dictionaries")
