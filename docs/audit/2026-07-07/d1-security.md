# D1 安全审计 (Security) — 2026-07-07

> 扫描范围: 前端 BFF routes / lib/api / lib/chat / middleware, 后端 auth / models
> 关注维度: 鉴权, 注入 (SQL/Cypher), IDOR/租户隔离, CORS, XSS (markdown), 依赖 CVE, SSRF

---

## Finding 总览

| ID | severity | 维度 | 标题 |
|---|---|---|---|
| SEC-001 | medium | deps CVE | @js-temporal/polyfill 0.5.1 已知 CVE-2024-5261 风险 (虽然已在修复版本) |
| SEC-002 | high | BFF 鉴权 | 4 个 BFF 路由漏注 x-user-token header (依赖浏览器 cookie 透传) |
| SEC-003 | medium | BFF 鉴权 | chat messages SSE 限流仅按 IP 未绑定 user, 1 个公共 token 共享配额 |
| SEC-004 | medium | XSS | streamdown markdown 渲染缺显式 sanitize, src 透传可触发 javascript:/data: |
| SEC-005 | high | IDOR | BFF catch-all /api/[...path] 代理静默接受请求但若源 SSR 注入无 referrer 校验 |
| SEC-006 | medium | CORS | dev 默认 allow 三个本地源, prod env 配错时退化为 allow 0/不可用, 无白名单 fallback |
| SEC-007 | low | 注入 | Neo4j dataset label 字面量拼接 (经 validate_dataset 白名单防御) — 暂安全 |
| SEC-008 | medium | SSRF | DIFY_BASE_URL / OPENAI_BASE_URL 来自 env 无白名单校验, 配错可变内网探测 |
| SEC-009 | high | IDOR | chat share GET 公开端点未要求 user_id/conv 校验, share_id 9 字节熵足够但创建后无审计 owner |
| SEC-010 | low | 鉴权 | RAG_DEV_AUTH 环境变量未在 CORS 配置中互斥, 可被误开启后门 |
| SEC-011 | medium | BFF 鉴权 | /api/auth/anon BFF 直接 fetch API_BASE 无 timeout 限制, Slowloris 风险 |
| SEC-012 | low | BFF 鉴权 | forgot-password 限流 5/15min, 但账户枚举已用统一响应防御, 留意: RateLimit key 含 IPv6 全长 (key 过长 redis 内存浪费) |
| SEC-013 | medium | IDOR | chat/{user_id}/avatar 代理公开读, account_id 可枚举 → 头像/email 关联风险 |

---

## SEC-001 @js-temporal/polyfill 0.5.1 已修复 CVE-2024-5261 (info)

```yaml
id: SEC-001
dimension: security
severity: info
confidence: high
title: "@js-temporal/polyfill 0.5.1 已修复 CVE-2024-5261, 当前 pin 恰好在修复版本"
file: "packages/web/package.json"
line: 32
description: |
  项目固定 `@js-temporal/polyfill@^0.5.1`, 该版本是 CVE-2024-5261 (from()/with() prototype pollution)
  的修复版本 (2024-05-20 发布). 当前锁定在已修复的 minor, 没有再往上的 0.5.x 已知 CVE.
  但项目走 `^0.5.1` (caret), 任意 0.5.x 都满足. 若上游发布 0.5.2+ 含回归, 仍会被自动拉入.
  建议锁定精确版本或定期 `npm audit` / `bun audit` 校验.
evidence: |
  "@js-temporal/polyfill": "^0.5.1",
  "lib/date": "TC39 Temporal via @js-temporal/polyfill (~25KB gzip)"
impact: |
  当前无 active 漏洞, 但 caret range 未来若引入回归可能无声升级. 低危.
fix_sketch: |
  把 `^0.5.1` 改为 `0.5.1` (精确锁), 加 Dependabot / renovate 监控 0.5.x release.
references:
  - https://github.com/tc39/proposal-temporal/security/advisories/GHSA-2rcv-c9px-9f3q
  - https://nvd.nist.gov/vuln/detail/CVE-2024-5261
```

