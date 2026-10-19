# scan-brief.md 模板

> **用法**: 主线程 Phase 1 复制本文件 → `docs/audit/$DATE/scan-brief.md` → 替换 `{{DATE}}` 等占位符
> 6 个 subagent 共享这份 brief, 每个 agent 从自己的维度段 (§D1 - §D6) 读指令
> 不要硬编码到 agent prompt 里 — 写在文件里, agent 启动时 Read

---

```markdown
# scan-brief — 6 维度全栈审计 (YYYY-MM-DD)

> 本文件是 6 个 subagent 的统一指令源. 主线程在 Phase 1 写入 `docs/audit/YYYY-MM-DD/scan-brief.md`, Phase 2 派 agent 时 prompt 里指引用本文件.

## 通用约束 (所有维度共用)

### 你的角色

你是 [{{DIM}}] 维度的扫描 agent. 严格只读 (Read / Grep / Glob / WebSearch / WebFetch), 禁用 Edit / Write / NotebookEdit. 不修改任何业务代码, 不修改 lockfile, 不修改 CI 配置.

### 工作目录

- 项目根: `c:/doc/Code/rag/`
- 你的产出文件: `c:/doc/Code/rag/docs/audit/YYYY-MM-DD/d{{N}}-{{DIM_FILE}}.md`
- 本 brief 文件: `c:/doc/Code/rag/docs/audit/YYYY-MM-DD/scan-brief.md`

### Finding Schema (严格)

每条 finding 必须满足:

```yaml
- id: {{DIM_PREFIX}}-001          # 必填, 3 位数字 (Phase 4 会重新编号)
  dimension: {{DIM}}              # 必填: security|concurrency|error|data|frontend|arch
  severity: critical              # 必填: critical|high|medium|low|info
  confidence: high                # 必填: high|medium|low (Phase 3 verify 会改)
  title: "一句话, ≤ 80 字符"
  file: packages/service/src/...  # 相对项目根
  line: 42                        # 整数
  description: |
    中文, ≥ 2 句, 解释问题本质.
  evidence: |
    ```python
    代码引用 ≥ 3 行 (用 Read 复制真实代码, 不编造)
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

D1 Security **允许** WebSearch / WebFetch (查依赖 CVE).
D2-D6 **禁止** 网络 (纯本地只读).

### 输出格式

你的**最终回复**必须是 markdown 文本, 顶部带元信息 + finding 列表. 结构:

```markdown
# D{{N}}: {{DIM_LABEL}} 扫描结果

> 扫描时间: YYYY-MM-DD
> Agent 角色: {{ROLE}}
> 工具调用次数: X / 30
> 找到 N 条 finding (verified: M, refuted: K, 待 verify: N-M-K)

## 元信息

- 项目根: c:/doc/Code/rag
- 扫描路径: <列出本维度扫过的目录/文件>
- 已知跳过: <因工具限制 / 时间限制 / 网络限制无法覆盖的路径>
- 备注: <其他说明>

## Findings (N 条)

[每条 finding 按 schema 输出, YAML 格式]

## 未扫 / 已知缺口

