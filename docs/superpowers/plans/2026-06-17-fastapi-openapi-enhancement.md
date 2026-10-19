# FastAPI OpenAPI 展示增强 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **关键性质**: 本 plan **纯 metadata 改动**, 不改业务逻辑, 不改鉴权, 不改响应 shape. 0 业务测试受影响, 每个 commit 验 `/openapi.json` 即可.

**端点数核算**: 67 = 14 router × 64 端点 + 3 inline (`app.py` 的 `/decode` `/series` `/health`). 另有 `storage/session.py:48` 的 `@app.get("/items")` 是 Redis session 内部端点, **不在本 plan 范围** (独立 session 子系统, 不进 FastAPI app). `ingest/api.py` 端点用 `@ingest_router` 不用 `@router`, grep 时注意.

**Goal:** 让 FastAPI 自带 `/docs` Swagger UI 从"能看"变"好用":
- L1: 全局 metadata (title/description/contact/license/servers/openapi_tags) 完善
- L2: 2 个不规范 tag 标准化
- L3: **67 端点** 全部加 `summary` / `description` / `responses`
- L4: **~50 个 Pydantic 字段** 补 `Field(description=...)`

**Architecture:**
- 1 个 commit 改 `app.py` + 2 个 tag (P0)
- 6 个 commit 按 router 分组改端点 metadata (P1)
- 2 个 commit 按文件分组补字段 description (P2)
- 共 **9 commits, ~8 小时**

**Tech Stack:** FastAPI 0.115+ 原生 OpenAPI 参数 (`summary=` / `description=` / `responses=` / `openapi_tags` / `Field(description=)`), Pydantic 2.x, **不引入新库**

**Spec:** [2026-06-17-fastapi-openapi-enhancement-design.md](../specs/2026-06-17-fastapi-openapi-enhancement-design.md)

---

## File Structure

**修改 (15 个文件)**:
- `packages/service/src/product_decoders/app.py` (P0: FastAPI() 全局 metadata + 3 inline 端点 metadata)
- `packages/service/src/memory/router.py` (L2: tag; P1: 6 端点)
- `packages/service/src/chat_share/router.py` (L2: tag; P1: 6 端点)
- `packages/service/src/permissions/router.py` (P1: 7 端点 + P2: 4 BaseModel)
- `packages/service/src/eval/router.py` (P1: 5 端点)
- `packages/service/src/health/router.py` (P1: 1 端点)
- `packages/service/src/ingest/api.py` (P1: 7 端点)
- `packages/service/src/auth/router.py` (P1: 2 端点 + P2: 2 BaseModel)
- `packages/service/src/auth/auth_account_router.py` (P1: 6 端点 + P2: 7 BaseModel)
- `packages/service/src/auth/auth_admin_router.py` (P1: 6 端点 + P2: 7 BaseModel)
- `packages/service/src/auth/auth_invite_router.py` (P1: 2 端点 + P2: 3 BaseModel)
- `packages/service/src/approvals/router.py` (P1: 8 端点 + P2: 2 BaseModel)
- `packages/service/src/kg/router.py` (P1: 13 端点 + P2: 6 BaseModel)
- `packages/service/src/api/routes.py` (P1: 4 端点)
- `packages/service/src/product_decoders/output_api.py` (P1: 2 端点)
- `packages/service/src/chat_share/schemas.py` (P2: 3 字段)
- `packages/service/src/ingest/schemas_presign.py` (P2: 4 字段)
- `packages/service/src/api/schemas.py` (P2: 3 字段)
- `packages/service/src/memory/schemas.py` (P2: 已有 9 字段, 不动)

**新建 (1 个文件, 可选)**:
- `packages/service/tests/openapi/test_openapi_metadata.py` (smoke test, 验 `summary`/`description`/`responses` 全覆盖; 单文件 ~50 行, 不阻塞)

**新建 (1 个文件, 必做)**:
- `docs/superpowers/handoffs/2026-06-17-fastapi-openapi-enhancement.md` (实施完写 handoff, 跟 RBAC 模式一致)

---

## 全局约定 (实施前读)

### 元数据模板

