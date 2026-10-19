---
name: feedback-rsc-throw-must-not-crash-page
description: "RSC/server component 里 throw 必须被 try/catch 兜住, 不能让 fetch 失败直接挂整页 500"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

RSC / server component / server action / route handler 任何位置 throw (apiFetch / prefetchQuery / rscGet / 任何 fetch wrapper), 都会导致整页 500 让用户看不到导航/header/footer/其他模块. 用户原话: "以后不要出现 throw 报错，导致页面直接挂掉的写法".

**Why:** 2026-06-14 用户报 `GET /zh/output 500`, stack 落在 `lib/api/config.ts:54 throw new NetworkError(...)`. 根因是 RSC `prefetchQuery` 失败抛错, Next dev overlay 把整页 500 渲染, 整站 navigation/header 都不可见. **修法不是 try 让它不出错, 是 try/catch 兜住, 留 fallback 让页面继续 render + 弹错提示**. 修后: RSC prefetch 失败 → 整页 200, 客户端 useQuery 看到 cache miss 重拉, 重拉失败由 `QueryCache.onError` 弹 sonner toast. layout 也需要 mount `<Toaster>` 全局可见 (sonner 库里 Toaster 是入口, 命名上像 shadcn 旧版本但 sonner 库本身没废弃).

**How to apply:**
- 任何 RSC/server component/server action 调外部 API 时, **外面必须有 try/catch**, 失败时返 fallback (空数组/空对象/null) + 写 console.warn 留痕, 不抛
- 客户端错误处理: 集中到 `lib/api/query-client.ts` 的 `QueryCache.onError` → `toast.error(errorMessage)`, 不要再让每个 useQuery 调用方自己 try/catch
- `<Toaster>` 必须挂到 root layout (next-intl provider 内), 否则 toast 不显示
- 错误类 (`ApiError` / `NetworkError`) 在 `lib/api/errors.ts`, toast 取 `.message`
- 新加 RSC prefetch 失败兜底测试: `await expect(Page()).resolves.toBeDefined()` (不再 `rejects.toThrow`)
- 关联 [[feedback-debug-distinguish-root-causes]] (500 是症状, 真因是 RSC throw 没兜)
- 关联 [[feedback-bff-must-propagate-502-not-silently-zero]] (类似: 不能用兜底掩盖错误, 但要用户能看见)
- 关联 [[feedback-fix-root-cause-not-remove-feature]] (不能为不挂而删功能, 改成"挂时给提示")