- (列出本维度未覆盖的路径, 留给下次审计)
```

### 质量门禁 (主线程会用)

1. 每条 finding `evidence` ≥ 3 行真实代码引用 (用 Read 复制)
2. `file:line` 必须在 git HEAD 存在 (主线程会 `git show <file>` 验)
3. severity 必填, 必 ∈ {critical, high, medium, low, info}
4. `id` 维度内唯一, 3 位数字
5. `confidence` 必填, 必 ∈ {high, medium, low}
6. `description` ≥ 2 句中文
7. `fix_sketch` ≤ 3 句中文

---

## 维度特定指令

### D1: Security

**角色**: 偏向攻击者视角: 假设每个端点都可能被绕过.

**必扫路径**:
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

**检查项** (优先级排序):
1. 鉴权缺失/绕过 — 端点无 `Depends(get_current_user)` / 角色检查缺失
2. 注入 — SQL/NoSQL/command/LLM prompt
3. SSRF — `httpx.AsyncClient` 用用户提供的 URL
4. IDOR — 用 user_id 做查询但未校验所属
5. Path traversal — `os.path.join(base, user_input)` 无 `os.path.realpath` 校验
6. 不安全 deserialization — `pickle.loads` / `yaml.load` (不用 safe_load)
7. MinIO presign scope — 上传后未限 read
8. Cookie / CSRF — SameSite / Secure / __Host- 前缀缺失
9. Rate limit — 登录/注册/重置密码无频率限制
10. PII 泄露 — 日志含 email/token/password
11. CORS — `allow_origins=["*"]` 误用
12. env / secret 泄露 — `.env` commit / 前端引用 `process.env.NEXT_PUBLIC_*` 含敏感
13. 弱密码 hash — MD5 / SHA1 / bcrypt cost < 12
14. Token 长度/熵/过期 — JWT 过期 7d+ / secret < 32 字节
15. Deps CVE — `uv run pip-audit` + `bun audit --production`

**Dimension**: `security`
**ID prefix**: `SEC-`
**网络**: 允许 WebSearch / WebFetch 查 deps CVE
**优先级**: 必扫代码 > 必扫 deps > 可选扩展

### D2: Concurrency & State

**角色**: 偏并发视角: 假设所有外部状态都可被并发改写.

**必扫路径**:
- `packages/service/src/chat/service.py`
- `packages/service/src/memory/*`
- `packages/service/src/ingest/tasks.py`
- `packages/service/src/auth/account_service.py`
- `packages/service/src/eval/*`
- `packages/service/src/scheduler/*`
- Grep `session_scope` 在所有 router
- Grep `def.*session` 找所有 service 层函数

**检查项**:
1. TOCTOU — 检查权限后实际使用间隔过大
2. Double-commit — 同一事务提交两次
3. 软删 + 唯一约束 — `deleted_at` 后 unique index 仍生效 → 重名失败
4. Cron 重入 — 长任务未加 distributed lock
5. JSONB read-modify-write 缺锁 — `SELECT → modify → UPDATE` 期间被改
6. 长事务 — 事务内 await 外部 IO
7. 缓存一致性 — DB 改后 Redis 未失效
8. 状态机缺失 — 状态字段无 CHECK 约束
9. Pagination 期间 offset 漂移 — 用 `OFFSET 1000` 时新数据插入导致错位
10. 锁顺序不一致 — A 锁 X 再锁 Y, B 锁 Y 再锁 X → 死锁

**Dimension**: `concurrency`
**ID prefix**: `CONC-`
**网络**: 禁止

### D3: Error handling & Resilience

**角色**: 偏韧性视角: 假设所有外部依赖都不可用.

**必扫路径**:
- `packages/service/src/core/redis_client.py`
- `packages/service/src/storage/object_store.py`
- `packages/service/src/middleware/*`
- Grep `except Exception` / `except:` / `except BaseException` 全局
- Grep `@app.exception_handler` FastAPI 全局处理
- 第三方 SDK 调用: OpenAI / Anthropic / Dify / Neo4j / MinIO

**检查项**:
1. Bare except — `except:` 不指定异常类型
2. 异常吞掉 — `except: pass` / `except: ...` 不 re-raise 不 log
3. 缺失超时 — httpx/requests 无 `timeout=` 参数
4. Retry 风暴 — 无指数退避 / 无 max_retries
5. Fallback 缺失 — Redis 挂时直接 5xx 而非降级到 DB
6. 错误响应泄露 stacktrace — `str(e)` 直接返回给客户端
7. PII 进日志 — log 含 email/token/password
8. 5xx 缺全局 handler — 没有 `@app.exception_handler(Exception)`
9. Circuit breaker 缺失 — 外部依赖挂时持续重试
10. LLM 无 max_tokens 预算 — 用户可传无限长 prompt

**Dimension**: `error`
**ID prefix**: `ERR-`
**网络**: 禁止

### D4: Data integrity & Migrations

**角色**: 偏数据视角: 假设数据被破坏/迁移失败.

**必扫路径**:
- `packages/service/src/storage/migrations/versions/*.py`
- 所有 `models.py` (auth, chat, eval, approvals, kg, lookups, db)
- `packages/service/src/lookups/*`
- Grep `ForeignKey` / `relationship` 找所有 FK 关系
- 每个 alembic migration 的 `downgrade()` 段

**检查项**:
1. Alembic 可回滚性 — `downgrade()` 与 `upgrade()` 不对称
2. ORM / SQL 字段不一致 — 模型有但表无, 或反之
3. FK 缺失/错配 — 逻辑外键无索引
4. FK ondelete 错 — `ondelete="CASCADE"` 在不该删的字段
5. Enum 硬编字符串 — 违反 lookups 唯一事实源 (见 [packages/service/src/lookups/README.md](../../../service/src/lookups/README.md))
6. JSONB 无 schema — `JSONB` 字段无 Pydantic 校验
7. 软删 + 唯一约束冲突 — 同 1
8. 迁移顺序依赖 — B 迁移引用 A 迁移加的列, 但编号在 A 之前
9. Deprecated column 残留 — `is_active` 字段已用 `status` 替换但表里还在
10. 测试用真 migration 缺 isolation — 测试连真 PG (违反 4 模式)

**Dimension**: `data`
**ID prefix**: `DATA-`
**网络**: 禁止

### D5: Frontend pitfalls

**角色**: 偏 React/Next.js 视角: 假设所有用户输入都不可信.

**必扫路径**:
- `packages/web/app/[locale]/**`
- `packages/web/lib/chat/*`
- `packages/web/lib/api/*`
- `packages/web/components/common/**`
- `packages/web/proxy.ts`
- `packages/web/middleware.ts`
- `packages/web/i18n/**`
- `packages/web/next.config.ts`

**检查项**:
1. React 19 / Next.js 16 误用 — `use()` 在 try/catch 之外 / `useFormStatus` 错用
2. useEffect cleanup 缺失 — 订阅/计时器没 cleanup
3. TanStack Query staleTime / cache key 错配 — staleTime=0 导致每次重新 fetch
4. `useRouter` 从 `next/navigation` 引 — 已知 bug 模式 (应从 `@/i18n/navigation` 引)
5. next-intl 漏消息 — 用 `t("key")` 但 zh.json 没注册
6. Bundle 体积过大 — 整库 `import lodash` 而非 `import { debounce } from 'lodash'`
7. Ref 持有陈旧 closure — `useRef` 捕获了旧 props
8. A11y 缺失 — `<div onClick>` 而非 `<button>` / 缺 aria-label
9. `'use client'` / `'use server'` 边界错 — server action 误在 client component
10. Client-secret 泄露到 client bundle — `process.env.OPENAI_API_KEY` 在 `'use client'` 文件
11. 路由跳转 SSR 串 locale — 切换语言后状态污染

**Dimension**: `frontend`
**ID prefix**: `FE-`
**网络**: 禁止

### D6: Architecture & Convention

**角色**: 偏架构视角: 假设所有规约都有例外.

**必扫路径**:
- 全局 (但用 Grep 高效, 不全读)
- 对比 [CLAUDE.md](../../../CLAUDE.md), [packages/service/CLAUDE.md](../../../service/CLAUDE.md), [packages/web/CLAUDE.md](../../../web/CLAUDE.md) 全部规则
- `packages/service/pyproject.toml`
- `packages/web/package.json`
- `bun.lock` + `uv.lock` (只查版本号, 不 commit 修改)
- `tests/` 覆盖率报告 (有的话)
- `.env.example` / `.env.local`

**检查项**:
1. 重复代码 — 相同 ≥ 3 行 ≥ 3 处未抽装
2. 未抽装 — 函数/类 > 100 行违反规约
3. 模块边界违反 — 跨层 import (如 service 直引 web 组件)
4. 规约违反 — CLAUDE.md 已定但代码未遵守 (如不删注释 / 不硬编码 / TDD)
5. 测试缺口 — 4 模式覆盖不全 / 测试连真 PG (违反强制规范)
6. Env 散落 — 配置项没走 [config.py](../../../service/src/config.py)
7. 监控/可观测性缺失 — 关键路径无 metrics/log/trace
8. 文档与代码脱节 — README 说有 X 但代码无
9. `package.json` scripts 不一致 — `bun run lint` 与 `lint:fix` 行为冲突
10. Pre-commit 钩子绕过 — 提交时未跑 lint-staged
11. 业务 enum 硬编 — 违反 lookups 唯一事实源
12. StrEnum 新增不走 lookup — 同上

**Dimension**: `arch`
**ID prefix**: `ARCH-`
**网络**: 禁止

---

## 输出示例 (D1 Security 第一个 finding)

```yaml
- id: SEC-001
  dimension: security
  severity: high
  confidence: high
  title: "忘记密码接口无 rate limit, 可被暴力枚举"
  file: packages/service/src/auth/account_router.py
  line: 142
  description: |
    `POST /auth/forgot-password` 端点接受任意 email, 直接发邮件, 无频率限制.
    攻击者可对单一邮箱发 1000+ 次, 触发邮件轰炸 + 暴露邮箱有效性.
  evidence: |
    ```python
    @router.post("/forgot-password")
    async def forgot_password(email: str):
        await send_reset_email(email)  # 无 rate limit, 无 captcha, 无去重
        return {"ok": True}
    ```
  impact: |
    邮件轰炸 (DoS) + 邮箱枚举攻击 (返回时长差异) + 用户骚扰.
  fix_sketch: |
    加 Redis rate limit (10 次/小时/IP) + 邮箱去重 (1 次/5 分钟/邮箱) + 统一返回时长.
  references:
    - cwe-307
    - owasp-a04:2021
```
```

---

## 重要提示 (给所有 agent)

1. **不要写代码** — 这是 audit, 不是 fix
2. **不要修 lockfile** — 即使发现 deps CVE, 也只在 finding 里记录, 等 P0-security spec 决定如何升级
3. **不要 commit** — 主线程 Phase 4 统一 commit
4. **找不到 finding 是合法的** — 在"未扫/已知缺口"段说明, 不要编
5. **evidence 必须真实** — 主线程会 `git show <file>` 验, 造假会被发现
6. **依赖 scan-brief.md** — 不确定的指令回读本文件, 不要凭记忆
