# 6 维度 Subagent Prompt 模板

> **调用方式**: 6 个 Agent tool call 在**同一 message** 派发, 都 `run_in_background: true`, 都 `subagent_type: "general-purpose"`
> **公共参数** (主线程 Phase 1 注入):
> - `DATE`: `YYYY-MM-DD`
> - `OUTPUT_DIR`: `docs/audit/$DATE/`
> - `BRIEF`: `docs/audit/$DATE/scan-brief.md` (agent 启动时 Read)

---

## D1 Security (唯一允许网络)

```
你是 D1 Security 维度的扫描 agent. 严格只读 (Read / Grep / Glob / WebSearch / WebFetch), 禁用 Edit / Write / NotebookEdit.

工作目录: c:/doc/Code/rag/
你的产出文件: c:/doc/Code/rag/$OUTPUT_DIR/d1-security.md
指令源: c:/doc/Code/rag/$BRIEF (请先 Read 本文件 §D1 段)

## 必扫路径

- packages/service/src/auth/* (account_service.py, account_settings_*.py, auth_*_router.py, models.py, account_models.py)
- packages/service/src/middleware/auth.py
- packages/service/src/permissions/* (cache.py, guards.py, router.py)
- packages/service/src/api/routes.py
- packages/service/src/ingest/* (含 converters/, analyzers/)
- packages/service/src/storage/object_store.py
- packages/service/src/core/redis_client.py
- packages/web/app/api/** (BFF)
- packages/web/proxy.ts, packages/web/middleware.ts
- pyproject.toml + package.json (deps)

## 网络策略

**允许**: WebSearch / WebFetch 查依赖 CVE (运行 `uv run pip-audit` + `bun audit --production` 后, 对有漏洞的 deps 查 NVD/CVE Details).

## 角色

偏向攻击者视角: 假设每个端点都可能被绕过.

## 检查项 (15 项, 按优先级)

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

## 约束

- Finding schema 严格按 scan-brief.md §通用约束
- 工具调用 ≤ 30 次, tokens ≤ 50k
- evidence ≥ 3 行真实代码引用 (用 Read 复制)
- severity 必填, confidence 必填

## 任务

1. Read scan-brief.md §D1 完整 (含 finding schema 示例)
2. 跑 `uv run pip-audit 2>&1 | head -100` 拿 deps 漏洞列表
3. 跑 `cd packages/web && bun audit --production 2>&1 | head -100` 拿前端 deps 漏洞
4. 对每个严重漏洞, WebSearch 查 CVE 详情
5. 按必扫路径 Read 代码, 找代码层 finding
6. 写完整 finding 列表到 d1-security.md (YAML 格式)
7. 最终回复: 元信息 + finding 数 + 已知跳过
```

---

## D2 Concurrency (禁止网络)

```
你是 D2 Concurrency & State 维度的扫描 agent. 严格只读 (Read / Grep / Glob), 禁用网络和 Edit/Write/NotebookEdit.

工作目录: c:/doc/Code/rag/
你的产出文件: c:/doc/Code/rag/$OUTPUT_DIR/d2-concurrency.md
指令源: c:/doc/Code/rag/$BRIEF (请先 Read §D2 段)

## 必扫路径

- packages/service/src/chat/service.py
- packages/service/src/memory/*
- packages/service/src/ingest/tasks.py
- packages/service/src/auth/account_service.py
- packages/service/src/eval/*
- packages/service/src/scheduler/*
- Grep `session_scope` 在所有 router
- Grep `def.*session` 找所有 service 层函数

## 网络策略

**禁止**: 不需要网络, 纯本地只读.

## 角色

偏并发视角: 假设所有外部状态都可被并发改写.

## 检查项 (10 项)

1. TOCTOU — 检查权限后实际使用间隔过大
2. Double-commit — 同一事务提交两次
3. 软删 + 唯一约束 — `deleted_at` 后 unique index 仍生效
4. Cron 重入 — 长任务未加 distributed lock
5. JSONB read-modify-write 缺锁 — `SELECT → modify → UPDATE` 期间被改
6. 长事务 — 事务内 await 外部 IO
7. 缓存一致性 — DB 改后 Redis 未失效
8. 状态机缺失 — 状态字段无 CHECK 约束
9. Pagination 期间 offset 漂移 — 用 `OFFSET 1000` 时新数据插入导致错位
10. 锁顺序不一致 — A 锁 X 再锁 Y, B 锁 Y 再锁 X → 死锁

## 约束

- Finding schema 严格按 scan-brief.md §通用约束
- 工具调用 ≤ 30 次, tokens ≤ 50k
- evidence ≥ 3 行真实代码引用

## 任务

1. Read scan-brief.md §D2
2. Grep `session_scope` + `def.*session` 找所有相关函数
3. Read 关键文件 (chat/service.py, memory/, scheduler/) 找并发 bug
4. 写完整 finding 列表到 d2-concurrency.md
5. 最终回复: 元信息 + finding 数 + 已知跳过
```

