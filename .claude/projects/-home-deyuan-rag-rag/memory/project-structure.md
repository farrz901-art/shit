---
name: project-structure
description: "项目结构、工具链、规范速查 (单仓单包, bun, TDD, 中文)"
metadata: 
  node_type: memory
  type: project
  originSessionId: e231d327-c644-4a6c-949e-d3f999036ee1
---

- 单仓单包: 根 `c:\doc\Code\worktrees\rag-refactor\`, 前端在 `web/`, 后端 Python 在 `src/`
- 包管理: **bun** (用 `bun.lock`, 不用 npm/pnpm/yarn)
- 前端栈: Next.js 16.2 (App Router) + React 19.2 + Tailwind v4.3 (`@tailwindcss/postcss`, 无 tailwind.config.ts, 配置全在 `app/globals.css` 的 `@theme inline`) + shadcn/ui (default + slate, cssVariables=true) + TypeScript 8 + vitest 4 + jsdom + Playwright
- 后端栈: Python + FastAPI + uv
- 测试命令: `cd web && bun run test` (vitest) / `bun run test:e2e` (Playwright) / `bun run typecheck` (tsgo) / `bun run lint` (oxlint) / `bun run format` (oxfmt)
- 工作流: pre-commit → tsgo → vitest → format:check
- 业务页 100% 在 `app/`, 业务组件在 `components/{knowledge,chat,evaluate}/`, shadcn 原生在 `components/ui/`
- 业务知识库 API: `web/lib/api/knowledge.ts` (经 BFF 透传后端)

**Why:** 项目级配置事实, 跨 spec 通用, 跟 coding 规范相关
**How to apply:** 改代码前查工具链, 别用 npm/pnpm, 别用 jest, 别建 tailwind.config.ts
