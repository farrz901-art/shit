# web/ 前端局部约定

## 包管理

- 用 `bun`（不用 npm/pnpm/yarn）
- 装包：`bun install`
- 装包后 `bun.lock` 自动生成, 入库

## 代码规范

### 必须严格遵守eslint和oxlint代码规范

- 不要在return jsx里面写大量表达式，或者数组，或者数组里面有大量表达式，这样没有可读性
- 禁止在 JSX 里写声明函数（行内 `onClick={() => {}}`）、复杂语句或过长表达式，一律提取为命名函数或变量放在组件体内
- 使用函数表达式声明和箭头函数声明函数，禁止用function声明
- 禁止使用单个字符当变量，用val替代v，用idx替代i
- 禁止使用魔法数字，用常量替代，可以在const中定义常用常量
- import 必须按首字母排序
- 改动文件时必须同时修复IDE提示的警告和报错

### 优先使用已安装的库和框架新特性

- 优先使用react19，nextjs16新特性开发，有更好的写法就不要用老写法
- 优先使用tanstack query，zustand，react-use，es-toolkit，date-fns等已经装好的库来实现功能，而不是什么都自己实现
- 优先使用已经封装的组件和函数实现功能，然后是shadcn或其它工具

### 函数和代码封装

- 重复出现的组件和函数必须封装，优先封装成hooks函数，纯函数，组件
- 一个jsx里面如果需要多个组件，优先拆成多个文件

### 函数式编程

- 优先使用箭头函数，禁止使用function生命函数，除非是class，不然禁止使用this
- 优先使用纯函数
- 禁止在 JSX 中写除了三元表达式或 map 等基础语句之外的复杂表达式（如 switch、if/else 块等），必须提取为命名函数或变量
- 禁止使用立即执行函数（IIFE），优先声明一个命名函数，然后执行取值

### 接口封装

- BBF接口放在`app/api`下，其它接口放在`lib/api`下，优先使用BBF实现，前端页面隐藏接口调用

### react组件封装

- 优先使用RSC，然后是普通react组件
- 优先使用shadcn封装，实现不了就自己实现
- 封装的组件要符合样式规定，并且接入主题系统
- 尽量美观，有设计感，有质感，有动画，有交互效果

## 工具链 (替代 ESLint + Prettier + tsc)

- **类型检查**：`tsc --noEmit` (项目用 typescript 6, 见 [package.json:typecheck](package.json))
  ```bash
  bun run typecheck    # = tsc --noEmit
  ```
- **Lint**：`oxlint` (Rust 写的, 极快)
  ```bash
  bun run lint         # 检查
  bun run lint:fix     # 自动修
  ```
- **Format**：`oxfmt` (跟 Prettier 兼容)
  ```bash
  bun run format         # 写
  bun run format:check   # 只检查
  ```
- **Pre-commit**：`husky` + `lint-staged`
  ```bash
  .husky/pre-commit  # 跑 lint-staged → tsc → vitest → format:check
  ```

## 跑测试

```bash
bun run test         # 一次性跑 vitest (jsdom)
bun run test:watch   # watch 模式
bun run test:e2e     # 跑 Playwright E2E (自动起 next dev + 后端)
bun run test:e2e:ui  # E2E UI 模式 (浏览器可见)
```

**注意**：`bun test` 是 bun 自带 runner, 不读 `vitest.config.ts`, 不会用 jsdom 环境. 跑 vitest 测试要用 `bun run test` (= `vitest run`).

**E2E** 用 Playwright, 18 用例覆盖 5 页面冒烟 + 型号解码 + knowledge 4 Tab, 详见 [../docs/web-e2e.md](../docs/web-e2e.md)。

## 跑 dev server

```bash
bun run dev           # localhost:3000
```

**dev 模式要开两个终端**：

1. 后端：`uv run python main.py` (localhost:8000)
2. 前端：`cd web && bun run dev` (localhost:3000)

CORS 已在后端配好（`http://localhost:3000`）。

## TDD 流程

- 单元测试文件跟实现文件同目录, 后缀 `.test.ts` / `.test.tsx` (vitest + jsdom)
- E2E 测试放 `web/e2e/`, 后缀 `.spec.ts` (playwright + chromium)
- 先红后绿, commit 用 `test:` / `feat:` 前缀
- **commit 前 husky 会自动跑 lint/typecheck/test**, 不用手动跑全套
- vitest 别名: 配了 `@/` → `./` (在 `vitest.config.ts`)

