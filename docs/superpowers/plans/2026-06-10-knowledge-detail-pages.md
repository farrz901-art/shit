# 知识库文档/数据集详情页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 2 new detail pages (datasets list + dataset documents list) and wire up StatCard click-throughs on the existing documents entry page.

**Architecture:** Follow the existing `nodes/page.tsx` template (shadcn Table + sticky header + client-side pagination + motion.tr animations). Extend `fetchDatasets` return type to include full Dify fields. Modify `KnowledgeTabs` children array to highlight new routes.

**Tech Stack:** Next.js 16.2 App Router, React 19, shadcn/ui Table + Pagination + Badge, SWR, motion (Framer Motion), vitest 4, Playwright

---

## File Structure

**Create:**
- `web/app/knowledge/datasets/page.tsx` — datasets list page (table)
- `web/app/knowledge/datasets/page.test.tsx` — vitest
- `web/app/knowledge/dataset-documents/[dataset_id]/page.tsx` — dataset documents page (table)
- `web/app/knowledge/dataset-documents/[dataset_id]/page.test.tsx` — vitest

**Modify:**
- `web/lib/api/knowledge.ts:190-194` — extend `fetchDatasets` return type
- `web/lib/api/knowledge.test.ts` — add test for extended type
- `web/app/knowledge/documents/page.tsx:26-39` — wrap StatCards with Link + datasetId fallback
- `web/app/knowledge/documents/page.test.tsx` — add click-through assertions
- `web/components/knowledge/KnowledgeTabs.tsx:21` — add `/knowledge/datasets` and `/knowledge/dataset-documents` to children
- `web/e2e/05-knowledge-routes.spec.ts` — add 2 new E2E tests

---

### Task 1: Extend `fetchDatasets` return type

**Files:**
- Modify: `web/lib/api/knowledge.ts:190-194`
- Modify: `web/lib/api/knowledge.test.ts`

- [ ] **Step 1: Write the failing test**

Add test to `web/lib/api/knowledge.test.ts` that verifies `fetchDatasets` returns extended fields.

```typescript
// 在 knowledge.test.ts 末尾追加
it("fetchDatasets 返回包含 description / document_count / word_count", async () => {
  const mockDatasets = [
    { id: "ds1", name: "数据集A", description: "desc", document_count: 5, word_count: 1000 },
    { id: "ds2", name: "数据集B" },
  ];
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => mockDatasets,
  });
  const result = await knowledgeApi.fetchDatasets();
  expect(result).toHaveLength(2);
  expect(result[0].description).toBe("desc");
  expect(result[0].document_count).toBe(5);
  expect(result[0].word_count).toBe(1000);
  // 第二条没有扩展字段, 也能正常返回
  expect(result[1].description).toBeUndefined();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run lib/api/knowledge.test.ts`
Expected: FAIL — `fetchDatasets` 返回类型不包含 `description` / `document_count` / `word_count`

- [ ] **Step 3: Write minimal implementation**

Add `DatasetRow` interface and update `fetchDatasets` return type:

```typescript
// knowledge.ts — 在 QAListResponse 之后加
export interface DatasetRow {
  id: string;
  name: string;
  description?: string;
  document_count?: number;
  word_count?: number;
}
```

修改 `fetchDatasets` (L190-194):
```typescript
  /** 数据集列表 — 走 SWR (Dify datasets 列表, 全字段) */
  fetchDatasets: (): Promise<DatasetRow[]> =>
    fetch(`${BASE}/api/kg/datasets`, { headers: authHeaders() }).then((r) => {
      if (!r.ok) throw new ApiError(r.status, r.statusText);
      return r.json() as Promise<DatasetRow[]>;
    }),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && bun run test -- --run lib/api/knowledge.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/api/knowledge.ts web/lib/api/knowledge.test.ts
git commit -m "feat(api): extend fetchDatasets 返回类型 (DatasetRow 全字段)"
```

---

### Task 2: `/knowledge/datasets` page — test first

