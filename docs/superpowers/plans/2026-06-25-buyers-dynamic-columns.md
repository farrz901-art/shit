# Buyers 列表动态画像字段列 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `app/[locale]/buyers/page.tsx` 表格删除 `buyer_key` 列, 改成根据 `useFieldConfigs()` 激活字段动态生成 N 列画像数据列, 按 field_type 差异化渲染 (select/tags→Badge, number→num 等宽字体, boolean→是/否, 其他纯文本).

**Architecture:** 1 个原子 commit (页面 + 测试 + i18n), TDD 顺序: 先测试 (覆盖 9 种场景) → 实现 buildProfileColumn helper → 改造 buildColumns + 加 useFieldConfigs → 加 i18n → 跑全套测试验证 0 新 fail. 中间不 commit (单原子).

**Tech Stack:** React 19 / Next.js 16 / TypeScript 8 / vitest / @testing-library/react / TanStack Query / shadcn/ui (Badge) / next-intl 4

---

## 前置约束

### 项目铁律

```bash
cd packages/web
bun run format      # 0 报错
bun run lint:fix    # 0 报错
bun run typecheck   # 0 error
bun run test        # 0 新 fail (跟 baseline 对比)
```

### Baseline 测试快照 (Task 1 前必跑)

```bash
cd packages/web
bun run test 2>&1 | tee /tmp/baseline-test.log
```

记录 baseline fail 列表. Task 1 末尾跑 `bun run test`, 跟 baseline 对比, fail 列表不能增加.

### 命名约定

- 文件名 kebab-case: `page.test.tsx`
- 组件声明: `const BuyersPage = () => {}`, 禁止 `function`
- 变量名: 无单字符 (`idx` 替代 `i`, `val` 替代 `v`)
- 魔法数字: 提取到顶层 `const` 或 import from `@/const/index` (`ZERO`)
- import: 按字母排序 (oxlint sort-imports)
- 注释: 中文
- 行内 `onClick` 复杂表达式禁止, 提取命名函数
- 行内三元表达式禁止, 改 if/else

### 行数硬指标

| 文件 | 行数目标 |
|---|---|
| `buyers/page.tsx` (改后) | ≤ 240 行 (现状 195, 加 ~45 行动态列逻辑) |
| `buyers/page.test.tsx` (新) | ≤ 220 行 |

### 0 调用方改动 (硬约束)

`git diff` 必须空:

```bash
git diff packages/web/app/[locale]/buyers/\[id\]/page.tsx \
         packages/web/app/[locale]/buyers/\[id\]/_components/change-timeline.tsx \
         packages/web/app/[locale]/buyers/\[id\]/_components/profile-card.tsx \
         packages/web/app/[locale]/buyers/layout.tsx \
         packages/web/app/[locale]/admin/profile-fields/page.tsx
```

### 0 后端 / schema / API 改动

`packages/service/**` 不能动. `packages/web/lib/buyer-profile/types.ts` 不能动.

---

## 文件结构总览

```
packages/web/app/[locale]/buyers/
  ├── page.tsx                    # 改: 195 → ≤240 行
  ├── page.test.tsx               # 新: ≤220 行, 9 it
  ├── layout.tsx                  # 不动
  └── [id]/page.tsx               # 不动

packages/web/app/[locale]/admin/profile-fields/page.tsx  # 不动

packages/web/lib/buyer-profile/
  ├── types.ts                    # 不动
  └── hooks.ts                    # 不动

packages/web/messages/
  ├── zh.json                     # 改: +"是" / +"否"
  └── en.json                     # 改: +"Yes" / +"No"
```

---

### Task 1: 实施完整 feature (1 个原子 commit)

**Files**:
- Modify: `packages/web/app/[locale]/buyers/page.tsx`
- Create: `packages/web/app/[locale]/buyers/page.test.tsx`
- Modify: `packages/web/messages/zh.json`
- Modify: `packages/web/messages/en.json`

**目标**: 1 个原子 commit 完成所有改动. 不分多 commit (因为测试失败状态下 commit 中间版本会破坏其他调用方).

- [ ] **Step 1.1: 写失败测试 (TDD 红)**

