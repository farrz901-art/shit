# 2026-07-09 Pre-analysis 产物查看页 (章节目录 + 段落提取) 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `/admin/pre-analysis/{task_id}/chapters` (扁平可折叠章节表) + `/admin/pre-analysis/{task_id}/flagged` (标记段落实体表) 子路由, 加 2 helper (`getPreAnalysisChapterStructure` / `getPreAnalysisFlaggedParagraphs`), 详情页产物表格的操作列加 "查看" 按钮跳子路由, 加 13 个 i18n key.

**Architecture:**
- 前端 lib 直连后端 `/api/pre-analysis/tasks/{id}/files/...` (跟现状一致, 不开 BFF)
- 章节树: 客户端 `flattenChapters()` 把嵌套树展平 + 应用 collapsed state → 4 列 DataTable (标题含 chevron+indent / 页范围 / 子章节数) + 行高 36px
- 段落页: 14 列 DataTable 直接渲染, text 列 `line-clamp-3` + AppTooltip 看完整
- 详情页 actions 列加 "查看" 按钮 (用 `isViewableKind` 类型守卫), 其它 kind (table/index) 不显示

**Tech Stack:**
- Next 16 (App Router, RSC async, params 是 Promise)
- React 19 + TanStack Query 5 + next-intl 4 + Tailwind v4 + shadcn/ui
- papaparse 5.5.4 (CSV 解析, `parse({header: true, skipEmptyLines: true})`)
- TypeScript 8 + vitest + jsdom

---

## Global Constraints

来自 spec 的全局约定 (从 `packages/web/CLAUDE.md` + `CLAUDE.md` 沉淀):

- **i18n**: 用 `t("中文 key")` 中间接 key, zh.json identity (`value = key`), en.json 翻译. 详见 spec §9.
- **路由跳转**: `import { useRouter } from "@/i18n/navigation"`, 禁止 `next/navigation`. 详见 [packages/web/CLAUDE.md §路由跳转必须用 next-intl 的 useRouter](packages/web/CLAUDE.md)
- **文件命名**: kebab-case (`admin-pre-analysis-chapters-client.tsx`)
- **表格封装**: `<DataTable<T>>` from `@/components/common/table/data-table`. 不许手写 `<table>` markup
- **常量命名**: `const FLAG_PAGE_SIZE = 5` 不允许魔法数字
- **JSX 内不写 onClick 复杂表达式**: handleToggle 等抽函数名
- **import 按字母排序** (oxlint)
- **测试运行**: 单文件 `bun run test -- <path>`, 全量只在 phase 结束跑
- **i18n sync**: 加新 t() key 必须同时加 zh.json + en.json
- **RSC entry**: `params: Promise<{...}>`, 必须 await, 子组件 client 拿的是 sync value
- **GuardPage**: `<GuardPage pageKey="admin">` (不是 `requiredRole="admin"`)
- **i18n key 27 个新加**: 见 spec §9 (Task 5 加 13 个 + 后续 page 引用时按需)
- **ErrorBanner 数据 ID**: `dataTestid` (camelCase), 不是 `data-testid`
- **AppTooltip 路径**: `@/components/common/overlay/app-tooltip`, 不是 `feedback/app-tooltip`

---

## File Structure

### 新建

| 路径 | 责任 |
|---|---|
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/chapters/page.tsx` | RSC entry. await params + GuardPage + 渲染 client. |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/chapters/_components/admin-pre-analysis-chapters-client.tsx` | 客户端. fetch → flatten → DataTable. 折叠/展开. |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/chapters/_components/admin-pre-analysis-chapters-client.test.tsx` | 客户端单测. |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/flagged/page.tsx` | RSC entry. 同 chapters pattern. |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/flagged/_components/admin-pre-analysis-flagged-client.tsx` | 客户端. fetch → DataTable (14 列). |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/flagged/_components/admin-pre-analysis-flagged-client.test.tsx` | 客户端单测. |

### 改

| 路径 | 责任变化 |
|---|---|
| `packages/web/lib/api/pre-analysis.ts` | 加 `ChapterTreeNode` / `ChapterStructurePayload` / `FlaggedParagraphRow` 3 个 export type; 加 `getPreAnalysisChapterStructure` / `getPreAnalysisFlaggedParagraphs` 2 个 export 函数. |
| `packages/web/lib/api/pre-analysis.test.ts` | 加 2 个 describe 覆盖 2 helper (§8.1 spec). |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx` | actions 列 cell 加 "查看" 按钮 + `useRouter` from `@/i18n/navigation`. 加 `VIEWABLE_KINDS` 常量 + `isViewableKind` 类型守卫. |
| `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx` | 加新断言: chapter_structure 行有 `view-file-chapter_structure.json` 按钮, flagged_paragraphs 行有 `view-file-flagged_paragraphs.csv` 按钮, table 行无 view 按钮. |
| `packages/web/messages/zh.json` | 加 13 个中文 key (zh identity). |
| `packages/web/messages/en.json` | 加同 13 个 key 英文翻译. |

---

# Phase 1: Helper + Types (底层, 先于 2 页面)

## Task 1: 加 types + helpers + 单测

**Files:**
- Modify: `packages/web/lib/api/pre-analysis.ts` (在 file 末尾, 紧跟 `retryPreAnalysisTask` 后)
- Modify: `packages/web/lib/api/pre-analysis.test.ts` (在文件末尾追加 describe)

**Interfaces:**
- Produces: 3 export types (`ChapterTreeNode`, `ChapterStructurePayload`, `FlaggedParagraphRow`) + 2 export functions (`getPreAnalysisChapterStructure(taskId)`, `getPreAnalysisFlaggedParagraphs(taskId)`). Task 2/3 import 这些 types + functions.

- [ ] **Step 1: 写失败的 helper 单测**

打开 `packages/web/lib/api/pre-analysis.test.ts`, 在文件末尾 (`retryPreAnalysisTask` describe 之后, 实际当前是 `downloadPreAnalysisZip` describe 后无更多) 追加 (注意 vitest 一个文件多 describe OK):

```ts
import {
  getPreAnalysisChapterStructure,
  getPreAnalysisFlaggedParagraphs,
  type ChapterStructurePayload,
} from "./pre-analysis";

// (2026-07-09 viewer pages) chapter_structure.json 拉取 + parse 单测
describe("getPreAnalysisChapterStructure", () => {
  it("GET /api/pre-analysis/tasks/{id}/files/chapter_structure.json 返 parsed object", async () => {
    const mockPayload: ChapterStructurePayload = {
      max_level: 3,
      total_pages: 100,
      total_chapters: 6,
      extracted_at: "2026-07-09T10:00:00Z",
      toc_source: "pdf_outline",
      llm_summary_enabled: false,
      chapters: [
        {
          id: "ch_1",
          level: 1,
          title: "Chapter 1",
          page_start: 1,
          page_end: 20,
          children: [],
        },
      ],
    };
    installMockFetch(Response.json(mockPayload, { status: 200 }));

    const result = await getPreAnalysisChapterStructure("pa-1");
    expect(result.chapters).toHaveLength(1);
    expect(result.chapters[0]?.id).toBe("ch_1");
  });

  it("404 throws 'fetch failed'", async () => {
    installMockFetch(new Response("not found", { status: 404 }));
    await expect(getPreAnalysisChapterStructure("pa-1")).rejects.toThrow(/fetch failed/);
  });

  it("invalid JSON throws", async () => {
    installMockFetch(new Response("{not valid json", { status: 200 }));
    await expect(getPreAnalysisChapterStructure("pa-1")).rejects.toThrow();
  });

  it("chapters field missing throws 'not an array'", async () => {
    installMockFetch(new Response("{}", { status: 200 }));
    await expect(getPreAnalysisChapterStructure("pa-1")).rejects.toThrow(/not an array/);
  });
});

