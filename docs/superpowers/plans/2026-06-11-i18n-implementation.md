# 国际化 (i18n) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 RAG 管理后台接入 next-intl，支持 zh/en 双语切换，提取 678 处硬编码中文到 `t()` 调用，SettingsDialog 语言行启用。

**Architecture:** next-intl 4.x + App Router + 路径前缀（`/zh/...`、`/en/...`）+ cookie 降级（`NEXT_LOCALE`）。所有页面移入 `app/[locale]/`，API 路由不动。所有 20 个页面 + 共享组件逐个替换中文为 `t("key")`，并写入 `messages/zh.json` + `messages/en.json` 嵌套 JSON。

**Tech Stack:** next-intl 4.x, React 19, TypeScript strict, vitest + @testing-library/react, jsdom, bun

**Spec:** `docs/superpowers/specs/2026-06-10-i18n-design.md`

**前置条件:**
- 当前在 `master` 分支, 已有 ~17 个 commit (主题系统实施 16 任务已完成, `ed27669 chore: add ahooks dependency`)
- 计划完成后会重构路由结构, 建议开 worktree (`git worktree add ../rag-i18n -b feature/i18n`) 避免阻塞主线
- 后端启动 (`:8000`) 需要保持运行用于 E2E 验证
- `ahooks` 已装 (`ed27669`), 未来 i18n 切换 + 任何 hooks 工具可以直接用
- **`SettingsDialog` 已存在** (在 `web/components/settings/settings-dialog.tsx`, 主题行已活, 语言/账号行 disabled 占位) — Phase 6 不再是 SKIP, 是激活任务
- **`Header` 已抽到 `web/components/header.tsx`** (client component, 拥有 `useState` 控制 SettingsDialog 开合) — 不再内联在 `app/layout.tsx`
- **`ThemeProvider` 已包住整个 body** (在 `app/layout.tsx` 里) — I18nProvider 必须**嵌套在 ThemeProvider 内部** (ThemeProvider 在 `<html>` 上挂 `class`, 是最外层)
- `web/CLAUDE.md` 已有"## 主题系统 (Theme)"小节 — Phase 7.3 加的"## 国际化 (i18n)"小节放在它后面

**已知差异 (vs spec):**
- 实际有 **20 个页面** (spec 写 19), 见 Phase 3 列表
- `EvalListRow.tsx` 不存在 — `fmtDate()` 是 `app/evaluate/page.tsx` 内联函数
- `SettingsDialog` **已存在** (主题切换可点, 语言/账号行 disabled), Phase 6 改为激活语言行, 账号行保持 disabled

---

## Phase 1: 基础设施 (5 任务)

### Task 1.1: 装 next-intl

**Files:**
- Modify: `web/package.json`

- [ ] **Step 1: 装最新 next-intl**

```bash
cd web
bun add next-intl@latest
```

- [ ] **Step 2: 验证装成功**

```bash
cd web
bun pm ls next-intl
```

Expected: `next-intl@4.x.x` (支持 App Router 4.0+)

- [ ] **Step 3: Commit**

```bash
git add web/package.json web/bun.lock
git commit -m "chore(deps): add next-intl for i18n"
```

---

### Task 1.2: 写 routing.ts + 测试

**Files:**
- Create: `web/i18n/routing.ts`
- Create: `web/i18n/routing.test.ts`

next-intl 4.x 提供 `defineRouting` + `createNavigation` API。

- [ ] **Step 1: 写失败的测试**

```typescript
// web/i18n/routing.test.ts
import { describe, it, expect } from "vitest";
import { routing } from "./routing";

describe("routing config", () => {
  it("locales 包含 zh 和 en", () => {
    expect(routing.locales).toEqual(["zh", "en"]);
  });

  it("defaultLocale 是 zh", () => {
    expect(routing.defaultLocale).toBe("zh");
  });

  it("localePrefix 用 always (URL 强制前缀)", () => {
    expect(routing.localePrefix).toBe("always");
  });
});
```

- [ ] **Step 2: 跑测试看 red**

```bash
cd web
bun run test i18n/routing
```

Expected: FAIL `Cannot find module './routing'`

- [ ] **Step 3: 实现 routing.ts**

```typescript
// web/i18n/routing.ts
import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["zh", "en"],
  defaultLocale: "zh",
  localePrefix: "always",
});
```

- [ ] **Step 4: 跑测试看 green**

```bash
cd web
bun run test i18n/routing
```

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add web/i18n/routing.ts web/i18n/routing.test.ts
git commit -m "feat(i18n): routing config with zh/en locales"
```

---

### Task 1.3: 写 request.ts + 测试

**Files:**
- Create: `web/i18n/request.ts`
- Create: `web/i18n/request.test.ts`

- [ ] **Step 1: 写失败的测试**

```typescript
// web/i18n/request.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";

describe("getRequestConfig", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("zh locale 加载 messages/zh.json", async () => {
    vi.doMock("../messages/zh.json", () => ({ default: { common: { loading: "加载中" } } }));
    vi.doMock("../messages/en.json", () => ({ default: { common: { loading: "Loading" } } }));
    const { default: getRequestConfig } = await import("./request");
    const cfg = await getRequestConfig({ requestLocale: Promise.resolve("zh") });
    expect(cfg.messages.common.loading).toBe("加载中");
  });

  it("en locale 加载 messages/en.json", async () => {
    vi.doMock("../messages/zh.json", () => ({ default: { common: { loading: "加载中" } } }));
    vi.doMock("../messages/en.json", () => ({ default: { common: { loading: "Loading" } } }));
    const { default: getRequestConfig } = await import("./request");
    const cfg = await getRequestConfig({ requestLocale: Promise.resolve("en") });
    expect(cfg.messages.common.loading).toBe("Loading");
  });

  it("未知 locale 降级到 zh", async () => {
    vi.doMock("../messages/zh.json", () => ({ default: { common: { loading: "加载中" } } }));
    const { default: getRequestConfig } = await import("./request");
    const cfg = await getRequestConfig({ requestLocale: Promise.resolve("fr" as any) });
    expect(cfg.locale).toBe("zh");
  });
});
```

- [ ] **Step 2: 跑测试看 red**

```bash
cd web
bun run test i18n/request
```

Expected: FAIL `Cannot find module './request'`

- [ ] **Step 3: 创建 messages 目录 + 空文件**

```bash
mkdir -p web/messages
echo '{}' > web/messages/zh.json
echo '{}' > web/messages/en.json
```

- [ ] **Step 4: 实现 request.ts**

```typescript
// web/i18n/request.ts
import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;
  if (!locale || !routing.locales.includes(locale as "zh" | "en")) {
    locale = routing.defaultLocale;
  }
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
```

- [ ] **Step 5: 跑测试看 green**

```bash
cd web
bun run test i18n/request
```

Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add web/i18n/request.ts web/i18n/request.test.ts web/messages/
git commit -m "feat(i18n): request config loads locale messages with zh fallback"
```

---

### Task 1.4: 写 provider.tsx + 测试

**Files:**
- Create: `web/i18n/provider.tsx`
- Create: `web/i18n/provider.test.tsx`

- [ ] **Step 1: 写失败的测试**