文件 `packages/web/app/[locale]/buyers/page.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import BuyersPage from "./page";

// Mock hooks — 不连真后端
vi.mock("@/lib/buyer-profile/hooks", () => ({
  useBuyerProfiles: vi.fn(),
  useFieldConfigs: vi.fn(),
  useCreateFieldConfig: vi.fn(),
  useUpdateFieldConfig: vi.fn(),
}));

import { useBuyerProfiles, useFieldConfigs } from "@/lib/buyer-profile/hooks";

const TEST_PROFILE_COUNT = 2;
const FIRST_INDEX = 0;
const ZERO_INDEX = 0;

const mockProfiles = [
  {
    buyer_key: "k1",
    buyer_name: "张三",
    first_seen_at: null,
    id: "1",
    last_contact_at: null,
    notes: null,
    profile_data: {
      budget: { confidence: "high", source: "auto", updated_at: null, value: 50000 },
      region: { confidence: "high", source: "auto", updated_at: null, value: "华东" },
      products: { confidence: "medium", source: "auto", updated_at: null, value: ["云屏", "数显"] },
      active: { confidence: "high", source: "auto", updated_at: null, value: true },
    },
    status: "active",
    tags: [],
  },
  {
    buyer_key: "k2",
    buyer_name: "李四",
    first_seen_at: null,
    id: "2",
    last_contact_at: null,
    notes: null,
    profile_data: {
      budget: { confidence: "high", source: "auto", updated_at: null, value: 80000 },
      region: { confidence: "high", source: "auto", updated_at: null, value: "华北" },
      products: { confidence: "medium", source: "auto", updated_at: null, value: ["仪表"] },
      active: { confidence: "high", source: "auto", updated_at: null, value: false },
    },
    status: "archived",
    tags: [],
  },
];

const mockFieldConfigs = [
  { code: "budget", extraction_prompt: null, field_type: "number", id: 1, is_active: true, label: "预算", notify_on_change: [], options: [], sort_order: 1 },
  { code: "region", extraction_prompt: null, field_type: "select", id: 2, is_active: true, label: "区域", notify_on_change: [], options: [], sort_order: 2 },
  { code: "products", extraction_prompt: null, field_type: "tags", id: 3, is_active: true, label: "产品", notify_on_change: [], options: [], sort_order: 3 },
  { code: "active", extraction_prompt: null, field_type: "boolean", id: 4, is_active: true, label: "活跃", notify_on_change: [], options: [], sort_order: 4 },
  { code: "disabled_field", extraction_prompt: null, field_type: "text", id: 5, is_active: false, label: "停用字段", notify_on_change: [], options: [], sort_order: 5 },
];

const renderPage = () =>
  render(
    <IntlWrapper locale="zh">
      <BuyersPage />
    </IntlWrapper>,
  );

describe("BuyersPage 动态画像列", () => {
  it("基础渲染: 表格 + 列头 + 行数", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    expect(screen.getAllByTestId("data-table-row")).toHaveLength(TEST_PROFILE_COUNT);
  });

  it("按 sort_order 升序渲染动态列", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    const headers = Array.from(container.querySelectorAll("th")).map((th) => th.textContent);
    const budgetIdx = headers.indexOf("预算");
    const regionIdx = headers.indexOf("区域");
    const productsIdx = headers.indexOf("产品");
    const activeIdx = headers.indexOf("活跃");
    expect(budgetIdx).toBeGreaterThan(-1);
    expect(regionIdx).toBeGreaterThan(budgetIdx);
    expect(productsIdx).toBeGreaterThan(regionIdx);
    expect(activeIdx).toBeGreaterThan(productsIdx);
  });

  it("is_active=false 字段不渲染列", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    expect(screen.queryByText("停用字段")).not.toBeInTheDocument();
  });

  it("buyer_key 列已删除", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    const headers = Array.from(container.querySelectorAll("th")).map((th) => th.textContent);
    expect(headers).not.toContain("标识");
  });

  it("select 字段画 Badge", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      const cells = screen.getAllByText("华东");
      expect(cells.length).toBeGreaterThan(ZERO_INDEX);
    });
    expect(screen.getByText("华东").closest('[class*="rounded"]')).toBeTruthy();
  });

  it("tags 字段画多个 Badge", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("云屏")).toBeInTheDocument();
    });
    expect(screen.getByText("云屏")).toBeInTheDocument();
    expect(screen.getByText("数显")).toBeInTheDocument();
    expect(screen.getByText("仪表")).toBeInTheDocument();
  });

  it("boolean 字段画 是/否", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    const yesCells = screen.getAllByText("是");
    const noCells = screen.getAllByText("否");
    expect(yesCells.length).toBeGreaterThan(ZERO_INDEX);
    expect(noCells.length).toBeGreaterThan(ZERO_INDEX);
  });

  it("缺失 profile_data 字段渲染 —", async () => {
    const profilesMissingField = [
      {
        buyer_key: "k1",
        buyer_name: "王五",
        first_seen_at: null,
        id: "1",
        last_contact_at: null,
        notes: null,
        profile_data: {}, // 全部缺失
        status: "active",
        tags: [],
      },
    ];
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: profilesMissingField, total: 1 },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: mockFieldConfigs,
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useFieldConfigs>);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("王五")).toBeInTheDocument();
    });
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(4); // 4 个动态字段都缺失
  });

  it("useFieldConfigs 失败回退基础 5 列", async () => {
    vi.mocked(useBuyerProfiles).mockReturnValue({
      data: { items: mockProfiles, total: TEST_PROFILE_COUNT },
      isLoading: false,
      error: null,
    } as unknown as ReturnType<typeof useBuyerProfiles>);
    vi.mocked(useFieldConfigs).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("network error"),
    } as unknown as ReturnType<typeof useFieldConfigs>);

    const { container } = renderPage();

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });
    const headers = Array.from(container.querySelectorAll("th")).map((th) => th.textContent);
    expect(headers).not.toContain("预算");
    expect(headers).not.toContain("区域");
    expect(headers).not.toContain("产品");
    expect(headers).not.toContain("活跃");
    expect(screen.getByText("network error")).toBeInTheDocument();
  });
});
```

