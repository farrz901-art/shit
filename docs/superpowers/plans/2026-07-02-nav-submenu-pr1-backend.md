# PR1 — Backend: Page Metadata Passthrough + Dictionary Seed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the frontend to read `metadata_json` fields (`parent_id`, `is_group`, `icon`) from `page_key` dictionary items, and seed the dictionary with the new admin sub-pages and parent metadata.

**Files:**
- Modify: `packages/service/config/dictionaries_seed.yaml` (lines 56-124)
- Modify: `packages/service/src/permissions/cache.py:79-106` (passthrough `metadata`)
- Test: `packages/service/tests/permissions/test_cache.py` (new file, mock-based per project CLAUDE.md §测试隔离 4 模式 模式 1)
- Create: `packages/service/alembic/versions/XXXX_seed_admin_subpages.py` (NO — skip alembic; pure seed update)

---

## Task 1.1: Update yaml seed with new admin sub-pages and parent metadata

**Files:**
- Modify: `packages/service/config/dictionaries_seed.yaml:56-124`

- [ ] **Step 1: Read current yaml page_key section**

Run: `cat packages/service/config/dictionaries_seed.yaml | sed -n '56,125p'`

Expected: 10 page_key items as listed in spec §2.1.

- [ ] **Step 2: Rewrite page_key items in-place**

Replace the entire `items:` array under `- code: page_key` (lines 60-124) with the following content:

```yaml
    items:
      # === 顶级 (parent_id 缺省) ===
      - {
          key: admin,
          label_zh: 管理中心,
          label_en: Admin,
          sort: 50,
          metadata_json: { path: "/admin", is_group: true, icon: "shield" },
        }
      - {
          key: chat,
          label_zh: 对话,
          label_en: Chat,
          sort: 10,
          metadata_json: { path: "/chat", icon: "message-circle" },
        }
      - {
          key: output,
          label_zh: 文档结构化,
          label_en: Output,
          sort: 20,
          metadata_json: { path: "/output", icon: "file-text" },
        }
      - {
          key: knowledge,
          label_zh: 知识库,
          label_en: Knowledge,
          sort: 30,
          metadata_json: { path: "/knowledge", icon: "book-open" },
        }
      - {
          key: evaluate,
          label_zh: 评估,
          label_en: Evaluate,
          sort: 40,
          metadata_json: { path: "/evaluate", icon: "check-circle" },
        }
      - {
          key: submissions,
          label_zh: 审核中心,
          label_en: Submissions,
          sort: 60,
          metadata_json: { path: "/submissions", icon: "clipboard-check" },
        }
      - {
          key: decode,
          label_zh: 型号解析,
          label_en: Decode,
          sort: 70,
          metadata_json: { path: "/decode", icon: "scan" },
        }
      - {
          key: health,
          label_zh: 监控,
          label_en: Health,
          sort: 80,
          metadata_json: { path: "/health", icon: "activity" },
        }
      - {
          key: buyers,
          label_zh: 客户画像,
          label_en: Buyers,
          sort: 90,
          metadata_json: { path: "/buyers", icon: "users" },
        }

      # === 子页 (parent_id 指向顶级) ===
      - {
          key: knowledge_extract,
          label_zh: 知识图谱抽取,
          label_en: KG Extract,
          sort: 31,
          metadata_json: { path: "/knowledge/extract", parent_id: "knowledge" },
        }
      - {
          key: admin_users,
          label_zh: 用户管理,
          label_en: Users,
          sort: 51,
          metadata_json: { path: "/admin/users", parent_id: "admin" },
        }
      - {
          key: admin_invites,
          label_zh: 邀请码,
          label_en: Invites,
          sort: 52,
          metadata_json: { path: "/admin/invites", parent_id: "admin" },
        }
      - {
          key: admin_permissions,
          label_zh: 权限管理,
          label_en: Permissions,
          sort: 53,
          metadata_json: { path: "/admin/permissions", parent_id: "admin" },
        }
      - {
          key: admin_dicts,
          label_zh: 字典管理,
          label_en: Dicts,
          sort: 54,
          metadata_json: { path: "/admin/dicts", parent_id: "admin" },
        }
      - {
          key: admin_profile_fields,
          label_zh: 画像字段配置,
          label_en: Profile Fields,
          sort: 55,
          metadata_json: { path: "/admin/profile-fields", parent_id: "admin" },
        }
```