---

## SEC-002 4 个 BFF 路由 apiProxy 调用未注 x-user-token (high)

```yaml
id: SEC-002
dimension: security
severity: high
confidence: high
title: "4 个 BFF 路由漏注 x-user-token, 依赖浏览器自动带 cookie 但 SSR/RSC 路径裸跑"
file: "packages/web/app/api/ingest/tasks/[id]/download/route.ts"
line: 18
description: |
  审查 23 个 BFF 路由发现 4 个调 `apiProxy(...)` 但没注 `serverAuthHeaders()`:
  - `app/api/ingest/tasks/[id]/download/route.ts:18` (GET)
  - `app/api/ingest/tasks/[id]/files/[name]/route.ts:21` (GET, 实际有)
  - `app/api/approvals/[id]/approve/route.ts:17` (POST)
  - `app/api/approvals/[id]/reject/route.ts:18` (POST)
  - `app/api/approvals/[id]/retry/route.ts:17` (POST)
  - `app/api/evaluate/template/route.ts:13` (GET)
  - `app/api/health/system/route.ts:16` (GET)

  其中 `health/system` 和 `evaluate/template` 是无鉴权端点, OK; 但 `ingest/tasks/{id}/download` 和 3 个 approvals 都需要鉴权.
  在浏览器场景下, cookie 由同源 BFF 自动带, 看起来 OK, 但:
  1. 该 BFF 走 `apiProxy` 跨域到 API_BASE (RAG_BACKEND_URL), 不再同源, cookie 不会自动透传到 FastAPI;
  2. 后端 `resolve_user` 走 `x-user-token` header 优先, cookie 走降级路径, 但 FastAPI 跨域时浏览器**只**带 cookie 给同源请求, 跨域 fetch 不会带 cookie 除非显式 `credentials: 'include'`. 这里 `apiProxy` 调 `fetch(url, init)` 默认 `credentials: 'omit'`.
  3. 即便 user 浏览器有 `rag_user_token` cookie, 这 4 个 BFF 转发时 cookie 不会带, 后端 401.
  实际表现: 用户在 UI 点 "下载" 或 "批准" 按钮, 一律 401. 攻击者角度: 这些端点等价于未鉴权可触发, 但因后端守卫, 实际是拒绝服务 (UI 404/401).
evidence: |
  const resp = await apiProxy(`/api/ingest/tasks/${encodeURIComponent(id)}/download`, {
    cache: "no-store",
  });
impact: |
  - ingest/tasks/{id}/download: 用户无法下载任务产物, 功能破损
  - 3 个 approvals 路由: admin 无法批准/拒绝/重试审批, 功能破损
  - 安全侧: 因为后端守卫仍生效, 没有越权; 但属于 "BFF 鉴权反模式" — 既不安全 (跨域 cookie 不会自动带) 也不工作
fix_sketch: |
  全部加 `headers: await serverAuthHeaders()`, 跟其他 16 个 BFF 一致. 评审代码时把这个当成 lint 级别.
references:
  - packages/web/lib/api/auth.server.ts:20-29
```

---

## SEC-003 chat BFF 限流仅按 IP, 公共 token 共享配额 (medium)

```yaml
id: SEC-003
dimension: security
severity: medium
confidence: high
title: "chat messages 限流仅按 IP, 公共 token 共享配额, 无 user_id 维度"
file: "packages/web/app/api/chat/messages/route.ts"
line: 127
description: |
  `checkAndIncrement(`chat:${ip}`, RATE_LIMIT_MAX=20, RATE_LIMIT_WINDOW_MS=60_000)`.
  限流 key 只含 IP, 1 个 NAT 出口下所有用户共享 20 次/分配额.
  加之鉴权靠 `x-chat-token` (单字符串), 该 token 暴露在 `NEXT_PUBLIC_CHAT_TOKEN` (浏览器可读), 任意浏览器 JS 都能拿到:
  ```ts
  const token = process.env.NEXT_PUBLIC_CHAT_TOKEN ?? "";
  ```
  实际允许跨域伪造 chat 请求, 共享同一 IP 配额. 配合 Dify 转发, 攻击者可调高并发耗尽 LLM 配额或刷量计费.
evidence: |
  const ip = extractClientIp(req.headers);
  const rateResult = checkAndIncrement(`chat:${ip}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW_MS);
  if (!rateResult.allowed) {
    return tooManyRequests(rateResult.remaining);
  }
