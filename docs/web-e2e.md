# Web E2E 测试 (Playwright)

5 个管理页面的端到端冒烟 + 关键功能流程。配套 vitest 做组件/单测, 共同保证前端质量。

## 跑 E2E

```bash
# 一次性装浏览器 (180MB, 已下完)
bunx playwright install chromium

# 跑全部 (自动起 next dev + 后端 uvicorn)
bun run test:e2e

# 调试模式 (UI + 浏览器可见)
bun run test:e2e:ui
```

**无需手动启后端** — `web/scripts/e2e-up.sh` 在 Playwright 跑测试前**并行起 2 个进程**:
- `next dev` (端口 3000, 默认)
- `uvicorn src.product_decoders.app:app` (端口 8000, 用 venv python 避开 uv path 规范化 bug)

复用已有进程 (`reuseExistingServer: true`), 二次跑秒级。

## 覆盖范围

`web/e2e/` 4 个 spec 文件, 18 用例:

| Spec | 用例 | 覆盖 |
|---|---|---|
| `00-smoke.spec.ts` | 8 | 5 页面冒烟: nav + Tailwind 工具类 + 关键元素 + 截图 |
| `01-decode.spec.ts` | 2 | 型号解码: 提交 1LE0001 → 表格 OR 降级; 空输入禁用 |
| `02-knowledge.spec.ts` | 6 | Dashboard 入口; QA 表单 + 提交; Triples 加载态; Documents; Batch |
| `03-output.spec.ts` | 2 | Output 列表; 有文件时打开详情 |

**17 passed / 1 skipped / 0 failed** (17s)。

## 设计决策

### 1. 截图都进 `web/.e2e-logs/`

不是 Playwright 默认的 `test-results/`, 因为:
- 仓库 gitignore 已含 `.e2e-logs/` (放截图)
- 失败重试的 trace/screenshot 仍走 `test-results/` (Playwright 默认)

### 2. 后端缺时页面不挂

部分用例依赖 Dify / Neo4j, 测环境未必都起。设计原则:
- 页面挂 5xx → 显示降级 UI (错误条 / 空状态) → **测试通过**
- 提交 Dify 失败 → 红条 + 报错文字 → **测试通过**

如果想"必须真后端", 把 `.or(errBlock)` 改成单一 `.or(table)` 即可。

### 3. 用 venv python 不用 uv run

Windows 上 `uv run uvicorn ...` 报 `uv trampoline failed to canonicalize script path`
(worktree 路径有非 ASCII)。直接用 `.venv/Scripts/python.exe` 绕过。

### 4. SHA-256 截图去重

`web/e2e/00-smoke.spec.ts` 跑过的页面都截图, E2E diff 时直接看图比日志快。

## 已修复的 Bug (E2E 发现)

### Tailwind v4 样式 0 字节

**症状**: dev 模式首页裸 HTML, 无圆角无布局。

**根因**: Tailwind v4 仍需 `postcss.config.mjs` + `@tailwindcss/postcss` 包,
**漏了**, next.js PostCSS 没插件 → `@import "tailwindcss"` 不被处理 → 浏览器拿到的 CSS 0 字节。

**官方指南** (我们查过, 2026-06): <https://tailwindcss.com/docs/installation/framework-guides/nextjs>
- `npm install tailwindcss @tailwindcss/postcss postcss`
- `postcss.config.mjs` 配 `@tailwindcss/postcss`
- `app/globals.css` 第一行 `@import "tailwindcss";`

**修复**:
- `web/postcss.config.mjs` 新建
- `web/package.json` devDependencies 加 `@tailwindcss/postcss` + `postcss`
- `web/CLAUDE.md` 修过期说明 (原写"v4 不再需要 postcss.config", 错的)

**验证**: dev 起来后 `/_next/static/chunks/app_globals_*.css` 46KB, 含 `--tw-translate-x` 等 v4 变量。

### QA 页 BFF 502 时崩溃

**症状**: `Cannot read properties of undefined (reading 'length')` → ErrorBoundary 接管 → 整个页面挂了。

**根因**: `web/app/knowledge/qa/page.tsx:186` 直接 `list.items.length` 守卫, BFF 502 时返 `{detail: ...}` 无 items 字段。

**修复**:
```diff
-{list && list.items.length > 0 && (
+{list && Array.isArray(list.items) && list.items.length > 0 && (
```

## CI 接入 (未来)

- 浏览器二进制不入库, CI 跑 `bunx playwright install --with-deps chromium`
- 用 GitHub Actions 缓存 `~/.cache/ms-playwright` (~180MB)
- 后端用 `uv sync` 装好即可, 不需要 Dify/Neo4j 实例 (E2E 容忍降级)