- [ ] **Step 3: Verify yaml validity**

Run: `python -c "import yaml; yaml.safe_load(open('packages/service/config/dictionaries_seed.yaml'))"`

Expected: no output, exit code 0.

- [ ] **Step 4: Run seed script in dry-run (no DB write)**

Run: `cd packages/service && uv run python -m scripts.seed_dictionaries --help`

Expected: prints usage (no DB writes).

- [ ] **Step 5: Commit yaml change**

```bash
cd c:/doc/Code/rag
git add packages/service/config/dictionaries_seed.yaml
git commit -m "feat(seed): add parent_id/is_group/icon to page_key items (PR1/1)

5 new sub-pages (admin_users/invites/permissions/dicts/profile_fields)
+ knowledge_extract child of knowledge.
Metadata drives nav submenu (PR3) + permission matrix tree (PR6)."
```

---

## Task 1.2: Add failing test for metadata passthrough in cache.py

**Files:**
- Create: `packages/service/tests/permissions/test_cache.py`

- [ ] **Step 1: Create test directory and file**

```bash
mkdir -p packages/service/tests/permissions
```

Create `packages/service/tests/permissions/test_cache.py`:

```python
"""测试 get_all_page_metadata() 透传 metadata_json 整块到前端 (2026-07-02 nav spec §2.2).

模式 1 mock: 不连真 PG/Redis, mock LookupService.get 返假数据.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def fake_page_keys() -> list[dict]:
    return [
        {
            "key": "admin",
            "label_zh": "管理中心",
            "label_en": "Admin",
            "metadata_json": {"path": "/admin", "is_group": True, "icon": "shield"},
            "is_active": True,
        },
        {
            "key": "admin_users",
            "label_zh": "用户管理",
            "label_en": "Users",
            "metadata_json": {"path": "/admin/users", "parent_id": "admin"},
            "is_active": True,
        },
        {
            "key": "chat",
            "label_zh": "对话",
            "label_en": "Chat",
            "metadata_json": {"path": "/chat"},
            "is_active": True,
        },
        {
            "key": "knowledge_extract",
            "label_zh": "知识图谱抽取",
            "label_en": "KG Extract",
            "metadata_json": {"path": "/knowledge/extract", "parent_id": "knowledge"},
            "is_active": True,
        },
    ]


@pytest.mark.asyncio
async def test_get_all_page_metadata_passes_through_metadata_block(fake_page_keys):
    """get_all_page_metadata() 必须把整块 metadata_json 透传到 'metadata' 字段."""
    from src.permissions import cache

    fake_dict = {"items": fake_page_keys}

    with patch("src.lookups.service.LookupService") as mock_svc:
        mock_svc.get = AsyncMock(return_value=fake_dict)
        result = await cache.get_all_page_metadata()

    # admin (顶级 + is_group)
    admin_entry = next(r for r in result if r["key"] == "admin")
    assert admin_entry["metadata"] == {"path": "/admin", "is_group": True, "icon": "shield"}
    assert admin_entry["path"] == "/admin"
    assert admin_entry["label_zh"] == "管理中心"

    # admin_users (子页 + parent_id)
    users_entry = next(r for r in result if r["key"] == "admin_users")
    assert users_entry["metadata"] == {"path": "/admin/users", "parent_id": "admin"}
    assert users_entry["path"] == "/admin/users"

    # chat (顶级, 无 is_group)
    chat_entry = next(r for r in result if r["key"] == "chat")
    assert chat_entry["metadata"] == {"path": "/chat"}
    assert "is_group" not in chat_entry["metadata"]


@pytest.mark.asyncio
async def test_get_all_page_metadata_handles_missing_metadata_json():
    """历史数据 metadata_json 为 None → 'metadata' 字段为空 dict."""
    from src.permissions import cache

    fake_dict = {
        "items": [
            {
                "key": "legacy",
                "label_zh": "老页面",
                "label_en": "Legacy",
                "metadata_json": None,
                "is_active": True,
            }
        ]
    }

    with patch("src.lookups.service.LookupService") as mock_svc:
        mock_svc.get = AsyncMock(return_value=fake_dict)
        result = await cache.get_all_page_metadata()

    legacy = result[0]
    assert legacy["metadata"] == {}
    # 缺 metadata_json.path 时仍兜底成 /<key>
    assert legacy["path"] == "/legacy"


@pytest.mark.asyncio
async def test_get_all_page_metadata_fallback_on_lookup_failure():
    """LookupService 抛异常 → 返 _PAGE_METADATA_FALLBACK (R1 兼容)."""
    from src.permissions import cache

    with patch("src.lookups.service.LookupService") as mock_svc:
        mock_svc.get = AsyncMock(side_effect=RuntimeError("DB down"))
        result = await cache.get_all_page_metadata()

    # fallback 至少含 admin / chat / knowledge
    keys = [r["key"] for r in result]
    assert "admin" in keys
    assert "chat" in keys
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd packages/service && uv run pytest tests/permissions/test_cache.py -v`