## 样式约定

- Tailwind v4 + shadcn/ui (Default + Slate)
- 不用 CSS modules, 不用 styled-components
- 组合类用 `cn()` from `@/lib/utils`
- Tailwind v4 仍需 `postcss.config.mjs` + `@tailwindcss/postcss` 包 (Next.js 框架指南要求)
- 官方指南: <https://tailwindcss.com/docs/installation/framework-guides/nextjs>
  - 漏配 → dev/build 不报错, 但 `app_globals_*.css` 0 字节 → 页面裸 HTML

## 封装组件 (2026-06-14)

项目已封装 + 新封装, 一律优先使用, 不许手写对应模板.

### 已有封装 (7)

- `<AppDialog>` (shadcn Dialog 包装) — 弹框, 替手写 `fixed inset-0 bg-black/50`
- `<AppConfirm>` (shadcn AlertDialog 包装) — 危险操作二次确认, 替 `window.confirm()`
- `<AppDrawer>` (shadcn Sheet 包装) — 抽屉, 业务暂无用
- `<Form>` + `<FormItem>` (项目自有, Zod) — 表单 + 字段, 替 `<form onSubmit>` 模板
- `<FileDropzone>` (react-dropzone 包装) — 文件拖拽, 替手写 `<label>` + `<input type="file">`
- `<DataTable<T>>` (shadcn Table 包装) — 表格, 替手写 `<table>/<thead>/<tr>/<th>/<td>`
- `<DataEmpty>` (shadcn Empty 包装) — 空态, 替 "暂无数据" 文本

### Markdown 渲染 (2026-06-30 streamdown 迁移)

- 统一走 `components/markdown/`,禁止直接 import `streamdown` 或 `react-markdown`
- 流式 (chat): `<MarkdownStream onPreview={...}>{answer}</MarkdownStream>`
- 静态 (output): `<MarkdownStatic>{content}</MarkdownStatic>`
- 思考折叠: `<ThinkBlock testId="think-toggle">{thinking}</ThinkBlock>`
- `parseThinkTag` 在 `assistant-body.tsx` 内部完成, 业务代码不需要手动拆
- 删了 `react-markdown` 依赖, 启用了 streamdown 内置 GFM + Shiki

### Chat AI SDK 协议层 (2026-07-01 简化)

- **chat 协议层用 `TextDecoderStream` + `parseSseBlocks` (AI SDK 7)**, 不用手写 `TextDecoder` 字节解码
- `lib/chat/sse.ts` 只做 `\n\n` 切块, 不做字节解码、不做 JSON 解析 — 字节解码委托上游 `ReadableStream.pipeThrough(new TextDecoderStream())`
- BFF SSE 写入 (`app/api/chat/messages/route.ts`) 用 AI SDK `JsonToSseTransformStream` 替手写 `TextEncoder` + `data: ${JSON}\n\n` + `[DONE]` (AI SDK 在 `flush()` 自动 append `[DONE]`, 不要自己加)
- `lib/chat/openai.ts` 复用 `parseSseBlocks`, 不要自己写 `reader.read() + TextDecoder + buf` 循环
- Dify 双块 SSE 归一化 (6 种事件 + `seenMessageRef` 双发射防御 + `createParseBlock`) 在 `lib/chat/chat-event-decoder.ts`, 新增 provider 不需要关心 Dify 私有协议
- 新增 LLM provider 时: byte→text 层用 `ReadableStream.pipeThrough(new TextDecoderStream())`, 之后 `for await (const block of parseSseBlocks(textStream, signal))` — 0 行 SSE 字节解析
- 删了 `parseSseStream` (JSON 解析由消费方自行处理), 删了 `openai.ts` 重复的 reader/decoder/buffer (~61 行)
- **TS 类型注意**: `pipeThrough(new TextDecoderStream())` 在项目 lib 下要 `as unknown as ReadableWritablePair<string, Uint8Array>` cast (TS DOM lib 类型 mismatch), 这是项目既定模式, 不要去掉

### Chat 状态管理 (2026-07-01 Phase 2)

