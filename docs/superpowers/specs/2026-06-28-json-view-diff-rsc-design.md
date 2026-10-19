# JSON 高亮 + Diff 高亮 RSC 组件 (2026-06-28)

> 起源: 2026-06-28 用户提出需要在 Next.js 前端展示 JSON 高亮和两个 JSON 的 diff 高亮, 经讨论确认用 `shiki` + `diff` 库实现, 走 React Server Component 方案
> 范围: 2 个 RSC 组件 (`JsonView` / `JsonDiff`) + 1 个共享工具 + 测试, 覆盖全部 RSC 数据驱动的 JSON 展示场景
> 不依赖: 任何其它 spec

## 1. 目标

| # | 目标 | 验收 |
|---|---|---|
| 1 | `<JsonView>` RSC 组件: 单个 JSON 语法高亮展示 | `shiki` `codeToHtml` 产出带 shiki class 的 `<pre><code>` HTML, 深/浅双主题 |
| 2 | `<JsonDiff>` RSC 组件: 两个 JSON 行级 diff, 带 +/- gutter + 红绿背景 | `diffLines` 算 diff + `shiki` 着色, 渲染成 table, 相同行无色, added 绿, removed 红 |
| 3 | 主题跟随 `theme` prop, 默认 `github-dark` | `theme='github-dark'` | `theme='github-light'` 均可显式传入 |
| 4 | 空数据 / 完全相同 / 格式错误 容错 | `null` / `undefined` / `{}` 渲染占位, 相同 JSON 显示"无差异" |
| 5 | 超大 JSON 滚动 (maxHeight) | `maxHeight` prop 控制容器高度, 超出 `overflow-auto` |
| 6 | 无新增运行时依赖 | 只用 `shiki` + `diff` |
| 7 | 组件目录 `components/json/` 独立新目录 | `json-view.tsx` + `json-diff.tsx` + `json.test.tsx` 收纳在一处 |
| 8 | TDD 顺序 | 先写测试文件 (红) → 写实现 (绿) → format → lint → typecheck → test → commit |

## 2. 非目标 (YAGNI)

- ❌ Split view (左右对照) — unified view 行级 diff 覆盖 90% 场景, split view 需额外算法对齐行号, v2 再做
- ❌ 客户端高亮/fallback — 全部走 RSC 渲染, 不走 shiki WASM 或 highlight.js 降级 (当前场景 0 客户端动态 JSON 需要高亮)
- ❌ 复制按钮 — 需要 client event handler, 由外围 `CopyButton` 包装, 组件不内嵌
- ❌ 折叠/展开 — 纯展示组件, 不做交互
- ❌ 行号 (`showLineNumbers`) — shiki `codeToHtml` 不支持行号, 需 post-process 或 custom transformer, 价值低
- ❌ Word-level diff (词级) — 行级 diff 可读性已够, 词级 diff 复杂度过高
- ❌ 主题自动检测 (`useTheme`) — RSC 无法访问客户端 theme, 由 client wrapper 传 `theme` prop; 组件默认 `github-dark`
- ❌ i18n 集成 — JSON 展示无自然语言文案, diff 空态文字不落地 i18n (后续有需要再加)
- ❌ 动画/过渡 — 纯功能性组件
- ❌ 渲染大 JSON 的虚拟化 — 当前场景 JSON 规模 < 5000 行, overflow-auto 足够

## 3. 设计

### 3.1 组件数据流

```
服务端数据 / API 响应
        │
        ▼
 page.tsx (RSC async)
   const res = await fetch(...)
   const data: unknown = await res.json()
        │
        ▼
 <JsonView data={data} theme="github-dark" maxHeight="500px" />
   ├── JSON.stringify(data, null, 2)     → 格式化
   ├── await codeToHtml(jsonStr, ...)     → shiki 着色
   └── dangerouslySetInnerHTML            → 渲染 HTML

 <JsonDiff oldData={old} newData={new} theme="github-dark" />
   ├── JSON.stringify 双份格式化
   ├── diffLines(oldStr, newStr)          → Change[]
   ├── await codeToTokens(每段)           → 着色 token
   └── <table> + <tr> + <td> 渲染       → 行级展示
```

### 3.2 Props 设计