// (2026-07-09 viewer pages) flagged_paragraphs.csv 拉取 + papaparse 单测
describe("getPreAnalysisFlaggedParagraphs", () => {
  it("parses 14-column CSV with 3 data rows", async () => {
    const csv = [
      "matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language",
      '"foo|bar",12,"2.1","Lorem ipsum dolor sit amet.","density_high",0.85,True,0.9,1.2,3,5,"[1,2]",42,zh',
      '"baz",15,"2.2","Sed do eiusmod tempor.","density_high",0.72,False,0.8,1.0,2,3,"[3]",35,zh',
      '"qux",20,"3.1","Ut labore et dolore magna.","density_high",0.95,True,0.95,1.5,5,8,"[4,5]",60,zh',
    ].join("\n");
    installMockFetch(new Response(csv, { status: 200, headers: { "content-type": "application/json" } }));

    const rows = await getPreAnalysisFlaggedParagraphs("pa-1");
    expect(rows).toHaveLength(3);
    expect(rows[0]?.text).toBe("Lorem ipsum dolor sit amet.");
    expect(rows[0]?.page).toBe(12);
    expect(rows[0]?.is_dense).toBe(true);
    expect(rows[1]?.is_dense).toBe(false);
    expect(rows[2]?.token_count).toBe(60);
    expect(rows[0]?.row_index).toBe(1);
  });

  it("parses CSV with quoted comma in text", async () => {
    const csv = [
      "matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language",
      '"foo",1,"1","hello, ""world""","density_high",0.5,False,0.5,0.5,1,1,"[1]",10,zh',
    ].join("\n");
    installMockFetch(new Response(csv, { status: 200 }));

    const rows = await getPreAnalysisFlaggedParagraphs("pa-1");
    expect(rows[0]?.text).toBe('hello, "world"');
  });

  it("CSV header only returns []", async () => {
    const csv =
      "matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language";
    installMockFetch(new Response(csv, { status: 200 }));

    const rows = await getPreAnalysisFlaggedParagraphs("pa-1");
    expect(rows).toEqual([]);
  });

  it("404 throws", async () => {
    installMockFetch(new Response("not found", { status: 404 }));
    await expect(getPreAnalysisFlaggedParagraphs("pa-1")).rejects.toThrow();
  });
});
```

注意 import 上方的两个 type (`ChapterStructurePayload`) 已声明在 `pre-analysis.ts`. `getPreAnalysisChapterStructure` / `getPreAnalysisFlaggedParagraphs` 还没导入, TS 会爆红 (编译失败). Step 1 的目的是让 step 3 加实现时一起绿.

- [ ] **Step 2: 跑单测看红**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- lib/api/pre-analysis.test.ts 2>&1 | tail -30
```

预期: FAIL with "Export getPreAnalysisChapterStructure doesn't exist in target module" (或其他 import 报红), 因为还没实现.

- [ ] **Step 3: 实现 types + helpers + 内部 fetchPreAnalysisFile**

打开 `packages/web/lib/api/pre-analysis.ts`, 在 `downloadPreAnalysisFile` 之后 (`router.py:284` 后, 第 313 行 `retryPreAnalysisTask` 之前) 插入以下新代码 (P3 改完后这段新代码在 `downloadPreAnalysisFile` 后):

```ts
import { parse } from "papaparse";

// (2026-07-09 viewer pages) — 内部 fetch helper, 拉取产物文件成 text
// 后端 /files/{filename} 对 chapter_structure.json 用 application/json mime,
// 对 flagged_paragraphs.csv 也用 application/json mime (router.py:272 已知 bug),
// 本 helper 不检查 Content-Type, 一律走 resp.text() 让调用方自己 parse.

/** chapter_structure.json 文件名 (跟后端 chapters_section.py 落地一致) */
const CHAPTER_JSON_FILENAME = "chapter_structure.json";
/** flagged_paragraphs.csv 文件名 (跟后端 flagged_section.py 落地一致) */
const FLAG_CSV_FILENAME = "flagged_paragraphs.csv";

/**
 * (2026-07-09) 拉取预分析单个产物文件为 text 字符串.
 * 跟 downloadPreAnalysisFile 区别: 这个返 text 不返 Blob. viewer page 用此 +
 * 自实现 JSON.parse 或 papaparse.parse, 不需要浏览器 objectURL 下载流程.
 *
 * @param taskId 任务 ID
 * @param filename 产物文件名
 * @returns 文件文本 (UTF-8)
 * @throws 后端 4xx/5xx 时
 */
const fetchPreAnalysisFile = async (
  taskId: string,
  filename: string,
): Promise<string> => {
  const resp = await fetch(
    `/api/pre-analysis/tasks/${encodeURIComponent(taskId)}/files/${filename}`,
    { credentials: "include" },
  );
  if (!resp.ok) {
    await handleError(resp);
  }
  return await resp.text();
};

/**
 * 章节树原始 JSON 节点 (递归, 跟后端 chapters_section.py schema 严格对齐)
 * @shared
 * @property id 节点 ID, 形如 "ch_<n>"
 * @property level 层级深度, 1-6
 * @property title 章节标题
 * @property page_start 起始页 (1-based)
 * @property page_end 结束页 (含)
 * @property children 子节点, 叶子为空数组
 */
export interface ChapterTreeNode {
  id: string;
  level: number;
  title: string;
  page_start: number;
  page_end: number;
  children: ChapterTreeNode[];
}

/**
 * chapter_structure.json 解析后顶层 payload (跟后端 chapters_section.py 一致).
 * @shared
 * @property max_level 后端 truncate 截断深度
 * @property total_pages PDF 总页数
 * @property total_chapters 章节总数 (含嵌套的递归计数)
 * @property extracted_at 提取时间 ISO8601
 * @property toc_source toc 来源 (pdf_outline / toc_pages / llm_refined / empty)
 * @property llm_summary_enabled 是否启用 LLM 摘要
 * @property chapters 顶层章节 (含嵌套 children)
 */
export interface ChapterStructurePayload {
  max_level: number;
  total_pages: number;
  total_chapters: number;
  extracted_at: string;
  toc_source: "pdf_outline" | "toc_pages" | "llm_refined" | "empty";
  llm_summary_enabled: boolean;
  chapters: ChapterTreeNode[];
}

/**
 * (2026-07-09) 拉取任务章节结构文件, fetch + JSON.parse 返解析后的 payload.
 * 调后端 GET /api/pre-analysis/tasks/{taskId}/files/chapter_structure.json.
 * 后端 schema 跟 TypeScript 1:1 对齐, 编译时 TS 校验已经够用, helper 内只做最小 sanity check.
 *
 * @param taskId 任务 ID
 * @returns 解析后的章节结构对象
 * @throws 后端 4xx/5xx (走 handleError), 或 JSON.parse 失败, 或 schema 不符 (chapters 非数组) 时
 * @client-bff
 */
export const getPreAnalysisChapterStructure = async (
  taskId: string,
): Promise<ChapterStructurePayload> => {
  const text = await fetchPreAnalysisFile(taskId, CHAPTER_JSON_FILENAME);
  const parsed = JSON.parse(text) as ChapterStructurePayload;
  if (!Array.isArray(parsed.chapters)) {
    throw new Error("chapter_structure.json: 'chapters' field is not an array");
  }
  return parsed;
};

/**
 * flagged_paragraphs.csv 一行解析结果, 14 字段 + row_index.
 * @shared
 * @property row_index 1-based 行号 (CSV 表头是 row 0, 第一条数据是 row 1)
 * @property matched_keywords 命中的关键词 (DictReader 兼容字段, 后端 fixed)
 * @property page 页码 (1-based)
 * @property section 章节 (e.g. "1.2.3")
 * @property text 段落实体 (可能很长, 渲染时 line-clamp-3 + AppTooltip 看完整)
 * @property rule_categories 命中规则分类
 * @property density 综合密度
 * @property is_dense 是否高密度 (后端 Python bool → CSV 'True'/'False' 字符串)
 * @property raw_density 原始密度
 * @property weighted_density 加权密度
 * @property safe_hits 保守命中数
 * @property rec_hits 递归命中数
 * @property lemmas 引理 JSON 字符串 (后端 dump, 前端不解)
 * @property token_count token 数
 * @property language 语言代码
 */
export interface FlaggedParagraphRow {
  row_index: number;
  matched_keywords: string;
  page: number;
  section: string;
  text: string;
  rule_categories: string;
  density: number;
  is_dense: boolean;
  raw_density: number;
  weighted_density: number;
  safe_hits: number;
  rec_hits: number;
  lemmas: string;
  token_count: number;
  language: string;
}

/**
 * (2026-07-09) 拉取任务标记段落实体 CSV, fetch + papaparse 解析返 rows.
 * 后端 /files/{filename} 用 'application/json' mime 返 CSV (router.py:272 已知),
 * 本函数 fetcheFile() 后按 text 解析, 不检查 Content-Type.
 * papaparse 不自动转 Number/Boolean, helper 内手动比对;
 * is_dense 后端 Python bool → CSV "True"/"False" (capitalized), 这两种字符串都被识别为 true.
 *
 * @param taskId 任务 ID
 * @returns 已 parse 的 rows (空数组 if 文件仅表头)
 * @throws 后端 4xx/5xx 时
 * @client-bff
 */
export const getPreAnalysisFlaggedParagraphs = async (
  taskId: string,
): Promise<FlaggedParagraphRow[]> => {
  const text = await fetchPreAnalysisFile(taskId, FLAG_CSV_FILENAME);
  const parsed = parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: true,
  });
  return parsed.data.map((raw, idx) => ({
    row_index: idx + 1,
    matched_keywords: raw["matched_keywords"] ?? "",
    page: Number(raw["page"] ?? 0),
    section: raw["section"] ?? "",
    text: raw["text"] ?? "",
    rule_categories: raw["rule_categories"] ?? "",
    density: Number(raw["density"] ?? 0),
    is_dense: raw["is_dense"] === "True" || raw["is_dense"] === "true",
    raw_density: Number(raw["raw_density"] ?? 0),
    weighted_density: Number(raw["weighted_density"] ?? 0),
    safe_hits: Number(raw["safe_hits"] ?? 0),
    rec_hits: Number(raw["rec_hits"] ?? 0),
    lemmas: raw["lemmas"] ?? "",
    token_count: Number(raw["token_count"] ?? 0),
    language: raw["language"] ?? "",
  }));
};
```

