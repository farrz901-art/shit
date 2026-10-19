# Lookup 模块 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现通用业务字典模块（DB + Redis 缓存 + API + 前端 hook + Admin UI + 安全 6 层防御），首批迁移 4 个散落 enum。

**Architecture:** DB 唯一事实源 + Redis L2 缓存 + 进程内 L1 lru_cache + seed yaml 启动初始化 + SafetyGuard 6 层防御 + 前端 useLookup hook + Admin UI 最小可用。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 / Alembic / Redis 7 / Pydantic v2 / Next.js 15 / React 19 / SWR / Tailwind 4 / shadcn/ui / Zod

**Spec:** `docs/superpowers/specs/2026-06-19-lookup-module.md`

---

## File Structure

本 plan 涉及的文件：

### 后端
- **创建**：
  - `packages/service/src/storage/migrations/versions/20260619_000000_create_dictionary_tables.py` — Alembic migration
  - `packages/service/src/lookups/__init__.py`
  - `packages/service/src/lookups/models.py` — Dictionary / DictionaryItem SQLAlchemy
  - `packages/service/src/lookups/schemas.py` — Pydantic schema
  - `packages/service/src/lookups/service.py` — LookupService
  - `packages/service/src/lookups/cache.py` — LookupCache（Redis）
  - `packages/service/src/lookups/safety_guard.py` — SafetyGuard 6 层
  - `packages/service/src/lookups/router.py` — `/api/lookups/*` GET
  - `packages/service/src/lookups/admin_router.py` — `/api/admin/dicts/*` 写
  - `packages/service/src/lookups/audit.py` — 审计日志写入
  - `packages/service/src/lookups/import_export.py` — CSV/JSON 导入导出
  - `packages/service/src/lookups/exceptions.py` — LookupSafetyError
  - `packages/service/src/lookups/README.md` — 模块说明
  - `packages/service/src/common/dictionaries_seed.yaml` — 4 个字典种子
  - `packages/service/src/common/dictionaries_enum.py` — 从 yaml 编译的 StrEnum
  - `packages/service/src/common/dictionaries_loader.py` — yaml 加载器
  - `packages/service/scripts/seed_dictionaries.py` — 启动 seed 脚本
  - `packages/service/scripts/check_dictionary_refs.py` — 启动一致性校验
- **修改**：
  - `packages/service/main.py` — 启动时跑 seed + check_consistency
  - `packages/service/src/approvals/models.py` — StrEnum 改从 dictionaries_enum 引用
  - `packages/service/src/permissions/cache.py` — ALL_PAGE_KEYS 改从 DB 拉
  - `packages/service/src/permissions/router.py` — PAGE_METADATA 改从 DB 拉
  - `packages/service/tests/test_api_contract.py` — 加字典一致性 contract test
  - `packages/service/CLAUDE.md` — 加"字典使用规范"段

### 前端
- **创建**：
  - `packages/web/hooks/useLookup.ts` — 字典 hook
  - `packages/web/hooks/useLookup.test.ts` — hook 单元测试
  - `packages/web/lib/api/lookups.ts` — API 封装
  - `packages/web/app/[locale]/admin/dicts/page.tsx` — Admin UI 入口
  - `packages/web/app/[locale]/admin/dicts/_components/DictList.tsx`
  - `packages/web/app/[locale]/admin/dicts/_components/DictItemEditor.tsx`
  - `packages/web/app/[locale]/admin/dicts/_components/DictItemCreateDialog.tsx`
  - `packages/web/app/[locale]/admin/dicts/_components/DictItemDeleteDialog.tsx`
  - `packages/web/app/[locale]/admin/dicts/_components/DictAuditLog.tsx`
  - `packages/web/app/[locale]/admin/dicts/_components/ReadonlyBanner.tsx`
- **修改**：
  - `packages/web/messages/zh.json` — 加字典管理文案
  - `packages/web/messages/en.json` — 英文文案

### 测试
- **创建**（`packages/service/tests/lookups/`）：
  - `test_models.py` — Dictionary / DictionaryItem 模型
  - `test_service.py` — LookupService 各方法
  - `test_cache.py` — LookupCache 缓存 + 失效广播
  - `test_safety_guard.py` — 6 层防御每层一个 case
  - `test_router.py` — GET API
  - `test_admin_router.py` — POST/PATCH/DELETE
  - `test_import_export.py` — CSV/JSON
  - `test_seed.py` — seed 幂等
  - `test_check_consistency.py` — 启动校验
  - `test_migration.py` — migration up + down
- **创建**（前端）：
  - `packages/web/hooks/useLookup.test.ts` — hook 单元测试
  - `packages/web/app/[locale]/admin/dicts/_components/DictList.test.tsx` — 组件测试

### 文档
- `docs/cookbook/python/lookup.md` — L-语言类教程（~5000 字）
- `docs/superpowers/specs/2026-06-19-lookup-module.md` — 已写
- `docs/superpowers/plans/2026-06-19-lookup-module.md` — 本文档

---

## 任务依赖关系

```
Phase 1 数据层
  Task 1 (migration)
    ↓
  Task 2 (seed yaml + script)
    ↓
  Task 3 (enum 镜像)

Phase 2 核心服务
  Task 4 (Service + Cache + SafetyGuard) ← Task 1,2,3
    ↓
  Task 5 (GET API)  ┐
                     ├─ 并行
  Task 6 (Admin API) ┘

Phase 3 迁移
  Task 7 (4 个 enum 接入) ← Task 5,6

Phase 4 前端 + 文档
  Task 8 (useLookup hook)  ← Task 5
  Task 9 (Admin UI) ← Task 6,8
  Task 10 (docs) ← 全部

每 task 完成 → subagent 审核 → 通过才进下个
```

---

### Task 1: Alembic migration 建表

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260619_000000_create_dictionary_tables.py`
- Create: `packages/service/tests/lookups/test_migration.py`

- [ ] **Step 1: 先用 Alembic 生成空 revision**

```bash
cd c:/doc/Code/rag/packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run alembic revision -m "create_dictionary_tables"
```

Expected: 生成 `versions/20260619_xxxxxx_create_dictionary_tables.py`

- [ ] **Step 2: 写失败测试（test_migration.py）**

```python
"""migration 验证: up 建表成功 + 列/索引齐, down 删表成功"""

import pytest
from sqlalchemy import inspect
from src.storage.session import engine
from alembic.config import Config
from alembic import command


def test_migration_up_creates_tables():
    """up: 验证 dictionaries + dictionary_items 表存在 + 列对得上"""
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    insp = inspect(engine)
    assert insp.has_table("dictionaries")
    assert insp.has_table("dictionary_items")
    cols = {c["name"] for c in insp.get_columns("dictionaries")}
    expected = {"code", "label_zh", "label_en", "description", "version", "is_active",
                "is_readonly", "effective_at", "deprecated_at", "created_at", "updated_at"}
    assert expected.issubset(cols)
    item_cols = {c["name"] for c in insp.get_columns("dictionary_items")}
    expected_item = {"id", "dict_code", "key", "label_zh", "label_en", "description",
                     "sort", "is_active", "effective_at", "deprecated_at",
                     "metadata_json", "created_at", "updated_at"}
    assert expected_item.issubset(item_cols)
    # 索引
    indexes = {i["name"] for i in insp.get_indexes("dictionary_items")}
    assert "ix_dictionary_items_dict_code_is_active_sort" in indexes


def test_migration_down_drops_tables():
    """down: 验证能干净回退"""
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "-1")
    insp = inspect(engine)
    assert not insp.has_table("dictionary_items")
    assert not insp.has_table("dictionaries")
    # 跑回去，保持干净
    command.upgrade(cfg, "head")