```tsx
// web/i18n/provider.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { I18nProvider } from "./provider";

const messages = { common: { loading: "加载中" }, en: { common: { loading: "Loading" } } } as any;

describe("I18nProvider", () => {
  it("传入 messages 后子组件能用 useTranslations", () => {
    render(
      <I18nProvider locale="zh" messages={messages}>
        <NextIntlClientProvider locale="zh" messages={messages}>
          <Consumer />
        </NextIntlClientProvider>
      </I18nProvider>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("加载中");
  });
});

function Consumer() {
  // 用 next-intl 的 useTranslations 验证 messages 传透
  const t = require("next-intl").useTranslations("common");
  return <div data-testid="translated">{t("loading")}</div>;
}
```

- [ ] **Step 2: 跑测试看 red**

```bash
cd web
bun run test i18n/provider
```

Expected: FAIL `Cannot find module './provider'`

- [ ] **Step 3: 实现 provider.tsx**

```tsx
// web/i18n/provider.tsx
"use client";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";

interface Props {
  locale: string;
  messages: Record<string, unknown>;
  children: ReactNode;
}

export function I18nProvider({ locale, messages, children }: Props) {
  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}
```

- [ ] **Step 4: 跑测试看 green**

```bash
cd web
bun run test i18n/provider
```

Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add web/i18n/provider.tsx web/i18n/provider.test.tsx
git commit -m "feat(i18n): I18nProvider wrapper for NextIntlClientProvider"
```

---

### Task 1.5: 写 middleware.ts (locale 检测 + 重定向)

**Files:**
- Create: `web/middleware.ts`

- [ ] **Step 1: 实现 middleware.ts**

```typescript
// web/middleware.ts
import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // 匹配所有路径除了 api, _next, _vercel, 静态文件
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
```

- [ ] **Step 2: 验证 middleware 编译过**

```bash
cd web
bun run typecheck
```

Expected: 无 `i18n/middleware` 相关错误

- [ ] **Step 3: 启动 dev 验证根路径重定向**

```bash
cd web
bun run dev
# 浏览器打开 http://localhost:3000/
# 预期: 自动重定向到 http://localhost:3000/zh
```

- [ ] **Step 4: Commit**

```bash
git add web/middleware.ts
git commit -m "feat(i18n): middleware redirects / to /zh"
```

---

## Phase 2: 消息文件 (2 任务)

### Task 2.1: 创建 messages/zh.json 骨架

**Files:**
- Create: `web/messages/zh.json` (覆盖)

- [ ] **Step 1: 写完整 zh.json (按 spec 第 4 节结构)**

```json
{
  "common": {
    "loading": "加载中…",
    "error": "出错了",
    "retry": "重试",
    "empty": "暂无数据",
    "previous": "上一页",
    "next": "下一页",
    "save": "保存",
    "cancel": "取消",
    "delete": "删除",
    "confirm": "确认",
    "submit": "提交",
    "back": "返回",
    "search": "搜索",
    "filter": "筛选"
  },
  "nav": {
    "chat": "对话",
    "output": "文档结构化",
    "knowledge": "知识库",
    "evaluate": "评估",
    "decode": "型号解析"
  },
  "footer": "RAG · 德源通泰 · 2026",
  "knowledge": {
    "nodes": {
      "title": "节点列表",
      "subtitle": "Neo4j 图数据库中的实体节点",
      "column": { "id": "编号", "type": "类型", "name": "名称", "props": "属性" }
    },
    "relations": {
      "title": "关系列表",
      "subtitle": "Neo4j 图数据库中的实体关系",
      "column": { "type": "类型", "src": "起点", "arrow": "→", "dst": "终点", "props": "属性" }
    },
    "documents": {
      "title": "向量库",
      "subtitle": "Dify 知识库文档管理",
      "stat": { "documents": "文档数", "datasets": "数据集" },
      "entry": { "qa": "录 QA 对", "import": "批量导入" }
    },
    "qa": {
      "title": "向量库 · QA 录入",
      "subtitle": "录 QA 对",
      "form": { "question": "问题", "answer": "答案", "tags": "标签 (逗号分隔)", "syncToNeo4j": "同步到 Neo4j" },
      "action": { "submit": "录入 Dify", "test": "录入 + 立即测试", "submitting": "提交中…" },
      "validation": { "questionMin": "问题至少 2 字", "answerMin": "答案至少 2 字" }
    },
    "triples": {
      "title": "三元组录入",
      "subtitle": "向 Neo4j 写入实体关系"
    },
    "import": {
      "title": "批量导入",
      "subtitle": "从 Excel/JSON 解析 QA 行",
      "action": { "commit": "提交到 Dify" }
    },
    "batch": {
      "title": "后台批量任务"
    }
  },
  "evaluate": {
    "list": { "title": "评估历史" },
    "new": { "title": "新建评估" },
    "detail": { "title": "评估详情" }
  },
  "output": {
    "list": { "title": "输出文件" },
    "new": { "title": "新建摄取" }
  },
  "chat": {
    "composer": { "placeholder": "输入消息, Enter 发送, Shift+Enter 换行", "streaming": "AI 正在回复…" }
  },
  "decode": {
    "title": "产品订货号解码",
    "placeholder": "1LE0001-1AA42-1AA4",
    "button": "解码",
    "buttonLoading": "解码中..."
  },
  "settings": {
    "title": "设置",
    "theme": "主题",
    "language": "语言",
    "account": "账号"
  }
}
```

- [ ] **Step 2: 验证 JSON 合法**

```bash
cd web
node -e "JSON.parse(require('fs').readFileSync('messages/zh.json'))" && echo "valid"
```

Expected: `valid`

- [ ] **Step 3: Commit**

```bash
git add web/messages/zh.json
git commit -m "feat(i18n): zh.json skeleton with common/nav/page strings"
```

---

### Task 2.2: 创建 messages/en.json 完整翻译

**Files:**
- Create: `web/messages/en.json`

- [ ] **Step 1: 写完整 en.json**

```json
{
  "common": {
    "loading": "Loading…",
    "error": "Something went wrong",
    "retry": "Retry",
    "empty": "No data",
    "previous": "Previous",
    "next": "Next",
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "confirm": "Confirm",
    "submit": "Submit",
    "back": "Back",
    "search": "Search",
    "filter": "Filter"
  },
  "nav": {
    "chat": "Chat",
    "output": "Output",
    "knowledge": "Knowledge",
    "evaluate": "Evaluate",
    "decode": "Decode"
  },
  "footer": "RAG · Deyuan Tongtai · 2026",
  "knowledge": {
    "nodes": {
      "title": "Node List",
      "subtitle": "Entity nodes in Neo4j graph database",
      "column": { "id": "ID", "type": "Type", "name": "Name", "props": "Properties" }
    },
    "relations": {
      "title": "Relation List",
      "subtitle": "Entity relations in Neo4j graph database",
      "column": { "type": "Type", "src": "Source", "arrow": "→", "dst": "Target", "props": "Properties" }
    },
    "documents": {
      "title": "Vector Store",
      "subtitle": "Dify knowledge base document management",
      "stat": { "documents": "Documents", "datasets": "Datasets" },
      "entry": { "qa": "Add QA", "import": "Bulk Import" }
    },
    "qa": {
      "title": "Vector Store · QA Entry",
      "subtitle": "Add QA pairs",
      "form": { "question": "Question", "answer": "Answer", "tags": "Tags (comma-separated)", "syncToNeo4j": "Sync to Neo4j" },
      "action": { "submit": "Submit to Dify", "test": "Submit + Test", "submitting": "Submitting…" },
      "validation": { "questionMin": "Question must be at least 2 chars", "answerMin": "Answer must be at least 2 chars" }
    },
    "triples": {
      "title": "Triple Entry",
      "subtitle": "Write entity relations to Neo4j"
    },
    "import": {
      "title": "Bulk Import",
      "subtitle": "Parse QA rows from Excel/JSON",
      "action": { "commit": "Commit to Dify" }
    },
    "batch": {
      "title": "Background Batch Tasks"
    }
  },
  "evaluate": {
    "list": { "title": "Evaluation History" },
    "new": { "title": "New Evaluation" },
    "detail": { "title": "Evaluation Detail" }
  },
  "output": {
    "list": { "title": "Output Files" },
    "new": { "title": "New Ingest" }
  },
  "chat": {
    "composer": { "placeholder": "Type a message, Enter to send, Shift+Enter for newline", "streaming": "AI is replying…" }
  },
  "decode": {
    "title": "Product Order No. Decode",
    "placeholder": "1LE0001-1AA42-1AA4",
    "button": "Decode",
    "buttonLoading": "Decoding..."
  },
  "settings": {
    "title": "Settings",
    "theme": "Theme",
    "language": "Language",
    "account": "Account"
  }
}
```

- [ ] **Step 2: 验证两文件 key 一致**

```bash
cd web
node -e "
const zh = require('./messages/zh.json');
const en = require('./messages/en.json');
const flat = (o, p='') => Object.entries(o).flatMap(([k,v]) => v && typeof v === 'object' ? flat(v, p+k+'.') : [p+k]);
const zhKeys = flat(zh).sort();
const enKeys = flat(en).sort();
const missing = zhKeys.filter(k => !enKeys.includes(k));
const extra = enKeys.filter(k => !zhKeys.includes(k));
console.log('zh keys:', zhKeys.length, 'en keys:', enKeys.length);
console.log('missing in en:', missing);
console.log('extra in en:', extra);
"
```

Expected: `zh keys: N` `en keys: N` `missing in en: []` `extra in en: []`

- [ ] **Step 3: Commit**

```bash
git add web/messages/en.json
git commit -m "feat(i18n): en.json translation matching zh keys"
```

---

## Phase 3: 页面迁移 (3 任务)

### Task 3.1: 移动所有 20 个页面到 app/[locale]/

**Files:**
- Move: 20 个 page.tsx 从 `app/<name>/page.tsx` → `app/[locale]/<name>/page.tsx`
- Delete: 旧路径

⚠️ **顺序很重要**：用 `git mv` 而不是 `mv`，保留 git 历史。

- [ ] **Step 1: 创建目标目录 + 移动文件**

```bash
cd web
mkdir -p "app/[locale]"