- **chat 用 AI SDK useChat + 自实现 DifyHttpChatTransport**, 不用 useChatShellState 手写状态
- `useChatWithPersistence` hook 是入口: 注入 transport + 持久化 callback + Chat 实例 keying by convId
- Chat 实例构造时传 `transport` 参数 (`new Chat({ id, messages, transport })`), 只传 useChat({ chat }) 不够 (依赖 transport 实例)
- `DifyHttpChatTransport` 把 Dify ChatEvent SSE (6 types) 转成 UIMessageChunk 5 段配对 (text-start/delta/end + reasoning-start/delta/end + finish/error)
- `prepareSendMessagesRequest` 注入 user (accountId / anon uuid) + inputs.buyer_key + query + conversationId
- `ui-message-adapter.ts` 做 IDB flat Message ↔ UIMessage ↔ ServerMessage 转换 (3 函数, metadata 走 ChatMessageMetadata)
- 已删: useChatShellState 大半 / applyEvent / processStream / handleStreamError / setupAbortController / dispatchSendStream

### 表格组件 (2026-06-14)

**所有表格必须用 `<DataTable<T>>`** (`@/components/common/table/data-table`), 禁止直接用 shadcn `<Table>` 拼 markup.

- **API**: `dataSource` + `columns: ColumnDef<T>[]` + `rowKey` + `pagination` (受控/非受控) + `emptyText` (string 或 ReactNode) + `loading` + `onRowClick` + `rowClassName` + `expandedRowRender`
- **能力已覆盖**: 列渲染 (含 `render(row, i)` 函数), 本地分页, sticky 表头, 行 stagger 动画, loading, 空态
- **空态**: 优先 `<DataEmpty icon title description variant />` (来自 `@/components/common/display/app-data-empty`), 跟 shadcn `Empty` 套件配套. 纯文本可只传 `title` (图标可省)
- **外层包装**: PageHero / BackLink / Reveal 等页面级组件, 放在 DataTable **外面** (DataTable 不应感知页面级 header)
- **不许做的事**:
  - 手写 `<Table>` / `<TableHeader>` / `<TableBody>` / `<TableRow>` / `<TableCell>` / `<TableHead>` (4 文件已全清: DatasetsTable / DatasetDocumentsTable / NodesTable / RelationsTable 走 DataTable)
  - 手写 `<Pagination>` + `useState(page)` (DataTable 内建, 重复就是 6a93b06 那种 "重复模式被吸 7 页" 的反面)
  - 在 DataTable 内部再嵌一层 `<Reveal>` 或 stagger wrapper (DataTable 自带 motion 行入场)
- **新增表格时**: 1) 列定义放组件内 (t() hook 限制) 2) `rowKey` 选唯一字段 3) 空态传 `<DataEmpty>` 4) 测试用 `screen.getAllByTestId("data-table-row")` 断言
- **关联**: [[feedback-no-shim-no-minimal-changes]] (重复 markup = 隐藏技术债)

### `lib/date` (2026-07-07 Temporal wrapper)

替代 `date-fns` + 原生 `Date` 的统一 API. date-fns 4.x 风格签名 (differenceInDays, addDays, formatDate 等),
内部用 TC39 Temporal via `@js-temporal/polyfill`. 所有业务时间计算 / 格式化走这里, 禁止直接用 `Date.now()` / `new Date()` / `Date.parse()` / `Intl.DateTimeFormat`.

- **API**: `toInstant` / `nowInstant` / `nowMs` / `nowIso` / `differenceIn*` / `add*` / `isAfter|Before|Equal` / `formatDate|DateTime` / `fmtRelativeTime` / `formatRelativeTime` / `formatDurationMs` / `formatElapsedMs`
- **输入类型**: `DateInput = string | number | Date | Temporal.Instant`, 业务调用零改动
- **测试**: `lib/date.test.ts` 覆盖所有 export (vitest, 不 mock polyfill)
- **依赖**: `@js-temporal/polyfill` (~25KB gzip)

### 新封装 (7, 2026-07-07)

- `<AppSelect>` (antd 风格, options + value + onChange 一行) — 替 shadcn Select 6-行模板
- `<AppToggle>` (shadcn ToggleGroup 单选) — 替手写 button 按钮组 (例 decode view 切换)
- `<AppRadioGroup>` (antd 风格, options + value + onChange + renderLabel 复合, 2026-07-07) — 替 shadcn RadioGroup + RadioGroupItem 模板 (Root + Item × N), 适合"带 Tooltip/描述/图标的单选"场景 (例 pre-analysis 表格提取器), 默认横向并排
- `<ErrorBanner>` (shadcn Alert 包装, 5 variant) — 替 `<div className="border-destructive/30 bg-destructive/5 ...">` (16 处统一)
- `<CopyButton>` (clipboard + 1.5s 反馈) — 替 `navigator.clipboard.writeText` (4 处统一)
- `<FormField>` (FormItem 升级, Label + 错误展示) — 4 表单模板用
- `<AppTooltip>` (shadcn Tooltip 4 子件包装, 1 行 content + children) — 替 Provider/Root/Trigger/Content 4-行模板, 根 layout 没装 Provider 易漏, 强制统一 (2026-06-18 health badge 教训)

