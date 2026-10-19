---
name: ui-state-baseline-2026-06-10
description: "web/ UI 现状基线 — shadcn 18 已装, 4 真表 + 4 假表 + 4 Dialog 风格不一"
metadata: 
  node_type: memory
  type: project
  originSessionId: e231d327-c644-4a6c-949e-d3f999036ee1
---

**2026-06-10 web/ UI 现状** (探索结果, 决策输入):

- **shadcn 已装 18 组件** (`web/components/ui/`): alert, alert-dialog, badge, button, card, collapsible, dialog, dropdown-menu, input, pagination, progress, scroll-area, select, skeleton, sonner, table, tabs, textarea
- **未装**: sheet, popover, tooltip, command, calendar, data-table, form, radio-group, switch, checkbox, separator, avatar
- **4 处真 `<table>`**: nodes/relations (shadcn Table + sticky + 分页) / import (手写 + sticky) / triples (手写 + sticky + 行内编辑) / SampleTable (shadcn Table + sticky, 无分页)
- **3 处 grid 假表**: evaluate/page.tsx (grid 12) / output/page.tsx (grid 2) / output/[task_id] (flex)
- **4 处 Dialog** + **1 处 AlertDialog** — 0 手写弹窗
- **0 处 Popover/Tooltip/Drawer** — 缺失
- **9 处手写 `motion.button`** (该走 shadcn Button): evaluate/page.tsx, output/page.tsx, output/new/page.tsx, batch/page.tsx, qa/page.tsx, triples/page.tsx, decode/page.tsx
- **多手写 Badge**: `StatusBadge` (raw span), `HealthDot` (raw span)
- **业务组件目录**: `web/components/knowledge/`, `chat/`, `evaluate/` — 业务专用, Spec A 不动

**Why:** Spec A 决策事实, 替换清单数据源
**How to apply:** Spec A 替换时直接对照此清单, 见 `docs/superpowers/specs/2026-06-10-ui-component-library-design.md`