# 用 git mv 逐个移动, 保留历史
git mv app/page.tsx             "app/[locale]/page.tsx"
git mv app/chat/page.tsx        "app/[locale]/chat/page.tsx"
git mv app/decode/page.tsx      "app/[locale]/decode/page.tsx"
git mv app/evaluate/page.tsx    "app/[locale]/evaluate/page.tsx"
git mv "app/evaluate/[id]/page.tsx"      "app/[locale]/evaluate/[id]/page.tsx"
git mv "app/evaluate/new/page.tsx"       "app/[locale]/evaluate/new/page.tsx"
git mv app/knowledge/page.tsx   "app/[locale]/knowledge/page.tsx"
git mv app/knowledge/batch/page.tsx     "app/[locale]/knowledge/batch/page.tsx"
git mv "app/knowledge/dataset-documents/[dataset_id]/page.tsx" "app/[locale]/knowledge/dataset-documents/[dataset_id]/page.tsx"
git mv app/knowledge/datasets/page.tsx  "app/[locale]/knowledge/datasets/page.tsx"
git mv app/knowledge/documents/page.tsx "app/[locale]/knowledge/documents/page.tsx"
git mv app/knowledge/documents/import/page.tsx "app/[locale]/knowledge/documents/import/page.tsx"
git mv app/knowledge/graph/page.tsx    "app/[locale]/knowledge/graph/page.tsx"
git mv app/knowledge/nodes/page.tsx    "app/[locale]/knowledge/nodes/page.tsx"
git mv app/knowledge/qa/page.tsx       "app/[locale]/knowledge/qa/page.tsx"
git mv app/knowledge/relations/page.tsx "app/[locale]/knowledge/relations/page.tsx"
git mv app/knowledge/triples/page.tsx  "app/[locale]/knowledge/triples/page.tsx"
git mv app/output/page.tsx     "app/[locale]/output/page.tsx"
git mv "app/output/[task_id]/page.tsx" "app/[locale]/output/[task_id]/page.tsx"
git mv "app/output/[task_id]/[file]/page.tsx" "app/[locale]/output/[task_id]/[file]/page.tsx"
git mv app/output/new/page.tsx "app/[locale]/output/new/page.tsx"
```

- [ ] **Step 2: 验证移动成功**

```bash
cd web
git status | grep "renamed" | wc -l
# Expected: 20
```

- [ ] **Step 3: 同时移动对应测试文件**

```bash
cd web
# 找所有 .test.tsx 跟 page.tsx 在同目录的, 一起移动
# 用 git mv (跟上面 page.tsx 路径一致)
for test in $(find "app/[locale]" -name "page.test.tsx"); do
  echo "found test: $test"
done
# 期望: 应该有 6 个 page.test.tsx (decode, output, qa, knowledge, dataset-documents, knowledge/qa 等)
```

手动移动 (举例):
```bash
git mv "app/decode/page.test.tsx"  "app/[locale]/decode/page.test.tsx"
git mv "app/output/page.test.tsx"  "app/[locale]/output/page.test.tsx"
# 等等, 对照上面 page.tsx 移动过的路径
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(i18n): move 20 pages to app/[locale]/ for i18n routing"
```

---

### Task 3.2: 移动 app/layout.tsx → app/[locale]/layout.tsx

**Files:**
- Move: `app/layout.tsx` → `app/[locale]/layout.tsx`
- Modify: 新 `app/[locale]/layout.tsx` — `<html lang="zh">` → `<html lang={locale}>`, 加 `<I18nProvider>`

- [ ] **Step 1: 移动 layout.tsx**

```bash
cd web
git mv app/layout.tsx "app/[locale]/layout.tsx"
```

- [ ] **Step 2: 改 [locale]/layout.tsx — 加 locale 参数 + I18nProvider**

> **重要前提**: 当前 `app/layout.tsx` **已经没有内联 `Header()` / `NavLink()` / `Footer()` 函数**。这些都已经抽到 `web/components/header.tsx` (主题系统重构时迁移)。
>
> 新 `[locale]/layout.tsx` 只需要:
> 1. 从 `@/components/header` 导入 `Header`
> 2. 在 `<ThemeProvider>` 内嵌套 `<I18nProvider>` 包 `<Header />` + `<main>` + footer

完整新文件内容:

```tsx
// app/[locale]/layout.tsx
import { notFound } from "next/navigation";
import { getMessages, setRequestLocale } from "next-intl/server";
import { Geist, JetBrains_Mono } from "next/font/google";
import { I18nProvider } from "@/i18n/provider";
import { SWRProvider } from "@/lib/api/swr-provider";
import { Header } from "@/components/header";
import { ThemeProvider } from "@/components/theme-provider";
import { themes } from "@/lib/theme";
import { routing } from "@/i18n/routing";
import "./globals.css";

