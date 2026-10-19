# AppRadioGroup 封装 + pre-analysis 表格提取器改 RadioGroup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 封装 `AppRadioGroup` 组件，并把 `pre-analysis-upload-dialog` 的"表格提取器"从 `<AppSelect>` 改成 `<AppRadioGroup>` 横向并排圆点单选，保留 HelpCircle + AppTooltip 帮助图标。

**Architecture:** 沿用项目封装哲学——antd 风格 1 行 options API + 可选 `renderLabel` 复合（处理 Tooltip/描述/图标场景）。封装放 `components/common/input/`，跟 `AppSelect` / `AppToggle` 同列。业务侧只改 1 处对话框，联动逻辑 `useEffect → setParams(BACKEND_DEFAULT_PARAMS[backend])` 不动。

**Tech Stack:** shadcn `RadioGroup` + `RadioGroupItem` (基于 `@radix-ui/react-radio-group`) + shadcn `Label` + vitest + @testing-library/react + jsdom.

## Global Constraints

- 所有代码注释用中文 (项目 CLAUDE.md)
- 所有 export 函数 / interface / const 必须有 JSDoc 块
- import 按字母排序 (oxlint sort-imports)
- 变量名禁止单字符 (val 替代 v, idx 替代 i)
- 魔法数字必须提取为命名 const
- oxfmt + oxlint + tsc 必须 0 error 才 commit
- 函数声明用 `const = () => {}` (默认 export 组件例外)
- husky pre-commit 自动跑 lint-staged + tsc + vitest + format:check, 不用 `--no-verify` 绕过
- 跑测试用 `bun run test -- <file>` (单测), 跑全量 `bun run test`
- 跑 lint 用 `bun run lint` / 修用 `bun run lint:fix`
- 跑 typecheck 用 `bun run typecheck`
- 跑 format 用 `bun run format` (写) / `bun run format:check` (只读)
- pre-analysis-upload-dialog.tsx 高级选项 label/tooltip 硬编码 zh+en 合一, 不进 i18n

---

## File Structure

**新增**：
- `packages/web/components/common/input/app-radio-group.tsx` — AppRadioGroup 组件 + AppRadioOption 类型
- `packages/web/components/common/input/app-radio-group.test.tsx` — 6 个 vitest 用例

**改动**：
- `packages/web/components/common/input/index.ts` — 加 export
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` — 表格提取器 AppSelect → AppRadioGroup + BACKEND_OPTIONS 加 tooltip 字段 + Label 包根
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx` — backend-select → backend-radio + "Backend 后端" → "表格提取器" 文案同步

---

## Task 1: 写 `AppRadioGroup` 单元测试 (TDD 红)

**Files:**
- Create: `packages/web/components/common/input/app-radio-group.test.tsx`

**Interfaces:**
- Consumes: `./app-radio-group` (尚未存在, 测试会失败)
- Produces: 无

- [ ] **Step 1: 创建测试文件**

`packages/web/components/common/input/app-radio-group.test.tsx`:

```tsx
// AppRadioGroup 单元测试 (2026-07-07)
//   替 shadcn RadioGroup + RadioGroupItem 2 行模板 (Root/Item/Indicator) → 1 行 options + value + onChange
//   测试范围: 默认 label 渲染 + renderLabel 复合 + 受控值 + dataTestid Item 级透传 + disabled
//   (jsdom 测 Radix radio 选中状态, 跟 AppSelect 模式一致)
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AppRadioGroup } from "./app-radio-group";

const options = [
  { value: "pymupdf", label: "PyMuPDF" },
  { value: "camelot", label: "Camelot" },
  { value: "pdfplumber", label: "pdfplumber" },
];

describe("AppRadioGroup", () => {
  it("render root with dataTestid", () => {
    render(<AppRadioGroup options={options} dataTestid="backend" />);
    expect(screen.getByTestId("backend")).toBeInTheDocument();
  });

  it("render default label for each option", () => {
    render(<AppRadioGroup options={options} value="pymupdf" onChange={() => {}} />);
    expect(screen.getByText("PyMuPDF")).toBeInTheDocument();
    expect(screen.getByText("Camelot")).toBeInTheDocument();
    expect(screen.getByText("pdfplumber")).toBeInTheDocument();
  });

  it("renderLabel override default label", () => {
    render(
      <AppRadioGroup
        options={options}
        value="pymupdf"
        onChange={() => {}}
        renderLabel={(opt) => <span data-testid={`custom-${opt.value}`}>{`custom-${opt.label}`}</span>}
      />,
    );
    expect(screen.getByTestId("custom-pymupdf")).toHaveTextContent("custom-PyMuPDF");
    expect(screen.queryByText("PyMuPDF")).not.toBeInTheDocument();
  });

  it("onValueChange called with new value (controlled)", () => {
    const onChange = vi.fn();
    render(<AppRadioGroup options={options} value="pymupdf" onChange={onChange} />);
    // RadioGroupItem 的 click 触发 onValueChange (Radix 标准)
    screen.getByRole("radio", { name: "Camelot" }).click();
    expect(onChange).toHaveBeenCalledWith("camelot");
  });

  it("Item dataTestid composed as ${dataTestid}-${value}", () => {
    render(<AppRadioGroup options={options} dataTestid="backend" />);
    expect(screen.getByTestId("backend-pymupdf")).toBeInTheDocument();
    expect(screen.getByTestId("backend-camelot")).toBeInTheDocument();
    expect(screen.getByTestId("backend-pdfplumber")).toBeInTheDocument();
  });

  it("disabled option disable radio", () => {
    render(<AppRadioGroup options={[{ value: "a", label: "A", disabled: true }]} value="a" onChange={() => {}} />);
    expect(screen.getByRole("radio", { name: "A" })).toBeDisabled();
  });
});
```