```python
@router.<method>(
    "<path>",
    summary="<中文 1 行, ≤ 30 字>",
    description=(
        "## 用途\n\n"
        "<2-4 行说明, 业务背景>\n\n"
        "## 鉴权\n\n"
        "<require_xxx 规则>\n\n"
        "## 行为\n\n"
        "<业务细节 + 降级行为 + 错误条件>"
    ),
    responses={
        200: {"description": "<成功响应说明>"},
        400: {"description": "<4xx 错误条件>"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "权限不足"},
        404: {"description": "资源不存在"},
        409: {"description": "状态冲突"},
        413: {"description": "文件过大"},
        422: {"description": "Pydantic 校验失败"},
        500: {"description": "服务器内部错误"},
    },
    response_model=<保留原值>,    # 已有保留
    status_code=<保留原值>,        # 已有保留
    tags=<保留原值>,               # 已有保留
)
def <name>(...):
    <原 docstring 删掉, 因 description 已覆盖>
    <body 不变>
```

### 字段 description 模板

```python
class XxxIn(BaseModel):
    """<model 用途 docstring 保留>"""

    field_name: str = Field(
        ...,
        min_length=...,
        max_length=...,
        description="<含义; 例: 'user' / 'admin'; ≥ 1 字符>",
    )
```

### 验证命令 (每个 commit 必跑)

```bash
# 起服务 (后台)
cd packages/service
uv run uvicorn src.product_decoders.app:create_app --factory --port 8000 &
SERVER_PID=$!
sleep 3

# 验 info 完整
curl -s http://localhost:8000/openapi.json | jq '.info | {title, version, contact, license, servers: (.servers | length), tags: (.tags | length)}'

# 验 67 端点 100% 有 summary
curl -s http://localhost:8000/openapi.json | \
  jq '[.paths[].[get,post,patch,delete,put][]? | select(. != null)] | map({summary, has_desc: (.description != null), responses: (.responses | keys)}) | {total: length, no_summary: map(select(.summary == null)) | length, no_desc: map(select(.has_desc == false)) | length}'

# 验 14 tag 全有 description
curl -s http://localhost:8000/openapi.json | jq '.tags | map(select(.description == null))'

# 停服务
kill $SERVER_PID
```

---

## Phase 1: P0 全局 + Tag (1 commit, 30 min)

### Task 1.1: app.py 全局 metadata + 2 个 tag 标准化

**Files:**
- Modify: `packages/service/src/product_decoders/app.py` (替换 `FastAPI(...)` 调用 + 3 inline 端点 metadata)
- Modify: `packages/service/src/memory/router.py:39` (改 tag)
- Modify: `packages/service/src/chat_share/router.py:45` (改 tag)

- [ ] **Step 1: 改 `app.py` 的 FastAPI() 调用**

替换 `app = FastAPI(...)` (L59-64) 为 spec §5.1 的完整代码块 (含 title/summary/version/description/contact/license_info/openapi_tags/servers/lifespan).

- [ ] **Step 2: 改 `memory/router.py` tag**

```python
# src/memory/router.py:39
# 旧: tags=["记忆"]
# 新: tags=["memory"]
```

- [ ] **Step 3: 改 `chat_share/router.py` tag**

```python
# src/chat_share/router.py:45
# 旧: tags=["chat share"]
# 新: tags=["chat-share"]
```

- [ ] **Step 4: 改 `app.py` 的 3 inline 端点 metadata**

3 个端点 (L91 `/decode`, L103 `/series`, L108 `/health`) 各加 `summary` + `description`. 完整 description 见 spec §5.3.15. 删原 docstring (description 已覆盖).

- [ ] **Step 5: 跑验证命令**

跑上文"验证命令"块, 期望:

- `info.title` = "RAG + 产品订货号解析服务"
- `info.contact` 非空
- `info.license.name` = "MIT"
- `servers | length` = 3
- `tags | length` = 14
- 14 个 tag 全部 `description` 非空

- [ ] **Step 6: 跑既有测试确认无破坏**

```bash
cd packages/service
uv run pytest tests/ -q -x --ignore=tests/kg --ignore=tests/ingest/test_api.py --ignore=tests/approvals/test_repo.py
```