// UI 字体
const geistSans = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
});

// 数字/代码
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata = {
  title: "RAG 管理后台",
  description: "产品订货号解析 + 知识库管理 + 知识图谱",
};

// 启用 next-intl 静态生成
export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as "zh" | "en")) notFound();
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${geistSans.variable} ${jetbrainsMono.variable}`}
      data-scroll-behavior="smooth"
    >
      <body className="bg-paper flex h-screen flex-col overflow-x-hidden overflow-y-hidden text-foreground antialiased">
        {/* ThemeProvider 必须在最外层 (它给 <html> 挂 class); I18nProvider 嵌套其内 */}
        <ThemeProvider
          attribute="class"
          themes={themes.map((t) => t.name)}
          defaultTheme="system"
          enableSystem
        >
          <I18nProvider locale={locale} messages={messages}>
            <Header />
            <main className="w-full flex-1 min-h-0 overflow-hidden px-12 py-12">
              <SWRProvider>{children}</SWRProvider>
            </main>
            <footer className="shrink-0 border-t border-border/40 px-4 py-6">
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span className="eyebrow">{/* i18n key: footer — Phase 4 Task 4.1 替换 */}RAG · 德源通泰 · 2026</span>
              </div>
            </footer>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

**要点**:
- `Header` 是个 client component (用 `useState` 控制 SettingsDialog), 直接 `<Header />` 即可
- 老的 inline `<header>` + inline `<footer>` 在 `app/layout.tsx` 已经删除, 新文件不要再写
- footer 直接用 `<footer>` 标签, 不抽组件, 因为 Phase 4 Task 4.1 只是改文案

- [ ] **Step 3: 跑 typecheck**

```bash
cd web
bun run typecheck
```

Expected: 0 errors

- [ ] **Step 4: 启动 dev 验证路由**

```bash
cd web
bun run dev
# 浏览器打开 http://localhost:3000/zh → 应渲染主页
# 浏览器打开 http://localhost:3000/en → 应渲染英文主页
```

- [ ] **Step 5: Commit**

```bash
git add "app/[locale]/layout.tsx"
git commit -m "refactor(i18n): move layout to [locale] and wrap I18nProvider"
```

---

### Task 3.3: 写 LocalizedLink 包装 + Header 改用 (页面替换推到 Phase 4)

**Files:**
- Create: `web/components/i18n/LocalizedLink.tsx`
- Create: `web/components/i18n/LocalizedLink.test.tsx`
- Modify: `web/components/header.tsx`

> **设计原则**: 不在每个 page 里 `useLocale() + withLocale()`, 而是封装一个 `<LocalizedLink>` 组件, 内部用 `useLocale()` 拿 locale, 包 next/link `<Link>`, 自动给 href 加前缀。
>
> Phase 4 (t() 替换) 顺手把每个 page 里的 `<Link>` 换成 `<LocalizedLink>`, 不在 Task 3.3 一次性改 20 个文件。

**Steps:**

#### Step 1: 写失败的测试 (TDD red)

Create `web/components/i18n/LocalizedLink.test.tsx`:

```tsx
// web/components/i18n/LocalizedLink.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { LocalizedLink } from "./LocalizedLink";

const messages = { "测试": "测试" } as any;

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a>,
}));

describe("LocalizedLink", () => {
  it("zh locale 自动加 /zh 前缀", () => {
    render(
      <NextIntlClientProvider locale="zh" messages={messages}>
        <LocalizedLink href="/knowledge">知识库</LocalizedLink>
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("知识库").closest("a")).toHaveAttribute("href", "/zh/knowledge");
  });

  it("en locale 自动加 /en 前缀", () => {
    render(
      <NextIntlClientProvider locale="en" messages={messages}>
        <LocalizedLink href="/output">Output</LocalizedLink>
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("Output").closest("a")).toHaveAttribute("href", "/en/output");
  });

  it("已含 locale 前缀时不去重", () => {
    render(
      <NextIntlClientProvider locale="zh" messages={messages}>
        <LocalizedLink href="/zh/knowledge">知识库</LocalizedLink>
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("知识库").closest("a")).toHaveAttribute("href", "/zh/knowledge");
  });

  it("根路径 / → /zh", () => {
    render(
      <NextIntlClientProvider locale="zh" messages={messages}>
        <LocalizedLink href="/">Home</LocalizedLink>
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("Home").closest("a")).toHaveAttribute("href", "/zh");
  });
});
```

#### Step 2: 跑测试看 red

```bash
cd web
bun run test i18n/LocalizedLink
```

Expected: FAIL `Cannot find module './LocalizedLink'`

#### Step 3: 实现 LocalizedLink.tsx

```tsx
// web/components/i18n/LocalizedLink.tsx
"use client";
import Link from "next/link";
import { useLocale } from "next-intl";
import type { ComponentProps } from "react";

type Props = ComponentProps<typeof Link>;

/** 内部用 useLocale 拿 locale, 自动给 href 加 /<locale> 前缀 */
export function LocalizedLink({ href, children, ...rest }: Props) {
  const locale = useLocale();
  const localizedHref = prependLocale(locale, href as string);
  return (
    <Link href={localizedHref} {...rest}>
      {children}
    </Link>
  );
}

function prependLocale(locale: string, path: string): string {
  if (!path || path === "/") return `/${locale}`;
  if (path.startsWith(`/${locale}/`) || path === `/${locale}`) return path;
  return `/${locale}${path}`;
}
```

#### Step 4: 跑测试看 green

```bash
cd web
bun run test i18n/LocalizedLink
```

Expected: PASS (4 tests)

#### Step 5: 改 Header 用 LocalizedLink

```diff
  // web/components/header.tsx
- import Link from "next/link";
+ import { LocalizedLink } from "@/components/i18n/LocalizedLink";
  
  // NavLink 内:
  function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
-   return <Link href={href} ...>{children}</Link>
+   return <LocalizedLink href={href} ...>{children}</LocalizedLink>
  }
  
  // 品牌 logo:
- <Link href="/">RAG · 德源通泰</Link>
+ <LocalizedLink href="/">RAG · 德源通泰</LocalizedLink>
```

#### Step 6: 跑 Header 测试 + 全套

```bash
cd web
bun run test header
bun run test
```

Expected: 2 header tests pass, no regression

#### Step 7: Commit

```bash
git add web/components/i18n/LocalizedLink.tsx web/components/i18n/LocalizedLink.test.tsx web/components/header.tsx
git commit -m "refactor(i18n): LocalizedLink wrapper auto-prefixes href; Header uses it (page swaps deferred to Phase 4)"
```

---

## Phase 4: 页面 t() 替换 (5 任务, 按业务域分批)

### Task 4.1: Header (在 `web/components/header.tsx`) + Footer (在 `app/[locale]/layout.tsx`)

**Files:**
- Modify: `web/components/header.tsx` (Header 翻译 nav 链接)
- Modify: `app/[locale]/layout.tsx` (Footer 文案翻译)
- Modify: `web/components/header.test.tsx` (加语言切换断言, 已存在 2 个 test)

> **Header 已经抽到独立文件** (Phase 3.2 改 layout 时, 头只是 `<Header />` 一行), 所以翻译 nav 链接的代码改动全部在 `header.tsx`。

> **同时**: 把 page.tsx 里的 `<Link href="/...">` 换成 `<LocalizedLink href="/...">` (来自 `@/components/i18n/LocalizedLink`)。Phase 3 Task 3.3 创建了这个 wrapper, 此处批量应用。

- [ ] **Step 1: Header 改用 t("nav.xxx")**

```diff
  // web/components/header.tsx
  "use client";
  import { useState } from "react";
