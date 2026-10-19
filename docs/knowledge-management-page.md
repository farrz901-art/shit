# 知识库 + 知识图谱管理页 (/knowledge)

RAG 项目后台管理模块, 业务人员自助录入 QA/产品文档到 Dify, 工程师批量写三元组到 Neo4j。

## 5 个页面

| 路径                   | 用途                        | 写哪         |
| ---------------------- | --------------------------- | ------------ |
| `/knowledge`           | Dashboard 4 统计卡 + 4 入口 | -            |
| `/knowledge/qa`        | 录 QA 对                    | Dify         |
| `/knowledge/documents` | 上传 Excel/JSON             | Dify         |
| `/knowledge/triples`   | 录三元组                    | Neo4j        |
| `/knowledge/batch`     | 批量导入 (后台任务)         | Dify + Neo4j |

## 架构

```
Browser → /api/knowledge/* (Next.js BFF) → Dify Datasets API
                                          → FastAPI /api/kg/* → Neo4j
```

- 浏览器拿不到 Dify/Neo4j 凭据 (BFF 隔离)
- Stats 走 FastAPI, 不让 Next.js 直连 Neo4j

## 端到端流程 (录一条 QA)

1. 浏览器打开 `/knowledge/qa`
2. 选 dataset (顶 nav)
3. 填问题/答案 + 标签
4. 点 "录入 Dify" → `POST /api/knowledge/qa` → BFF → Dify createDocumentByText
5. 最近 20 条列表 SWR 1s 轮询 Dify 文档状态

## Schema 驱动

加节点/关系: 改 `configs/knowledge-schema.yaml` + `web/lib/schema-types.ts` 两处, 不改代码。

## BFF 端点 (10 个)

所有在 `web/app/api/knowledge/` 下, Next.js 透传到后端 `/api/kg/*` 或 Dify REST。

| 方法 | 路径                                | 后端                    | 用途                        |
| ---- | ----------------------------------- | ----------------------- | --------------------------- |
| GET  | `/api/knowledge/health`             | Dify                    | 健康点 (顶部 30s 轮询)      |
| GET  | `/api/knowledge/stats`              | `/api/kg/stats`         | Dashboard 4 统计卡          |
| GET  | `/api/knowledge/datasets`           | Dify                    | Dataset 下拉                |
| GET  | `/api/knowledge/schema`             | `/api/kg/schema`        | 节点/关系 schema (类型联动) |
| GET  | `/api/knowledge/qa`                 | Dify                    | 最近 20 条 (1s 轮询)        |
| POST | `/api/knowledge/qa`                 | Dify                    | 录 QA                       |
| POST | `/api/knowledge/qa/retrieve`        | Dify                    | Retriever 自测 Dialog       |
| GET  | `/api/knowledge/templates/{format}` | `/api/kg/templates/...` | 下载 Excel/JSON 模板        |
| POST | `/api/knowledge/documents/upload`   | Dify                    | 解析上传文件 (前端三步流程) |
| POST | `/api/knowledge/documents/commit`   | Dify                    | 提交解析结果                |
| POST | `/api/knowledge/batch`              | `/api/kg/batch`         | 批量任务 (后台)             |

## 已知 Bug 修复

| Bug                                 | 文件                                | 触发                                                    | 修复                                                |
| ----------------------------------- | ----------------------------------- | ------------------------------------------------------- | --------------------------------------------------- |
| BFF 502 时 `list.items.length` 崩页 | `web/app/knowledge/qa/page.tsx:186` | SWR 拉 `/api/knowledge/qa` 失败, `list.items` undefined | 加 `Array.isArray(list.items)` 守卫                 |
| Tailwind v4 样式 0 字节             | `web/postcss.config.mjs` 缺失       | dev 模式首页裸 HTML                                     | 补 `postcss.config.mjs` + `@tailwindcss/postcss` 包 |

详见 [web-e2e.md § 已修复的 Bug](web-e2e.md#已修复的-bug-e2e-发现)。

## 审核集成 (2026-06-13)

4 个写动作 (录 QA / 录三元组 / 批量导入 / 优化回答) 已改造为走 admin 审核:

- 提交后写 `approvals` 表 (`review_status=pending`, `apply_status=none`), **不直接** 调 Dify/Neo4j
- 提交者提交后跳 `/submissions` "我提交的" tab 看自己提交的状态
- admin 在同页 "全部待审" tab 展开看完整内容、批准/拒绝 (选 6 预设原因) / 重试
- 状态机 2 字段: `review_status` (admin 决定) + `apply_status` (系统写入)
- 详细见 [approval-system.md](approval-system.md) 跟 [spec](../superpowers/specs/2026-06-13-approval-system-design.md)