(忽略的 3 个是已知 baseline PG 依赖 fail, 跟 metadata 无关.)

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/product_decoders/app.py \
        packages/service/src/memory/router.py \
        packages/service/src/chat_share/router.py

git commit -m "feat(openapi): global metadata + tag normalization (P0)

- app.py: 扩 title/description/contact/license/servers/openapi_tags
- app.py: 3 inline 端点 (/decode /series /health) 加 summary + description
- memory/router.py: tag '记忆' → 'memory'
- chat_share/router.py: tag 'chat share' → 'chat-share'

效果: Swagger UI 首页从 1 行 → 60+ 行可读, 含 14 tag 分组 + 3 server 切换

Refs: docs/superpowers/specs/2026-06-17-fastapi-openapi-enhancement-design.md"
```

---

## Phase 2: P1 端点 metadata (6 commits, ~6 小时)

**并行建议**: 这 6 个 commit **文件不重叠**, 可以并行 4 个 subagent 同时改. 走 subagent-driven-development 模式.

### Task 2.1: permissions/router.py (7 端点, 0.5h)

**File:**
- Modify: `packages/service/src/permissions/router.py`

- [ ] **Step 1: 给 7 个端点加 summary/description/responses**

7 端点: `GET /api/permissions`, `PATCH /api/permissions`, `GET /api/permissions/me`, `GET /api/roles`, `POST /api/roles`, `PATCH /api/roles/{name}`, `DELETE /api/roles/{name}`. 端点对应 summary/description 要点见 spec §5.3.1.

- [ ] **Step 2: 删原 docstring** (description 已覆盖)

- [ ] **Step 3: 跑验证命令**

`curl /openapi.json | jq '.paths."/api/permissions".get.summary'` = "查询完整权限矩阵". 7 端点全部有 summary/description/responses.

- [ ] **Step 4: 跑既有测试**

```bash
cd packages/service
uv run pytest tests/permissions/ tests/roles/ tests/integration/test_rbac_e2e.py -q
```

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/permissions/router.py
git commit -m "feat(openapi): permissions router 7 端点 metadata (P1-1)

- summary/description/responses 全覆盖
- /api/permissions GET/PATCH/me, /api/roles GET/POST/PATCH/DELETE

Refs: docs/superpowers/specs/2026-06-17-fastapi-openapi-enhancement-design.md"
```

### Task 2.2: memory + chat_share (12 端点, 1h)

**Files:**
- Modify: `packages/service/src/memory/router.py` (6 端点)
- Modify: `packages/service/src/chat_share/router.py` (6 端点)

- [ ] **Step 1: 改 memory/router.py 6 端点**

端点对应 metadata 见 spec §5.3.2. 删原 docstring.

- [ ] **Step 2: 改 chat_share/router.py 6 端点**

端点对应 metadata 见 spec §5.3.3. 删原 docstring.

- [ ] **Step 3: 跑验证**

`curl /openapi.json | jq '.paths | keys'` 含 `/api/memory/{search,add,list,all,{memory_id}}` + `/api/chat/{shares,shares/{share_id},files,files/presign,files/finalize}`. 12 端点全有 summary.

- [ ] **Step 4: 跑既有测试**

```bash
cd packages/service
uv run pytest tests/memory/ tests/chat_share/ -q
```

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/memory/router.py packages/service/src/chat_share/router.py
git commit -m "feat(openapi): memory + chat_share 12 端点 metadata (P1-2)"
```

### Task 2.3: ingest + eval + health (13 端点, 1h)

**Files:**
- Modify: `packages/service/src/ingest/api.py` (7 端点)
- Modify: `packages/service/src/eval/router.py` (5 端点)
- Modify: `packages/service/src/health/router.py` (1 端点)

- [ ] **Step 1: 改 ingest/api.py 7 端点**

端点对应 metadata 见 spec §5.3.6. 删原 docstring.

> ⚠️ 提醒: `ingest/api.py` 用 `ingest_router` 不用 `router`, grep 改 `@ingest_router.`

- [ ] **Step 2: 改 eval/router.py 5 端点**

端点对应 metadata 见 spec §5.3.4. 删原 docstring.

- [ ] **Step 3: 改 health/router.py 1 端点**

端点对应 metadata 见 spec §5.3.5. 删原 docstring.

- [ ] **Step 4: 跑验证**

13 端点全有 summary. `/api/ingest/upload/presign` 等路径在 jq 输出.

- [ ] **Step 5: 跑既有测试**

```bash
cd packages/service
uv run pytest tests/ingest/ tests/eval/ tests/health/ -q --ignore=tests/ingest/test_api.py
```

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/ingest/api.py \
        packages/service/src/eval/router.py \
        packages/service/src/health/router.py

git commit -m "feat(openapi): ingest + eval + health 13 端点 metadata (P1-3)"
```