- [ ] **Step 1.2: 跑测试, 确认失败**

```bash
cd packages/web
bun run test buyers/page.test.tsx 2>&1 | tail -20
```

预期: FAIL (page.test.tsx 不存在 OR mock 未设置 OR 页面渲染失败)

- [ ] **Step 1.3: 加 i18n keys**

文件 `packages/web/messages/zh.json`, 在 `}` 闭合前 (即文件末尾 JSON 最后一个键值对后) 加:

```json
  ,
  "是": "是",
  "否": "否",
```

实际编辑: 找文件中最后一个键 (例 `"买家不存在"`), 在它后面加逗号 + `"是"` / `"否"` 2 行. 保持 identity 模式 (value=key).

文件 `packages/web/messages/en.json`, 同样位置加:

```json
  ,
  "是": "Yes",
  "否": "No"
```

验证 JSON 合法:

```bash
cd packages/web
node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"
```

预期: `OK`

- [ ] **Step 1.4: 改造 buyers/page.tsx**

文件 `packages/web/app/[locale]/buyers/page.tsx`, 用以下完整内容替换 (现状 195 行 → 改造后 ~230 行):

```tsx
"use client";
// 买家列表页 (2026-06-22 buyer-profile spec, 2026-06-25 动态画像列)
// TanStack Query 客户端获取 + DataTable 展示 + 状态筛选
// 动态列: useFieldConfigs() 激活字段按 sort_order 升序生成列, 按 field_type 差异化渲染

import { useRouter } from "@/i18n/navigation";
import { type ColumnDef, type ColumnWidth, DataTable } from "@/components/common/table/data-table";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { LoadingSkeleton } from "@/components/common/button/app-loading-skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ZERO } from "@/const/index";
import { useBuyerProfiles, useFieldConfigs } from "@/lib/buyer-profile/hooks";
import { Search, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import type { BuyerProfile, ProfileFieldConfig } from "@/lib/buyer-profile/types";

const STATUS_ALL = "";
const TWO_DIGIT = 2;
const PAD_CHAR = "0";
const FIRST = 1;
const INDEX_COL_WIDTH = 56;
const NAME_COL_WIDTH = 240;
const STATUS_COL_WIDTH = 100;
const DATE_COL_WIDTH = 160;
const ACTIONS_COL_WIDTH = 100;
const PROFILE_COL_MIN = 120;
const PROFILE_COL_MAX = 240;

const filterProfiles = (items: BuyerProfile[], searchText: string): BuyerProfile[] => {
  if (!searchText) {
    return items;
  }
  const query = searchText.toLowerCase();
  return items.filter(
    (profile) =>
      profile.buyer_name?.toLowerCase().includes(query) ||
      profile.buyer_key.toLowerCase().includes(query),
  );
};

const formatDate = (iso: string | null): string => {
  if (!iso) {
    return "—";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(new Date(iso));
};

const getStatusVariant = (status: string): "default" | "secondary" | "outline" | "destructive" => {
  switch (status) {
    case "active": {
      return "default";
    }
    case "archived": {
      return "secondary";
    }
    default: {
      return "outline";
    }
  }
};

const getProfileFieldValue = (row: BuyerProfile, code: string): unknown => {
  const field = row.profile_data[code];
  if (field === undefined) {
    return undefined;
  }
  return field.value;
};

const isEmptyValue = (value: unknown): boolean => value === null || value === undefined;

const buildSelectCell = (row: BuyerProfile, code: string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (isEmptyValue(value)) {
    return "—";
  }
  return <Badge variant="secondary">{String(value)}</Badge>;
};

const buildTagsCell = (row: BuyerProfile, code: string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (!Array.isArray(value) || value.length === ZERO) {
    return "—";
  }
  const tags = value.filter((tag): tag is string => typeof tag === "string");
  if (tags.length === ZERO) {
    return "—";
  }
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag} variant="secondary">
          {tag}
        </Badge>
      ))}
    </div>
  );
};

const buildNumberCell = (row: BuyerProfile, code: string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (isEmptyValue(value)) {
    return "—";
  }
  return <span className="num text-sm">{String(value)}</span>;
};

const buildBooleanCell = (row: BuyerProfile, code: string, translate: (key: string) => string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (isEmptyValue(value)) {
    return "—";
  }
  return value === true || value === "true" ? translate("是") : translate("否");
};

const buildTextCell = (row: BuyerProfile, code: string): ReactNode => {
  const value = getProfileFieldValue(row, code);
  if (isEmptyValue(value)) {
    return "—";
  }
  return <span className="text-sm">{String(value)}</span>;
};

const buildProfileColumn = (cfg: ProfileFieldConfig, translate: (key: string) => string): ColumnDef<BuyerProfile> => {
  const width: ColumnWidth = { max: PROFILE_COL_MAX, min: PROFILE_COL_MIN };
  const baseColumn: ColumnDef<BuyerProfile> = {
    key: `profile_${cfg.code}`,
    title: cfg.label,
    width,
  };
  switch (cfg.field_type) {
    case "select":
      return { ...baseColumn, render: (row) => buildSelectCell(row, cfg.code) };
    case "tags":
      return { ...baseColumn, render: (row) => buildTagsCell(row, cfg.code) };
    case "number":
      return { ...baseColumn, render: (row) => buildNumberCell(row, cfg.code) };
    case "boolean":
      return { ...baseColumn, render: (row) => buildBooleanCell(row, cfg.code, translate) };
    default:
      return { ...baseColumn, render: (row) => buildTextCell(row, cfg.code) };
  }
};

const buildColumns = (
  translate: (key: string) => string,
  activeFields: ProfileFieldConfig[],
): ColumnDef<BuyerProfile>[] => {
  const profileColumns = activeFields.map((cfg) => buildProfileColumn(cfg, translate));
  return [
    {
      key: "index",
      render: (_row, idx) => (
        <span className="num text-sm text-muted-foreground">
          {String(idx + FIRST).padStart(TWO_DIGIT, PAD_CHAR)}
        </span>
      ),
      title: "#",
      width: INDEX_COL_WIDTH,
    },
    {
      key: "buyer_name",
      render: (row) => <span className="truncate text-sm font-medium">{row.buyer_name ?? "—"}</span>,
      title: translate("买家"),
      width: NAME_COL_WIDTH,
    },
    ...profileColumns,
    {
      key: "status",
      render: (row) => <Badge variant={getStatusVariant(row.status)}>{row.status}</Badge>,
      title: translate("状态"),
      width: STATUS_COL_WIDTH,
    },
    {
      key: "last_contact_at",
      render: (row) => (
        <span className="num text-sm text-muted-foreground">{formatDate(row.last_contact_at)}</span>
      ),
      title: translate("最近联系"),
      width: DATE_COL_WIDTH,
    },
    {
      key: "actions",
      render: (_row) => (
        <Button size="sm" variant="ghost">
          {translate("查看")}
        </Button>
      ),
      title: translate("操作"),
      width: ACTIONS_COL_WIDTH,
    },
  ];
};

const BuyersPage = () => {
  const translate = useTranslations();
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState(STATUS_ALL);
  const [searchText, setSearchText] = useState("");

  const { data, isLoading: isLoadingProfiles, error: profilesError } = useBuyerProfiles(
    statusFilter ? { status: statusFilter } : undefined,
  );
  const { data: configs = [], isLoading: isLoadingFields, error: fieldsError } = useFieldConfigs();

  if (isLoadingProfiles || isLoadingFields) {
    return <LoadingSkeleton rows={5} />;
  }

  const activeFields = useMemo(
    () =>
      configs
        .filter((cfg) => cfg.is_active)
        .slice()
        .sort((a, b) => a.sort_order - b.sort_order),
    [configs],
  );

  const columns = useMemo(() => buildColumns(translate, activeFields), [translate, activeFields]);
  const filteredItems = filterProfiles(data?.items ?? [], searchText);

  const handleRowClick = (row: BuyerProfile) => {
    router.push(`/buyers/${row.id}`);
  };

  const profilesErrorMessage = profilesError instanceof Error ? profilesError.message : null;
  const fieldsErrorMessage = fieldsError instanceof Error ? fieldsError.message : null;

  return (
    <div className="space-y-6 p-6">
      <PageHero eyebrow="Buyers" title={translate("客户画像")} />

      <div className="flex items-center gap-3">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8"
            onChange={(ev) => setSearchText(ev.target.value)}
            placeholder={translate("搜索")}
            value={searchText}
          />
        </div>
        <div className="flex items-center gap-1">
          <Button
            onClick={() => setStatusFilter(STATUS_ALL)}
            size="sm"
            variant={statusFilter === STATUS_ALL ? "default" : "outline"}
          >
            {translate("全部")}
          </Button>
          <Button
            onClick={() => setStatusFilter("active")}
            size="sm"
            variant={statusFilter === "active" ? "default" : "outline"}
          >
            {translate("激活")}
          </Button>
          <Button
            onClick={() => setStatusFilter("archived")}
            size="sm"
            variant={statusFilter === "archived" ? "default" : "outline"}
          >
            {translate("已归档")}
          </Button>
        </div>
      </div>

      {profilesErrorMessage && (
        <ErrorBanner
          description={profilesErrorMessage ?? translate("出错了")}
          variant="destructive"
        />
      )}
      {fieldsErrorMessage && (
        <ErrorBanner
          description={fieldsErrorMessage ?? translate("出错了")}
          variant="destructive"
        />
      )}

      <DataTable<BuyerProfile>
        columns={columns}
        dataSource={filteredItems}
        emptyText={<DataEmpty icon={Users} title={translate("暂无买家")} />}
        onRowClick={handleRowClick}
        rowKey="id"
      />
    </div>
  );
};

export default BuyersPage;
```

