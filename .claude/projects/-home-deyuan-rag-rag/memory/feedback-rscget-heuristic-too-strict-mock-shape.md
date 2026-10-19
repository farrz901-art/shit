---
name: feedback-rscget-heuristic-too-strict-mock-shape
description: "rscGet 启发式 + test mock 形态必须跟 Dify 真响应一致, 简化包装 (单 key) 跟真包装 (5 key) 是两个测试场景, 漏一个就藏 bug"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 298dc759-254d-43ee-a841-71ccb0b25682
---

# rscGet 启发式 + test mock 形态必须跟 Dify 真响应一致

**问题**: 2026-06-15 [dataset_id]/page.tsx 报 `datasets.find is not a function`.

**根因链** (按 [feedback-debug-distinguish-root-causes](feedback-debug-distinguish-root-causes.md)):
1. 后端 `/api/kg/datasets` 透传 Dify 真响应: `{ data: T[], has_more, limit, total, page }` — **5 个 key**
2. `rscGet` 启发式 `Object.keys(raw).length === 1` 假设了"简化包装", 5 key 漏拆 → 上游拿包装对象
3. `[dataset_id]/page.tsx` 直接 `apiFetch` (没走 rscGet), 也没拆 → `datasets.find is not a function`
4. `DatasetSwitcher.tsx` 已有 shim `(data as { data?: Dataset[] } \| undefined)?.data ?? []` 工作 (违反 [feedback-no-shim-no-minimal-changes](feedback-no-shim-no-minimal-changes.md))
5. **测试 mock 返裸数组** `[...]` — 让"上游拿数组"的假象坐实, 隐藏 1-4 全部问题

**修法**:
- 启发式改成 `Array.isArray(raw.data)`, 任何 key 数量都正确解包
- 加 TDD 测试覆盖**真包装** (5 key) — 不只是简化包装
- 所有 Dify list 端点的 test mock 改返真包装 `{ data, has_more, limit, total, page }`
- API 层 (e.g. `knowledgeApi.fetchDatasets`) 内部解包装, 调用方拿裸数组, 跟 `DifyDatasets.listDatasets` 风格一致

**Why**: Dify 文档 (https://docs.dify.ai/api-reference) 列的响应是 5 key 完整形态. 简化包装 `{ data: [] }` 只是**后端无 DIFY_API_KEY 时**的兜底 (看 packages/service/src/kg/router.py:142 `return {"data": []}`), 不是 Dify 实际响应.

**How to apply**:
- 任何 `rscGet` 解包装逻辑必须测**真包装形态**, 不能只看 `{ data: T }` 简化版
- 任何 mock Dify list 端点测试必须用 `{ data, has_more, limit, total, page }` 5 key 形态
- API 层 (e.g. `knowledgeApi.fetchDatasets`) 解包装应在 `apiFetch` 之后立即 `.then(r => r.data ?? [])`, 调用方零感知
- 看到 `(data as { data?: T[] } \| undefined)?.data ?? []` 这种 shim 立刻删, 修上游

**相关**: [[feedback-dify-api-returns-data-wrapper]] (同根, 但只覆盖 "Dify 返 `{ data: T[] }`" 的发现, 没覆盖 "简化 mock 隐藏 bug" 的二阶教训)