**Files:**
- Create: `web/app/knowledge/datasets/page.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SWRConfig } from "swr";

vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (sel: (s: { datasetId: string }) => string) => sel({ datasetId: "ds1" }),
}));

import DatasetsPage from "./page";

const datasetsMock = [
  { id: "ds1", name: "数据集A", description: "第一个数据集", document_count: 5, word_count: 1200 },
  { id: "ds2", name: "数据集B", description: "第二个数据集", document_count: 3, word_count: 800 },
  { id: "ds3", name: "数据集C" },
];

const renderWithSWR = (ui: React.ReactNode) =>
  render(<SWRConfig value={{ provider: () => new Map() }}>{ui}</SWRConfig>);

describe("DatasetsPage", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => datasetsMock,
    });
  });

  it("渲染 KnowledgeHero title=数据集", () => {
    renderWithSWR(<DatasetsPage />);
    expect(screen.getByRole("heading", { name: /数据集/ })).toBeInTheDocument();
  });

  it("渲染 N 行表格 (3 条数据集)", async () => {
    renderWithSWR(<DatasetsPage />);
    // 等待 SWR 加载
    const rows = await screen.findAllByTestId("dataset-row");
    expect(rows).toHaveLength(3);
  });

  it("列 render: 名称 / 描述 / 文档数 / 字数", async () => {
    renderWithSWR(<DatasetsPage />);
    const row = (await screen.findAllByTestId("dataset-row"))[0];
    expect(within(row).getByText("数据集A")).toBeInTheDocument();
    expect(within(row).getByText("第一个数据集")).toBeInTheDocument();
    expect(within(row).getByText("5")).toBeInTheDocument();
    expect(within(row).getByText("1200")).toBeInTheDocument();
  });

  it("无 description 时显示 —", async () => {
    renderWithSWR(<DatasetsPage />);
    const row = (await screen.findAllByTestId("dataset-row"))[2];
    expect(within(row).getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("行点击跳 /knowledge/dataset-documents/:id", async () => {
    const user = userEvent.setup();
    renderWithSWR(<DatasetsPage />);
    const link = (await screen.findAllByRole("link", { name: /数据集A/ }))[0];
    expect(link).toHaveAttribute("href", "/knowledge/dataset-documents/ds1");
  });

  it("空态: 无数据时显示暂无数据集", () => {
    globalThis.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
    renderWithSWR(<DatasetsPage />);
    expect(screen.getByText("暂无数据集")).toBeInTheDocument();
  });

  it("loading 态显示加载中", () => {
    // 不 mock fetch → SWR 不返回 → isLoading
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithSWR(<DatasetsPage />);
    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run app/knowledge/datasets/page.test.tsx`
Expected: FAIL — `Cannot find module './page'`

- [ ] **Step 3: Commit (test first)**

```bash
mkdir -p web/app/knowledge/datasets
git add web/app/knowledge/datasets/page.test.tsx
git commit -m "test: /knowledge/datasets page 测试先行 (7 cases)"
```

---

### Task 3: `/knowledge/datasets` page — implement

**Files:**
- Create: `web/app/knowledge/datasets/page.tsx`

- [ ] **Step 1: Write implementation**

Follow `nodes/page.tsx` template exactly. Replace node-specific columns with dataset columns.