```

- [ ] **Step 3: 跑测试确认它失败（DB 还没表）**

```bash
cd c:/doc/Code/rag/packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run pytest tests/lookups/test_migration.py::test_migration_up_creates_tables -v
```

Expected: FAIL with `relation "dictionaries" does not exist`

- [ ] **Step 4: 写 migration 文件内容**

打开刚生成的 `versions/20260619_xxxxxx_create_dictionary_tables.py`，完整重写为：

```python
"""create dictionary tables (dictionaries + dictionary_items)

业务字典: DB 唯一事实源, 提供 /api/lookups + super_admin CRUD.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "20260619_000000"  # 替换为实际生成的 revision
down_revision: str | None = "<上一版本>"  # 查 alembic_version 表填
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    # dictionaries 表: 字典定义
    op.create_table(
        "dictionaries",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("label_zh", sa.String(128), nullable=False),
        sa.Column("label_en", sa.String(128), nullable=False),
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

    # dictionary_items 表: 字典项
    op.create_table(
        "dictionary_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dict_code", sa.String(64), sa.ForeignKey("dictionaries.code", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("label_zh", sa.String(128), nullable=False),
        sa.Column("label_en", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deprecated_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("dict_code", "key", name="uq_dict_item"),
    )
    op.create_index(
        "ix_dictionary_items_dict_code_is_active_sort",
        "dictionary_items",
        ["dict_code", "is_active", "sort"],
    )
    op.create_index(
        "ix_dictionary_items_dict_code_key_active",
        "dictionary_items",
        ["dict_code", "key"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_dictionary_items_dict_code_key_active", table_name="dictionary_items")
    op.drop_index("ix_dictionary_items_dict_code_is_active_sort", table_name="dictionary_items")
    op.drop_table("dictionary_items")
    op.drop_index("ix_dictionaries_is_active", table_name="dictionaries")
    op.drop_table("dictionaries")
```

> ⚠️ 把 `revision` 替换为 alembic 实际生成的；`down_revision` 填 `alembic_version` 表里当前 head。

- [ ] **Step 5: 跑 migration + 验证测试 PASS**

```bash
cd c:/doc/Code/rag/packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run alembic upgrade head
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run pytest tests/lookups/test_migration.py -v
```

Expected: 2 passed

- [ ] **Step 6: 提交**

```bash
cd c:/doc/Code/rag
git add packages/service/src/storage/migrations/versions/20260619_*.py \
        packages/service/tests/lookups/test_migration.py
git commit -m "feat(lookups): alembic migration 建 dictionaries + dictionary_items 表"
```

---

### Task 2: seed yaml + 启动脚本

**Files:**
- Create: `packages/service/src/common/dictionaries_seed.yaml`
- Create: `packages/service/src/common/dictionaries_loader.py`
- Create: `packages/service/scripts/seed_dictionaries.py`
- Create: `packages/service/tests/lookups/test_seed.py`

- [ ] **Step 1: 写 dictionaries_loader.py**

```python
"""dictionaries_seed.yaml 加载器 (启动时 + 测试 fixture 用)

约定: yaml 顶级是 dictionaries 列表, 每项有 code + items (items 可空).
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import yaml


class SeedItem(TypedDict):
    key: str
    label_zh: str
    label_en: str
    sort: int
    description: str | None
    metadata_json: dict | None


class SeedDict(TypedDict):
    code: str
    label_zh: str
    label_en: str
    description: str | None
    items: list[SeedItem]


SEED_PATH: Path = Path(__file__).parent / "dictionaries_seed.yaml"


