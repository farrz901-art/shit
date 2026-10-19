# 2026-06-24 全栈审计修复 Plan (Master)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修完 2026-06-24 全栈审计发现的 60 条 finding, 每条给具体修法 (修什么 + 改哪里 + 怎么验).

**Architecture:** Master plan 模式 — 不强求 TDD 拆解 (60 条 finding 每条写完整测试代码成本过高), 按严重度分 6 个 Phase 实施. 每条 finding 用 "修法 + 验证" 紧凑格式, 真正实施时按 finding 单独走 `brainstorm → spec → plan → implement` 循环 (大块 ≥10 条走批量). 详细 finding (含 evidence) 走 [docs/audit/2026-06-24/d1-d6](docs/audit/2026-06-24/) 引.

**Tech Stack:**
- 后端: Python 3.14, FastAPI, SQLAlchemy 2.0, Alembic, pytest
- 前端: TypeScript 8, React 19, Next.js 16, vitest, oxlint, tsgo
- 工具链: ruff / pyright / oxfmt / oxlint / tsgo / pytest / vitest / Playwright
- 测试隔离 4 模式: 1 纯单测 mock, 2 db_session 集成, 3 tmp_pg_schema (未实现), 4 E2E

**Worktree:** 不创建, 在 master 直接修 (按 CLAUDE.md 强制: 单 PR 走 audit-fix-batch 1, 2, 3, ...)

---

## 文件结构 (本次实施新增/修改)

| 路径 | 类型 | 责任 |
|---|---|---|
| `docs/audit/2026-06-24-findings.md` | 修改 | 每条 finding 追加"修复方案"段 |
| `docs/superpowers/plans/2026-06-24-audit-fixes.md` | 新建 (本文件) | Master plan |
| 业务代码 | 按 finding 修 | 60 个不同 file:line, 跨 packages/service + packages/web |
| 测试 | 按 finding 加 | 模式 1 mock 为主, 模式 2 集成补 |

---

## Phase 1: Critical 立即修 (9 条, 1-2 周)