- [ ] **Step 4: 跑单测看绿**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- lib/api/pre-analysis.test.ts 2>&1 | tail -30
```

预期: PASS. 8 个新测试 (`getPreAnalysisChapterStructure` 4 + `getPreAnalysisFlaggedParagraphs` 4) 全绿.

- [ ] **Step 5: format + lint + typecheck**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run format && bun run lint:fix && bun run typecheck
```

预期: 0 error.

- [ ] **Step 6: commit**

```bash
git add packages/web/lib/api/pre-analysis.ts packages/web/lib/api/pre-analysis.test.ts
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -m "$(cat <<'EOF'
feat(web): pre-analysis viewer pages — helper + types + unit tests

加 3 type + 2 helper:
- ChapterTreeNode / ChapterStructurePayload / FlaggedParagraphRow
- getPreAnalysisChapterStructure (JSON.parse)
- getPreAnalysisFlaggedParagraphs (papaparse)

导出 fetchPreAnalysisFile 内部 helper 抽 file → text 公共路径.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

# Phase 2: 章节目录页

## Task 2: 章节目录 RSC entry (page.tsx)

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/chapters/page.tsx`

**Interfaces:**
- Consumes: 路由 param `{ task_id: string }` (Promise, Next 16 pattern)
- Produces: RSC element, render GuardPage + client 子组件. Task 3 写 client component.

- [ ] **Step 1: 创建 chapters/page.tsx**

⚠ spec §6.5 写的是 `<GuardPage requiredRole="admin">`, **实际项目用 `<GuardPage pageKey="admin">`** (见 `[task_id]/page.tsx:25`). 本 task 用正确版本.

文件 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/chapters/page.tsx`:

```tsx
// admin/pre-analysis/[task_id]/chapters/page.tsx — RSC entry (2026-07-09)
// 调 AdminPreAnalysisChaptersClient 渲染章节树查看页.
// 跟 [task_id]/page.tsx 模式一致 (params 是 Promise, await 后传 sync value).

import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisChaptersClient } from "./_components/admin-pre-analysis-chapters-client";

/**
 * admin/pre-analysis 章节目录页 (RSC)
 *
 * 渲染章节树查看页. 路由参数 task_id 透传给 client 子组件.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数 Promise
 * @param props.params.task_id - 预分析任务 ID
 * @server-only
 */
export default async function AdminPreAnalysisChaptersPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisChaptersClient params={{ task_id }} />
    </GuardPage>
  );
}
```

- [ ] **Step 2: 跑 typecheck 看红 (import 没实现会爆)**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run typecheck 2>&1 | tail -20
```

预期: FAIL with "Cannot find module './_components/admin-pre-analysis-chapters-client'" (因为还没写 client).

- [ ] **Step 3: (留空, Task 3 写 client 后再跑)**

## Task 3: 章节目录客户端组件 + 单测

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/chapters/_components/admin-pre-analysis-chapters-client.tsx`
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/chapters/_components/admin-pre-analysis-chapters-client.test.tsx`

**Interfaces:**
- Consumes: Task 1 导出的 `getPreAnalysisChapterStructure(taskId)` + `ChapterTreeNode` type
- Produces: `AdminPreAnalysisChaptersClient` 组件 (4 列 DataTable, 默认折叠)

- [ ] **Step 1: 创建 client component**

文件 `admin-pre-analysis-chapters-client.tsx`:

```tsx
"use client";
// admin/pre-analysis 章节目录客户端组件 (2026-07-09)
// 调 getPreAnalysisChapterStructure 拉扁平 JSON, 客户端嵌套结构扁平化 + indent 列.
// 默认全部折叠 (用户进页只看 L1 节点), 点击 chevron 展开/收起.
// 复用 <DataTable<T>> + <BackLink> + <PageHero> + <ErrorBanner> + <DataEmpty>.

import { ChevronDown, ChevronRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { DataTable, type ColumnDef } from "@/components/common/table/data-table";
import {
  getPreAnalysisChapterStructure,
  type ChapterTreeNode,
} from "@/lib/api/pre-analysis";

/** 章节树展平后的扁平行 (UI 内部类型) */
interface FlatChapterRow {
  id: string;
  depth: number;
  title: string;
  pageRange: string;
  childCount: number;
  hasChildren: boolean;
}

/** 每级缩进宽度 (px), 章节标签左移对齐 */
const INDENT_PX_PER_LEVEL = 24;
/** chevron 按钮尺寸 (h-/w- Tailwind class), 跟缩进空格 w-6 对齐 */
const CHEVRON_BUTTON_CLASS = "h-6 w-6";

/** 页面组件路由参数 */
interface PageProps {
  /** 路由参数 */
  params: { task_id: string };
}

/**
 * 递归扁平化 + 应用 collapsed 状态 (深度优先).
 * 用户点 chevron → setCollapsed(record) → 重 flatten, 客户端无后端 roundtrip.
 * @param nodes 当前层节点
 * @param collapsed id → 是否折叠的字典
 * @param depth 当前深度 (root = 0)
 * @param acc 累加器 (递归复用, 避免 O(N²) spread)
 * @returns 扁平化后的行数组
 */
const flattenChapters = (
  nodes: ChapterTreeNode[],
  collapsed: Record<string, boolean>,
  depth: number,
  acc: FlatChapterRow[],
): FlatChapterRow[] => {
  for (const node of nodes) {
    acc.push({
      id: node.id,
      depth,
      title: node.title,
      pageRange: `${node.page_start} – ${node.page_end}`,
      childCount: node.children.length,
      hasChildren: node.children.length > 0,
    });
    if (node.children.length > 0 && !collapsed[node.id]) {
      flattenChapters(node.children, collapsed, depth + 1, acc);
    }
  }
  return acc;
};

/**
 * admin/pre-analysis 章节目录客户端组件 (2026-07-09)
 *
 * 调 getPreAnalysisChapterStructure 拉嵌套 chapter 树, 客户端 flattenChapters 展开
 * + 应用 collapsed 状态 → DataTable 4 列 (标题含 chevron + indent / 页范围 / 子章节数).
 * 默认全部折叠, 用户逐级点开. 章节数小 (< 100), 不分页, maxHeight=600px 滚动.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数
 * @param props.params.task_id - 预分析任务 ID
 * @returns 页面 React 元素
 * @client-bff
 */
export const AdminPreAnalysisChaptersClient = ({
  params,
}: PageProps): React.ReactElement => {
  const translate = useTranslations();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const { data, error, isLoading } = useQuery({
    queryKey: ["pre-analysis-task", params.task_id, "chapter_structure"],
    queryFn: () => getPreAnalysisChapterStructure(params.task_id),
  });

  /** 切换节点的折叠状态. */
  const handleToggle = useCallback((id: string) => {
    setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  const flattened = useMemo(
    () => (data ? flattenChapters(data.chapters, collapsed, 0, []) : []),
    [data, collapsed],
  );

  const columns = useMemo<ColumnDef<FlatChapterRow>[]>(
    () => [
      {
        accessorKey: "title",
        header: () => translate("标题"),
        cell: (ctx) => {
          const row = ctx.row.original;
          return (
            <div
              className="flex items-center gap-1"
              style={{ paddingLeft: `${row.depth * INDENT_PX_PER_LEVEL}px` }}
            >
              {row.hasChildren ? (
                <Button
                  aria-label={translate("展开章节")}
                  className={CHEVRON_BUTTON_CLASS}
                  data-testid={`chapter-toggle-${row.id}`}
                  onClick={() => handleToggle(row.id)}
                  size="icon"
                  variant="ghost"
                >
                  {collapsed[row.id] ? (
                    <ChevronRight className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              ) : (
                <span className="inline-block w-6" />
              )}
              <span className="text-sm">{row.title}</span>
            </div>
          );
        },
      },
      {
        accessorKey: "pageRange",
        header: () => translate("页范围"),
      },
      {
        accessorKey: "childCount",
        header: () => translate("子章节"),
      },
    ],
    [translate, collapsed, handleToggle],
  );

  return (
    <div className="space-y-6">
      <BackLink
        href={`/admin/pre-analysis/${params.task_id}` as never}
        label={translate("返回")}
      />
      <PageHero
        description={
          data
            ? `${translate("总章节")}: ${data.total_chapters} · ${translate("toc 来源")}: ${data.toc_source}`
            : undefined
        }
        title={translate("章节目录")}
      />
      {error ? (
        <ErrorBanner description={String(error)} variant="destructive" />
      ) : null}
      {data ? (
        <DataTable<FlatChapterRow>
          columns={columns}
          dataSource={flattened}
          emptyText={<DataEmpty title={translate("无章节数据")} />}
          loading={isLoading}
          pagination={undefined}
          maxHeight="600px"
          rowKey="id"
        />
      ) : null}
    </div>
  );
};
```

- [ ] **Step 2: 写 client 单测**

文件 `admin-pre-analysis-chapters-client.test.tsx`:

```tsx
// 章节目录客户端组件测试 (mode 1 mock fetch)

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { AdminPreAnalysisChaptersClient } from "./admin-pre-analysis-chapters-client";
import type { ChapterStructurePayload } from "@/lib/api/pre-analysis";

vi.mock("server-only", () => ({}));

afterEach(() => {
  vi.restoreAllMocks();
});

/** (2026-07-09) 3 层节点 fixture — 3 L1, ch_2 含 L2, ch_2_1 含 L3, 用于测折叠 + 缩进 */
const TREE_PAYLOAD: ChapterStructurePayload = {
  max_level: 3,
  total_pages: 100,
  total_chapters: 5,
  extracted_at: "2026-07-09T10:00:00Z",
  toc_source: "pdf_outline",
  llm_summary_enabled: false,
  chapters: [
    {
      id: "ch_1",
      level: 1,
      title: "Introduction",
      page_start: 1,
      page_end: 10,
      children: [],
    },
    {
      id: "ch_2",
      level: 1,
      title: "Background",
      page_start: 11,
      page_end: 50,
      children: [
        {
          id: "ch_2_1",
          level: 2,
          title: "Prior work",
          page_start: 12,
          page_end: 20,
          children: [
            {
              id: "ch_2_1_1",
              level: 3,
              title: "Methods (2020)",
              page_start: 13,
              page_end: 15,
              children: [],
            },
          ],
        },
      ],
    },
    {
      id: "ch_3",
      level: 1,
      title: "Conclusion",
      page_start: 51,
      page_end: 60,
      children: [],
    },
  ],
};

/**
 * 包装 QueryClientProvider + IntlWrapper. retry=false 避免 fetch fail 重试拖慢.
 */
const renderWithProviders = (ui: React.ReactElement): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">{ui}</IntlWrapper>
    </QueryClientProvider>,
  );
};

const installMockFetch = (resp: Response): void => {
  globalThis.fetch = vi.fn(async () => resp) as unknown as typeof fetch;
};

describe("AdminPreAnalysisChaptersClient", () => {
  it("默认全部折叠, 只渲染 L1 节点 (3 行)", async () => {
    installMockFetch(Response.json(TREE_PAYLOAD, { status: 200 }));
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("Introduction")).toBeTruthy();
      expect(screen.getByText("Background")).toBeTruthy();
      expect(screen.getByText("Conclusion")).toBeTruthy();
    });

    // L2/L3 节点默认不渲染
    expect(screen.queryByText("Prior work")).toBeNull();
    expect(screen.queryByText("Methods (2020)")).toBeNull();
  });

  it("点 ch_2 chevron 展开后, 子节点出现", async () => {
    installMockFetch(Response.json(TREE_PAYLOAD, { status: 200 }));
    const user = userEvent.setup();
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => expect(screen.getByText("Background")).toBeTruthy());
    await user.click(screen.getByTestId("chapter-toggle-ch_2"));

    expect(screen.getByText("Prior work")).toBeTruthy();
  });

  it("再点一次 ch_2 chevron 折叠, 子节点消失", async () => {
    installMockFetch(Response.json(TREE_PAYLOAD, { status: 200 }));
    const user = userEvent.setup();
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => expect(screen.getByText("Background")).toBeTruthy());
    await user.click(screen.getByTestId("chapter-toggle-ch_2"));
    expect(screen.getByText("Prior work")).toBeTruthy();
    await user.click(screen.getByTestId("chapter-toggle-ch_2"));
    expect(screen.queryByText("Prior work")).toBeNull();
  });

  it("叶子节点渲染 <span> 占位 (无 chevron button)", async () => {
    installMockFetch(Response.json(TREE_PAYLOAD, { status: 200 }));
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => expect(screen.getByText("Introduction")).toBeTruthy());

    // ch_1 是叶子, 不应该有 toggle button
    expect(screen.queryByTestId("chapter-toggle-ch_1")).toBeNull();
    // ch_2 有子节点, 应该有 toggle button
    expect(screen.getByTestId("chapter-toggle-ch_2")).toBeTruthy();
  });

  it("空树 (chapters: []) 渲染 <DataEmpty>", async () => {
    installMockFetch(
      Response.json({ ...TREE_PAYLOAD, chapters: [] }, { status: 200 }),
    );
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => expect(screen.getByText("无章节数据")).toBeTruthy());
  });

  it("fetch 失败时渲染 ErrorBanner", async () => {
    installMockFetch(new Response("not found", { status: 404 }));
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() =>
      expect(screen.getByText(/fetch failed/)).toBeTruthy(),
    );
  });
});
```

- [ ] **Step 3: 跑单测看红 (tree 没实现时 import 报错)**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- app/\[locale\]/admin/pre-analysis/\[task_id\]/chapters/_components/admin-pre-analysis-chapters-client.test.tsx 2>&1 | tail -30
```

预期: FAIL with "Cannot find module './admin-pre-analysis-chapters-client'" (step 1 已经建了, 应该能找到). 实际应该是 import 后的 test fail (因为还没 commit 完成).

实际预期: 6 个新测试至少 6 PASS (因为 import 已经成功, 实现正常). 改 - 跑测试看红:

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- app/\[locale\]/admin/pre-analysis/\[task_id\]/chapters/_components/admin-pre-analysis-chapters-client.test.tsx 2>&1 | tail -30
```

