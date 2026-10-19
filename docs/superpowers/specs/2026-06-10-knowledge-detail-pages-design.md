# 知识库文档/数据集详情页设计

> 2026-06-10 · Brainstorming → Spec
> Status: 待用户 review

## 1. 目标

在 `/knowledge/documents` 入口页给 2 张 StatCard (文档数/数据集) 加点击跳转, 引到 2 个新独立详情页 (均为表格), 与 `/knowledge/graph` 入口页同构.

不在范围 (后续 spec):
- 主题系统 (Spec C)
- i18n (Spec D)
- 业务逻辑重构 / 文档字段扩展 (Dify v1 `/documents` 不返回 `created_at` 等)
- DataTable 封装 (Spec A 落地后, 这 2 页 + nodes/relations 共 4 页统一切 DataTable)

## 2. 路由 + 文件

| 路径 | 角色 | 现状 | 变化 |
|---|---|---|---|
| `/knowledge/documents` | 入口页 (统计+入口) | 已存在 | **最小改动**: 2 张 StatCard 包 `<Link>`, 其它不动 |
| `/knowledge/dataset-documents/[dataset_id]` | **新**: 某数据集下文档列表 | 不存在 | 新建表格页 |
| `/knowledge/datasets` | **新**: 数据集列表 | 不存在 | 新建表格页 |
| `/knowledge/dataset-documents/[dataset_id]` | 行点击进的二级页 | 同上 | 用 path segment 不用 querystring (跟 nodes/relations 一致) |

## 3. 页面 1: `/knowledge/datasets` (数据集列表)

```
[KnowledgeHero eyebrow="Datasets" title="数据集" meta="共 N 个"]
[Stagger] 副标题
[Reveal]
  表格 (复用 nodes/relations 模板):
    - 名称 (id 截短 8 字符)
    - 描述 (截断 1 行)
    - 文档数 (num)
    - 字数 (num)
    - 跳转 (Link → /knowledge/dataset-documents/[id])
    - sticky header / motion.tr 进场 / hover:bg-muted/50
    - 分页 20/页 (client-side)
```

**API**: `GET /api/kg/datasets` (经 `knowledgeApi.fetchDatasets`)
**类型扩展**: 改 `fetchDatasets` 返回类型为 `Dataset & {description?, document_count?, word_count?}` (Dify 全字段已透传, 仅前端类型补齐)

## 4. 页面 2: `/knowledge/dataset-documents/[dataset_id]` (某数据集下文档)

```
[KnowledgeHero eyebrow="Documents" title="<dataset_name>" meta="共 N 条"]
  actions slot: <BackButton fallbackHref="/knowledge/datasets" />
[Stagger] 副标题: "dataset: <name>"
[Reveal]
  表格 (复用 nodes/relations 模板):
    - 文档 ID/name (Link 跳转)
    - 状态 (Badge: indexing_status)
    - 错误 (仅 error 时显示)
    - 块预览 (前 100 字 question)
    - sticky / 进场 / hover / 分页
```

**API**: `GET /api/kg/qa?dataset_id=<id>` (经 `knowledgeApi.fetchQADocuments`)
**类型**: 现有 `QAListResponse` (已是 QA-as-Document)

## 5. `/knowledge/documents` 入口页最小改动

```diff
- <StatCard label="文档数" value={stats.dify.documents} accent="indigo" />
- <StatCard label="数据集"  value={stats.dify.datasets}  accent="ochre" />
+ {datasetId
+   ? <Link href={`/knowledge/dataset-documents/${datasetId}`} className="contents">
+       <StatCard label="文档数" value={stats.dify.documents} accent="indigo" />
+     </Link>
+   : <StatCard label="文档数" value={stats.dify.documents} accent="indigo"
+       hint="请先选 dataset →" />}
+ <Link href="/knowledge/datasets" className="contents">
+   <StatCard label="数据集"  value={stats.dify.datasets}  accent="ochre" />
+ </Link>
```