### Task 2.4: auth 4 router (16 端点, 1.5h)

**Files:**
- Modify: `packages/service/src/auth/router.py` (2 端点)
- Modify: `packages/service/src/auth/auth_account_router.py` (6 端点)
- Modify: `packages/service/src/auth/auth_admin_router.py` (6 端点)
- Modify: `packages/service/src/auth/auth_invite_router.py` (2 端点)

- [ ] **Step 1: 改 auth/router.py 2 端点**

端点对应 metadata 见 spec §5.3.7. 删原 docstring.

- [ ] **Step 2: 改 auth_account_router.py 6 端点**

端点对应 metadata 见 spec §5.3.8. 删原 docstring.

- [ ] **Step 3: 改 auth_admin_router.py 6 端点**

端点对应 metadata 见 spec §5.3.9. 删原 docstring.

- [ ] **Step 4: 改 auth_invite_router.py 2 端点**

端点对应 metadata 见 spec §5.3.10. 删原 docstring.

- [ ] **Step 5: 跑验证**

16 端点全有 summary. `/api/auth/{migrate,anon}` + `/api/account/{login,logout,me,seed-admin,forgot-password,reset-password}` + `/api/admin/{users,invites,users/{user_id},users/{user_id}/reset-password,invites/{token}}` + `/api/invites/{token},{token}/redeem` 在 jq 输出.

- [ ] **Step 6: 跑既有测试**

```bash
cd packages/service
uv run pytest tests/auth/ tests/permissions/ -q
```

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/auth/