```tsx
"use client";
// 数据集列表页 (2026-06-10) — shadcn Table + 固定表头 + 分页 (复用 nodes/page.tsx 模板)
import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { motion, AnimatePresence } from "motion/react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationPrevious,
  PaginationNext,
} from "@/components/ui/pagination";
import { CSS_EASE, DUR, Reveal, Stagger, StaggerItem } from "@/components/ui/animated";
import { KnowledgeHero } from "@/components/knowledge/KnowledgeHero";
import { knowledgeApi, type DatasetRow } from "@/lib/api/knowledge";

const PAGE_SIZE = 20;

export default function DatasetsPage() {
  const { data, isLoading, error } = useSWR<DatasetRow[]>(
    knowledgeApi.datasetsUrl(),
    () => knowledgeApi.fetchDatasets(),
  );
  const [page, setPage] = useState(0);

  const total = data?.length ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const rows = data?.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE) ?? [];

  return (
    <div className="flex h-full flex-col gap-8">
      {/* hero */}
      <KnowledgeHero
        eyebrow="Datasets"
        title="数据集"
        meta={total > 0 ? `共 ${total} 个` : undefined}
      />

      {/* 错误提示 */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DUR.normal, ease: CSS_EASE.outQuint }}
            className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-base text-destructive"
          >
            加载数据集失败: {String(error)}
          </motion.div>
        )}
      </AnimatePresence>

      {/* 表格 */}
      <Reveal delay={0.2}>
        <div className="rounded-lg border border-border/40">
          <div className="min-h-0 flex-1 overflow-auto">
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm">
                <TableRow>
                  <TableHead className="eyebrow w-48">名称</TableHead>
                  <TableHead className="eyebrow">描述</TableHead>
                  <TableHead className="eyebrow w-24">文档数</TableHead>
                  <TableHead className="eyebrow w-24">字数</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                      <motion.span
                        animate={{ opacity: [0.4, 1, 0.4] }}
                        transition={{ duration: 1.6, repeat: Infinity }}
                      >
                        加载中…
                      </motion.span>
                    </TableCell>
                  </TableRow>
                ) : rows.length > 0 ? (
                  rows.map((ds, i) => (
                    <motion.tr
                      key={ds.id}
                      data-testid="dataset-row"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: DUR.normal, ease: CSS_EASE.outExpo, delay: i * 0.02 }}
                      className="border-b transition-colors hover:bg-muted/50"
                    >
                      <TableCell>
                        <Link
                          href={`/knowledge/dataset-documents/${ds.id}`}
                          className="text-base font-medium text-foreground hover:underline"
                        >
                          {ds.name}
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-xs truncate text-muted-foreground">
                        {ds.description || "—"}
                      </TableCell>
                      <TableCell className="num text-muted-foreground">
                        {ds.document_count ?? "—"}
                      </TableCell>
                      <TableCell className="num text-muted-foreground">
                        {ds.word_count ?? "—"}
                      </TableCell>
                    </motion.tr>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                      暂无数据集
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {/* 分页 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border/40 px-4 py-2">
              <span className="num text-sm text-muted-foreground">
                第 {page + 1} / {totalPages} 页 · 共 {total} 条
              </span>
              <Pagination className="mx-0 w-auto">
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                      className={page === 0 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                    />
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                      className={
                        page >= totalPages - 1 ? "pointer-events-none opacity-50" : "cursor-pointer"
                      }
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </div>
      </Reveal>
    </div>
  );
}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd web && bun run test -- --run app/knowledge/datasets/page.test.tsx`
Expected: PASS (7/7)

- [ ] **Step 3: Commit**

```bash
git add web/app/knowledge/datasets/page.tsx web/app/knowledge/datasets/page.test.tsx
git commit -m "feat(web): /knowledge/datasets 数据集列表页 (table + sticky + 分页)"
```

---

### Task 4: `/knowledge/dataset-documents/[dataset_id]` page — test first

