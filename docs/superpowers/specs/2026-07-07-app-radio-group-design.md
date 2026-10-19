# AppRadioGroup 封装 + pre-analysis 表格提取器改 RadioGroup (2026-07-07)

> 📅 创建日期：2026-07-07
> 📁 项目代码引用：以 `rag` 仓库当前 master (`fe2c62ff`) 为准
> 🎯 范围：封装项目第一个 `AppRadioGroup` 组件，并替换 `pre-analysis-upload-dialog.tsx` 的表格提取器 UI

---

## 一、目标 & 范围

**目标**：
1. 封装 `AppRadioGroup`（antd 风格 `options + value + onChange` + `renderLabel` 复合 API）
2. 把 `pre-analysis-upload-dialog.tsx` 的"表格提取器"从 `<AppSelect>` 下拉改成 `<AppRadioGroup>` 横向并排圆点单选

**核心约束**：
- ✅ 沿用项目封装规约（跟 `AppSelect` / `AppToggle` 同列、`AppRadioGroup` 放 `components/common/input/`）
- ✅ 不破坏现有 `backend-select` testid 之外的契约（data-testid 同步改 `backend-radio`，单测同步改）
- ✅ 保持联动行为不变（切 backend 仍触发 `useEffect → setParams(BACKEND_DEFAULT_PARAMS[backend])`）
- ❌ 不动其它封装组件（`AppSelect` / `AppToggle` / `AppTabs` 等保持现状）
- ❌ 不重构 `BACKEND_DEFAULT_PARAMS` / `getCamelotParamKeys` 逻辑
- ❌ 不引入 i18n（按项目规约"高级选项硬编码 zh+en 合一"）
- ❌ 不加 e2e 测试（pre-analysis 页面当前无 e2e 覆盖，本期不动）

---

## 二、架构

### 新增：`AppRadioGroup` 封装

**位置**：`packages/web/components/common/input/app-radio-group.tsx`

**导出**：
- `AppRadioGroup` 组件
- `AppRadioOption` 类型（跟 `AppSelectOption` 对齐：value/label/disabled）

**内部**：
- 根：`shadcn RadioGroup`（已装，基于 `@radix-ui/react-radio-group`）
- 项：`shadcn RadioGroupItem` + `<Label>` 包裹（cursor-pointer，符合 shadcn Label 模式）
- className 默认 `grid gap-2`（shadcn 自带值，cn() 合并用户传入）
- dataTestid 模式：`${dataTestid}-${option.value}`（跟 `AppToggle` 一致）

**关键设计决策**：

1. **renderLabel 复合**：跟 `AppSelectOption` 不同，RadioGroup 每项**经常需要自定义内容**（Tooltip / 描述 / 图标），所以提供可选 `renderLabel` 回调。缺省时直接渲染 `option.label`。
2. **值类型是 `string`**：不 narrow 到泛型，调用方 `as TableBackend` cast，跟现有 `AppSelect onChange` 用法一致。
3. **不抽 `AppRadioLabel` 子件**：shadcn `RadioGroupItem` 已经包含圆点 + label，再封一层冗余（这是方案 B 被否决的原因）。

### 改动业务：`pre-analysis-upload-dialog.tsx`

**表格提取器区域**：

```tsx
// 之前 (lines 371-381):
<AppSelect
  options={BACKEND_OPTIONS}
  value={state.backend}
  onChange={(val) => state.setBackend(val as TableBackend)}
  dataTestid="backend-select"
/>

// 之后:
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
```

**数据结构变更**：

```tsx
// 之前:
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";
const BACKEND_OPTIONS: AppSelectOption[] = [
  { value: "pymupdf", label: "PyMuPDF" },
  { value: "camelot", label: "Camelot" },
  { value: "pdfplumber", label: "pdfplumber" },
];

// 之后:
type TableBackend = "pymupdf" | "camelot" | "pdfplumber";
const BACKEND_OPTIONS: (AppRadioOption & { tooltip: string })[] = [
  { value: "pymupdf", label: "PyMuPDF", tooltip: "PyMuPDF 内置 find_tables()，开箱即用，识别速度最快" },
  { value: "camelot", label: "Camelot", tooltip: "lattice/stream/network/hybrid/ml 5 种解析器..." },
  { value: "pdfplumber", label: "pdfplumber", tooltip: "基于 pdfplumber 的 lines/text 策略 + 容差参数" },
];
```

**label htmlFor 处理**：

```tsx
// 之前:
<label className="text-sm font-medium" htmlFor="backend-select">表格提取器</label>

// 之后: 改用 shadcn Label 包根 (shadcn RadioGroupItem 不带 id，htmlFor 失效)
<Label className="text-sm font-medium">表格提取器</Label>
```

需要从 `@/components/ui/label` import `Label`（shadcn 已装）。

