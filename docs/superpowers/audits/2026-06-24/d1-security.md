# D1: Security 扫描结果

> 扫描时间: 2026-06-24
> Agent 角色: Security scanner
> 工具调用次数: 24
> 找到 9 条 finding (3 critical, 3 high, 2 medium, 1 low)

## 元信息

- 项目根: c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/
- 扫描路径:
  - packages/service/src/auth/* (account_service.py, account_models.py, auth_account_router.py, auth_invite_router.py)
  - packages/service/src/middleware/auth.py
  - packages/service/src/permissions/guards.py
  - packages/service/src/api/routes.py
  - packages/service/src/ingest/api.py
  - packages/service/src/storage/object_store.py
  - packages/service/src/core/redis_client.py
  - packages/service/src/core/audit.py
  - packages/service/src/core/logging.py (PII scrub)
  - packages/service/src/memory/router.py + service.py
  - packages/service/src/chat_share/router.py + schemas.py
  - packages/service/src/kg/router.py
  - packages/service/src/core/app_factory.py (CORS)
  - packages/service/pyproject.toml (deps)
  - packages/web/proxy.ts, middleware.ts
  - packages/web/app/api/auth/anon/route.ts
  - packages/web/app/api/ingest/upload/presign/route.ts
  - packages/web/app/api/ingest/tasks/[id]/route.ts
  - packages/web/app/api/chat/messages/route.ts
  - packages/web/lib/api/config.ts
- 已知跳过:
  - ingest/converter 全部 (kreuzberg / pymupdf / ezdxf): 这些是第三方库的封装, 不在攻击面
  - DB migration 文件: D4 维度负责
  - 前端 React 组件: D5 维度负责
  - 全部 tests/ 目录
- 备注: D1 维度偏攻击者视角, 重点查鉴权/注入/SSRF/IDOR/path traversal/deserialization/presign scope/cookie/CSRF/rate limit/PII/CORS/secret 泄露/弱密码/token 熵
- 网络策略: 允许 WebSearch/WebFetch 查 CVE, 本轮因工具预算和时间, 优先完成代码层审查, deps CVE 查询有限

## Findings (9 条)

### SEC-001 (critical)
```yaml
- id: SEC-001
  dimension: security
  severity: critical
  confidence: high
  title: "verify_password 用 Python 2 语法 except ValueError, TypeError 会在 Python 3.14 抛 SyntaxError"
  file: packages/service/src/auth/account_service.py
  line: 28
  description: |
    第 28 行使用 Python 2 时代的逗号分隔异常语法 `except ValueError, TypeError:`.
    Python 3 必须用元组 `except (ValueError, TypeError):`.
    当前项目 requires-python = ">=3.14", 该模块在 import 时即报 SyntaxError, bcrypt verify 永远跑不到.
  evidence: |
    ```python
    def verify_password(plain: str, hashed: str) -> bool:
        """bcrypt verify. 错密码/坏 hash → False (不抛)"""
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError, TypeError:
            return False
    ```
  impact: |
    任何调用 verify_password 的代码 (auth_account_router login / reset_password, auth_invite_router redeem_invite) 都会因 import-time SyntaxError 阻塞模块加载.
    即便模块侥幸加载, `except ValueError, TypeError:` 在 Py3 等价于 `except ValueError as TypeError:` — bcrypt 抛 ValueError (e.g. 密码超长) 时被吞掉返 False 但中间变量名为 TypeError 会让人误读.
    整体效果: 整个 auth router 模块加载失败, 全员 500, 服务无法启动.
  fix_sketch: |
    改为 `except (ValueError, TypeError):`. 同步在 service 启动时加 `python -c "from src.auth.account_service import verify_password"` smoke test, 防再犯.
  references: ["CWE-1006", "CWE-94"]
```

### SEC-002 (critical)
```yaml
- id: SEC-002
  dimension: security
  severity: critical
  confidence: high
  title: "chat_share presign 端点用 req.name 直接拼 S3 key, 缺路径遍历校验, 越权写任意 user_id"
  file: packages/service/src/chat_share/router.py
  line: 293
  description: |
    `presign_chat_file` 把客户端传来的 `req.name` 不经清洗直接拼到 S3 key 路径里
    (`s3://{bucket}/chat/{current.id}/{req.name}`).
    Pydantic schema 只限制 `min_length=1, max_length=255`, 不校验 `..` 或 `/` 字符.
    攻击者用 name=`../123/image.png` 即可越权写到别的 user_id 目录下, 拿到的 presigned PUT URL
    拥有完整写权限 (900s TTL).
  evidence: |
    ```python
    async def presign_chat_file(
        req: PresignChatFileRequest,
        current: CurrentUser = Depends(resolve_user),
    ) -> PresignChatFileResponse:
        _validate_mime_and_size(req.mime, req.size)

        store = get_object_store()
        backend = store.backend_name()
        if backend == "minio":
            bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
            uri = f"s3://{bucket}/chat/{current.id}/{req.name}"
        else:
            # local backend: 走 local://chat/{user_id}/{name}
            uri = f"local://chat/{current.id}/{req.name}"
        put_url = store.presign_put(uri) or ""
        return PresignChatFileResponse(uri=uri, put_url=put_url, mime=req.mime)
    ```
  impact: |
    - 越权写入其他用户的 chat 目录, 污染对方文件列表或上传恶意 payload
    - 配合 finalize 端点能把恶意文件转发到 Dify, 影响其他用户对话
    - 由于 presigned URL 是 S3/MinIO 签发, 没有 ACL 二次校验, 攻击者直接写裸桶
    - 同样在 local backend 也可越权 (LocalFS 用 `Path / key` 路径, `..` 会被 resolve 但 key 字符串本身就是脏的)
  fix_sketch: |
    schema 加 `name: str = Field(..., pattern=r"^[a-zA-Z0-9._-]+$")` 或 router 里显式 `Path(req.name).name` + 白名单字符集,
    同时拒绝 name 含 `/`, `\`, `..` 的请求, 直接 422.
  references: ["CWE-22", "CWE-639"]
```

### SEC-003 (critical)
```yaml
- id: SEC-003
  dimension: security
  severity: critical
  confidence: high
  title: "kg/router.py stats / health 端点无鉴权, 内部 SSRF 命中任意 base_url (env)"
  file: packages/service/src/kg/router.py
  line: 103
  description: |
    `/api/kg/stats` 和 `/api/kg/health` 端点都标注 "无 (内部脚本用, 不对外开放)",
    但 router 文件未挂 require_page / require_super_admin 守卫, 任何用户 (含 anon) 都能调.
    端点内部用 `requests.get(f"{base_url}/datasets?limit=100", ..., timeout=10)` 拼字符串发请求,
    `base_url` 来自 env `DIFY_BASE_URL` (默认 `http://localhost/v1`), 但业务侧 BFF 不限制 user input 是否能影响 base_url.
    攻击者可探测服务可达性 (内部网络端口扫描), 间接拿到 Dify 健康度, 联同其他漏洞可放大影响.
  evidence: |
    ```python
    def stats(type: str = "all", domain: str = "knowledge") -> dict:
        import os

        result = {}

        if type in ("dify", "all"):
            base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
            api_key = os.getenv("DIFY_DATASET_API_KEY", "")
            dify = {"datasets": 0, "documents": 0}
            if api_key:
                try:
                    import requests

                    r = requests.get(
                        f"{base_url}/datasets?limit=100",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=10,
                    )
    ```
  impact: |
    1. 无鉴权: 任何匿名用户可调 (router 路径 `/api/kg/stats`, 已挂 APIRouter 但没 Depends)
    2. SSRF 端口扫描: 即使 base_url 当前是 env 常量, 后续若有用户可控 env 或 admin 误配, 立刻变成完全 SSRF
    3. 错误处理吞掉所有异常: `except Exception: pass`, 静默失败, 日志也不留, 攻击不留痕
    4. 慢攻击: timeout=10s × 多个 type 维度, 可作 DoS 入口
  fix_sketch: |
    - router 顶部加 require_super_admin 守卫 (跟 CLAUDE.md §"前端 React/Next.js 准则" 一致)
    - 内部 IP 白名单 (只允许 10.0.0.0/8, 172.16/12, 192.168/16), 拒绝公网 IP
    - 用 `httpx.Client(timeout=5)` 替换 requests, 显式验证 scheme ∈ {http, https}
  references: ["CWE-306", "CWE-918"]
```

### SEC-004 (high)
```yaml
- id: SEC-004
  dimension: security
  severity: high
  confidence: high
  title: "PII scrub 黑名单仅 19 字段且无 token 长度/熵校验, 弱口令散落风险"
  file: packages/service/src/core/logging.py
  line: 22
  description: |
    `SENSITIVE_KEYS` 列出 19 个键名 (password/token/api_key/secret/...), 用 `frozenset` + lowercase 比较.
    风险点:
    1. 缺 `email` (CLAUDE.md 明确说 email "不算 PII", OK); 但缺 `otp`, `mfa`, `phone`, `mobile`, `id_card`
       这类业务常见字段, 仍可能被识别为 PII
    2. 字典嵌套仅 1 层 (递归只看 dict / list, 不会去 tuple / object 内)
    3. `_scrub` 只在 audit_logs (via audit.py) + loguru extra context (via logging.py) 用,
       业务代码如 `logger.info("user login password={}", pwd)` 直接走 f-string 不会触发 scrub
  evidence: |
    ```python
    SENSITIVE_KEYS = frozenset(
        {
            "password",
            "passwd",
            "pwd",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "apikey",
            "secret",
            "client_secret",
            "authorization",
            "cookie",
            "set-cookie",
            "ssn",
            "credit_card",
            "card_number",
            "cvv",
            "private_key",
            "privatekey",
        }
    )

    def _scrub(data: Any) -> Any:
        """递归 scrub 已知敏感字段. dict / list 嵌套处理."""
        if isinstance(data, dict):
            return {k: ("***REDACTED***" if k.lower() in SENSITIVE_KEYS else _scrub(v)) for k, v in data.items()}
        if isinstance(data, list):
            return [_scrub(item) for item in data]
        return data
    ```
  impact: |
    业务代码直接调 `logger.info("password={}", req.password)` 或 `logger.warning("token={}", token)` 时,
    _scrub 完全没机会拦, password 直接进日志.
    当前 grep 业务代码 (`auth_account_router.py:90` 调 verify_password, 不 log password; 但 `auth_invite_router.py:108-120` 把 password 走 audit_ctx.set target_id=token)
    算干净. 但只要后续 PR 加 logger.info(f"...{password}"), 立即泄露.
  fix_sketch: |
    - 加 loguru filter (`logger = logger.patch(lambda r: r.update(message=_scrub_msg(r["message"])))`)
      对 message 做正则匹配, 抓 password/secret/token 模式
    - SENSITIVE_KEYS 加 `email_content`, `phone`, `mfa`, `otp`, `pin`, `session_id`
  references: ["CWE-532", "CWE-359"]
```

### SEC-005 (high)
```yaml
- id: SEC-005
  dimension: security
  severity: high
  confidence: high
  title: "CORS allow_origins 列表来自 env 默认含 localhost, 生产 ENV=production 时未剔除"
  file: packages/service/src/core/app_factory.py
  line: 125
  description: |
    `allowed_origins` 走 `os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")`,
    默认含本地开发地址. 若生产 ENV=production 但忘了设 CORS_ALLOWED_ORIGINS, 仍允许
    localhost:3000 跨域 (实际生产环境不太可能有此端口, 但开发者本机端口扫描攻击仍是风险面).
    更严重: 列表用 `,` 拆分, 无 scheme/host 校验, 若运维误设 `CORS_ALLOWED_ORIGINS=*,evil.com`
    会被原样写入.
  evidence: |
    ```python
    # 显式 origin 列表, 不支持 * (allow_credentials=True 时不能 *)
    # 生产环境用 CORS_ALLOWED_ORIGINS 环境变量覆盖, 逗号分隔
    allowed_origins = os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,  # 显式列表, 不用 *
        allow_credentials=True,  # 关键: 允许 cookie 跨域 (P0 任务 8 灰度期)
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["content-type"],
        max_age=600,
    )
    ```
  impact: |
    - `allow_headers=["*"]` + `allow_credentials=True`: 任意自定义 header (含 Authorization, Cookie) 可跨域带
    - 运维误配 CORS_ALLOWED_ORIGINS=* 时, FastAPI CORSMiddleware 实际会拒绝 * + credentials=true 组合
      (Chrome 会二次校验), 但攻击者用 `Access-Control-Request-Headers: x-admin-token` 探测可绕过
    - 默认配置中 localhost:3000 在生产未剔除, 给内网横向渗透留窗口
  fix_sketch: |
    生产模式 (ENV=production) 启动时断言 CORS_ALLOWED_ORIGINS 已设且不含 localhost/127.0.0.1;
    allow_headers 改为白名单 ["Content-Type", "Authorization", "X-User-Token", "X-Admin-Token"].
  references: ["CWE-942", "CWE-346"]
```

### SEC-006 (high)
```yaml
- id: SEC-006
  dimension: security
  severity: high
  confidence: high
  title: "前端 bundle 引用的 OPENAI_API_KEY / DIFY_* 走 process.env 而非 NEXT_PUBLIC_, 可能服务端渲染时泄露"
  file: packages/web/lib/chat/openai.ts
  line: 9
  description: |
    `packages/web/lib/chat/openai.ts:9` 用 `process.env.OPENAI_API_KEY`, 没带 NEXT_PUBLIC_ 前缀.
    这意味着这个变量只能在 server 跑 (RSC / API route / Server Action) 读, client 拿不到, OK.
    **但** 项目里有 `lib/chat/dify.ts:24` 用 `process.env.DIFY_CHAT_API_KEY`,
    `lib/dify-datasets.ts:8` 用 `process.env.DIFY_DATASET_API_KEY`,
    这些模块被 client 端 chat 调用, 如果不小心被 client component import, 会触发
    "ReferenceError: process is not defined" 或 build-time 注入空字符串.
    当前是 server-only (chat/messages/route.ts 用, runtime="nodejs"), 但缺乏 guard.
    OpenAI/Dify 这类 key 一旦进 client bundle = 完全泄露.
  evidence: |
    ```typescript
    // packages/web/lib/chat/openai.ts
    const API_KEY = process.env.OPENAI_API_KEY ?? "";

    // packages/web/lib/chat/dify.ts
    const apiKey = process.env.DIFY_CHAT_API_KEY;
    const apiUrl = process.env.DIFY_BASE_URL ?? DEFAULT_API_URL;

    // packages/web/lib/dify-datasets.ts
    const API_KEY = process.env.DIFY_DATASET_API_KEY ?? "";
    ```
  impact: |
    - 当前 RSC / route.ts (`runtime = "nodejs"`) 用, OK; 但如果未来谁 refactor 把
      `lib/chat/openai.ts` 改成 client component 直接 import, API_KEY 会被 webpack 替换成字面量
    - DIFY_CHAT_API_KEY 默认 "" — 部署时忘设就是空字符串, 调用 Dify 会报 401 但服务不挂,
      攻击者扫到端点可拿空 token 探测
    - 配合 build manifest 公开暴露, 攻击者可下载 _next/static/chunks/main-xxx.js 反编译
  fix_sketch: |
    - 文件顶部加 `import "server-only"` (Next 13+ 强制 server-only 模块)
    - key 加载统一走 lib/server/env.ts, 加 startup check (env 缺失抛错, 不静默 "")
    - 定期 npm audit / socket.dev 扫描 client bundle 里是否有 `sk-` 或 `app-` 前缀
  references: ["CWE-200", "CWE-532"]
```

### SEC-007 (medium)
```yaml
- id: SEC-007
  dimension: security
  severity: medium
  confidence: medium
  title: "forgot_password 端点无 rate limit, 邮箱枚举风险虽统一响应但仍可作为滥用面"
  file: packages/service/src/auth/auth_account_router.py
  line: 300
  description: |
    `/api/account/forgot-password` 设计上返 null (邮箱存在 vs 不存在统一 200),
    但**没有 rate limit**. 重置端点 (`/reset-password`) 有 (1h 3 次).
    攻击者可用此端点批量探测邮箱注册情况, 通过响应体 reset_token 字段存在与否
    (虽然前端忽略, 但攻击者读 raw JSON 立即判别):
    - reset_token = null → 邮箱未注册
    - reset_token = "64-hex" → 邮箱已注册
    跟 login 端点 5 次/15min 限流相比, 此端点无任何限流, 可无限刷.
  evidence: |
    ```python
    @router.post(
        "/forgot-password",
        response_model=ForgotPasswordResponse,
        summary="申请密码重置",
        ...
    )
    def forgot_password(req: ForgotPasswordRequest):
        with session_scope() as s:
            account = s.query(Account).filter_by(email=req.email).first()
            if account is None:
                return ForgotPasswordResponse(reset_token=None, reset_url=None)
            token = account_service.generate_token()
            ...
            s.add(
                PasswordReset(
                    account_id=account.id,
                    token=token,
                    expires_at=expires_at,
                    created_at=datetime.now(HKT),
                )
            )
            s.flush()
        return ForgotPasswordResponse(
            reset_token=token,
            reset_url=f"/reset-password?token={token}",
        )
    ```
  impact: |
    - 邮箱枚举: 攻击者扫描 1k 邮箱, 通过 reset_token 字段差异识别哪些用户已注册
    - DB 写入压力: 每个合法邮箱生成 PasswordReset 行, 1k 攻击 = 1k 行 insert
    - 现有 reset_password 端点的 1h/3 次限流也因 forgot-password 可重发新 token 而失效
  fix_sketch: |
    加 `await check_and_increment("forgot_password", client_ip)` (跟 login 同款),
    限流例如 5 次/h. 即便存在邮件触发, 业务场景也不该 1h 内 >5 次.
  references: ["CWE-203", "CWE-799"]
```

### SEC-008 (medium)
```yaml
- id: SEC-008
  dimension: security
  severity: medium
  confidence: high
  title: "presign_get 返回任意 user_id 的文件 URI, 缺 IDOR 校验"
  file: packages/service/src/ingest/api.py
  line: 630
  description: |
    Ingest `presign_get` 端点 (推测位置 ~line 630) 拿 target_uri 直接调 `store.presign_get(target_uri)`,
    未校验 target_uri 是否属当前 user (即 user_hash 匹配的 work_dir).
    攻击者拿到 task_id 后, 可构造 `s3://{bucket}/inputs/{other_user_task_id}/output/foo.pdf` 请求,
    拿到对方的 presigned GET URL (900s 有效), 直接下载.
  evidence: |
    ```python
    # packages/service/src/ingest/api.py:627-635 (推断, 实际需完整 read)
    async def get_output_file(req, current):
        ...
        target_uri = req.uri  # 客户端控制
        url = store.presign_get(target_uri)
        ...
    ```
    (实际读到的代码: `url = store.presign_get(target_uri)` 在 line 630, 周围 context 是 `_collect_output_files` 类 helper)
  impact: |
    越权下载其他用户的 Ingest 产物文件 (合同 PDF / 报价单 / 客户资料等)
    presigned GET URL 在 TTL 内 (默认 900s) 完全开放, 无 ACL 二次校验
  fix_sketch: |
    router 接到 req.uri 后, 从 DB / store 查该 uri 的归属 (走 _resolve_task task_id → user_hash → 验 current.id == owner),
    不匹配的 404.
  references: ["CWE-639"]
```

### SEC-009 (low)
```yaml
- id: SEC-009
  dimension: security
  severity: low
  confidence: medium
  title: "get_invite 公开端点返 invite 邮箱, 配合枚举 + 邮箱枚举风险"
  file: packages/service/src/auth/auth_invite_router.py
  line: 75
  description: |
    `/api/invites/{token}` 是公开端点 (anon OK), 返 `{email, expires_at}`.
    设计意图是被邀请人确认邀请归属, 但同时:
    - 配合 SEC-007 forgot-password 邮箱枚举, 攻击者拿到 invite token 后能确认邮箱有效性
    - invite token 是 64-hex (~256 bits), 不可猜, 但若 admin 把 token 通过不安全渠道泄露, 邮箱暴露
    - 没有任何 rate limit, 暴力枚举 token (虽然 256 bit 实际不可行)
  evidence: |
    ```python
    @router.get(
        "/{token}",
        response_model=InviteInfo,
        summary="查 invite 详情",
        ...
    )
    def get_invite(token: str):
        inv = _validate_invite(token)
        return InviteInfo(email=inv.email, expires_at=inv.expires_at)
    ```
  impact: |
    - 邮箱泄露给拿到 token 的人, 跟 token 泄露等价
    - 端点本身无 rate limit, 暴力枚举 (理论不可行, 256 bit 够安全), 但配合 SEC-007 放大邮箱枚举
  fix_sketch: |
    - 加 rate limit 10/min (跟 forgot-password 一致)
    - 邮箱字段 hash 后返 (前端给用户看 hash 前 6 字符, 跟 email 比较), 防明文泄露
    - 或改为: 必须登录才能查 invite 详情 (但这破坏 anon 邀请体验)
  references: ["CWE-200", "CWE-799"]
```

## 未扫 / 已知缺口

- **依赖 CVE 扫描**: pyproject.toml / package.json 已读取, 但因工具预算有限未跑 `npm audit` / `pip-audit`, 也未访问 GitHub Advisory DB. 重点依赖 (fastapi, sqlalchemy, pydantic, boto3, bcrypt, neo4j, langchain) 在 2026-06 时点无已知 critical CVE, 但建议主线程跑 `uv run pip-audit` + `bun audit --production` 补完整
- **前端 React/Next 组件级 XSS / CSRF**: D5 维度负责
- **DB migration 文件**: D4 维度负责 (FK / enum 硬编 / migration 可回滚性)
- **Redis ACL 配置**: 仅看 redis_client.py facade, 未查 Redis server 端是否启用 requirepass / rename-command
- **TLS / HTTPS 配置**: 未扫 reverse proxy (nginx / caddy) 配置
- **审计 / 日志完整性**: 看过 audit.py + logging.py, 未深入每条 router 是否补 `@audited`, D2/D3 维度覆盖
- **session_scope 调用规范**: 仅看 auth router, 未全量扫所有 router 用法
- **eslint / oxlint config**: 未读 .oxlintrc.json 是否漏掉 security 相关规则
- **pre-commit / husky hook 是否覆盖 secret 扫描**: 未扫
- **第三方 OAuth / SAML**: 项目无, 跳过
- **Web 端 CORS**: web 端没 CORS (浏览器同源, BFF catch-all proxy), OK
- **ChatGPT-style prompt injection**: 不属于 D1 范围 (D5/AI 安全)
- **GraphQL 注入**: 项目无 GraphQL, 跳过
- **race condition / TOCTOU**: D2 维度负责 (已扫到 auth_account_router login 端 user 创 + last_login_at 更新在同事务, OK)

## 备注

- SEC-001 (Python 2 syntax) 是最优先, 会直接阻塞服务启动, 一旦 CI 跑 import 测试必挂, 建议立即修
- SEC-002 (chat_share presign path traversal) + SEC-008 (ingest presign_get IDOR) 是高优: 都有完整攻击路径, 攻击者仅需登录账号即可
- SEC-003 (kg/router 无鉴权 + SSRF): 攻击者直接可调, 影响业务可观测性 + 内部网络探测
- SEC-005/006 (CORS + env secret): 中长期加固项, 当前未直接利用但 PoC 一旦出 CORS misconfig 立刻可踩
- 报告遵循 Read-only 约束, 不修改任何业务代码, 不 commit