+ import { useTranslations, useLocale } from "next-intl";
  import Link from "next/link";
+ import { withLocale } from "@/i18n/link-helper";
  import { HealthDot } from "@/components/knowledge/HealthDot";
  import { EnvBadge } from "@/components/knowledge/EnvBadge";
  import { ThemeToggle } from "@/components/settings/theme-toggle";
  import { SettingsDialog } from "@/components/settings/settings-dialog";

  export function Header() {
    const [settingsOpen, setSettingsOpen] = useState(false);
+   const t = useTranslations("nav");
+   const locale = useLocale();

    return (
      <>
        <header className="...">
          <div className="...">
            <Link href={withLocale(locale, "/")} className="...">
              RAG<span className="text-clay"> · </span>德源通泰
            </Link>
            <nav className="ml-auto flex items-center gap-1 text-base">
-             <NavLink href="/chat">对话</NavLink>
-             <NavLink href="/output">文档结构化</NavLink>
-             <NavLink href="/knowledge">知识库</NavLink>
-             <NavLink href="/evaluate">评估</NavLink>
-             <NavLink href="/decode">型号解析</NavLink>
+             <NavLink href={withLocale(locale, "/chat")}>{t("chat")}</NavLink>
+             <NavLink href={withLocale(locale, "/output")}>{t("output")}</NavLink>
+             <NavLink href={withLocale(locale, "/knowledge")}>{t("knowledge")}</NavLink>
+             <NavLink href={withLocale(locale, "/evaluate")}>{t("evaluate")}</NavLink>
+             <NavLink href={withLocale(locale, "/decode")}>{t("decode")}</NavLink>
            </nav>
            {/* ThemeToggle / EnvBadge / HealthDot 不动 */}
          </div>
        </header>
        <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
      </>
    );
  }
```

- [ ] **Step 2: Footer 改用 t("footer")** (在 `app/[locale]/layout.tsx`)

```diff
  // app/[locale]/layout.tsx — footer 在 layout 里直接写
  <footer className="...">
    <div className="...">
-     <span className="eyebrow">RAG · 德源通泰 · 2026</span>
+     <span className="eyebrow">{t("footer")}</span>
    </div>
  </footer>
```

注意 footer 在 server component (layout 是 async), 用 `getTranslations` (server):

```tsx
// app/[locale]/layout.tsx 顶部
import { getTranslations } from "next-intl/server";

// 在 LocaleLayout 组件里
const t = await getTranslations();
```

- [ ] **Step 3: 写测试 — Header 语言切换断言** (在 `web/components/header.test.tsx`)

文件已存在 (2 个 test), 追加语言切换断言:

```tsx
// web/components/header.test.tsx — 追加
import { NextIntlClientProvider } from "next-intl";
import enMessages from "@/messages/en.json";
import zhMessages from "@/messages/zh.json";

it("zh locale 显示中文 nav 链接", () => {
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <Header />
    </NextIntlClientProvider>,
  );
  expect(screen.getByText("对话")).toBeInTheDocument();
  expect(screen.getByText("知识库")).toBeInTheDocument();
});

it("en locale 显示英文 nav 链接", () => {
  render(
    <NextIntlClientProvider locale="en" messages={enMessages}>
      <Header />
    </NextIntlClientProvider>,
  );
  expect(screen.getByText("Chat")).toBeInTheDocument();
  expect(screen.getByText("Knowledge")).toBeInTheDocument();
});
```

- [ ] **Step 4: 跑测试**

```bash
cd web
bun run test header
```

Expected: PASS (4 tests: 原 2 + 新增 2)

- [ ] **Step 5: 手动验证**

```bash
cd web
bun run dev
# 打开 /zh/ → nav 是"对话, 文档结构化, 知识库..."
# 打开 /en/ → nav 是"Chat, Output, Knowledge..."
```

- [ ] **Step 6: Commit**

```bash
git add web/components/header.tsx web/components/header.test.tsx "app/[locale]/layout.tsx"
git commit -m "feat(i18n): translate header nav + footer with t()"
```

---

### Task 4.2: knowledge 域 (8 个 page + 共享组件)

**Files:**
- Modify: 8 个 page.tsx 在 `app/[locale]/knowledge/`
- 共享组件: `KnowledgeHero`, `DatasetSwitcher`, `DomainSwitcher`, `SchemaFieldRenderer`, `SchemaBrowser` 等

⚠️ **工作量**: 这是 678 处提取里最大的一块。建议拆成 2-3 个 commit (按子目录)。

> **同时**: 把 page.tsx 里的 `<Link href="/...">` 换成 `<LocalizedLink href="/...">` (来自 `@/components/i18n/LocalizedLink`)。Phase 3 Task 3.3 创建了这个 wrapper, 此处批量应用。

- [ ] **Step 1: knowledge/page.tsx (仪表盘)**

逐个替换硬编码中文:
- "向量库" → `t("knowledge.documents.title")`
- "Datasets" / "数据集" → `t("knowledge.documents.stat.datasets")`
- 4 个 EntryCard 标题/描述 → `t("knowledge.documents.entry.*")` + `t("knowledge.nodes.title")` etc.

- [ ] **Step 2: knowledge/nodes/page.tsx + 共享 Node 组件**

- [ ] **Step 3: knowledge/relations/page.tsx + Relation 组件**

- [ ] **Step 4: knowledge/datasets/page.tsx + knowledge/dataset-documents/[id]/page.tsx**

- [ ] **Step 5: knowledge/qa/page.tsx (有表单 + 验证信息)**

- [ ] **Step 6: knowledge/triples/page.tsx + knowledge/import/page.tsx**

- [ ] **Step 7: knowledge/batch/page.tsx + knowledge/documents/page.tsx + knowledge/graph/page.tsx**

- [ ] **Step 8: 写每个 page.test.tsx 加语言切换断言**

举例 `app/[locale]/knowledge/nodes/page.test.tsx` 加:

```tsx
import enMessages from "@/messages/en.json";
import { NextIntlClientProvider } from "next-intl";

it("en locale 显示英文 title", () => {
  render(
    <NextIntlClientProvider locale="en" messages={enMessages}>
      <NodesPage />
    </NextIntlClientProvider>,
  );
  expect(screen.getByText("Node List")).toBeInTheDocument();
});
```

- [ ] **Step 9: 跑全套测试**

```bash
cd web
bun run test
```

Expected: 所有 page.test.tsx 通过, 包含语言切换断言

- [ ] **Step 10: Commit (按子目录分批)**

```bash
git add "app/[locale]/knowledge/nodes/" "app/[locale]/knowledge/relations/"
git commit -m "feat(i18n): translate knowledge nodes/relations pages"