- [ ] **Step 1.5: 跑测试, 确认通过**

```bash
cd packages/web
bun run test buyers/page.test.tsx 2>&1 | tail -20
```

预期: PASS (9/9 it)

- [ ] **Step 1.6: 跑全套测试, 跟 baseline 对比**

```bash
cd packages/web
bun run test 2>&1 | tail -10
```

预期: fail 列表 == baseline (新 9 个 it 全部通过, 老 it 不动)

- [ ] **Step 1.7: 跑全套质量检查**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
```

预期:
- format: 0 报错
- lint:fix: 0 报错 (可能含 1 个 pre-existing warning in app-dialog.test.tsx, 不算)
- typecheck: 0 error

- [ ] **Step 1.8: 验证 0 调用方改动 + 0 后端改动**

```bash
cd "c:/Users/abcuc/Desktop/rag"
git diff packages/web/app/[locale]/buyers/\[id\]/page.tsx \
         packages/web/app/[locale]/buyers/\[id\]/_components/change-timeline.tsx \
         packages/web/app/[locale]/buyers/\[id\]/_components/profile-card.tsx \
         packages/web/app/[locale]/buyers/layout.tsx \
         packages/web/app/[locale]/admin/profile-fields/page.tsx

git diff packages/web/lib/buyer-profile/types.ts \
         packages/web/lib/buyer-profile/hooks.ts