```typescript
// components/json/json-view.tsx
export interface JsonViewProps {
  /** 要展示的 JSON 数据 (任何可 JSON 序列化的值) */
  data: unknown;
  /** shiki 主题, 默认 "github-dark" */
  theme?: ShikiTheme;
  /** 外层容器 className */
  className?: string;
  /** 容器最大高度, 超出滚动. 如 "500px" / 400 (数字转 px) */
  maxHeight?: string | number;
}

// components/json/json-diff.tsx
export interface JsonDiffProps {
  /** 旧 JSON 数据 */
  oldData: unknown;
  /** 新 JSON 数据 */
  newData: unknown;
  /** shiki 主题 */
  theme?: ShikiTheme;
  /** 外层容器 className */
  className?: string;
  /** 容器最大高度, 超出滚动 */
  maxHeight?: string | number;
  /** 是否仅显示有差异的行 (v1 deferred, 暂不实现) */
  // showDiffOnly?: boolean;
}

/** 支持的 shiki 主题 (v1 只留 2 个, 后续按需扩充) */
export type ShikiTheme = "github-dark" | "github-light";
```

### 3.3 JsonView 实现设计

```tsx
// components/json/json-view.tsx
// ⚠️ RSC: 无 "use client", 纯 async component

import { codeToHtml } from "shiki";
import { cn } from "@/lib/utils";
import type { ShikiTheme } from "./types";  // shared type

export interface JsonViewProps { /* ... */ }

const EMPTY_PLACEHOLDER = "—";
const DEFAULT_THEME = "github-dark";

export const JsonView = async ({
  data,
  theme = DEFAULT_THEME,
  className,
  maxHeight,
}: JsonViewProps) => {
  // 1. 空数据兜底
  if (data === null || data === undefined) {
    return (
      <div className={cn("flex items-center justify-center rounded-lg border p-8 text-muted-foreground", className)}>
        {EMPTY_PLACEHOLDER}
      </div>
    );
  }

  // 2. 序列化
  let jsonStr: string;
  try {
    jsonStr = JSON.stringify(data, null, 2);
  } catch {
    return (
      <div className={cn("flex items-center justify-center rounded-lg border p-8 text-destructive", className)}>
        JSON 序列化失败
      </div>
    );
  }

  // 3. shiki 着色
  const html = await codeToHtml(jsonStr, {
    lang: "json",
    theme,
  });

  // 4. 渲染
  return (
    <div
      className={cn(
        "overflow-auto rounded-lg border font-mono text-sm leading-relaxed",
        // shiki 默认 html 不额外加样式, 靠 border/background 装饰
        "[&_pre]:m-0 [&_pre]:p-4",
        className,
      )}
      style={maxHeight != null ? { maxHeight: resolveCssDimension(maxHeight) } : undefined}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};
```

**关键点**:
- `codeToHtml` 是 shiki v3 shorthand API, 内部缓存 highlighter 实例, 性能好
- 外层 div 用 `overflow-auto` + `maxHeight` 做滚动容器
- shiki 输出 `<pre><code>` 已带行样式, 仅需 `font-mono text-sm` 微调
- `dangerouslySetInnerHTML` 是 RSC 渲染 shiki HTML 的唯一方式 (Next.js RSC 支持)

### 3.4 JsonDiff 实现设计

```tsx
// components/json/json-diff.tsx
// ⚠️ RSC: 无 "use client"

import { codeToTokens } from "shiki";
import { diffLines } from "diff";
import { cn } from "@/lib/utils";
import type { ShikiTheme } from "./types";

export interface JsonDiffProps { /* ... */ }

const EMPTY_PLACEHOLDER = "—";
const DEFAULT_THEME = "github-dark";

export const JsonDiff = async ({
  oldData,
  newData,
  theme = DEFAULT_THEME,
  className,
  maxHeight,
}: JsonDiffProps) => {
  // 1. 空数据兜底
  if (oldData == null && newData == null) {
    return <div className={...}>{EMPTY_PLACEHOLDER}</div>;
  }

  // 2. 序列化 (各自 catch)
  const oldStr = safeStringify(oldData);
  const newStr = safeStringify(newData);
  if (oldStr == null || newStr == null) {
    return <div className={...}>JSON 序列化失败</div>;
  }

  // 3. 完全相同 → 提早返回
  if (oldStr === newStr) {
    return (
      <div className={cn("flex items-center justify-center rounded-lg border p-8 text-muted-foreground", className)}>
        无差异
      </div>
    );
  }

  // 4. diffLines 算行级变化
  const changes = diffLines(oldStr, newStr);

  // 5. 逐块 tokenize → 构建行列表
  //    每行: { type: 'add' | 'remove' | 'none', tokens: ... }
  type DiffLineType = "add" | "remove" | "none";
  const lines: Array<{
    type: DiffLineType;
    tokens: Array<{ content: string; color?: string; fontStyle?: number }>;
  }> = [];

  for (const change of changes) {
    const type: DiffLineType = change.added ? "add" : change.removed ? "remove" : "none";
    const { tokens } = await codeToTokens(change.value, {
      lang: "json",
      theme,
      includeWhitespace: true,
    });
    for (const line of tokens) {
      lines.push({ type, tokens: line });
    }
  }

  // 6. 渲染 table
  return (
    <div
      className={cn("overflow-auto rounded-lg border font-mono text-sm leading-relaxed", className)}
      style={maxHeight != null ? { maxHeight: resolveCssDimension(maxHeight) } : undefined}
    >
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((line, idx) => (
            <DiffRow key={idx} line={line} />
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

**DiffRow** 提取为组件 (纯函数, 不需要 async):

```tsx
// 提取到 diff-row.tsx (或保持内联)
interface DiffRowProps {
  line: { type: DiffLineType; tokens: Array<{ content: string; color?: string }> };
}