### 反模式 (禁止手写)

- `<input type="text|email|password|number">` → shadcn `<Input>` 或 `<FormField>` 包装
- shadcn `<Select>` 6-行模板 → `<AppSelect>` (antd 风格 1 行)
- `<input type="checkbox">` / shadcn `<Switch>` / shadcn `<Textarea>` 直用 (跟 `<AppSelect>` 价值不同, 1 行就够, 不抽包装)
- shadcn `<RadioGroup>` + `<RadioGroupItem>` 模板 → `<AppRadioGroup>` (antd 风格 options + value + onChange + renderLabel)
- `<table>/<thead>/<tbody>/<tr>/<th>/<td>` → `<DataTable<T>>`
- `<div className="fixed inset-0 z-50 bg-black/50">` (Dialog 遮罩) → `<AppDialog>`
- `<form onSubmit>` → `<Form>` (项目自有 + Zod)
- `<input type="file">` 包在 `<label>` → `<FileDropzone>`
- `<div className="border-destructive/30 bg-destructive/5 ...">` (错误条) → `<ErrorBanner>`
- `navigator.clipboard.writeText` → `<CopyButton>`
- `window.confirm(...)` → `<AppConfirm>`
- 手写 button 按钮组 (例 decode view 切换) → `<AppToggle>`
- 复合 shadcn 模板 (Tooltip + TooltipTrigger + TooltipContent + TooltipProvider 等) 都要仿 antd 风格抽 1 个 `<AppXxx>` 包装, 不许业务代码直接拼 4-5 个 Radix 原语 (根 layout 没装 Provider, 业务手写易漏, 抽包装强制统一)

### 封装新组件流程 (2026-06-18 强制)

凡是"组合 ≥3 个 shadcn/Radix 原语"或"业务出现 ≥2 次"都要考虑封装成 `<AppXxx>` 放 `components/common/`. **封装前必须先跟用户确认**:

1. 提方案: 包装名 + 接受的 props + 跟 antd 对应组件的对照
2. 等用户明确同意才动手
3. 完成后: 同步更新本文件 "新封装" 段 + 加测试 + i18n (如有文案)

### 新增表格 / 表单 / 弹框 / 状态提示 时

1. 表格 → `<DataTable<T>>` + `<DataEmpty>` 空态
2. 表单 → `<Form>` + `<FormField>` 包装每字段, shadcn Input/Checkbox/Textarea 内嵌
3. 弹框 → `<AppDialog>` (二次确认 → `<AppConfirm>`)
4. 错误 → `<ErrorBanner>` (success/warning/destructive 走对应 variant)
5. 复制 → `<CopyButton>`
6. 状态切换按钮组 → `<AppToggle>`

## 主题系统 (Theme)

- **自实现 ThemeProvider** (不依赖 next-themes: 0.4.6 一年没更新, React 19 报警, 详见 [[feedback-next-themes-dead-use-self-implement]])
- 主题配置: `web/lib/theme/themes.ts` (light/dark + set of CSS variables)
- ThemeProvider: `web/components/theme-provider.tsx` (包在 root layout, FOUC script 走 useEffect 注入)
- 主题切换 UI: 齿轮按钮 (`ThemeToggle`) → SettingsDialog
- 状态色: 用 `bg-status-{success|warning|error|running}/10` 替代 `bg-{emerald|amber|rose|blue}-100`
- 新增色 token: `--color-status-*`, `--color-ochre`, `--color-indigo`
- 文档: <https://tailwindcss.com/docs/installation/framework-guides/nextjs>

## 国际化 (i18n)