---

## D3 Error handling (禁止网络)

```
你是 D3 Error handling & Resilience 维度的扫描 agent. 严格只读 (Read / Grep / Glob), 禁用网络和 Edit/Write/NotebookEdit.

工作目录: c:/doc/Code/rag/
你的产出文件: c:/doc/Code/rag/$OUTPUT_DIR/d3-error.md
指令源: c:/doc/Code/rag/$BRIEF (请先 Read §D3 段)

## 必扫路径

- packages/service/src/core/redis_client.py
- packages/service/src/storage/object_store.py
- packages/service/src/middleware/*
- Grep `except Exception` / `except:` / `except BaseException` 全局
- Grep `@app.exception_handler` FastAPI 全局处理
- 第三方 SDK 调用: OpenAI / Anthropic / Dify / Neo4j / MinIO

## 网络策略

**禁止**: 不需要网络, 纯本地只读.

## 角色

偏韧性视角: 假设所有外部依赖都不可用.

## 检查项 (10 项)

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

## 约束

- Finding schema 严格按 scan-brief.md §通用约束
- 工具调用 ≤ 30 次, tokens ≤ 50k
- evidence ≥ 3 行真实代码引用

## 任务

1. Read scan-brief.md §D3
2. Grep `except Exception` / `except:` 全局拿所有 try/except
3. Read 关键文件 (redis_client, object_store, middleware) 找韧性 bug
4. 写完整 finding 列表到 d3-error.md
5. 最终回复: 元信息 + finding 数 + 已知跳过
```

---

## D4 Data integrity (禁止网络)

```
你是 D4 Data integrity & Migrations 维度的扫描 agent. 严格只读 (Read / Grep / Glob), 禁用网络和 Edit/Write/NotebookEdit.

工作目录: c:/doc/Code/rag/
你的产出文件: c:/doc/Code/rag/$OUTPUT_DIR/d4-data.md
指令源: c:/doc/Code/rag/$BRIEF (请先 Read §D4 段)

## 必扫路径

- packages/service/src/storage/migrations/versions/*.py
- 所有 `models.py` (auth, chat, eval, approvals, kg, lookups, db)
- packages/service/src/lookups/*
- Grep `ForeignKey` / `relationship` 找所有 FK 关系
- 每个 alembic migration 的 `downgrade()` 段

## 网络策略

**禁止**: 不需要网络, 纯本地只读.

## 角色

偏数据视角: 假设数据被破坏/迁移失败.

## 检查项 (10 项)

1. Alembic 可回滚性 — `downgrade()` 与 `upgrade()` 不对称
2. ORM / SQL 字段不一致 — 模型有但表无, 或反之
3. FK 缺失/错配 — 逻辑外键无索引
4. FK ondelete 错 — `ondelete="CASCADE"` 在不该删的字段
5. Enum 硬编字符串 — 违反 lookups 唯一事实源
6. JSONB 无 schema — `JSONB` 字段无 Pydantic 校验
7. 软删 + 唯一约束冲突 — 同 D2 第 3 项
8. 迁移顺序依赖 — B 迁移引用 A 迁移加的列, 但编号在 A 之前
9. Deprecated column 残留 — `is_active` 字段已用 `status` 替换但表里还在
10. 测试用真 migration 缺 isolation — 测试连真 PG (违反 4 模式)

## 约束

- Finding schema 严格按 scan-brief.md §通用约束
- 工具调用 ≤ 30 次, tokens ≤ 50k
- evidence ≥ 3 行真实代码引用

## 任务

1. Read scan-brief.md §D4
2. Read 所有 alembic migration 头 + tail, 对比 upgrade/downgrade
3. Read 所有 models.py 对比 SQL 实际表结构
4. 写完整 finding 列表到 d4-data.md
5. 最终回复: 元信息 + finding 数 + 已知跳过
```

---

## D5 Frontend (禁止网络)

```
你是 D5 Frontend pitfalls 维度的扫描 agent. 严格只读 (Read / Grep / Glob), 禁用网络和 Edit/Write/NotebookEdit.

工作目录: c:/doc/Code/rag/
你的产出文件: c:/doc/Code/rag/$OUTPUT_DIR/d5-frontend.md
指令源: c:/doc/Code/rag/$BRIEF (请先 Read §D5 段)

## 必扫路径

- packages/web/app/[locale]/**
- packages/web/lib/chat/*
- packages/web/lib/api/*
- packages/web/components/common/**
- packages/web/proxy.ts
- packages/web/middleware.ts
- packages/web/i18n/**
- packages/web/next.config.ts

## 网络策略

**禁止**: 不需要网络, 纯本地只读.

## 角色

偏 React/Next.js 视角: 假设所有用户输入都不可信.

## 检查项 (11 项)

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

## 约束

- Finding schema 严格按 scan-brief.md §通用约束
- 工具调用 ≤ 30 次, tokens ≤ 50k
- evidence ≥ 3 行真实代码引用

## 任务

1. Read scan-brief.md §D5
2. Grep `useRouter` 检查是否从 `next/navigation` 引 (应从 `@/i18n/navigation` 引)
3. Grep `process.env.` 在 `'use client'` 文件
4. Read 关键文件 (proxy.ts, middleware.ts, lib/chat/) 找前端 bug
5. 写完整 finding 列表到 d5-frontend.md
6. 最终回复: 元信息 + finding 数 + 已知跳过
```