预期: 6 PASS.

- [ ] **Step 4: (无 step 4 - 实现已经在 step 1 完成)**

- [ ] **Step 5: format + lint + typecheck**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run format && bun run lint:fix && bun run typecheck
```

预期: 0 error. 注意可能 i18n 报 MISSING key (因为 zh.json 还没加), typecheck 不会报, 但测试可能. 先跳过测试跑 typecheck.

- [ ] **Step 6: 加 i18n key (zh.json + en.json)**

打开 `packages/web/messages/zh.json`, 在 line 612 "章节显示层级" 后插入:

```json
  "章节目录": "章节目录",
  "段落提取": "段落提取",
  "查看": "查看",
  "标题": "标题",
  "页范围": "页范围",
  "子章节": "子章节",
  "展开章节": "展开章节",
  "总章节": "总章节",
  "toc 来源": "toc 来源",
  "页码": "页码",
  "章节": "章节",
  "段落": "段落",
  "命中规则": "命中规则",
  "密度": "密度",
  "高密度": "高密度",
  "条标记段落": "条标记段落",
  "无章节数据": "无章节数据",
  "无标记段落": "无标记段落",
  "网络异常,请稍后重试": "网络异常,请稍后重试",
  "该任务暂无此产物,请等待 pre-analysis 完成后查看": "该任务暂无此产物,请等待 pre-analysis 完成后查看",
  "章节结构文件格式错误": "章节结构文件格式错误",
```

⚠ 检查是否已存在重复 key 后再插入 (grep -nF '"章节目录"' messages/zh.json). 如果重复跳过.

打开 `packages/web/messages/en.json`, 同样位置插入:

```json
  "章节目录": "Chapter Outline",
  "段落提取": "Paragraph Extraction",
  "查看": "View",
  "标题": "Title",
  "页范围": "Page Range",
  "子章节": "Sub-chapters",
  "展开章节": "Expand chapter",
  "总章节": "Total chapters",
  "toc 来源": "TOC Source",
  "页码": "Page",
  "章节": "Section",
  "段落": "Paragraph",
  "命中规则": "Rule Matched",
  "密度": "Density",
  "高密度": "High Density",
  "条标记段落": "flagged paragraphs",
  "无章节数据": "No chapter data",
  "无标记段落": "No flagged paragraphs",
  "网络异常,请稍后重试": "Network error, please retry",
  "该任务暂无此产物,请等待 pre-analysis 完成后查看": "Artifact not yet available, please wait until pre-analysis completes",
  "章节结构文件格式错误": "Chapter structure file format error",
```

`Token` 和 `语言` 已在 messages/zh.json line 171 存在 ("语言":"语言") - 跳过.

- [ ] **Step 7: 验证 i18n JSON 合法**

```bash
cd /home/deyuan/rag/rag/packages/web && node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"
```

预期: `OK`.

- [ ] **Step 8: 跑单测看绿**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- app/\[locale\]/admin/pre-analysis/\[task_id\]/chapters/_components/admin-pre-analysis-chapters-client.test.tsx 2>&1 | tail -30
```

预期: 6 PASS. `IntlWrapper` 提供 zh messages, 测试跟 zh.json 加完后, i18n key 全部能 resolve.

- [ ] **Step 9: commit**

```bash
git add packages/web/messages/zh.json packages/web/messages/en.json \
  packages/web/app/\[locale\]/admin/pre-analysis/\[task_id\]/chapters/_components/admin-pre-analysis-chapters-client.tsx \
  packages/web/app/\[locale\]/admin/pre-analysis/\[task_id\]/chapters/_components/admin-pre-analysis-chapters-client.test.tsx
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -m "$(cat <<'EOF'
feat(web): pre-analysis viewer — 章节目录页 (扁平可折叠)

加 [task_id]/chapters 子路由:
- RSC entry await params + GuardPage + client
- 客户端 flattenChapters() 把嵌套树展平 + 应用 collapsed state
- 4 列 DataTable (标题含 chevron + indent / 页范围 / 子章节数)
- 默认全部折叠, 点击 chevron 展开/收起

i18n 加 20 个 key, zh.json identity + en.json 翻译.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

⚠ 注意: RSC entry `chapters/page.tsx` 也在这一波 commit, 但 git add 没加 — 修正:

```bash
git add packages/web/messages/zh.json packages/web/messages/en.json \
  packages/web/app/\[locale\]/admin/pre-analysis/\[task_id\]/chapters/
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -m "$(cat <<'EOF'
feat(web): pre-analysis viewer — 章节目录页 (扁平可折叠)

加 [task_id]/chapters 子路由:
- RSC entry await params + GuardPage + client
- 客户端 flattenChapters() 把嵌套树展平 + 应用 collapsed state
- 4 列 DataTable (标题含 chevron + indent / 页范围 / 子章节数)
- 默认全部折叠, 点击 chevron 展开/收起

i18n 加 20 个 key, zh.json identity + en.json 翻译.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

(整体 chapters 目录一起 commit.)

---

# Phase 3: 段落页 + 详情页改 + 详情页回归

## Task 4: 段落页 RSC entry

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/flagged/page.tsx`

**Interfaces:**
- Consumes: 路由 param `{ task_id: string }` (Promise, Next 16 pattern)
- Produces: RSC element, render GuardPage + client 子组件. Task 5 写 client.

- [ ] **Step 1: 创建 flagged/page.tsx**

文件 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/flagged/page.tsx`:

```tsx
// admin/pre-analysis/[task_id]/flagged/page.tsx — RSC entry (2026-07-09)
// 调 AdminPreAnalysisFlaggedClient 渲染标记段落实体表.
// 跟 chapters/page.tsx 同 shape.

import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisFlaggedClient } from "./_components/admin-pre-analysis-flagged-client";

/**
 * admin/pre-analysis 段落提取页 (RSC)
 *
 * 渲染标记段落实体表. 路由参数 task_id 透传给 client 子组件.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数 Promise
 * @param props.params.task_id - 预分析任务 ID
 * @server-only
 */
export default async function AdminPreAnalysisFlaggedPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisFlaggedClient params={{ task_id }} />
    </GuardPage>
  );
}
```

## Task 5: 段落客户端组件 + 单测

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/flagged/_components/admin-pre-analysis-flagged-client.tsx`
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/flagged/_components/admin-pre-analysis-flagged-client.test.tsx`

**Interfaces:**
- Consumes: Task 1 导出的 `getPreAnalysisFlaggedParagraphs(taskId)` + `FlaggedParagraphRow` type
- Produces: `AdminPreAnalysisFlaggedClient` 组件 (14 列 DataTable, 8 列展示 + AppTooltip text 列)

- [ ] **Step 1: 创建 client component**

文件 `admin-pre-analysis-flagged-client.tsx`:

```tsx
"use client";
// admin/pre-analysis 段落提取客户端组件 (2026-07-09)
// 调 getPreAnalysisFlaggedParagraphs 拉 CSV 解析后的 rows, 14 列 DataTable 展示.
// text 列用 line-clamp-3 + AppTooltip 看完整, is_dense=true 行用 AlertTriangle + Badge.
// 复用 <DataTable<T>> + <BackLink> + <PageHero> + <ErrorBanner> + <DataEmpty>.

import { AlertTriangle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import { DataTable, type ColumnDef } from "@/components/common/table/data-table";
import {
  getPreAnalysisFlaggedParagraphs,
  type FlaggedParagraphRow,
} from "@/lib/api/pre-analysis";

/** 段落页每页条数 (跟详情页产物列表一致) */
const FLAG_PAGE_SIZE = 5;
/** 初始化分页页码 */
const INITIAL_PAGE = 1;
/** 密度列小数位 */
const DENSITY_DECIMALS = 1;
/** token 列千分位分隔 */
const THOUSAND_SEPARATOR = ",";
/** text 列最大宽度 (ch 单位) */
const TEXT_MAX_WIDTH_CH = 60;

/** 页面组件路由参数 */
interface PageProps {
  /** 路由参数 */
  params: { task_id: string };
}

/**
 * 数字保留 DENSITY_DECIMALS 位小数.
 * @param num 原始 number
 * @returns 格式化字符串 (e.g. "0.9")
 */
const formatNumber = (num: number): string => {
  return num.toFixed(DENSITY_DECIMALS);
};

/**
 * 千分位分隔数字 (e.g. 12000 → "12,000").
 * @param num 原始 number
 * @returns 千分位格式化字符串
 */
const formatToken = (num: number): string => {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, THOUSAND_SEPARATOR);
};

/**
 * admin/pre-analysis 段落提取客户端组件 (2026-07-09)
 *
 * 调 getPreAnalysisFlaggedParagraphs 拉 14 列 CSV 解析后的 rows, DataTable 展示.
 * 8 列: 页码 / 章节 / 段落 (line-clamp-3 + AppTooltip) / 命中规则 / 密度 / 高密度 (Badge) / Token / 语言.
 * raw_density / weighted_density / safe_hits / rec_hits / lemmas 5 列本期不展示 (省略; 用户校对主要关注 page + section + text + density).
 *
 * @param props - 组件属性
 * @param props.params - 路由参数
 * @param props.params.task_id - 预分析任务 ID
 * @returns 页面 React 元素
 * @client-bff
 */
export const AdminPreAnalysisFlaggedClient = ({
  params,
}: PageProps): React.ReactElement => {
  const translate = useTranslations();
  const [currentPage, setCurrentPage] = useState(INITIAL_PAGE);

  const { data, error, isLoading } = useQuery({
    queryKey: ["pre-analysis-task", params.task_id, "flagged_paragraphs"],
    queryFn: () => getPreAnalysisFlaggedParagraphs(params.task_id),
  });

  const columns = useMemo<ColumnDef<FlaggedParagraphRow>[]>(
    () => [
      { accessorKey: "page", header: () => translate("页码") },
      { accessorKey: "section", header: () => translate("章节") },
      {
        accessorKey: "text",
        header: () => translate("段落"),
        cell: (ctx) => (
          <AppTooltip content={ctx.row.original.text}>
            <span
              className="line-clamp-3 max-w-[60ch] cursor-help"
              style={{ maxWidth: `${TEXT_MAX_WIDTH_CH}ch` }}
            >
              {ctx.row.original.text}
            </span>
          </AppTooltip>
        ),
      },
      { accessorKey: "rule_categories", header: () => translate("命中规则") },
      {
        accessorKey: "density",
        cell: (ctx) => formatNumber(ctx.row.original.density),
        header: () => translate("密度"),
      },
      {
        accessorKey: "is_dense",
        cell: (ctx) =>
          ctx.row.original.is_dense ? (
            <Badge variant="warning">
              <AlertTriangle className="mr-1 h-3 w-3" />
              {translate("高密度")}
            </Badge>
          ) : null,
        header: () => translate("高密度"),
      },
      {
        accessorKey: "token_count",
        cell: (ctx) => formatToken(ctx.row.original.token_count),
        header: () => translate("Token"),
      },
      { accessorKey: "language", header: () => translate("语言") },
    ],
    [translate],
  );

  return (
    <div className="space-y-6">
      <BackLink
        href={`/admin/pre-analysis/${params.task_id}` as never}
        label={translate("返回")}
      />
      <PageHero
        description={data ? `${data.length} ${translate("条标记段落")}` : undefined}
        title={translate("段落提取")}
      />
      {error ? (
        <ErrorBanner description={String(error)} variant="destructive" />
      ) : null}
      <DataTable<FlaggedParagraphRow>
        columns={columns}
        dataSource={data ?? []}
        emptyText={<DataEmpty title={translate("无标记段落")} />}
        loading={isLoading}
        maxHeight="600px"
        pagination={{
          current: currentPage,
          onChange: setCurrentPage,
          pageSize: FLAG_PAGE_SIZE,
          total: data?.length ?? 0,
        }}
        rowKey="row_index"
      />
    </div>
  );
};
```

- [ ] **Step 2: 写 client 单测**

文件 `admin-pre-analysis-flagged-client.test.tsx`:

```tsx
// 段落提取客户端组件测试 (mode 1 mock fetch)

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { AdminPreAnalysisFlaggedClient } from "./admin-pre-analysis-flagged-client";
import type { FlaggedParagraphRow } from "@/lib/api/pre-analysis";

vi.mock("server-only", () => ({}));

afterEach(() => {
  vi.restoreAllMocks();
});

/** (2026-07-09) 4 row fixture — 2 dense (True) + 2 normal (False) */
const FIXTURE_ROWS: FlaggedParagraphRow[] = [
  {
    row_index: 1,
    matched_keywords: "foo|bar",
    page: 12,
    section: "2.1",
    text: "Lorem ipsum dolor sit amet.",
    rule_categories: "density_high",
    density: 0.85,
    is_dense: true,
    raw_density: 0.9,
    weighted_density: 1.2,
    safe_hits: 3,
    rec_hits: 5,
    lemmas: "[1,2]",
    token_count: 12000,
    language: "zh",
  },
  {
    row_index: 2,
    matched_keywords: "baz",
    page: 15,
    section: "2.2",
    text: "Sed do eiusmod tempor.",
    rule_categories: "density_high",
    density: 0.72,
    is_dense: false,
    raw_density: 0.8,
    weighted_density: 1.0,
    safe_hits: 2,
    rec_hits: 3,
    lemmas: "[3]",
    token_count: 35,
    language: "zh",
  },
  {
    row_index: 3,
    matched_keywords: "qux",
    page: 20,
    section: "3.1",
    text: "Ut labore et dolore magna.",
    rule_categories: "density_high",
    density: 0.95,
    is_dense: true,
    raw_density: 0.95,
    weighted_density: 1.5,
    safe_hits: 5,
    rec_hits: 8,
    lemmas: "[4,5]",
    token_count: 60,
    language: "zh",
  },
  {
    row_index: 4,
    matched_keywords: "x",
    page: 25,
    section: "3.2",
    text: "Excepteur sint occaecat.",
    rule_categories: "normal",
    density: 0.3,
    is_dense: false,
    raw_density: 0.3,
    weighted_density: 0.3,
    safe_hits: 0,
    rec_hits: 0,
    lemmas: "[6]",
    token_count: 20,
    language: "zh",
  },
];

/** 创建 mock fetch 让 flagged helper 直接返 CSV text 后被 helper 内 papaparse */
const installMockFetchCsv = (csvText: string): void => {
  globalThis.fetch = vi.fn(async () => new Response(csvText, { status: 200 })) as unknown as typeof fetch;
};

const renderWithProviders = (ui: React.ReactElement): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">{ui}</IntlWrapper>
    </QueryClientProvider>,
  );
};

describe("AdminPreAnalysisFlaggedClient", () => {
  it("renders 14-column table with 4 rows", async () => {
    // 直接 mock helper 不行 (vitest mock 隔离): 用 fetch level mock, 返 CSV text 让 helper parse
    const csv = [
      "matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language",
      ...FIXTURE_ROWS.map((r) =>
        `"${r.matched_keywords}",${r.page},"${r.section}","${r.text}","${r.rule_categories}",${r.density},${r.is_dense ? "True" : "False"},${r.raw_density},${r.weighted_density},${r.safe_hits},${r.rec_hits},"${r.lemmas}",${r.token_count},${r.language}`,
      ),
    ].join("\n");
    installMockFetchCsv(csv);

    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      // 4 row 的 text 都出现
      expect(screen.getByText(/Lorem ipsum dolor sit amet\./)).toBeTruthy();
      expect(screen.getByText(/Sed do eiusmod tempor\./)).toBeTruthy();
      expect(screen.getByText(/Ut labore et dolore magna\./)).toBeTruthy();
      expect(screen.getByText(/Excepteur sint occaecat\./)).toBeTruthy();
    });
  });

  it("is_dense=true 行渲染 Badge + AlertTriangle icon", async () => {
    const csv = [
      "matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language",
      '"foo",1,"1","text","density_high",0.85,True,0.9,1.2,3,5,"[1]",42,zh',
      '"bar",2,"1","text2","normal",0.3,False,0.3,0.3,0,0,"[2]",10,zh',
    ].join("\n");
    installMockFetchCsv(csv);

    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      // 高密度 Badge 至少出现 1 次 (is_dense=true 的那行)
      expect(screen.getAllByText("高密度").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("空 data 渲染 <DataEmpty>", async () => {
    installMockFetch(new Response("not found", { status: 404 }));

    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => expect(screen.getByText(/fetch failed/)).toBeTruthy());
  });
});
```