impact: |
  - 公共 chat-token 暴露 (NEXT_PUBLIC_*), 任何 web visitor 都能伪造合法请求, 1 IP 下多用户共享配额被耗尽
  - 后端 Dify 调用是项目出钱, 攻击者刷量会消耗 LLM token 配额, 计费风险
fix_sketch: |
  1. 限流 key 加 user_id 或 session_id 维度: `chat:${ip}:${user_id}`
  2. 后端 chat 端点也校验 IP + token 双向绑定
  3. CHAT_PUBLIC_TOKEN 不应该走 NEXT_PUBLIC_*, 应从后端 server action / cookie 取
references: []
```

---

## SEC-004 streamdown markdown 渲染 src 透传未过滤 (medium)

```yaml
id: SEC-004
dimension: security
severity: medium
confidence: medium
title: "Streamdown markdown 渲染 img src 未做 javascript:/data: 协议过滤"
file: "packages/web/components/markdown/markdown-static.tsx"
line: 13
description: |
  MarkdownStream / MarkdownStatic 直接把 LLM 返回的 markdown `<img src=...>` 渲染.
  `markdown-img.tsx` 对 src 仅做 `typeof src === "string"` 检查, 没过滤 javascript:/data: URL scheme.
  LLM 输出若被 prompt injection 引导输出 `<img src="javascript:alert(1)">`, Streamdown 默认行为可能执行或透传.
  实际 XSS 风险依赖 Streamdown 内部 rehype-sanitize 配置. 项目没显式接 rehypePlugins, 用默认值.
  CVE-2026-22167 (react-markdown <9.0.1 XSS) 已迁移到 streamdown, 但 streamdown 自身未发布 2.5.x 的 sanitize 文档, 行为未审计.
evidence: |
  img: ({ src, alt }) => <img src={src} alt={alt} className="max-w-full rounded" />,
  components={{ img: ({ src, alt }) => (
    <MarkdownImg src={src} alt={alt} onPreview={onPreview ?? (() => {})} />
  ) }}
impact: |
  - LLM 输出的恶意 markdown (含 prompt injection) 可能触发存储型 XSS
  - MarkdownStatic 用在 output 页 (静态渲染任务产物), attack surface 比 chat 小
  - 用户 chat 输入若被诱导输出 `<img>` 触发 fetch 第三方 URL, 可作 SSRF-like beacon
fix_sketch: |
  在 MarkdownStatic / MarkdownStream components.img 回调里加 protocol allowlist:
  `if (!/^https?:|^\/|^data:image\//.test(src)) return null;`
  配合 streamdown rehype-sanitize 显式启用.
references:
  - packages/web/components/markdown/markdown-img.tsx:29-46