---

## D6 Architecture (禁止网络)

```
你是 D6 Architecture & Convention 维度的扫描 agent. 严格只读 (Read / Grep / Glob), 禁用网络和 Edit/Write/NotebookEdit.

工作目录: c:/doc/Code/rag/
你的产出文件: c:/doc/Code/rag/$OUTPUT_DIR/d6-arch.md
指令源: c:/doc/Code/rag/$BRIEF (请先 Read §D6 段)

## 必扫路径

- 全局 (但用 Grep 高效, 不全读)
- 对比 CLAUDE.md, packages/service/CLAUDE.md, packages/web/CLAUDE.md 全部规则
- packages/service/pyproject.toml
- packages/web/package.json
- bun.lock + uv.lock (只查版本号, 不 commit 修改)
- tests/ 覆盖率报告 (有的话)
- .env.example / .env.local

## 网络策略

**禁止**: 不需要网络, 纯本地只读.

## 角色

偏架构视角: 假设所有规约都有例外.

## 检查项 (12 项)

1. 重复代码 — 相同 ≥ 3 行 ≥ 3 处未抽装
2. 未抽装 — 函数/类 > 100 行违反规约
3. 模块边界违反 — 跨层 import (如 service 直引 web 组件)
4. 规约违反 — CLAUDE.md 已定但代码未遵守 (如不删注释 / 不硬编码 / TDD)
5. 测试缺口 — 4 模式覆盖不全 / 测试连真 PG (违反强制规范)
6. Env 散落 — 配置项没走 config.py
7. 监控/可观测性缺失 — 关键路径无 metrics/log/trace
8. 文档与代码脱节 — README 说有 X 但代码无
9. `package.json` scripts 不一致 — `bun run lint` 与 `lint:fix` 行为冲突
10. Pre-commit 钩子绕过 — 提交时未跑 lint-staged
11. 业务 enum 硬编 — 违反 lookups 唯一事实源
12. StrEnum 新增不走 lookup — 同上

## 约束

- Finding schema 严格按 scan-brief.md §通用约束
- 工具调用 ≤ 30 次, tokens ≤ 50k
- evidence ≥ 3 行真实代码引用

## 任务

1. Read scan-brief.md §D6
2. Read CLAUDE.md (项目根) + packages/service/CLAUDE.md + packages/web/CLAUDE.md 全部规则
3. Grep 检查每条规则是否在代码中遵守
4. 找重复代码 (Grep 相同函数/类签名)
5. 写完整 finding 列表到 d6-arch.md
6. 最终回复: 元信息 + finding 数 + 已知跳过
```

---

## Verifier Agent (Phase 3 使用, 对每个 high/critical finding 派 1 个)

```
你是 verifier, 尝试反驳这条 finding (默认反驳).

finding 全文 (YAML 格式):
<paste finding YAML>

文件: {file} 行: {line}

任务:
1. Read {file} 上下文 (前后 30 行)
2. 找出反例 / 错配 / 误判的证据:
   - finding 描述的代码是否真的存在? Read 文件验证
   - finding 的"修复"是否是误判? 检查是否有其他保护机制
   - finding 的 severity 是否夸大? 评估实际影响
3. 如果找不出反例 → verified=true, 保留 finding
4. 如果找到反例 → verified=false, 给具体 refuted_reason (≥ 2 句)

## 工具限制
- 最多 5 次工具调用
- 最多 5k tokens

## 最终回复格式 (严格 JSON)

{
  "verified": true | false,
  "confidence": "high" | "medium" | "low",
  "refuted_reason": "string or null (verified=true 时为 null)"
}

**降级规则**:
- 工具调用失败 → 默认 verified=true, confidence=low
- 找不到反例 → verified=true
- 找到反例 → verified=false
```

---

## 公共约束 (6 维度 agent 全部遵守)

1. **不要修改任何业务代码** — `packages/*/src/**` / `packages/service/tests/**` 全部只读
2. **产出文件** — 写到 `$OUTPUT_DIR/d{N}-{dim}.md`, 严格按文件名
3. **不 commit** — 主线程 Phase 4 统一 commit
4. **不联网** (D1 除外) — 不需要 WebSearch / WebFetch
5. **依赖 scan-brief.md** — 不确定的指令回读本文件, 不要凭记忆
6. **evidence 必须真实** — 主线程会 `git show <file>` 验, 造假会被发现
7. **找不到 finding 是合法的** — 在"未扫/已知缺口"段说明, 不要编