git add "app/[locale]/knowledge/qa/" "app/[locale]/knowledge/triples/" "app/[locale]/knowledge/documents/"
git commit -m "feat(i18n): translate knowledge qa/triples/documents pages"

git add "app/[locale]/knowledge/datasets/" "app/[locale]/knowledge/dataset-documents/" "app/[locale]/knowledge/import/" "app/[locale]/knowledge/batch/" "app/[locale]/knowledge/graph/" "app/[locale]/knowledge/"
git commit -m "feat(i18n): translate remaining knowledge pages"
```

---

### Task 4.3: evaluate 域 (3 个 page)

**Files:**
- Modify: `app/[locale]/evaluate/page.tsx`, `[id]/page.tsx`, `new/page.tsx`
- Modify: `app/[locale]/evaluate/page.tsx` 的内联 `fmtDate()` — 改用 `Intl.DateTimeFormat(locale)`

> **同时**: 把 page.tsx 里的 `<Link href="/...">` 换成 `<LocalizedLink href="/...">` (来自 `@/components/i18n/LocalizedLink`)。Phase 3 Task 3.3 创建了这个 wrapper, 此处批量应用。

- [ ] **Step 1: evaluate/page.tsx 标题 + 列头 + StatusBadge 标签**

- [ ] **Step 2: 把 fmtDate 改成 locale 感知**

```diff
- function fmtDate(iso: string): string {
-   const d = new Date(iso);
-   const m = String(d.getMonth() + 1).padStart(2, "0");
-   const day = String(d.getDate()).padStart(2, "0");
-   const hh = String(d.getHours()).padStart(2, "0");
-   const mm = String(d.getMinutes()).padStart(2, "0");
-   return `${m}-${day} ${hh}:${mm}`;
- }
+ function fmtDate(iso: string, locale: string): string {
+   return new Intl.DateTimeFormat(locale, {
+     month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
+   }).format(new Date(iso));
+ }
```

调用处:
```diff
- <span>{fmtDate(r.created_at)}</span>
+ <span>{fmtDate(r.created_at, locale)}</span>
```

- [ ] **Step 3: evaluate/[id]/page.tsx + evaluate/new/page.tsx**

- [ ] **Step 4: 加语言切换测试**

- [ ] **Step 5: Commit**

```bash
git add "app/[locale]/evaluate/"
git commit -m "feat(i18n): translate evaluate pages + locale-aware fmtDate"
```

---

### Task 4.4: output 域 (4 个 page)

**Files:**
- Modify: `app/[locale]/output/page.tsx`, `new/page.tsx`, `[task_id]/page.tsx`, `[task_id]/[file]/page.tsx`

> **同时**: 把 page.tsx 里的 `<Link href="/...">` 换成 `<LocalizedLink href="/...">` (来自 `@/components/i18n/LocalizedLink`)。Phase 3 Task 3.3 创建了这个 wrapper, 此处批量应用。

- [ ] **Step 1: output/page.tsx 列表 + 空态 + 错误**

- [ ] **Step 2: output/new/page.tsx 上传表单**

- [ ] **Step 3: output/[task_id]/page.tsx 任务详情**

- [ ] **Step 4: output/[task_id]/[file]/page.tsx 文件详情**

- [ ] **Step 5: 加语言切换测试**

- [ ] **Step 6: Commit**

```bash
git add "app/[locale]/output/"
git commit -m "feat(i18n): translate output pages"
```

---

### Task 4.5: chat + decode 域 + 共享组件

**Files:**
- Modify: `app/[locale]/chat/page.tsx`, `decode/page.tsx`
- Modify: `components/chat/Composer.tsx` (placeholder)
- Modify: `components/chat/ChatShell.tsx`, `MessageBubble.tsx`, `ConversationList.tsx`
- Modify: 共享组件 `StatusBadge`, `TaskStatusBadge`, `HealthDot`, `EnvBadge`, `SampleTable`, `pagination.tsx`

> **同时**: 把 page.tsx 里的 `<Link href="/...">` 换成 `<LocalizedLink href="/...">` (来自 `@/components/i18n/LocalizedLink`)。Phase 3 Task 3.3 创建了这个 wrapper, 此处批量应用。

- [ ] **Step 1: decode/page.tsx (标题 + placeholder + 按钮)**

- [ ] **Step 2: chat/page.tsx + Composer.tsx (placeholder 翻译)**

- [ ] **Step 3: ConversationList formatRelativeTime 改 Intl.RelativeTimeFormat**

```diff
- function formatRelativeTime(ts: number): string {
-   // 硬编码中文: "刚刚", "X 分钟前", "X 小时前", "X 天前"
- }
+ function formatRelativeTime(ts: number, locale: string): string {
+   const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
+   const diffSec = (ts - Date.now()) / 1000;
+   if (Math.abs(diffSec) < 60) return rtf.format(0, "second");
+   if (Math.abs(diffSec) < 3600) return rtf.format(Math.round(diffSec / 60), "minute");
+   if (Math.abs(diffSec) < 86400) return rtf.format(Math.round(diffSec / 3600), "hour");
+   return rtf.format(Math.round(diffSec / 86400), "day");
+ }
```

- [ ] **Step 4: 共享组件: StatusBadge / TaskStatusBadge / SampleTable / pagination.tsx**

- [ ] **Step 5: 加语言切换测试**

- [ ] **Step 6: Commit**

```bash
git add "app/[locale]/decode/" "app/[locale]/chat/" "components/chat/" "components/evaluate/" "components/ui/pagination.tsx"
git commit -m "feat(i18n): translate chat/decode pages + shared components"
```

---

## Phase 5: 日期/数字格式 + 细节 (1 任务)

### Task 5.1: animated.tsx CountUp locale 感知

**Files:**
- Modify: `components/ui/animated.tsx`

- [ ] **Step 1: CountUp 改用 locale**

```diff
- {value.toLocaleString("en-US")}
+ {value.toLocaleString(locale)}
```

需要从 `useLocale()` 拿 locale:

```tsx
"use client";
import { useLocale } from "next-intl";

export function CountUp({ value, ... }: Props) {
  const locale = useLocale();
  // ...
  return <span>{value.toLocaleString(locale)}</span>;
}
```

- [ ] **Step 2: 写测试**

```tsx
// components/ui/animated.test.tsx (新建)
it("CountUp zh locale 用中文千分位", () => {
  render(<CountUp value={1234} />, { wrapper: intlWrapper("zh") });
  expect(screen.getByText("1,234")).toBeInTheDocument();
});
```

- [ ] **Step 3: Commit**

```bash
git add components/ui/animated.tsx components/ui/animated.test.tsx
git commit -m "feat(i18n): CountUp locale-aware number formatting"
```

---

## Phase 6: SettingsDialog 联动 (1 任务)

### Task 6.1: 激活 SettingsDialog 的 "语言" 行

**Files:**
- Modify: `web/components/settings/settings-dialog.tsx`
- Modify: `web/components/settings/settings-dialog.test.tsx` (已存在 5 个 test, 需调整)

> **现状**: `web/components/settings/settings-dialog.tsx` 已存在, 主题行 (活), 语言行 (Badge "中文" + opacity-60 disabled), 账号行 (Badge "admin" + opacity-60 disabled)。
>
> **本次任务**: 把语言行从 disabled 改为可交互的 `<Select>` (zh / en), 切语言时 `router.push(/<newLocale>/<currentPath>)` + 设 cookie。账号行保持 disabled (per spec, 占位)。

- [ ] **Step 1: 改 settings-dialog.tsx — 语言行从 Badge → Select**

```diff
  // web/components/settings/settings-dialog.tsx
  "use client";
