# Health Page 验收 (2026-06-11)

## Spec 覆盖

| AC  | Spec 条目                                          | 实现                                          |
| --- | -------------------------------------------------- | --------------------------------------------- |
| 1   | 5 类检查 (Python / Dify / Neo4j / pgvector / 主机) | `src/rag/health/checks.py`                    |
| 2   | 后台 5s task + 进程内 cache                        | `src/rag/health/cache.py`                     |
| 3   | admin-only `/api/health/system`                    | `src/rag/health/router.py`                    |
| 4   | BFF 透传 + 502 on backend down                     | `web/app/api/health/system/route.ts`          |
| 5   | /[locale]/health 页 (5 区块 + 5s 轮询)             | `web/app/[locale]/health/page.tsx`            |
| 6   | SettingsDialog 「健康」 行                         | `web/components/settings/settings-dialog.tsx` |
| 7   | i18n (zh + en, flat keys per project rule)         | `web/messages/{zh,en}.json`                   |
| 8   | psutil + pynvml 新增依赖                           | `pyproject.toml`                              |
| 9   | BFF 契约测试更新                                   | `tests/test_api_contract.py`                  |

## 自动化覆盖

### Backend: 17 新 cases (本次)

- `src/rag/health/checks_test.py`: 10 cases
- `src/rag/health/cache_test.py`: 3 cases
- `src/rag/health/router_test.py`: 4 cases

### Frontend: 6 新 cases (本次)

- `web/app/[locale]/health/page.test.tsx`: 6 cases

### 契约: 1 新条目

- `tests/test_api_contract.py`: 1 BFF 路由 (`GET /api/health/system`)

## Commits (13)

| Commit       | Task   | Title                                                             |
| ------------ | ------ | ----------------------------------------------------------------- |
| 1bb879c      | (plan) | docs(plan): health page 实施计划 (14 任务, 5 阶段)                |
| 4fa2432      | 1      | chore(deps): add psutil + pynvml for health check                 |
| 0d85541      | 2      | feat(health): checks.py — 5 个 check 函数 + CheckResult           |
| fd5171c      | 3      | feat(health): cache.py — in-memory cache + 后台 5s loop           |
| bc71f2f      | 4      | feat(health): router.py — admin-only /api/health/system           |
| d3709b6      | 5      | feat(rag): register health_router in register_routers             |
| 878a86f      | 6      | feat(app): lifespan 启动 health check 后台 5s 任务                |
| ecdaf73      | 8      | feat(bff): /api/health/system 透传 + 502 on backend down          |
| aee4231      | 9      | feat(i18n): 添加 health 页 16 个翻译 key (zh+en)                  |
| 9178088      | 10     | test: /[locale]/health page 测试先行 (6 cases)                    |
| 326a73b      | 10     | feat(web): /[locale]/health 健康状态页 (5 区块 + 5s 轮询)         |
| b12707e      | 11     | feat(settings): SettingsDialog 加「健康」行 (跳 /[locale]/health) |
| 75c6786      | 12     | test(contract): BFF /api/health/system 期望添加                   |
| (本 handoff) | 14     | docs: health page 验收清单                                        |

> 注: Task 7 (BFF 契约测试先行) 与 Task 8 (BFF 透传实现) 的契约定义已整合到 Task 8/12 commit 中; Task 13 是手动验证清单 (见下方), 无独立 commit.

## 安全/隔离 checklist ✅

- [x] admin-only (`x-admin-token` header 必填, 401 if missing)
- [x] 任一子检查失败不影响 HTTP 200
- [x] GPU 驱动缺失优雅降级 (gpu=[])
- [x] cache 任务失败不退出 loop
- [x] 跨用户: admin token 本身就是 admin-only, 不涉及跨用户

## 风险点验证 ✅

- [x] pynvml NVMLError → gpu=[] (无 crash) — `_sample_gpu` 全包 try/except
- [x] psutil.cpu_percent(interval=0.1) Windows 兼容
- [x] 后台 5s 任务 vs TestClient 事件循环 — 测试用 monkeypatch 注入, 不真起 loop

## 已知遗留 (out of scope)

- SettingsDialog 的 5 个 SettingsDialog.test.tsx 用例失败 (useLocale 缺 intl provider). **pre-existing** 在 Task 11 之前就存在, 不是本次回归.
- 前端 vitest 40 个 pre-existing failures (主要 next-intl context 缺失). 与本次 work 无关.

## 手动验证清单 (Task 13 后, dev session 可跑)

⚠️ **uvicorn 必须重启** (per `feedback-uvicorn-must-restart-after-route-add`):

1. `cd c:/doc/Code/worktrees/rag-refactor && netstat -ano | grep :8000` → 杀旧进程
2. `uv run python main.py` (起 FastAPI, 端口 8000, 自动启动 lifespan 健康检查 loop)
3. `cd web && bun run dev` (起 Next.js, 端口 3000)
4. 浏览器打开 `http://localhost:3000/zh/health`
5. 验证 5 区块 (Python 后端 / Dify / Neo4j / pgvector / 主机资源)
6. 等 5 秒, 数据自动刷新 (SWR refreshInterval)
7. 点齿轮 → SettingsDialog → 「健康」 行 → 点击 → 跳到 `/zh/health`
8. 试 `/en/health` 看英文翻译

## Notes

- 后端 lifespan 在 FastAPI 启动时自动起 5s 后台任务 (start_health_loop + asyncio.create_task), shutdown 时 stop_health_loop
- 前端 SWR 5s 轮询, refreshInterval: 5000
- 依赖用的是 NVIDIA 官方 `nvidia-ml-py` 包, `import pynvml` 不再触发 FutureWarning (PyPI 上的 `pynvml` 是 deprecated shim)