git status packages/service/
```

预期: 3 个 diff 全空 (前端 + lib + 后端都不动)

- [ ] **Step 1.9: 验证行数**

```bash
cd packages/web
wc -l app/\[locale\]/buyers/page.tsx app/\[locale\]/buyers/page.test.tsx
```

预期: page.tsx ≤ 240, page.test.tsx ≤ 220

- [ ] **Step 1.10: 原子 commit**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck

cd ../..
git add packages/web/app/\[locale\]/buyers/page.tsx \
        packages/web/app/\[locale\]/buyers/page.test.tsx \
        packages/web/messages/zh.json \
        packages/web/messages/en.json

git commit -m "feat(buyers): 表格动态列展示画像字段 + 删除 buyer_key 列

- 表格列顺序: # / 买家 / [动态画像 N 列] / 状态 / 最近联系 / 操作
- 动态列来源: useFieldConfigs() 激活 (is_active=true) 且按 sort_order 升序
- 渲染按 field_type 差化: select/tags → Badge, number → 等宽字体,
  boolean → 是/否, 其他纯文本, null → —
- 删除 buyer_key 列 (业务上 buyer_key 是机器标识, 不展示给客户)
- 加 page.test.tsx (9 it), mock hook + 0 真后端连
- i18n zh/en.json 加 是/否/Yes/No (boolean 渲染)

0 后端 / schema / API 改动, 0 admin/profile-fields 改动,
4 个买家详情页 0 改动."
```