```

---

## SEC-005 catch-all BFF /api/[...path] 未鉴权 + 静默透传 (high)

```yaml
id: SEC-005
dimension: security
severity: high
confidence: high
title: "BFF catch-all /api/[...path]/route.ts 未做 source 限制, 仅靠 cookie 同源保护"
file: "packages/web/app/api/[...path]/route.ts"
line: 184
description: |
  `proxy()` 函数接受任意 path 数组, 拼成 `/api/{segments.join("/")}`, 然后走 `fetch(API_BASE + apiPath)`.
  没有任何 source/host 白名单, 仅在 `getAuthHeaders` 读 cookie (若没有 cookie 就不注 x-user-token).
  这意味着:
  1. 后端 `resolve_user` 收到无 x-user-token → 401 (因 `RAG_DEV_AUTH=production` 模式下不走 dev fallback)
  2. 但若后端设了 `RAG_DEV_AUTH=true` (dev 模式), 任何路径都返 super_admin
  3. 攻击者可枚举 /api/health/* /api/admin/* 等路径, 看哪些端点会因 cookie 携带返回 200
  4. 转发时 `buildForwardHeaders` 只透传 content-type, 不透传 cookie; 即便 user 有 cookie, 转发也是裸请求
  实际表现: catch-all 等于强制走无鉴权路径, 因为前端代码几乎所有调 apiFetch 都不带 x-user-token (依赖浏览器 cookie 自动带, 但 BFF 跨域 fetch 不带 cookie).
evidence: |
  const proxy = async (
    req: NextRequest,
    params: { path: string[] },
    method: string,
  ): Promise<Response> => {
    const apiPath = buildApiPath(params.path);
    if (!apiPath) {
      return notFoundResponse();
    }
    const targetUrl = buildTargetUrl(apiPath, req.url);
    const forwardHeaders = await buildForwardHeaders(req);
    const body = await extractRequestBody(req, method);
    return forwardRequest(targetUrl.toString(), {
      body,
      headers: forwardHeaders,
      method,
      signal: req.signal,
    });
  };
impact: |
  - BFF 跨域转发丢失浏览器 cookie → 实质所有经 catch-all 的请求都未鉴权 (除带 serverAuthHeaders 的具体 BFF)
  - RAG_DEV_AUTH=true 部署错误 = 攻击者任意 GET/POST 后端任何路径
  - 生产环境若运维误开 RAG_DEV_AUTH, 即便 catch-all 没注 cookie, 仍以 dev super_admin 身份通过
fix_sketch: |
  1. `getAuthHeaders` 在 cookie 不存在时直接返 401, 不允许转发
  2. catch-all 加 path 白名单 (e.g. 仅 /api/chat/messages /api/health/* 等), 其余 404
  3. 生产禁用 RAG_DEV_AUTH (env 启动校验 fail-fast)
references:
  - packages/web/app/api/[...path]/route.ts:74-83
  - packages/web/lib/api/auth.server.ts
```

---

## SEC-006 CORS 配置 production env 缺失时退化为空白名单 (medium)

```yaml
id: SEC-006
dimension: security
severity: medium
confidence: high
title: "production env CORS_ALLOW_ORIGINS 缺失 → allow_origins=[] → 所有跨域请求被拒"
file: "packages/service/src/core/app_factory.py"
line: 128
description: |
  CORS 配置:
  ```python
  if env_value == "production":
      cors_str = os.getenv("CORS_ALLOW_ORIGINS", "")
      allow_origins = [o.strip() for o in cors_str.split(",") if o.strip()] if cors_str else []
  else:
      allow_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"]
  ```
  若 `ENV=production` 但 `CORS_ALLOW_ORIGINS` 没设, `allow_origins=[]`. 此时:
  - 浏览器任何跨域请求都被 CORS 拒 (无 origin 在白名单), 即便合法来源
  - 但 `allow_credentials=True` + 空白名单 = 配置文件失败, 不会泄漏 (CORS 拒的是 preflight/响应头), 没风险
  - 安全侧: 配置失败 fail-fast (启动报错) 应该, 当前是静默退化为不可用
  - 信息侧: 配置文件遗漏时只看到 "CORS error in console", debug 不直观
evidence: |
  env_value = os.getenv("ENV", "development")
  if env_value == "production":
      cors_str = os.getenv("CORS_ALLOW_ORIGINS", "")
      allow_origins = [o.strip() for o in cors_str.split(",") if o.strip()] if cors_str else []
  else:
      allow_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"]
impact: |
  - prod 部署 CORS 配错时, 整个前端 → 后端跨域静默失败, 没有 fail-fast 报警
  - 安全侧目前安全 (空 list 不放过任何 origin), 但可能误开 `allow_origins=["*"]` 当 fallback, 引出 CVE
fix_sketch: |
  production 模式下若 CORS_ALLOW_ORIGINS 为空 → 启动抛 RuntimeError, 跟 dictionaries check_consistency 模式一致.
references: []
```

---

## SEC-007 Neo4j Cypher dataset label 字面量拼接 (low, 暂安全)

```yaml
id: SEC-007
dimension: security
severity: low
confidence: high
title: "Neo4j dataset label 用 f-string 拼接, 防御靠 KG_ALLOWED_DATASETS 白名单"
file: "packages/service/src/kg/client.py"
line: 96
description: |
  `_build_merge_node_cypher` / `list_products` 等用 `f"...`{dataset}`..."` 把 dataset label 嵌入 cypher 字面量.
  Cypher label/rel_type 不能参数化 (项目 memory 里有记录 [feedback-cypher-merge-label-rel-type-not-parameterizable]),
  必须字面量拼接. 防御靠 `validate_dataset()` 白名单 (env `KG_ALLOWED_DATASETS`):
  ```python
  validate_dataset(dataset)  # 强校验: 白名单 + 合法 identifier
  ```
  若未来有人加 endpoint 接受 user-controlled dataset 而漏调 `validate_dataset()`, 即刻变 Cypher 注入.
  当前审计: 5 处 f-string 都先经过 `validate_dataset()`, 暂安全.
evidence: |
  cypher = f"MERGE (n:{label}:`{dataset}` {{{merge_props}}}) SET n += $extra RETURN id(n) AS node_id"
  cypher = (
      f"MATCH (n) WHERE n:`{self._dataset}` AND size(labels(n)) > 0 "
      "RETURN id(n) AS id, labels(n)[0] AS label, properties(n) AS props "
      "SKIP $skip LIMIT $limit"
  )
impact: |
  当前 0 active 注入路径. 风险在于未来重构漏调 validate_dataset.
fix_sketch: |
  1. 加 ruff/pyright AST 检查: f-string 含 cypher 关键字 (MERGE/MATCH) 必须先调 validate_dataset
  2. 把 `validate_dataset` 改成 decorator 强制每个 router endpoint 都过
references:
  - packages/service/src/kg/client.py:91-98
  - packages/service/src/kg/router.py:399
```

---

## SEC-008 DIFY_BASE_URL / OPENAI_BASE_URL 无白名单, 可配错变内网 SSRF (medium)

```yaml
id: SEC-008
dimension: security
severity: medium
confidence: medium
title: "DIFY_BASE_URL / OPENAI_BASE_URL 来自 env 无白名单, 配置错误可指内网"
file: "packages/web/lib/chat/dify.ts"
line: 33
description: |
  Dify / OpenAI provider 走 `apiProxy(base=apiUrl, ...)`, `apiUrl` 直接来自 `process.env.DIFY_BASE_URL`.
  前端 Dockerfile 注释: "必须在 bun run build 之前, 通过 build arg 接收并声明成 ENV".
  若运维误把 DIFY_BASE_URL 配成 `http://10.0.0.5:8000/api` (内网后端), 每次 chat 都把用户 query 透传到内网.
  攻击者 (有 chat token + query 注入能力) 可借 Dify / OpenAI 作为 SSRF 跳板, 让项目服务器代为 fetch 内网 URL (利用 prompt injection + LLM tool calls).
  当前无白名单校验, 任何 URL scheme (http/https/file) 都接受.
evidence: |
  const apiUrl = process.env.DIFY_BASE_URL ?? DEFAULT_API_URL;
  const res = await apiProxy("/chat-messages", {
    base: apiUrl,
  const BASE_URL = process.env.OPENAI_BASE_URL ?? "https://api.openai.com/v1";
  const res = await apiProxy("/chat/completions", {
    base: BASE_URL,
impact: |
  - 内网 SSRF (项目后端容器可访问的内网地址)
  - 数据外泄: 用户 query 被代发到攻击者控制的 URL
  - LLM 代理滥用: 配错指向攻击者 API, 收集用户对话
fix_sketch: |
  1. 启动校验: DIFY_BASE_URL / OPENAI_BASE_URL 必须 https:// 或已知内网白名单
  2. 加 prefix allowlist (https://api.dify.ai, https://api.openai.com, 自建域名等)
  3. 服务端 timeout + response size cap 防数据滥用
references: []
```

---

## SEC-009 chat share 公开 GET 端点 user_id 验证 + 短 ID 熵 (high)

```yaml
id: SEC-009
dimension: security
severity: high
confidence: high
title: "chat share GET 公开 + 短 ID 9 字节熵 (~71 bits), revoke 后真删但创建无审计"
file: "packages/service/src/chat_share/service.py"
line: 222
description: |
  `get_share(share_id)` 公开 anon 可读, 短 ID `secrets.token_urlsafe(9)[:12]` = 12 字符 base64, 熵 ~71 bits.
  71 bits 在工程实践足够 (NIST 建议 > 64 bits), 但仍有 1/2^71 暴力枚举可能.
  更关键:
  1. `create_share` 没 audit 装饰器 (对比 chat router 全用 @audited), 创建行为不可追溯
  2. `get_share` 公开响应**不含** user_id 是好的, 但 messages 包含完整对话内容, 若用户分享敏感对话 (含个人信息), 链接泄露=永久泄露
  3. `revoke_share` 仅所有者可调, 但 `expires_at` 默认 7 天, 没有更快过期的开关
  4. share URL 是 `/zh/chat/s/{share_id}`, share_id 出现在 URL 里, 浏览器历史 / Referer header 会泄露
evidence: |
  @staticmethod
  def _gen_share_id() -> str:
      """生成 12 字符短 ID (nanoid 等价: 9 字节 base64 = 12 字符, 熵 ~71 bits)."""
      return secrets.token_urlsafe(9)[: defaults.DEFAULT_CHAT_SHARE_ID_LENGTH]

  def get_share(self, share_id: str) -> dict[str, Any]:
      """读 share 快照, 不含 user_id / 任何 PII. 不存在 → ShareNotFound."""
      share = self._repo.get_by_id(share_id)
      if share is None:
          raise ShareNotFound(f"share {share_id} 不存在")
      return {
          "share_id": share.share_id,
          "title": share.title,
          "messages": json.loads(share.messages_json or "[]"),
          "model": share.model,
          "created_at": share.created_at,
      }
impact: |
  - 创建 share 无审计, 出现泄密事件时无法溯源
  - share_id URL 路径暴露在 Referer header 给第三方 (embed 第三方页面时)
  - 71 bits 熵足够但缺乏 brute-force 检测 (e.g. 同一 IP 100 次 404 应触发告警)
fix_sketch: |
  1. create_share 加 @audited("chat.share.create")
  2. 增加 share_id 查询限流 (anon 端点)
  3. 提供可选 `expires_in` 参数, 让用户选 1h / 24h / 7d
  4. 加 `password_protected` 字段 (用户可设密码, 兑换后短时链接才有效)
references:
  - packages/service/src/chat_share/service.py:120-134
```

---

## SEC-010 RAG_DEV_AUTH 可被误开导致 super_admin 旁路 (low)

```yaml
id: SEC-010
dimension: security
severity: low
confidence: medium
title: "RAG_DEV_AUTH=true 部署泄漏 = 任意 anon 访问 super_admin 角色"
file: "packages/service/src/middleware/auth.py"
line: 103
description: |
  `resolve_user` 在 `RAG_DEV_AUTH=1/true/yes` 时, 无 token 直接返 super_admin:
  ```python
  if not user_token:
      if os.getenv("RAG_DEV_AUTH", "").lower() in ("1", "true", "yes"):
          _ensure_dev_user()
          return CurrentUser(
              id=1,
              public_token="dev-default",
              role="super_admin",
              is_account=False,
          )
  ```
  生产误开 (k8s configmap 误复制 dev env, docker-compose dev 推到 prod 镜像) → 攻击者无需任何凭证直接 super_admin.
  没启动校验说 "ENV=production 时禁止 RAG_DEV_AUTH=true".
evidence: |
  if not user_token:
      if os.getenv("RAG_DEV_AUTH", "").lower() in ("1", "true", "yes"):
          _ensure_dev_user()
          return CurrentUser(
              id=1,
              public_token="dev-default",
              role="super_admin",
              is_account=False,
          )
impact: |
  - 单条 env 配错 → 整个鉴权层绕过, 任意 anon → super_admin
  - 没有告警/启动 fail-fast
fix_sketch: |
  启动期 `if ENV == "production" and RAG_DEV_AUTH in ("1", "true", "yes"): raise RuntimeError`
  加 audit log 启动时若有 RAG_DEV_AUTH, 打印 WARNING
references: []
```

---

## SEC-011 /api/auth/anon BFF 直接 fetch API_BASE 无 timeout (medium)

```yaml
id: SEC-011
dimension: security
severity: medium
confidence: high
title: "/api/auth/anon BFF fetch 后端无 timeout/AbortSignal, Slowloris 风险"
file: "packages/web/app/api/auth/anon/route.ts"
line: 23
description: |
  BFF `fetch(${API_BASE}/api/auth/anon, { cache: "no-store", method: "POST" })` 无:
  - `signal: req.signal` (用户 disconnect 时取消)
  - timeout (Slowloris 攻击: 后端慢响应, 占用 BFF 连接)
  - 错误降级 (upstream 不可达时返什么?)
  对比 `app/api/[...path]/route.ts` 透传: 那里有 `signal: req.signal`. 这个 anon BFF 漏写.
  攻击者: 高并发 POST /api/auth/anon, 后端慢响应, BFF 容器 socket 耗尽 → 拒绝服务.
evidence: |
  const upstream = await fetch(`${API_BASE}/api/auth/anon`, {
    cache: "no-store",
    method: "POST",
  });
  return proxyAuthResponse(upstream);
impact: |
  - BFF socket 耗尽, 拒绝其他用户请求
  - User disconnect 后 BFF 仍跑完, 浪费资源
fix_sketch: |
  加 `signal: req.signal` + `AbortSignal.timeout(10_000)`. 跟其他 BFF 一致.
references:
  - packages/web/app/api/auth/anon/route.ts:22-28
```

---

## SEC-012 rate limiter key 用 IPv6 全长字符串, Redis 浪费 (low)

```yaml
id: SEC-012
dimension: security
severity: low
confidence: high
title: "rate limiter key 包含 IPv6 全长 (~45 字符), Redis 内存浪费, IPv6 bypass 风险"
file: "packages/service/src/auth/auth_account_router.py"
line: 79
description: |
  `client_ip = request.client.host` 直接作 `check_and_increment("login", client_ip)` key.
  IPv4: "1.2.3.4" (7 字符), OK.
  IPv6: "2001:db8:0:0:0:0:0:1" 或带 zone id 全长 ~45 字符.
  Redis key 越长 → 内存浪费 + 慢查询.
  攻击者: IPv6 子网巨大, 同一攻击者换 IP 就能绕过限流 (e.g. ::1, ::2, ::ffff:1.2.3.4 等).
  项目 CLAUDE.md 提到 redis key 规范 "长 key 取 sha256[:16]", 但 rate limiter 没遵循.
evidence: |
  client_ip = request.client.host if request.client else "unknown"
  allowed, _ = await check_and_increment("login", client_ip)
impact: |
  - IPv6 用户绕过限流 (低概率, 因前端用户通常固定 IP)
  - Redis 内存浪费
fix_sketch: |
  client_ip 用 ipaddress.ip_address(...).compressed + 截 IPv6 前 4 段 (e.g. /64 prefix), 防绕过
  长期: 把 client_ip hash 成 16 字节 hex 作 key
references: []
```

---

## SEC-013 /api/account/avatar/{account_id} 公开 IDOR + 信息泄露 (medium)

```yaml
id: SEC-013
dimension: security
severity: medium
confidence: high
title: "/api/account/avatar/{account_id} 公开 anon 读, 枚举 account_id 可关联用户"
file: "packages/service/src/auth/account_settings_router.py"
line: 164
description: |
  ```python
  @router.get("/avatar/{account_id}")
  def get_avatar(account_id: int):
      with session_scope() as s:
          account = s.get(Account, account_id)
          if account is None or account.avatar_url is None:
              raise HTTPException(status_code=404, detail="avatar not found")
  ```
  无鉴权. 攻击者可枚举 `account_id` (1, 2, 3...), 看到哪些账号上传过头像.
  对比 "404 avatar not found" vs "200 webp bytes", 区分了 "账号不存在" 和 "账号存在但没头像".
  虽然 avatar 本身是公开图片, 但 account_id 序列号让攻击者知道:
  - 哪些 id 是真实账号 (返回 404 因没头像 vs 200 因有头像)
  - 哪些 id 不存在 (返 404 因账号不存在)
  - 头像文件 mtime / size 推算用户活跃度
evidence: |
  @router.get(
      "/avatar/{account_id}",
      summary="获取头像 (代理)",
      description=(
          "## 用途\n\n"
          "ObjectStore 代理路由: 查 Account.avatar_url → ObjectStore.get_bytes → 返 image/webp 字节流.\n\n"
          "## 鉴权\n\n"
          "无需鉴权 (头像公开). 仅 cache 1h.\n\n"
      ),
  )
  def get_avatar(account_id: int):
      with session_scope() as s:
          account = s.get(Account, account_id)
          if account is None or account.avatar_url is None:
              raise HTTPException(status_code=404, detail="avatar not found")
impact: |
  - account_id 枚举泄露用户存在性
  - 用户活跃度推断 (有头像 vs 无头像)
fix_sketch: |
  1. 用 opaque token (UUID) 替代递增 account_id 公开暴露
  2. 不区分 "账号不存在" vs "账号存在但没头像" — 统一返 404 (跟 chat_share "防 ID 探测" 一致)
references: []
```

---

## 总结

| 维度 | 数量 | 主要发现 |
|---|---|---|
| 鉴权 | 5 | BFF 漏注 x-user-token (high), chat-token 暴露 (med), RAG_DEV_AUTH 误开 (low) |
| 注入 | 1 | Cypher label 拼接 (low, 靠白名单防御) |
| IDOR | 2 | avatar/account_id 枚举 (med), chat share 公开 + 创建无审计 (high) |
| SSRF | 1 | DIFY/OPENAI base URL 无白名单 (med) |
| XSS | 1 | Streamdown markdown 渲染 src 未过滤 (med) |
| CORS | 1 | prod env 缺失 CORS_ALLOW_ORIGINS 静默失败 (med) |
| 依赖 CVE | 1 | @js-temporal/polyfill 当前安全, caret range 留意 (info) |
| DoS | 1 | /api/auth/anon fetch 无 timeout (med) |

**P0 (立即修)**:
- SEC-002: 4 个 BFF 加 serverAuthHeaders (影响功能 + 反模式)
- SEC-005: catch-all BFF 强制鉴权 (RAG_DEV_AUTH=prod 时变后门)

**P1 (本周修)**:
- SEC-009: chat share create 加 audit
- SEC-013: avatar/account_id 公开端点统一 404 防枚举
- SEC-004: Streamdown 加 protocol allowlist

**P2 (排期)**:
- 其余 medium/low 项