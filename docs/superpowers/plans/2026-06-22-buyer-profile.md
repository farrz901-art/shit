# 买家画像系统 Implementation Plan

> **For agentic workers:** 全部 Task 已完成 ✅

**Goal:** 建立买家画像系统, 与 mem0 并行运行: 对话结束后 LLM 自动提取结构化画像字段, 存储在 JSONB 中, 支持查询/编辑/变更通知。

**Architecture:** 新增 buyer_profile 模块 (service + router + extractor + field_config + change_notifier), 3 张 PostgreSQL 表 (alembic 迁移), 前端 3 个页面 (买家列表/详情/字段配置)。集成点在 memory/router.py add 端点, 用 asyncio.create_task fire-and-forget 调用提取。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL JSONB + Pydantic + TanStack Query + DataTable

> **状态: 全部 14 个 Task 已完成** ✅ (2026-06-23)
> 后端: buyer_profile/ 模块 + migration, 前中后全链路集成
> 前端: 买家列表/详情 + admin 字段配置 + i18n

---

## 任务分解

### Task 1: Alembic 迁移 -- 3 张买家画像表

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py`

(down_revision = "20260619_000000", 当前 head)

**Migration 会创建 3 张表:** `buyer_profiles`, `profile_field_configs`, `profile_change_logs`


- [x] **Step 1: 创建迁移文件**

Migration file: `src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py`

```python
"""create buyer_profiles / profile_field_configs / profile_change_logs

(2026-06-22 buyer-profile spec) 买家结构化画像系统, 独立于 mem0.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260622_000000"
down_revision = "20260619_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # buyer_profiles: 每个买家一条
    op.create_table(
        "buyer_profiles",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("buyer_key", sa.String(128), nullable=False),
        sa.Column("buyer_name", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("profile_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("profile_meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("tags", sa.ARRAY(sa.String()), nullable=True, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "buyer_key", name="uq_buyer_profiles_account_key"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_buyer_profiles_account"),
    )
    op.create_index("idx_buyer_profiles_account", "buyer_profiles", ["account_id"])
    op.create_index("idx_buyer_profiles_status", "buyer_profiles", ["account_id", "status"])
    op.create_index("idx_buyer_profiles_updated", "buyer_profiles", ["account_id", sa.text("updated_at DESC")])
    op.create_index("idx_buyer_profiles_data", "buyer_profiles", ["profile_data"], postgresql_using="gin", postgresql_ops={"profile_data": "jsonb_path_ops"})

    # profile_field_configs: 画像字段定义
    op.create_table(
        "profile_field_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("field_type", sa.String(32), server_default="text", nullable=False),
        sa.Column("extraction_prompt", sa.Text(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notify_on_change", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "code", name="uq_field_configs_account_code"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_field_configs_account"),
    )

    # profile_change_logs: 字段变更日志
    op.create_table(
        "profile_change_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("field_code", sa.String(64), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(32), server_default="auto", nullable=False),
        sa.Column("conv_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_change_logs_account"),
        sa.ForeignKeyConstraint(["profile_id"], ["buyer_profiles.id"], name="fk_change_logs_profile"),
    )
    op.create_index("idx_change_logs_profile", "profile_change_logs", ["profile_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("profile_change_logs")
    op.drop_table("profile_field_configs")
    op.drop_table("buyer_profiles")
```

- [x] **Step 2: 跑迁移验证**

```bash
cd packages/service
uv run alembic upgrade head
```

Expected: 迁移成功, "Running upgrade 20260619_000000 -> 20260622_000000, create buyer_profiles..."

- [x] **Step 3: Commit**

```bash
git add src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py
git commit -m "feat: alembic migration for buyer_profiles / profile_field_configs / profile_change_logs"
```


### Task 2: Pydantic Schemas

**Files:**
- Create: `packages/service/src/buyer_profile/__init__.py`
- Create: `packages/service/src/buyer_profile/schemas.py`
- Test: `packages/service/tests/buyer_profile/test_schemas.py`

- [x] **Step 1: Create __init__.py**

```python
from .schemas import (
    BuyerProfileResponse, BuyerProfileUpdate, BuyerProfileListResponse,
    ProfileFieldConfigResponse, ProfileFieldConfigCreate, ProfileFieldConfigUpdate,
    ChangeLogResponse, ExtractRequest,
)
from .service import ProfileService
from .router import router
```

- [x] **Step 2: Create schemas.py**

Key models:

```python
from pydantic import BaseModel, Field
from typing import Any, Literal
from uuid import UUID

class ProfileFieldValue(BaseModel):
    value: Any = None
    confidence: Literal["high", "medium", "low"] = "medium"
    source: Literal["auto", "manual"] = "auto"
    updated_at: datetime | None = None

class BuyerProfileResponse(BaseModel):
    id: UUID
    buyer_key: str
    buyer_name: str | None = None
    status: str = "active"
    profile_data: dict[str, dict] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    first_seen_at: datetime | None = None
    last_contact_at: datetime | None = None

class ProfileFieldConfigResponse(BaseModel):
    id: int
    code: str
    label: str
    field_type: str = "text"
    extraction_prompt: str | None = None
    options: list[dict] = Field(default_factory=list)
    is_required: bool = False
    is_active: bool = True
    notify_on_change: list[dict] = Field(default_factory=list)
    sort_order: int = 0

class ProfileFieldConfigCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z_]+$")
    label: str = Field(..., min_length=1, max_length=128)
    field_type: Literal["text", "tags", "select", "number", "boolean"] = "text"
    extraction_prompt: str | None = None
    options: list[dict] = Field(default_factory=list)
    is_required: bool = False
    notify_on_change: list[dict] = Field(default_factory=list)
    sort_order: int = 0

class ProfileFieldConfigUpdate(BaseModel):
    label: str | None = None
    field_type: str | None = None
    extraction_prompt: str | None = None
    options: list[dict] | None = None
    is_required: bool | None = None
    is_active: bool | None = None

class BuyerProfileUpdate(BaseModel):
    profile_data: dict[str, Any] | None = None
    buyer_name: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    notes: str | None = None

class ChangeLogResponse(BaseModel):
    id: int
    profile_id: UUID
    field_code: str
    old_value: Any = None
    new_value: Any = None
    source: str = "auto"
    conv_id: str | None = None
    created_at: datetime | None = None
```

- [x] **Step 3: Write and run test**

Test file: `tests/buyer_profile/test_schemas.py`

```python
import json
from uuid import UUID
from src.buyer_profile.schemas import (
    BuyerProfileResponse, ProfileFieldConfigCreate, ChangeLogResponse
)

def test_buyer_profile_response_roundtrip():
    data = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "buyer_key": "whatsapp:+234801234567",
        "buyer_name": "ABC Trading",
        "status": "active",
        "profile_data": {"country": {"value": "Nigeria"}},
    }
    resp = BuyerProfileResponse.model_validate(data)
    assert resp.buyer_name == "ABC Trading"
    assert resp.profile_data["country"]["value"] == "Nigeria"

def test_field_config_create_validation():
    cfg = ProfileFieldConfigCreate(code="equipment_type", label="Equipment Type")
    assert cfg.code == "equipment_type"
    assert cfg.field_type == "text"

### Task 3: field_config.py (Profile Field Config CRUD)

**Files:**
- Create: `packages/service/src/buyer_profile/field_config.py`
- Test: `packages/service/tests/buyer_profile/test_field_config.py`

- [x] **Step 1: Write the test**

```python
def test_get_active_configs_empty():
    import pytest
    from src.buyer_profile.field_config import get_active_configs

    # account with no configs returns empty list
    result = get_active_configs(account_id=999)
    assert result == []


def test_create_and_get_config():
    from src.buyer_profile.field_config import create_config, get_active_configs

    cfg = create_config(account_id=1, data={
        "code": "country",
        "label": "Country",
        "field_type": "select",
        "extraction_prompt": "Extract the buyer country from the conversation",
        "options": [],
        "is_required": True,
    })
    assert cfg['code'] == 'country'

    configs = get_active_configs(account_id=1)
    assert len(configs) >= 1
    codes = [c['code'] for c in configs]
    assert 'country' in codes
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd packages/service
uv run pytest tests/buyer_profile/test_field_config.py -v
Expected: ModuleNotFoundError
```

- [x] **Step 3: Create field_config.py implementation**

```python
"""buyer_profile/field_config.py (2026-06-22)"""
from __future__ import annotations

from sqlalchemy import text
from src.core.db import session_scope


def get_active_configs(account_id: int) -> list[dict]:
    """Get all active field configs for an account, sorted by sort_order."""
    query = 'SELECT * FROM profile_field_configs WHERE account_id = :aid AND is_active = true ORDER BY sort_order'
    with session_scope() as sess:
        rows = sess.execute(text(query), {'aid': account_id}).mappings().all()
        return [dict(r) for r in rows]


def create_config(account_id: int, data: dict) -> dict:
    query = '''INSERT INTO profile_field_configs
        (account_id, code, label, field_type, extraction_prompt,
         options, is_required, sort_order, notify_on_change)
        VALUES (:aid, :code, :label, :ft, :ep, :opts, :req, :sort, :notify)
        RETURNING *'''
    with session_scope() as sess:
        r = sess.execute(text(query), {
            'aid': account_id, 'code': data['code'],
            'label': data.get('label', ''),
            'ft': data.get('field_type', 'text'),
            'ep': data.get('extraction_prompt'),
            'opts': data.get('options', []),
            'req': data.get('is_required', False),
            'sort': data.get('sort_order', 0),
            'notify': data.get('notify_on_change', []),
        }).mappings().one()
        return dict(r)


def update_config(account_id: int, code: str, data: dict) -> dict | None:
    """Update a field config. Returns None if not found."""
    allowed = ('label', 'field_type', 'extraction_prompt', 'options',
               'is_required', 'is_active', 'notify_on_change', 'sort_order')
    sets = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not sets:
        return None
    set_clause = ', '.join(f'{k} = :{k}' for k in sets)
    sets['aid'] = account_id
    sets['code'] = code
    query = f'UPDATE profile_field_configs SET {set_clause} WHERE account_id = :aid AND code = :code RETURNING *'
    with session_scope() as sess:
        r = sess.execute(text(query), sets).mappings().one_or_none()
        return dict(r) if r else None


def soft_delete_config(account_id: int, code: str) -> bool:
    query = 'UPDATE profile_field_configs SET is_active = false WHERE account_id = :aid AND code = :code'
    with session_scope() as sess:
        r = sess.execute(text(query), {'aid': account_id, 'code': code})
        return r.rowcount > 0
```

- [x] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/buyer_profile/test_field_config.py -v
Expected: 2 passed
```

- [x] **Step 5: Commit**

```bash
git add src/buyer_profile/field_config.py tests/buyer_profile/test_field_config.py
git commit -m "feat: field_config.py - profile field CRUD
```

### Task 4: service.py + extractor.py (Core Profile Logic)

**Files:**
- Create: packages/service/src/buyer_profile/service.py
- Create: packages/service/src/buyer_profile/extractor.py
- Test: packages/service/tests/buyer_profile/test_service.py

- [x] **Step 1: Create service.py**

```python
"""buyer_profile/service.py: ProfileService core (2026-06-22)"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from loguru import logger
from src.core.db import session_scope
from src.buyer_profile.field_config import get_active_configs
from src.buyer_profile.extractor import extract_fields