git commit -m "feat(openapi): auth 4 router 16 端点 metadata (P1-4)"
```

### Task 2.5: approvals + kg (21 端点, 1.5h)

**Files:**
- Modify: `packages/service/src/approvals/router.py` (8 端点)
- Modify: `packages/service/src/kg/router.py` (13 端点)

- [ ] **Step 1: 改 approvals/router.py 8 端点**

端点对应 metadata 见 spec §5.3.11. 删原 docstring.

- [ ] **Step 2: 改 kg/router.py 13 端点**

端点对应 metadata 见 spec §5.3.12. 删原 docstring.

- [ ] **Step 3: 跑验证**

21 端点全有 summary. `/api/approvals/*` + `/api/kg/*` 在 jq 输出.

- [ ] **Step 4: 跑既有测试**

```bash
cd packages/service
uv run pytest tests/approvals/test_router.py tests/kg/test_kg_router.py -q --ignore=tests/approvals/test_repo.py
```

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/approvals/router.py packages/service/src/kg/router.py

git commit -m "feat(openapi): approvals + kg 21 端点 metadata (P1-5)"
```

### Task 2.6: output + api + inline (4 端点, 0.5h)

**Files:**
- Modify: `packages/service/src/product_decoders/output_api.py` (2 端点)
- Modify: `packages/service/src/api/routes.py` (4 端点)

> 注: `app.py` 的 3 inline 端点已 在 Task 1.1 改过, 此处不再重复.

- [ ] **Step 1: 改 output_api.py 2 端点**

端点对应 metadata 见 spec §5.3.14. 删原 docstring.

- [ ] **Step 2: 改 api/routes.py 4 端点**

端点对应 metadata 见 spec §5.3.13. **特别注意**: `GET /api/v1/health` (L84) 当前无 docstring, 必须补 summary + description.

- [ ] **Step 3: 跑验证**

6 端点全有 summary. `/api/output/*` + `/api/v1/*` 在 jq 输出.

- [ ] **Step 4: 跑既有测试**

```bash
cd packages/service
uv run pytest tests/ingest/test_web_apis.py tests/api/ -q
```

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/product_decoders/output_api.py \
        packages/service/src/api/routes.py

git commit -m "feat(openapi): output + api 6 端点 metadata (P1-6, 含 /api/v1/health 补 docstring)"
```

### Task 2.7: P1 整体验收

- [ ] **Step 1: 跑全局验证**

```bash
# 起服务
cd packages/service
uv run uvicorn src.product_decoders.app:create_app --factory --port 8000 &
sleep 3

# 67 端点全有 summary
COUNT=$(curl -s http://localhost:8000/openapi.json | \
  jq '[.paths[].[get,post,patch,delete,put][]? | select(. != null)] | length')
echo "Total endpoints: $COUNT (expect 67)"

NO_SUMMARY=$(curl -s http://localhost:8000/openapi.json | \
  jq '[.paths[].[get,post,patch,delete,put][]? | select(. != null) | select(.summary == null)] | length')
echo "Endpoints without summary: $NO_SUMMARY (expect 0)"

NO_DESC=$(curl -s http://localhost:8000/openapi.json | \
  jq '[.paths[].[get,post,patch,delete,put][]? | select(. != null) | select(.description == null)] | length')
echo "Endpoints without description: $NO_DESC (expect 0)"

# 停服务
kill %1
```

- [ ] **Step 2: 跑全量测试 (排除 baseline 失败)**

```bash
cd packages/service
uv run pytest tests/ -q \
  --ignore=tests/kg \
  --ignore=tests/ingest/test_api.py \
  --ignore=tests/approvals/test_repo.py
```

Expected: 跟基线 225+ passed 一致, 0 业务测试因 metadata 改动而 fail.

---

## Phase 3: P2 Pydantic 字段 description (2 commits, ~2h)

### Task 3.1: permissions + approvals + kg + chat_share (16 字段, 1h)

**Files:**
- Modify: `packages/service/src/permissions/router.py` (4 BaseModel)
- Modify: `packages/service/src/approvals/router.py` (2 BaseModel)
- Modify: `packages/service/src/kg/router.py` (6 BaseModel)
- Modify: `packages/service/src/chat_share/schemas.py` (3 字段)

- [ ] **Step 1: 改 permissions/router.py 4 BaseModel**

完整字段 description 见 spec §5.4.1. 注意 `CreateRoleRequest.name` 加 `pattern=r"^[a-z0-9_]+$"` 跟 router 端 `ROLE_NAME_PATTERN` 对齐.

- [ ] **Step 2: 改 approvals/router.py 2 BaseModel**

完整字段 description 见 spec §5.4.6.

- [ ] **Step 3: 改 kg/router.py 6 BaseModel**

完整字段 description 见 spec §5.4.7.

- [ ] **Step 4: 改 chat_share/schemas.py 3 字段**

完整字段 description 见 spec §5.4.8. 注意: `PresignChatFileRequest.size` 当前只 `ge=0`, 加 `le=20*1024*1024` 跟 router 端 `defaults.DEFAULT_CHAT_FILE_MAX_BYTES` 对齐.

- [ ] **Step 5: 跑验证**

```bash
# 验 components.schemas 字段全有 description
curl -s http://localhost:8000/openapi.json | \
  jq '[.components.schemas | to_entries[] | {name: .key, fields: [.value.properties | to_entries[] | .value.description]}] | map({name, no_desc: (.fields | map(select(. == null)) | length)}) | map(select(.no_desc > 0))'
```

Expected: 4 文件对应 15 个 BaseModel 字段全有 description (空 list).

- [ ] **Step 6: 跑既有测试**

```bash
cd packages/service
uv run pytest tests/permissions/ tests/roles/ tests/approvals/ tests/kg/ tests/chat_share/ -q --ignore=tests/kg/test_kg_router.py --ignore=tests/approvals/test_repo.py
```

(注: 改了 `PresignChatFileRequest.size` 加 `le=20MB` 上限, 若有测试传 > 20MB size, 会 fail 422. 检查 tests/chat_share/ 是否有这种测试, 有就改测试或调 size 上限.)

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/permissions/router.py \
        packages/service/src/approvals/router.py \
        packages/service/src/kg/router.py \
        packages/service/src/chat_share/schemas.py

git commit -m "feat(openapi): 4 文件 15 BaseModel 字段 description (P2-1)"
```

### Task 3.2: auth + ingest + api (22 字段, 1h)

**Files:**
- Modify: `packages/service/src/auth/router.py` (2 BaseModel)
- Modify: `packages/service/src/auth/auth_account_router.py` (7 BaseModel)
- Modify: `packages/service/src/auth/auth_admin_router.py` (7 BaseModel)
- Modify: `packages/service/src/auth/auth_invite_router.py` (3 BaseModel)
- Modify: `packages/service/src/ingest/schemas_presign.py` (4 字段)
- Modify: `packages/service/src/api/schemas.py` (3 字段)

- [ ] **Step 1: 改 auth/router.py 2 BaseModel**

完整字段 description 见 spec §5.4.2.

- [ ] **Step 2: 改 auth_account_router.py 7 BaseModel**

完整字段 description 见 spec §5.4.3.

- [ ] **Step 3: 改 auth_admin_router.py 7 BaseModel**

完整字段 description 见 spec §5.4.4.

- [ ] **Step 4: 改 auth_invite_router.py 3 BaseModel**

完整字段 description 见 spec §5.4.5.

- [ ] **Step 5: 改 ingest/schemas_presign.py 4 字段**

完整字段 description 见 spec §5.4.9.

- [ ] **Step 6: 改 api/schemas.py 3 字段**

完整字段 description 见 spec §5.4.10.

- [ ] **Step 7: 跑验证**

```bash
curl -s http://localhost:8000/openapi.json | \
  jq '[.components.schemas | to_entries[] | {name: .key, fields: [.value.properties | to_entries[] | .value.description]}] | map({name, no_desc: (.fields | map(select(. == null)) | length)}) | map(select(.no_desc > 0))'
```

Expected: 空 list (所有字段有 description).

- [ ] **Step 8: 跑既有测试**

```bash
cd packages/service
uv run pytest tests/auth/ tests/ingest/ tests/api/ -q --ignore=tests/ingest/test_api.py
```

(注: `LoginRequest.password` 当前无 `min_length`, 加 `min_length=1` 跟 spec 一致, 可能有测试传空字符串, 改测试或保留无 min_length.)

- [ ] **Step 9: Commit**

```bash
git add packages/service/src/auth/ \
        packages/service/src/ingest/schemas_presign.py \
        packages/service/src/api/schemas.py

git commit -m "feat(openapi): auth + ingest + api 6 文件 22 BaseModel 字段 description (P2-2)"
```

---

## Phase 4: 收口 (smoke test + handoff + 文档, 0.5h)

### Task 4.1: OpenAPI metadata smoke test (可选, 但建议)

**File:**
- Create: `packages/service/tests/openapi/test_openapi_metadata.py`

- [ ] **Step 1: 写 smoke test**

```python
"""OpenAPI metadata 完整性 smoke test (2026-06-17)

防止后续 PR 把 summary/description/responses 删掉, 一键回归.
不替代 Swagger UI 视觉检查, 纯结构性校验.
"""

import pytest
from fastapi.testclient import TestClient

from src.product_decoders.app import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture(scope="module")
def openapi(client: TestClient) -> dict:
    return client.get("/openapi.json").json()


def test_info_has_required_fields(openapi: dict) -> None:
    info = openapi["info"]
    assert "RAG" in info["title"]
    assert info["contact"]["name"]
    assert info["license"]["name"] == "MIT"
    assert len(info.get("description", "")) > 100  # 不只是一句话


def test_has_3_servers(openapi: dict) -> None:
    servers = openapi.get("servers", [])
    assert len(servers) >= 3, f"期望 ≥ 3 server (dev/staging/prod), 实得 {len(servers)}"


def test_all_14_tags_have_description(openapi: dict) -> None:
    tags = openapi.get("tags", [])
    assert len(tags) == 14, f"期望 14 tag, 实得 {len(tags)}"
    for t in tags:
        assert t.get("description"), f"tag {t['name']} 缺 description"


def test_all_67_endpoints_have_summary(openapi: dict) -> None:
    methods = ["get", "post", "put", "patch", "delete"]
    endpoints = []
    for path, ops in openapi["paths"].items():
        for m in methods:
            if m in ops:
                endpoints.append((path, m, ops[m]))
    assert len(endpoints) == 67, f"期望 67 端点, 实得 {len(endpoints)}"
    for path, m, op in endpoints:
        assert op.get("summary"), f"{m.upper()} {path} 缺 summary"


def test_all_endpoints_have_description(openapi: dict) -> None:
    methods = ["get", "post", "put", "patch", "delete"]
    for path, ops in openapi["paths"].items():
        for m in methods:
            if m in ops:
                op = ops[m]
                assert op.get("description"), f"{m.upper()} {path} 缺 description"


def test_all_endpoints_have_4xx_responses(openapi: dict) -> None:
    methods = ["get", "post", "put", "patch", "delete"]
    for path, ops in openapi["paths"].items():
        for m in methods:
            if m in ops:
                op = ops[m]
                resp_codes = set(op.get("responses", {}).keys())
                # 至少有 200 + 1 个 4xx
                has_2xx = any(c.startswith("2") for c in resp_codes)
                has_4xx = any(c.startswith("4") for c in resp_codes)
                assert has_2xx, f"{m.upper()} {path} 缺 2xx 响应"
                assert has_4xx, f"{m.upper()} {path} 缺 4xx 响应"


def test_no_chinese_or_space_tags(openapi: dict) -> None:
    """L2: tag 标准化, 不允许中文 / 空格"""
    for t in openapi.get("tags", []):
        name = t["name"]
        assert name.isascii(), f"tag '{name}' 含非 ASCII 字符"
        assert " " not in name, f"tag '{name}' 含空格"


def test_all_schemas_have_field_descriptions(openapi: dict) -> None:
    """L4: 所有 Pydantic 字段有 description"""
    schemas = openapi.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        if schema.get("type") != "object":
            continue  # 跳过 enum 等非 object
        for field_name, field_schema in schema.get("properties", {}).items():
            assert field_schema.get("description"), \
                f"{name}.{field_name} 缺 description"
```

- [ ] **Step 2: 跑 smoke test**

```bash
cd packages/service
uv run pytest tests/openapi/test_openapi_metadata.py -v
```

Expected: 8 passed. 若 fail, 必有端点/字段漏 metadata, 回去补.

- [ ] **Step 3: Commit**

```bash
git add packages/service/tests/openapi/
git commit -m "test(openapi): smoke test for metadata completeness (8 cases)"
```

### Task 4.2: Handoff 文档

**File:**
- Create: `docs/superpowers/handoffs/2026-06-17-fastapi-openapi-enhancement.md`

- [ ] **Step 1: 写 handoff (跟 RBAC handoff 同款格式)**

模板见 docs/superpowers/handoffs/2026-06-17-rbac-permission-system.md, 关键内容:
- 9 commits hash + 1 行说明
- smoke test 8/8 pass
- 全量 pytest 跟基线一致 (无 baseline 退化)
- 验收 checklist 全 ✅
- 接手者速查: 哪个 router 加了什么

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/handoffs/
git commit -m "docs(openapi): handoff for 2026-06-17 enhancement"
```

---

## 整体验收 (Phase 1-4 完成后跑)

### 验收 checklist

- [ ] 9 commits 全部 push, hash 记录在 handoff
- [ ] `curl /openapi.json | jq '.info'` 看到完整 title/description/contact/license/servers/openapi_tags
- [ ] Swagger UI (`/docs`) 首页 60+ 行可读
- [ ] 14 tag 全有 description
- [ ] 67 端点 100% 有 summary + description + 至少 1 个 4xx response
- [ ] 66+ 字段 100% 有 description
- [ ] smoke test 8/8 pass
- [ ] 全量 pytest 跟基线一致 (除已知 baseline 失败)
- [ ] `/openapi.json` 体积 < 100KB (description 是文本, 不应过大)
- [ ] Swagger UI 视觉检查 (手开浏览器, 抽查 3 个 tag 渲染正常)

### 完整端到端命令

```bash
# 起服务
cd packages/service
uv run uvicorn src.product_decoders.app:create_app --factory --port 8000 &
sleep 3

# 1. info
echo "=== INFO ==="
curl -s http://localhost:8000/openapi.json | jq '.info | keys'
curl -s http://localhost:8000/openapi.json | jq '.info.title, .info.version, (.info.contact // null), (.info.license // null), (.servers | length)'

# 2. tags
echo "=== TAGS ==="
curl -s http://localhost:8000/openapi.json | jq '.tags | length'
curl -s http://localhost:8000/openapi.json | jq '.tags | map(.name)'

# 3. 端点覆盖
echo "=== ENDPOINTS ==="
curl -s http://localhost:8000/openapi.json | \
  jq '[.paths[].[get,post,patch,delete,put][]? | select(. != null)] | {total: length, no_summary: map(select(.summary == null)) | length, no_desc: map(select(.description == null)) | length, no_4xx: map(select((.responses | keys | map(select(. | startswith("4"))) | length) == 0)) | length}'

# 4. 字段覆盖
echo "=== SCHEMAS ==="
curl -s http://localhost:8000/openapi.json | \
  jq '[.components.schemas | to_entries[] | .value | select(.type == "object") | .properties | to_entries[] | select(.value.description == null)] | length'

# 5. 体积
echo "=== SIZE ==="
curl -s http://localhost:8000/openapi.json | wc -c

# 6. smoke test
echo "=== SMOKE TEST ==="
cd packages/service
uv run pytest tests/openapi/test_openapi_metadata.py -v

# 7. 全量测试 (排除 baseline)
echo "=== FULL TESTS ==="
uv run pytest tests/ -q \
  --ignore=tests/kg \
  --ignore=tests/ingest/test_api.py \
  --ignore=tests/approvals/test_repo.py

# 停服务
kill %1
```

Expected:
- INFO: keys 含 7 个 (title, version, description, contact, license, termsOfService, summary)
- TAGS: 14
- ENDPOINTS: `{total: 67, no_summary: 0, no_desc: 0, no_4xx: 0}`
- SCHEMAS: 0
- SIZE: < 100KB
- SMOKE TEST: 8 passed
- FULL TESTS: 跟基线一致

---

## 风险 + 回滚

| 风险 | 概率 | 缓解 / 回滚 |
|------|------|------------|
| 改 tag 影响客户端 (codegen, monitoring group-by-tag) | 低 | 本次不接入 codegen, 监控走 path 不走 tag; 真出问题 `git revert <commit>` |
| 中文 summary 在 Postman 旧版乱码 | 低 | 现代 client OK; 旧版降级显示, 不影响 API 行为 |
| 加 Pydantic 约束 (`min_length` / `le=`) 触发旧测试 fail | 中 | Step 6/8 跑测试, fail 改测试或撤回约束; 这是好事, 暴露 spec 跟代码不一致 |
| 改 `description` 引入 typo, 前端 codegen 解析时炸 | 低 | 本次不接入 codegen; smoke test 只能查 key 存在, 查不出 typo; 手验 /docs |

**回滚**: 9 个 commit 各自独立, 任一 commit 引发问题 `git revert <hash>` 即回滚该层.

---

## 关联文档

- Spec: [2026-06-17-fastapi-openapi-enhancement-design.md](../specs/2026-06-17-fastapi-openapi-enhancement-design.md)
- Handoff (实施完写): `docs/superpowers/handoffs/2026-06-17-fastapi-openapi-enhancement.md`
- 关联 spec: [2026-06-17-rbac-permission-system-design.md](../specs/2026-06-17-rbac-permission-system-design.md) (本次最大受益方)
- 关联 spec: [2026-06-16-rag-minio-integration-design.md](../specs/2026-06-16-rag-minio-integration-design.md) (MinIO chat 文件端点本次也补 metadata)