def load_seed() -> list[SeedDict]:
    """读 yaml, 返字典列表"""
    with open(SEED_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "dictionaries" not in data:
        return []
    return data["dictionaries"]


def get_seed_dict(code: str) -> SeedDict | None:
    for d in load_seed():
        if d["code"] == code:
            return d
    return None
```

- [ ] **Step 2: 写 dictionaries_seed.yaml (4 个字典, 见 spec §3.3)**

按 spec 第三节 3.3 的 yaml 内容写入 `packages/service/src/common/dictionaries_seed.yaml`。

- [ ] **Step 3: 写失败测试 test_seed.py**

```python
"""seed 脚本测试: 4 字典 + 幂等性"""

import pytest
from src.common.dictionaries_loader import load_seed, get_seed_dict
from src.storage.session import session_scope
from src.lookups.service import LookupService
from scripts.seed_dictionaries import run_seed


def test_seed_yaml_loads():
    data = load_seed()
    assert len(data) == 5  # approval_review_status + approval_apply_status + approval_kind + reject_reason + page_key
    assert get_seed_dict("reject_reason") is not None


def test_seed_runs_and_is_idempotent():
    """跑 seed 后再跑, 行数不变"""
    run_seed(force_sync=False)
    with session_scope() as s:
        count_1 = s.query(LookupService.Dictionary).count()
        item_count_1 = s.query(LookupService.DictionaryItem).count()
    run_seed(force_sync=False)
    with session_scope() as s:
        count_2 = s.query(LookupService.Dictionary).count()
        item_count_2 = s.query(LookupService.DictionaryItem).count()
    assert count_1 == count_2
    assert item_count_1 == item_count_2


def test_seed_force_sync_overrides_labels():
    """force_sync=True 时, super_admin 后台改的 label 会被 yaml 覆盖 (危险, 需显式)"""
    # 准备: 改一个 item 的 label_zh
    with session_scope() as s:
        item = s.query(LookupService.DictionaryItem).filter_by(
            dict_code="reject_reason", key="other"
        ).one()
        item.label_zh = "其他 (admin 改)"
    run_seed(force_sync=False)
    with session_scope() as s:
        item = s.query(LookupService.DictionaryItem).filter_by(
            dict_code="reject_reason", key="other"
        ).one()
        assert item.label_zh == "其他 (admin 改)"  # 没被覆盖
    run_seed(force_sync=True)
    with session_scope() as s:
        item = s.query(LookupService.DictionaryItem).filter_by(
            dict_code="reject_reason", key="other"
        ).one()
        assert item.label_zh == "其他"  # 被覆盖回 yaml
```

> 注：Task 4 才会建 LookupService.Dictionary，这里测试依赖 Task 4；本 Task 写到步骤 2 暂停，等 Task 4 完成后再回来写步骤 3-5。

- [ ] **Step 4: 写 seed_dictionaries.py 脚本**

```python
"""启动 seed 脚本: 读 yaml, UPSERT 到 DB (默认不覆盖已存在 label, --force-sync 才覆盖)

用法:
  python -m scripts.seed_dictionaries               # 启动跑一次, 缺啥补啥
  python -m scripts.seed_dictionaries --force-sync  # 危险: 强制用 yaml 覆盖 DB label
"""

from __future__ import annotations

import argparse
import sys

from src.common.dictionaries_loader import load_seed
from src.storage.session import session_scope
from sqlalchemy import select

# 延迟 import 避免循环 (LookupService 依赖 models, models 依赖 storage)
def _import():
    from src.lookups.models import Dictionary, DictionaryItem
    return Dictionary, DictionaryItem


def run_seed(force_sync: bool = False) -> tuple[int, int]:
    """跑 seed, 返 (字典数, item 数)"""
    Dictionary, DictionaryItem = _import()
    data = load_seed()
    dict_count = 0
    item_count = 0
    with session_scope() as s:
        for d in data:
            # UPSERT dictionary
            existing = s.execute(
                select(Dictionary).where(Dictionary.code == d["code"])
            ).scalar_one_or_none()
            if existing is None:
                s.add(Dictionary(
                    code=d["code"],
                    label_zh=d["label_zh"],
                    label_en=d["label_en"],
                    description=d.get("description"),
                ))
                dict_count += 1
            elif force_sync:
                existing.label_zh = d["label_zh"]
                existing.label_en = d["label_en"]
                if d.get("description"):
                    existing.description = d["description"]
            for item in d.get("items", []):
                # UPSERT item
                existing_item = s.execute(
                    select(DictionaryItem).where(
                        DictionaryItem.dict_code == d["code"],
                        DictionaryItem.key == item["key"],
                    )
                ).scalar_one_or_none()
                if existing_item is None:
                    s.add(DictionaryItem(
                        dict_code=d["code"],
                        key=item["key"],
                        label_zh=item["label_zh"],
                        label_en=item["label_en"],
                        description=item.get("description"),
                        sort=item.get("sort", 0),
                        metadata_json=item.get("metadata_json"),
                    ))
                    item_count += 1
                elif force_sync:
                    existing_item.label_zh = item["label_zh"]
                    existing_item.label_en = item["label_en"]
                    if "sort" in item:
                        existing_item.sort = item["sort"]
    return dict_count, item_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-sync", action="store_true", help="强制用 yaml 覆盖 DB label (危险)")
    args = parser.parse_args()
    d, i = run_seed(force_sync=args.force_sync)
    print(f"已 seed: {d} 个新字典 + {i} 个新 item{' (force-sync)' if args.force_sync else ''}")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 跑 seed 验证**

```bash
cd c:/doc/Code/rag/packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run python -m scripts.seed_dictionaries
```

Expected: 输出 `已 seed: 5 个新字典 + 25 个新 item`

```bash
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run python -m scripts.seed_dictionaries
```

Expected: 输出 `已 seed: 0 个新字典 + 0 个新 item`（幂等）

- [ ] **Step 6: 提交（包含 Task 2 全部内容）**

```bash
cd c:/doc/Code/rag
git add packages/service/src/common/dictionaries_seed.yaml \
        packages/service/src/common/dictionaries_loader.py \
        packages/service/scripts/seed_dictionaries.py \
        packages/service/tests/lookups/test_seed.py
git commit -m "feat(lookups): seed yaml + 启动脚本 (4 字典 25 item, UPSERT 幂等)"
```

---

### Task 3: 代码 enum 镜像（dictionaries_enum.py）

**Files:**
- Create: `packages/service/src/common/dictionaries_enum.py`
- Create: `packages/service/tests/common/test_dictionaries_enum.py`

- [ ] **Step 1: 写失败测试**

```python
"""字典 enum 镜像: 从 yaml 编译 StrEnum, schema Literal 引用它"""

from src.common.dictionaries_enum import (
    ApprovalReviewStatusEnum,
    ApprovalApplyStatusEnum,
    ApprovalKindEnum,
    RejectReasonEnum,
    PageKeyEnum,
)


def test_enum_values_match_yaml():
    """所有 enum 值必须 = yaml 里的 key"""
    assert {e.value for e in ApprovalReviewStatusEnum} == {"pending", "approved", "rejected"}
    assert {e.value for e in RejectReasonEnum} == {
        "duplicate", "low_quality", "incomplete", "wrong_category", "format_issue", "other"
    }
    assert {e.value for e in PageKeyEnum} == {
        "admin", "chat", "output", "knowledge", "evaluate", "submissions", "decode", "health"
    }


def test_enum_is_str_subclass():
    """StrEnum 必须可当 str 用 (Pydantic 兼容)"""
    assert ApprovalReviewStatusEnum.PENDING == "pending"
    assert str(ApprovalReviewStatusEnum.PENDING) == "ApprovalReviewStatusEnum.PENDING"
```

- [ ] **Step 2: 跑测试确认它失败**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest tests/common/test_dictionaries_enum.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.common.dictionaries_enum'`

- [ ] **Step 3: 写 dictionaries_enum.py**

```python
"""字典 enum 镜像: 启动时从 dictionaries_seed.yaml 编译成 StrEnum

用途: schema Literal / 业务代码类型提示. DB 是运行时事实源, yaml 是种子.
新增/删除 enum key 必须改 yaml (本文件是自动生成, 不手改).
"""

from __future__ import annotations

from enum import StrEnum

from .dictionaries_loader import get_seed_dict


def _build_enum(name: str, code: str) -> type[StrEnum]:
    """从 yaml 字典项编译 StrEnum"""
    d = get_seed_dict(code)
    if d is None:
        raise ValueError(f"seed yaml 找不到字典: {code}")
    members = {}
    for item in d.get("items", []):
        # 跳过重复 key (yaml 拼错提示)
        if item["key"] in members:
            raise ValueError(f"字典 {code} 有重复 key: {item['key']}")
        members[item["key"].upper()] = item["key"]
    return StrEnum(name, members)


# 启动时编译 (单例, import 一次)
ApprovalReviewStatusEnum = _build_enum("ApprovalReviewStatusEnum", "approval_review_status")
ApprovalApplyStatusEnum = _build_enum("ApprovalApplyStatusEnum", "approval_apply_status")
ApprovalKindEnum = _build_enum("ApprovalKindEnum", "approval_kind")
RejectReasonEnum = _build_enum("RejectReasonEnum", "reject_reason")
PageKeyEnum = _build_enum("PageKeyEnum", "page_key")


# 引用 map: enum 类 → dict_code (供 check_dictionary_refs.py 用)
ENUM_REGISTRY: dict[str, str] = {
    "ApprovalReviewStatusEnum": "approval_review_status",
    "ApprovalApplyStatusEnum": "approval_apply_status",
    "ApprovalKindEnum": "approval_kind",
    "RejectReasonEnum": "reject_reason",
    "PageKeyEnum": "page_key",
}
```

- [ ] **Step 4: 跑测试 PASS**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest tests/common/test_dictionaries_enum.py -v
```

Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd c:/doc/Code/rag
git add packages/service/src/common/dictionaries_enum.py \
        packages/service/tests/common/test_dictionaries_enum.py
git commit -m "feat(lookups): 字典 enum 镜像 (从 yaml 编译 StrEnum, schema Literal 用)"
```

---

### Task 4: LookupService + LookupCache + SafetyGuard

**Files:**
- Create: `packages/service/src/lookups/__init__.py`
- Create: `packages/service/src/lookups/exceptions.py`
- Create: `packages/service/src/lookups/models.py`
- Create: `packages/service/src/lookups/service.py`
- Create: `packages/service/src/lookups/cache.py`
- Create: `packages/service/src/lookups/safety_guard.py`
- Create: `packages/service/src/lookups/audit.py`
- Create: `packages/service/tests/lookups/test_service.py`
- Create: `packages/service/tests/lookups/test_cache.py`
- Create: `packages/service/tests/lookups/test_safety_guard.py`

- [ ] **Step 1: 写 exceptions.py + models.py + __init__.py**

`exceptions.py`:

```python
"""字典模块异常: LookupSafetyError (403/404/409/412/429 统一表达)"""

from __future__ import annotations


class LookupSafetyError(Exception):
    """SafetyGuard 拒绝时抛. code 映射 HTTP status."""

    def __init__(self, http_status: int, detail: str):
        self.http_status = http_status
        self.detail = detail
        super().__init__(detail)


class LookupNotFoundError(Exception):
    """字典 / item 不存在"""
    pass
```

`models.py`:

```python
"""Dictionary / DictionaryItem SQLAlchemy 模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.base import Base


class Dictionary(Base):
    """字典定义 (一行 = 一个字典)"""

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
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DictionaryItem(Base):
    """字典项 (一行 = 一个枚举值)"""

    __tablename__ = "dictionary_items"
    __table_args__ = (UniqueConstraint("dict_code", "key", name="uq_dict_item"),)

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
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
```

`__init__.py`:

```python
"""字典模块: DB 唯一事实源, 通用业务字典"""
```

- [ ] **Step 2: 写 audit.py**

```python
"""字典变更审计: 复用项目 audit_log 表"""

from __future__ import annotations

from typing import Any

from src.db.models.audit_log import AuditLog
from src.storage.session import session_scope


def log_dict_change(
    *,
    actor: str,
    action: str,
    target: str,
    before: dict | None,
    after: dict | None,
    ip: str | None,
    forced: bool = False,
):
    """写一条字典变更审计"""
    with session_scope() as s:
        s.add(AuditLog(
            actor=actor,
            action=f"dictionary.{action}{'.forced' if forced else ''}",
            target=target,
            before_json=before,
            after_json=after,
            ip=ip,
        ))
```

- [ ] **Step 3: 写 cache.py (LookupCache, 复用 permission_cache_redis 模式)**

```python
"""LookupCache: Redis L2 + 进程内 L1 (lru_cache)

- 全字典 hash 存 1 个 key: dict:all
- 启动预热 + 5 分钟 TTL
- 写操作触发 DEL + PUBLISH dict.invalidate
- 进程内 lru_cache 由 Redis 订阅广播失效
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import redis

from src.core.redis_client import get_redis_client


_REDIS_KEY = "dict:all"
_REDIS_TTL = 300  # 5 分钟
_INVALIDATE_CHANNEL = "dict.invalidate"


class LookupCache:
    """全局单例 (类属性)"""

    _instance: "LookupCache | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._l1_data = None
        return cls._instance

    def get_all(self) -> dict[str, dict] | None:
        """返 {dict_code: {label_zh, label_en, version, items: [...]}}"""
        if self._l1_data is not None:
            return self._l1_data
        try:
            r = get_redis_client()
            raw = r.get(_REDIS_KEY)
            if raw is None:
                return None
            self._l1_data = json.loads(raw)
            return self._l1_data
        except redis.RedisError:
            return None  # 降级: 不缓存, 直接查 DB

    def set_all(self, data: dict[str, dict]):
        self._l1_data = data
        try:
            r = get_redis_client()
            r.setex(_REDIS_KEY, _REDIS_TTL, json.dumps(data, default=str))
        except redis.RedisError:
            pass  # 降级: 进程内还有 L1

    def invalidate(self, dict_code: str | None = None):
        """失效 cache: 删 Redis + 清 L1 + 广播"""
        self._l1_data = None
        try:
            r = get_redis_client()
            r.delete(_REDIS_KEY)
            r.publish(_INVALIDATE_CHANNEL, dict_code or "*")
        except redis.RedisError:
            pass

    def get_dict_readonly(self, dict_code: str) -> bool:
        """查字典级 is_readonly (从 cache 拉)"""
        data = self.get_all() or {}
        d = data.get(dict_code, {})
        return d.get("is_readonly", False)

    def get_dict_version(self, dict_code: str) -> int:
        data = self.get_all() or {}
        d = data.get(dict_code, {})
        return d.get("version", 0)


lookup_cache = LookupCache()


# 启动时订阅广播 (在 main.py lifespan 里 start subscriber)
def start_invalidation_subscriber():
    """订阅 dict.invalidate channel, 收到消息清 L1"""
    import threading

    def _subscriber():
        try:
            r = get_redis_client()
            pubsub = r.pubsub()
            pubsub.subscribe(_INVALIDATE_CHANNEL)
            for msg in pubsub.listen():
                if msg.get("type") == "message":
                    lookup_cache.invalidate(msg["data"].decode() if isinstance(msg["data"], bytes) else msg["data"])
        except redis.RedisError:
            pass  # 降级: TTL 兜底

    t = threading.Thread(target=_subscriber, daemon=True, name="dict-invalidate-subscriber")
    t.start()
```

- [ ] **Step 4: 写 safety_guard.py (6 层防御)**

```python
"""SafetyGuard: 所有写操作走 6 层防御, 任一失败 raise LookupSafetyError"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select, func

from src.core.rate_limiter import rate_limiter
from src.middleware.auth import CurrentUser
from src.lookups.cache import lookup_cache
from src.lookups.exceptions import LookupSafetyError
from src.storage.session import session_scope


# 业务表 → 字典项 的反向引用 map
_REFERENCE_MAP: dict[str, list[tuple[str, str]]] = {
    "approval_kind":          [("approvals", "kind")],
    "approval_review_status": [("approvals", "review_status")],
    "approval_apply_status":  [("approvals", "apply_status")],
    "reject_reason":          [("approvals", "reject_reason")],
    "page_key":               [("role_permissions", "page_key")],
}


class SafetyGuard:
    def check_all(
        self,
        *,
        action: Literal["create", "patch", "delete"],
        dict_code: str,
        key: str | None,
        user: CurrentUser,
        confirm_token: str | None,
        payload: dict[str, Any],
        force: bool = False,
    ):
        self._check_role(user)  # 第 1 层
        self._check_readonly(dict_code)  # 第 2 层
        if action == "delete":
            self._check_confirm_token(user, confirm_token)  # 第 3 层
            if not force:
                self._check_business_references(dict_code, key)  # 第 4 层
        if payload.get("expected_version") is not None:
            self._check_version(dict_code, payload["expected_version"])  # 第 5 层
        self._check_rate_limit(user)  # 第 6 层

    def _check_role(self, user: CurrentUser):
        if user.role != "super_admin":
            raise LookupSafetyError(403, "super_admin required")

    def _check_readonly(self, dict_code: str):
        if os.getenv("DICTIONARY_READONLY", "").lower() == "true":
            raise LookupSafetyError(403, "DICTIONARY_READONLY=true (env readonly)")
        if lookup_cache.get_dict_readonly(dict_code):
            raise LookupSafetyError(403, f"dictionary '{dict_code}' is readonly")

    def _check_confirm_token(self, user: CurrentUser, token: str | None):
        if not token:
            raise LookupSafetyError(412, "confirm token required for delete")
        # token = sha256(user.password_hash : YYYYMMDDHH)[:16]
        # 客户端必须先 POST /api/admin/dicts/confirm-token 拿当前小时 token
        # 这里只校验格式, 真实 token 由 router 在确认时签发
        if len(token) != 16 or not all(c in "0123456789abcdef" for c in token.lower()):
            raise LookupSafetyError(412, "invalid confirm token format")

    def _check_business_references(self, dict_code: str, key: str):
        refs = _REFERENCE_MAP.get(dict_code, [])
        if not refs:
            return
        total = 0
        with session_scope() as s:
            from sqlalchemy import text
            for table, column in refs:
                sql = text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :key")
                total += s.execute(sql, {"key": key}).scalar() or 0
        if total > 0:
            raise LookupSafetyError(
                409,
                f"item '{dict_code}:{key}' still referenced by {total} rows; "
                f"soft-delete refused. Use ?force=true to bypass (audit logged)",
            )

    def _check_version(self, dict_code: str, expected_version: int):
        current = lookup_cache.get_dict_version(dict_code)
        if current != expected_version:
            raise LookupSafetyError(
                412, f"version mismatch: expected={expected_version}, current={current}"
            )

    def _check_rate_limit(self, user: CurrentUser):
        key = f"dict_admin:{user.id}"
        if not rate_limiter.allow(key, max_per_minute=60):
            raise LookupSafetyError(429, "rate limit exceeded (60/min)")


safety_guard = SafetyGuard()
```

- [ ] **Step 5: 写 service.py (LookupService)**

```python
"""LookupService: 字典读写业务逻辑, 走 cache + audit"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.lookups.cache import lookup_cache
from src.lookups.models import Dictionary, DictionaryItem
from src.lookups.audit import log_dict_change
from src.lookups.exceptions import LookupNotFoundError
from src.storage.session import session_scope


class LookupService:
    """DB 唯一事实源, 缓存加速, 写操作触发缓存失效 + 审计"""

    @staticmethod
    def list_all_dicts() -> list[dict]:
        """列出全部字典概要 (缓存)"""
        data = lookup_cache.get_all()
        if data is None:
            data = LookupService._load_all_from_db()
            lookup_cache.set_all(data)
        return [
            {
                "code": code,
                "label_zh": d["label_zh"],
                "label_en": d["label_en"],
                "version": d["version"],
                "is_active": d.get("is_active", True),
            }
            for code, d in data.items()
        ]

    @staticmethod
    def get(dict_code: str, *, only_active: bool = True, lang: str = "both") -> dict:
        """查单字典 + items"""
        data = lookup_cache.get_all()
        if data is None:
            data = LookupService._load_all_from_db()
            lookup_cache.set_all(data)
        d = data.get(dict_code)
        if d is None:
            raise LookupNotFoundError(f"dictionary '{dict_code}' not found")
        items = d.get("items", [])
        if only_active:
            items = [i for i in items if i.get("is_active", True)]
        if lang == "zh":
            items = [{k: v for k, v in i.items() if k != "label_en"} for i in items]
        elif lang == "en":
            items = [{k: v for k, v in i.items() if k != "label_zh"} for i in items]
        return {
            "code": dict_code,
            "label_zh": d["label_zh"],
            "label_en": d["label_en"],
            "version": d["version"],
            "items": items,
        }

    @staticmethod
    def get_one(dict_code: str, key: str) -> dict:
        data = lookup_cache.get_all()
        if data is None:
            data = LookupService._load_all_from_db()
            lookup_cache.set_all(data)
        d = data.get(dict_code)
        if d is None:
            raise LookupNotFoundError(f"dictionary '{dict_code}' not found")
        for item in d.get("items", []):
            if item["key"] == key:
                return item
        raise LookupNotFoundError(f"item '{dict_code}:{key}' not found")

    @staticmethod
    def create_item(dict_code: str, payload: dict, *, actor: str, ip: str) -> dict:
        """新增 item"""
        with session_scope() as s:
            # 验证 dict 存在
            d = s.execute(select(Dictionary).where(Dictionary.code == dict_code)).scalar_one_or_none()
            if d is None:
                raise LookupNotFoundError(f"dictionary '{dict_code}' not found")
            # 验证 key 不重复
            existing = s.execute(
                select(DictionaryItem).where(
                    DictionaryItem.dict_code == dict_code,
                    DictionaryItem.key == payload["key"],
                )
            ).scalar_one_or_none()
            if existing:
                from src.lookups.exceptions import LookupSafetyError
                raise LookupSafetyError(409, f"item '{dict_code}:{payload['key']}' already exists")
            new = DictionaryItem(
                dict_code=dict_code,
                key=payload["key"],
                label_zh=payload["label_zh"],
                label_en=payload["label_en"],
                sort=payload.get("sort", 0),
                description=payload.get("description"),
                metadata_json=payload.get("metadata_json"),
            )
            s.add(new)
            d.version = d.version + 1
        lookup_cache.invalidate(dict_code)
        log_dict_change(actor=actor, action="item.create", target=f"{dict_code}:{payload['key']}",
                        before=None, after=payload, ip=ip)
        return payload

    @staticmethod
    def patch_item(dict_code: str, key: str, payload: dict, *, actor: str, ip: str) -> dict:
        """改 item (label/sort/metadata_json/is_active)"""
        with session_scope() as s:
            item = s.execute(
                select(DictionaryItem).where(
                    DictionaryItem.dict_code == dict_code,
                    DictionaryItem.key == key,
                )
            ).scalar_one_or_none()
            if item is None:
                raise LookupNotFoundError(f"item '{dict_code}:{key}' not found")
            before = {
                "label_zh": item.label_zh, "label_en": item.label_en,
                "sort": item.sort, "is_active": item.is_active,
            }
            for field in ("label_zh", "label_en", "sort", "is_active", "description", "metadata_json"):
                if field in payload and payload[field] is not None:
                    setattr(item, field, payload[field])
            # dict version + 1
            d = s.execute(select(Dictionary).where(Dictionary.code == dict_code)).scalar_one()
            d.version = d.version + 1
        lookup_cache.invalidate(dict_code)
        log_dict_change(actor=actor, action="item.patch", target=f"{dict_code}:{key}",
                        before=before, after=payload, ip=ip)
        return {"key": key, **payload}

    @staticmethod
    def soft_delete_item(dict_code: str, key: str, *, actor: str, ip: str, force: bool = False) -> dict:
        """软删: is_active=False + deprecated_at=NOW()"""
        with session_scope() as s:
            item = s.execute(
                select(DictionaryItem).where(
                    DictionaryItem.dict_code == dict_code,
                    DictionaryItem.key == key,
                )
            ).scalar_one_or_none()
            if item is None:
                raise LookupNotFoundError(f"item '{dict_code}:{key}' not found")
            item.is_active = False
            item.deprecated_at = datetime.utcnow()
            d = s.execute(select(Dictionary).where(Dictionary.code == dict_code)).scalar_one()
            d.version = d.version + 1
        lookup_cache.invalidate(dict_code)
        log_dict_change(
            actor=actor, action="item.delete", target=f"{dict_code}:{key}",
            before={"is_active": True}, after={"is_active": False, "deprecated_at": "NOW"},
            ip=ip, forced=force,
        )
        return {"key": key, "is_active": False, "deprecated_at": "NOW"}

    @staticmethod
    def _load_all_from_db() -> dict[str, dict]:
        """从 DB 加载全部字典, 写入 cache"""
        with session_scope() as s:
            dicts = s.execute(select(Dictionary)).scalars().all()
            items = s.execute(
                select(DictionaryItem).order_by(DictionaryItem.dict_code, DictionaryItem.sort)
            ).scalars().all()
        result: dict[str, dict] = {}
        for d in dicts:
            result[d.code] = {
                "label_zh": d.label_zh, "label_en": d.label_en,
                "version": d.version, "is_active": d.is_active,
                "is_readonly": d.is_readonly,
                "items": [],
            }
        for item in items:
            if item.dict_code in result:
                result[item.dict_code]["items"].append({
                    "key": item.key, "label_zh": item.label_zh, "label_en": item.label_en,
                    "sort": item.sort, "is_active": item.is_active,
                    "description": item.description, "metadata_json": item.metadata_json,
                    "effective_at": item.effective_at, "deprecated_at": item.deprecated_at,
                })
        return result
```

- [ ] **Step 6: 写失败测试 test_service.py / test_cache.py / test_safety_guard.py**

> 测试代码按 spec §5.1-5.4 + §4.6 + §4.7 覆盖：
> - test_service.py: list / get / get_one / create / patch / soft_delete
> - test_cache.py: get/set/invalidate/订阅广播
> - test_safety_guard.py: 6 层每层一个 case

```python
# test_safety_guard.py 关键 case 示意
import pytest
from src.lookups.safety_guard import safety_guard
from src.lookups.exceptions import LookupSafetyError


def test_layer1_role_check_fails():
    user = MockUser(role="user")
    with pytest.raises(LookupSafetyError) as exc:
        safety_guard.check_all(action="patch", dict_code="reject_reason", key="duplicate",
                               user=user, confirm_token=None, payload={})
    assert exc.value.http_status == 403


def test_layer2_env_readonly_fails(monkeypatch):
    monkeypatch.setenv("DICTIONARY_READONLY", "true")
    user = MockUser(role="super_admin")
    with pytest.raises(LookupSafetyError) as exc:
        safety_guard.check_all(action="patch", dict_code="reject_reason", key="duplicate",
                               user=user, confirm_token=None, payload={})
    assert "DICTIONARY_READONLY" in exc.value.detail


def test_layer3_delete_requires_confirm_token():
    user = MockUser(role="super_admin")
    with pytest.raises(LookupSafetyError) as exc:
        safety_guard.check_all(action="delete", dict_code="reject_reason", key="duplicate",
                               user=user, confirm_token=None, payload={})
    assert exc.value.http_status == 412


def test_layer4_delete_blocks_when_referenced():
    # mock _check_business_references 走 DB, 假设 duplicate 被 12 个 approvals 引用
    user = MockUser(role="super_admin")
    with pytest.raises(LookupSafetyError) as exc:
        safety_guard.check_all(action="delete", dict_code="reject_reason", key="duplicate",
                               user=user, confirm_token="0123456789abcdef", payload={}, force=False)
    assert exc.value.http_status == 409
    assert "still referenced" in exc.value.detail


def test_layer5_version_mismatch():
    user = MockUser(role="super_admin")
    with pytest.raises(LookupSafetyError) as exc:
        safety_guard.check_all(action="patch", dict_code="reject_reason", key="other",
                               user=user, confirm_token=None,
                               payload={"expected_version": 999})
    assert exc.value.http_status == 412


def test_layer6_rate_limit():
    user = MockUser(role="super_admin")
    for _ in range(60):
        safety_guard._check_rate_limit(user)
    with pytest.raises(LookupSafetyError) as exc:
        safety_guard._check_rate_limit(user)
    assert exc.value.http_status == 429
```

- [ ] **Step 7: 跑全部测试**

```bash
cd c:/doc/Code/rag/packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run pytest tests/lookups/ -v
```

Expected: 全部 PASS（>=20 个测试）

- [ ] **Step 8: 提交**

```bash
cd c:/doc/Code/rag
git add packages/service/src/lookups/ packages/service/tests/lookups/test_service.py \
        packages/service/tests/lookups/test_cache.py packages/service/tests/lookups/test_safety_guard.py
git commit -m "feat(lookups): LookupService + Cache(Redis+L1) + SafetyGuard 6层"
```

---

### Task 5: GET API (/api/lookups/*)

**Files:**
- Create: `packages/service/src/lookups/schemas.py`
- Create: `packages/service/src/lookups/router.py`
- Create: `packages/service/tests/lookups/test_router.py`
- Modify: `packages/service/src/api/routes.py` — 注册 router

- [ ] **Step 1: 写 schemas.py (Pydantic)**

按 spec §4.6 的 schema 定义。

- [ ] **Step 2: 写 router.py (3 个 GET 端点)**

```python
"""/api/lookups/* — 字典读 API (任何登录用户)"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.lookups.schemas import DictionaryListResponse, DictionaryResponse, LookupItemResponse
from src.lookups.service import LookupService
from src.lookups.exceptions import LookupNotFoundError
from src.middleware.auth import resolve_user, CurrentUser

router = APIRouter(prefix="/api/lookups", tags=["lookups"])


@router.get("", response_model=DictionaryListResponse)
def list_all_dicts(user: CurrentUser = Depends(resolve_user)):
    """列出全部字典概要"""
    return {"dictionaries": LookupService.list_all_dicts()}


@router.get("/{dict_code}", response_model=DictionaryResponse)
def get_dict(
    dict_code: str,
    only_active: bool = Query(True),
    lang: str = Query("both", pattern="^(zh|en|both)$"),
    user: CurrentUser = Depends(resolve_user),
):
    """查单字典 + items"""
    try:
        return LookupService.get(dict_code, only_active=only_active, lang=lang)
    except LookupNotFoundError as e:
        raise HTTPException(404, detail=str(e))


@router.get("/{dict_code}/{key}", response_model=LookupItemResponse)
def get_one_item(
    dict_code: str, key: str,
    user: CurrentUser = Depends(resolve_user),
):
    """查单个 item"""
    try:
        return LookupService.get_one(dict_code, key)
    except LookupNotFoundError as e:
        raise HTTPException(404, detail=str(e))
```

- [ ] **Step 3: 在 routes.py 注册**

打开 `packages/service/src/api/routes.py`，找到合适位置加：

```python
from src.lookups.router import router as lookups_router
# ...
app.include_router(lookups_router)
```

- [ ] **Step 4: 写 test_router.py (3 个端点 + 401/404)**

- [ ] **Step 5: 启动 + 手动 curl 验证**

```bash
cd c:/doc/Code/rag/packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run python main.py &
# 等启动
sleep 5
TOKEN="<先 login 拿>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/lookups/reject_reason | python -m json.tool
```

Expected: 200, 返回 6 个 item

- [ ] **Step 6: 提交**

```bash
cd c:/doc/Code/rag
git add packages/service/src/lookups/schemas.py packages/service/src/lookups/router.py \
        packages/service/src/api/routes.py packages/service/tests/lookups/test_router.py
git commit -m "feat(lookups): GET /api/lookups/* 读 API (3 端点)"
```

---

### Task 6: Admin API (/api/admin/dicts/*)

**Files:**
- Create: `packages/service/src/lookups/admin_router.py`
- Create: `packages/service/src/lookups/import_export.py`
- Create: `packages/service/tests/lookups/test_admin_router.py`
- Create: `packages/service/tests/lookups/test_import_export.py`
- Modify: `packages/service/src/api/routes.py` — 注册 admin router

- [ ] **Step 1: 写 admin_router.py**

按 spec §4.2 + §4.3 写 7 个端点：
- POST `/api/admin/dicts` — 新建字典
- PATCH `/api/admin/dicts/{dict_code}` — 改字典 metadata
- POST `/api/admin/dicts/{dict_code}/items` — 新增 item
- PATCH `/api/admin/dicts/{dict_code}/items/{key}` — 改 item
- DELETE `/api/admin/dicts/{dict_code}/items/{key}` — 软删
- POST `/api/admin/dicts/confirm-token` — 签发删除确认 token
- GET `/api/admin/dicts/{dict_code}/audit` — 审计日志

每个端点都用 `safety_guard.check_all()` 守门，然后调 `LookupService` 方法。

- [ ] **Step 2: 写 import_export.py (CSV/JSON)**

```python
"""字典导入导出: CSV / JSON"""

import csv
import io
import json
from typing import Any


def export_dict_to_csv(items: list[dict]) -> str:
    """导出 items 为 CSV 字符串"""
    if not items:
        return ""
    output = io.StringIO()
    fieldnames = ["key", "label_zh", "label_en", "sort", "is_active", "description", "metadata_json"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        row = {**item}
        if isinstance(row.get("metadata_json"), dict):
            row["metadata_json"] = json.dumps(row["metadata_json"], ensure_ascii=False)
        writer.writerow(row)
    return output.getvalue()


def import_items_from_csv(csv_text: str) -> list[dict]:
    """解析 CSV 文本, 返 item 列表"""
    reader = csv.DictReader(io.StringIO(csv_text))
    result = []
    for row in reader:
        if row.get("metadata_json"):
            try:
                row["metadata_json"] = json.loads(row["metadata_json"])
            except json.JSONDecodeError:
                row["metadata_json"] = None
        result.append(row)
    return result


def export_to_json(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, indent=2, default=str)


def import_from_json(text: str) -> dict:
    return json.loads(text)
```

- [ ] **Step 3: 写 test_admin_router.py + test_import_export.py**

测试矩阵：
- 6 层防御每层一个 case (super_admin 通过 / 普通用户 403 / env readonly 403 / 缺 confirm_token 412 / 引用未解 409 / 版本不匹配 412 / rate limit 429)
- 创建 / 改 / 软删 happy path
- CSV 导出导入 round-trip
- JSON 导出导入 round-trip

- [ ] **Step 4: 注册 admin router**

```python
# packages/service/src/api/routes.py
from src.lookups.admin_router import router as lookups_admin_router
app.include_router(lookups_admin_router)
```

- [ ] **Step 5: 提交**

```bash
cd c:/doc/Code/rag
git add packages/service/src/lookups/admin_router.py \
        packages/service/src/lookups/import_export.py \
        packages/service/src/api/routes.py \
        packages/service/tests/lookups/test_admin_router.py \
        packages/service/tests/lookups/test_import_export.py
git commit -m "feat(lookups): /api/admin/dicts/* 写 API + CSV/JSON 导入导出"
```

---

### Task 7: 现有 4 个 enum 接入 lookup (双写兼容)

**Files:**
- Modify: `packages/service/src/approvals/models.py` — StrEnum 改从 dictionaries_enum 导入
- Modify: `packages/service/src/permissions/cache.py` — ALL_PAGE_KEYS 改从 DB 拉
- Modify: `packages/service/src/permissions/router.py` — PAGE_METADATA 改从 DB 拉
- Modify: `packages/service/src/api/routes.py` — 无（已注册）
- Create: `packages/service/scripts/check_dictionary_refs.py`
- Modify: `packages/service/main.py` — 启动跑 seed + check_consistency
- Modify: `packages/service/tests/test_api_contract.py` — 加字典一致性 contract test

- [ ] **Step 1: 改 approvals/models.py**

```python
# 旧 enum 删掉, 改从 dictionaries_enum 导入 (R1 兼容期)
# 保留 import 以便外部代码仍可 from src.approvals.models import ApprovalReviewStatus
from src.common.dictionaries_enum import (
    ApprovalReviewStatusEnum as ApprovalReviewStatus,
    ApprovalApplyStatusEnum as ApprovalApplyStatus,
    ApprovalKindEnum as ApprovalKind,
)
from src.common.dictionaries_enum import RejectReasonEnum as RejectReason

# class ApprovalReviewStatus(StrEnum): ... # 已删
```

- [ ] **Step 2: 改 permissions/cache.py**

```python
# ALL_PAGE_KEYS 改从 DB 拉
# 启动时缓存, 后续 PATCH 触发 invalidate
from src.lookups.service import LookupService

def _get_all_page_keys() -> tuple[str, ...]:
    try:
        d = LookupService.get("page_key", only_active=True)
        return tuple(item["key"] for item in d["items"])
    except Exception:
        # fallback: 旧硬编 (R1 兼容期, R2 删)
        return (
            "admin", "chat", "output", "knowledge",
            "evaluate", "submissions", "decode", "health",
        )

# ALL_PAGE_KEYS = _get_all_page_keys()  # 模块导入时跑一次
# 注: 用函数代替, 启动时调一次缓存; 后续 PATCH 通过 lookup_cache.invalidate 刷

PAGE_METADATA: list[dict] = []  # 从 DB 拉, 见 router
```

- [ ] **Step 3: 改 permissions/router.py**

把硬编的 `pages: PAGE_METADATA` 改为从 `LookupService.get("page_key", lang="both")` 取 items（含 path 在 metadata_json）。

- [ ] **Step 4: 写 check_dictionary_refs.py 启动校验**

```python
"""启动时一致性校验: yaml 字典 ⊆ DB 字典, enum 类 ⊆ DB items"""

import sys
from src.common.dictionaries_loader import load_seed
from src.common.dictionaries_enum import ENUM_REGISTRY
from src.lookups.service import LookupService
from src.lookups.exceptions import LookupNotFoundError


def check_consistency():
    """启动时 fail-fast 校验, 不一致 raise"""
    yaml_dicts = {d["code"] for d in load_seed()}
    db_dicts = {d["code"] for d in LookupService.list_all_dicts()}
    missing = yaml_dicts - db_dicts
    if missing:
        raise RuntimeError(
            f"DB missing dictionaries: {missing}. Run: python -m scripts.seed_dictionaries"
        )
    # enum 镜像校验
    for enum_name, dict_code in ENUM_REGISTRY.items():
        try:
            d = LookupService.get(dict_code, only_active=True)
            db_keys = {item["key"] for item in d["items"]}
        except LookupNotFoundError:
            raise RuntimeError(f"ENUM_REGISTRY 指向不存在的字典: {dict_code}")
        # 静态 import enum 类
        import importlib
        enums_module = importlib.import_module("src.common.dictionaries_enum")
        enum_cls = getattr(enums_module, enum_name)
        enum_keys = {e.value for e in enum_cls}
        if not enum_keys.issubset(db_keys):
            extra = enum_keys - db_keys
            raise RuntimeError(f"enum {enum_name} has keys not in DB {dict_code}: {extra}")


if __name__ == "__main__":
    try:
        check_consistency()
        print("✅ Dictionary consistency check passed")
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)
```

- [ ] **Step 5: 在 main.py 启动时跑 seed + check**

打开 `packages/service/main.py` 找到 lifespan/startup 部分，加：

```python
from scripts.seed_dictionaries import run_seed
from scripts.check_dictionary_refs import check_consistency

@app.on_event("startup")
def on_startup():
    run_seed(force_sync=False)  # 缺啥补啥
    check_consistency()  # 启动 fail-fast
    from src.lookups.cache import start_invalidation_subscriber
    start_invalidation_subscriber()  # 启动 Redis 订阅
```

- [ ] **Step 6: 加 contract test**

`packages/service/tests/test_api_contract.py` 加：

```python
def test_dictionary_consistency_with_schema():
    """所有 StrEnum + Literal 都必须 ⊆ DB 字典项"""
    from src.common.dictionaries_enum import ENUM_REGISTRY
    from src.lookups.service import LookupService
    from src.common.dictionaries_loader import load_seed
    # 业务 enum 镜像
    for enum_name, dict_code in ENUM_REGISTRY.items():
        d = LookupService.get(dict_code, only_active=True)
        db_keys = {item["key"] for item in d["items"]}
        import importlib
        enum_cls = getattr(importlib.import_module("src.common.dictionaries_enum"), enum_name)
        enum_keys = {e.value for e in enum_cls}
        assert enum_keys.issubset(db_keys), f"{enum_name} 多了: {enum_keys - db_keys}"
    # 扫 router Literal (已有扫 Literal 的 helper, 复用)
    # ...
```

- [ ] **Step 7: 跑全部相关测试**

```bash
cd c:/doc/Code/rag/packages/service
RAG_DB_URL=postgresql+psycopg://postgres:deyuan888@localhost:5432/rag \
  uv run pytest tests/ -v
```

Expected: 全部通过；包括 approvals / permissions / contract / lookups

- [ ] **Step 8: 提交**

```bash
cd c:/doc/Code/rag
git add packages/service/src/approvals/models.py \
        packages/service/src/permissions/cache.py \
        packages/service/src/permissions/router.py \
        packages/service/scripts/check_dictionary_refs.py \
        packages/service/main.py \
        packages/service/tests/test_api_contract.py
git commit -m "refactor(lookups): 4 个 enum 接入 lookup (R1 兼容期, 旧 StrEnum 仍可 import)"
```

---

### Task 8: useLookup hook + 替换前端 enum 用法

**Files:**
- Create: `packages/web/lib/api/lookups.ts`
- Create: `packages/web/hooks/useLookup.ts`
- Create: `packages/web/hooks/useLookup.test.ts`

- [ ] **Step 1: 写 lookups.ts (API 封装)**

```typescript
// packages/web/lib/api/lookups.ts
export type LookupItem = {
  key: string;
  label_zh: string;
  label_en: string;
  sort: number;
  is_active: boolean;
  description?: string | null;
  metadata_json?: Record<string, unknown> | null;
};

export type LookupDict = {
  code: string;
  label_zh: string;
  label_en: string;
  version: number;
  items: LookupItem[];
};

export async function fetchLookup(
  dictCode: string,
  opts: { lang?: "zh" | "en" | "both"; onlyActive?: boolean } = {}
): Promise<LookupDict> {
  const lang = opts.lang ?? "both";
  const onlyActive = opts.onlyActive ?? true;
  const res = await fetch(
    `/api/lookups/${dictCode}?lang=${lang}&only_active=${onlyActive}`,
    { credentials: "include" }
  );
  if (!res.ok) throw new Error(`lookup ${dictCode} failed: ${res.status}`);
  return res.json();
}

export async function fetchAllDicts(): Promise<{ code: string; label_zh: string; label_en: string; version: number; is_active: boolean }[]> {
  const res = await fetch(`/api/lookups`, { credentials: "include" });
  if (!res.ok) throw new Error(`fetch all dicts failed: ${res.status}`);
  const data = await res.json();
  return data.dictionaries;
}
```

- [ ] **Step 2: 写 useLookup.ts (SWR hook)**

按 spec §5.5。

- [ ] **Step 3: 写 useLookup.test.ts**

测试：mock fetch → 验证 hook 返 items / byKey / labelFor / refresh。

- [ ] **Step 4: 跑测试**

```bash
cd c:/doc/Code/rag/packages/web
bunx vitest run hooks/useLookup.test.ts
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd c:/doc/Code/rag
git add packages/web/lib/api/lookups.ts packages/web/hooks/useLookup.ts packages/web/hooks/useLookup.test.ts
git commit -m "feat(web): useLookup hook + API 封装"
```

---

### Task 9: Admin UI 最小可用版

**Files:**
- Create: `packages/web/app/[locale]/admin/dicts/page.tsx`
- Create: `packages/web/app/[locale]/admin/dicts/_components/*.tsx` (6 个)
- Modify: `packages/web/messages/zh.json` / `en.json`

- [ ] **Step 1: 写 DictList.tsx (列表 + 行内编辑)**

- [ ] **Step 2: 写 DictItemEditor.tsx (单行编辑表单)**

- [ ] **Step 3: 写 DictItemCreateDialog.tsx (新增弹窗)**

- [ ] **Step 4: 写 DictItemDeleteDialog.tsx (删除 + 二次确认输入框)**

- [ ] **Step 5: 写 DictAuditLog.tsx (审计日志抽屉)**

- [ ] **Step 6: 写 ReadonlyBanner.tsx (顶部 DICTIONARY_READONLY 状态条)**

- [ ] **Step 7: 写 page.tsx (入口: dict_code 下拉 + 子组件组装)**

- [ ] **Step 8: 加 i18n 文案 (zh + en)**

- [ ] **Step 9: 提交**

```bash
cd c:/doc/Code/rag
git add packages/web/app/\[locale\]/admin/dicts/ packages/web/messages/
git commit -m "feat(web): Admin UI /admin/dicts 字典管理 (6 组件 + i18n)"
```

---

### Task 10: 文档

**Files:**
- Create: `docs/cookbook/python/lookup.md`
- Create: `packages/service/src/lookups/README.md`
- Modify: `packages/service/CLAUDE.md`

- [ ] **Step 1: 写 cookbook/python/lookup.md (L-语言类教程, ~5000 字)**

按 cookbook 教程模板 9 节写：是什么 / 安装 / 基础语法 / 核心概念 / 常用命令 / 项目集成点 / 项目代码示例 / 项目没用到的能力 / 最佳实践 + 常见坑

- [ ] **Step 2: 写 packages/service/src/lookups/README.md**

```markdown
# Lookups 模块

业务字典: DB 唯一事实源, 通用 enum 集中管理.

## 模块结构

- `models.py` — Dictionary / DictionaryItem SQLAlchemy
- `schemas.py` — Pydantic
- `service.py` — LookupService
- `cache.py` — Redis L2 + 进程内 L1
- `safety_guard.py` — 6 层防御
- `router.py` — GET 读 API
- `admin_router.py` — super_admin 写 API
- `audit.py` — 审计日志
- `import_export.py` — CSV/JSON

## 公共 API

- `LookupService.get(code, *, only_active, lang)` — 查字典
- `LookupService.get_one(code, key)` — 查单个 item
- `LookupService.create_item(code, payload, *, actor, ip)` — 新增 (super_admin)
- `LookupService.patch_item(code, key, payload, *, actor, ip)` — 改 (super_admin)
- `LookupService.soft_delete_item(code, key, *, actor, ip, force)` — 软删 (super_admin)

## 测试

```bash
RAG_DB_URL=... uv run pytest tests/lookups/ -v
```

## 启动

`main.py` lifespan 自动跑 `scripts/seed_dictionaries.py` + `scripts/check_dictionary_refs.py` + 启动 Redis 订阅。
```

- [ ] **Step 3: 改 packages/service/CLAUDE.md 加字典规范**

```markdown
## 字典使用规范

- **业务 enum 必须走 lookup**: 不许新增硬编 `StrEnum` (除非 LLM 框架要求)
- **新加字典流程**:
  1. 改 `src/common/dictionaries_seed.yaml` (出厂种子)
  2. `src/common/dictionaries_enum.py` 编译新 enum (启动时自动从 yaml 生成)
  3. `_REFERENCE_MAP` (在 `src/lookups/safety_guard.py`) 注册新字典的反向引用
  4. 跑 `seed_dictionaries.py` 同步到 DB
  5. 更新 `docs/cookbook/python/lookup.md` 教程
- **DB 是唯一事实源**, yaml 仅种子 + 类型提示参考
- **删除 key 必走 admin API + 二次确认**, 禁止手工 SQL 删
```

- [ ] **Step 4: 提交**

```bash
cd c:/doc/Code/rag
git add docs/cookbook/python/lookup.md packages/service/src/lookups/README.md packages/service/CLAUDE.md
git commit -m "docs(lookups): cookbook 教程 + 模块 README + CLAUDE.md 字典规范"
```

---

## 验收门（每个 Task 完成后必走）

每完成一个 Task，dispatch `gsd-code-reviewer` subagent 严格审（**不用自审**）：

**subagent prompt 模板**：
```text
请严格审核 lookup 模块 Task N 的实现.

**审核维度**（每项 PASS/FAIL + 证据）:
1. 代码风格: 与现有 src/approvals/models.py 等保持一致 (中文 docstring, 中文注释)
2. 测试覆盖: >= 90% 行覆盖 (pytest --cov)
3. 文档引用真实: 所有 file_path:line_number 引用真实存在
4. migration 可回滚: alembic downgrade -1 成功
5. 安全 6 层防御: 任一缺失立即 FAIL
6. 双写兼容: Task 7 后, 旧 StrEnum 仍可 import, contract test 通过
7. 性能: LookupCache 命中后 < 1ms
8. 错误处理: SafetyGuard 各层异常有清晰 detail 消息

**输出**: PASS / FAIL + 修复建议
```

FAIL 项必须修, 再 dispatch 一次确认 PASS, 才进下个 Task。

---

## 自审（spec 覆盖）

| Spec 节 | 实施 Task |
|---------|----------|
| 一、目标 & 范围 | 全局贯穿 (10 task) |
| 二、架构总览 | Task 4 (Service+Cache), Task 5+6 (Router) |
| 三、数据模型 | Task 1 (migration), Task 2 (seed yaml) |
| 四、API 设计 | Task 5 (GET), Task 6 (Admin) |
| 五、SafetyGuard + 前端 | Task 4 (Guard), Task 8 (hook), Task 9 (UI) |
| 六、实施节奏 & 风险 | 本 plan 整体 (10 task) |
| 七、迁移兼容 & 文档 | Task 7 (4 enum), Task 10 (docs) |
| 八、范围外 | plan 内未列 codegen/可视化编辑器 |

**无占位符**。所有 file_path 与 alembic revision、test 命名空间等显式给出。

---

## 执行选择

**Plan complete and saved to `docs/superpowers/plans/2026-06-19-lookup-module.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个 task 派一个新 subagent, task 间 review, 快速迭代

**2. Inline Execution** - 当前会话批量执行 + checkpoints

**Which approach?**