- // SettingsDialog — 设置弹框 (2026-06-11)
- //   主题切换 (活) / 语言 (占位) / 账号 (占位)
+ // SettingsDialog — 设置弹框 (2026-06-11)
+ //   主题切换 (活) / 语言切换 (活) / 账号 (占位)
  import { useTheme } from "next-themes";
+ import { useLocale, useTranslations } from "next-intl";
+ import { useRouter, usePathname } from "next/navigation";
  import { AppDialog } from "@/components/common/dialog/app-dialog";
  import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
  import { Badge } from "@/components/ui/badge";
  import { themes } from "@/lib/theme";

  interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
  }

  export function SettingsDialog({ open, onOpenChange }: Props) {
    const { theme, setTheme } = useTheme();
+   const router = useRouter();
+   const pathname = usePathname();
+   const currentLocale = useLocale();
+   const t = useTranslations("settings");

    const handleLocaleChange = (newLocale: string) => {
      if (newLocale === currentLocale) return;
      // 1. 设 cookie (持久化, 刷新后保留)
      document.cookie = `NEXT_LOCALE=${newLocale}; path=/; max-age=${60 * 60 * 24 * 365}`;
      // 2. 切路径: 当前 /zh/knowledge → /en/knowledge
      const segments = pathname.split("/");
      if (segments[1] === currentLocale) {
        segments[1] = newLocale;
      } else {
        segments.splice(1, 0, newLocale);
      }
      router.push(segments.join("/") || "/");
    };

    return (
      <AppDialog
        open={open}
        onOpenChange={onOpenChange}
        title={t("title")}
        maxWidth="sm"
      >
        <div className="divide-y divide-border/40">
          {/* 行 1: 主题 (活) */}
          <div className="flex items-center justify-between px-6 py-4">
            <span className="text-sm font-medium">{t("theme")}</span>
            <Select value={theme} onValueChange={setTheme}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {themes.map((th) => (
                  <SelectItem key={th.name} value={th.name}>
                    {th.label}
                  </SelectItem>
                ))}
                <SelectItem value="system">跟随系统</SelectItem>
              </SelectContent>
            </Select>
          </div>

-         {/* 行 2: 语言 (占位 disabled) */}
-         <div className="flex items-center justify-between px-6 py-4 opacity-60">
-           <span className="text-sm font-medium">语言</span>
-           <Badge variant="outline">中文</Badge>
-         </div>
+         {/* 行 2: 语言 (活) */}
+         <div className="flex items-center justify-between px-6 py-4">
+           <span className="text-sm font-medium">{t("language")}</span>
+           <Select value={currentLocale} onValueChange={handleLocaleChange}>
+             <SelectTrigger className="w-32">
+               <SelectValue />
+             </SelectTrigger>
+             <SelectContent>
+               <SelectItem value="zh">中文</SelectItem>
+               <SelectItem value="en">English</SelectItem>
+             </SelectContent>
+           </Select>
+         </div>

          {/* 行 3: 账号 (占位 disabled — 保持不动 per spec) */}
          <div className="flex items-center justify-between px-6 py-4 opacity-60">
            <span className="text-sm font-medium">{t("account")}</span>
            <Badge variant="outline">admin</Badge>
          </div>
        </div>
      </AppDialog>
    );
  }
