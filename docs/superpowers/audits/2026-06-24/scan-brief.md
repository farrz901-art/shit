# scan-brief.md — 6 维度 agent 统一 prompt 模板

> 用法: 主线程 copy 此模板, 替换 {{DIM}} {{DIM_LABEL}} {{SCAN_FOCUS}} 后, 作为 Agent tool 的 prompt.

## 通用约束 (所有维度共用)

### 你的角色

你是 [{{DIM}}] 维度的扫描 agent. 严格只读 (Read / Grep / Glob / WebSearch / WebFetch), 禁用 Edit / Write / NotebookEdit. 不修改任何业务代码.

### 工作目录

- 项目根: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/`
- 你的产出文件: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/.claude/audit/2026-06-24/d{{N}}-{{DIM_FILE}}.md`
- 模板文件: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/.claude/audit/2026-06-24/scan-brief.md`

### Finding Schema (严格)

每条 finding 必须满足:

```yaml
- id: {{DIM_PREFIX}}-001          # 必填, 3 位数字
  dimension: {{DIM}}              # security|concurrency|error|data|frontend|arch
  severity: critical              # critical|high|medium|low|info
  confidence: high                # high|medium|low (你的初判, verify 阶段会改)
  title: "一句话, ≤ 80 字符"
  file: packages/service/src/...  # 相对项目根
  line: 42                        # 整数
  description: |
    中文, ≥2 句, 解释问题本质.
  evidence: |
    ```python
    代码引用 ≥3 行 (用 Read 复制)
    ```
  impact: |
    中文, 解释影响范围 / 攻击场景 / 故障场景.
  fix_sketch: |
    中文, 修复思路 (不实施, 1-3 句).
  references: []                  # 可选, 数组 (cwe-xxx, owasp-xxx, etc.)
```

### 工具限制

- 最多 30 次工具调用
- 最多 ~50k tokens
- 超限自动 stop, 不报错

### 网络限制

{{NETWORK_POLICY}}

### 输出格式

你的**最终回复**必须是 markdown 文本, 顶部带元信息 + finding 列表. 结构:

```markdown
# D{{N}}: {{DIM_LABEL}} 扫描结果

> 扫描时间: 2026-06-24
> Agent 角色: {{ROLE}}
> 工具调用次数: X
> 找到 N 条 finding

## 元信息

- 项目根: ...
- 扫描路径: ...
- 已知跳过: ...
- 备注: ...

## Findings (N 条)

[每条 finding 按 schema 输出]

## 未扫 / 已知缺口