const DiffRow = ({ line }: DiffRowProps) => {
  const bgMap: Record<DiffLineType, string> = {
    add: "bg-green-950/20 dark:bg-green-950/40",
    remove: "bg-red-950/20 dark:bg-red-950/40",
    none: "",
  };
  const gutterMap: Record<DiffLineType, string> = {
    add: "text-green-500",
    remove: "text-red-500",
    none: "text-muted-foreground",
  };
  const signMap: Record<DiffLineType, string> = {
    add: "+",
    remove: "-",
    none: " ",
  };

  return (
    <tr className={bgMap[line.type]}>
      <td className={cn("w-8 select-none text-right", gutterMap[line.type])}>
        {signMap[line.type]}
      </td>
      <td className="whitespace-pre px-2">
        {line.tokens.length > 0
          ? line.tokens.map((t, j) => (
              <span key={j} style={{ color: t.color }}>{t.content}</span>
            ))
          : <span>&nbsp;</span>}
      </td>
    </tr>
  );
};
```

**关键点**:
- `diffLines` 输出 `Change[]` (added / removed / 无标记三种), 按原序排列
- 相同段 (`type='none'`) 也 tokenize, 保证着色一致性
- `includeWhitespace: true` 保证缩进空格保留
- `DiffRow` 用 `<table>` 而非 `<div>` flex 布局, 保证多行对齐
- 临行末尾的空行 (空字符串 value) tokenize 结果是空数组, 用 `&nbsp;` 占位保行高

### 3.5 共享工具函数

```typescript
// components/json/utils.ts

/** 安全序列化 JSON, 失败返回 null */
export const safeStringify = (data: unknown): string | null => {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return null;
  }
};


/** 统一 css 维度解析: 数字转 px, 字符串原样 */
export const resolveCssDimension = (v: string | number): string =>
  typeof v === "number" ? `${v}px` : v;
```

### 3.6 文件结构

```
packages/web/components/json/
├── json-view.tsx         # RSC — 单个 JSON 高亮 (async)
├── json-diff.tsx         # RSC — 两个 JSON diff (async)
├── diff-row.tsx          # 纯函数 — diff 行渲染 (被 json-diff 引用)
├── utils.ts              # 共享工具: safeStringify / resolveCssDimension
├── types.ts              # 共享类型: ShikiTheme
├── json-view.test.tsx    # JsonView 测试
├── json-diff.test.tsx    # JsonDiff 测试
├── utils.test.ts         # 工具函数测试
└── index.ts              # 导出: { JsonView, JsonDiff, ShikiTheme }
```

### 3.7 使用示例

```tsx
// app/[locale]/some-page/page.tsx — RSC
import { JsonView, JsonDiff } from "@/components/json";

export default async function SomePage() {
  const oldSettings = await fetchSettings("v1");
  const newSettings = await fetchSettings("v2");

  return (
    <div className="space-y-8 p-4">
      {/* 单个 JSON */}
      <JsonView
        data={oldSettings}
        theme="github-dark"
        maxHeight="600px"
      />

      {/* 两个 JSON diff */}
      <JsonDiff
        oldData={oldSettings}
        newData={newSettings}
        theme="github-dark"
        maxHeight="600px"
      />
    </div>
  );
}
```

### 3.8 主题说明

| prop 值 | shiki 主题 | 适用场景 |
|---|---|---|
| `"github-dark"` (默认) | `github-dark` | 深色主题页面 |
| `"github-light"` | `github-light` | 浅色主题页面 |

RSC 无法读取客户端主题偏好。若需自动跟随，在外层加 `"use client"` wrapper 读取 `useTheme()` hook 后将 `theme` prop 传给 RSC 组件:

```tsx
// 可选: components/json/json-view-client.tsx
"use client";
import { useTheme } from "@/lib/theme/use-theme";  // 假设存在
import { JsonView as JsonViewRSC } from "./json-view";
import type { JsonViewProps } from "./json-view";