Expected: 3 tests, all FAIL with `KeyError: 'metadata'` or `AssertionError`.

- [ ] **Step 3: Commit failing test**

```bash
cd c:/doc/Code/rag
git add packages/service/tests/permissions/test_cache.py
git commit -m "test(cache): add failing tests for metadata_json passthrough (PR1/2)"
```

---

## Task 1.3: Implement metadata passthrough in cache.py

**Files:**
- Modify: `packages/service/src/permissions/cache.py:79-106`

- [ ] **Step 1: Read current cache.py metadata function**

Run: `cat packages/service/src/permissions/cache.py | sed -n '79,106p'`

Expected output:
```python
async def get_all_page_metadata() -> list[dict]:
    ...
    d = await LookupService.get("page_key", only_active=False)
    result: list[dict] = []
    for item in d.get("items", []):
        meta = item.get("metadata_json") or {}
        path = meta.get("path") if isinstance(meta, dict) else None
        result.append(
            {
                "key": item["key"],
                "label_zh": item.get("label_zh", item["key"]),
                "label_en": item.get("label_en", item["key"]),
                "path": path or f"/{item['key']}",
                "is_active": item.get("is_active", True),
            }
        )
```

- [ ] **Step 2: Replace the result.append block**

In `packages/service/src/permissions/cache.py`, replace the loop body (lines 89-101):

```python
    d = await LookupService.get("page_key", only_active=False)
    result: list[dict] = []
    for item in d.get("items", []):
        raw_meta = item.get("metadata_json")
        # (2026-07-02 nav spec §2.2) 透传整块 metadata_json, 缺失兜底空 dict
        meta = raw_meta if isinstance(raw_meta, dict) else {}
        path = meta.get("path")
        result.append(
            {
                "key": item["key"],
                "label_zh": item.get("label_zh", item["key"]),
                "label_en": item.get("label_en", item["key"]),
                "path": path or f"/{item['key']}",
                "is_active": item.get("is_active", True),
                "metadata": meta,  # 整块 metadata_json 透传给前端 (parent_id / is_group / icon 等)
            }
        )
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd packages/service && uv run pytest tests/permissions/test_cache.py -v`

Expected: 3 tests PASS.

- [ ] **Step 4: Run full test suite to ensure no regressions**

Run: `cd packages/service && uv run pytest --no-cov -q -x 2>&1 | tail -30`

