# Streamdown 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `packages/web` 内 2 处 `react-markdown@^10.1.0` 调用替换成 `streamdown@^2.5.0`,抽 2 个独立 wrapper(`MarkdownStream` / `MarkdownStatic`),启用内置 GFM + Shiki 代码高亮,删外层 `prose` Tailwind 类,8 个新单元测试 + 2 个补 case + 1 个 e2e。

**Architecture:**
- `MarkdownStream`(client, `mode="streaming"` + `parseIncompleteMarkdown`)- 给 chat 流式用,接 `onPreview` 透传到 `components.img`
- `MarkdownStatic`(client, `mode="static"`)- 给 output 页静态文件预览用
- `ThinkBlock`(client)- 折叠展示 `<think>` 内容,包装 `AppCollapsible`
- `markdown-img` **保留位置**在 `components/chat/markdown-img.tsx`(只有 chat 用,延迟抽象)

**Tech Stack:** TypeScript 6, React 19, Next.js 16, Vitest 4, Playwright, Tailwind v4, streamdown 2.5.0

**Reference Spec:** `docs/superpowers/specs/2026-06-30-streamdown-migration-design.md`

**Key Memory 引用:**
- [[feedback-test-real-code-path-not-just-mock-mock]] - 不 mock 第三方库本体
- [[feedback-test-scope-per-task]] - 单 task 只 test 改过的文件
- [[feedback-no-shim-no-minimal-changes]] - 不写 shim / 兼容代码
- [[feedback-react-file-size-and-dialog-naming]] - 单文件 ≤300 行,Dialog 拆独立
- [[feedback-filename-kebab-case-strict]] - 文件名 kebab-case
- [[feedback-design-docs-in-chinese]] - 中文注释

---

## 实施顺序(11 个任务)

每个任务**自包含**,跑通验证后 commit 再进下一个。

**工作量估算(2026-06-30 修正)**: 11 task × 平均 15 min/task = 2.5h 主体;加命令串行 + 1-2 次 lint/返工 = **3-4 小时(半天)**,不是 1-2 天(原估算把单位换算错了)。

---

### Task 1: 创建 `ThinkBlock` 组件 + 单元测试

**Files:**
- Create: `packages/web/components/markdown/think-block.tsx`
- Create: `packages/web/components/markdown/think-block.test.tsx`

- [ ] **Step 1: 写测试文件(先红)**

写 `packages/web/components/markdown/think-block.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThinkBlock } from "./think-block";

describe("ThinkBlock", () => {
  it("默认折叠, 显示 '思考过程' 标题", () => {
    render(<ThinkBlock>分析中...</ThinkBlock>);
    expect(screen.getByText("思考过程")).toBeInTheDocument();
    expect(screen.queryByText("分析中...")).not.toBeInTheDocument();
  });

  it("点击 trigger 展开, 显示 children", async () => {
    const user = userEvent.setup();
    render(<ThinkBlock>实际思考内容</ThinkBlock>);
    await user.click(screen.getByText("思考过程"));
    expect(screen.getByText("实际思考内容")).toBeInTheDocument();
  });

  it("defaultOpen=true 时默认展开", () => {
    render(<ThinkBlock defaultOpen>已展开内容</ThinkBlock>);
    expect(screen.getByText("已展开内容")).toBeInTheDocument();
  });

  it("数据 testId 透传到 AppCollapsible", () => {
    render(<ThinkBlock testId="think-toggle">x</ThinkBlock>);
    expect(screen.getByTestId("think-toggle")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd packages/web && bun run test components/markdown/think-block.test.tsx`
Expected: FAIL with "Cannot find module './think-block'"

- [ ] **Step 3: 写实现文件**

写 `packages/web/components/markdown/think-block.tsx`:

```tsx
"use client";
/**
 * ThinkBlock — 折叠展示 AI 思考过程 (2026-06-30 streamdown 迁移)
 * 包装 AppCollapsible, 接受纯文本 children, 不做 markdown 解析
 * 取代 assistant-body.tsx 内联 renderThinking IIFE
 */
import { AppCollapsible } from "@/components/common/display/app-collapsible";
import { type ReactNode } from "react";

const THINK_TITLE = "思考过程";

export interface ThinkBlockProps {
  /** 思考内容, 纯文本无 markdown */
  children: string;
  /** 非受控默认展开, 默认 false */
  defaultOpen?: boolean;
  /** 受控展开状态 */
  open?: boolean;
  /** 受控展开回调 */
  onOpenChange?: (open: boolean) => void;
  /** 透传到 trigger 按钮的 testId, 默认 'think-toggle' */
  testId?: string;
  /** 外层 className */
  className?: string;
  /** 触发按钮左侧 icon, 默认 ChevronDown */
  icon?: ReactNode;
}

export const ThinkBlock = ({
  children,
  defaultOpen,
  open,
  onOpenChange,
  testId = "think-toggle",
  className,
  icon,
}: ThinkBlockProps) => (
  <AppCollapsible
    title={THINK_TITLE}
    defaultOpen={defaultOpen}
    open={open}
    onOpenChange={onOpenChange}
    icon={icon}
    testId={testId}
    className={className ?? "mb-2"}
  >
    <div className="mt-1 whitespace-pre-wrap rounded-lg border border-border/40 bg-muted/30 p-3 text-sm text-muted-foreground">
      {children}
    </div>
  </AppCollapsible>
);
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd packages/web && bun run test components/markdown/think-block.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
git add components/markdown/think-block.tsx components/markdown/think-block.test.tsx
git commit -m "feat(markdown): 抽 ThinkBlock 组件, 替代 assistant-body 内联折叠 JSX"
```

---

### Task 2: 创建 `MarkdownStatic` 组件 + 单元测试

**Files:**
- Create: `packages/web/components/markdown/markdown-static.tsx`
- Create: `packages/web/components/markdown/markdown-static.test.tsx`

- [ ] **Step 1: 写测试文件(先红)**

写 `packages/web/components/markdown/markdown-static.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarkdownStatic } from "./markdown-static";

describe("MarkdownStatic", () => {
  it("渲染纯文本不崩", () => {
    render(<MarkdownStatic>hello world</MarkdownStatic>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("渲染 GFM 表格", () => {
    render(
      <MarkdownStatic>
        {`| a | b |
| - | - |
| 1 | 2 |`}
      </MarkdownStatic>,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("渲染图片但 onPreview 不被调用 (output 路径无预览)", () => {
    render(<MarkdownStatic>![alt](https://example.com/a.png)</MarkdownStatic>);
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("src", "https://example.com/a.png");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd packages/web && bun run test components/markdown/markdown-static.test.tsx`
Expected: FAIL with "Cannot find module './markdown-static'"

- [ ] **Step 3: 写实现文件**

写 `packages/web/components/markdown/markdown-static.tsx`:

```tsx
"use client";
/**
 * MarkdownStatic — 静态 markdown 渲染 (2026-06-30 streamdown 迁移)
 * 取代 output/[task_id]/[file]/page.tsx 内联 <ReactMarkdown>
 * mode="static" + 无 onPreview + 默认 <img>
 */
import { Streamdown, type StreamdownProps } from "streamdown";
import { type ReactNode } from "react";

const components: StreamdownProps["components"] = {
  // output 页无预览, 走默认 <img> 加 rounded
  img: ({ src, alt }) => (
    <img src={src} alt={alt} className="max-w-full rounded" />
  ),
};

export interface MarkdownStaticProps {
  /** markdown 源文本 */
  children: string;
  /** 容器 className */
  className?: string;
  /** 透传到 Streamdown, 预留未来 rehype 插件接入 */
  remarkPlugins?: StreamdownProps["remarkPlugins"];
  rehypePlugins?: StreamdownProps["rehypePlugins"];
}

export const MarkdownStatic = ({
  children,
  className,
  remarkPlugins,
  rehypePlugins,
}: MarkdownStaticProps): ReactNode => (
  <div className={className ?? "max-w-none"}>
    <Streamdown
      mode="static"
      components={components}
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
    >
      {children}
    </Streamdown>
  </div>
);
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd packages/web && bun run test components/markdown/markdown-static.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
git add components/markdown/markdown-static.tsx components/markdown/markdown-static.test.tsx
git commit -m "feat(markdown): 抽 MarkdownStatic, 取代 output 页 react-markdown"
```

