---
name: six-specs-breakdown
description: 6 个原始需求 → 5 个 spec 的拆分决策
metadata: 
  node_type: memory
  type: project
  originSessionId: e231d327-c644-4a6c-949e-d3f999036ee1
---

**2026-06-10 用户原始 6 需求拆分**:

| 原需求 | 对应 Spec | 状态 |
|---|---|---|
| 1. 封装 shadcn 表格 (分页/高度/固定表头) | A: UI 组件库封装 | ✅ design doc committed (d53fc6b) |
| 2. 封装 shadcn 弹框 (title/content/footer 插槽) | A | ✅ 同上 (A 包含弹框 + Form) |
| 3. 检查未用 shadcn 组件的 | A 末尾审计报告 + 顺手换 9 处 button | ✅ 同上 (含在 A 里) |
| 4. 主题配置文件 + 白天/夜间 + 扩展 | C: 主题系统 | ⏳ 探索完成, 准备 brainstorming |
| 5. i18n 国际化 | D: i18n | ⏸️ 暂未开始 |
| 6. /knowledge/documents 模仿 /graph 节点/关系数 | E: 知识库详情页 | ✅ design doc committed (aadfd32) |

**Spec B 单独化决策**: 原需求 #3 "检查未用 shadcn" = 一份审计报告, 收口到 A 末尾 + 顺手换 9 处 button, 不单独成 spec

**用户选型决策** (2026-06-10):
- 目录分层: `ui/` (shadcn 原生) + `common/` (本次封装) + 业务目录 (不动)
- Form 完整封装 (仿 antd), 用插槽支持任意受控组件 + Zod
- Spec A 不引 tanstack/react-table
- 入口页轻量: /documents 只 StatCard 包 Link, 业务页其它不动
- datasetId 缺失时, 文档数卡不可点, 提示"请先选 dataset"

**Why:** 跨 spec 决策记录
**How to apply:** 后续 spec 参考此决策
