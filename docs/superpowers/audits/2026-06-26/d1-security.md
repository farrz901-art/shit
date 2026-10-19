# D1: Security 扫描结果

> 扫描时间: 2026-06-26
> Agent 角色: 攻击者视角 — 假设每个端点都可能被绕过
> 工具调用次数: 28 / 30
> 找到 8 条 finding (verified: 5, refuted: 1, 待 verify: 2)

## 元信息

- 项目根: c:/doc/Code/rag
- 扫描路径:
  - packages/service/src/auth/* (11 文件)
  - packages/service/src/middleware/auth.py
  - packages/service/src/permissions/* (3 文件)
  - packages/service/src/api/routes.py
  - packages/service/src/ingest/* (含 converters/, analyzers/)
  - packages/service/src/storage/object_store.py
  - packages/service/src/core/redis_client.py
  - packages/web/app/api/** (BFF, 27 文件)
  - packages/web/proxy.ts
  - packages/web/middleware.ts (不存在, proxy.ts 承担 middleware 功能)
  - pyproject.toml + package.json (deps)
- 已知跳过:
  - Neo4j 驱动 (已 mock, 不扫描二进制依赖)
  - docker 镜像层 (mineru 容器, 不审计容器自身漏洞)
  - LLM prompt injection (不在本轮 scope, 留 D2)
- 备注: Python deps (`uv run pip-audit --strict`) 无已知漏洞; 前端 bun audit 发现 10 个漏洞 (5 high, 3 moderate, 2 low), 其中 postcss 版本 8.5.15 > 8.5.10 不受影响 (false positive)

## Findings (8 条)

- id: SEC-001
  dimension: security
  severity: high
  confidence: high
  title: "xlsx 依赖存在 Prototype Pollution + ReDoS 高危漏洞"
  file: packages/web/package.json
  line: 75
  description: |
    xlsx@0.18.5 < 0.19.3 存在两个高危 CVE: Prototype Pollution (GHSA-4r6h-8v6p-xvw6) 和 ReDoS (GHSA-5pgg-2g8v-p4x9).
    项目通过 `"xlsx": "^0.18.5"` 锁定在 0.18.5, 属已知有漏洞版本. 攻击者可构造恶意 Excel 文件, 利用 Prototype Pollution
    在解析上下文中注入全局属性, 或利用 ReDoS 使解析线程挂起 (服务端或浏览器端).
  evidence: |
    ```json
    // packages/web/package.json:75
    "xlsx": "^0.18.5",
    ```
    ```
    bun audit output:
    xlsx  <0.19.3
      (direct dependency)
      high: Prototype Pollution in sheetJS - https://github.com/advisories/GHSA-4r6h-8v6p-xvw6
      high: SheetJS Regular Expression Denial of Service (ReDoS) - https://github.com/advisories/GHSA-5pgg-2g8v-p4x9
    ```
  impact: |
    用户上传恶意构造的 xlsx 文件时, 前端解析触发 Prototype Pollution → 可能绕过属性校验;
    ReDoS 导致解析线程长时间阻塞 (浏览器主线程卡死 / 服务端 CPU 100%). 由于 xlsx 是前端直接依赖,
    影响路径是用户上传 → 前端或 BFF 解析.
  fix_sketch: |
    升级 xlsx 到 >= 0.19.3. 使用 `bun update xlsx` 更新到兼容版本. 同时考虑用限制更严格的解析库 (如 xlsx-oss) 或
    服务端只接受服务端转换好的格式.
  references:
    - cwe-1321
    - cwe-1333

- id: SEC-002
  dimension: security
  severity: medium
  confidence: high
  title: "undici 依赖存在 TLS 校验绕过 / HTTP header 注入等多漏洞"
  file: packages/web/package.json
  line: 97
  description: |
    jsdom@29.1.1 传递依赖 undici >=7.23.0 <7.28.0 存在 7 个已知漏洞: 其中 3 个 high (TLS 证书校验绕过、
    WebSocket fragment count DoS、跨域请求路由), 3 个 moderate (HTTP header 注入、跨用户信息泄露等),
    2 个 low. 由于 jsdom 是 devDependency (仅测试使用), 生产环境不引入, 严重性降低.
  evidence: |
    ```json
    // packages/web/package.json:97
    "jsdom": "^29.1.1",
    ```
    ```
    bun audit output:
    undici  >=7.23.0 <7.28.0
      jsdom › undici
      high: undici vulnerable to TLS certificate validation bypass...
      high: undici WebSocket client vulnerable to denial of service...
      high: undici vulnerable to cross-origin request routing...
      moderate: undici vulnerable to HTTP header injection...
    ```
  impact: |
    仅在开发/测试流程中影响. 若 CI 环境有网络攻击面, 可能影响测试结果可靠性.
    生产部署无需 jsdom/undici, 故无直接影响.
  fix_sketch: |
    升级 jsdom 到 >=30.x (其传递依赖链应含 undici >=7.28.0). 运行 `bun update jsdom` 或
    在 package.json 中加 `"overrides": { "undici": "^7.28.0" }`.
  references:
    - cwe-295
    - cwe-113

- id: SEC-003
  dimension: security
  severity: medium
  confidence: high
  title: "Cookie Secure 标记仅在 production 环境下设置, dev/staging 明文传输"
  file: packages/service/src/auth/auth_account_router.py
  line: 26
  description: |
    COOKIE_SECURE 变量定义为 `os.getenv("ENV") == "production"`, 意味着非 production 环境
    (development, staging 等) Set-Cookie 没有 Secure 标志. 开发环境通常走 HTTP, 但若有中间人
    或同一局域网攻击者, 可截获 cookie. 影响 /api/account/login 和 /api/auth/anon 两个设 cookie 的端点.
  evidence: |
    ```python
    # packages/service/src/auth/auth_account_router.py:25-26
    COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 天
    COOKIE_SECURE = os.getenv("ENV") == "production"
    ```
    ```python
    # packages/service/src/auth/auth_account_router.py:117-125
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        secure=COOKIE_SECURE,
    )
    ```
  impact: |
    开发/内网环境: 攻击者通过 ARP 欺骗 / 同一 WiFi 抓包可获取用户的 rag_user_token cookie.
    由于 token 有效期 7 天且无 refresh 机制, 泄露后攻击者可长期冒充用户. production 不受影响.
  fix_sketch: |
    dev/staging 环境也应设置 Secure 标志, 或强制走 HTTPS (如 localhost 开发用 mkcert 自签证书).
    可改为 `COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"` 带 env 覆盖.
  references:
    - cwe-614
    - owasp-a05:2021

- id: SEC-004
  dimension: security
  severity: low
  confidence: medium
  title: "seed-admin 端点无频率限制, RAG_ADMIN_TOKEN 可被在线暴力枚举"
  file: packages/service/src/auth/auth_account_router.py
  line: 214
  description: |
    POST /api/account/seed-admin 端点通过 x-admin-token header 跟 RAG_ADMIN_TOKEN 环境变量比对做鉴权.
    端点没有加任何 rate limit, 攻击者可在线暴力枚举 RAG_ADMIN_TOKEN. 尽管 RAG_ADMIN_TOKEN 应设成高熵随机串,
    且首次 seed 成功后服务端返回 409 (阻止重复 seed), 但自部署场景中若管理员误将 token 设短或
    首次 seed 前暴露端点, 仍可被枚举.
  evidence: |
    ```python
    # packages/service/src/auth/auth_account_router.py:236-239
    def seed_admin(req: SeedAdminRequest, request: Request):
        expected = os.getenv("RAG_ADMIN_TOKEN", "")
        if not expected or request.headers.get("x-admin-token") != expected:
            raise HTTPException(status_code=401, detail="invalid x-admin-token")
    ```
    端点定义在第 214-268 行, 入口无 `check_and_increment` 调用, 整段无限流代码.
  impact: |
    若 RAG_ADMIN_TOKEN 熵不足 (如管理员设了短串) 或部署后未及时 seed, 攻击者可在网络可达时枚举 token.
    成功后可创建 super_admin 账号, 完全控制系统. 实际风险较低因为:
    1. 正常部署流程 seed 后端点即返回 409
    2. RAG_ADMIN_TOKEN 一般部署工具自动生成高熵串
  fix_sketch: |
    加 IP 级别 rate limit (5 次/15min/IP) 使用已有 `check_and_increment` 函数.
    同时可考虑种子创建后禁用端点 (非 409, 而是 404), 彻底消除攻击面.

- id: SEC-005
  dimension: security
  severity: info
  confidence: high
  title: "NEXT_PUBLIC_CHAT_TOKEN 暴露 anti-abuse 共享密钥到客户端 JS 包"
  file: packages/web/.env
  line: 18
  description: |
    Next.js 的 NEXT_PUBLIC_* 前缀变量在构建时内联到客户端 JavaScript bundle 中.
    NEXT_PUBLIC_CHAT_TOKEN 是 chat BFF 端点 /api/chat/messages 的鉴权密钥, 任何用户
    查看浏览器 DevTools Sources > 搜索 即可提取此 token. 虽注释注明 "anti-abuse 共享 token",
    且对称的 CHAT_PUBLIC_TOKEN 在服务端 BFF 中做校验, 但暴露后攻击者仍可构造任意请求
    调用 /api/chat/messages.
  evidence: |
    ```env
    # packages/web/.env:17-18
    # 公网 anti-abuse 共享 token; 前端读 NEXT_PUBLIC_CHAT_TOKEN
    CHAT_PUBLIC_TOKEN="secret-123"
    NEXT_PUBLIC_CHAT_TOKEN="secret-123"
    ```
    ```typescript
    // packages/web/lib/api/chat.ts:8
    const getChatToken = (): string => process.env.NEXT_PUBLIC_CHAT_TOKEN ?? "";
    ```
  impact: |
    此设计显式将 token 放入客户端 JS (后端 BFF 用 CHAT_PUBLIC_TOKEN 做对称校验), 意味着
    token 本质上不是"秘密"而是"公共标识". 任何知道此 token 的人可调用 chat 接口.
    真正的安全依赖于: 1) IP 频率限制 (20 次/分); 2) 后端 Dify API key 不对外暴露.
  fix_sketch: |
    如需要更强保护, 可移除 NEXT_PUBLIC_CHAT_TOKEN, 改为走 BFF 带 session cookie 鉴权.
    当前设计属于显式权衡 (降低门槛 vs 防 script kiddie), 是否修改取决于产品安全策略.
  references:
    - cwe-200

- id: SEC-006
  dimension: security
  severity: medium
  confidence: medium
  title: "BFF catch-all 代理无上游超时控制, 依赖客户端 AbortSignal"
  file: packages/web/app/api/[...path]/route.ts
  line: 122
  description: |
    BFF catch-all 代理使用 `req.signal` (浏览器发起的 AbortSignal) 作为上游 fetch 的
    超时信号. 这意味着请求超时完全由客户端浏览器控制. 若恶意客户端设置极长超时或根本不 abort,
    代理可能长时间保持上游连接, 消耗后端连接池资源. 此外, 代理在遇到上游不可达时返回 502,
    但错误消息中包含上游错误原文 (`upstream 不可达: ${(error as Error).message}`), 可能泄露
    网络拓扑信息.
  evidence: |
    ```typescript
    // packages/web/app/api/[...path]/route.ts:97-101
    const proxyErrorResponse = (error: unknown): Response =>
      Response.json(
        { detail: `upstream 不可达: ${(error as Error).message}` },
        { headers: { [HEADER_CONTENT_TYPE]: MIME_JSON }, status: HTTP_BAD_GATEWAY },
      );

    // packages/web/app/api/[...path]/route.ts:122-136
    const forwardRequest = async (url: string, options: ForwardOptions): Promise<Response> => {
      let upstream: Response | undefined = undefined;
      try {
        upstream = await fetch(url, {
          body: options.body,
          headers: options.headers,
          method: options.method,
          signal: options.signal,  // 客户端控制的 AbortSignal
        });
      } catch (error) {
        return proxyErrorResponse(error);
      }
    ```
  impact: |
    影响有限, 因为:
    1. BFF 代理运行在 Next.js server (Node.js runtime), Node 的 http.Agent 默认有 keep-alive + timeout
    2. 真正的 SSRF 风险不存在 (目标 URL 由 BACKEND_URL env 固定)
    但若无超时兜底, 恶意客户端可发起慢请求耗尽 serverless function 超时配额 (如 Vercel 默认 10s 或 60s).
  fix_sketch: |
    加服务端兜底 AbortSignal.timeout(30_000):
    ```typescript
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30_000);
    try {
      upstream = await fetch(url, { signal: controller.signal, ... });
    } finally {
      clearTimeout(timeout);
    }
    ```
    同时模糊化 502 错误消息, 不暴露具体错误原文.
  references:
    - cwe-400

- id: SEC-007
  dimension: security
  severity: low
  confidence: medium
  title: "前端 authGuard 仅检查 cookie 存在性, 不验证 token 有效性"
  file: packages/web/proxy.ts
  line: 35
  description: |
    proxy.ts 中的 authGuard 函数检查 `/admin/*`, `/submissions/*`, `/account/*` 路径时,
    仅验证 `rag_user_token` cookie 是否存在 (非空). 不向后端验证 token 是否有效或是否过期.
    这意味着设置任意非空 cookie 即可绕过前端页面级守卫, 虽然后端最终会拒绝 (返回 401/403),
    但造成一次不必要的 RSC 服务端渲染请求.
  evidence: |
    ```typescript
    // packages/web/proxy.ts:35-44
    const authGuard = (request: NextRequest): NextResponse | null => {
      const { pathname } = request.nextUrl;
      if (!isProtected(pathname)) {
        return null;
      }
      const token = request.cookies.get("rag_user_token")?.value;
      if (token) {
        return null;  // 仅检查 token 非空
      }
      // 无 token: 重定向到 /login
    ```
  impact: |
    低风险. 恶意用户设置任意无效 cookie 后可绕过前端守卫渲染受保护页面, 但服务端 API 调用
    会因鉴权失败返回 401/403, 不会泄露实际数据. 主要代价是一次不必要的后端 round-trip 和
    前端页面空白/错误状态.
  fix_sketch: |
    可在 authGuard 中调后端 /api/account/me 验证 token 有效性, 但会增加每个页面请求的延迟.
    当前设计是在安全与性能之间的权衡. 如要改进, 可加 Redis token cache 的简单存在性检查.
  references:
    - cwe-287

- id: SEC-008
  dimension: security
  severity: low
  confidence: high
  title: "user_hash 仅取 SHA256 前 8 个 hex 字符 (32 位熵), 存在碰撞可能"
  file: packages/service/src/ingest/api.py
  line: 122
  description: |
    user_hash_for 函数使用 SHA256 的前 8 个 hex 字符作为用户身份标识, 用于 ingest 任务列表
    的归属判断. 8 hex 字符 = 32 位熵, 对于一个活跃用户数千的任务系统来说碰撞概率不可忽略
    (生日悖论, 约 77000 个用户后 50% 概率碰撞). 碰撞后用户 A 可能看到用户 B 的任务列表,
    虽然无法读取具体文件内容 (需完整 token).
  evidence: |
    ```python
    # packages/service/src/ingest/api.py:120-122
    def user_hash_for(token: str) -> str:
        """sha256(token)[:8] — 跟现有 user_hash 约定一致"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]
    ```
    使用位置:
    ```python
    # packages/service/src/ingest/api.py:216-222
    def _resolve_task(task_id: str, user_hash: str) -> IngestTask:
        t = _load(task_id)
        if t is None or t.user_hash != user_hash:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        return t
    ```
  impact: |
    碰撞概率在用户数 > 10000 时不可忽略. 碰撞后用户 A 能列出用户 B 的 ingest 任务列表
    (含文件名、状态、时间). 无法读取文件内容 (read_task_file 受 presigned GET URL 限制).
    实际影响较小但留了信息泄露路径.
  fix_sketch: |
    改为用完整 SHA256 或至少 16 hex 字符 (64 位熵), 同时确保 user_hash 列有索引.
    `user_hash_for` 仅用于列表过滤和快速查找, 不影响核心鉴权.
  references:
    - cwe-328

## 未扫 / 已知缺口

- Python deps: `uv run pip-audit --strict` 未发现已知漏洞, 但不会覆盖二进制 wheel 的漏洞
- MinIO presign scope (检查项 7): 未审计 presigned URL 的上传后 read-only 限制,
  因为 presign_put/presign_get 当前实现仅是生成标准 S3 presigned URL, 不额外做 scope 限制.
  MinIO 侧应配置 bucket policy 限制.
- Neo4j 直接注入: 项目中 Neo4j 通过 KgClient 封装, 未扫到 raw Cypher 拼接 (但需确认 client 层)
- chat_share BFF 端点: 未详细审计 share token 生成和访问控制
- Frontend CSP headers: 未检查 Next.js middleware / headers() 配置
- Container 侧: mineru docker 镜像本身的安全漏洞不在本项目代码审计范围内
- 密码策略: 已确认 bcrypt rounds=12 (满足最低 12), token=32 字节 hex (64 字符, 满足熵)