- 用 next-intl 4.x + App Router
- 路径前缀: `/zh/...` `/en/...` (URL 强制带)
- 消息文件: `web/messages/zh.json` + `en.json` (扁平 key=value, 中文作 key)
- **核心约定**: `t("中文")` 中间直接用中文作 key (zh.json identity, en.json 翻译)
  - 原因: grep 中文直接定位所有引用点, 不维护 namespace 树
  - 反例: 禁止 `t("knowledge.nodes.title")` 这种 dotted namespace
  - **省略号字符统一 (2026-06-18)**: zh.json 写中文 `…` (U+2026, 1 字符), en.json value 写英文 `...` (ASCII 3 个点). 反例: en value 混 Unicode `…` 跟中文不统一. 实施: 加新状态文本 (e.g. `t("加载中…")`) 同步 zh/en.json 时, zh 写 `…`, en 写 `...`
  - **dev 模式改 messages/\*.json 不 HMR (2026-06-18 教训)**: next-intl cache 翻译, 报 `IntlError: MISSING_MESSAGE` 时**不是代码 bug**, 先 `Ctrl+C` 停 `bun run dev` + 重新 `bun run dev` + 浏览器 hard refresh (`Ctrl+Shift+R`), 详见 [[feedback-next-intl-dev-messages-cache]]. 跟 [[feedback-turbopack-postcss-panic-10054]] 同模式 (dev infra 抓不到某些改动, 重启即好)
- 翻译工具: `useTranslations()` (client) / `getTranslations()` (server)
- Provider 嵌套: ThemeProvider 外, I18nProvider 内 (都在 layout.tsx)
- 链接加前缀: 用 `<LocalizedLink href="/foo">` 替代 `<Link>` (来自 `@/components/i18n/LocalizedLink`)
- 切换 UI: SettingsDialog 语言行 (zh/en 下拉, router.push + cookie 持久化)
- 测试 wrapper: `IntlWrapper locale="zh|en"` 来自 `@/lib/test-utils/intl-wrapper`
- 路由配置: `web/i18n/routing.ts` (locales, defaultLocale, localePrefix)
- Server config: `web/i18n/request.ts` (getRequestConfig 加载 messages)

### ⚠️ 路由跳转必须用 next-intl 的 useRouter (2026-06-17 强制)

**`useRouter` 只能从 `@/i18n/navigation` import**（项目内 `createNavigation(routing)` 封装），**禁止**直接从 `next/navigation` 引，**也禁止**直接引 `next-intl/navigation`（4.x 改了 API，模块里没 `useRouter` 直接导出，必须走 createNavigation 包装）。

```typescript
// ✅ 正确 — 项目内统一封装, 自动加 /<locale> 前缀, 1 跳直达
import { useRouter, Link, redirect, usePathname, getPathname } from "@/i18n/navigation";
const router = useRouter();
router.push("/admin/users"); // → /zh/admin/users

// ❌ 错误 — 不带 locale, 被 intlMiddleware 307 重定向, 用户感觉"没反应"
import { useRouter } from "next/navigation";
router.push("/admin/users"); // → 307 → /zh/admin/users, 多一跳 + 多一次服务端 roundtrip

// ❌ 错误 — next-intl 4.x 不再直接导出 useRouter, 编译报 "Export useRouter doesn't exist in target module"
import { useRouter } from "next-intl/navigation";
```

**封装位置**: `i18n/navigation.ts` — `createNavigation(routing)` 解构出 `Link/redirect/usePathname/useRouter/getPathname` 集中导出。所有新组件必须从这个本地模块引。

**真实 bug 案例 (2026-06-17)**: `/zh/login` 登录成功调 `router.push("/")`, 因用 `next/navigation` 的 useRouter, 跳到 `/` 被 middleware 307 重定向到 `/zh`. 用户看到"页面刷新一下"以为登录失败, 实际已经登录成功.

**Note**: `useSearchParams` 仍然从 `next/navigation` 引（next-intl 不重新导出这个 hook）。

**回归保护**: `app/[locale]/login/page.test.tsx` 有 import guard 测试, 禁止 `useRouter` 从 `next/navigation` 引, 且断言必须从 `@/i18n/navigation` 引. 其它 5 个文件 (EvaluateListView / EvaluateNewForm / TriplesForm / RunDetailView / invite/[token]) 当前未报 bug, **不主动改**, 等谁报再按同模式修.

### **改动时 i18n 同步检查 (2026-06-14)**

每次新加功能 / 改 UI 文案 / 提交 commit 前, **必须** 同步:

1. **新文案**: 所有 `t("...")` 字符串先在 `messages/zh.json` 加 (中文作 key, value=同样中文), 再在 `messages/en.json` 加同 key 英文翻译
2. **删除文案**: 删 zh.json 跟 en.json 里的 key (避免脏数据)
3. **批量校验**: `node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"` 验 JSON 合法
4. **漏改典型**: t("新建任务") 用了但 zh.json 没注册 → not-found.tsx MISSING_MESSAGE 报错就属这类
5. **commit 必带**: 改 UI 文案 commit message 提 "i18n: add 改文案" 或 "refactor: XXX (i18n sync)"

**Why**: 之前 Sprint shadcn 改 UI + t("...") 加新文案, 漏同步 messages/{zh,en}.json → not-found.tsx 报 MISSING_MESSAGE 错 (用户 2026-06-14 反馈过 1 次).
**How to apply**: 任何 commit 改 .tsx / .ts 文件包含 t("...") 字符串时, commit 前 git diff 看 t() 新增 key, 同步加 messages/{zh,en}.json.

- 跳过项: 详见 `docs/todo/i18n-deferred-tasks.md` (locale-aware fmtDate, ConversationList formatRelativeTime, animated CountUp)
- 官方文档: <https://next-intl.dev/docs/getting-started/app-router/with-i18n-routing>

## 聊天历史存储约定 (2026-06-19 chat spec)

### anon → IDB, 登录 → 服务端, 登录后 IDB 清空 (A 策略)

跟 ChatGPT/Claude/Gemini/Poe/Perplexity 5 标杆 100% 一致. **不**做 anon → 登录自动合并.

```typescript
// 业务代码不要直调 lib/chat/db.ts 或 localStorage
// 走 facade 包装
import { loadConversations, saveMessages } from "@/lib/chat/storage"; // anon: IDB
// 或
import { useConversations, useDeleteConversation } from "@/lib/chat/api"; // 登录: REST
```

### 6 个核心函数 / 6 个 hook

<<<<<<< Updated upstream

=======

> > > > > > > Stashed changes
> > > > > > > | Use case | 函数 / Hook | 数据源 |
> > > > > > > | ----------- | ------------------------- | ------------------------------------------ |
> > > > > > > | 列表 (anon) | `loadConversations()` | IndexedDB via Dexie |
> > > > > > > | 列表 (登录) | `useConversations()` | TanStack Query → /api/chat/conversations |
> > > > > > > | 详情 (anon) | `loadMessages(convId)` | IndexedDB |
> > > > > > > | 详情 (登录) | `useConversation(id)` | /api/chat/conversations/{id} |
> > > > > > > | 创建 | `useCreateConversation()` | /api/chat/conversations POST |
> > > > > > > | 删除 | `useDeleteConversation()` | /api/chat/conversations/{id} DELETE (软删) |

### 迁移触发: ChatShell mount 时

```typescript
import { performAnonToLoginMigration } from "@/lib/chat/migration";

useEffect(() => {
  if (isAccount) {
    performAnonToLoginMigration(t);
  }
}, [isAccount]);
```

弹 shadcn Sonner toast: 2 按钮 (下载 JSON 备份 / 知道了) → 不论哪个都 `clearLocalChat()`.

### Key 规范

- Dexie 表名 `rag-chat`, version 1
- 字段名跟 types.Conversation / types.Message 对齐 (id / title / content / conversationId)
- owner 字段: `"anon" | "imported"`, 留好未来 C/D 模式扩展

### 永不阻塞 + 软删 30d

服务端软删 (`DELETE /api/chat/conversations/{id}`) → `deleted_at = NOW()` → cron 每天 03:05 跑 30d hard-delete (GDPR).

### i18n (zh + en)

10 个新增字符串: toast 文案 + 操作按钮, 全部用 `t("中文 key")` (跟项目 i18n 约定一致).

### 测试模式 (跟 4 模式一致)

- 模式 1 (mock): vitest + fake-indexeddb, 测 Dexie CRUD
- 模式 1 (mock): vitest mock apiFetch, 测 TanStack Query hooks
- 模式 4 (E2E): Playwright (待 CI 配真账号, 本期 1 个跑通 + 3 skip)

## JSDoc 注释规约 (2026-07-05 沉淀)

**所有 export 函数 / interface / const 必须有 JSDoc 块** (test/stories/components/ui 豁免).