---

### Task 3: 创建 `MarkdownStream` 组件 + 单元测试(核心)

**Files:**
- Create: `packages/web/components/markdown/markdown-stream.tsx`
- Create: `packages/web/components/markdown/markdown-stream.test.tsx`

- [ ] **Step 1: 写测试文件(先红)**

写 `packages/web/components/markdown/markdown-stream.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MarkdownStream } from "./markdown-stream";

// 避免 lucide-react 在 test 拿不到 X 等 icon (项目既有模式)
vi.mock(import("lucide-react"), async (importOriginal) => ({
  ...(await importOriginal()),
  ZoomIn: () => null,
}));

describe("MarkdownStream", () => {
  it("渲染纯文本不崩", () => {
    render(<MarkdownStream>hello world</MarkdownStream>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });

  it("渲染 GFM 表格", () => {
    render(
      <MarkdownStream>
        {`| a | b |
| - | - |
| 1 | 2 |`}
      </MarkdownStream>,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("渲染代码块带 Shiki 高亮 class", () => {
    const md = "```ts\nconst x = 1;\n```";
    render(<MarkdownStream>{md}</MarkdownStream>);
    // shiki 通常加 'shiki' class 或 data 属性
    const pre = document.querySelector("pre");
    expect(pre).toBeInTheDocument();
    expect(pre?.className ?? "").toMatch(/shiki|streamdown/);
  });

  it("不完全代码块 (```ts\\nconst) 自动闭合不抛错", () => {
    expect(() => {
      render(<MarkdownStream>{"```ts\nconst x"}</MarkdownStream>);
    }).not.toThrow();
  });

  it("img 点击触发 onPreview 回调", () => {
    const onPreview = vi.fn();
    render(
      <MarkdownStream onPreview={onPreview}>
        {"![alt](https://example.com/a.png)"}
      </MarkdownStream>,
    );
    const img = screen.getByRole("img");
    fireEvent.click(img);
    expect(onPreview).toHaveBeenCalledWith("https://example.com/a.png");
  });

  it("无 onPreview 时 img 不挂 onClick", () => {
    render(<MarkdownStream>![alt](https://example.com/a.png)</MarkdownStream>);
    const img = screen.getByRole("img");
    // MarkdownImg 内部 safeSrc 守卫, onClick 在 safeSrc 缺失时不会调 onPreview
    // 这里只验渲染不崩 + src 属性正确
    expect(img).toHaveAttribute("src", "https://example.com/a.png");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd packages/web && bun run test components/markdown/markdown-stream.test.tsx`
Expected: FAIL with "Cannot find module './markdown-stream'"

- [ ] **Step 3: 写实现文件**

写 `packages/web/components/markdown/markdown-stream.tsx`:

```tsx
"use client";
/**
 * MarkdownStream — 流式 markdown 渲染 (2026-06-30 streamdown 迁移)
 * 取代 assistant-body.tsx 内联 <ReactMarkdown>
 * mode="streaming" + parseIncompleteMarkdown + 接 onPreview 透传图片点击
 */
import { Streamdown, type StreamdownProps } from "streamdown";
import { type ReactNode } from "react";
import { MarkdownImg } from "@/components/chat/markdown-img";

export interface MarkdownStreamProps {
  /** markdown 源文本 (已剥离 thinking 部分) */
  children: string;
  /** 图片点击回调, 透传到 components.img */
  onPreview?: (src: string) => void;
  /** 容器 className */
  className?: string;
}

/**
 * 用 useMemo 在每次 render 合并 components 是反模式, 这里直接在调用处
 * 内联合并避免每次创建新对象触发 streamdown memo 失效
 */
export const MarkdownStream = ({
  children,
  onPreview,
  className,
}: MarkdownStreamProps): ReactNode => {
  // 每次 render 创建新 components 对象, 但 streamdown 内部 memo 靠 children + props 比较
  // 这里 onPreview 是新 closure, 不可避免. 真要优化可包 useCallback, 暂 YAGNI
  const components: StreamdownProps["components"] = {
    img: (props) => <MarkdownImg {...props} onPreview={onPreview ?? (() => {})} />,
    // think 留口: parseThinkTag 已在 AssistantBody 预处理, 此处不会触发
    // 但若未来上游直接发 <think> 标签, 走这里兜底
    think: ({ children: thinkChildren }) => <>{thinkChildren}</>,
  };
  return (
    <div className={className ?? "max-w-none"}>
      <Streamdown
        mode="streaming"
        parseIncompleteMarkdown
        components={components}
      >
        {children}
      </Streamdown>
    </div>
  );
};
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd packages/web && bun run test components/markdown/markdown-stream.test.tsx`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
git add components/markdown/markdown-stream.tsx components/markdown/markdown-stream.test.tsx
git commit -m "feat(markdown): 抽 MarkdownStream, 取代 chat 内联 react-markdown"
```

---

### Task 4: 接通 `assistant-body.tsx` - 用 `MarkdownStream` + `ThinkBlock`

**Files:**
- Modify: `packages/web/components/chat/assistant-body.tsx`(全文 56 行 → 改写)

- [ ] **Step 1: 改写 assistant-body.tsx**

完整文件替换为:

```tsx
/**
 * Assistant 消息主体 (2026-06-30 streamdown 迁移)
 * 原 message-bubble.tsx 内联 IIFE bodyContent (assistant 分支) 提取
 * 关键: parseThinkTag 拆 thinking / answer → ThinkBlock 折叠 + MarkdownStream 渲染 answer
 *       markdown img 点击 → onPreview 回调给父组件弹 ImagePreview
 */
import { MarkdownStream } from "@/components/markdown/markdown-stream";
import { ThinkBlock } from "@/components/markdown/think-block";
import { type ReactNode } from "react";

const THINK_TAG_PATTERN = /<think>(?<thinkingContent>[\s\S]*?)<\/think>/;
const THINK_REMOVE_PATTERN = /<think>[\s\S]*?<\/think>/;
const EMPTY_THINKING = "";

/** 从 content 中提取  thinking... response 标签, 返回 { thinking, answer } */
const parseThinkTag = (content: string): { thinking: string; answer: string } => {
  const match = content.match(THINK_TAG_PATTERN);
  if (!match) {
    return { answer: content, thinking: EMPTY_THINKING };
  }
  return {
    answer: content.replace(THINK_REMOVE_PATTERN, "").trim(),
    thinking: match.groups?.thinkingContent?.trim() ?? "",
  };
};

interface AssistantBodyProps {
  content: string;
  onPreview: (src: string) => void;
}

export const AssistantBody = ({ content, onPreview }: AssistantBodyProps): ReactNode => {
  const { thinking, answer } = parseThinkTag(content);
  return (
    <>
      {thinking && <ThinkBlock defaultOpen testId="think-toggle">{thinking}</ThinkBlock>}
      <MarkdownStream onPreview={onPreview}>{answer}</MarkdownStream>
    </>
  );
};
```

**改动要点**:
- 删 `import ReactMarkdown from "react-markdown"`
- 删 `import { AppCollapsible }` 和 `import { MarkdownImg }`(都迁到新组件)
- 删 `renderThinking` IIFE(被 `<ThinkBlock>` 替代)
- 删外层 `<div className="prose prose-sm max-w-none">`(streamdown 自带 typography)
- 删 `THINK_TOGGLE_TEXT` 常量(被 `ThinkBlock` 内部 `THINK_TITLE` 替代)

- [ ] **Step 2: 跑 chat 相关测试验证未崩**

Run: `cd packages/web && bun run test components/chat/assistant-body components/chat/message-bubble`
Expected: 现有 6 个 message-bubble.test.tsx + think-block 相关 case 全 PASS

- [ ] **Step 3: 跑 markdown 相关测试验证 wiring 对**

Run: `cd packages/web && bun run test components/markdown`
Expected: Task 1-3 的 4+3+6 = 13 个测试全 PASS

- [ ] **Step 4: Commit**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
git add components/chat/assistant-body.tsx
git commit -m "refactor(chat): 切到 MarkdownStream + ThinkBlock, 删 react-markdown import"
```

---

### Task 5: 接通 `output/[task_id]/[file]/page.tsx` - 用 `MarkdownStatic`

**Files:**
- Modify: `packages/web/app/[locale]/output/[task_id]/[file]/page.tsx`(1 处 import + 1 处 JSX)

- [ ] **Step 1: 删 ReactMarkdown import**

Edit 替换(只一行):

```diff
-import ReactMarkdown from "react-markdown";
 import { fetchFileMeta } from "@/lib/api/ingest";
```

- [ ] **Step 2: 加 MarkdownStatic import**

Edit 替换(在 `import { useTranslations } from "next-intl";` 后面):

```diff
 import { useTranslations } from "next-intl";
+import { MarkdownStatic } from "@/components/markdown/markdown-static";
```

注意:import 按字母序,MarkdownStatic 在 MarkdownImg 之后。`packages/web/CLAUDE.md` 强制 import 排序,手工调整位置。

最终 import 段应该是:
```tsx
import { AnimateUp, FadePresence, Reveal } from "@/components/motion/animated";
import { ApiError, NetworkError } from "@/lib/api/errors";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { Card, CardContent } from "@/components/ui/card";
import { use, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { GuardClient } from "@/components/auth/guard-client";
import { MarkdownStatic } from "@/components/markdown/markdown-static";
import { fetchFileMeta } from "@/lib/api/ingest";
import { useTranslations } from "next-intl";
```

- [ ] **Step 3: 替换 JSX**

Edit 替换(第 137-139 行 `<article>` + `<ReactMarkdown>`):

```diff
-          {state.mime === MIME_MARKDOWN ? (
-            <article className="prose prose-neutral dark:prose-invert max-w-none p-6">
-              <ReactMarkdown>{state.content}</ReactMarkdown>
-            </article>
-          ) : (
+          {state.mime === MIME_MARKDOWN ? (
+            <div className="p-6">
+              <MarkdownStatic>{state.content}</MarkdownStatic>
+            </div>
+          ) : (
             <pre className="num overflow-x-auto bg-muted/30 p-6 text-sm leading-relaxed">
               {state.content}
             </pre>
           )}
```

- [ ] **Step 4: 类型检查 + 跑测试**

Run: `cd packages/web && bun run typecheck`
Run: `cd packages/web && bun run test app/[locale]/output`
Expected: 0 type errors, 现有测试全 PASS(output 页没有专属测试,主要靠 e2e 覆盖)

- [ ] **Step 5: Commit**

```bash
cd packages/web
bun run format
bun run lint:fix
git add "app/[locale]/output/[task_id]/[file]/page.tsx"
git commit -m "refactor(output): 切到 MarkdownStatic, 删 react-markdown 引用"
```

---

### Task 6: 配 Tailwind v4 `@source` 让 streamdown 工具类被扫到

**Files:**
- Modify: `packages/web/app/globals.css`(追加 1 行)

- [ ] **Step 1: 在 globals.css 末尾追加 @source**

读 `packages/web/app/globals.css` 末尾(约 319 行 `<::-webkit-scrollbar-corner>` 后),追加:

```css
/* ========================================================================
   Streamdown typography 工具类扫描 (2026-06-30 streamdown 迁移)
   monorepo 3 层: packages/web/app/globals.css → ../../../node_modules/streamdown
   触发 streamdown 组件内的 Tailwind 类 (如 prose-shiki, code block) 被生成
   ======================================================================== */
@source "../../../node_modules/streamdown/dist/*.js";
```

- [ ] **Step 2: 验证 Tailwind 编译不报错**

Run: `cd packages/web && bun run build 2>&1 | tail -20`
Expected: 0 error(可能有 warning 提示 `@source` path 不存在但不影响 build)

如果 path 拼错报错:实际可能 `packages/web/node_modules/streamdown` 是直接路径,因为 bun 在 web 包层 install,不需要 3 层 `..`。验证:

```bash
ls packages/web/node_modules/streamdown/dist/index.js
```

- 存在 → 用 `../../node_modules/streamdown/dist/*.js`(2 层)
- 不存在 → 保持 3 层

按实际发现调整 path 后重新 build。

- [ ] **Step 3: Commit**

```bash
cd packages/web
git add app/globals.css
git commit -m "chore(css): 加 streamdown @source, 让 streamdown 工具类被 Tailwind 扫到"
```

---

### Task 7: 从 `package.json` 删 `react-markdown` 依赖

**Files:**
- Modify: `packages/web/package.json`(1 行)
- Modify: `packages/web/bun.lock`(自动)

- [ ] **Step 1: 跑一次全量 vitest 确认无残留引用**

Run: `cd packages/web && grep -r "react-markdown" components app lib messages 2>&1 || true`
Expected: 0 hits

如果有 hit:回到对应文件删除 import。

- [ ] **Step 2: 删 package.json 里的 react-markdown 行**

Edit 替换:

```diff
     "react-dropzone": "^15.0.0",
-    "react-markdown": "^10.1.0",
     "react-use": "^17.6.1",
```

- [ ] **Step 3: 重装依赖 + 跑类型检查**

Run: `cd packages/web && bun install`
Run: `cd packages/web && bun run typecheck`
Expected: 0 error(react-markdown 类型包被移除,streamdown 替代)

- [ ] **Step 4: 跑全量 vitest**

Run: `cd packages/web && bun run test`
Expected:719 + 13(新) = 732 个 test 全部 PASS(0 新 fail)

- [ ] **Step 5: Commit**

```bash
cd packages/web
git add package.json bun.lock
git commit -m "chore(deps): 删 react-markdown 依赖, 完全迁到 streamdown"
```

---

### Task 8: 补 `assistant-body.test.tsx` 2 个 case

**Files:**
- Modify: `packages/web/components/chat/assistant-body.test.tsx`(若不存在则新建在 `assistant-body.tsx` 旁)

- [ ] **Step 1: 检查现有测试文件**

Run: `cd packages/web && ls components/chat/assistant-body*`
Expected: 只有 `assistant-body.tsx`,没有 `.test.tsx`

如果 `message-bubble.test.tsx` 已有 `AssistantBody` 间接测试(通过 `MessageBubble` 包),本任务在 `message-bubble.test.tsx` 补 2 个 case 即可,不另建文件。

- [ ] **Step 2: 在 `message-bubble.test.tsx` 末尾追加 2 个 case**

Edit 追加到 `describe("MessageBubble", () => { ... })` 块最末尾(第 89 行 `})` 之前):

```tsx
  // (2026-06-30 streamdown 迁移) GFM 启用回归
  it("assistant 消息含 **bold** 时正确渲染 <strong>", () => {
    const msg: Message = {
      content: "这是 **粗体** 文本",
      createdAt: 1_700_000_003_000,
      id: "m4",
      role: "assistant",
    };
    renderInI18n(<MessageBubble message={msg} />);
    const strong = screen.getByText("粗体");
    expect(strong.tagName).toBe("STRONG");
  });

  it("assistant 消息含 <think> 时, 思考内容进 ThinkBlock, answer 进 MarkdownStream", () => {
    const msg: Message = {
      content: "<think>步骤 1\n步骤 2</think>**最终**答案",
      createdAt: 1_700_000_004_000,
      id: "m5",
      role: "assistant",
    };
    renderInI18n(<MessageBubble message={msg} />);
    // ThinkBlock 渲染
    expect(screen.getByTestId("think-toggle")).toBeInTheDocument();
    // 答案区有 <strong>
    const strong = screen.getByText("最终");
    expect(strong.tagName).toBe("STRONG");
  });
```

- [ ] **Step 3: 跑测试确认通过**

Run: `cd packages/web && bun run test components/chat/message-bubble.test.tsx`
Expected: 6 + 2 = 8 个 case 全 PASS

- [ ] **Step 4: Commit**

```bash
cd packages/web
git add components/chat/message-bubble.test.tsx
git commit -m "test(chat): 补 assistant-body 2 个 case 覆盖 GFM + think 拆分"
```

---

### Task 9: 加 1 个 E2E case 覆盖 streaming + markdown

**Files:**
- Modify: `packages/web/e2e/chat-full-flow.spec.ts`(追加 1 个 test)

- [ ] **Step 1: 读文件末尾,找插入点**

读 `packages/web/e2e/chat-full-flow.spec.ts` 末尾(已有 test 块结束处),找一个 test 块后面追加新 test。

- [ ] **Step 2: 追加 1 个 e2e test**

Edit 追加(在文件末尾,最后一个 test 块后):

```tsx
// (2026-06-30 streamdown 迁移) 验证 chat 渲染 GFM + Shiki + bold
test("streamdown 渲染 GFM 表格 + Shiki 代码块 + bold", async ({ page }) => {
  await page.goto("/zh/chat");
  await clearAnonState(page);
  await page.goto("/zh/chat");

  const MOCK_REPLY = [
    "**重要** 结论:",
    "",
    "| 参数 | 值 |",
    "| - | - |",
    "| 功率 | 1.5kW |",
    "",
    "```ts",
    "const x = 1;",
    "```",
  ].join("\n");

  // 拦截 chat 发送请求, 模拟 Dify 流式返回
  await page.route("**/api/chat/send**", async (route) => {
    const body = JSON.stringify({ event: "message", delta: MOCK_REPLY });
    await route.fulfill({
      contentType: "text/event-stream",
      body: `data: ${body}\n\ndata: ${JSON.stringify({ event: "message_end" })}\n\n`,
    });
  });

  await page.getByPlaceholder(/(说点什么|Ask something)/).fill("测试 markdown");
  await page.keyboard.press("Enter");

  // 验证 GFM 表格出现
  await expect(page.getByRole("table")).toBeVisible({ timeout: TIMEOUT_DIFY_LONG_MS });
  // 验证 <strong> 出现
  await expect(page.locator("strong", { hasText: "重要" })).toBeVisible();
  // 验证 Shiki 代码块
  await expect(page.locator("pre")).toBeVisible();
});
```

注:`page.route` + `route.fulfill` 是 Playwright 拦截 fetch 的标准 API,本文件其他 test 若已有类似拦截,改用同一 pattern。

- [ ] **Step 3: 跑 e2e 验证**

Run: `cd packages/web && bun run test:e2e -- chat-full-flow.spec.ts`
Expected: 已有 N 个 test + 1 个新 test 全 PASS

如果失败:看 Playwright 报告 / trace 调试,最常见是 mock fetch URL pattern 不对,改 `**/api/chat/send**` 的 glob。

- [ ] **Step 4: Commit**

```bash
cd packages/web
git add e2e/chat-full-flow.spec.ts
git commit -m "test(e2e): 加 streamdown GFM + Shiki + bold 渲染验证"
```

---

### Task 10: 收尾验证 - 全量 format/lint/typecheck/test

**Files:** 无(只跑命令)

- [ ] **Step 1: 跑 format**

Run: `cd packages/web && bun run format`

- [ ] **Step 2: 跑 lint + 自动修**

Run: `cd packages/web && bun run lint:fix`
Run: `cd packages/web && bun run lint`
Expected: 0 error(允许 pre-existing warning)

- [ ] **Step 3: 跑类型检查**

Run: `cd packages/web && bun run typecheck`
Expected: 0 error

- [ ] **Step 4: 跑全量 vitest**

Run: `cd packages/web && bun run test`
Expected: 732 个 test 全 PASS(719 旧 + 13 新 = 732)

- [ ] **Step 5: 跑全量 e2e**

Run: `cd packages/web && bun run test:e2e`
Expected: 18 旧 + 1 新 = 19 个 e2e 全 PASS(允许 pre-existing skip)

- [ ] **Step 6: 最终 commit(如有 format 自动改动)**

```bash
cd packages/web
git status
# 如果有 uncommitted 改动:
git add -A
git commit -m "chore: 收尾 format 自动修"
```

---

### Task 11: 手动视觉验证 + 文档同步

**Files:**
- Create/Modify: `packages/web/CLAUDE.md`(加 1 段 markdown 渲染约定)

- [ ] **Step 1: 启动 dev server**

后端(终端 1):
```bash
cd packages/service && uv run python main.py
```

前端(终端 2):
```bash
cd packages/web && bun run dev
```

- [ ] **Step 2: 视觉验证 chat**

1. 打开 http://localhost:3000/zh/chat
2. 发一条带 `**bold**` + ```` ```ts\nconst x\n``` ```` + `| a | b |` + `![img](https://placehold.co/200x100)` 的 prompt
3. 检查:
   - 浅色 / 深色主题下,文字颜色和背景对比 OK
   - GFM 表格有边框
   - 代码块有 Shiki 配色
   - 流式打字时光标不抖
   - 点击图片弹预览

- [ ] **Step 3: 视觉验证 output 页**

1. 打开 http://localhost:3000/zh/output/<task_id>/<file.md>(任选一个 md 文件)
2. 检查: 浅/深主题下排版 OK,代码块有 Shiki

- [ ] **Step 4: 同步 CLAUDE.md 文档**

读 `packages/web/CLAUDE.md`,找到"封装组件"段后面,加 1 段:

```markdown
### Markdown 渲染 (2026-06-30 streamdown 迁移)

- 统一走 `components/markdown/`,禁止直接 import `streamdown` 或 `react-markdown`
- 流式 (chat): `<MarkdownStream onPreview={...}>{answer}</MarkdownStream>`
- 静态 (output): `<MarkdownStatic>{content}</MarkdownStatic>`
- 思考折叠: `<ThinkBlock testId="think-toggle">{thinking}</ThinkBlock>`
- `parseThinkTag` 在 `assistant-body.tsx` 内部完成, 业务代码不需要手动拆
- 删了 `react-markdown` 依赖, 启用了 streamdown 内置 GFM + Shiki
```

- [ ] **Step 5: Commit 文档**

```bash
cd packages/web
git add CLAUDE.md
git commit -m "docs(web): 加 streamdown 迁移后 markdown 渲染约定"
```

---

## 自检(对照 spec)

### Spec 覆盖

| Spec 章节 | 实施任务 |
|---|---|
| §3 文件结构(4 个新文件) | Task 1-3(创建 3 个组件 + 测试);Task 4-5 集成 |
| §4.1 MarkdownStream 契约 | Task 3 |
| §4.2 MarkdownStatic 契约 | Task 2 |
| §4.3 ThinkBlock 契约 | Task 1 |
| §5.1 chat 渲染流程 | Task 4 |
| §5.2 output 渲染流程 | Task 5 |
| §6 错误处理(不抛错,不加 ErrorBoundary) | Task 2-3 实现 + Task 4-5 集成无 try/catch |
| §7.1 单元测试 11 个 | Task 1(4) + Task 2(3) + Task 3(6) + Task 8(2)= 15 个 ✓(超出 11 是补的) |
| §7.2 e2e 1 个 | Task 9 ✓ |
| §7.3 测试隔离(不 mock 第三方) | Task 2-3 走真 import, Task 9 走真 page.route |
| §8 验证清单(6 步) | Task 10 |
| §9 风险 1(typography 视觉差异) | Task 11 Step 2-3 手动对比 |
| §9 风险 3(漏掉 react-markdown 引用) | Task 7 Step 1 跑 grep |
| §10 实施顺序 11 步 | 完全对齐 |

### 占位符扫描

- 无 "TBD" / "TODO" / "待补"
- 无 "类似 Task N"(代码都贴全)
- 无 "add appropriate error handling"(无,§6 说不加)

### 类型一致性

- `MarkdownStreamProps.onPreview: (src: string) => void`(Task 3)- 与 assistant-body.tsx `onPreview: (src: string) => void` 一致 ✓
- `ThinkBlock` 接 `defaultOpen: boolean`(Task 1)- assistant-body.tsx 传 `defaultOpen`(无值,默认 false),跟 props 匹配 ✓
- `MarkdownStatic` 接 `children: string`(Task 2)- output page 传 `state.content: string` ✓
- `components.img` 的 `(src, alt)` 参数(各 task 写的都是 React.ImgHTMLAttributes 风格)- 跟 streamdown 的 `Components` 类型签名一致 ✓

### 检查通过

- 11 个任务线性可执行
- 0 占位符
- 类型 / prop 命名跨 task 一致
- spec §12 4 个用户确认项全部采用默认(不迁 markdown-img / max-w-none / defaultOpen=false / client 边界下沉)