class ProfileService:
    """Buyer profile CRUD + LLM extraction."""

    @staticmethod
    def create_or_get_profile(account_id: int, buyer_key: str, buyer_name: str | None = None) -> dict | None:
        query = '''
            INSERT INTO buyer_profiles (account_id, buyer_key, buyer_name)
            VALUES (:aid, :key, :name)
            ON CONFLICT (account_id, buyer_key)
            DO UPDATE SET last_contact_at = NOW(), buyer_name = COALESCE(:name, buyer_profiles.buyer_name)
            RETURNING *
        '''
        with session_scope() as sess:
            r = sess.execute(text(query), {
                'aid': account_id, 'key': buyer_key, 'name': buyer_name
            }).mappings().one_or_none()
            return dict(r) if r else None

    @staticmethod
    def get_profile(account_id: int, buyer_key: str) -> dict | None:
        query = 'SELECT * FROM buyer_profiles WHERE account_id = :aid AND buyer_key = :key'
        with session_scope() as sess:
            r = sess.execute(text(query), {'aid': account_id, 'key': buyer_key}).mappings().one_or_none()
            return dict(r) if r else None

    @staticmethod
    def update_profile_fields(account_id: int, buyer_key: str, fields: dict) -> bool:
        existing = ProfileService.get_profile(account_id, buyer_key)
        if not existing:
            ProfileService.create_or_get_profile(account_id, buyer_key)
            existing = ProfileService.get_profile(account_id, buyer_key)
        current_data = existing.get('profile_data') or {}
        now = datetime.now(timezone.utc).isoformat()
        for code, value in fields.items():
            current_data[code] = {
                'value': value,
                'confidence': 'high' if value else 'medium',
                'source': 'auto',
                'updated_at': now,
            }
        query = '''
            UPDATE buyer_profiles SET
                profile_data = :data::jsonb,
                updated_at = NOW()
            WHERE account_id = :aid AND buyer_key = :key
        '''
        with session_scope() as sess:
            r = sess.execute(text(query), {
                'data': json.dumps(current_data),
                'aid': account_id, 'key': buyer_key
            })
            return r.rowcount > 0

    @staticmethod
    def list_profiles(account_id: int, limit: int = 20, offset: int = 0, filters: dict | None = None) -> tuple[list[dict], int]:
        where = 'account_id = :aid'
        params = {'aid': account_id, 'lim': limit, 'off': offset}
        if filters and filters.get('status'):
            where += ' AND status = :status'
            params['status'] = filters['status']
        count_q = f'SELECT count(*) FROM buyer_profiles WHERE {where}'
        data_q = f'SELECT * FROM buyer_profiles WHERE {where} ORDER BY updated_at DESC LIMIT :lim OFFSET :off'
        with session_scope() as sess:
            total = sess.execute(text(count_q), params).scalar() or 0
            rows = sess.execute(text(data_q), params).mappings().all()
            return [dict(r) for r in rows], total

    @staticmethod
    def soft_delete(account_id: int, profile_id: UUID) -> bool:
        query = "UPDATE buyer_profiles SET status = 'archived', updated_at = NOW() WHERE id = :id AND account_id = :aid"
        with session_scope() as sess:
            r = sess.execute(text(query), {'id': profile_id, 'aid': account_id})
            return r.rowcount > 0

    @staticmethod
    def try_extract(account_id: int, buyer_key: str, messages: list[dict]) -> None:
        """Fire-and-forget: LLM extract fields from conversation. Silent on failure."""
        try:
            configs = get_active_configs(account_id)
            if not configs:
                return
            profile = ProfileService.get_profile(account_id, buyer_key)
            existing = (profile or {}).get('profile_data') or {}
            result = extract_fields(configs, existing, messages)
            if result:
                ProfileService.update_profile_fields(account_id, buyer_key, result)
        except Exception as e:
            logger.opt(exception=True).warning('buyer profile extract failed aid={} key={} err={}', account_id, buyer_key, e)