```

**关键点**:
- 删掉 `opacity-60` 因为语言行不再是 disabled
- 用 `useLocale()` 拿到当前 locale 作为 Select 默认值
- 切语言时: (1) 设 `NEXT_LOCALE` cookie; (2) 用 `usePathname` + `useRouter` 切路径
- `handleLocaleChange` 用 pathname 替换第一段 (即 locale 段), 不是简单 prefix 拼接 — 处理 `/zh` vs `/zh/xxx` 两种情况

- [ ] **Step 2: 改 settings-dialog.test.tsx — 调整 "disabled" 断言**

原 test 文件里有两个断言要更新:

```diff
  // web/components/settings/settings-dialog.test.tsx
  it("渲染 3 行: 主题 (活) / 语言 (活) / 账号 (disabled)", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("主题")).toBeInTheDocument();
    expect(within(dialog).getByText("语言")).toBeInTheDocument();
    expect(within(dialog).getByText("账号")).toBeInTheDocument();
  });

  it("主题 Select 存在且可交互", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("语言和账号行 — 语言是 Select (活), 账号是 disabled", () => {
    render(<SettingsDialog open={true} onOpenChange={vi.fn()} />);
    // 主题 + 语言都渲染 Select 组件 (2 个 combobox)
    const comboboxes = screen.getAllByRole("combobox");
    expect(comboboxes.length).toBe(2);
    // 账号行还是 disabled
    expect(screen.getByText("admin")).toBeInTheDocument();
  });
```

> **注意**: `useLocale` 来自 `next-intl` 需要 `NextIntlClientProvider` wrapper, 现有 test 没包, 跑会报错。需追加:
>
> ```tsx
> import { NextIntlClientProvider } from "next-intl";
> import zhMessages from "@/messages/zh.json";
>
> // 在所有 render(...) 外面包
> const renderWithI18n = (ui: React.ReactNode) =>
>   render(
>     <NextIntlClientProvider locale="zh" messages={zhMessages}>
>       {ui}
>     </NextIntlClientProvider>
>   );
> ```
>
> 把 5 个 `render(...)` 调用全改成 `renderWithI18n(...)`。

- [ ] **Step 3: 跑测试看 green**

```bash
cd web
bun run test settings-dialog
```

Expected: PASS (5 tests)

- [ ] **Step 4: 手动验证**

```bash
cd web
bun run dev
# 1. 打开 /zh/knowledge, 点齿轮 → 设置弹框
# 2. 语言行 Select 切到 English
# 3. URL 变成 /en/knowledge
# 4. nav 变成 "Chat, Output, Knowledge..."
# 5. 刷新页面: 仍然是 /en/ (cookie 持久化)
# 6. DevTools → Application → Cookies → 看到 NEXT_LOCALE=en
```

- [ ] **Step 5: Commit**

```bash
git add web/components/settings/settings-dialog.tsx web/components/settings/settings-dialog.test.tsx
git commit -m "feat(i18n): enable SettingsDialog language switcher with router.push + cookie"
```

---

## Phase 7: 收尾 (3 任务)

### Task 7.1: 跑全套测试

- [ ] **Step 1: 跑 vitest**

```bash
cd web
bun run test
```

Expected: 所有测试通过, 包含语言切换断言

- [ ] **Step 2: 跑 typecheck**

```bash
cd web
bun run typecheck
```

Expected: 0 errors

- [ ] **Step 3: 跑 lint + format**

```bash
cd web
bun run lint
bun run format:check
```

Expected: 无问题

- [ ] **Step 4: 跑契约测试 (后端)**

```bash
cd ..
uv run python -m pytest tests/test_api_contract.py -v
```

Expected: 3/3 PASS (确保 i18n 改动没碰后端)

---

### Task 7.2: 手动 E2E 验证

- [ ] **Step 1: 起 dev + 后端**

```bash
# 终端 1: 后端
cd ..
uv run python main.py

# 终端 2: 前端
cd web
bun run dev
```

- [ ] **Step 2: 浏览器走一遍**

1. `http://localhost:3000/` → 自动跳到 `/zh/`
2. nav 是中文 ("对话, 文档结构化, ...")
3. 点 `/zh/knowledge/nodes` → 显示中文 "节点列表"
4. 手动改 URL 成 `/en/knowledge/nodes` → 显示英文 "Node List"
5. 后退到 `/en/knowledge` → 仪表盘也是英文
6. cookie 验证: DevTools → Application → Cookies → `NEXT_LOCALE=en`

- [ ] **Step 3: 跑 Playwright E2E (如果有覆盖)**

```bash
cd web
bun run test:e2e
```

Expected: 所有 E2E 通过

---

### Task 7.3: 文档更新

**Files:**
- Modify: `web/CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: web/CLAUDE.md 加 i18n 章节 (放在"## 主题系统"小节**之后**)**

> web/CLAUDE.md 当前结构: 包管理 / 工具链 / 跑测试 / 跑 dev / TDD / 样式 / **主题系统 (Theme)**。在 "主题系统" 小节末尾追加 "国际化 (i18n)" 小节 (主题和 i18n 都是 provider-wrapped layout-level 系统, 放一起).

```markdown
## 国际化 (i18n)

- 用 next-intl 4.x + App Router
- 路径前缀: `/zh/...` `/en/...` (URL 强制带)
- cookie 降级: `NEXT_LOCALE`
- 消息文件: `web/messages/zh.json` + `en.json` (嵌套 JSON, key 必须一致)
- 翻译工具: `useTranslations("namespace")` (client) / `getTranslations("namespace")` (server)
- 内部链接: 用 `<LocalizedLink href="/path">` from `@/components/i18n/LocalizedLink` (自动加 /<locale> 前缀, 不要直接用 next/link `<Link>`)
- 测试 wrapper: `intlWrapper(locale)` from `web/i18n/__tests__/intl-wrapper.tsx`
- Provider 嵌套: `ThemeProvider` (outer) → `I18nProvider` (inner), 都包在 root layout
- 切换 UI: `SettingsDialog` 第二个 Select 行 → 改路径 + 设 `NEXT_LOCALE` cookie
```

- [ ] **Step 2: README.md 加"国际化"小节**

```markdown
## 国际化

- URL 前缀: `/zh/...` (默认) `/en/...`
- 切换: DevTools → Application → Cookies → 改 `NEXT_LOCALE` 刷新
- 新增翻译 key: `web/messages/zh.json` + `en.json` 必须同步, 用 `bun run test` 里的 key 一致性检查
```

- [ ] **Step 3: Commit**

```bash
git add web/CLAUDE.md README.md
git commit -m "docs(i18n): add i18n conventions to web/CLAUDE.md + README"
```

---

## 自检 (Self-Review)

✅ **Spec 覆盖**:
- next-intl 集成 ✓ Task 1.1
- 678 处提取 → Phase 4 (按业务域分批)
- `messages/zh.json` + `en.json` ✓ Task 2.1, 2.2
- SettingsDialog 启用 → ✓ Task 6.1 (激活语言行 Select + cookie + router.push)
- vitest 语言切换断言 → Task 3.3 Step 3, 4.1 Step 3, 4.2 Step 8, 4.3-4.5 都有
- 路径前缀 + cookie 降级 ✓ Task 1.5, 3.2, 6.1
- 日期/数字格式 ✓ Task 4.3 (fmtDate), 4.5 (formatRelativeTime), 5.1 (CountUp)
- Provider 嵌套顺序 ✓ Task 3.2 (ThemeProvider outer, I18nProvider inner)

✅ **No Placeholders**:
- 所有代码块都有完整内容
- 文件路径都是绝对路径
- 命令 + Expected output 都写明
- 没有 "TBD" / "TODO"

✅ **类型一致性**:
- `routing.locales: ["zh", "en"]` 在 Task 1.2 定义, Task 1.3, 1.5, 3.2, 6.1 都用
- `<LocalizedLink>` 在 Task 3.3 定义, Task 3.3 (Header) + Phase 4 (每个 page) 复用
- `prependLocale` 内部封装在 `LocalizedLink.tsx` 内, 不暴露 `withLocale` 工具函数 — 避免每页 `useLocale() + withLocale()` 重复样板
- `messages/zh.json` 嵌套结构在 Task 2.1 定义, Phase 4 所有 page + Task 6.1 都引用同名 key

✅ **LocalizedLink 封装 (避免重复)**:
- Task 3.3 创建 `web/components/i18n/LocalizedLink.tsx` 把 `useLocale() + prepend` 一次性封装
- Header 改用 `<LocalizedLink>` 做 smoke test
- Phase 4 各 sub-task (4.1, 4.2, 4.3, 4.4, 4.5) 在替换 t() 的同时, 顺手把 page.tsx 里的 `<Link>` 换成 `<LocalizedLink>` — 一次编辑完成两件事, 不需要单独再开 "改所有 href" 任务

✅ **与当前项目状态一致 (2026-06-11 sync)**:
- `web/components/header.tsx` 已存在 (client component, 拥有 SettingsDialog state) — Task 3.2 / 4.1 直接用
- `web/components/settings/settings-dialog.tsx` 已存在 (主题活, 语言/账号 disabled) — Task 6.1 改语言行
- `app/layout.tsx` 当前结构: ThemeProvider 包 body, footer 内联, Header 抽走 — Task 3.2 起点正确
- `web/CLAUDE.md` 已有"## 主题系统"小节 — Task 7.3 在它后面追加"## 国际化"
- `ahooks` 已装 (`ed27669`) — 任何未来 hooks 工作直接可用
- 17 个 commit 已在 master, 用户尚未推送 — 计划开始前 `git pull` (worktree 路径)

---

## 风险提醒

1. **路由大重构**: Phase 3 把 20 个页面移入 `[locale]/`, 影响面大. 建议开 worktree 隔离
2. **Link href 加 locale 前缀**: 通过 `<LocalizedLink>` 包装组件统一处理 (Task 3.3), Phase 4 各 sub-task 在替换 t() 时顺手把 `<Link>` 换成 `<LocalizedLink>`, 改漏一个就 404 — 一次编辑完成 t() 替换 + Link 切换, 比单独一轮全量改 Link 风险更低
3. **测试 wrapper**: 现有 page.test.tsx 大部分没包 I18nProvider, Phase 4 加翻译时需要同步加 wrapper, 不然 `useTranslations()` 报 "no provider"
4. **678 处提取**: 纯机械工作量大, 建议 Phase 4 按子目录分 5+ 个 commit 避免单 commit 过大
5. **API 路由不动**: `web/app/api/` 保留原路径, middleware matcher 已排除 `/api`
6. **LocalizedLink 是 client component**: `useLocale()` 是 client hook, 所以包装的 Link 也是 client. 任何 server component 想用它 (例如 server-rendered 列表里的链接) 需要再考虑; 当前所有 `<Link>` 在 'use client' 页面里, 没问题

---

**完成所有 task 后**: invoke `superpowers:finishing-a-development-branch` 决定 merge/PR/discard