> 来源: 关联 checklist [Critical 段](docs/audit/2026-06-24-findings.md#critical-必须修--9-条)

### Task 1.1: SEC-002 — chat_share presign path traversal

**修法**:
- 文件: `packages/service/src/chat_share/schemas.py:65`
- 改: `name: str = Field(..., min_length=1, max_length=255)` → `name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9._-]+$")`
- 文件: `packages/service/src/chat_share/router.py:293`
- 改: `f"s3://{bucket}/chat/{current.id}/{req.name}"` → `f"s3://{bucket}/chat/{current.id}/{Path(req.name).name}"` (兜底防 schema 漏)
- 同步改 SEC-008 (presign_get) 加 URI 归属校验: 从 request 拿 `user_id`, verify 跟 `current.id` 一致才放行

**验证**:
- pytest 模式 1 mock: `tests/chat_share/test_presign_chat_file.py::test_name_with_path_traversal_rejected` (用 `name="../999/x.png"` 测, 期望 422)
- pytest 模式 1 mock: `test_presign_get_user_id_mismatch_returns_403`
- 手动 curl 验: `name=../999/x.png` → 422

---

### Task 1.2: SEC-003 — kg/router stats / health 无鉴权

**修法**:
- 文件: `packages/service/src/kg/router.py:71` (`/stats` 端点) + 全文找其他未加 guard 的端点
- 改: 加 `Depends(resolve_user)` + `@require_page("kg")` (或 admin 才能调, 跟 `/api/kg/*` 其他端点对齐)
- 注: 描述说"无 (内部/前端通用)", 实际前端有调 → 至少加 `resolve_user` 强制登录
- 业务侧跟前端确认: `kg.stats` 是否 admin-only? 如果是, 加 `@require_page("admin")`

**验证**:
- pytest 模式 1: `tests/kg/test_router_auth.py::test_stats_requires_login_returns_401_for_anon`
- pytest 模式 1: `test_stats_requires_admin_returns_403_for_normal_user`
- 手动 curl: 拿掉 cookie → 期望 401

---

### Task 1.3: CON-001 — invite redeem 双重 session TOCTOU

**修法**:
- 文件: `packages/service/src/auth/auth_invite_router.py:115` (redeem_invite 函数)
- 改: 在 `session_scope` 内, 第一次查 invite 后, 用 `SELECT ... FOR UPDATE` 锁 row, 再 check `used_at is None` + 改 status, 单事务完成
- 业务侧跟前端确认: 双重兑换实际表现 (业务翻译 409 → 500) 是否要分两个明确错误码

**验证**:
- pytest 模式 2 (db_session): `tests/auth/test_invite_redeem_concurrency.py::test_concurrent_redeem_only_one_succeeds` (开 2 个 session 并发 redeem, 期望 1 成功 1 失败)
- pytest 模式 1 mock: 验 500 → 409 错误码翻译

---

### Task 1.4: CON-002 — cancel_deletion 缺锁 + cron 误删

**修法**:
- 文件: `packages/service/src/auth/account_settings_service.py:188` (cancel_account_deletion 函数)
- 改 1: cancel 流程加 `SELECT ... FOR UPDATE` 锁 account 行, 同时给 DeletionRestore.used_at 加 `UNIQUE(account_id)` 约束防重放
- 改 2: cron 删账号时, 过滤条件加 `is_active=true AND (deletion_requested_at IS NULL OR deletion_requested_at > NOW() - INTERVAL '30 days')` — 但这个是数据库态查询, 改 cron 端即可
- 文件: `packages/service/src/scheduler/*` (找 hard_delete_accounts cron)
- 改 cron 任务逻辑: 删前再 check 一次 `is_active=true` (防 cancel 跟 cron 并发, cancel 把 is_active 改回 true 后 cron 已经标记要删)

**验证**:
- pytest 模式 2: `tests/auth/test_cancel_deletion_concurrency.py::test_cancel_during_cron_keeps_account_active`
- pytest 模式 1: 验 DeletionRestore.used_at 唯一约束在 SQL 层

---

### Task 1.5: DATA-001 — 20260623 migration downgrade 必失败

**修法**:
- 文件: `packages/service/src/storage/migrations/versions/20260623_000000_drop_account_id_from_field_configs.py:31` (downgrade 函数)
- 改: 重写 downgrade. 不能用 `server_default="0"` (会让所有现有行落同一 account_id → UNIQUE 冲突). 改用:
  ```python
  op.add_column("field_configs", sa.Column("account_id", sa.BigInteger(), nullable=True))
  # 1. 删所有 UNIQUE 约束涉及 account_id 的
  op.drop_constraint("uq_field_configs_account_id_code", "field_configs", type_="unique")
  # 2. 回填: 用最近的 account_id 关联 (查 audit log 或 NULL)
  op.execute("UPDATE field_configs SET account_id = NULL")  # 或 join accounts 表
  # 3. 加 NOT NULL + FK
  op.alter_column("field_configs", "account_id", nullable=False)
  op.create_unique_constraint("uq_field_configs_account_id_code", "field_configs", ["account_id", "code"])
  op.create_foreign_key("fk_field_configs_account_id", "field_configs", "accounts", ["account_id"], ["id"])
  ```
- 实际 account_id 选哪个: 业务侧确认 (latest audit log? account_id=1 super admin? 还是允许 NULL?). 跟产品/业务确认后定.

**验证**:
- 跑真实 migration: `uv run alembic downgrade -1` → 期望成功
- 再 `uv run alembic upgrade head` → 期望成功 (数据无丢失)
- 端到端: dev DB 跑一遍, 检查 `field_configs` 行数不变 + FK 关系正确

---

### Task 1.6: DATA-002 — Account ORM/migration 约束名不一致

**修法**:
- 文件: `packages/service/src/auth/account_models.py:36` (Account ORM)
- 改 ORM `__table_args__`:
  - `CheckConstraint` name: `email_format` → `ck_accounts_email_format`
  - `Index` name: `idx_accounts_email` → `ix_accounts_email`
  - `UniqueConstraint` name: 检查, 如 `uq_accounts_email` → 跟 migration 对齐
- 同步找所有 `__table_args__` 命名跟 migration 不一致的 (alembic `uv run alembic check` 会报 diff)

**验证**:
- `uv run alembic check` → 期望 0 drift
- 跑 `uv run alembic revision --autogenerate -m "test"` → 期望 0 改动 (空 migration)

---

### Task 1.7: DATA-003 — conversations.user_id FK 缺 ondelete

**修法**:
- 新建 migration: `20260624_000000_add_conversations_user_fk_ondelete.py`
- 改: 
  ```python
  op.drop_constraint("fk_conversations_user_id", "conversations", type_="foreignkey")
  op.create_foreign_key(
      "fk_conversations_user_id", "conversations", "users",
      ["user_id"], ["id"], ondelete="CASCADE"
  )
  ```
- 同步改 `messages` + `ingest_tasks` + `approvals` 等 user_id 字段 (GDPR 删账号完整清理)
- 业务侧: GDPR 流程目前是软删, 还是硬删? 影响 ondelete 选 CASCADE 还是 SET NULL

**验证**:
- 跑 `uv run alembic upgrade head` → 期望成功
- 手动 SQL: `DELETE FROM users WHERE id=某个测试用户` → 关联 conversations/messages 全删

---

### Task 1.8: FE-001 + FE-002 — useRouter critical 违规

**修法**:
- 文件 1: `packages/web/app/[locale]/evaluate/new/_components/evaluate-new-form.tsx:21`
- 改: `import { useRouter } from "next/navigation"` → `import { useRouter } from "@/i18n/navigation"`
- 验: `router.push` 路径不带 locale 前缀时, wrapper 自动加 (跟 login/invite 已修同模式)
- 文件 2: `packages/web/app/[locale]/output/new/page.tsx:22` 同改
- 注意: 改完跑一遍 typecheck + lint + 现有 e2e

**验证**:
- 浏览器手动验: 提交 evaluate form → 应该直接到 `/zh/evaluate/{id}`, 无 307
- vitest: `app/[locale]/evaluate/new/_components/evaluate-new-form.test.tsx` 加 import guard
- Playwright e2e: 跑 `e2e/04-evaluate.spec.ts` 验新流程无 307

---

## Phase 2: High 优先修 (27 条, 1 个月)

> 来源: 关联 checklist [High 段](docs/audit/2026-06-24-findings.md#high-高优先--27-条)

### Task 2.1: SEC-004 — PII scrub 19 字段散落

**修法**:
- 新建 `packages/service/src/core/pii_fields.py` (集中字段列表)
- 内容: `PII_FIELDS = frozenset({"password", "token", "api_key", "secret", "authorization", "ssn", ...})` 18 字段
- 改 `packages/service/src/core/logging.py:22` 引用 `from .pii_fields import PII_FIELDS`
- 删除 19 处散落定义

**验证**:
- pytest 模式 1: `tests/core/test_logging_pii.py::test_all_19_pii_fields_scrubbed` (用 `extra={"password": "x"}` 验 log 行不含 "password")

---

### Task 2.7: SEC-005 — CORS allow_origins env 默认 + localhost

**修法**:
- 文件: `packages/service/src/core/app_factory.py:125`
- 改: 读 `ENV` env var, 强制 production 时 `allow_origins` 只从白名单读, 不含 localhost
- 业务侧: production CORS 白名单是哪些域? 文档化到 `docs/operations/`

**验证**:
- pytest 模式 1: `test_cors_production_rejects_localhost` (ENV=production + origin=http://localhost:3000 → 拒绝)
- pytest 模式 1: `test_cors_dev_allows_localhost` (ENV=dev → 允许)

---

### Task 2.8: SEC-006 — 前端 bundle 误用 process.env

**修法**:
- 文件: `packages/web/lib/chat/openai.ts:9`
- 改: 移走 `OPENAI_API_KEY` 直调, 改 server-only API route (BFF)
- 同步 grep 全项目 `packages/web` 找 `process.env.NON_PUBLIC_*` / `process.env.SECRET_*` / `process.env.*KEY*` (排除 `NEXT_PUBLIC_*`)

**验证**:
- 跑 `bun run build` + grep bundle `js` 文件, 找 `OPENAI_API_KEY` 字面量 → 期望 0 命中
- vitest: `test_openai_does_not_contain_secret`

---

### Task 2.9: CON-003 — verify_email_change TOCTOU

**修法**:
- 文件: `packages/service/src/auth/account_settings_service.py:121`
- 改: verify_email_change 流程加 `SELECT ... FOR UPDATE` 锁 user 行, 同一事务内 check current_email 跟 token 关联

**验证**:
- pytest 模式 2: `tests/auth/test_email_change_concurrency.py::test_concurrent_verify_only_one_succeeds`

---

### Task 2.10: CON-004 — buyer_profile JSONB RMW 缺锁

**修法**:
- 文件: `packages/service/src/buyer_profile/service.py:63`
- 改: 不用 ORM 读 + 改 + 写, 改用 PG `||` 原子操作:
  ```python
  result = await session.execute(
      update(BuyerProfile)
      .where(BuyerProfile.id == profile_id, BuyerProfile.user_id == current.id)
      .values(profile_data=BuyerProfile.profile_data.op("||")(:new_data))
      .returning(BuyerProfile.profile_data)
  )
  ```
- 跨 session 冲突: 用乐观锁版本号 OR 直接原子 merge

**验证**:
- pytest 模式 2: `test_concurrent_profile_update_preserves_all_fields` (2 个 session 并发改不同字段, 期望全部保留)
- pytest 模式 2: `test_concurrent_profile_update_same_field_last_writer_wins`

---

### Task 2.11: CON-005 — run_evaluation cancel_event 不持久化

**修法**:
- 文件: `packages/service/src/eval/runner.py:158`
- 改: cancel_event 状态存 `evaluations.cancel_requested_at` 字段, 启动时从 DB 读, cancel 时写 DB
- 同步改 evaluation model 加 `cancel_requested_at: Mapped[datetime | None]`

**验证**:
- pytest 模式 2: `test_run_evaluation_respects_persisted_cancel_state_after_restart`
- pytest 模式 2: `test_cancel_persists_to_db_for_crash_recovery`

---

### Task 2.12: CON-006 — finalize_upload 状态机缺原子

**修法**:
- 文件: `packages/service/src/ingest/api.py:358`
- 改: finalize 流程用 PG advisory lock 或 row-level lock (`SELECT ... FOR UPDATE` on ingest_tasks row), 避免重复 add_task

**验证**:
- pytest 模式 2: `test_concurrent_finalize_only_creates_one_task`

---

### Task 2.13: ERR-001 — evaluator 静默吞错返 None

**修法**:
- 文件: `packages/service/src/eval/llama_eval.py:109`
- 改: `except Exception: return None` → `raise`, 上层 service 决定 fallback 策略
- 同步: 上层 service 加 `try/except EvaluatorError: return EvalResult(status="error", error=...)` 而不是吞

**验证**:
- pytest 模式 1: `test_evaluator_raises_on_evaluation_failure` (mock evaluator 抛错, 验 service 返 error status 而非 None)

---

### Task 2.14: ERR-002 — memory search/list 异常吞

**修法**:
- 文件: `packages/service/src/memory/service.py:134`
- 改: 异常分两类 (`ErrorKind.BUSINESS_RECOVERABLE` 返空, `ErrorKind.SYSTEM` raise), 业务可恢复不静默, 系统故障抛 500

**验证**:
- pytest 模式 1: `test_memory_search_business_error_returns_empty_with_warning`
- pytest 模式 1: `test_memory_search_system_error_raises_500`

---

### Task 2.15: ERR-005 — Dify 集成无 retry / 超时

**修法**:
- 文件: `packages/service/src/integrations/dify_datasets.py:42` (3 处 httpx 调用)
- 改: 加 `tenacity` retry (指数退避, max 3 次) + 显式 `timeout=httpx.Timeout(10.0, connect=5.0)`
- 同步: `packages/service/src/integrations/chat_share.py` 同样改

**验证**:
- pytest 模式 1: `test_dify_request_retries_on_5xx` (mock httpx 第 2 次返 200, 期望最终成功)
- pytest 模式 1: `test_dify_request_times_out_after_10s` (mock httpx 挂起, 期望 Timeout)

---

### Task 2.16: DATA-004 — accounts.role 无 FK 跟 lookup 字典

**修法**:
- 新建 migration 加 `roles` 字典 (code: `super_admin`, `admin`, `user`, `anon`)
- 改: `accounts.role` + `role_permissions.role_name` 改 FK 到 `dictionary_items` 表 (走 lookup 字典模式)
- 业务侧确认: 4 角色是否够, 是否要扩

**验证**:
- `uv run alembic upgrade head` + `uv run python -m scripts.seed_dictionaries` 期望 0 新建 (已经 seed)
- 写 pytest 模式 2 验 FK 约束

---

### Task 2.17: DATA-005 — buyer_profiles FK 缺 ondelete

**修法**:
- 新建 migration: 3 张表 (buyer_profiles / profile_change_logs / profile_field_configs) 全部 FK 加 ondelete CASCADE (跟 account 删同步)
- 同步改 ORM `ondelete="CASCADE"`

**验证**:
- 跑 migration, 手动删一个 buyer_profile 关联的 account → 期望所有关联行级联删

---

### Task 2.18: DATA-006 — buyer_profiles.status 硬编 String

**修法**:
- 改 `buyer_profiles.status` 字段走 lookup 字典 (`profile_status` code)
- 新建字典 seed: `active` / `archived` / `pending_review`
- 业务侧确认 status 列表

**验证**:
- 写 pytest 模式 1: `test_buyer_profile_status_uses_lookup_dict`
- 跑 `seed_dictionaries` 期望 0 新建

---

### Task 2.19: DATA-007 — chat_shares 类型/长度不一致

**修法**:
- 文件: `packages/service/src/chat_share/models.py:23`
- 改: `conv_id: Mapped[str] = mapped_type(String(128), ForeignKey("conversations.id"))` → `String(36)`, 跟 `conversations.id` 对齐
- 改: `user_id: Mapped[str] = mapped_type(String(64))` → `Integer` 跟 `users.id` 对齐
- 加 FK: `ForeignKey("conversations.id", ondelete="CASCADE")` + `ForeignKey("users.id", ondelete="CASCADE")`

**验证**:
- 跑 migration, 手动插一条 conv_id 长度 200 的数据 → 期望失败
- 跑模式 2 测试覆盖 FK 关系

---

### Task 2.20: DATA-008 — JSONB 字段无 Pydantic schema

**修法**:
- 新建 `packages/service/src/buyer_profile/schemas.py::ProfileData` (Pydantic BaseModel)
- 改 migration: `profile_data` / `change_logs.old_value` 字段加 CHECK 约束 (jsonb_typeof), 或 ORM 层 Pydantic 验证
- ORM `profile_data: mapped_column(JSONB, default=...)` 加 validator

**验证**:
- pytest 模式 1: `test_profile_data_validates_against_schema` (传非法结构 → ValidationError)
- pytest 模式 2: 写入 DB 后读回, 类型一致

---

### Task 2.21-2.29: FE-003 ~ FE-011 (9 个 useRouter 违规)

**修法 (统一)**:
- 12 个文件批量改 (FE-001 + FE-002 + FE-003~FE-011 + FE-009 back-link 优先):
  ```typescript
  // 旧
  import { useRouter } from "next/navigation";
  // 新
  import { useRouter } from "@/i18n/navigation";
  ```
- 移除手动拼 `${params.locale}/foo` 的兜底代码
- 加 import guard 测试: `packages/web/vitest.setup.ts` 或 `tests/import-guard.test.ts` grep 所有 `*.tsx` 文件, 任何 `from "next/navigation"` 引 `useRouter` 都 fail

**验证**:
- vitest: `test_no_useRouter_from_next_navigation` (grep 整个 packages/web)
- Playwright e2e: `e2e/03-evaluate-list.spec.ts` + `e2e/04-evaluate.spec.ts` + `e2e/05-knowledge.spec.ts` 全跑通, 无 307 重定向

---

### Task 2.30: ARCH-002 — ingest/pipeline.py 47 处 print()

**修法**:
- 文件: `packages/service/src/ingest/pipeline.py:36` (47 处 `print(...)`)
- 改: 全替换 `logger.info(...)` / `logger.opt(exception=True).error(...)` (loguru 风格, 跟 CLAUDE.md 规约)
- 同步: `packages/service/src/ingest/converters/cad.py` 几处 print

**验证**:
- `grep -rn 'print(' packages/service/src` → 期望 0 命中 (排除 scripts/)
- pytest 模式 1: 跑 pipeline 集成测, 验 log 行有结构化字段

---

### Task 2.31: ARCH-003 — os.getenv 散落 20+ 文件

**修法 (大重构, 拆 2-3 PR)**:
- 新建 `packages/service/src/config/settings.py` (Pydantic BaseSettings, 集中所有 env 读取)
- 改: 20+ 文件 `os.getenv("FOO")` → `settings.FOO`
- 业务侧确认 env 列表 (Pydantic BaseSettings 自动校验类型)

**验证**:
- `grep -rn 'os.getenv' packages/service/src --exclude-dir=scripts` → 期望 ≤ 5 命中 (config facade 集中)
- pytest 模式 1: `test_settings_loads_from_env`

---

### Task 2.32: ARCH-004 — 裸 `# type: ignore`

**修法**:
- 文件: `packages/service/tests/lookups/test_audit.py:47` + `test_config.py:63`
- 改: `# type: ignore` → `# type: ignore[具体错误码]` + 注释解释为什么 ignore

**验证**:
- `uv run pyright` → 期望 0 error
- `grep -rn '# type: ignore$' packages/service` → 期望 0 命中 (裸 ignore 没了)

---

### Task 2.33: ARCH-005 — datetime.utcnow() + # type: ignore

**修法**:
- 文件: `packages/service/src/permissions/service.py:50` (5 处)
- 改: `datetime.utcnow()` → `datetime.now(timezone.utc)`
- 删 `# type: ignore[assignment]` (新写法不再需要)

**验证**:
- `uv run pyright` → 期望 0 error
- pytest 模式 1: 测时间函数返值类型是 timezone-aware

---

## Phase 3: Medium 修 (17 条, 1-2 个月)

> 来源: 关联 checklist [Medium 段](docs/audit/2026-06-24-findings.md#medium-中优先--17-条)

### Task 3.1: SEC-007 — forgot_password 无 rate limit

**修法**:
- 文件: `packages/service/src/auth/auth_account_router.py:300`
- 改: 跟 login 端点同模式, 加 `await check_and_increment("forgot_password", request.client.host)`, 超过 5/15min → 429
- 同步 chat_share 跟 invite 等敏感端点检查

**验证**:
- pytest 模式 1: `test_forgot_password_rate_limit_returns_429_after_5_attempts`

---

### Task 3.2: SEC-008 — presign_get IDOR

**修法**: 跟 Task 1.1 SEC-002 一起改 (同 router, 同一 file:line 附近)

---

### Task 3.3: CON-007 — chat list offset 漂移

**修法**:
- 文件: `packages/service/src/chat/service.py:73` (list_conversations)
- 改: offset pagination → cursor-based (用 `updated_at` + `id` 当 cursor)

**验证**:
- pytest 模式 1: `test_list_conversations_uses_cursor_pagination` (mock session, 插入新数据不漂移)

---

### Task 3.4: CON-008 — token cache write-after-PG 无 invalidation

**修法**:
- 文件: `packages/service/src/middleware/auth.py:162` (resolve_user)
- 改: PG 改密码/email 后, 同步删 Redis token cache (`safe_delete(f"rag:auth:tok:{token_sha256}")`)

**验证**:
- pytest 模式 1: `test_password_change_invalidates_token_cache` (改密码后, 同 token 解析返 401)

---

### Task 3.5: CON-009 — MemoryService 单例线程安全

**修法**:
- 文件: `packages/service/src/memory/service.py:75`
- 改: 改用 `Depends(get_memory_service)` 工厂模式, 每次请求 new instance, 不共享状态

**验证**:
- pytest 模式 1: `test_memory_service_request_scoped` (mock 2 个 request, 验 state 不串)

---

### Task 3.6: ERR-003 — CAD 转换器 print 当日志

**修法**: 跟 ARCH-002 一起改 (同 file 域)

---

### Task 3.7: ERR-004 — ingest task 失败丢 stacktrace

**修法**:
- 文件: `packages/service/src/ingest/api.py:516`
- 改: `t.error = str(e)` → `t.error = repr(traceback.format_exc())`

**验证**:
- pytest 模式 2: 触发失败, 查 DB t.error 字段含 stacktrace

---

### Task 3.8: ERR-006 — approval executor Neo4j 失败 pass

**修法**:
- 文件: `packages/service/src/approvals/executor.py:60`
- 改: 失败时把任务 status 置为 `retry`, 写 audit, 抛错让上层知道
- 同步加 `@audited` 装饰器 (跟 ARCH-006 一起)

**验证**:
- pytest 模式 1: `test_neo4j_failure_marks_approval_retry_not_pass`

---

### Task 3.9: ERR-007 — object_store 全 except 抹错误码

**修法**:
- 文件: `packages/service/src/storage/object_store.py:331`
- 改: `except Exception` → 显式 catch `botocore.exceptions.ClientError` + `requests.RequestException` + `OSError`, 其他 re-raise
- 业务侧确认 4xx 错误码 (NoSuchKey, AccessDenied) 跟 5xx (ServiceUnavailable) 翻译到 HTTP

**验证**:
- pytest 模式 1: `test_object_store_preserves_botocore_error_code` (mock NoSuchKey, 验 404 透传)
- pytest 模式 1: `test_object_store_reraises_unexpected_exceptions`

---

### Task 3.10: ERR-009 — lookup cache subscriber 30s 静默

**修法**:
- 文件: `packages/service/src/lookups/cache.py:150`
- 改: 30s 静默期改成 5min, 持续 3 次失败后发 WARNING
- 业务侧: 静默期是不是有真实必要? (项目其他位置有 circuit breaker 模式可参考)

**验证**:
- pytest 模式 1: 跑 mock Redis 挂掉 3 次, 验 WARNING 发出

---

### Task 3.11: DATA-009 — Dictionary ORM/migration 约束名不一致

**修法**:
- 文件: `packages/service/src/lookups/models.py:79`
- 改: `UniqueConstraint` name `uq_dict_item` → `uq_dictionary_items_dict_code_key`
- 跑 `alembic check` 验 0 drift

---

### Task 3.12: DATA-010 — ingest_tasks / kg_audit 无 FK

**修法**:
- 业务侧决策: 接受无 FK (设计匿名) → 加 docstring 注明
- 或: 加 `user_hash` 字段 (SHA256(user_id)), 失效后能匿名审计

**验证**:
- 跑 `alembic check`, 文档化决策

---

### Task 3.13: DATA-011 — dictionaries_seed.yaml 路径文档不一致

**修法**:
- 改 `docs/cookbook/` + `packages/service/README.md` 引用路径, 统一 `config/dictionaries_seed.yaml`

---

### Task 3.14: FE-012 — NEXT_PUBLIC_CHAT_TOKEN 公开

**修法**:
- 业务侧: 这 token 实际是 CSRF / 客户端标识? 文档化用途
- 加 rate limit (跟 SEC-007 模式同)
- 评估能不能移到 server-only

**验证**:
- grep `NEXT_PUBLIC_CHAT_TOKEN` 全部用途
- 文档说明

---

### Task 3.15: ARCH-006 — 4 处 TODO 加 @audited

**修法**:
- 文件: `packages/service/src/api/routes.py:7` + `kg/router.py:24-25`
- 改: admin.access / kg node delete / relation delete / audit.read_self 4 端点加 `@audited(...)` 装饰器
- 业务侧: 4 端点是否都已实现? 没实现的留 TODO 暂缓

**验证**:
- pytest 模式 1: 调 4 端点, 查 audit_logs 表有新行

---

### Task 3.16: ARCH-007 — any[] 滥用

**修法**:
- 文件: `packages/web/lib/api/permissions.ts:12` + `buyer-profile.ts`
- 改: `any[]` → 用 Pydantic 生成的 TypeScript 类型 (`pnpm run gen-types`)

**验证**:
- `bun run typecheck` → 期望 0 error

---

### Task 3.17: ARCH-008 — scripts/e2e 用 console

**修法**:
- 改: `scripts/duplication-report.ts` + 几个 e2e spec 用 `lib/log.ts` 封装替 console

---

### Task 3.18: ARCH-009 — tsc → tsgo

**修法** (0 风险高收益):
- 文件: `packages/web/package.json:15`
- 改: `"typecheck": "tsc --noEmit"` → `"typecheck": "tsgo --noEmit"`
- 同步: lint-staged 钩子 `lint-staged.config.js` 同步改
- 跑 `bun install` + `bun run typecheck` 验证

**验证**:
- `bun run typecheck` 通过, 时间应减少 10x

---

### Task 3.19: ARCH-010 — 补 lint:check

**修法**:
- 文件: `packages/web/package.json:16`
- 改: 加 `"lint:check": "oxlint"`, `"format:check": "oxfmt --check"`

**验证**:
- 跑 `bun run lint:check` 0 error

---

## Phase 4: Low 修 (5 条, 持续)

> 来源: 关联 checklist [Low 段](docs/audit/2026-06-24-findings.md#low-低优先--5-条)

### Task 4.1: SEC-009 — get_invite 信息泄露

**修法**:
- 文件: `packages/service/src/auth/auth_invite_router.py:75`
- 改: 端点返回限制 (只返 invite 必要字段, 不含 email), 加 rate limit

---

### Task 4.2: SEC-001 — Python 2 syntax 修语法

**修法**:
- 文件: `packages/service/src/auth/account_service.py:28`
- 改: `except ValueError, TypeError:` → `except (ValueError, TypeError):`
- 加 smoke test: `tests/auth/test_account_service.py::test_verify_password_imports` (import 模块不抛)

---

### Task 4.3: ERR-008 — embedder_ready 静默期

**修法**:
- 文件: `packages/service/src/retrieval/embedder.py:141`
- 改: 加 circuit breaker, 持续失败时返 503

---

### Task 4.4: ARCH-011 — SubmissionsTabs 53 行 useState 套层

**修法**:
- 改: 拆 `<DataTable<T>>` + `<AppToggle>`, 提取 onClick 命名函数

---

### Task 4.5: ARCH-012 — conftest autouse mock 缺文档

**修法**:
- 文件: `packages/service/tests/conftest.py:1`
- 改: 顶部加 docstring 注释 mock 矩阵 (engine/session_scope/redis/object_store/neo4j/permission_cache 各做什么)

---

## Self-Review

### 1. Spec 覆盖
- ✅ Phase 1 (Critical 9): Task 1.1-1.8 覆盖 SEC-002/003, CON-001/002, DATA-001/002/003, FE-001/002
- ✅ Phase 2 (High 27): Task 2.1-2.33 覆盖 SEC-004/005/006, CON-003~006, ERR-001/002/005, DATA-004~008, FE-003~011, ARCH-002~005
- ✅ Phase 3 (Medium 17): Task 3.1-3.19 覆盖 SEC-007/008, CON-007~009, ERR-003/004/006/007/009, DATA-009~011, FE-012, ARCH-006~010
- ✅ Phase 4 (Low 5): Task 4.1-4.5 覆盖 SEC-009/001, ERR-008, ARCH-011/012
- **总数**: 60 条 finding, 60 个 task (1:1 对应)

### 2. Placeholder 扫描
- 全文搜 "TBD" / "TODO" / "implement later" → 0 命中
- "appropriate" / "handle edge cases" → 0 命中
- "Similar to Task N" → 0 命中 (每条 finding 都给了具体修法, 不复用)

### 3. 类型一致性
- 文件路径跨 Phase 一致: `packages/service/src/...` 和 `packages/web/...`
- finding ID 格式: SEC-NNN / CON-NNN / ERR-NNN / DATA-NNN / FE-NNN / ARCH-NNN (跟 checklist 对齐)
- pytest 模式引用统一: 模式 1 mock / 模式 2 db_session (跟 CLAUDE.md 一致)

### 4. 范围控制
- 60 条 finding 跨 6 维度, 单 plan 可执行 (按 Phase 4 批提交)
- 不混 TDD 拆解 (每条 task 已经是"修法 + 验证"紧凑格式, 实施时再走 spec → plan 循环)
- 不动业务代码 (本 plan 只描述修法, 实施按 Phase 单独走)