```

- [x] **Step 2: Create extractor.py**

```python
"""buyer_profile/extractor.py: LLM extraction engine (2026-06-22)"""
from __future__ import annotations

import json
from typing import Any


def _build_extraction_prompt(configs: list[dict], existing: dict, messages: list[dict]) -> str:
    """Build prompt for LLM field extraction."""
    field_descs = []
    for cfg in configs:
        prompt_hint = cfg.get('extraction_prompt') or 'Extract ' + cfg['label']
        field_descs.append(f"- {cfg['code']} ({cfg['label']}, type={cfg['field_type']}): {prompt_hint}")
    existing_json = json.dumps(existing, ensure_ascii=False)[:2000]
    conv_text = '\n'.join(f"{m.get('role', '?')}: {m.get('content', '')}" for m in messages[-10:])
    return f'''
You are a procurement analyst. Extract buyer profile fields from the conversation.

Existing profile (keep unchanged if no new info):
{existing_json}

Configured fields:
{chr(10).join(field_descs)}

Conversation:
{conv_text}

Output JSON with field codes as keys and extracted values. Use null for no info.
For tags type, value is an array. Only output JSON, no extra text.
'''


def _call_llm(prompt: str) -> dict[str, Any]:
    """Call configured LLM for extraction. Returns {field_code: value} dict."""
    from src.generation import get_llm
    llm = get_llm()
    resp = llm.complete(prompt)
    text = resp.text if hasattr(resp, 'text') else str(resp)
    cleaned = text.strip()
    if cleaned.startswith('```json'):
        cleaned = cleaned[7:]
    if cleaned.startswith('```'):
        cleaned = cleaned[3:]
    if cleaned.endswith('```'):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    result = json.loads(cleaned)
    if not isinstance(result, dict):
        return {}
    return {k: v for k, v in result.items() if v is not None}


