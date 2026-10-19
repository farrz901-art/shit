---
name: feedback-cache-py-rewarm-after-invalidate
description: "permissions.cache._page_metadata_cache invalidate 后必须立即 rewarm, 否则 sync 读 miss 走 fallback 9 项 (2026-07-03 nav orphan 真实事故)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 412b9e1e-f8ac-42e0-90a2-3a8dec1cdc85
---

`src/permissions/cache.py` 的 `_page_metadata_cache` (跟 `_page_keys_cache` 一对) 是**进程内 L1 cache**, 由 `warmup_page_keys()` 启动时填. 旧实现 `invalidate_page_keys_cache()` 只把 cache 变量设 None, **不等同**重填. 下次 sync 读走 `get_all_page_metadata_sync()` miss → 返 `_PAGE_METADATA_FALLBACK` (硬编 9 项, 没 admin_* / 没 is_group / 没 icon). 结果前端 `/api/permissions/me` 拿到 9 项, buildNavTree 6 个 admin_* 全部 orphan, 浏览器报 nav 异常.

**Why:** 2026-07-03 实测. 重启后端 → warmup 填满 16 项完整数据 → PATCH 改 admin item 触发 `LookupService.patch_item` 调 `lookup_cache.invalidate` (Redis L2 dict cache) + 我手动加的 `invalidate_page_keys_cache` (清进程内 L1). 之后 `get_all_page_metadata_sync` miss → fallback 9 项, 不是从 DB 重建. DB 跟 API 不一致, 但 PATCH 已经 invalidate 了 Redis L2 → 进程内 L1 是唯一 stale 层. 

**How to apply:**
1. **任何写字典 item 的入口** (admin_router.patch_item / delete_item / create_dict) 必须**两步调**: `invalidate_page_keys_cache()` 清 L1 + `await rewarm_page_keys_cache()` 立即重建
2. `rewarm_page_keys_cache()` 是 async 函数 (admin_router 在 async 上下文, 不能 `asyncio.run`); 走 `await get_all_page_keys()` + `await get_all_page_metadata()` 重填
3. **测试 mock 必须 100%**: 老测试 `test_fallback_keys_when_not_warmed` 假设 `invalidate → 返 fallback`, 我加了 rewarm 后**没改 contract** (invalidate 仍只清不填, rewarm 是新函数), 老测试不变. 但**没 rewarm 路径上的回归测试** (PATCH 完立刻 GET 应该拿新数据) — 后续要补
4. **fallback 9 项 = legacy R1 兼容期**, 业务只有 8 个 page_key 时用. 现在 16+ 项, fallback 永远不准. 治本是删 fallback, 但 mock 测试要重写, 留给后续 cleanup
5. **千万别改 `get_all_page_metadata_sync` miss 时直接连 DB 重建** (会破 mock, 而且同步 SQLAlchemy session 路径会跟事务冲突). 永远走 rewarm 异步入口

**关联**:
- [[feedback-no-shim-no-minimal-changes]] — fallback 9 项本身就是 shim
- [[feedback-test-must-be-100pct-mock-no-real-db]] — 不能在 sync 路径连真 DB
- [[feedback-uvicorn-must-restart-after-route-add]] — 加新 endpoint 后 uvicorn 不 reload, 必须 restart
- [[feedback-postgres-json-jsonb-family-of-bugs]] — JSONB 一族 bug 的姊妹篇: 进程内 cache 一族 bug

**修法 commit 摘要** (2026-07-03):
- `src/permissions/cache.py`: 加 `rewarm_page_keys_cache()` async 函数
- `src/lookups/admin_router.py`: 3 处写字典入口加 `invalidate_page_keys_cache() + await rewarm_page_keys_cache()` (create_dict / patch_item / delete_item)