```ts
/**
 * 中文动词开头描述 (做什么)
 * @param name  参数说明
 * @returns     返回值说明
 *
 * 调用边界 (3 选 1):
 *   - @server-only   RSC / Server Action / route.ts
 *   - @client-bff    前端调 BFF
 *   - @shared        前后端通用 (纯函数)
 */
export const foo = ...
```

**interface 必须有 @property**:

```ts
/**
 * 用户信息
 * @property id 用户 ID
 * @property name 用户名
 */
export interface User {
  id: number;
  name: string;
}
```

**非 export 函数/常量也必须补** (如 `loginApiCall`, `setLoginCookie` 等内部函数).

**禁止**:

- 空壳 `/** */`
- 重复类型名的单行 `/** 登录状态 */`
- 缺 `@param` (有参数时)
- 缺 `@returns` (有返回值时)
- 不改不删已有注释

参考范例:

- [lib/hooks/use-polling.ts:5-9](packages/web/lib/hooks/use-polling.ts#L5-L9) — 简洁单行 + @param
- [lib/api/permissions.ts:1-15](packages/web/lib/api/permissions.ts#L1-L15) — calling-boundary 段落

扫描: `bun run check:jsdoc` (覆盖率) / `bun run check:jsdoc:report` (仅报告).

**Why**: 907 个 export 缺文档导致新人 onboarding 慢 + AI 上下文缺失 (2026-07-05 全量加固经验).
**How to apply**: 新加 export 必须带 JSDoc 块, PR review 把这条当 lint 级别校验.

## 文档地址

- ant-design：https://ant-design.antgroup.com/components/modal-cn 用于参考组件封装设计
- shadcn：https://ui.shadcn.com/docs/components shadcn组件
- dify api文档 https://docs.dify.ai/api-reference
- ahooks react hooks文档 https://ahooks.js.org/zh-CN/hooks/use-request/index
- better-auth文档 https://better-auth.com/docs/authentication/email-password
- bunjs文档 https://bun.com/docs
- nextjs文档 https://nextjs.org/docs
- es-toolkit文档 https://es-toolkit.dev/intro.html
- oxlint规范 https://oxc.rs/docs/guide/usage/linter/rules.html
- ai sdk 文档 https://ai-sdk.dev/docs/introduction

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in node_modules/next/dist/docs/ before writing any code. Heed deprecation notices.

## 代码质量清理总结 (2026-06-19 code-quality spec)

### oxfmt / oxlint / tsgo 起始 vs 结束

| 工具             | 起始 (master 07bda92)                     | 结束 (P5)     | 减幅                      |
| ---------------- | ----------------------------------------- | ------------- | ------------------------- |
| oxfmt --write    | 0 files reformatted                       | 0 reformatted | - (前端已经是 oxfmt 格式) |
| oxlint --fix     | 16 files fixed (no-nested-ternary 加括号) | 16 fixed      | -16 (P1)                  |
| tsgo (typecheck) | 0 errors                                  | 0 errors      | 0 (前端无 TS 类型错)      |

注: oxlint 仍报 3412 warning (id-length / no-magic-numbers / sort-imports / func-style 等风格规约), 0 自动修复. 这些是项目 lint 配置 strict 但风格类, 不在本期范围, 留给后续 spec 单独处理 (`packages/web/.oxlintrc.json` 调整 / 逐文件修).

### vitest 起始 vs 结束

| 指标       | 起始 (P0 前)         | 结束 (P5)                  | 减幅                                                                 |
| ---------- | -------------------- | -------------------------- | -------------------------------------------------------------------- |
| Test Files | 156                  | **156**                    | 0                                                                    |
| Tests      | 705 passed + 14 fail | **719 passed**             | +14                                                                  |
| Failed     | 14                   | **0** (+2 修, +8 deferred) | -14 (修了 4 个测试文件) + 2 (删了 2 个死回归, 2026-06-27 `7a1439c2`) |

> **2026-06-27 update**: baseline 加到 721 passed + 8 fail。修了的 14+2=16 fail 中, 6 个在原 spec 内修, 2 个是 [2026-06-27 plan](docs/superpowers/plans/2026-06-27-pre-existing-test-failures.md) Task 2 (删 SettingsDialog 死回归). 剩 8 fail (R1: 5 + R3: 3) deferred 到后续 spec — 根因 next-intl 4.x 内部 `import("next/navigation")` 走 Node ESM loader 绕开 Vite resolver, R3 是 RSC fetch mock 失效. 详见 plan 文件.

修了的 4 个文件:

| Test File                                           | 修复内容                                                                                                               |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `messages/__tests__/i18n.test.ts`                   | `zh.json` 'N 个用户正在使用' 改 identity (去 `{N}` 占位符), 加 '权限不足' / '请联系 super_admin 申请访问权限' 2 个 key |
| `components/common/dialog/app-dialog.test.tsx`      | icon 顺序断言改用 `firstChild` (jsdom compareDocumentPosition mask 行为差异)                                           |
| `components/chat/memory-management-dialog.test.tsx` | lucide-react mock 改 `importOriginal` 模式 (DialogContent 用 X 关闭按钮 icon, 缺 X 导致 8 个 test fail)                |
| `lib/chat/memory-integration.test.ts`               | 全文重写 - 实现已重构成 server-only (fetch + cookies()), test 改 mock global fetch + next/headers cookies()            |

### vitest coverage 起始覆盖率 (2026-06-19 baseline)

| 维度       | 起始                   | 目标 (后续 spec) |
| ---------- | ---------------------- | ---------------- |
| Statements | **66.52%** (2969/4463) | ≥ 75%            |
| Branches   | **56.76%** (1510/2660) | ≥ 65%            |
| Functions  | **65.79%** (858/1304)  | ≥ 80%            |
| Lines      | **66.75%** (2893/4334) | ≥ 75%            |

跑法: `bun run test:coverage`. coverage provider 用 v8, 报告在 `coverage/index.html`.

注: vitest config 因 coverage instrumentation 变慢, 默认 5s timeout 不够 RSC 测试, 已加 `testTimeout: 15000`.

### 本轮发现 top-12 防再犯守则

1. **oxfmt / oxlint / tsgo 必须 0 error 才 commit**. husky pre-commit 钩子会自动跑, 不要 `--no-verify` 绕过 (除非本期这种纯格式化批量改).
2. **优先用项目封装** (DataTable / AppDialog / AppConfirm / ErrorBanner / CopyButton / AppTooltip / Form / FormField). 见项目「封装组件」段.
3. **JSX 不写行内 onClick 复杂表达式**. 必须提取命名函数放在组件体内.
4. **函数声明用 const = () =>**, 禁止 `function foo() {}` (项目规约), 除非是 React 组件 default export.
5. **变量名禁止单字符** (val 替代 v, idx 替代 i).
6. **禁止魔法数字**, 用 const 定义常用常量 (e.g. `const DRAFT_KEY = "rag.chat.draft.v1"`).
7. **import 必须按首字母排序** (oxlint sort-imports 规则).
8. **i18n key 用中文**: `t("中文 key")`, zh.json identity (value=key), en.json 翻译. 改 UI 文案 commit 前必看 `git diff` 加 zh/en.json.
9. **i18n value 不能含 namespace 字符**: 不能用 `.` 或 `:`. 例: `"加载中…"` 而非 `"加载中..."` (3 个 dot 会被 next-intl 误当 namespace key).
10. **路由跳转用 `@/i18n/navigation` 的 useRouter**, 禁止 `next/navigation` (强制 locale 前缀, 避免 307 重定向).
11. **TanStack Query 5.x**: staleTime 默认 60_000 (1 min), refetchOnWindowFocus 默认 false (跟项目风格一致).
12. **lucide-react mock 必须用 `importOriginal`**: `vi.mock(import("lucide-react"), async (importOriginal) => ({...await importOriginal(), Brain: ...}))`. 直接 `vi.mock("lucide-react", () => ({Brain: ...}))` 会缺 X 等其他 icon, 导致 DialogContent / Button 等组件抛 'X export is not defined'.

### 覆盖别人 worktree 残留警告

- 用 `git stash list` 确认有没有别人的 stash, 不动
- 切分支前用 `git status` 看工作树, 别用 `git reset --hard` (会丢工作)
- 跨 packages/\* 的工作需要别人确认, 不要自行决定保留/丢弃

## 零 lint warning 规范 (2026-06-19 phase2)

- `bun run lint` 必须 0 warning + 0 error
- 函数声明用 `const Component = () => {}`，禁止 `function Component(){}`
  (React 组件 default export 例外: `export default function Page(){}`)
- 魔法数字必须提取到 `const/index.ts` 作为命名常量
- 变量名禁止单字符 (val 替代 v, idx 替代 i)
- import 按字母排序
- 三元表达式禁止，改用 if/else 或提取变量