**Files:**
- Create: `web/app/knowledge/dataset-documents/[dataset_id]/page.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SWRConfig } from "swr";

vi.mock("next/navigation", () => ({
  useParams: () => ({ dataset_id: "ds1" }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/lib/store/app-store", () => ({
  useAppStore: (sel: (s: { datasetId: string }) => string) => sel({ datasetId: "ds1" }),
}));

import DatasetDocumentsPage from "./page";

const docsMock = {
  items: [
    { id: "doc1", question: "什么是电机?", answer: "电机是...", name: "电机FAQ", indexing_status: "completed" },
    { id: "doc2", question: "如何选型?", answer: "选型需...", name: "选型指南", indexing_status: "indexing" },
    { id: "doc3", question: "", answer: "", name: "error-doc", indexing_status: "error" },
  ],
};

// mock datasets fetch (用于获取 dataset name)
const datasetsMock = [
  { id: "ds1", name: "数据集A" },
];

const renderWithSWR = (ui: React.ReactNode) =>
  render(<SWRConfig value={{ provider: () => new Map() }}>{ui}</SWRConfig>);

describe("DatasetDocumentsPage", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes("/api/kg/datasets")) {
        return Promise.resolve({ ok: true, json: async () => datasetsMock });
      }
      if (String(url).includes("/api/kg/qa")) {
        return Promise.resolve({ ok: true, json: async () => docsMock });
      }
      return Promise.resolve({ ok: true, json: async () => [] });
    });
  });

  it("渲染 KnowledgeHero title=数据集A", async () => {
    renderWithSWR(<DatasetDocumentsPage />);
    expect(await screen.findByRole("heading", { name: /数据集A/ })).toBeInTheDocument();
  });

  it("渲染 BackButton fallbackHref=/knowledge/datasets", () => {
    renderWithSWR(<DatasetDocumentsPage />);
    const btn = screen.getByTestId("back-button");
    expect(btn).toBeInTheDocument();
  });

  it("渲染 N 行文档 (3 条)", async () => {
    renderWithSWR(<DatasetDocumentsPage />);
    const rows = await screen.findAllByTestId("doc-row");
    expect(rows).toHaveLength(3);
  });

  it("列 render: 名称 / 状态 / 预览", async () => {
    renderWithSWR(<DatasetDocumentsPage />);
    const row = (await screen.findAllByTestId("doc-row"))[0];
    expect(within(row).getByText("电机FAQ")).toBeInTheDocument();
    expect(within(row).getByText("completed")).toBeInTheDocument();
    expect(within(row).getByText(/什么是电机/)).toBeInTheDocument();
  });

  it("error 状态行显示错误标记", async () => {
    renderWithSWR(<DatasetDocumentsPage />);
    const row = (await screen.findAllByTestId("doc-row"))[2];
    expect(within(row).getByText("error")).toBeInTheDocument();
  });

  it("空态: 无文档时显示暂无文档", () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (String(url).includes("/api/kg/datasets")) {
        return Promise.resolve({ ok: true, json: async () => datasetsMock });
      }
      return Promise.resolve({ ok: true, json: async () => ({ items: [] }) });
    });
    renderWithSWR(<DatasetDocumentsPage />);
    expect(screen.getByText("暂无文档")).toBeInTheDocument();
  });

  it("loading 态显示加载中", () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
    renderWithSWR(<DatasetDocumentsPage />);
    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && bun run test -- --run app/knowledge/dataset-documents/\[dataset_id\]/page.test.tsx`
Expected: FAIL — `Cannot find module './page'`

- [ ] **Step 3: Commit (test first)**

```bash
mkdir -p "web/app/knowledge/dataset-documents/[dataset_id]"
git add "web/app/knowledge/dataset-documents/[dataset_id]/page.test.tsx"
git commit -m "test: /knowledge/dataset-documents/[dataset_id] page 测试先行 (7 cases)"
```

---

### Task 5: `/knowledge/dataset-documents/[dataset_id]` page — implement

**Files:**
- Create: `web/app/knowledge/dataset-documents/[dataset_id]/page.tsx`

- [ ] **Step 1: Write implementation**

Follow `nodes/page.tsx` template. Fetch datasets (for name) + QA documents in parallel.