- [ ] **Step 2: 跑测试确认 fail**

```bash
cd packages/web && bun run test -- "components/common/input/app-radio-group.test.tsx"
```

Expected: FAIL — `./app-radio-group` 模块找不到 (Cannot find module)

- [ ] **Step 3: 不 commit (测试先红, 下个 task 实现)**

---

## Task 2: 实现 `AppRadioGroup` 组件 (TDD 绿)

**Files:**
- Create: `packages/web/components/common/input/app-radio-group.tsx`

**Interfaces:**
- Consumes: `@/components/ui/radio-group` (RadioGroup, RadioGroupItem), `@/components/ui/label` (Label), `@/lib/utils` (cn)
- Produces:
  - `AppRadioOption` interface: `{ value: string; label: string; disabled?: boolean }`
  - `AppRadioGroupProps` interface: `{ options, value?, defaultValue?, onChange?, renderLabel?, className?, dataTestid? }`
  - `AppRadioGroup` 组件

- [ ] **Step 1: 创建实现文件**

`packages/web/components/common/input/app-radio-group.tsx`:

```tsx
"use client";
// Antd 风格 RadioGroup 包装 (2026-07-07): 替 shadcn RadioGroup + RadioGroupItem 2 行模板
//   用法: <AppRadioGroup options={[{value,label}]} value={x} onChange={setX} />
//   跟 AppSelect / AppToggle 一致, 每项支持 renderLabel 复合 (带 Tooltip/描述/图标场景)
//   关联 [[feedback-no-shim-no-minimal-changes]]
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";

/**
 * AppRadioGroup 选项 — 值及展示文案
 * @client-bff
 */
export interface AppRadioOption {
  /** 选项值 */
  value: string;
  /** 选项展示文案 (renderLabel 缺省时使用) */
  label: string;
  /** 禁用单项 */
  disabled?: boolean;
}

/**
 * AppRadioGroup 属性接口 — 选项列表、受控值、变化回调、每项自定义渲染
 * @client-bff
 */
export interface AppRadioGroupProps {
  /** 选项列表 */
  options: AppRadioOption[];
  /** 受控值 */
  value?: string;
  /** 非受控初始值 */
  defaultValue?: string;
  /** 值变化回调 (传入新值) */
  onChange?: (value: string) => void;
  /** 自定义单选项渲染 — 默认只渲染 label 文本 */
  renderLabel?: (option: AppRadioOption) => React.ReactNode;
  /** 根容器 className (shadcn grid gap-2 默认) */
  className?: string;
  /** 根容器 testid — Item 级 testid 拼成 `${dataTestid}-${option.value}` */
  dataTestid?: string;
}

/**
 * 单选组 — antd 风格 RadioGroup 包装, 替 shadcn RadioGroup + RadioGroupItem 2 行模板
 * @param props.options 选项列表
 * @param props.value 受控值
 * @param props.onChange 值变化回调
 * @param props.renderLabel 自定义单选项渲染
 * @returns RadioGroup JSX
 */
export const AppRadioGroup = ({
  options,
  value,
  defaultValue,
  onChange,
  renderLabel,
  className,
  dataTestid,
}: AppRadioGroupProps) => (
  <RadioGroup
    value={value}
    defaultValue={defaultValue}
    onValueChange={onChange}
    className={cn("grid gap-2", className)}
    data-testid={dataTestid}
  >
    {options.map((opt) => {
      // 不传 dataTestid 时透传 undefined, 保持 RadioGroupItem 内部 data-testid 不被覆盖
      // eslint-disable-next-line no-ternary -- init-declarations + prefer-ternary 互斥
      const testid = dataTestid ? `${dataTestid}-${opt.value}` : undefined;
      // Item id 用 testid 同字符串, 让 Label htmlFor 跟 data-testid 共享, 缺省时退化为 radio-<value>
      const itemId = testid ?? `radio-${opt.value}`;
      return (
        <div key={opt.value} className="flex items-center gap-2">
          <RadioGroupItem
            value={opt.value}
            disabled={opt.disabled}
            id={itemId}
            data-testid={testid}
          />
          <Label htmlFor={itemId} className="cursor-pointer font-normal">
            {renderLabel ? renderLabel(opt) : opt.label}
          </Label>
        </div>
      );
    })}
  </RadioGroup>
);
```

