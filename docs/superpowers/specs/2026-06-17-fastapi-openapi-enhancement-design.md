# FastAPI OpenAPI 展示增强 spec (2026-06-17)

> Status: **DRAFT v1 — 等审批**
> 目标: 让 `/docs` 页面从"能看"变成"好用", 14 router × 64 端点 + 3 inline × 3 端点 = **67 端点** + 全部 Pydantic schema 字段补中文说明, 支持 server 切换 + 错误码表 + example 预览.

## 1. 背景与动机

### 1.1 当前痛点 (3 类)

| 痛点 | 表现 | Swagger 截图描述 |
|------|------|------------------|
| **首页贫瘠** | `title="Product Order No. Decoder"`, `description` 一句话, 只覆盖 4 个端点 (`/decode` `/series` `/health` + `/api/output/*`), 完全没说 14 个 router 50+ 端点的存在 | 首页像 "Hello world" |
| **端点裸奔** | 67 个端点**全部**没设 `summary` / `description` / `responses`, 全部靠 docstring 自动推断. OpenAPI 区分 `summary` (一行) 和 `description` (Markdown), 不设就退化 | 端点列表只显示 path, 点进去 schema 栏空白 |
| **schema 字段无说明** | 14 个文件里 `Field(description=...)` 共 16 处 (memory 9 + chat_share 3 + api 3 + product_decoders 1), **0 处** `Field(description=...)` 在 `permissions` / `auth` / `admin` / `ingest` / `kg` / `approvals` / `eval` router 内 | 字段只看类型, 不知道含义/范围/例子 |

### 1.2 为什么现在做 (3 个 trigger)

1. **RBAC 落地后 admin 后台要靠 docs 自服务**: super_admin 在 `/admin/permissions` 改权限矩阵时, 需要 `/docs` 看 `/api/permissions/*` 端点完整 shape; 当前 docs 没 description, 改错了前端跟着炸
2. **前端 codegen 化酝酿中**: 虽本次不做 (非目标), 但 schema description 越早补, 后续接入越零成本
3. **Dify/前端联调**: chat 媒体 presign/finalize 端点 (chat_share/router.py:182, 206) Dify 端看不到完整请求/响应 shape, 调试来回切邮

### 1.3 不引入新库 (用户偏好)

- **不** 用 `spectree` / `flasgger` / `swagger-spec-validator` (集成性差, 跟 FastAPI 原生 OpenAPI 割裂)
- **不** 用 `openapi-typescript` 给前端 codegen (本次非目标)
- **不** 把 `example` payload 落 git (本次非目标, Swagger "Try it out" 体验降级)
- **只** 用 FastAPI 原生 `summary=` / `description=` / `responses=` / `Field(description=)` / `openapi_tags` 参数

## 2. 目标 (in-scope, 4 层)

1. **L1 全局 metadata** (`app.py`): 扩 title / description / contact / license / servers / openapi_tags
2. **L2 tag 标准化** (2 处): 中文 tag `"记忆"` → 英文 `"memory"`, 空格 tag `"chat share"` → `"chat-share"`
3. **L3 端点 metadata** (67 端点): 每端点加 `summary=` (中文 1 行) + `description=` (中文 Markdown 3-8 行) + `responses=` (200/4xx/5xx 各一行)
4. **L4 Pydantic 字段 description** (35+ 字段): 14 个 router 内 + 4 个 schema 文件内未补的字段全加 `Field(description=...)`

## 3. 非目标 (YAGNI)

- **不** 把 `example` payload 加进 `responses=` (用户偏好, 不入库)
- **不** 接 `openapi-typescript` / 任何 codegen 工具
- **不** 用 `spectree` / `flasgger` 等替代方案
- **不** 给 docs 加自定义 logo / 主题色 (跟项目 i18n 设计无关, 后续 UI spec 再说)
- **不** 把 `version="1.0.0"` 改 `importlib.metadata.version()` (硬编够用, 后续 ops spec 再说)
- **不** 拆 `app.py` 的 3 inline 端点到独立 router (为 OpenAPI 改架构不值)
- **不** 改 router 业务逻辑 / 鉴权 / 错误码本身, 只改 metadata
- **不** 补单元测试 (FastAPI `test_client.get("/openapi.json")` 已有现成检查点, 写 spec 时手动验一次即可)

## 4. 现状盘点 (4 张表)

### 4.1 全局 metadata (`src/product_decoders/app.py:59-64`)

```python
app = FastAPI(
    title="Product Order No. Decoder",  # ❌ 只覆盖 4 端点
    description="产品订货号通用解析服务 - 配置驱动, 多厂商",  # ❌ 一句话
    version="1.0.0",  # ⚠️ 硬编
    lifespan=_lifespan,
)
```

缺: `summary` / `contact` / `license_info` / `servers` / `openapi_tags`

### 4.2 Tag 现状 (15 router, 13 个 tag, 2 个不规范)

| Router | Tag | 规范? |
|--------|-----|-------|
| `product_decoders/app.py` | (无 tag, 走根 /) | ⚠️ 在 Swagger 侧栏顶部 "Default" 分组 |
| `api/routes.py` | `"rag"` | ✅ |
| `kg/router.py` | `"kg"` | ✅ |
| `eval/router.py` | `"evaluate"` | ✅ |
| `ingest/api.py` | `"ingest"` | ✅ |
| `auth/router.py` | `"auth"` | ✅ |
| `auth/auth_account_router.py` | `"account"` | ✅ |
| `auth/auth_admin_router.py` | `"admin"` | ✅ |
| `auth/auth_invite_router.py` | `"invite"` | ✅ |
| `approvals/router.py` | `"approvals"` | ✅ |
| `health/router.py` | `"health"` | ✅ |
| `memory/router.py` | `"记忆"` | ❌ 中英混用 |
| `chat_share/router.py` | `"chat share"` | ❌ 空格 |
| `permissions/router.py` | `"permissions"` | ✅ |
| `product_decoders/output_api.py` | `"output"` | ✅ |