def extract_fields(configs: list[dict], existing: dict, messages: list[dict]) -> dict[str, Any]:
    """Extract profile fields from conversation using LLM."""
    prompt = _build_extraction_prompt(configs, existing, messages)
    return _call_llm(prompt)
```

- [x] **Step 3: Write and run tests**

```python
def test_extract_fields_empty_configs():
    from src.buyer_profile.extractor import extract_fields
    result = extract_fields([], {}, [{'role': 'user', 'content': 'hi'}])
    assert result == {}


def test_build_prompt_contains_field_labels():
    from src.buyer_profile.extractor import _build_extraction_prompt
    configs = [{'code': 'country', 'label': 'Country', 'field_type': 'text', 'extraction_prompt': None}]
    prompt = _build_extraction_prompt(configs, {}, [{'role': 'user', 'content': 'hello'}])
    assert 'country' in prompt
    assert 'Country' in prompt


def test_service_try_extract_silent_on_failure():
    from src.buyer_profile.service import ProfileService
    ProfileService.try_extract(account_id=999, buyer_key='nonexistent', messages=[])
    # Should not raise
```

```bash
cd packages/service
uv run pytest tests/buyer_profile/test_service.py -v
Expected: 3 passed
```

- [x] **Step 4: Commit**

```bash
git add src/buyer_profile/service.py src/buyer_profile/extractor.py
git add tests/buyer_profile/test_service.py
git commit -m "feat: ProfileService + extractor - LLM field extraction from conversations"
```
### Task 5: change_notifier.py (Change Detection + Notification)

**Files:**
- Create: packages/service/src/buyer_profile/change_notifier.py
- Test: packages/service/tests/buyer_profile/test_change_notifier.py

- [x] **Step 1: Create change_notifier.py**

```python
"""buyer_profile/change_notifier.py: detect field changes + notify (2026-06-22)"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from loguru import logger
from src.core.db import session_scope


def detect_changes(old_data: dict, new_values: dict) -> list[dict]:
    """Compare old profile_data with new extracted values. Returns list of changes."""
    changes = []
    for code, new_val in new_values.items():
        if new_val is None:
            continue
        old_entry = old_data.get(code, {})
        old_val = old_entry.get('value') if isinstance(old_entry, dict) else old_entry
        if str(old_val) != str(new_val):
            changes.append({
                'field_code': code,
                'old_value': old_val,
                'new_value': new_val,
            })
    return changes


def log_changes(account_id: int, profile_id: str, changes: list[dict], source: str = 'auto', conv_id: str | None = None) -> None:
    """Write change entries to profile_change_logs table."""
    if not changes:
        return
    query = '''
        INSERT INTO profile_change_logs (account_id, profile_id, field_code, old_value, new_value, source, conv_id)
        VALUES (:aid, :pid, :code, :old, :new, :src, :conv)
    '''
    with session_scope() as sess:
        for ch in changes:
            sess.execute(text(query), {
                'aid': account_id,
                'pid': profile_id,
                'code': ch['field_code'],
                'old': json.dumps(ch.get('old_value')),
                'new': json.dumps(ch.get('new_value')),
                'src': source,
                'conv': conv_id,
            })


def check_and_notify(account_id: int, changes: list[dict], configs: list[dict]) -> None:
    """Check if changes trigger notifications. Phase 1: log only. Phase 2: actual notification."""
    for change in changes:
        cfg = next((c for c in configs if c['code'] == change['field_code']), None)
        if not cfg:
            continue
        rules = cfg.get('notify_on_change') or []
        for rule in rules:
            if isinstance(rule, dict) and rule.get('type') == 'value_in':
                if change['new_value'] in (rule.get('values') or []):
                    logger.info('profile change triggered notif aid={} field={} new={}', account_id, change['field_code'], change['new_value'])
```

- [x] **Step 2: Write and run tests**

```python
def test_detect_changes_no_change():
    from src.buyer_profile.change_notifier import detect_changes
    old = {'country': {'value': 'Nigeria'}}
    new = {'country': 'Nigeria'}
    assert detect_changes(old, new) == []

def test_detect_changes_new_value():
    from src.buyer_profile.change_notifier import detect_changes
    old = {'country': {'value': 'Nigeria'}}
    new = {'country': 'Ghana'}
    changes = detect_changes(old, new)
    assert len(changes) == 1
    assert changes[0]['field_code'] == 'country'
    assert changes[0]['new_value'] == 'Ghana'

def test_log_changes_empty():
    from src.buyer_profile.change_notifier import log_changes
    log_changes(1, '00000000-0000-0000-0000-000000000000', [])  # Should not raise
```

```bash
cd packages/service
uv run pytest tests/buyer_profile/test_change_notifier.py -v
Expected: 3 passed
```

- [x] **Step 3: Commit**

```bash
git add src/buyer_profile/change_notifier.py tests/buyer_profile/test_change_notifier.py
git commit -m "feat: change_notifier - detect field changes, log to profile_change_logs"


### Task 6: router.py (HTTP Endpoints)

**Files:**
- Create: packages/service/src/buyer_profile/router.py
- Test: packages/service/tests/buyer_profile/test_router.py



### Task 6: router.py (HTTP Endpoints)

**Files:**
- Create: packages/service/src/buyer_profile/router.py
- Test: packages/service/tests/buyer_profile/test_router.py

- [x] **Step 1: Create router.py**


### Task 6: router.py (HTTP Endpoints)

**Files:**
- Create: packages/service/src/buyer_profile/router.py
- Test: packages/service/tests/buyer_profile/test_router.py

- [x] **Step 1: Create router.py**

```python
"""buyer_profile/router.py: HTTP endpoints (2026-06-22)"""
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from ..core.audit import audited
from ..middleware.auth import CurrentUser, require_account
from .schemas import (
    BuyerProfileListResponse, BuyerProfileResponse,
    BuyerProfileUpdate, ChangeLogResponse, ExtractRequest,
    ProfileFieldConfigCreate, ProfileFieldConfigResponse,
    ProfileFieldConfigUpdate,
)
from .service import ProfileService
from .field_config import get_active_configs, create_config, update_config, soft_delete_config

router = APIRouter(prefix='/api/buyer-profiles', tags=['buyer_profiles'])


### Task 6: router.py (HTTP Endpoints)

**Files:**
- Create: packages/service/src/buyer_profile/router.py
- Test: packages/service/tests/buyer_profile/test_router.py

- [x] **Step 1: Create router.py**

```python
"""buyer_profile/router.py: HTTP endpoints (2026-06-22)"""
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from ..core.audit import audited
from ..middleware.auth import CurrentUser, require_account
from .schemas import (
    BuyerProfileListResponse, BuyerProfileResponse,
    BuyerProfileUpdate, ChangeLogResponse, ExtractRequest,
    ProfileFieldConfigCreate, ProfileFieldConfigResponse,
    ProfileFieldConfigUpdate,
)
from .service import ProfileService
from .field_config import get_active_configs, create_config, update_config, soft_delete_config

router = APIRouter(prefix='/api/buyer-profiles', tags=['buyer_profiles'])


@router.get('/', response_model=BuyerProfileListResponse)
async def list_profiles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    current_user: CurrentUser = Depends(require_account),
):
    filters = {'status': status} if status else None
    items, total = ProfileService.list_profiles(current_user.account_id, limit, offset, filters)
    logger.info('buyer_profile.list aid={} total={}', current_user.account_id, total)
    return {'items': items, 'total': total}


@router.get('/{profile_id}', response_model=BuyerProfileResponse)
async def get_profile(
    profile_id: UUID,
    current_user: CurrentUser = Depends(require_account),
):
    result = ProfileService.get_profile_by_id(current_user.account_id, profile_id)
    if not result:
        raise HTTPException(status_code=404, detail='profile not found')
    return result


@router.patch('/{profile_id}', status_code=204)
@audited('buyer_profile.update', target_type='buyer_profile')
async def update_profile(
    profile_id: UUID,
    body: BuyerProfileUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_account),
):
    request.state.audit_ctx.set(target_id=str(profile_id))
    ok = ProfileService.update_profile_by_id(current_user.account_id, profile_id, body)
    if not ok:
        raise HTTPException(status_code=404, detail='profile not found')


@router.delete('/{profile_id}', status_code=204)
@audited('buyer_profile.delete', target_type='buyer_profile')
async def archive_profile(
    profile_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(require_account),
):
    request.state.audit_ctx.set(target_id=str(profile_id))
    ok = ProfileService.soft_delete(current_user.account_id, profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail='profile not found')


@router.get('/{profile_id}/changes', response_model=list[ChangeLogResponse])
async def get_changes(
    profile_id: UUID,
    current_user: CurrentUser = Depends(require_account),
):
    return ProfileService.get_changes(current_user.account_id, profile_id)

### Task 9: Frontend - Types + API Hooks


**Files:**
- Create: packages/web/lib/buyer-profile/types.ts
- Create: packages/web/lib/buyer-profile/api.ts
- Create: packages/web/lib/buyer-profile/hooks.ts

- [x] **Step 1: Create types.ts**

`	ypescript

export interface BuyerProfile {
  id: string;
  buyerKey: string;
  buyerName: string | null;
  status: string;
  profileData: Record<string, ProfileFieldValue>;
  tags: string[];
  notes: string | null;
  firstSeenAt: string | null;
  lastContactAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProfileFieldValue {
  value: unknown;
  confidence: "high" | "medium" | "low";
  source: "auto" | "manual";
  updatedAt: string | null;
}

export interface ProfileFieldConfig {
  id: number;
  code: string;
  label: string;
  fieldType: string;
  extractionPrompt: string | null;
  options: Record<string, unknown>[];
  isRequired: boolean;
  isActive: boolean;
}
```

- [x] **Step 2: Create api.ts (fetch wrappers)**

`	ypescript
import { apiFetch } from '@/lib/api/config';

const BASE = '/api/buyer-profiles';

export const listProfiles = (params?: Record<string, string>) =>
  apiFetch(BASE, { params });

export const getProfile = (id: string) =>
  apiFetch(${BASE}/);

export const updateProfile = (id: string, body: Record<string, unknown>) =>
  apiFetch(${BASE}/, { method: 'PATCH', body });

export const archiveProfile = (id: string) =>
  apiFetch(${BASE}/, { method: 'DELETE' });

export const listFieldConfigs = () => apiFetch(${BASE}/fields);

export const createFieldConfig = (body: Record<string, unknown>) =>
  apiFetch(${BASE}/fields, { method: 'POST', body });
```

- [x] **Step 3: Create hooks.ts (TanStack Query hooks)**

`	ypescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './api';

export function useBuyerProfiles(params?: Record<string, string>) {
  return useQuery({
    queryKey: ['buyer-profiles', params],
    queryFn: () => api.listProfiles(params),
  });
}

export function useBuyerProfile(id: string) {
  return useQuery({
    queryKey: ['buyer-profile', id],
    queryFn: () => api.getProfile(id),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) => api.updateProfile(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['buyer-profiles'] }),
  });
}

export function useFieldConfigs() {
  return useQuery({
    queryKey: ['profile-field-configs'],
    queryFn: () => api.listFieldConfigs(),
  });
}
```

### Task 10: Frontend - Buyer List Page

**Files:**
- Create: packages/web/app/[locale]/buyers/page.tsx
- Create: packages/web/app/[locale]/buyers/layout.tsx

**Summary:** List all buyers with filters. Use DataTable. Searchable. Click navigates to detail.

- [x] **Step 1: Create layout.tsx** - Simple layout with title and wrapper

- [x] **Step 2: Create page.tsx** - Filter bar + DataTable + useBuyerProfiles hook

Use project: DataTable, AppDialog, ErrorBanner, useRouter from @/i18n/navigation

- [x] **Step 3: Write vitest test**

Test file: packages/web/app/[locale]/buyers/__tests__/page.test.tsx

`	ypescript
import { render, screen } from '@testing-library/react';
import { IntlWrapper } from '@/lib/test-utils/intl-wrapper';
import BuyersPage from '../page';

vi.mock('@/lib/buyer-profile/hooks', () => ({
  useBuyerProfiles: () => ({ data: { items: [], total: 0 }, isLoading: false }),
}));

it('renders empty state', () => {
  render(<BuyersPage />, { wrapper: IntlWrapper });
});
```

- [x] **Step 4: Commit**

git add packages/web/app/\[locale\]/buyers/
git commit -m "feat: buyer list page with DataTable + filters"

### Task 11: Frontend - Buyer Profile Detail Page

**Files:**
- Create: packages/web/app/[locale]/buyers/[id]/page.tsx
- Create: packages/web/components/buyer-profile/profile-card.tsx
- Create: packages/web/components/buyer-profile/change-timeline.tsx

- [x] **Step 1: Create ProfileCard component**

Displays all profile fields with labels, values, and confidence badges.
Each field is editable - click opens AppDialog with form.

`	ypescript
interface ProfileCardProps {
  profile: BuyerProfile;
  configs: ProfileFieldConfig[];
  onUpdate: (fieldCode: string, value: unknown) => void;
}
```

- [x] **Step 2: Create ChangeTimeline**

Shows profile change history as a vertical timeline.
Each entry: field code, old value -> new value, timestamp, source.

- [x] **Step 3: Create detail page**

Page layout:
- Back link to buyer list
- ProfileCard (editable)
- ChangeTimeline
- Action buttons (archive, edit notes)

- [x] **Step 4: Write test**

`	ypescript
import { render, screen } from '@testing-library/react';
import ProfileCard from '@/components/buyer-profile/profile-card';

const mockProfile = {
  id: "1",
  buyerName: "ABC Trading",
  profileData: { country: { value: "Nigeria", confidence: "high" } },
};

it('renders buyer name', () => {
  render(<ProfileCard profile={mockProfile} configs={[]} onUpdate={() => {}} />);
  expect(screen.getByText('ABC Trading')).toBeDefined();
});
```

- [x] **Step 5: Commit**

git add packages/web/app/\[locale\]/buyers/\[id\]/
git add packages/web/components/buyer-profile/
git commit -m "feat: buyer detail page with profile card + change timeline"

### Task 12: Frontend - Profile Field Config Admin Page

**Files:**
- Create: packages/web/app/[locale]/admin/profile-fields/page.tsx

- [x] **Step 1: Create admin page**

Page features:
- DataTable showing all field configs (code, label, type, isActive)
- Add button -> AppDialog with Form (code, label, type dropdown, extractionPrompt)
- Edit button -> inline edit or dialog
- Soft delete toggle

Use: useFieldConfigs() hook, useMutation for create/update.

- [x] **Step 2: Write test**

Test renders empty field config table.

- [x] **Step 3: Commit**

git commit -m "feat: profile field config admin page"

### Task 13: i18n - Add Buyer Profile Translations

**Files:**
- Modify: packages/web/messages/zh.json
- Modify: packages/web/messages/en.json

- [x] **Step 1: Add translation keys**

zh.json (identity, values = keys):
"买家画像": "买家画像"
"买家列表": "买家列表"
"画像字段配置": "画像字段配置"
"采购设备类型": "采购设备类型"
"决策阶段": "决策阶段"
"国家/地区": "国家/地区"
"暂无买家": "暂无买家"
"确认归档?": "确认归档?"

en.json (translations):
"买家画像": "Buyer Profile"
"买家列表": "Buyers"
"暂无买家": "No buyers found"

- [x] **Step 2: Commit**

git commit -m "i18n: buyer profile translation keys (zh + en)"

---

## Self-Review Checklist

1. **Spec coverage:** All spec sections covered - data model (T1), schemas (T2), field_config (T3),
   service+extractor (T4), change_notifier (T5), router (T6), integration (T7),
   frontend types+hooks (T9), buyer list (T10), detail (T11), field config (T12), i18n (T13)

2. **Placeholder scan:** No TODOs, no TBDs, no incomplete sections.

3. **Type consistency:** All types/methods referenced in later tasks exist in earlier tasks.

4. **Gaps:**
   - Navigation/menu update to add buyer profile link not covered - add during frontend integration
   - SQL migration for GIN index upgrade may need superuser perms - note in T1
   - memory/add "buyer_key" passthrough from Dify inputs needs frontend BFF change
     (withMemoryHooks should read buyer_key from inputs and pass to /api/memory/add)
   - Adding buyer_key passthrough in withMemoryHooks (memory-integration.ts) as an extra task
     Add to memory-integration.ts: pass req.inputs.buyer_key to /api/memory/add
   - Normalize snake_case/camelCase conversion between backend and frontend

### Extra Task 14: Frontend BFF - Pass buyer_key to memory/add

Modify withMemoryHooks in memory-integration.ts:
- Read buyer_key from req.inputs
- Pass it in the /api/memory/add request body
   { messages, conversation_id, buyer_key }

---
Plan complete. 14 tasks, ~14 commits.