**联动行为不变**：
- `useEffect` 监听 `backend` 变化 → `setParams(BACKEND_DEFAULT_PARAMS[backend])`
- `paramKeys` 计算逻辑不变（camelot 走 `getCamelotParamKeys`，其他走静态字典）
- 提交时 `TableExtractionConfig` 不变

---

## 三、API 定义

### `AppRadioGroup` Props

```ts
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
```

### 内部实现骨架

```tsx
"use client";
// Antd 风格 RadioGroup 包装 (2026-07-07): 替 shadcn RadioGroup + RadioGroupItem 2 行模板
//   用法: <AppRadioGroup options={[{value,label}]} value={x} onChange={setX} />
//   跟 AppSelect / AppToggle 一致, 每项支持 renderLabel 复合 (带 Tooltip/描述/图标场景)
//   关联 [[feedback-no-shim-no-minimal-changes]]
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export const AppRadioGroup = ({ options, value, defaultValue, onChange, renderLabel, className, dataTestid }: AppRadioGroupProps) => (
  <RadioGroup
    value={value}
    defaultValue={defaultValue}
    onValueChange={onChange}
    className={cn("grid gap-2", className)}
    data-testid={dataTestid}
  >
    {options.map((opt) => {
      const testid = dataTestid ? `${dataTestid}-${opt.value}` : undefined;
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

---

## 四、测试

### `app-radio-group.test.tsx`（新增）

vitest + jsdom + `@testing-library/react`，跟 `app-select.test.tsx` 同模式。

测试用例：
1. ✅ 渲染无报错
2. ✅ 默认渲染 `option.label` 文本
3. ✅ `renderLabel` 自定义渲染生效（传入 ReactNode 替代默认 label）
4. ✅ 受控值变化：onChange 回调拿到新 value（用 `userEvent.click` 选第二项）
5. ✅ `dataTestid` 透传 Item 级为 `${dataTestid}-${option.value}`
6. ✅ `disabled` 项不响应点击

### `pre-analysis-upload-dialog.test.tsx`（同步改）

- 改 `getByTestId("backend-select")` → `getByTestId("backend-radio")`（2 处：line 158, 172）
- 新增断言：渲染 3 个 Item（`backend-radio-pymupdf` / `backend-radio-camelot` / `backend-radio-pdfplumber`）

### E2E

无。pre-analysis 页面无 e2e 覆盖。

---

## 五、风险 & 缓解

| 风险 | 缓解 |
|------|------|
| RadioGroupItem 不带 `id` 导致 `<label htmlFor>` 失效 | 用 `<Label>` + 显式 `htmlFor` 绑定 `id`（见骨架代码） |
| RadioGroup 默认 `grid gap-2` 让"后端名 + Tooltip"每项独占一行 | 业务侧 `renderLabel` 用 `<span className="flex items-center gap-1">` 控制间距 |
| tooltip 图标按 HelpCircle 渲染时点击会触发 radio 选中 | `AppTooltip` 内部 Radix Tooltip 默认 click 触发，hover-only 由 shadcn 默认；测试一下没问题就行 |
| shadcn RadioGroup `asChild` 不支持（不像 SelectTrigger） | 暂不暴露 `asChild`，未来有需求再加 |
| 数据结构 `(AppRadioOption & { tooltip: string })[]` 不优雅 | 用 intersection 类型足够清晰；不抽新类型 `BackendOption`（避免过度抽象） |

---

## 六、文件清单

**新增**：
- `packages/web/components/common/input/app-radio-group.tsx`
- `packages/web/components/common/input/app-radio-group.test.tsx`

**改动**：
- `packages/web/components/common/input/index.ts`（加 export）
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.tsx`
  - imports: 加 `AppRadioGroup`, `AppRadioOption`; 加 `Label` from `@/components/ui/label`
  - `BACKEND_OPTIONS` 类型变更 + 加 `tooltip` 字段
  - 渲染部分：`AppSelect` → `AppRadioGroup`
  - `<label htmlFor>` → `<Label>` 包根
- `packages/web/app/[locale]/admin/pre-analysis/_components/pre-analysis-upload-dialog.test.tsx`
  - `getByTestId("backend-select")` → `getByTestId("backend-radio")`
  - 新增 Item 级 testid 断言

**不改**：
- `packages/web/components/ui/radio-group.tsx`（已有）
- `packages/web/components/ui/radio-group.test.tsx`（已有，测的是底层）
- 后端 BFF / API / 任何业务逻辑

---

## 七、执行顺序

1. **新增** `app-radio-group.tsx` + `app-radio-group.test.tsx`
2. **改** `components/common/input/index.ts` 加 export
3. **改** `pre-analysis-upload-dialog.tsx`（imports / 数据结构 / 渲染）
4. **改** `pre-analysis-upload-dialog.test.tsx`（testid 同步）
5. 跑 `bun run lint` / `bun run typecheck` / `bun run test -- <files>`
6. 跑 `bun run format`

按项目规约格式：`refactor: 封装 AppRadioGroup + pre-analysis 表格提取器改 RadioGroup (i18n 不动)`