Expected: same baseline (1075 passed + 22 fail + 38 errors), no new failures.

Note: If you see lint warnings from ruff, run `uv run ruff check src/permissions/cache.py` and fix.

- [ ] **Step 5: Commit passthrough change**

```bash
cd c:/doc/Code/rag
git add packages/service/src/permissions/cache.py
git commit -m "feat(cache): passthrough metadata_json to frontend (PR1/3)

Frontend can now read parent_id / is_group / icon via PageMeta.metadata.
Zero schema change. Fallback dict for legacy / DB-down paths."
```

---

## Task 1.4: Update _PAGE_METADATA_FALLBACK for offline parity

**Files:**
- Modify: `packages/service/src/permissions/cache.py:44-57`

- [ ] **Step 1: Read current fallback**

Run: `sed -n '44,57p' packages/service/src/permissions/cache.py`

- [ ] **Step 2: Replace fallback to include new page_keys + metadata field**

Replace the `_PAGE_METADATA_FALLBACK` definition with:

```python
# fallback 元数据 (跟 ALL_PAGE_KEYS_FALLBACK 对应, DB 挂时返回)
# (2026-07-02 nav spec) 含 metadata 字段, 离线时仍渲染顶级平铺导航 (Phase-1 兼容)
_PAGE_METADATA_FALLBACK: list[dict] = [
    {"key": k, "label_zh": zh, "label_en": en, "path": f"/{k}", "is_active": True,
     "metadata": {"path": f"/{k}"}}
    for k, zh, en in [
        ("admin", "管理中心", "Admin"),
        ("buyers", "客户画像", "Buyers"),
        ("chat", "对话", "Chat"),
        ("output", "文档结构化", "Output"),
        ("knowledge", "知识库", "Knowledge"),
        ("evaluate", "评估", "Evaluate"),
        ("submissions", "审核中心", "Submissions"),
        ("decode", "型号解析", "Decode"),
        ("health", "监控", "Health"),
    ]
]
```

- [ ] **Step 3: Re-run test suite**

Run: `cd packages/service && uv run pytest tests/permissions/test_cache.py -v`

Expected: 3 tests PASS (fallback test still works because it checks `admin`/`chat`/`knowledge` keys).

- [ ] **Step 4: Verify pyright strict**

Run: `cd packages/service && uv run pyright src/permissions/cache.py`

Expected: 0 errors.

- [ ] **Step 5: Commit fallback update**

```bash
cd c:/doc/Code/rag
git add packages/service/src/permissions/cache.py
git commit -m "refactor(cache): metadata field in fallback dict (PR1/4)

Offline / DB-down path renders flat nav correctly. Same schema as live path."
```

---

## Task 1.5: Final regression check

- [ ] **Step 1: Run full backend tests**

Run: `cd packages/service && uv run pytest --no-cov -q 2>&1 | tail -15`

Expected: same baseline as before this PR. Look for: `XXXX passed` count matches baseline (1075 + 3 new = 1078). No new failures.

- [ ] **Step 2: Run pyright strict on changed files**

Run: `cd packages/service && uv run pyright`

Expected: 0 errors.

- [ ] **Step 3: Run ruff check**

Run: `cd packages/service && uv run ruff check`

Expected: 0 errors.

- [ ] **Step 4: Final commit if anything changed**

```bash
cd c:/doc/Code/rag
git status
# 如果有未 commit 的 lint/format 改动, git add -u && git commit -m "chore(pr1): final lint/format pass"
```

---

## PR1 Definition of Done

- [ ] yaml seed updated with 5 new sub-pages + parent_id/is_group/icon metadata
- [ ] `get_all_page_metadata()` returns `metadata` field with full metadata_json block
- [ ] 3 new tests pass; baseline 1075+ tests still pass
- [ ] pyright 0 errors, ruff 0 errors
- [ ] No DB schema changes (pure yaml + cache.py)
- [ ] Ready for PR2 (frontend buildNavTree)