**约束**:
- 入口页其它结构 (EntryCard 录 QA 对 / 批量导入) 不动
- `datasetId` 从 `useAppStore` 拿 (`web/lib/store/app-store.ts:12-49`), 缺则 disable 文档数卡 + 提示文字
- 数据集数卡始终可点 (不依赖 datasetId)

## 6. Tabs / ActiveSwitch 改动

**KnowledgeTabs** (`web/components/knowledge/KnowledgeTabs.tsx:18-22`): "向量库" tab 的 `children` 数组加 2 个新路径:
- `/knowledge/datasets`
- `/knowledge/dataset-documents`

**ActiveSwitch** (`web/components/knowledge/ActiveSwitch.tsx`): **不改** — `/knowledge/datasets` 不在现有分支列表, 走默认 `DatasetSwitcher` (✓ 语义对); `/knowledge/dataset-documents/...` 已经在 `/knowledge/documents` 分支里 (用 `pathname.startsWith`), 自动走 `DatasetSwitcher` (✓ 语义对)

## 7. 复用模板 (来自 `nodes/page.tsx:38-176`)

- 容器: `rounded-lg border border-border/40` + `overflow-auto`
- sticky header: `sticky top-0 z-10 bg-muted/80 backdrop-blur-sm`
- 表头: `eyebrow` + Tailwind 宽度
- 数字列: `num text-muted-foreground`
- 行: `motion.tr initial/animate delay i*0.02`
- hover: `hover:bg-muted/50`
- 空态/loading: `colSpan={N} h-24 text-center text-muted-foreground`
- 分页: 20/页 client-side + Previous/Next + "第 X / Y 页 · 共 N 条"

## 8. 测试

- `web/app/knowledge/datasets/page.test.tsx`: 渲染空 / 渲染 N 行 / 列 render / 分页 / 行点击跳 / sticky / 空态 / loading
- `web/app/knowledge/dataset-documents/[dataset_id]/page.test.tsx`: 同样模式 + 路径参数 / BackButton 行为 / 错误态
- `web/app/knowledge/documents/page.test.tsx`: 追加断言: 文档数卡可点跳 / datasetId 缺失时不可点 / 数据集数卡可点 / EntryCard 不变
- E2E `web/e2e/05-knowledge-routes.spec.ts`: 追加: 点文档数 → 到 dataset-documents 页 / 点数据集数 → 到 datasets 页

## 9. 风险

- **Dify Document 字段缺**: 无 `created_at` / `size` / `type`, 表格列只能放 `name / status / error / preview`
- **`fetchDatasets` 返回类型仅 `{id, name}`**: 需扩为 `Dataset & {description?, document_count?, word_count?}` — 前向兼容 (现有 DatasetSwitcher 只用 id/name, 不破坏)
- **datasetId 缺失**: 入口页 hint "请先选 dataset →", 文档数卡不可点 (仍显示数字, 不报错)

## 10. TDD 任务列表 (11 任务)

1. 扩 `fetchDatasets` 返回类型 (Dataset 全字段)
2. `web/app/knowledge/datasets/page.tsx` 测试先行 (vitest)
3. `web/app/knowledge/datasets/page.tsx` 实现
4. `web/app/knowledge/dataset-documents/[dataset_id]/page.tsx` 测试先行
5. `web/app/knowledge/dataset-documents/[dataset_id]/page.tsx` 实现
6. `web/app/knowledge/documents/page.tsx` 入口页 StatCard 包 Link + datasetId 缺失兜底
7. `web/app/knowledge/documents/page.test.tsx` 加跳转断言
8. `KnowledgeTabs.tsx` children 数组加 2 个新路径
9. E2E 加 2 个新 tab 跳转用例
10. 回归全 vitest + typecheck + lint
11. 手动验证 4 页串通 (graph → documents → datasets → dataset-documents)
