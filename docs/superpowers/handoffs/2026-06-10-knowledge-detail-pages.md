# Knowledge Detail Pages 验收 (2026-06-10)

## Spec 覆盖

| AC  | Spec 条目                                    | 实现                                                        |
| --- | -------------------------------------------- | ----------------------------------------------------------- |
| 1   | /knowledge/datasets 数据集列表               | `web/app/knowledge/datasets/page.tsx`                       |
| 2   | /knowledge/dataset-documents/[id] 文档列表   | `web/app/knowledge/dataset-documents/[dataset_id]/page.tsx` |
| 3   | /documents 入口页 StatCard 可点跳            | `web/app/knowledge/documents/page.tsx`                      |
| 4   | datasetId 缺失兜底 (hint="请先选 dataset →") | 同上                                                        |
| 5   | KnowledgeTabs 高亮新路径                     | `web/components/knowledge/KnowledgeTabs.tsx`                |
| 6   | E2E 跳转测试                                 | `web/e2e/05-knowledge-routes.spec.ts`                       |
| 7   | pytest 7+ vitest 30+                         | 15 新 vitest tests                                          |

## 自动化覆盖

### Backend: 0 changes

本次纯前端工作，后端 API 复用现有的 `/api/kg/datasets` 和 `/api/kg/qa?dataset_id=...`。

### Frontend vitest: 15 新 cases (本次)

- `lib/api/knowledge.test.ts`: 1 case (DatasetRow 全字段)
- `app/knowledge/datasets/page.test.tsx`: 7 cases
- `app/knowledge/dataset-documents/[dataset_id]/page.test.tsx`: 7 cases
- `app/knowledge/documents/page.test.tsx`: +4 cases (现有 3 + 4 新)

合计: 15 新 vitest cases 全绿.

### E2E: 2 新 cases (本次)

`web/e2e/05-knowledge-routes.spec.ts` +2 个跳转用例 (待 backend 跑)。

### Typecheck

3 个 Plan 1 Form 残留错误 (已知, Plan 2 不引入新错误)。

## Plan vs Implementation 偏差 (1 个)

| Task | 偏差                                                | 修复                       |
| ---- | --------------------------------------------------- | -------------------------- |
| 3    | 空态测试用 sync `getByText` 而非 async `findByText` | 改 `findByText` (SWR 异步) |

## Commits (9)

| Commit    | Task | Title                                                                           |
| --------- | ---- | ------------------------------------------------------------------------------- |
| `aaf4889` | 1    | feat(api): extend fetchDatasets 返回类型 (DatasetRow 全字段)                    |
| `38e1eb1` | 2    | test: /knowledge/datasets page 测试先行 (7 cases)                               |
| `42a3c07` | 3    | feat(web): /knowledge/datasets 数据集列表页 (table + sticky + 分页)             |
| `0545f81` | 4    | test: /knowledge/dataset-documents/[dataset_id] page 测试先行 (7 cases)         |
| `d8c858d` | 5    | feat(web): /knowledge/dataset-documents/[id] 文档列表页 (table + sticky + 分页) |
| `38caa2a` | 6    | feat(web): /documents 入口页 StatCard 包 Link + datasetId 缺失兜底              |
| `7a4c8e9` | 7    | test: /documents 入口页加 StatCard 跳转断言 (4 cases)                           |
| `97c8e07` | 8    | feat(web): KnowledgeTabs 向量库 tab 加 datasets / dataset-documents 子路径      |
| `57e5133` | 9    | test(e2e): 05-knowledge-routes 加 datasets / dataset-documents 跳转用例         |

## 安全/隔离 checklist ✅

- [x] 跨用户: 不涉及 (只读用户 dataset 列表, 跟现有 nodes/relations 一致)
- [x] 路径校验: `useParams<{dataset_id}>` 拿字符串, 后端 `/api/kg/qa?dataset_id=...` 校验
- [x] 路由: 路径前缀 (跟 nodes/relations 一致), KnowledgeTabs 包含新路径

## 手动验证清单 (Task 11 后, dev session 可跑)

1. `cd web && bun run dev` (起 Next dev server)
2. `uv run python -m src.product_decoders.app` (起 FastAPI, 端口 8000)
3. 浏览器打开 `http://localhost:3000/knowledge/documents`
4. 验证 2 张 StatCard (文档数 + 数据集)
5. 点 "数据集" 卡 → 跳到 `/knowledge/datasets` → 看到数据集表格
6. 点某行数据集名 → 跳到 `/knowledge/dataset-documents/:id` → 看到文档表格
7. 点 BackButton → 回到 `/knowledge/datasets`
8. 点浏览器后退 → 回到 `/knowledge/documents`
9. 点 "文档数" 卡 → 跳到当前选中 dataset 的文档列表
10. 验证 KnowledgeTabs "向量库" 在 datasets / dataset-documents 页高亮

## Notes

- 本 spec 依赖 Plan 1 的 `DataTable` 组件作为参考模式 (本 spec 仍用 shadcn 原生 Table, 与 nodes/relations 模板一致)
- Dify Document 字段缺 (无 created_at / size / type), 表格列只能放 name / status / preview
- 旧 `output/[file]/page.tsx` 不动 (跟本次无关)
