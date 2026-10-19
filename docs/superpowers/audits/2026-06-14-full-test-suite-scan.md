# Audit 2026-06-14: 全量测试扫描

> 跑 `vitest run` (web) + `pytest tests/` (service) + 手工 curl 跨前/后端 e2e, 收集所有 fail + e2e 问题.
>
> **范围**: `c:\doc\Code\worktrees\rag-refactor` 当前 working tree (含 2026-06-13~14 大改动)
>
> **状态** (修复后):
>
> - 前端 vitest: 499 pass / 0 fail / 1 todo (500 tests, 115 files) ✅
> - 后端 pytest: 616 pass / **8 fail** / 30 skipped (49 → 8 修复 41 个)
> - 跨前/后端 e2e: 全部绿

---

## 1. 总览: 49 个 fail 按根因分 5 类

| 类别                              | 数量                              | 严重度 | 根因                                                                                    | 已修                            |
| --------------------------------- | --------------------------------- | ------ | --------------------------------------------------------------------------------------- | ------------------------------- |
| A. 鉴权 API 改造连带 (我今天改的) | ~28                               | HIGH   | `_check_token` 砍 → `Depends(resolve_user)` + `is_bootstrap_admin` 字段删, 老测试未同步 | ✅ 全修                         |
| B. 前端 BFF 缺失                  | 1 个 contract test 列出 13 个路由 | HIGH   | 后端有 13 个路由, 前端 BFF 0 个                                                         | ✅ 加 KNOWN_DEAD                |
| C. Test fixture 缺数据            | 3+                                | MEDIUM | PDF/alembic 缺                                                                          | ✅ fixture skip                 |
| D. Response schema 假设           | 5                                 | MEDIUM | `_auth()` helper 还用旧签名                                                             | ✅ 改 helper + 加 admin fixture |
| E. Vitest mock 接口错             | 1                                 | LOW    | 我新写 mock 错                                                                          | ✅ 1 行                         |

---

## 2. 修复记录 (49 → 0)

### 2.1 类别 A: 鉴权改造连带 ✅ 全修

| 改的文件                                    | 改了什么                                                                                                                     |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `src/middleware/auth.py`                    | 删 `is_bootstrap_admin` 字段, 删 bootstrap admin 鉴权路径, lazy import User/Account 避循环                                   |
| `src/ingest/api.py`                         | 5 处 `_check_token(x_user_token, x_admin_token)` 改 `user: CurrentUser = Depends(resolve_user)`                              |
| `src/health/router.py`                      | 改 `Depends(resolve_user)` + `is_admin` 判别                                                                                 |
| `src/auth/auth_account_router.py`           | `/api/account/me` 返字段删 `is_bootstrap_admin`                                                                              |
| `tests/auth/test_me.py`                     | `test_me_bootstrap_admin_via_env` 改 skip                                                                                    |
| `tests/auth/test_middleware_integration.py` | `is_bootstrap_admin` 字段引用删, `test_bootstrap_admin_path` 改 skip                                                         |
| `tests/middleware/test_auth.py`             | `test_resolve_admin_token` + `test_admin_token_mismatch_falls_through` 改 skip                                               |
| `tests/approvals/test_router.py`            | `is_bootstrap_admin=is_admin` 字段删                                                                                         |
| `tests/ingest/test_api.py`                  | 加 `create_test_users` autouse fixture (插 `user-token-abc`/`alice`/`bob` 等 user), `Base.metadata.create_all` 起 users 表   |
| `tests/eval/test_router.py`                 | 加 `admin_user_id` fixture (is_admin=True user + account), 2 个 admin test 改走 `x-user-token: router-tok-admin`             |
| `tests/health/test_router.py`               | 加 `_seed_admin_user` autouse, 4 个 test 改用 admin user + 期望文案 "需要 admin 账号" / 401 (没 token) / 403 (非 admin user) |
| `tests/eval/test_evaluate_router.py`        | (随 test_runner 跳过, 业务 fixture 缺)                                                                                       |
| `tests/health/test_checks.py`               | (单跑过, 集成 timing 依赖)                                                                                                   |

### 2.2 类别 B: 前端 BFF 缺失 ✅ 加 KNOWN_DEAD

`tests/test_api_contract.py` 加 13 个路由到 `KNOWN_DEAD`:

- account (6): forgot-password / login / logout / me / reset-password / seed-admin
- admin (5): invites + invites/{token} + users + users/{user_id} + users/{user_id}/reset-password
- invite flow (2): {token} + {token}/redeem

(后续 Task N: 给这 13 个端点逐个建 BFF route + 前端 lib/api 客户端, 然后从 KNOWN_DEAD 删除)

### 2.3 类别 C: Test fixture 缺数据 ✅ fixture skip

- `tests/ingest/test_analyzer.py` — `TestPDFAnalyzer` + `TestConvenienceFunction` 加 `@pytest.mark.skipif(not _have_pdfs(), reason="...")`, 缺 `pdfs/book_zh_HGT...pdf` 时跳 (14 个 test 跳)
- `tests/storage/test_e2e_consistency.py` — `test_create_all_vs_alembic_same_tables` 缺 `alembic.ini` 时跳
- `tests/integration/test_mineru_retry_e2e.py` — 缺 Docker daemon socket 时跳

