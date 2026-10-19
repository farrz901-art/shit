# Streamdown 迁移设计文档

> 起草日期: 2026-06-30
> 状态: 已通过设计阶段对话,待用户对写盘后的 spec 做最终审阅
> 范围: 把 `packages/web` 内仅存的两处 `react-markdown@^10.1.0` 调用替换成 `streamdown@^2.5.0`(已由 commit `54d7672e` 加入 `package.json` 但未引用),顺手启用内置 GFM / Shiki 高亮

## 1. 背景与动机

### 1.1 现状(写盘时已确认)

- `react-markdown@^10.1.0` 在 `packages/web/` 源码中只有 **2 处 import**:
  - [components/chat/assistant-body.tsx:8](packages/web/components/chat/assistant-body.tsx#L8) - chat 助手消息渲染,外面包了 `parseThinkTag` 拆 `` 块
  - [app/[locale]/output/[task_id]/[file]/page.tsx:15](packages/web/app/%5Blocale%5D/output/%5Btask_id%5D/%5Bfile%5D/page.tsx#L15) - 文件预览页(RSC)
- 当前没有 `MarkdownRenderer` 统一包装,两处都直接用 `<ReactMarkdown>` + 默认配置
- 没有 `remark` / `rehype` 插件,没有 GFM,没有代码块高亮
- `streamdown@^2.5.0` 已在 `package.json` 和 `bun.lock` 中(commit `54d7672e` 2026-06-30 15:46 +0800),但 **没有任何 import 引用它**
- 当前 0 个 markdown 渲染相关的单元测试,0 个 E2E 用例覆盖 markdown 输出

### 1.2 性能痛点(迁移主因)

流式路径当前是这样:每个 SSE chunk → `setMessagesByConv` 累加 `content` 字符串 → `MessageList` 重渲染 → `<ReactMarkdown>` 重新解析 **整段** markdown 累计串。

一个 800 token 的回答大约触发 50-100 次完整 reparse,无 debounce、无增量解析。这是 streamdown 专门要消除的痛点(streamdown 原生 `mode="streaming"` + `parseIncompleteMarkdown` + 块级增量渲染)。

### 1.3 业务痛点

- 当前 chat 输出 **没有 GFM**:模型回表格 `| col | col |` 全部被 `react-markdown@10` 渲染为纯文本行
- 代码块没有高亮,排版与 prose 融为一体,可读性差
- 流式中未闭合的代码块会"裸"在消息里,等下一行再补,UI 抖动

## 2. 目标与非目标

### 2.1 In scope

- 把两处 `react-markdown` 调用换成 `streamdown`,删 `react-markdown` 依赖
- 启用 streamdown 内置 **GFM**(自动,无需配置)和 **Shiki 代码高亮**(自动,无需配置)
- 抽 2 个独立 wrapper:`MarkdownStream`(chat 流式)和 `MarkdownStatic`(output 静态)
- 保留现有 `parseThinkTag` 思考块拆分;`components.think` 留口但暂不预存实例
- 保留 `MarkdownImg` 图片预览,改用 `components.img` 注入
- 删外层 `prose` Tailwind 类(streamdown 自带 typography)
- 配 Tailwind v4 `@source` 让 streamdown 工具类被扫到
- 8 个新单元测试 + 2 个 assistant-body 补 case + 1 个 e2e

### 2.2 Out of scope(YAGNI)

- ❌ mermaid 图表(用户已确认不启用)
- ❌ KaTeX 数学公式(同上)
- ❌ CJK 友好调节(streamdown 内置默认即可)
- ❌ 自定义 Shiki 主题 / 语言集(默认 1-2 个语言,够用)
- ❌ `streamdown/styles.css`(`animated` prop 才会用到,本项目不用)
- ❌ 保留 `react-markdown` 作为 fallback(违反项目"严禁 shim"原则,出问题 git revert)
- ❌ 把 `markdown-img` 拆出 `components/chat/` 之外(目前只 chat 用,不提前抽象)
- ❌ 重写 `parseThinkTag` 改用 streamdown 的 `components.think`(保持现有稳定拆分逻辑)

## 3. 文件结构

### 3.1 新增文件

```
packages/web/components/markdown/
├── markdown-stream.tsx              # client, mode=streaming
├── markdown-static.tsx              # client, mode=static
├── markdown-img.tsx                 # 从 components/chat/ 迁过来(?)
├── think-block.tsx                  # 折叠展示 thinking
├── markdown-stream.test.tsx         # 6 用例
├── markdown-static.test.tsx         # 3 用例
└── think-block.test.tsx             # 2 用例
```

### 3.2 修改文件

| 文件 | 改动 |
|---|---|
| [components/chat/assistant-body.tsx](packages/web/components/chat/assistant-body.tsx) | 删 `ReactMarkdown` import;`<ReactMarkdown>` → `<MarkdownStream onPreview={onPreview}>`;删外层 `prose prose-sm max-w-none` div;`ThinkBlock` 替代手写 `<AppCollapsible>` |
| [app/[locale]/output/[task_id]/[file]/page.tsx:15,137](packages/web/app/%5Blocale%5D/output/%5Btask_id%5D/%5Bfile%5D/page.tsx) | 删 `ReactMarkdown` import;`<ReactMarkdown>` → `<MarkdownStatic>`;删外层 `prose prose-neutral dark:prose-invert max-w-none p-6`,换 `<div className="p-6">` |
| [app/globals.css](packages/web/app/globals.css) | 追加 `@source "../../../node_modules/streamdown/dist/*.js";` (monorepo 3 层) |
| [package.json](packages/web/package.json) | 删 `"react-markdown": "^10.1.0"`,保留 `"streamdown": "^2.5.0"` |
| [components/chat/assistant-body.test.tsx](packages/web/components/chat/assistant-body.test.tsx) | 补 2 个 case:剥离 thinking 后 stream 输入正确;含 `**bold**` 渲染 `<strong>` |

### 3.3 候选删除

- `components/chat/markdown-img.tsx`(31 行) - 可选迁到 `components/markdown/`,也可保留位置不挪(只在 chat 用)

> **待最终确认**:`markdown-img` 是否迁出?建议保留在原位,减少单次变更文件数。chat 用的就是 chat 路径下的,语义清晰。

### 3.4 不动的部分

- `parseThinkTag` 实现(在 `assistant-body.tsx` 内部)
- `AppCollapsible`(走 `think-block.tsx` 包装一层)
- `MessageBubble` 的 `previewSrc` 状态机
- `lib/chat/*` 整条 SSE/状态链(streamdown 是纯渲染层)
- `shiki` 包(JSON view/diff 还在用,不能删)
- `@tailwindcss/typography` 插件(项目别处可能用,留)

## 4. 组件契约

### 4.1 `MarkdownStream`

```tsx
// packages/web/components/markdown/markdown-stream.tsx
"use client";
import { Streamdown, type StreamdownProps } from "streamdown";
import { MarkdownImg } from "@/components/chat/markdown-img";

const components: StreamdownProps["components"] = {
  img: (props) => {
    // onPreview 由调用方通过 render props 注入
    return <MarkdownImg {...props} /* onPreview 由父级 useState 透传 */ />;
  },
  // think 留口:当前 AssistantBody 走 parseThinkTag 预处理,
  // 不会传 <think> 标签进 streamdown,但 API 仍可被未来场景使用
  think: ({ children }) => <>{children}</>,
};

export interface MarkdownStreamProps {
  /** markdown 源文本(已经过 parseThinkTag 拆分后的 answer 部分) */
  children: string;
  /** 图片点击回调,透传给 components.img */
  onPreview?: (src: string) => void;
  /** 容器 className,默认 "max-w-none" */
  className?: string;
}

export function MarkdownStream({ children, onPreview, className = "max-w-none" }: MarkdownStreamProps) {
  const mergedComponents: StreamdownProps["components"] = {
    ...components,
    img: (props) => <MarkdownImg {...props} onPreview={onPreview} />,
  };
  return (
    <div className={className}>
      <Streamdown
        mode="streaming"
        parseIncompleteMarkdown
        components={mergedComponents}
      >
        {children}
      </Streamdown>
    </div>
  );
}
```

**关键决策**:
- `mode="streaming"` - 触发流式增量解析
- `parseIncompleteMarkdown`(默认 true)- 自动补未闭合代码块、表格
- `components` 在组件外定义基础版,函数内合并 onPreview(避免每次 render 创建新对象)

### 4.2 `MarkdownStatic`

```tsx
// packages/web/components/markdown/markdown-static.tsx
"use client";
import { Streamdown, type StreamdownProps } from "streamdown";

const components: StreamdownProps["components"] = {
  // output 页不接 onPreview,直接走 streamdown 默认 <img>
  img: ({ src, alt }) => <img src={src} alt={alt} className="max-w-full rounded" />,
};

export interface MarkdownStaticProps {
  children: string;
  className?: string;
}

export function MarkdownStatic({ children, className = "max-w-none" }: MarkdownStaticProps) {
  return (
    <div className={className}>
      <Streamdown mode="static" components={components}>
        {children}
      </Streamdown>
    </div>
  );
}
```

**注意**:此组件是 `"use client"`。被 RSC 页面 import 时会把 import 子树切到 client 边界。`page.tsx` 接受此变化。

### 4.3 `ThinkBlock`

```tsx
// packages/web/components/markdown/think-block.tsx
"use client";
import { AppCollapsible } from "@/components/common/display/app-collapsible";

export interface ThinkBlockProps {
  /** 思考内容(纯文本,无 markdown 解析) */
  children: string;
  /** 默认是否展开,默认 false */
  defaultOpen?: boolean;
}

export function ThinkBlock({ children, defaultOpen = false }: ThinkBlockProps) {
  return (
    <AppCollapsible
      title="思考过程"
      defaultOpen={defaultOpen}
      className="mb-2"
    >
      <div className="mt-1 whitespace-pre-wrap rounded-lg border border-border/40 bg-muted/30 p-3 text-sm text-muted-foreground">
        {children}
      </div>
    </AppCollapsible>
  );
}
```

**取代现有内联 JSX**(assistant-body.tsx:28-34):
```tsx
<AppCollapsible title="思考过程" defaultOpen={false} className="mb-2">
  <div className="mt-1 whitespace-pre-wrap rounded-lg border border-border/40 bg-muted/30 p-3 text-sm text-muted-foreground">
    {thinking}
  </div>
</AppCollapsible>
```

抽出来是为了:① 行数限制(CLAUDE.md 单文件 ≤300 行);② 复用与单测方便;③ 未来想加 motion 或 stats 改 1 处。

## 5. 渲染流程

### 5.1 Chat(助手消息)

```
SSE delta 到达
   │
   ▼
stream-handler.ts:138-147
   │  setMessagesByConv({ ...msg, content: msg.content + ev.delta })
   ▼
use-chat-state(状态变更)
   │
   ▼
MessageList 重渲染
   │
   ▼
MessageBubble → AssistantBody({ content, onPreview })
   │
   ├─── parseThinkTag(content) → { thinking, answer }
   │
   ├─── thinking  → <ThinkBlock>{thinking}</ThinkBlock>          [默认折叠]
   │
   └─── answer    → <MarkdownStream onPreview={onPreview}>{answer}</MarkdownStream>
                        │
                        ▼
                   <Streamdown mode="streaming" parseIncompleteMarkdown components={...}>
                      {answer}
                   </Streamdown>
```

### 5.2 Output 页(文件预览)

```
RSC: page.tsx 加载 state.content(字符串)
   │
   ▼
<MarkdownStatic>{state.content}</MarkdownStatic>     // client component 边界
   │
   ▼
<Streamdown mode="static" components={...}>
   {state.content}
</Streamdown>
```

## 6. 错误处理

- **Markdown 解析抛错** - `<Streamdown>` 在坏 markdown 上不抛错,按原文渲染。不需要 try/catch。
- **MarkdownImg 收到坏 src** - 已有 `safeSrc` 守卫,保留原样
- **streamdown 库自身异常** - `parseIncompleteMarkdown` 总会返回部分渲染树;正则失败时降级为纯文本
- **不加 ErrorBoundary** - 项目约定不滥用(参考已有 .dark / ErrorBanner 模式)

## 7. 测试计划(11 个)

### 7.1 单元测试(放源文件旁,跟项目规约一致)

| 文件 | 用例 | 验证点 |
|---|---|---|
| `markdown-stream.test.tsx` | 1. 默认渲染纯文本不崩 | smoke |
| | 2. 渲染 GFM 表格(pipe 语法) | `\| col1 \| col2 \|` → `<table>` |
| | 3. 渲染代码块,内置 Shiki 高亮 | 出现 `shiki` 主题类 |
| | 4. 不完全代码块(`` ```ts\nconst ``)自动闭合 | 渲染 `<pre>` 不抛错 |
| | 5. `components.img` 收到 props,点击触发 `onPreview` | `MarkdownImg` 被调 |
| | 6. `components.think` 渲染 children | API 入口存在 |
| `markdown-static.test.tsx` | 1. 渲染完整 markdown 不崩 | smoke |
| | 2. 渲染 GFM 表格 | 同上 |
| | 3. 渲染带图片 markdown,`onPreview` 不会触发(无回调) | output 路径无预览 |
| `think-block.test.tsx` | 1. 默认折叠,显示"思考过程"标题 | `data-state="closed"` |
| | 2. 点击展开,内容显示 | `data-state="open"` |
| `assistant-body.test.tsx`(补) | 1. 包含 `` 时,`MarkdownStream` 接的是剥离 thinking 后的 answer | props 校验 |
| | 2. 包含 `**bold**` 时,正确渲染 `<strong>` | GFM 启用回归 |

### 7.2 E2E 测试(补 1 个)

修改 `packages/web/e2e/chat-full-flow.spec.ts`,新增 1 个 case:
- 用 Dify mock 发送包含 ```` ```ts\nconst x = 1\n``` ```` + `| a | b |` + `**bold**` 的回复
- 断言:页面出现 `<table>` + Shiki 高亮 `<pre>` + `<strong>`

### 7.3 测试隔离

- 用 `@testing-library/react` + jsdom,跟现有 `components/chat/*.test.tsx` 一致
- 不 mock streamdown 库本体(vitest 走真 import 测真行为,避免 mock 隐藏 import 错误)
- 范围测试用 `bun run test components/markdown` 跑目录;完整 plan 收尾再跑 `bun run test` 全量(参考 [[feedback-test-scope-per-task]])

## 8. 验证清单(收尾跑)

```bash
# 1. format
bun run format

# 2. lint
bun run lint:fix
bun run lint

# 3. 类型
bun run typecheck

# 4. 范围测试
bun run test components/markdown
bun run test components/chat/assistant-body.test.tsx

# 5. 全量回归
bun run test

# 6. 视觉验证(手动)
#   - 启动 dev,发一条带 **bold** + ```code``` + 表格 + ![img](url) 的 prompt
#   - 检查流式打字时 GFM 表格/代码块不抖
#   - 检查 output 页加载 .md 文件预览正常
#   - 检查 dark mode 下 prose 替代后颜色仍可读
#   - 截图对比迁移前/后 chat 浅色/深色 + output 浅色/深色
```

## 9. 风险点

| # | 风险 | 缓解 |
|---|---|---|
| 1 | streamdown 内置 typography 跟 `prose` 类视觉差异大 | 迁移前先截一组图(chat 浅/深 + output 浅/深),迁移后对比;不通过则加自定义类覆盖 |
| 2 | Shiki 高亮增加 bundle 体积 | streamdown 默认只引 1-2 个语言,首版不评估;真出问题再裁剪 |
| 3 | 删 `react-markdown` 漏掉隐式引用 | 迁移完成时 `grep -r "react-markdown" packages/web/src` 应 0;`bun run typecheck` 再过一道 |
| 4 | RSC 页面变 client 边界导致 hydration 警告 | output 页只有静态 markdown 字符串作为 prop,无状态、无 effect,理论上不警告;e2e case 验证 |

**回退方式**:不保留 env 开关(用户已选)。回退 = `git revert` 单次 commit。

## 10. 实施顺序建议(给 writing-plans 用)

1. 装 streamdown 依赖(已有,确认版本)
2. 创建 `components/markdown/` 目录 + 4 个新文件
3. 写 `ThinkBlock` + 它的 2 个测试(最纯,先稳定)
4. 写 `MarkdownStatic` + 它的 3 个测试(无 onPreview 依赖,先稳)
5. 写 `MarkdownStream` + 它的 6 个测试(最复杂,核心)
6. 改 `assistant-body.tsx` 接 `MarkdownStream` + `ThinkBlock`
7. 改 `output/[task_id]/[file]/page.tsx` 接 `MarkdownStatic`
8. 改 `globals.css` 加 `@source`
9. 改 `package.json` 删 `react-markdown`
10. 补 `assistant-body.test.tsx` 2 个 case + e2e 1 个 case
11. 跑全套验证 + 视觉对比

## 11. 关联文档

- 现状基线:本 spec §1.1(项目自探索)
- streamdown 官方文档:https://streamdown.ai/docs/migrate
- 项目 CLAUDE.md:`c:\Users\abcuc\Desktop\rag\CLAUDE.md`(工具链、测试 4 模式、范围控制)
- 项目 `.claude/CLAUDE.md`:`c:\Users\abcuc\Desktop\rag\.claude\CLAUDE.md`(TDD 强制、i18n 路由、JSX 规范)
- 已知 memory:[[feedback-test-real-code-path-not-just-mock-mock]]、[[feedback-test-scope-per-task]]、[[feedback-no-shim-no-minimal-changes]]、[[feedback-filename-kebab-case-strict]]、[[feedback-react-file-size-and-dialog-naming]]

## 12. 待用户最终确认事项

- [ ] `markdown-img` 是否迁出 `components/chat/` 到 `components/markdown/`?默认:不迁
- [ ] `markdown-stream` / `markdown-static` 容器默认 className `max-w-none` 是否合适?默认:合适
- [ ] `ThinkBlock` 默认 `defaultOpen={false}` 是否保留?默认:保留
- [ ] output 页 client 边界下沉是否接受?默认:接受