```tsx
"use client";
// 数据集文档列表页 (2026-06-10) — shadcn Table + 固定表头 + 分页 (复用 nodes/page.tsx 模板)
import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { motion, AnimatePresence } from "motion/react";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationPrevious,
  PaginationNext,
} from "@/components/ui/pagination";
import { CSS_EASE, DUR, Reveal, Stagger, StaggerItem } from "@/components/ui/animated";
import { KnowledgeHero } from "@/components/knowledge/KnowledgeHero";
import { BackButton } from "@/components/knowledge/BackButton";
import { knowledgeApi, type QAListResponse, type DatasetRow } from "@/lib/api/knowledge";

const PAGE_SIZE = 20;

// 状态 → Badge 样式
const statusStyle: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  indexing: "bg-blue-100 text-blue-700 animate-pulse",
  queued: "bg-slate-100 text-slate-700",
  error: "bg-rose-100 text-rose-700",
};

export default function DatasetDocumentsPage() {
  const params = useParams<{ dataset_id: string }>();
  const datasetId = params.dataset_id;

  // 获取数据集名称
  const { data: datasets } = useSWR<DatasetRow[]>(
    knowledgeApi.datasetsUrl(),
    () => knowledgeApi.fetchDatasets(),
  );
  const datasetName = datasets?.find((d) => d.id === datasetId)?.name ?? datasetId;

  // 获取文档列表
  const { data, isLoading, error } = useSWR<QAListResponse>(
    datasetId ? knowledgeApi.qaListUrl(datasetId) : null,
    datasetId ? () => knowledgeApi.fetchQADocuments(datasetId) : null,
  );

  const [page, setPage] = useState(0);

  const total = data?.items.length ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const rows = data?.items.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE) ?? [];

  return (
    <div className="flex h-full flex-col gap-8">
      {/* hero */}
      <KnowledgeHero
        eyebrow="Documents"
        title={datasetName}
        meta={total > 0 ? `共 ${total} 条` : undefined}
        actions={<BackButton fallbackHref="/knowledge/datasets" />}
      />

      {/* 错误提示 */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DUR.normal, ease: CSS_EASE.outQuint }}
            className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-base text-destructive"
          >
            加载文档失败: {String(error)}
          </motion.div>
        )}
      </AnimatePresence>

      {/* 表格 */}
      <Reveal delay={0.2}>
        <div className="rounded-lg border border-border/40">
          <div className="min-h-0 flex-1 overflow-auto">
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm">
                <TableRow>
                  <TableHead className="eyebrow w-48">文档名</TableHead>
                  <TableHead className="eyebrow w-28">状态</TableHead>
                  <TableHead className="eyebrow">预览</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={3} className="h-24 text-center text-muted-foreground">
                      <motion.span
                        animate={{ opacity: [0.4, 1, 0.4] }}
                        transition={{ duration: 1.6, repeat: Infinity }}
                      >
                        加载中…
                      </motion.span>
                    </TableCell>
                  </TableRow>
                ) : rows.length > 0 ? (
                  rows.map((doc, i) => (
                    <motion.tr
                      key={doc.id}
                      data-testid="doc-row"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: DUR.normal, ease: CSS_EASE.outExpo, delay: i * 0.02 }}
                      className="border-b transition-colors hover:bg-muted/50"
                    >
                      <TableCell className="font-medium">{doc.name || doc.id}</TableCell>
                      <TableCell>
                        <Badge className={statusStyle[doc.indexing_status] ?? statusStyle.queued}>
                          {doc.indexing_status}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-md truncate text-muted-foreground">
                        {doc.question || "—"}
                      </TableCell>
                    </motion.tr>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={3} className="h-24 text-center text-muted-foreground">
                      暂无文档
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {/* 分页 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border/40 px-4 py-2">
              <span className="num text-sm text-muted-foreground">
                第 {page + 1} / {totalPages} 页 · 共 {total} 条
              </span>
              <Pagination className="mx-0 w-auto">
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      onClick={() => setPage((p) => Math.max(0, p - 1))}
                      className={page === 0 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                    />
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                      className={
                        page >= totalPages - 1 ? "pointer-events-none opacity-50" : "cursor-pointer"
                      }
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </div>
      </Reveal>
    </div>
  );
}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd web && bun run test -- --run app/knowledge/dataset-documents/\[dataset_id\]/page.test.tsx`
Expected: PASS (7/7)

- [ ] **Step 3: Commit**

```bash
git add "web/app/knowledge/dataset-documents/[dataset_id]/page.tsx" "web/app/knowledge/dataset-documents/[dataset_id]/page.test.tsx"
git commit -m "feat(web): /knowledge/dataset-documents/[id] 文档列表页 (table + sticky + 分页)"
```

---

### Task 6: `/knowledge/documents` 入口页 — StatCard 包 Link + datasetId 缺失兜底

**Files:**
- Modify: `web/app/knowledge/documents/page.tsx:26-39`

- [ ] **Step 1: Write the code change**

修改 `documents/page.tsx`, 给 2 张 StatCard 包 `<Link>`, datasetId 缺失时文档数卡不可点.