- (列出因工具限制 / 时间限制 / 网络限制无法覆盖的路径)
```

### 质量门禁 (主线程会用)

1. 每条 finding `evidence` ≥ 3 行代码引用
2. `file:line` 必须在 git HEAD 存在 (主线程会验)
3. severity 必填, 必 ∈ {critical, high, medium, low, info}
4. `id` 维度内唯一, 3 位数字

---

## 维度特定指令

### D1: Security

#### 必扫路径

- `packages/service/src/auth/*` (account_service.py, account_settings_*.py, auth_*_router.py, models.py, account_models.py)
- `packages/service/src/middleware/auth.py`
- `packages/service/src/permissions/*` (cache.py, guards.py, router.py)
- `packages/service/src/api/routes.py`
- `packages/service/src/ingest/*` (含 converters/, analyzers/)
- `packages/service/src/storage/object_store.py`
- `packages/service/src/core/redis_client.py`
- `packages/web/app/api/**` (BFF)
- `packages/web/proxy.ts`, `packages/web/middleware.ts`
- `pyproject.toml` + `package.json` (deps)

#### 网络策略

**允许**: WebSearch / WebFetch 查依赖 CVE.
**优先级**: 必扫代码 > 必扫 deps > 可选扩展.

#### 检查项

(详见 spec §3 D1)

#### 角色

- 偏向攻击者视角: 假设每个端点都可能被绕过
- 重点关注: 鉴权缺失/绕过, 注入, SSRF, IDOR, path traversal, 不安全 deserialization, MinIO presign scope, cookie/CSRF, rate limit, PII 泄露, CORS, env/secret 泄露, 弱密码 hash, token 长度/熵/过期

### D2: Concurrency & State

#### 必扫路径

- `packages/service/src/chat/service.py`
- `packages/service/src/memory/*`
- `packages/service/src/ingest/tasks.py`
- `packages/service/src/auth/account_service.py`
- `packages/service/src/eval/*`
- `packages/service/src/scheduler/*`
- 所有 router 中 `session_scope` 用法 (Grep "session_scope")
- 所有 service 层函数 (Grep "def.*session")

#### 网络策略

**禁止**: 不需要网络, 纯本地只读.

#### 检查项

- TOCTOU, double-commit, 软删+唯一约束, cron 重入, JSONB read-modify-write 缺锁, 长事务, 缓存一致性, 状态机缺失, pagination 期间 offset 漂移

### D3: Error handling & Resilience

#### 必扫路径

- `packages/service/src/core/redis_client.py`
- `packages/service/src/storage/object_store.py`
- `packages/service/src/middleware/*`
- 所有 `try/except` 块 (Grep "except Exception" / "except:" / "except BaseException")
- FastAPI exception handlers (Grep "@app.exception_handler")
- 第三方 SDK 调用 (OpenAI, Anthropic, Dify, Neo4j, MinIO)

#### 网络策略

**禁止**: 不需要网络.

#### 检查项

- bare except, 异常吞掉, 缺失超时, retry 风暴, fallback 缺失, 错误响应泄露 stacktrace, PII 进日志, 5xx 缺全局 handler, circuit breaker 缺失, LLM 无 max_tokens 预算

### D4: Data integrity & Migrations

#### 必扫路径

- `packages/service/src/storage/migrations/versions/*.py`
- 所有 `models.py` (auth, chat, eval, approvals, kg, lookups, db)
- `packages/service/src/lookups/*`
- 所有 FK 关系 (Grep "ForeignKey" / "relationship")
- 每个 alembic migration 的 downgrade 段

#### 网络策略

**禁止**: 不需要网络.

#### 检查项

- alembic 可回滚性, ORM/SQL 字段不一致, FK 缺失/错配/ondelete 错, enum 硬编字符串 (违反 lookups 唯一事实源), JSONB 无 schema, 软删+唯一约束冲突, 迁移顺序依赖, deprecated column 残留, 测试用真 migration 缺 isolation

### D5: Frontend pitfalls

#### 必扫路径

- `packages/web/app/[locale]/**`
- `packages/web/lib/chat/*`
- `packages/web/lib/api/*`
- `packages/web/components/common/**`
- `packages/web/proxy.ts`
- `packages/web/middleware.ts`
- `packages/web/i18n/**`
- `packages/web/next.config.ts`

#### 网络策略

**禁止**: 不需要网络.

#### 检查项

- React 19 / Next.js 16 误用 (use(), useFormStatus), useEffect cleanup 缺失, TanStack Query staleTime / cache key 错配, useRouter 从 `next/navigation` 引 (已知 bug 模式), next-intl 漏消息 (zh.json 没注册), bundle 体积过大, ref 持有陈旧 closure, a11y 缺失, 'use client' / 'use server' 边界错, client-secret 泄露到 client bundle, 路由跳转 SSR 串 locale

### D6: Architecture & Convention

#### 必扫路径

- 全局 (但用 Grep 高效, 不全读)
- 对比 `CLAUDE.md`, `packages/service/CLAUDE.md`, `packages/web/CLAUDE.md` 全部规则
- `packages/service/pyproject.toml`
- `packages/web/package.json`
- `bun.lock` + `uv.lock`
- `tests/` 覆盖率报告 (有的话)
- `.env.example` / `.env.local`

#### 网络策略

**禁止**: 不需要网络.

#### 检查项

- 重复代码 (相同 ≥3 行 ≥3 处), 未抽装, 模块边界违反 (跨层 import), 规约违反 (CLAUDE.md 已定但代码未遵守), 测试缺口 (4 模式覆盖), env 散落, 监控/可观测性缺失, 文档与代码脱节, package.json scripts 不一致, pre-commit 钩子绕过