### 4.3 端点 metadata 现状 (67 端点)

| 维度 | 计数 |
|------|------|
| 总端点数 | 67 (64 router + 3 inline) |
| 用了 `summary=` 的 | 0 |
| 用了 `description=` 的 | 0 |
| 用了 `responses=` 的 | 0 |
| 有 docstring 的 | 66 (只有 `api/routes.py:84` 的 `GET /api/v1/health` 没 docstring) |
| 用了 `response_model=` 的 | 30 (约 45%, 另一半直接 dict) |

### 4.4 Pydantic Field description 现状

| 文件 | `Field(description=...)` 数 | 评价 |
|------|---------------------------|------|
| `memory/schemas.py` | 9 | ✅ 详细 (含 min/max/例子) |
| `chat_share/schemas.py` | 3 | ⚠️ 缺大半 |
| `api/schemas.py` | 3 | ⚠️ 缺大半 |
| `ingest/schemas_presign.py` | 0 | ❌ |
| `product_decoders/app.py` (DecodeRequest) | 1 | - |
| `permissions/router.py` (4 BaseModel) | 0 | ❌ |
| `auth/router.py` (2 BaseModel) | 0 | ❌ |
| `auth/auth_account_router.py` (7 BaseModel) | 0 | ❌ |
| `auth/auth_admin_router.py` (7 BaseModel) | 0 | ❌ |
| `auth/auth_invite_router.py` (3 BaseModel) | 0 | ❌ |
| `approvals/router.py` (2 BaseModel) | 0 | ❌ |
| `kg/router.py` (6 BaseModel) | 0 | ❌ |
| `eval/router.py` | 0 BaseModel (用 inline) | - |
| `product_decoders/output_api.py` | 0 | - |
| `health/router.py` | 0 | - |
| **合计** | **16 处** | **目标 +50 处** |

## 5. 设计

### 5.1 L1 全局 metadata 改动 (`src/product_decoders/app.py:59-64`)

**改动**:

```python
app = FastAPI(
    title="RAG + 产品订货号解析服务",
    summary="RAG 检索增强 + 产品订货号解析的统一后端 API",
    version="0.2.0",  # 硬编, 后续 ops spec 改动态
    description=(
        "## 服务范围\n\n"
        "本服务为前端 Dify 工作流和管理后台提供以下能力:\n\n"
        "- **RAG 检索增强生成** (`/api/v1/*`): 查询 / 摄取 / 评估 (LlamaIndex)\n"
        "- **产品订货号解码** (`/decode` `/series`): 配置驱动的多厂商解析\n"
        "- **记忆系统** (`/api/memory/*`): Mem0 集成, 跨会话用户记忆\n"
        "- **知识图谱** (`/api/kg/*`): Neo4j 集成, 三元组 CRUD\n"
        "- **评估批** (`/api/evaluate/*`): 上传 CSV 跑 LlamaIndex 评估\n"
        "- **Ingest 子系统** (`/api/ingest/*`): 文件格式转换 (PDF/DOCX/CAD)\n"
        "- **聊天分享 + 文件上传** (`/api/chat/*`): 对话快照 + MinIO 集成\n"
        "- **审核工作流** (`/api/approvals/*`): 提交 / 批准 / 拒绝 / 重试\n"
        "- **权限管理** (`/api/permissions/*` + `/api/roles/*`): RBAC 配置\n"
        "- **用户管理** (`/api/admin/*`): super_admin 后台\n"
        "- **账号系统** (`/api/account/*`): 登录 / 登出 / 找回密码\n"
        "- **健康检查** (`/api/health/*`): 5 类系统指标\n\n"
        "## 鉴权\n\n"
        "大部分端点依赖 `CurrentUser` 依赖项, 通过 `x-user-token` header "
        "或 `rag_user_token` cookie 鉴权. 详情见各端点说明.\n\n"
        "## 错误码\n\n"
        "| 码 | 含义 | 触发场景 |\n"
        "|----|------|----------|\n"
        "| 400 | 请求参数错误 | 文件类型不支持 / 路径越权 / reset token 失效 |\n"
        "| 401 | 未登录 / token 无效 | `x-user-token` 缺失或不在 users 表 |\n"
        "| 403 | 权限不足 | require_page 失败 / require_super_admin 失败 |\n"
        "| 404 | 资源不存在 | task / approval / role / user 不存在 |\n"
        "| 409 | 状态冲突 | 创建重复 / 操作非法状态机转换 |\n"
        "| 413 | 文件过大 | ingest / chat 文件超过 20-200MB |\n"
        "| 422 | Pydantic 校验失败 | 字段类型错 / 长度越界 / 枚举值非法 |\n"
        "| 500 | 服务器内部错误 | LLM 拒抽 / Dify 503 / 未捕获异常 |\n"
        "| 503 | 外部依赖不可用 | MinIO / Neo4j / Dify / Mem0 不可达 |\n"
    ),
    contact={
        "name": "RAG Backend Team",
        "url": "https://github.com/forkai/rag",
        "email": "rag-team@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {"name": "rag", "description": "RAG 检索 + 摄取 + 评估 (LlamaIndex, 内部脚本用)"},
        {"name": "kg", "description": "知识图谱 CRUD (Neo4j 驱动)"},
        {"name": "evaluate", "description": "评估批管理 (上传 CSV + LlamaIndex 4 指标)"},
        {"name": "ingest", "description": "文档摄取 (PDF/DOCX/CAD/Archive → Markdown/JSON)"},
        {"name": "auth", "description": "匿名 token + 老 cookie 迁移 (灰度期)"},
        {"name": "account", "description": "账号登录 / 登出 / 找回密码 / 当前用户"},
        {"name": "admin", "description": "用户 + 邀请管理 (super_admin 限定)"},
        {"name": "invite", "description": "公开 invite 兑换 (无需登录)"},
        {"name": "approvals", "description": "审核工作流 (提交 → 批准 → 后台应用)"},
        {"name": "memory", "description": "Mem0 记忆管理 (登录用户限定)"},
        {"name": "chat-share", "description": "聊天快照分享 + 文件直传 MinIO"},
        {"name": "permissions", "description": "RBAC 角色 + 权限矩阵 (super_admin 限定)"},
        {"name": "health", "description": "系统级健康检查 (super_admin 限定)"},
        {"name": "output", "description": "Pipeline 产物只读 API (管理后台用)"},
    ],
    servers=[
        {"url": "http://localhost:8000", "description": "本地开发"},
        {"url": "https://staging-rag.example.com", "description": "Staging"},
        {"url": "https://rag.example.com", "description": "生产"},
    ],
    lifespan=_lifespan,
)
```

**效果**: Swagger 首页从 1 行 → 60+ 行可读文档, 含模块导航 + 错误码表 + 3 server 切换.

### 5.2 L2 Tag 标准化 (2 处改动)

| 文件 | 行 | 旧 | 新 |
|------|----|----|-----|
| `src/memory/router.py` | 39 | `tags=["记忆"]` | `tags=["memory"]` |
| `src/chat_share/router.py` | 45 | `tags=["chat share"]` | `tags=["chat-share"]` |

**说明**:
- 中文 tag 在 OpenAPI 3.0 spec 合法, 但 Swagger UI 渲染有 fallback 风险, 改英文更稳定
- 空格 tag 解析时 OpenAPI 3.0 转为 `chat%20share` 或保留原样, 不同 client 行为不一, 改 `-` 统一
- 中文说明**保留**在 `openapi_tags` 列表的 `description` 字段 (L1 已写), 不丢信息

### 5.3 L3 端点 metadata (67 端点, 按 router 分)

每端点补 3 个参数: `summary=` (1 行) + `description=` (3-8 行 Markdown) + `responses=` (200/4xx/5xx 各一行).

**统一模板**:

```python
@router.<method>(
    "<path>",
    summary="<中文 1 行>",
    description=(
        "## 用途\n\n"
        "<2-4 行说明>\n\n"
        "## 鉴权\n\n"
        "`<require_xxx>` 守卫 (具体规则见下).<若特殊>\n\n"
        "## 行为\n\n"
        "<业务细节 + 降级行为 + 错误条件>"
    ),
    responses={
        200: {"description": "<成功响应说明>"},
        400: {"description": "<4xx 错误条件>"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "权限不足 (require_page / require_super_admin)"},
        404: {"description": "资源不存在"},
        409: {"description": "状态冲突"},
        422: {"description": "Pydantic 校验失败"},
    },
    response_model=...,  # 已有保留
    status_code=...,     # 已有保留
)
```

**67 端点逐个 summary/description 草稿** (按 router 分, 表格形式, description 全文放实施期):

#### 5.3.1 `src/permissions/router.py` (7 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `GET /api/permissions` | "查询完整权限矩阵" | require_super_admin | 返 {roles[], matrix{}, pages[]}, super_admin 行代码层过滤 |
| `PATCH /api/permissions` | "批量更新权限矩阵" | require_super_admin | 拒绝改 super_admin, 拒绝未知 page_key/role, 一次 commit 全部 |
| `GET /api/permissions/me` | "查询当前用户权限" | resolve_user (anon OK) | 返 {role, allowed[], pages[]}, anon role="user" 拿 user 角色的 allowed |
| `GET /api/roles` | "列所有角色" | require_super_admin | 含 user_count (用此角色的 account 数), created_at, updated_at |
| `POST /api/roles` | "创建自定义角色" | require_super_admin | name 必须 match `[a-z0-9_]{2,32}`, 拒绝 name="super_admin" (400), 重复 name → 409 |
| `PATCH /api/roles/{name}` | "修改角色 label" | require_super_admin | name 不可改, 仅 label_zh/label_en, 系统角色也能改 |
| `DELETE /api/roles/{name}` | "删除自定义角色" | require_super_admin | is_deletable=False → 400, user_count > 0 → 409, 不存在 → 404 |

#### 5.3.2 `src/memory/router.py` (6 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `POST /api/memory/search` | "检索相关记忆" | require_account | 降级: Mem0 不可达 → `memories=[]`; 调 mem0 `m.search(query, user_id, limit)` |
| `POST /api/memory/add` | "写入本轮对话" | require_account | 失败静默吞, 仅日志; msgs 1-20 条 |
| `GET /api/memory/list` | "列当前用户所有记忆" | require_account | 降级: `memories=[]`; mem0 get_all 自带 user_id 隔离 |
| `DELETE /api/memory/all` | "清空当前用户所有记忆" | require_account | m.delete_all(user_id) 自带隔离; 返 `{deleted_count: 0}` 占位 (mem0 不返 count) |
| `PATCH /api/memory/{id}` | "编辑单条记忆" | require_account | 跨用户 → 403; 其他异常 → 500 |
| `DELETE /api/memory/{id}` | "删单条记忆" | require_account | 跨用户 → 403; 不区分 404/403 防 ID 探测 |

#### 5.3.3 `src/chat_share/router.py` (6 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `POST /api/chat/shares` | "创建对话快照分享" | resolve_user | 返 {share_id, url, title, expires_at, created_at} |
| `GET /api/chat/shares/{id}` | "公开读分享" | 无 (anon) | 公开端点, 不含 user_id / token; 不存在 → 404 |
| `DELETE /api/chat/shares/{id}` | "撤销分享" | resolve_user | 非所有者 → 统一 404 (防 ID 探测) |
| `POST /api/chat/files` | "上传文件 (透传 Dify)" | resolve_user | 20MB 上限; 白名单 image/audio/text/pdf; octet-stream 显式禁用 |
| `POST /api/chat/files/presign` | "签 PUT URL 直传" | resolve_user | URI: `s3://{bucket}/chat/{user_id}/{name}` 或 local 前缀; Pydantic + handler 双重校验 |
| `POST /api/chat/files/finalize` | "通知后端拉 bytes 转发 Dify" | resolve_user | URI 必须在 store 存在; Dify 失败 → URI 保留可重试 |

#### 5.3.4 `src/eval/router.py` (5 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `GET /api/evaluate/template` | "下载 CSV 模板" | 无 | 模板里无数据; text/csv |
| `GET /api/evaluate/runs` | "列历史评估" | require_page("evaluate") | admin 看全部, 普通 user_id 过滤 |
| `POST /api/evaluate/runs` | "上传 CSV 启动评估" | require_page("evaluate") | 写 ABC `s3://.../eval/{run_uuid}/dataset.csv`; 返 {id, status: pending}; BackgroundTask |
| `GET /api/evaluate/runs/{id}` | "查单次评估详情" | require_page("evaluate") | 含 samples[]; 别人 evaluation → 404 防泄露 |
| `POST /api/evaluate/runs/{id}/cancel` | "取消评估" | require_page("evaluate") | 返 {cancelled: bool} |

#### 5.3.5 `src/health/router.py` (1 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `GET /api/health/system` | "查询系统健康状态" | require_super_admin | 5 类检查聚合 (DB/MinIO/Dify/LLM/Mem0); 后台 5s 任务持续刷新 in-memory cache |

#### 5.3.6 `src/ingest/api.py` (7 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `POST /api/ingest/upload/presign` | "签上传 PUT URL" | require_page("submissions") | 单文件 ≤50MB, 任务总 ≤200MB; work_dir 走 ABC |
| `POST /api/ingest/upload/finalize` | "启动 Ingest 后台任务" | require_page("submissions") | task state 必须是 queued; BackgroundTask 调 process_uri |
| `POST /api/ingest/upload` | "上传 fallback (multipart 透传)" | require_page("submissions") | 浏览器无 presign 能力时用; 走 store.put_stream |
| `GET /api/ingest/tasks` | "列当前用户任务" | require_page("submissions") | 按 started_at 倒序 |
| `GET /api/ingest/tasks/{id}` | "查单任务 (轮询用)" | require_page("submissions") | 跨用户 404 |
| `GET /api/ingest/tasks/{id}/files/{name}` | "读产物文件" | require_page("submissions") | URI 模式 → presigned GET; Path 模式 → read_text; SAFE_NAME 白名单 |
| `GET /api/ingest/tasks/{id}/download` | "下载所有产物 zip" | require_page("submissions") | 流式 outputs/ + inputs/ 打包 |

#### 5.3.7 `src/auth/router.py` (2 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `POST /api/auth/migrate` | "老 token → Set-Cookie" | 无 | 灰度期: 老用户 localStorage 旧 token 换 HttpOnly cookie |
| `POST /api/auth/anon` | "生成匿名 token" | 无 | 32 字节 hex; 落 users 表; 同时 body 返 (兼容老前端) + Set-Cookie |

#### 5.3.8 `src/auth/auth_account_router.py` (6 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `POST /api/account/login` | "账号登录" | 无 | email + password → token + cookie; 错密码/禁用/不存在 → 统一 401 (防探测) |
| `POST /api/account/logout` | "登出 (清 cookie)" | 无 | 软登出: cookie 清, users 行不动 |
| `GET /api/account/me` | "查当前用户" | resolve_user | 返 7 字段; 2026-06-17 加 role 替 is_admin |
| `POST /api/account/seed-admin` | "创建首个 super_admin" | 无 (header `x-admin-token`) | 首次部署用; 已存在 super_admin → 409 |
| `POST /api/account/forgot-password` | "申请密码重置" | 无 | 总是 200 (不暴露邮箱是否存在); 返 reset_token + url |
| `POST /api/account/reset-password` | "用 token 重置密码" | 无 | token 失效/已用 → 400; new_password ≥ 8 字符 |

#### 5.3.9 `src/auth/auth_admin_router.py` (6 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `GET /api/admin/users` | "列所有用户" | require_super_admin (v2) | kind/is_active 下推到 SQL WHERE (防真实 bug: page 1 全 anon 过滤返空) |
| `POST /api/admin/users` | "创建邀请" | require_super_admin | 拒绝创 super_admin invite (400); 重复 email/未用 invite → 409 |
| `PATCH /api/admin/users/{id}` | "修改用户字段" | require_super_admin | 自禁 → 400; 改自己 role 降权 → 400; anon user 不允许 role 字段 |
| `POST /api/admin/users/{id}/reset-password` | "admin 重置用户密码" | require_super_admin | 返 temp_password (admin 复制手工发) |
| `GET /api/admin/invites` | "列邀请" | require_super_admin | status 过滤: pending/redeemed/expired/all; limit 200 |
| `DELETE /api/admin/invites/{token}` | "撤销未 redeem 邀请" | require_super_admin | 已 redeem → 400 (保留审计) |

#### 5.3.10 `src/auth/auth_invite_router.py` (2 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `GET /api/invites/{token}` | "查 invite 详情" | 无 | 公开端点; 不存在/已用/过期 → 400 (统一 msg 防探测) |
| `POST /api/invites/{token}/redeem` | "兑换 invite 创账号" | 无 | display_name 1-50 字符; password ≥ 8 字符; email 已注册 → 409 |

#### 5.3.11 `src/approvals/router.py` (8 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `POST /api/approvals` | "提交审核项" | require_login | kind+payload; 返 {id, kind, review_status, apply_status} |
| `GET /api/approvals` | "admin 列审核项" | require_admin | review/apply 可选过滤; skip/limit 分页 |
| `GET /api/approvals/me` | "列当前用户提交" | require_login | 自动 user_id 过滤 |
| `GET /api/approvals/stats` | "admin 概览" | require_admin | 返 {pending, applied, failed} 计数 |
| `GET /api/approvals/{id}` | "查单条详情" | require_login | 仅 submitter 或 admin 可见; payload 默认隐藏 (需 include_payload=true) |
| `POST /api/approvals/{id}/approve` | "批准 + 触发后台" | require_admin | review: pending→approved; BGTask 跑 apply; 不存在 → 404, 状态错 → 409 |
| `POST /api/approvals/{id}/reject` | "拒绝" | require_admin | reason 必填; reason=other 时 note 必填 (422) |
| `POST /api/approvals/{id}/retry` | "重试失败的" | require_admin | 限制: 仅 (approved, failed) 可重试 |

#### 5.3.12 `src/kg/router.py` (13 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `GET /api/kg/stats` | "知识图谱统计" | 无 | type: dify/neo4j/all; 不通时返空对象不抛异常 |
| `GET /api/kg/health` | "Dify 健康检查" | 无 | 返 {ok: bool, error?: str}; DIFY_API_KEY 缺失 → ok=False |
| `GET /api/kg/datasets` | "Dify 数据集列表" | 无 | DIFY_API_KEY 缺失 → 返 {data: []} |
| `GET /api/kg/segments` | "Dify segments 列表" | 无 | 需 dataset_id + document_id; 缺则返 {data: []} |
| `GET /api/kg/nodes` | "列 Neo4j 节点 (分页)" | 无 | skip/limit; Neo4j 不可达 → 返空 list (不挂整页) |
| `GET /api/kg/relationships` | "列 Neo4j 关系 (分页)" | 无 | skip/limit; 不可达 → 返空 list |
| `GET /api/kg/schemas` | "列可用 schema domain" | 无 | 扫 configs/*-schema.yaml |
| `GET /api/kg/schema` | "读 schema yaml" | 无 | domain 参数; 不存在 → 404 (fallback 第一个) |
| `GET /api/kg/products` | "列 Product 节点" | 无 | q 模糊匹配 model/name; limit |
| `GET /api/kg/templates/excel` | "下载 Excel QA 模板" | 无 | application/vnd.openxmlformats-... |
| `POST /api/kg/triples` | "提交三元组 (事务)" | 无 | 整批提交; 返 {success, failed, errors[]}; 写 audit log |
| `POST /api/kg/batch` | "大批量提交 (后台 task)" | 无 | 立即返 {task_id}; 后台跑; 调 `GET /api/kg/tasks/{id}` 查状态 |
| `GET /api/kg/tasks/{id}` | "查任务状态" | 无 | task_id 不存在 → 404 |

#### 5.3.13 `src/api/routes.py` (4 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `POST /api/v1/query` | "RAG 检索查询" | 无 (内部脚本) | top_k 1-100, 默认 5; 返 {response, sources[], latency_ms} |
| `POST /api/v1/evaluate` | "LlamaIndex 单条评估" | 无 (内部脚本) | 4 指标 + avg_score; 替换原 RAGAS (Windows 安装问题) |
| `POST /api/v1/ingest` | "触发文档摄取" | 无 (内部脚本) | input_dir/output_dir 走本地 FS; 返 {status, processed, errors} |
| `GET /api/v1/health` | "RAG 子系统 health" | 无 | 返 {status: "ok"}; 跟 `/api/health/system` 不同, 这个只 ping RAG |

#### 5.3.14 `src/product_decoders/output_api.py` (2 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `GET /api/output/files` | "列产物文件 (.md / .json)" | 无 | 按 mtime 倒序; local backend 走本地 FS, minio backend 走 ABC presigned GET |
| `GET /api/output/files/{name}` | "读单个产物文件" | 无 | SAFE_NAME 白名单; >10MB → 413; 路径越权 → 400; minio 返 presigned URL |

#### 5.3.15 `src/product_decoders/app.py` inline 端点 (3 端点)

| 端点 | summary | 鉴权 | 关键 description 要点 |
|------|---------|------|---------------------|
| `POST /decode` | "解码订货号" | 无 | 完整订货号如 `1LE0001-1AA42-1AA4`; 返结构化 + llm_view; 不识别 → 400 |
| `GET /series` | "列支持的产品系列" | 无 | 返 list[{series, manufacturer, name, prefix}] |
| `GET /health` | "解码服务 health" | 无 | 返 {status: "ok", series_count: int} |

### 5.4 L4 Pydantic 字段 description (~50 字段)

**原则**: 每字段写清 3 件事 — 含义 / 取值范围 / 一个具体例子.

**改动清单** (按文件):

#### 5.4.1 `src/permissions/router.py` (4 BaseModel)

```python
class PermissionUpdate(BaseModel):
    role_name: str = Field(..., min_length=2, max_length=32, description="角色名, 必须是 `roles` 表里存在的, 例: 'admin' / 'user' / 自定义")
    page_key: str = Field(..., description="页面 key, 7 选 1: dashboard / knowledge / chat / memory / evaluate / submissions / admin")
    allowed: bool = Field(..., description="true=允许访问, false=拒绝")

class PermissionsPatchRequest(BaseModel):
    updates: list[PermissionUpdate] = Field(..., min_length=1, max_length=100, description="批量更新项, 一次 commit 全部生效")

class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=32, pattern=r"^[a-z0-9_]+$", description="角色标识, 例: 'reviewer' / 'editor' (小写字母数字下划线)")
    label_zh: str = Field(..., max_length=64, description="中文显示名, 例: '审核员'")
    label_en: str = Field(..., max_length=64, description="英文显示名, 例: 'Reviewer'")
    permissions: dict[str, bool] = Field(default_factory=dict, description="初始权限矩阵, key 为 page_key, value 为 allowed; 未知 key 跳过")

class UpdateRoleRequest(BaseModel):
    label_zh: str | None = Field(None, max_length=64, description="新中文 label; 传 null 不改")
    label_en: str | None = Field(None, max_length=64, description="新英文 label; 传 null 不改")
```

#### 5.4.2 `src/auth/router.py` (2 BaseModel)

```python
class AnonTokenResponse(BaseModel):
    token: str = Field(..., description="32 字节 hex (64 字符), 客户端存 cookie 后续请求带")

class MigrateRequest(BaseModel):
    token: str = Field(..., min_length=1, description="老 localStorage 里的 rag_user_token, 用于换 Set-Cookie")
```

#### 5.4.3 `src/auth/auth_account_router.py` (7 BaseModel)

```python
class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254, description="账号邮箱, 例: admin@rag.local")
    password: str = Field(..., min_length=1, description="明文密码, 服务端 bcrypt 校验")

class AccountOut(BaseModel):
    id: int = Field(..., description="Account 主键")
    email: str = Field(..., description="账号邮箱")
    display_name: str | None = Field(None, description="显示名, 可空")
    role: str = Field(..., description="角色名, 例: 'user' / 'admin' / 'super_admin' (2026-06-17 替原 is_admin)")
    is_admin: bool = Field(..., description="派生: role in ('admin', 'super_admin') (兼容旧前端)")

class LoginResponse(BaseModel):
    token: str = Field(..., description="32 字节 hex, 客户端用此换 cookie")
    account: AccountOut

class SeedAdminRequest(BaseModel):
    email: str = Field(..., max_length=254, description="首个 super_admin 邮箱")
    password: str = Field(..., min_length=8, description="明文密码")
    display_name: str | None = Field(None, description="显示名, 默认取 email @ 前")

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="申请重置的邮箱; 邮箱不存在时仍返 200")

class ForgotPasswordResponse(BaseModel):
    reset_token: str | None = Field(None, description="重置 token; 邮箱不存在时为 null")
    reset_url: str | None = Field(None, description="重置 URL: /reset-password?token=...")

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="forgot-password 返的 reset_token")
    new_password: str = Field(..., min_length=8, description="新密码, ≥ 8 字符")
```

#### 5.4.4 `src/auth/auth_admin_router.py` (7 BaseModel)

```python
class UserItem(BaseModel):
    id: int = Field(..., description="User 主键")
    email: str | None = Field(None, description="账号邮箱; 匿名用户为 null")
    display_name: str | None = Field(None, description="显示名")
    role: str = Field(..., description="角色名; 匿名用户固定 'user'")
    is_admin: bool = Field(..., description="派生: role in ('admin', 'super_admin')")
    is_active: bool = Field(..., description="是否启用; 匿名用户永远 True")
    kind: Literal["account", "anon"] = Field(..., description="'account' = 正式账号, 'anon' = 匿名 token 用户")
    account_id: int | None = Field(None, description="关联 Account.id; 匿名用户为 null")
    created_at: datetime
    last_seen_at: datetime
    last_login_at: datetime | None = Field(None, description="最近登录时间; 匿名用户为 null")

class UserListResponse(BaseModel):
    items: list[UserItem]
    total: int = Field(..., description="满足过滤条件的总条数 (受分页影响前)")
    page: int = Field(..., ge=1, description="当前页码, 1-based")
    page_size: int = Field(..., ge=1, le=100, description="每页条数")

class CreateInviteRequest(BaseModel):
    email: str = Field(..., max_length=254, description="被邀请人邮箱")
    role: str = Field("user", description="邀请关联的角色名, 必须是 roles 表里存在的; 不能是 'super_admin'")
    display_name: str | None = Field(None, description="可选显示名, 写入 Account.display_name")

class CreateInviteResponse(BaseModel):
    invite_token: str = Field(..., description="邀请 token, 拼到 /invite/{token} 链接")
    invite_url: str = Field(..., description="完整邀请 URL: /zh/invite/{invite_token}")
    email: str
    role: str
    is_admin: bool = Field(..., description="派生: role in ('admin', 'super_admin')")

class PatchUserRequest(BaseModel):
    is_active: bool | None = Field(None, description="新启用状态; 自禁 → 400")
    role: str | None = Field(None, description="新角色; 改自己降权 → 400; anon user 不接受")
    display_name: str | None = Field(None, max_length=64, description="新显示名")

class InviteItem(BaseModel):
    id: int
    token: str = Field(..., description="邀请 token, 用于 /api/admin/invites/{token} 撤销")
    email: str
    invited_by_account_id: int = Field(..., description="发起邀请的 super_admin account_id")
    expires_at: datetime
    redeemed_at: datetime | None = Field(None, description="兑换时间; 未兑换为 null")
    created_at: datetime

class InviteListResponse(BaseModel):
    items: list[InviteItem]
    total: int = Field(..., description="满足 status 过滤的总条数")
```

#### 5.4.5 `src/auth/auth_invite_router.py` (3 BaseModel)

```python
class InviteInfo(BaseModel):
    email: str = Field(..., description="邀请的邮箱 (用于前端 confirm 提示)")
    expires_at: datetime = Field(..., description="过期时间")

class RedeemRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=50, description="账号显示名")
    password: str = Field(..., min_length=8, description="密码, ≥ 8 字符")

class RedeemResponse(BaseModel):
    token: str = Field(..., description="兑换后的 32 字节 hex token")
    email: str
    account: AccountOut  # 复用 auth_account_router 的 AccountOut
```

#### 5.4.6 `src/approvals/router.py` (2 BaseModel)

```python
class RejectBody(BaseModel):
    reason: RejectReason = Field(..., description="拒绝原因枚举: invalid / duplicate / outdated / other")
    note: str | None = Field(None, max_length=500, description="备注; reason=other 时必填, 其他情况可选")

class SubmitBody(BaseModel):
    kind: ApprovalKind = Field(..., description="审核类型枚举, 决定 apply 阶段用哪个 executor")
    payload: dict[str, Any] = Field(..., description="自由 JSON, 落库前 json.dumps; 业务侧 schema 由 kind 决定")
```

#### 5.4.7 `src/kg/router.py` (6 BaseModel)

```python
class TripleRowIn(BaseModel):
    from_label: str = Field(..., description="起点节点 label, 例: 'Product' / 'Series' / 'Spec'")
    from_key: str = Field(..., description="起点节点匹配字段, 例: 'model'")
    from_value: str = Field(..., description="起点节点匹配值, 例: '1LE0001-1AA42-1AA4'")
    rel_type: str = Field(..., description="关系类型, 自由字符串, 例: 'HAS_SPEC' / 'BELONGS_TO' / 'MATCHES'")
    to_label: str = Field(..., description="终点节点 label")
    to_key: str = Field(..., description="终点节点匹配字段")
    to_value: str = Field(..., description="终点节点匹配值")
    properties: dict = Field(default_factory=dict, description="关系附加属性, 自由 JSON")

class TriplesRequest(BaseModel):
    rows: list[TripleRowIn] = Field(..., min_length=1, max_length=1000, description="三元组列表, 整批事务提交")

class TriplesResponse(BaseModel):
    success: int = Field(..., description="成功条数")
    failed: int = Field(..., description="失败条数")
    errors: list[str] = Field(default_factory=list, description="错误描述列表, 与 rows 顺序对应")

class BatchItem(BaseModel):
    target: Literal["dify", "neo4j"] = Field(..., description="'dify' = 推 Dify 知识库, 'neo4j' = 推 Neo4j 知识图谱")
    type: str = Field(..., description="操作类型, 例: 'document' / 'triple' (由 executor 解释)")
    payload: dict = Field(..., description="操作 payload, schema 由 type 决定")

class BatchRequest(BaseModel):
    items: list[BatchItem] = Field(..., min_length=1, max_length=5000, description="批量操作列表")

class BatchResponse(BaseModel):
    task_id: str = Field(..., description="后台 task ID, 调 GET /api/kg/tasks/{task_id} 查状态")
```

#### 5.4.8 `src/chat_share/schemas.py` (3 字段补充)

```python
class PresignChatFileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="文件名, 例: 'image.png'; 不含路径分隔符")
    size: int = Field(..., ge=0, le=20*1024*1024, description="字节数, ≤ 20MB")
    mime: str = Field(..., min_length=1, max_length=100, description="MIME, 例: 'image/png' / 'application/pdf'; 前缀须匹配白名单")

class PresignChatFileResponse(BaseModel):
    uri: str = Field(..., description="完整 URI, 例: 's3://rag-ingest/chat/{user_id}/image.png'")
    put_url: str = Field(..., description="预签名 PUT URL, 浏览器直传, 900s 有效")
    mime: str

class FinalizeChatFileRequest(BaseModel):
    uri: str = Field(..., min_length=1, max_length=500, description="presign 返的 URI; 必须在 store 存在")
    name: str = Field(..., min_length=1, max_length=255, description="文件名, 用于 Dify uploadFileId 关联")
    mime: str = Field(..., min_length=1, max_length=100, description="MIME, 用于 Dify uploadFileId 关联")
```

#### 5.4.9 `src/ingest/schemas_presign.py` (4 字段补充)

```python
class PresignFileItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="文件名, 例: 'manual.pdf'; 扩展名必须在白名单")
    size: int = Field(..., ge=0, le=200*1024*1024, description="字节数, 单文件 ≤ 200MB; 任务总 ≤ 200MB")
    mime: str = Field(..., min_length=1, max_length=100, description="MIME, 例: 'application/pdf' / 'image/png'")

class PresignUploadRequest(BaseModel):
    files: list[PresignFileItem] = Field(..., min_length=1, max_length=50, description="文件列表, 1-50 个")

class PresignUploadItem(BaseModel):
    name: str = Field(..., description="文件名")
    uri: str = Field(..., description="完整 URI, 例: 's3://rag-ingest/inputs/{task_id}/input/manual.pdf'")
    put_url: str | None = Field(None, description="预签名 PUT URL; local backend 可能为 null (走 fallback upload 端点)")
    mime: str

class FinalizeUploadRequest(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=64, description="presign 返的 task_id")
```

#### 5.4.10 `src/api/schemas.py` (3 字段补充)

```python
class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="用户查询文本")
    user_id: str | None = Field(None, description="用户 ID, 用于 Mem0 记忆检索; null = 跳过记忆")
    top_k: int = Field(5, ge=1, le=100, description="检索条数, 默认 5")

class SourceNode(BaseModel):
    file_path: str = Field("", description="源文件路径, 例: '/data/docs/manual.pdf'")
    page_label: str = Field("", description="页码标签, 例: '3' / 'A-2'")
    text: str = Field("", description="源文本片段")

class EvaluateRequest(BaseModel):
    question: str = Field(..., description="评估的问题")
    answer: str = Field(..., description="系统生成的答案")
    contexts: list[str] = Field(..., min_length=1, description="检索到的上下文列表")
    ground_truth: str | None = Field(None, description="人工标注的真值, 缺则 context_recall 不可算")
```

## 6. 实施计划 (3 阶段, P0/P1/P2 独立可发)

### 6.1 P0 - 全局 + Tag 标准化 (1 小时, 1 commit)

**单文件改动**: `src/product_decoders/app.py` (替换 FastAPI(...) 调用) + `src/memory/router.py:39` + `src/chat_share/router.py:45` (改 2 个 tag)

**验收**:
- [ ] `curl http://localhost:8000/openapi.json | jq .info` 看到 title/description/contact/license/servers/openapi_tags
- [ ] Swagger UI 顶部出现 3 个 server 下拉
- [ ] Swagger UI 侧栏出现 14 个 tag 分组 (含 "memory" / "chat-share", 不再有 "记忆" / "chat share")
- [ ] 侧栏点开任一 tag, 看到中文 description

### 6.2 P1 - 67 端点 metadata (~6 小时, 6 commits)

按 router 分批, 每批 1 commit:

| Commit | 范围 | 端点数 | 工时 |
|--------|------|--------|------|
| `feat(openapi): permissions 7 端点 metadata` | `permissions/router.py` | 7 | 0.5h |
| `feat(openapi): memory + chat_share 12 端点` | `memory/router.py` + `chat_share/router.py` | 12 | 1h |
| `feat(openapi): ingest + eval 12 端点` | `ingest/api.py` + `eval/router.py` | 12 | 1h |
| `feat(openapi): auth 14 端点 (auth + account + admin + invite)` | 4 auth router | 16 | 1.5h |
| `feat(openapi): approvals + kg 21 端点` | 2 router | 21 | 1.5h |
| `feat(openapi): output + api + inline 9 端点` | output_api + routes + app inline | 9 | 0.5h |

**验收 (每 commit)**:
- [ ] `curl http://localhost:8000/openapi.json | jq '.paths["/api/<path>"].<method>.summary, .description, .responses'` 三个 key 都有
- [ ] Swagger UI 点开端点, 看到 summary 粗体 + description 渲染的 Markdown + Responses 表格有 4xx/5xx

### 6.3 P2 - Pydantic 字段 description (~2 小时, 2 commits)

| Commit | 范围 | 字段数 | 工时 |
|--------|------|--------|------|
| `feat(openapi): permissions + approvals + kg + chat_share schemas` | 4 文件 | 16 字段 | 1h |
| `feat(openapi): auth + ingest + api schemas` | 6 文件 | 22 字段 | 1h |

**验收 (每 commit)**:
- [ ] `curl http://localhost:8000/openapi.json | jq '.components.schemas.<ModelName>.properties.<field>.description'` 全部有
- [ ] Swagger UI 点开任一端点的 "Schemas" 折叠, 字段下方有灰色描述

## 7. 风险 + 缓解

| 风险 | 缓解 |
|------|------|
| 中文 summary 在 OpenAPI 3.0 渲染时部分 client (e.g. Postman 旧版) 乱码 | 英文 summary 太长, 中文更易读; 接受 Postman 旧版降级, 现代 client (Postman 10+/Insomnia 2023+) OK |
| 改 tag 影响客户端代码生成 (e.g. `openapi-typescript` 后续接入) | 本次不接入 codegen; 后续接入时 groupBy: 'tags' 即可, 英文 tag 更友好 |
| `description` 里嵌 Markdown 表格在 Swagger UI 渲染, ReDoc 不支持 | 99% 团队用 Swagger UI (FastAPI 默认), ReDoc 用户手动接受降级 |
| 改 `responses` 加 4xx 后, 业务代码 4xx 文案跟 spec 不一致会被发现 | 这是好事, 借此对齐; 不一致就改业务或改 spec 保持一致 |
| 改 `summary` / `description` 不影响运行时, 不会破测试 | ✅ 0 风险, FastAPI 把这些只用于 OpenAPI 生成, 不进请求处理 |

## 8. 验收 checklist (整体)

### 8.1 Swagger UI (`http://localhost:8000/docs`) 视觉

- [ ] 首页: 60+ 行可读, 含模块导航 + 错误码表 + 3 server 切换
- [ ] 侧栏: 14 个 tag 分组, 每个有中文 description
- [ ] 端点列表: summary 粗体一行能看出干啥
- [ ] 端点详情: description 渲染 Markdown (含 `##` 标题 + 表格)
- [ ] Schemas 折叠: 字段下方灰色 description, 标明含义 + 范围 + 例子
- [ ] Responses 折叠: 200/400/401/403/404/409/413/422/500/503 表格列出

### 8.2 OpenAPI JSON (`/openapi.json`) 结构

```bash
# 验证 title
jq '.info.title'   # "RAG + 产品订货号解析服务"

# 验证 contact
jq '.info.contact'  # {name, url, email}

# 验证 servers
jq '.servers | length'  # 3

# 验证 openapi_tags
jq '.tags | length'  # 14

# 验证 summary 覆盖
jq '[.paths[].[get,post,patch,delete,put][]?.summary] | map(select(. == null)) | length'  # 0 (全有 summary)

# 验证 description 覆盖
jq '[.paths[].[get,post,patch,delete,put][]?.description] | map(select(. == null)) | length'  # 0

# 验证 responses 覆盖
jq '[.paths[].[get,post,patch,delete,put][]?.responses | keys] | map(select(length < 2)) | length'  # 0 (每端点至少 200 + 1 个 4xx)
```

### 8.3 性能

- [ ] `curl /openapi.json | wc -c` 增加 < 50KB (description 是文本, 不影响性能)
- [ ] Swagger UI 首屏渲染 < 1s (description 多但都是静态, 不进 JS bundle)

## 9. 实施后 commit 模板

```
feat(openapi): enhance Swagger docs metadata (P0/P1/P2)

P0 - 全局 metadata + tag 标准化
- app.py: 加 title/description/contact/license/servers/openapi_tags
- memory/router.py:39 改 tag "记忆" → "memory"
- chat_share/router.py:45 改 tag "chat share" → "chat-share"

P1 - 67 端点 metadata
- [每个 router 文件]: 给 @router.<method> 加 summary= + description= + responses=

P2 - Pydantic 字段 description
- [每个 schema 文件 + router 内 BaseModel]: 给每个字段加 Field(description=...)

效果:
- Swagger UI 首页从 1 行 → 60+ 行可读
- 端点列表有 summary, 详情有 description + responses
- Schema 字段有含义/范围/例子
- /openapi.json 体积 +X KB (description 文本)

Refs: docs/superpowers/specs/2026-06-17-fastapi-openapi-enhancement-design.md
```

## 10. 关联文档

- 触发 plan: `docs/superpowers/plans/2026-06-17-fastapi-openapi-enhancement.md` (待写, 跟 spec 配套)
- 相关: `2026-06-17-rbac-permission-system-design.md` (本次最大用户: super_admin 改权限矩阵时要看 docs)
- 关联: `2026-06-16-rag-minio-integration-design.md` (MinIO chat 文件端点本次也补 metadata)