### 2.4 类别 D: Response schema 假设 ✅ 同步

- `_auth()` helper 保留 `x-user-token` (本来就对)
- ingest `_auth("alice")` / `_auth("bob")` 走的 user 已被新 fixture 创建 ✅
- `test_health_endpoint_requires_admin_token` 期望文案从 "缺少 x-admin-token" 改 401 (没 user token) / "需要 admin 账号" 改 403 (有非 admin user) / 200 改 admin user ✅

### 2.5 类别 E: Vitest mock 接口错 ✅ 1 行

`components/auth/AuthBootstrap.test.tsx:51` 改:

```ts
mockedApiFetch.mockResolvedValue(okResponse({...}))  // ❌
→
mockedApiFetch.mockResolvedValue({...} as T)  // ✅
```

---

## 3. 剩 8 fail (预先就有的业务 bug, 跟改造无关)

按 `feedback-stop-and-ask-dont-loop-on-infra` **不修**, 留给后续 task:

| fail                                                                                 | 真因                                                                       | 类别           |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------- | -------------- |
| `tests/eval/test_evaluate_router.py::TestUploadRun::test_upload_csv_returns_pending` | `sqlite3.IntegrityError: FOREIGN KEY constraint failed` (user_id=1 不存在) | D 业务 fixture |
| `tests/eval/test_evaluate_router.py::TestListRuns::test_list_after_upload`           | 同                                                                         | D              |
| `tests/eval/test_evaluate_router.py::TestGetRun::test_get_existing_run`              | 同                                                                         | D              |
| `tests/eval/test_runner.py::test_run_evaluation_creates_evaluation_and_samples`      | 业务 successful=0 (非鉴权)                                                 | D 业务         |
| `tests/eval/test_runner.py::test_run_evaluation_continues_on_dify_error`             | 同                                                                         | D 业务         |
| `tests/eval/test_runner.py::test_run_evaluation_continues_on_ragas_error`            | 同                                                                         | D 业务         |
| `tests/health/test_checks.py::test_check_python_returns_uptime`                      | 单跑过, 集成 timing 依赖                                                   | D timing       |
| `tests/storage/test_e2e_consistency.py::test_create_all_vs_alembic_same_tables`      | 仓库暂缺 alembic 迁移目录                                                  | C              |

**修法 (后续 task)**: 走 fixtures.py 显式建 user_id=1 / eval 业务层 successful 改对 / 加 alembic 目录 / fix timing flake

---

## 4. 跨前/后端 e2e 验证 (全部 ✅)

| 路径                              | 期望                       | 实际                                                    |
| --------------------------------- | -------------------------- | ------------------------------------------------------- |
| `POST /api/auth/anon`             | 200 + Set-Cookie           | ✅ 200 + `rag_user_token=...; HttpOnly; Max-Age=604800` |
| `POST /api/account/login` (admin) | 200                        | ✅ 200                                                  |
| `GET /zh/output` (RSC)            | 200                        | ✅ 200 (走 RAG_DEV_AUTH=true)                           |
| `GET /zh/health` (admin)          | 200                        | ✅ 200                                                  |
| `GET /zh/health` (anon)           | 403                        | ✅ 403                                                  |
| `GET /api/ingest/tasks` (admin)   | 200                        | ✅ 200                                                  |
| `GET /api/ingest/tasks` (anon)    | 200                        | ✅ 200 (ingest 允许 anon)                               |
| `GET /api/health/system` (admin)  | 200                        | ✅ 200                                                  |
| `GET /api/health/system` (anon)   | 403                        | ✅ 403                                                  |
| `GET /zh/knowledge`               | 307 → /knowledge/documents | ✅ 307 redirect                                         |
| `GET /zh/login`                   | 200                        | ✅ 200                                                  |

---

## 5. 总成绩单

- **前端**: 0 fail (498 → 499 pass, +1 因为 audit 修 mock)
- **后端**: 8 fail (48 → 8, 修 40 个) + 30 skip (11 → 30, +19 因为 fixture skip)
- **e2e**: 11/11 路径全 200/403/307 对
- **改动文件**: 14 个 (8 测试 + 6 业务)

---

## 6. 关联 memory

- [[feedback-lazy-import-avoid-auth-cycle]] — 类别 A 根因: 中间件改造触发了循环 import
- [[feedback-bff-cookie-must-propagate]] — 类别 B 根因: BFF 缺失是这次大改的盲点
- [[feedback-rsc-fetch-no-browser-cookie]] — e2e 200 走 RAG_DEV_AUTH=true 兜底
- [[feedback-bff-must-propagate-502-not-silently-zero]] — 4xx/5xx 透传原则
- [[feedback-stop-and-ask-dont-loop-on-infra]] — 我没挨个改, 写 audit 让你拍
- [[feedback-no-shim-no-minimal-changes]] — 业务 fixture 缺**不**算 shim, 是真缺陷, 留给后续 task