export const JsonView = (props: Omit<JsonViewProps, "theme">) => {
  const { theme } = useTheme();
  return <JsonViewRSC {...props} theme={theme === "dark" ? "github-dark" : "github-light"} />;
};
```

**v1 不提供 client wrapper**, 仅记录此模式供后续需要时采用。

### 3.9 性能考虑

- `codeToHtml` / `codeToTokens` 内部懒加载 highlighter, 首次调用加载 grammar + theme JSON (~200KB), 后续命中缓存, 纳秒级返回
- JSON stringify 对 < 1MB 数据 < 10ms, 不做分块
- diff 逐行量 < 5000 行, `diffLines` O(n) 算法 < 5ms
- `maxHeight` 纯 CSS 滚动, 不虚拟化

## 4. 改动文件清单

| 文件 | 性质 | 改动行(估) |
|---|---|---|
| `packages/web/package.json` | 改 | +2 (加 `shiki` + `diff` 依赖) |
| `packages/web/components/json/types.ts` | 新 | +10 |
| `packages/web/components/json/utils.ts` | 新 | +20 |
| `packages/web/components/json/utils.test.ts` | 新 | +40 |
| `packages/web/components/json/diff-row.tsx` | 新 | +35 |
| `packages/web/components/json/json-view.tsx` | 新 | +60 |
| `packages/web/components/json/json-view.test.tsx` | 新 | +70 |
| `packages/web/components/json/json-diff.tsx` | 新 | +90 |
| `packages/web/components/json/json-diff.test.tsx` | 新 | +80 |
| `packages/web/components/json/index.ts` | 新 | +5 |

**总计**: ~412 行 (新)

**后端 0 改动**, **i18n 0 改动** (无文案), **const 0 改动** (无魔法数字)

## 5. 测试策略

### 5.1 测试模式: 全部模式 1 (纯逻辑 mock)

| 测试文件 | 测什么 | 怎么测 |
|---|---|---|
| `utils.test.ts` | `safeStringify` 正常/边缘、`resolveCssDimension` 数字/字符串 | 纯函数, `expect()` |
| `json-view.test.tsx` | 空数据渲染占位、有效 JSON 渲染 HTML (snapshot)、序列化失败兜底 | mock `shiki` `codeToHtml` 返回固定 HTML 字符串, 断言容器内包含字符串片段 |
| `json-diff.test.tsx` | 完全相同显示"无差异"、有空数据时兜底、有差异时正确渲染 +/- 行数 | mock `shiki` `codeToTokens`、mock `diff` `diffLines` 返回固定变化片 |

### 5.2 shiki mock 策略

```typescript
// vitest setup 或测试文件内
vi.mock("shiki", async (importOriginal) => ({
  ...await importOriginal(),    // 保留其他导出 (如 Highlighter 类型)
  codeToHtml: vi.fn().mockResolvedValue('<pre><code><span style="color:#fff">{"a":1}</span></code></pre>'),
  codeToTokens: vi.fn().mockResolvedValue({
    tokens: [[{ content: '{"a":1}', color: "#fff" }]],
  }),
}));
```

不测 shiki 着色准确性 (shiki 自身测试覆盖)。组件测试只断言:
1. 传入 data → 调用了 `codeToHtml` / `codeToTokens`
2. 空/错误数据 → 不调 shiki, 直接渲染占位
3. 渲染的 HTML 结构符合预期 (snapshot 或 jest-dom matcher)

### 5.3 diff mock 策略

```typescript
vi.mock("diff", () => ({
  diffLines: vi.fn(() => [
    { value: '{"a": 1}\n', removed: true },
    { value: '{"a": 2}\n', added: true },
    { value: '{"b": 3}\n' },
  ]),
}));
```

### 5.4 TDD 顺序

1. `utils.test.ts` 先红 (先写断言) → 写 `utils.ts` → 绿
2. `json-view.test.tsx` 先红 → 写 `json-view.tsx` + `types.ts` → 绿
3. `json-diff.test.tsx` 先红 → 写 `diff-row.tsx` + `json-diff.tsx` → 绿
4. 写 `index.ts` 重导出

## 6. 实施步骤

### Phase 1: 依赖 + 基础设施

```bash
cd packages/web
bun add shiki diff
```

### Phase 2: 工具函数 (TDD)

1. 写 `utils.test.ts` — safeStringify (正常/undefined/循环引用), resolveCssDimension (100/"100px")
2. 写 `utils.ts` — 实现 2 个函数
3. 写 `types.ts` — `ShikiTheme` 类型

### Phase 3: JsonView (TDD)

4. 写 `json-view.test.tsx` — 空/normal/序列化失败
5. 写 `json-view.tsx` — async component

### Phase 4: JsonDiff (TDD)

6. 写 `json-diff.test.tsx` + `diff-row.tsx` — 相同/不同/空
7. 写 `json-diff.tsx` — async component + diff-row 引用

### Phase 5: 验收

按项目铁律:

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
bun run test -- json       # 只跑 components/json/ 测试
bun run test               # 全量: 0 新 fail
```