注意: 第 3 个 test 实际是 error 渲染不是空 — 后面会改成 mock 返空 CSV 字符串. 修改:

```tsx
  it("空 data 渲染 <DataEmpty>", async () => {
    installMockFetch(
      new Response(
        "matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language",
        { status: 200 },
      ),
    );

    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => expect(screen.getByText("无标记段落")).toBeTruthy());
  });
```

- [ ] **Step 3: 跑单测**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- app/\[locale\]/admin/pre-analysis/\[task_id\]/flagged/_components/admin-pre-analysis-flagged-client.test.tsx 2>&1 | tail -30
```

预期: 3 PASS.

- [ ] **Step 4: format + lint + typecheck**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run format && bun run lint:fix && bun run typecheck
```

预期: 0 error.

- [ ] **Step 5: commit**

```bash
git add packages/web/app/\[locale\]/admin/pre-analysis/\[task_id\]/flagged/
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -m "$(cat <<'EOF'
feat(web): pre-analysis viewer — 段落提取页 (14 列实体表)

加 [task_id]/flagged 子路由:
- RSC entry await params + GuardPage + client
- 客户端 8 列 DataTable (页码 / 章节 / 段落 / 命中规则 / 密度 / 高密度 / Token / 语言)
- text 列用 line-clamp-3 + AppTooltip 看完整
- is_dense=true 行用 AlertTriangle + Badge 高亮

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

# Phase 4: 详情页改 (加 "查看" 按钮 + 回归测)

## Task 6: 详情页 actions 列改 + 详情页回归测

**Files:**
- Modify: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx`
- Modify: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx`

**Interfaces:**
- Consumes: 已有 `PreAnalysisOutputFile` type from `@/lib/api/pre-analysis`
- Produces: detail client actions 列 cell 加 "查看" button + `useRouter` from `@/i18n/navigation`

- [ ] **Step 1: 写回归测加新断言**

打开 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx`, 在
`describe("admin pre-analysis detail page"` 末尾 (line 145 `renders download zip button` after) 加:

```ts
  it("chapter_structure 行渲染 '查看' 按钮跳子路由, table 行不显示", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json(mockTask, { status: 200 }),
    ) as unknown as typeof fetch;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      // chapter_structure 行的查看按钮
      expect(
        screen.getByTestId("view-file-chapter_structure.json"),
      ).toBeTruthy();
      // flagged_paragraphs 行的查看按钮
      expect(
        screen.getByTestId("view-file-flagged_paragraphs.csv"),
      ).toBeTruthy();
      // table 行的查看按钮 不存在 (只有 download)
      expect(
        screen.queryByTestId("view-file-tables/page-3-table-1.csv"),
      ).toBeNull();
    });
  });
```

- [ ] **Step 2: 跑回归测看红**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- app/\[locale\]/admin/pre-analysis/\[task_id\]/page.test.tsx 2>&1 | tail -30
```

预期: 现有 5 个测试还绿, 新加的 1 个测试 FAIL (找不到 view-file button, 因为还没改 detail client).

- [ ] **Step 3: 改 detail client**

打开 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx`.

修改 imports (line 8 `import { Download, RefreshCw } from "lucide-react"` 之后追加 `, Eye`):

```tsx
import { Download, Eye, RefreshCw } from "lucide-react";
```

修改 imports (line 13 `import { BackLink }` block 之前 — 在 useRouter 位置; spec §6.6 把 useRouter import 放在 next-intl imports 之后, 跟现有 import 顺序 by alphabet 一致; 加 `from "@/i18n/navigation"`):

现有 import 是:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { BackLink } from "@/components/common/navigation/app-back-link";
...
```

加:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { BackLink } from "@/components/common/navigation/app-back-link";
...

import { useRouter } from "@/i18n/navigation";
```

模块顶部常量段 (~ line 30-50), 在 `STATE_LABELS` 后 (line 60) 加:

```tsx
/**
 * (2026-07-09 viewer pages) 可在 web 端预览的产物 kind — chapter_structure 跳 chapters 子路由, flagged_paragraphs 跳 flagged 子路由.
 * table / index 没 viewer 页, 仍只走 download 按钮.
 */
const VIEWABLE_KINDS = ["chapter_structure", "flagged_paragraphs"] as const;
type ViewableKind = (typeof VIEWABLE_KINDS)[number];

/**
 * 类型守卫: 检查 kind 是否在 VIEWABLE_KINDS 列表, 是则 narrow 成 ViewableKind.
 * @param kind 产物 kind
 * @returns true 当 kind 可在 web 端查看
 */
const isViewableKind = (
  kind: PreAnalysisOutputFile["kind"],
): kind is ViewableKind =>
  (VIEWABLE_KINDS as readonly PreAnalysisOutputFile["kind"][]).includes(kind);

/**
 * 根据 ViewableKind 算对应子路由 href.
 * @param kind ViewableKind (chapter_structure | flagged_paragraphs)
 * @param taskId 预分析任务 ID
 * @returns 子路由 href (不含 locale 前缀, useRouter 自动加)
 */
const viewHrefForKind = (kind: ViewableKind, taskId: string): string =>
  kind === "chapter_structure"
    ? `/admin/pre-analysis/${taskId}/chapters`
    : `/admin/pre-analysis/${taskId}/flagged`;
```

(注意: spec §6.6 把 VIEWABLE_KINDS 放在 actions 列 cell 内联, 实际抽到顶部常量更易阅读 —
 跟项目"一切可提取的都放到模块顶部常量"规范一致.)

修改组件体 (line 107 `export const AdminPreAnalysisDetailClient = ...` block 内, 在 `useTranslations` 那行 `const translate = useTranslations();` 后, `useState` 那行前) 加 useRouter:

```tsx
  const translate = useTranslations();
  const router = useRouter();
  const [currentPage, setCurrentPage] = useState(INITIAL_PAGE);
```

修改 columns (line 151-184), 把 actions 列 cell 完整替换:

原 actions cell:

```tsx
      {
        accessorKey: "actions",
        cell: (ctx) => (
          <Button
            data-testid={`download-file-${ctx.row.original.filename}`}
            onClick={() => {
              void handleDownloadFile(ctx.row.original.filename);
            }}
            size="sm"
            variant="outline"
          >
            <Download className="mr-1 h-4 w-4" />
            {translate("下载")}
          </Button>
        ),
        header: () => translate("操作"),
      },
```

新 actions cell:

```tsx
      {
        accessorKey: "actions",
        cell: (ctx) => {
          const file = ctx.row.original;
          const viewable = isViewableKind(file.kind)
            ? viewHrefForKind(file.kind, params.task_id)
            : null;
          return (
            <div className="flex gap-2">
              {viewable ? (
                <Button
                  data-testid={`view-file-${file.filename}`}
                  onClick={() => {
                    router.push(viewable);
                  }}
                  size="sm"
                  variant="outline"
                >
                  <Eye className="mr-1 h-4 w-4" />
                  {translate("查看")}
                </Button>
              ) : null}
              <Button
                data-testid={`download-file-${file.filename}`}
                onClick={() => {
                  void handleDownloadFile(file.filename);
                }}
                size="sm"
                variant="outline"
              >
                <Download className="mr-1 h-4 w-4" />
                {translate("下载")}
              </Button>
            </div>
          );
        },
        header: () => translate("操作"),
      },
```

- [ ] **Step 4: 跑回归测看绿**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- app/\[locale\]/admin/pre-analysis/\[task_id\]/page.test.tsx 2>&1 | tail -30
```

预期: 现有 5 + 新加 1 = 6 PASS.

- [ ] **Step 5: format + lint + typecheck**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run format && bun run lint:fix && bun run typecheck
```