---

## 验收总表

| 维度 | 验收命令 | 预期 |
|---|---|---|
| page.tsx 行数 | `wc -l buyers/page.tsx` | ≤ 240 |
| page.test.tsx 行数 | `wc -l buyers/page.test.tsx` | ≤ 220 |
| 测试 it 数 | `bun run test buyers/page.test.tsx` | 9 it 全过 |
| 调用方 0 改动 | `git diff` 4 文件 | 空 |
| 后端 0 改动 | `git status packages/service/` | 无新 M |
| lib 0 改动 | `git diff packages/web/lib/buyer-profile/` | 空 |
| format | `bun run format` | 0 报错 |
| lint | `bun run lint` | 0 报错 (允许 1 pre-existing warning) |
| typecheck | `bun run typecheck` | 0 error |
| 全套测试 | `bun run test` | fail 列表 == baseline |

## 关联文档

- Spec: [docs/superpowers/specs/2026-06-25-buyers-dynamic-columns-design.md](../../specs/2026-06-25-buyers-dynamic-columns-design.md)
- 上游 spec: [docs/superpowers/specs/2026-06-22-buyer-profile-design.md](../../specs/2026-06-22-buyer-profile-design.md)
- DataTable 封装: [docs/superpowers/specs/2026-06-25-data-table-split-design.md](../../specs/2026-06-25-data-table-split-design.md)
- 项目铁律: [packages/web/CLAUDE.md](../../../../packages/web/CLAUDE.md)
- 测试隔离 4 模式: [packages/web/CLAUDE.md §测试规范](../../../../packages/web/CLAUDE.md)

## Self-Review

### Spec coverage

| Spec 章节 | 覆盖 task |
|---|---|
| §1 目标 (动态列 + 删除 buyer_key) | Task 1 Step 1.4 |
| §2 YAGNI (0 后端 / 0 schema / 0 admin) | Task 1 Step 1.8 验证 |
| §3.1 数据流 | Task 1 Step 1.4 (useFieldConfigs + useBuyerProfiles) |
| §3.3 错误处理 | Task 1 Step 1.4 (ProfilesError + fieldsError 聚合) + Step 1.4 test it |
| §3.4 buildProfileColumn | Task 1 Step 1.4 完整代码 |
| §3.5 buildColumns 改造 | Task 1 Step 1.4 完整代码 |
| §3.6 i18n 是/否 | Task 1 Step 1.3 |
| §3.7 错误处理策略 | Task 1 Step 1.4 + test it 9 |
| §3.9 测试策略 | Task 1 Step 1.1 (9 it 完整覆盖) |
| §5 验收 | Task 1 Step 1.5/1.6/1.7/1.8/1.9 |

✅ 全部覆盖

### Placeholder scan

- ✅ 0 TBD / TODO / "fill in"
- ✅ 所有代码块完整 (无空函数)
- ✅ 所有步骤有具体文件路径 + 命令

### Type consistency

- ✅ `buildProfileColumn(cfg: ProfileFieldConfig, translate: ...)` 跟 §3.4 一致
- ✅ `buildColumns(translate, activeFields)` 跟 §3.5 一致
- ✅ `ColumnWidth = { max: PROFILE_COL_MAX, min: PROFILE_COL_MIN }` 跟 §3.4 弹性宽一致
- ✅ Field value 类型 `unknown` 处理 5 种 (`isEmptyValue` + 4 字段类型判空)

## 执行 handoff

Plan 完成. 两种执行方式:

1. **Subagent-Driven (推荐)**: 派 subagent 实施 Task 1, 主会话 2-stage review
2. **Inline Execution**: 当前会话直接跑 Task 1

由于 Task 1 是 1 个原子 commit, 2 种方式差别不大. Subagent 略慢但能保留主会话上下文.

请选择执行方式.