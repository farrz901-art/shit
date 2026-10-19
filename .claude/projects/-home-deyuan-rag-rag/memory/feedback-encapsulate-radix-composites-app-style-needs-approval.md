---
name: feedback-encapsulate-radix-composites-app-style-needs-approval
description: "复合 shadcn/Radix 原语必须仿 antd 抽 AppXxx 包装, 但封装前必须用户明确同意"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 86274fe2-84a3-46fd-9e5b-6248c9a64260
---

凡是组合 ≥3 个 shadcn/Radix 原语 (例 Tooltip + TooltipTrigger + TooltipContent + TooltipProvider) 或业务出现 ≥2 次的复合组件, 都要仿 antd 风格抽 1 个 `<AppXxx>` 放 `web/components/common/`. 业务代码不许直接拼 4-5 个 Radix 原语.

**根因**: 根 layout 没装 Provider, 业务手写易漏 (例 health-service-card.tsx 第一次写 Tooltip 就缺 TooltipProvider → 测试 2 failed). 抽包装强制统一, 同时业务层 1 行调用.

**流程 (2026-06-18 用户强制)**:
1. 提方案: 包装名 + 接受的 props + 跟 antd 对应组件的对照
2. **封装前必须先跟用户确认**, 等用户明确同意才动手
3. 完成后同步更新 `packages/web/CLAUDE.md` "新封装" 段 + 加测试 + i18n (如有文案)

**Why**: 防止 agent 自行决定 "这个也封装一下" 范围升级, 改用户没要求的代码.

**How to apply**:
- 看到 `Tooltip / Popover / DropdownMenu / Select / Dialog` 等等 Radix 多原语组合 → 提方案给用户, 不直接写
- 用户同意后才动, 走 [[feedback-no-shim-no-minimal-changes]] 原则, 抽干净不打折
- 写进 [[project-rag-shim-audit-2026-06-08]] 前先看是否已有半封装可加固