- [ ] **Step 2: 跑测试确认 green**

```bash
cd packages/web && bun run test -- "components/common/input/app-radio-group.test.tsx"
```

Expected: 6 个 test 全部 PASS

- [ ] **Step 3: 跑 lint + typecheck**

```bash
cd packages/web && bun run lint && bun run typecheck
```

Expected: 0 error

- [ ] **Step 4: commit**

```bash
cd /home/deyuan/rag/rag && git add packages/web/components/common/input/app-radio-group.tsx packages/web/components/common/input/app-radio-group.test.tsx && git commit -m "feat: 封装 AppRadioGroup (antd 风格 options + value + onChange + renderLabel)"
```

---

## Task 3: `components/common/input/index.ts` 加 export

**Files:**
- Modify: `packages/web/components/common/input/index.ts`

- [ ] **Step 1: 按字母序加 export (radio 在 dropdown/file/image/search/select/tabs/toggle 之间)**

当前 `index.ts`:

```ts
// input 模块对外 API (2026-06-25) 批量出口
export * from "./app-dropdown-menu";
export * from "./app-file-dropzone";
export * from "./app-image-preview";
export * from "./app-search-input";
export * from "./app-select";
export * from "./app-tabs";
export * from "./app-toggle";
```

替换为:

```ts
// input 模块对外 API (2026-07-07) 批量出口 (新增 app-radio-group)
export * from "./app-dropdown-menu";
export * from "./app-file-dropzone";
export * from "./app-image-preview";
export * from "./app-radio-group";
export * from "./app-search-input";
export * from "./app-select";
export * from "./app-tabs";
export * from "./app-toggle";
```

- [ ] **Step 2: 跑 typecheck 确认 export 通**

```bash
cd packages/web && bun run typecheck
```

Expected: 0 error (无业务 import 触发, 仅 export 检查)

- [ ] **Step 3: commit**

```bash
cd /home/deyuan/rag/rag && git add packages/web/components/common/input/index.ts && git commit -m "feat(input): export AppRadioGroup from common/input barrel"
```

---

## Task 4: 改 `pre-analysis-upload-dialog.tsx` — imports + BACKEND_OPTIONS + 渲染

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx:11-18, 27-33, 372-381`

**Interfaces:**
- Consumes: `AppRadioGroup` + `AppRadioOption` from `@/components/common/input`, `Label` from `@/components/ui/label`
- Produces: 无 (只改实现, 行为不变)

- [ ] **Step 1: imports 替换 (删 AppSelect, 加 AppRadioGroup + AppRadioOption + Label)**

在 `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx` 找到第 11-18 行:

```tsx
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppSelect, type AppSelectOption } from "@/components/common/input/app-select";
import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { Input } from "@/components/ui/input";
```

替换为 (按字母排序, AppRadioGroup 跟 AppSelect 一起从 barrel 引, 不改其它路径):

```tsx
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppRadioGroup, type AppRadioOption, AppSelect, type AppSelectOption } from "@/components/common/input";
import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { FileDropzone } from "@/components/common/input/app-file-dropzone";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
```

**注**: `AppSelect` 暂时保留 (用于 `FLAVOR_OPTIONS` / `STRATEGY_OPTIONS` 的下拉选择, 不在本期改动范围), 跟 `AppRadioGroup` 一起从 barrel 导入. `FileDropzone` 保留原子文件路径不动.

- [ ] **Step 2: BACKEND_OPTIONS 类型变更 + 加 tooltip 字段**

找到第 27-33 行:

```tsx
// (2026-07-06) 高级选项: 硬编码 zh+en 合一 label/tooltip, 不进 i18n
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";