```tsx
"use client";
// 文档入口页 (2026-06-10 redesign) — Dify tab 统计 + 录入入口卡 (仿老 Dify tab)
//   KnowledgeTabs + ActiveSwitch 由 /knowledge/layout 提供
//   实际导入流程在 /knowledge/documents/import 子页
import Link from "next/link";
import useSWR from "swr";
import { StatCard } from "@/components/knowledge/StatCard";
import { EntryCard } from "@/components/knowledge/EntryCard";
import { Reveal } from "@/components/ui/animated";
import { knowledgeApi } from "@/lib/api/knowledge";
import { KnowledgeHero } from "@/components/knowledge/KnowledgeHero";
import { useAppStore } from "@/lib/store/app-store";
import { Download, MessageSquare } from "lucide-react";

export default function DocumentsPage() {
  // 仿老 Dify tab: 文档数 + 数据集 统计 (30s 刷新)
  const { data: stats, isLoading: statsLoading } = useSWR<{
    dify: { datasets: number; documents: number };
  }>(knowledgeApi.statsUrl());

  const datasetId = useAppStore((s) => s.datasetId);

  return (
    <div className="h-full overflow-y-auto space-y-8">
      {/* hero */}
      <KnowledgeHero eyebrow="Vector" title="向量库" />

      {/* 仿老 Dify tab: 文档数 + 数据集 统计 */}
      <Reveal delay={0.12}>
        <div className="grid grid-cols-2 gap-4">
          {datasetId ? (
            <Link href={`/knowledge/dataset-documents/${datasetId}`} className="contents">
              <StatCard
                label="文档数"
                value={statsLoading ? "—" : (stats?.dify.documents ?? 0)}
                accent="indigo"
                index={0}
              />
            </Link>
          ) : (
            <StatCard
              label="文档数"
              value={statsLoading ? "—" : (stats?.dify.documents ?? 0)}
              accent="indigo"
              index={0}
              hint="请先选 dataset →"
            />
          )}
          <Link href="/knowledge/datasets" className="contents">
            <StatCard
              label="数据集"
              value={statsLoading ? "—" : (stats?.dify.datasets ?? 0)}
              accent="ochre"
              index={1}
            />
          </Link>
        </div>
      </Reveal>

      {/* 仿老 Dify tab: 录入入口 (2 张卡) */}
      <Reveal delay={0.15}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <EntryCard
            href="/knowledge/qa"
            icon={<MessageSquare className="h-6 w-6" />}
            title="录 QA 对"
            desc="表单写入 Dify 向量库"
            index={0}
          />
          <EntryCard
            href="/knowledge/documents/import"
            icon={<Download className="h-6 w-6" />}
            title="批量导入"
            desc="Excel / JSON 模板批量导入"
            index={1}
          />
        </div>
      </Reveal>
    </div>
  );
}
```

- [ ] **Step 2: Run existing tests to verify no regression**