1 commit: `feat(json): add JsonView and JsonDiff RSC components with shiki highlighting`

## 7. 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `shiki` `codeToHtml` 在 Next.js RSC 中因 Node 版本/模块格式不兼容报错 | 先 `bun add shiki` 写一个最小测试 (在 page.tsx 调 `codeToHtml`) 再写组件 | 换 `react-syntax-highlighter` 方案 (方案 A) 或回滚整个 commit |
| `diff` 库的 `diffLines` 对大文件 OOM | 当前场景 JSON < 5000 行, 已有测试覆盖 1000 行场景 | 回滚到单 JSON 展示 |
| `dangerouslySetInnerHTML` 安全风险 | shiki HTML 是确定性产出, 无用户注入路径 | 回滚到纯文本方案 |
| `codeToTokens` 返回 `tokens` 字段名不匹配 | 实施前在独立文件调一下验证类型 | 改字段匹配 |
| vitest mock shiki 后类型不匹配 | `vi.mock(import("shiki"), async (importOriginal) => ...)` 模式, 跟项目现有 mock lucide-react 一致 | 改 mock 实现 |

## 8. 验收

```bash
# 1. JsonView 核心
grep -n "codeToHtml" packages/web/components/json/json-view.tsx    # 1 hit
grep -n "dangerouslySetInnerHTML" packages/web/components/json/json-view.tsx  # 1 hit

# 2. JsonDiff 核心
grep -n "diffLines" packages/web/components/json/json-diff.tsx      # 1 hit
grep -n "codeToTokens" packages/web/components/json/json-diff.tsx    # ≥1 hit

# 3. 测试覆盖
grep -n "describe(" packages/web/components/json/json-view.test.tsx  # ≥3 cases (空/有效/失败)
grep -n "describe(" packages/web/components/json/json-diff.test.tsx  # ≥3 cases (空/相同/不同)

# 4. 工具测试
grep -n "safeStringify" packages/web/components/json/utils.test.ts   # ≥2 cases
grep -n "resolveCssDimension" packages/web/components/json/utils.test.ts # ≥2 cases

# 5. 规约对齐
cd packages/web
bun run format:check || bun run format
bun run lint
bun run typecheck
bun run test            # 0 新 fail

# 6. 后端 / i18n / const 0 改动
git diff packages/service/   # 0 hit
git diff messages/           # 0 hit
git diff const/              # 0 hit
```

## 9. 关联

- [shiki 官方文档](https://shiki.style/) — 着色引擎, 本方案核心
- [diff NPM](https://www.npmjs.com/package/diff) — `diffLines` 行级 diff 算法
- [project-rules §零 lint warning](CLAUDE.md) — oxlint 0 warning, 箭头函数, 排序 import
- [project-rules §TDD 顺序](CLAUDE.md) — format→lint→typecheck→test→commit 不可颠倒
- [packages/web/CLAUDE.md §封装组件](packages/web/CLAUDE.md) — 项目组件封装规范, 本组件无 shadcn 包装需求, 不走 App 前缀
- 相关 memory:
  - [[feedback-subagent-vs-inline-pivot]] — 本 spec 约 400 行, 属于"中等复杂度", 按需决定 subagent 或 inline
  - [[feedback-no-shim-no-minimal-changes]] — 不预留 client wrapper, v1 纯 RSC, 需要时加