const BACKEND_OPTIONS: AppSelectOption[] = [
  { value: "pymupdf", label: "PyMuPDF" },
  { value: "camelot", label: "Camelot" },
  { value: "pdfplumber", label: "pdfplumber" },
];
```

替换为:

```tsx
// (2026-07-06) 高级选项: 硬编码 zh+en 合一 label/tooltip, 不进 i18n
// (2026-07-07) 表格提取器改 RadioGroup 后, BACKEND_OPTIONS 加 tooltip 字段, 类型走 AppRadioOption
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";

const BACKEND_OPTIONS: (AppRadioOption & { tooltip: string })[] = [
  { value: "pymupdf", label: "PyMuPDF", tooltip: "PyMuPDF 内置 find_tables()，开箱即用，识别速度最快" },
  { value: "camelot", label: "Camelot", tooltip: "lattice/stream/network/hybrid/ml 5 种解析器，按 flavor 切换不同参数组" },
  { value: "pdfplumber", label: "pdfplumber", tooltip: "基于 pdfplumber 的 lines/text 策略 + 容差参数" },
];
```

- [ ] **Step 3: 渲染部分 AppSelect → AppRadioGroup + Label 包根**

找到第 371-381 行:

```tsx
<div>
  <label className="text-sm font-medium" htmlFor="backend-select">
    表格提取器
  </label>
  <AppSelect
    options={BACKEND_OPTIONS}
    value={state.backend}
    onChange={(val) => state.setBackend(val as TableBackend)}
    dataTestid="backend-select"
  />
</div>
```

替换为:

```tsx
<div>
  {/* (2026-07-07) Label 包根 (shadcn RadioGroupItem 不带 id, htmlFor 失效; 改用 Label 触发整组焦点) */}
  <Label className="text-sm font-medium">表格提取器</Label>
  <AppRadioGroup
    options={BACKEND_OPTIONS}
    value={state.backend}
    onChange={(val) => state.setBackend(val as TableBackend)}
    dataTestid="backend-radio"
    renderLabel={(opt) => (
      <span className="flex items-center gap-1">
        {opt.label}
        <AppTooltip content={opt.tooltip}>
          <HelpCircle className="h-3.5 w-3.5 cursor-help text-muted-foreground" />
        </AppTooltip>
      </span>
    )}
  />
</div>
```

- [ ] **Step 4: 跑 typecheck + lint**

```bash
cd packages/web && bun run typecheck && bun run lint
```

Expected: 0 error

- [ ] **Step 5: 跑业务侧单测看是否 fail**

```bash
cd packages/web && bun run test -- "app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx"
```

Expected: 至少 2 处 fail — `getByTestId("backend-select")` 找不到 (`backend-radio`), "Backend 后端" 找不到 ("表格提取器"). **预期失败, 下个 task 修**

---

## Task 5: 同步改 `pre-analysis-upload-dialog.test.tsx` — testid + 文案

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx:146, 156, 158, 172`

**Interfaces:**
- Consumes: 无
- Produces: 无

- [ ] **Step 1: 改 line 146 注释 + 断言文案**

找到 line 144-147:

```tsx
it("默认状态下高级选项折叠区收起, 看不到 backend 选择器", () => {
  renderDialog();
  // Collapsible 默认 closed → Backend 后端 label 不可见
  expect(screen.queryByText("Backend 后端")).not.toBeInTheDocument();
});
```

替换为:

```tsx
it("默认状态下高级选项折叠区收起, 看不到 backend 选择器", () => {
  renderDialog();
  // Collapsible 默认 closed → 表格提取器 label 不可见
  expect(screen.queryByText("表格提取器")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: 改 line 156 断言文案**

找到 line 149-159:

```tsx
it("点高级选项开关 → 看到 backend 选择器 + 默认 pymupdf", async () => {
  const user = userEvent.setup();
  renderDialog();
  // Collapsible 的 Trigger 按钮
  const toggle = screen.getByTestId("advanced-toggle");
  await user.click(toggle);
  // Backend label 可见
  expect(screen.getByText("Backend 后端")).toBeInTheDocument();
  // AppSelect 默认显示 PyMuPDF
  expect(screen.getByTestId("backend-select")).toHaveTextContent("PyMuPDF");
});
```

替换为:

```tsx
it("点高级选项开关 → 看到 backend 选择器 + 默认 pymupdf", async () => {
  const user = userEvent.setup();
  renderDialog();
  // Collapsible 的 Trigger 按钮
  const toggle = screen.getByTestId("advanced-toggle");
  await user.click(toggle);
  // 表格提取器 label 可见
  expect(screen.getByText("表格提取器")).toBeInTheDocument();
  // AppRadioGroup 默认显示 PyMuPDF
  expect(screen.getByTestId("backend-radio-pymupdf")).toBeInTheDocument();
});
```

- [ ] **Step 3: 改 line 172 testid**

找到 line 172:

```tsx
expect(screen.getByTestId("backend-select")).toHaveTextContent("PyMuPDF");
```

替换为:

```tsx
expect(screen.getByTestId("backend-radio-pymupdf")).toBeInTheDocument();
```

- [ ] **Step 4: 跑业务侧单测确认 green**

```bash
cd packages/web && bun run test -- "app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx"
```

Expected: 全部 PASS

- [ ] **Step 5: 跑全链路质量门禁**

```bash
cd packages/web && bun run format && bun run lint:fix && bun run typecheck && bun run test -- "components/common/input/app-radio-group.test.tsx" "app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx"
```

Expected: 0 error

- [ ] **Step 6: commit**

```bash
cd /home/deyuan/rag/rag && git add packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx && git commit -m "refactor: 表格提取器改 AppRadioGroup (后端名 + Tooltip 图标横向并排, testid backend-select → backend-radio)"
```

---

## Task 6: 全量前端质量门禁 + 文档同步

**Files:**
- Modify: `packages/web/CLAUDE.md` (新封装段加 AppRadioGroup)

- [ ] **Step 1: 跑全量 vitest 看有没有 regression**

```bash
cd packages/web && bun run test
```

Expected: 全部 PASS (baseline 已有 + 6 个新增 AppRadioGroup 用例 + 业务侧改动 0 新 fail)

- [ ] **Step 2: 跑 format:check 看有没有未格式化**

```bash
cd packages/web && bun run format:check
```

Expected: 0 exit

如有 fail 跑 `bun run format` 修.

- [ ] **Step 3: 同步更新 `packages/web/CLAUDE.md` 新封装段 + 反模式段**

**A. 新封装段**: line 173 `### 新封装 (6, 2026-06-18)` 改为 `### 新封装 (7, 2026-07-07)`, 在 line 176 (`<AppToggle>`) 之后插入新条目:

```diff
 - `<AppSelect>` (antd 风格, options + value + onChange 一行) — 替 shadcn Select 6-行模板
 - `<AppToggle>` (shadcn ToggleGroup 单选) — 替手写 button 按钮组 (例 decode view 切换)
+- `<AppRadioGroup>` (antd 风格, options + value + onChange + renderLabel 复合, 2026-07-07) — 替 shadcn RadioGroup 2-行模板 (Root + Item × N), 适合"带 Tooltip/描述/图标的单选"场景 (例 pre-analysis 表格提取器)
 - `<ErrorBanner>` ...
```

**B. 反模式段**: line 186 当前写 `<input type="checkbox">` / shadcn `<Switch>` / shadcn `<RadioGroup>` / shadcn `<Textarea>` 直用 — 把 `shadcn <RadioGroup>` 从这条**移除** (因为现在有 `<AppRadioGroup>` 包装), 改为:

```diff
-- `<input type="checkbox">` / shadcn `<Switch>` / shadcn `<RadioGroup>` / shadcn `<Textarea>` 直用 (跟 `<AppSelect>` 价值不同, 1 行就够, 不抽包装)
+- `<input type="checkbox">` / shadcn `<Switch>` / shadcn `<Textarea>` 直用 (跟 `<AppSelect>` 价值不同, 1 行就够, 不抽包装)
+- shadcn `<RadioGroup>` + `<RadioGroupItem>` 模板 → `<AppRadioGroup>` (antd 风格 options + value + onChange + renderLabel)
```

- [ ] **Step 4: commit**

```bash
cd /home/deyuan/rag/rag && git add packages/web/CLAUDE.md && git commit -m "docs(web): 新封装段加 AppRadioGroup (7 个)"
```