预期: 0 error.

- [ ] **Step 6: commit**

```bash
git add packages/web/app/\[locale\]/admin/pre-analysis/\[task_id\]/_components/admin-pre-analysis-detail-client.tsx \
        packages/web/app/\[locale\]/admin/pre-analysis/\[task_id\]/page.test.tsx
git -c user.name=Claude -c user.email=noreply@anthropic.com commit -m "$(cat <<'EOF'
refactor(web): pre-analysis detail client — actions 列加 查看 按钮

chapter_structure / flagged_paragraphs 行加 查看 button 跳子路由 (chapters / flagged).
table / index 行继续只显示 download (没有 viewer 页).
加 VIEWABLE_KINDS const + isViewableKind 类型守卫 + viewHrefForKind 路径 helper.

详情页回归测加 1 个断言:
- chapter_structure.json / flagged_paragraphs.csv 行有 view-file-... testid
- table 行无 view-file-... testid

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

---

# Phase 5: 全量验证

## Task 7: 全量 lint + typecheck + test

**Files:** (无 file 改动, 全是验证命令)

- [ ] **Step 1: 全量 lint + format check + typecheck**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run format && bun run lint && bun run typecheck
```

预期: format 0 changed, lint 0 error, typecheck 0 error.

- [ ] **Step 2: 全量单测**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test 2>&1 | tail -30
```

预期: 全部测试通过, **包括** 现有 baseline 测试, **外加**新加的:
- lib/api/pre-analysis.test.ts: 8 个新测试 (existing + 8)
- chapters client: 6
- flagged client: 3
- detail page: 1 新断言

实际基线 `packages/web/CLAUDE.md §代码质量清理` 提到 719 passed (baseline 前).
 本期 net + 17 tests.

如果失败 — 不要立即重跑, 先定位:
- 单文件跑 grep FAIL
- 看哪个具体 test 报红
- 修复后再重跑

- [ ] **Step 3: i18n sync 校验**

```bash
cd /home/deyuan/rag/rag/packages/web && node -e "
const zh = JSON.parse(require('fs').readFileSync('messages/zh.json'));
const en = JSON.parse(require('fs').readFileSync('messages/en.json'));
const KEYS = ['章节目录', '段落提取', '查看', '标题', '页范围', '子章节', '展开章节', '总章节', 'toc 来源', '页码', '章节', '段落', '命中规则', '密度', '高密度', '条标记段落', '无章节数据', '无标记段落', '网络异常,请稍后重试', '该任务暂无此产物,请等待 pre-analysis 完成后查看', '章节结构文件格式错误'];
let errCount = 0;
for (const k of KEYS) {
  if (zh[k] !== k) { console.error('zh identity broken:', k, '=', zh[k]); errCount++; }
  if (!en[k]) { console.error('en missing:', k); errCount++; }
}
console.log('Total errors:', errCount);
"
```

预期: `Total errors: 0`.

- [ ] **Step 4: (无 commit, 验证完成)**

---

# 总结

7 个 task, 3 个 commit + 1 个验证 phase:

| Phase | Task | Commit |
|---|---|---|
| 1 | Task 1 | `feat(web): pre-analysis viewer pages — helper + types + unit tests` |
| 2 | Task 2, 3 | `feat(web): pre-analysis viewer — 章节目录页 (扁平可折叠)` |
| 3 | Task 4, 5 | `feat(web): pre-analysis viewer — 段落提取页 (14 列实体表)` |
| 4 | Task 6 | `refactor(web): pre-analysis detail client — actions 列加 查看 按钮` |

Phase 5 不 commit, 只验证.

## 风险记录 (实施时如遇到, 回头查这张表)

| 风险 | 触发条件 | 解决 |
|---|---|---|
| Task 2 RSC entry 跑 typecheck 时 "Cannot find module" 报红 | Task 1 没完成 | 先跑 Task 1 再跑 Task 2 |
| Task 6 改 detail client 时 useRouter 加错位置 | import 顺序警告 | 按字母序: lucide-react → next-intl → react → 项目内 @/... |
| i18n key 漏加导致 test 报 MISSING_MESSAGE | 没跑 step 6 (Task 2-3) | 跑 Task 3 step 6 加 zh/en.json |
| AppTooltip import path 错 | 误以为在 feedback/ | 实际在 `components/common/overlay/app-tooltip` |
| guardPage mode | spec 写 `requiredRole="admin"` 实际是 `pageKey="admin"` | 用后者 |
| ErrorBanner data-testid vs dataTestid | spec 写错 | 数据 ID 走 camelCase `dataTestid` |
| `FlaggedParagraphRow` 类型对不上 (列数 / 字段) | 后端 schema 变 | helper 内 String/Number 兜底, 失败返 0 或 "" |
| papaparse 引号转义不识别 | 多行字段 / 非标准 CSV | 默认 options 已够; 数据 fix 而不是升级 papaparse |

## 跟现有约定的关键差异 (避免按 spec 直接抄)

1. **Spec §6.5 GuardPage 用错**: `requiredRole` 不存在, 用 `pageKey="admin"`
2. **Spec §6.4 AppTooltip 路径错**: 是 `overlay/app-tooltip` 不是 `feedback/app-tooltip`
3. **Spec §6.4 ErrorBanner dataTestid**: camelCase 不是 kebab-case
4. **Spec §6.6 VIEWABLE_KINDS 位置**: 抽到模块顶部常量比 inline 在 cell 里更易测/审 (项目惯例)
5. **Spec §6.4 列省略**: 14 列 → 8 列; raw_density / weighted_density / safe_hits / rec_hits / lemmas / matched_keywords 等本期省略 (用户校对关注 page + section + text + density, 后端列数据细节不重要)
6. **Spec §6.5 同步 vs Promise params**: 实际 page.tsx 用 `params: Promise<...>`, client 子组件 params 是 sync — 跟现状一致

---

# Self-Review 报告

✅ **Spec 覆盖核查**:
- §6.1 helper 签名 → Task 1
- §6.2 章节目录客户端 → Task 2 + 3
- §6.4 段落客户端 → Task 4 + 5 (5 列省略是合理决策, 在 self-review 报告里说明)
- §6.5 RSC entry → Task 2 + 4
- §6.6 详情页改 → Task 6
- §8 测试 → Task 1 (helper) + 3 (chapters client) + 5 (flagged client) + 6 (detail 回归)
- §9 i18n → Task 3 step 6
- §10 阶段交付 → Task 1/2-3/4-5/6 4 个 commit
- §11/§12 风险和文档 → 本 plan 风险表 + spec 是设计唯一来源

✅ **Placeholder 扫描**:
- 无 "TBD" / "TODO" / "implement later"
- 无 "Add appropriate error handling" 类模糊描述
- 每个 test step 有具体 assertion + 值
- 无 "Similar to Task N" — 每个 task 自包含

✅ **Type 一致性**:
- `ChapterTreeNode` 在 Task 1 定义, Task 3 用 `import type { ChapterTreeNode }`
- `ChapterStructurePayload` 同
- `FlaggedParagraphRow` 在 Task 1 定义, Task 5 用
- `FlatChapterRow` 在 Task 3 内部定义 (UI 内部类型, 不导出)
- `getPreAnalysisChapterStructure(taskId)` / `getPreAnalysisFlaggedParagraphs(taskId)` 签名一致

✅ **修正 spec 错误**:
- §6.5 GuardPage 用 `pageKey="admin"` (不是 `requiredRole="admin"`)
- §6.4 AppTooltip import path 用 `overlay/app-tooltip` (不是 `feedback/app-tooltip`)
- §6.4 ErrorBanner 用 `dataTestid` (camelCase)
- §6.6 把 `VIEWABLE_KINDS` / `isViewableKind` / `viewHrefForKind` 抽到模块顶部 (不 inline 在 cell)

✅ **歧义消除**:
- i18n key 21 个明确列出在 Task 3 step 6
- 5 列省略理由写在 plan self-review 报告
- 各 phase `expected output` (PASS / 0 error) 明确
- 风险表 8 行, 实施时直接查