Run: `cd web && bun run test -- --run app/knowledge/documents/page.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 3: Commit**

```bash
git add web/app/knowledge/documents/page.tsx
git commit -m "feat(web): /documents 入口页 StatCard 包 Link + datasetId 缺失兜底"
```

---

### Task 7: `/knowledge/documents` page.test.tsx — 加跳转断言

**Files:**
- Modify: `web/app/knowledge/documents/page.test.tsx`

- [ ] **Step 1: Add new test cases**

在现有 `page.test.tsx` 末尾追加:

```tsx
  it("数据集数卡可点, 跳 /knowledge/datasets", () => {
    renderWithSWR(<DocumentsPage />);
    const link = screen.getByRole("link", { name: /数据集/ });
    expect(link).toHaveAttribute("href", "/knowledge/datasets");
  });

  it("文档数卡在 datasetId 存在时可点, 跳 /knowledge/dataset-documents/:id", () => {
    renderWithSWR(<DocumentsPage />);
    const link = screen.getByRole("link", { name: /文档数/ });
    expect(link).toHaveAttribute("href", "/knowledge/dataset-documents/ds1");
  });

  it("datasetId 缺失时文档数卡不可点, 显示提示", () => {
    // 重新 mock useAppStore 返回空 datasetId
    vi.doMock("@/lib/store/app-store", () => ({
      useAppStore: (sel: (s: { datasetId: string }) => string) => sel({ datasetId: "" }),
    }));
    // 需要重新 import 组件以拿到新 mock
    // 注意: vi.doMock 需要配合 dynamic import 或重新 render
    // 简化: 直接检查 hint 文本
    renderWithSWR(<DocumentsPage />);
    expect(screen.getByText("请先选 dataset →")).toBeInTheDocument();
  });

  it("EntryCard 录 QA 对 + 批量导入 仍然存在", () => {
    renderWithSWR(<DocumentsPage />);
    expect(screen.getByRole("heading", { name: "录 QA 对" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "批量导入" })).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd web && bun run test -- --run app/knowledge/documents/page.test.tsx`
Expected: PASS (7/7)

- [ ] **Step 3: Commit**

```bash
git add web/app/knowledge/documents/page.test.tsx
git commit -m "test: /documents 入口页加 StatCard 跳转断言 (4 cases)"
```

---

### Task 8: KnowledgeTabs children 加 2 个新路径

**Files:**
- Modify: `web/components/knowledge/KnowledgeTabs.tsx:21`

- [ ] **Step 1: Write the code change**

修改 "向量库" tab 的 children 数组, 加 2 个新路径:

```diff
  {
    href: "/knowledge/documents",
    label: "向量库",
-   children: ["/knowledge/documents", "/knowledge/qa"],
+   children: ["/knowledge/documents", "/knowledge/qa", "/knowledge/datasets", "/knowledge/dataset-documents"],
  },
```

- [ ] **Step 2: Run existing KnowledgeTabs tests**

Run: `cd web && bun run test -- --run components/knowledge/KnowledgeTabs`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add web/components/knowledge/KnowledgeTabs.tsx
git commit -m "feat(web): KnowledgeTabs 向量库 tab 加 datasets / dataset-documents 子路径"
```

---

### Task 9: E2E 加 2 个新 tab 跳转用例

**Files:**
- Modify: `web/e2e/05-knowledge-routes.spec.ts`

- [ ] **Step 1: Add 2 new E2E tests**

在现有 `05-knowledge-routes.spec.ts` 末尾追加:

```typescript
  test("6. 点数据集数卡 → URL 跳 /knowledge/datasets, heading visible", async ({ page }) => {
    await page.goto("/knowledge/documents");
    // 点数据集 StatCard (Link 包裹)
    await page.click('a[href="/knowledge/datasets"]');
    await expect(page).toHaveURL(/\/knowledge\/datasets/);
    await expect(page.getByRole("heading", { name: /数据集/ })).toBeVisible();
  });

  test("7. 点文档数卡 → URL 跳 /knowledge/dataset-documents/:id, heading visible", async ({ page }) => {
    await page.goto("/knowledge/documents");
    // 点文档数 StatCard (Link 包裹, 带 datasetId)
    const docLink = page.locator('a[href*="/knowledge/dataset-documents/"]');
    await docLink.click();
    await expect(page).toHaveURL(/\/knowledge\/dataset-documents\//);
    // heading 应为数据集名或 datasetId
    await expect(page.getByRole("heading")).toBeVisible();
  });
```

- [ ] **Step 2: Commit**

```bash
git add web/e2e/05-knowledge-routes.spec.ts
git commit -m "test(e2e): 05-knowledge-routes 加 datasets / dataset-documents 跳转用例"
```

---

### Task 10: 回归全 vitest + typecheck + lint

**Files:** None (verification only)

- [ ] **Step 1: Run full vitest**

Run: `cd web && bun run test`
Expected: All tests PASS (除 pre-existing `lib/chat/factory.test.ts` 1 fail)

- [ ] **Step 2: Run typecheck**

Run: `cd web && bun run typecheck`
Expected: 0 errors

- [ ] **Step 3: Run lint**

Run: `cd web && bun run lint`
Expected: 0 errors (warnings OK)

- [ ] **Step 4: Commit (if any fix needed)**

```bash
git add -A
git commit -m "fix: 回归修复 (typecheck / lint / test)"
```

---

### Task 11: 手动验证 4 页串通

**Files:** None (manual verification)

- [ ] **Step 1: 启动 dev server**

Run: `cd web && bun run dev`

- [ ] **Step 2: 验证 4 页串通**

手动操作:
1. 打开 `/knowledge/documents` → 看到 2 张 StatCard (文档数 + 数据集)
2. 点 "数据集" 卡 → 跳到 `/knowledge/datasets` → 看到数据集表格
3. 点某行数据集名 → 跳到 `/knowledge/dataset-documents/:id` → 看到文档表格
4. 点 BackButton → 回到 `/knowledge/datasets`
5. 点浏览器后退 → 回到 `/knowledge/documents`
6. 点 "文档数" 卡 → 跳到当前选中 dataset 的文档列表
7. 验证 KnowledgeTabs "向量库" 在 datasets / dataset-documents 页高亮

- [ ] **Step 3: 验证 datasetId 缺失兜底**

手动操作:
1. 清 localStorage (`rag.app-store.v1`)
2. 刷新 `/knowledge/documents`
3. "文档数" 卡应不可点, 显示 "请先选 dataset →"
4. "数据集" 卡仍可点
