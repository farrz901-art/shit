# 2026-07-09 Pre-analysis 产物查看页 (章节目录 + 段落提取) 设计

> Brainstorming 沉淀. 用户报告: 详情页只能下产物文件, 看不到内容.
>
> 本 spec 在现有详情页加 2 个子路由:
> `[task_id]/chapters` (扁平可折叠章节表) + `[task_id]/flagged` (标记段落实体表).
> 加 2 个 helper (`getPreAnalysisChapterStructure` / `getPreAnalysisFlaggedParagraphs`),
> 用 papaparse 解析 CSV.

## 1. 背景

### 1.1 现状 (代码已确认)

详情页 `packages/web/app/[locale]/admin/pre-analysis/[task_id]/_components/admin-pre-analysis-detail-client.tsx:185-289` 当前渲染:

- 任务状态卡片 (PDF 文件名 / 状态 / 耗时)
- 4 个 StatCard (表格数 / 章节数 / 标记段落数 / 跨页候选)
- **产物 DataTable** (kind / filename / size / 仅下载按钮)

产物 DataTable 4 种 kind: `chapter_structure` / `flagged_paragraphs` / `table` / `index`.
当前操作列**只有下载按钮**, 用户看不到内容, 必须在本地解压 zip 才能看产物长啥样.

### 1.2 用户报告

- 用户在 Siemens D81.1 PDF 等大文档 pre-analysis 后, 想验证 "章节树识别是否对"/"标记段落命中位置在哪"
- 流程断在 "下 zip → 解压 → 看 JSON / CSV" 4 步, 平台
  admin 视角应能在 web 端直接预览这 2 类关键产物

### 1.3 现有 helper (lib/api/pre-analysis.ts)

只有一个产物文件下载 API: `downloadPreAnalysisFile(taskId, filename): Promise<Blob>`.
**没有** JSON.parse 后返回 typed 对象的 helper, **没有** CSV → row 的 helper.

后端单文件 endpoint `GET /api/pre-analysis/tasks/{id}/files/{filename}` 已就绪
(`packages/service/src/ingest/pre_analysis/router.py:232-281`):

- `chapter_structure.json` → 返回 `application/json` mime, 内容是嵌套 chapter 树
- `flagged_paragraphs.csv` → 返回 `application/json` mime (后端已知 Content-Type bug, 见
  `router.py:272` 强制改 mime; 实际是 CSV 文本), 14 列 1 表头 + N 行

### 1.4 项目前后端约定

- 前端 lib 直连后端路径 `/api/pre-analysis/*` (现有 lib/api/pre-analysis.ts 全部 fetch 直连,
  BFF route 一行都没有, 跨 spec 已知 gap, 本期不补)
- i18n key 用中文作 key, zh.json identity (`value=key`), en.json 翻译
- 路由跳转必须 `import { useRouter } from "@/i18n/navigation"` (强制 locale 前缀)
- 文件命名 kebab-case (`admin-pre-analysis-chapters-client.tsx`)
- 数据表格复用 `<DataTable<T>>` (`@/components/common/table/data-table`), 不许手写 `<table>` markup

## 2. 目标

- **新增 2 个子路由** `/admin/pre-analysis/{task_id}/chapters` 和
  `/admin/pre-analysis/{task_id}/flagged`, 直连后端拉产物并渲染
- **新增 2 个 helper** (`getPreAnalysisChapterStructure` / `getPreAnalysisFlaggedParagraphs`)
  把产物 fetch + 解析合为一个 Promise<typed> 函数
- **章节树用扁平 + indent 列实现可折叠表格**, 默认全部折叠 (用户进页只看到一级章节)
- **详情页产物表格操作列加分 "查看" 按钮** 跳子路由; 其它 kind (table / index) 不动, 仍只下载
- **i18n 加 ~16 个 key** (页面标题 / 列名 / 错误信息 / 按钮文案)

## 3. 非目标

- **不**开 pre-analysis BFF (整个 pre-analysis 模块的 BFF 缺失是先验 gap,
  后续 spec 单独补, 本期继续直连后端, 跟现有 lib/api/pre-analysis.ts 风格一致)
- **不**改后端 (`packages/service/src/ingest/pre_analysis/router.py:272` 那个
  application/json mime bug 不动, 前端按 text 读)
- **不**渲染后端另外 2 类产物 (table / index), 本期只做章节树 + 标记段落
- **不**改 admin / pre-analysis 列表页 (`admin/pre-analysis/page.tsx`)
- **不**改后端 schema (`ChapterTreeNode.children` 嵌套结构不重构)
- **不**改 TanStack DataTable 内部实现 (本期不引入 `getExpandedRowModel`, 扁平 + indent 列
  模式即可, 详见 §6.2 技术决策)
- **不**做 E2E 测试 (本期先单测, e2e 跟后续 BFF 一起补)
- **不**做"全部展开 / 全部折叠"快捷按钮 (默认全折叠, 用户逐个点开符合 doc 现状)

## 4. 整体架构

### 4.1 URL 形态

| URL | 渲染 | BackLink 指向 |
|---|---|---|
| `/{locale}/admin/pre-analysis/{task_id}` | 详情页 (不变) | `/admin/pre-analysis` |
| `/{locale}/admin/pre-analysis/{task_id}/chapters` | 章节目录页 (新) | `/admin/pre-analysis/{task_id}` |
| `/{locale}/admin/pre-analysis/{task_id}/flagged` | 标记段落实体页 (新) | `/admin/pre-analysis/{task_id}` |

### 4.2 文件树

```
packages/web/app/[locale]/admin/pre-analysis/[task_id]/
├── _components/
│   └── admin-pre-analysis-detail-client.tsx        # 改: 操作列加 "查看" 按钮
├── chapters/                                       # 新
│   ├── page.tsx                                    # 新 RSC entry
│   └── _components/
│       └── admin-pre-analysis-chapters-client.tsx  # 新
└── flagged/                                        # 新
    ├── page.tsx                                    # 新 RSC entry
    └── _components/
        └── admin-pre-analysis-flagged-client.tsx   # 新

packages/web/lib/api/
├── pre-analysis.ts                                 # 改: +2 helpers + 3 types
└── pre-analysis.test.ts                            # 改: helper 单测

packages/web/messages/
├── zh.json                                         # 改: 加 ~16 中文 key
└── en.json                                         # 改: 加同 key 英文翻译
```

### 4.3 数据流

```
User → Chapters Page → useQuery({queryKey, queryFn: getPreAnalysisChapterStructure})
                       ↓
                  fetch /api/pre-analysis/tasks/{id}/files/chapter_structure.json
                       ↓
                  Resp.ok → blob.text() → JSON.parse → ChapterStructurePayload
                       ↓
                  flattenChapters(payload.chapters, collapsedRecord) → FlatChapterRow[]
                       ↓
                  DataTable<FlatChapterRow> (4 列: 标题含 chevron+indent / 页范围 / 子章节数 / 操作)
                       ↓
                  点击 chevron → setCollapsed(Record<id, true|false>) → 重 flatten

User → Flagged Page  → useQuery({queryFn: getPreAnalysisFlaggedParagraphs})
                       ↓
                  fetch /api/pre-analysis/tasks/{id}/files/flagged_paragraphs.csv
                       ↓
                  Resp.ok → blob.text() → papaparse.parse(header:true) → FlaggedParagraphRow[]
                       ↓
                  DataTable<FlaggedParagraphRow> (14 列全展示 + 格式化)
```

## 5. 后端契约 (本期不改, 只读后端 schema)

### 5.1 chapter_structure.json schema

来源: `packages/service/src/ingest/pre_analysis/chapters_section.py:82-90` + 实际落地文件.

```ts
interface ChapterTreeNode {
  id: string;        // "ch_<n>"
  level: number;     // 1-6
  title: string;
  page_start: number;
  page_end: number;
  children: ChapterTreeNode[];   // 递归, 叶子为空数组
}

interface ChapterStructurePayload {
  max_level: number;                          // 配置截断深度
  total_pages: number;
  total_chapters: number;                     // 含嵌套的递归计数
  extracted_at: string;                       // ISO8601
  toc_source: "pdf_outline" | "toc_pages" | "llm_refined" | "empty";
  llm_summary_enabled: boolean;
  chapters: ChapterTreeNode[];
}
```

### 5.2 flagged_paragraphs.csv schema

来源: `packages/service/src/ingest/pre_analysis/flagged_section.py:26-41` (CSV_FIELDNAMES).

14 列 (按顺序):

```
matched_keywords | page | section | text | rule_categories | density |
is_dense | raw_density | weighted_density | safe_hits | rec_hits |
lemmas | token_count | language
```

写入 mime 是 `text/csv` (`flagged_section.py:110`),
但 `/files/{filename}` 端点 `router.py:272` 强制改 `application/json`.
**前端按 text 读, 不检查 Content-Type.**

## 6. 详细设计

### 6.1 helper 签名 (lib/api/pre-analysis.ts)

加 3 个 export type + 2 个 export 函数:

```ts
/**
 * 章节树原始 JSON 节点 (递归, 跟后端 schema 严格对齐)
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
 * chapter_structure.json 解析后顶层 payload.
 * @property max_level 后端 truncate 截断深度
 * @property total_pages PDF 总页数
 * @property total_chapters 章节总数 (含嵌套)
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
 * flagged_paragraphs.csv 一行解析结果, 14 字段 + row_index.
 * @property row_index 1-based 行号 (CSV 表头是 row 0, 第一条数据是 row 1)
 * @property matched_keywords 命中的关键词 (DictReader 兼容字段)
 * @property text 段落实体 (可能很长, 渲染时截断 + tooltip)
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
  lemmas: string;          // JSON string 原样返
  token_count: number;
  language: string;
}

/**
 * 拉取任务章节结构文件, fetch + JSON.parse 返解析后的 payload.
 * 调后端 GET /api/pre-analysis/tasks/{taskId}/files/chapter_structure.json.
 * @param taskId 任务 ID
 * @returns 解析后的章节结构对象
 * @throws 当后端返 4xx/5xx, 或 JSON.parse 失败, 或 schema 不符时
 * @client-bff
 */
export const getPreAnalysisChapterStructure = (
  taskId: string,
): Promise<ChapterStructurePayload>;

/**
 * 拉取任务标记段落实体 CSV, fetch + papaparse 解析返 rows.
 * 后端 /files/{filename} 用 'application/json' mime 返 CSV (router.py:272 已知),
 * 本函数 blob.text() 后按 text 解析, 不检查 Content-Type.
 * @param taskId 任务 ID
 * @returns 已 parse 的 rows (空数组 if 文件仅表头)
 * @throws 当后端返 4xx/5xx 时
 * @client-bff
 */
export const getPreAnalysisFlaggedParagraphs = (
  taskId: string,
): Promise<FlaggedParagraphRow[]>;
```

实现骨架 (跟现有 `downloadPreAnalysisFile` 一致:

```ts
const FLAG_CSV_FILENAME = "flagged_paragraphs.csv";
const CHAPTER_JSON_FILENAME = "chapter_structure.json";

const fetchPreAnalysisFile = async (taskId: string, filename: string): Promise<string> => {
  const resp = await fetch(
    `/api/pre-analysis/tasks/${encodeURIComponent(taskId)}/files/${filename}`,
  );
  if (!resp.ok) {
    throw new Error(`pre-analysis file ${filename} fetch failed: ${resp.status}`);
  }
  return resp.text();
};

export const getPreAnalysisChapterStructure = async (
  taskId: string,
): Promise<ChapterStructurePayload> => {
  const text = await fetchPreAnalysisFile(taskId, CHAPTER_JSON_FILENAME);
  const parsed = JSON.parse(text) as ChapterStructurePayload;
  // 最小 sanity check: chapters 是数组. 后端 schema 不变, 无需 zod.
  if (!Array.isArray(parsed.chapters)) {
    throw new Error("chapter_structure.json: 'chapters' field is not an array");
  }
  return parsed;
};

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

CSV 解析注释: `is_dense` 后端写的是 Python `bool` (`flagged_section.py:97`),
CSV 序列化变 `True` / `False` (capitalized). papaparse 不会自动转 bool, 所以 helper 内手动比对.

### 6.2 章节目录客户端

`admin-pre-analysis-chapters-client.tsx`:

```tsx
"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { DataTable, type ColumnDef } from "@/components/common/table/data-table";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { Button } from "@/components/ui/button";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useState } from "react";
import { getPreAnalysisChapterStructure, type ChapterTreeNode } from "@/lib/api/pre-analysis";

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
/** chevron 按钮尺寸 (h-/w-) */
const CHEVRON_BUTTON_SIZE = "h-6 w-6";

/** 递归扁平化 + 应用 collapsed 状态 (深度优先). */
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

interface PageProps {
  params: { task_id: string };
}

/**
 * Admin pre-analysis 章节目录客户端组件 (2026-07-09)
 *
 * 调 getPreAnalysisChapterStructure 拉扁平 JSON, 客户端嵌套结构扁平化 + indent 列
 * 渲染可折叠表格. 默认全部折叠 (用户进页只看一级).
 *
 * @client-bff
 */
export const AdminPreAnalysisChaptersClient = ({ params }: PageProps): React.ReactElement => {
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
                  className={CHEVRON_BUTTON_SIZE}
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

技术决策:

- **默认全折叠**: 用户案例中章节通常 < 100 节点但可能跨 3-4 层,
  默认全开会让首屏要滚 3 屏才能看到 PDF 文件名.
  默认全折叠 + 只显示 L1 节点, 用户想看细节再点开. 跟"从概括到细节"的阅读习惯对齐.
  (实施中如发现用户反馈"想默认全开", 再迭代)
- **扁平 + indent 列 (不用递归 DataTable)**: 见 §6.3
- **后端默认 expanded**: 不改. 折叠状态是**客户端**的偏好, 跟后端 chapter_structure.json 解耦.

### 6.3 章节树不嵌套 DataTable 的理由

经过详尽调研 (`packages/web/components/common/table/data-table.tsx:147`,
`data-table-body.tsx:101-126`), 嵌套 DataTable 在本项目有以下多重风险:

| 风险 | 现状 |
|---|---|
| border 双线 | `data-table-body.tsx:119` 假设展开行是表体末行, 加 `border-b-0`. 嵌套表格中外层展开行是中间行, 跟相邻数据行画双 border |
| stagger 动画串扰 | `data-table-body.tsx:148` 用 `motion.tr` + `rowStagger`, 嵌套时深层 stagger 触发外层父行 frame 抖动 |
| React key 冲突 | 父子都用 `rowKey="id"` (后端 ch_1, ch_2... 全局唯一, 但内层 motion.tr key 用 `${key}-expanded` 命名空间, 多层不够) |
| 每层分页器 | `data-table.tsx:305` pagination 受控, 嵌套时每层都渲染分页器 (噪声) |
| maxHeight 滚动嵌套 | sticky 表头要求 `maxHeight`, 嵌套时双 scrollbar |
| 性能 | 无虚拟化, 1000 节点全开 = 2000-3000 `<tr>` 全 DOM 渲染 |

而 **扁平 + indent 列**模式只动业务侧 (列的 cell 内联 indent + chevron), 不动 DataTable 内部:
- 复用列对齐 / sticky / 分页 / loading 全部 DataTable 能力
- 性能: 单层 DataTable, N 个 `<tr>`, N 即实际可见章节数
- 状态简单: `Record<id, boolean>`, 客户端 toggle 即时

### 6.4 段落客户端

`admin-pre-analysis-flagged-client.tsx`:

```tsx
"use client";

import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DataTable, type ColumnDef } from "@/components/common/table/data-table";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { AppTooltip } from "@/components/common/feedback/app-tooltip";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { getPreAnalysisFlaggedParagraphs, type FlaggedParagraphRow } from "@/lib/api/pre-analysis";

/** 段落页每页条数 (跟详情页产物列表一致) */
const FLAG_PAGE_SIZE = 5;
/** 初始化分页页码 */
const INITIAL_PAGE = 1;
/** 密度列小数位 */
const DENSITY_DECIMALS = 1;
/** token 列千分位分隔 */
const THOUSAND_SEPARATOR = ",";
/** text 列最大宽度 (ch) */
const TEXT_MAX_WIDTH_CH = 60;
/** text 列截断行数 */
const TEXT_LINE_CLAMP = 3;

interface PageProps {
  params: { task_id: string };
}

const formatNumber = (num: number): string => {
  return num.toFixed(DENSITY_DECIMALS);
};

const formatToken = (num: number): string => {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, THOUSAND_SEPARATOR);
};

export const AdminPreAnalysisFlaggedClient = ({ params }: PageProps): React.ReactElement => {
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
        description={
          data ? `${data.length} ${translate("条标记段落")}` : undefined
        }
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

技术决策:

- **14 列全部展示, 不分页**: 用户既要 page / section / token_count 概要信息,
  也要 text 段落实体. 不展示会让校对段落不可用
- **text 列用 AppTooltip**: 段落可能很长 (几十字到几百字), 不能让 cell 撑爆其它列宽.
  CSS `line-clamp-3 max-w-[60ch]` + hover tooltip 看完整内容
- **is_dense=true 行用 AlertTriangle icon + Badge**: 不用 emoji, 跟项目 [[feedback-no-emoji-use-lucide-icons]] 一致
- **字段映射**: 14 列全部前端做类型转换 (Number/Boolean). 后端 CSV 是 python repr,
  papaparse 不自动转. 失败兜底 Number(x ?? 0) = 0

### 6.5 RSC entry pages

`chapters/page.tsx` 和 `flagged/page.tsx` 都遵循项目现有模式 (跟详情 page.tsx 同 shape):

```tsx
// chapters/page.tsx
import { GuardPage } from "@/lib/auth/guard-page";
import { AdminPreAnalysisChaptersClient } from "./_components/admin-pre-analysis-chapters-client";

interface PageProps {
  params: Promise<{ task_id: string }>;
}

export default async function AdminPreAnalysisChaptersPage(props: PageProps) {
  const { task_id } = await props.params;
  return (
    <GuardPage requiredRole="admin">
      <AdminPreAnalysisChaptersClient params={{ task_id }} />
    </GuardPage>
  );
}
```

> ⚠ 详情页 `admin-pre-analysis-detail-client.tsx:62-65` 当前 `params: { task_id: string }`
> (同步, 不是 Promise). 跟 Next 16 实际不一致 (page.tsx 是 Promise). 详情页有 client component
> 类型 mismatch, 但 AdminPreAnalysisDetailClient 只读 props.params.task_id (同步值), 所以运行时 OK
> (Next 16 把 Promise<{...}> await 后传 sync value 到 client).
> **本期跟现状一致, 同步 params**. 如果后续要统一 Promise, 单独 spec 处理.

### 6.6 详情页改动

`admin-pre-analysis-detail-client.tsx` 改 actions 列 (`admin-pre-analysis-detail-client.tsx:167-182`),
`chapter_structure` / `flagged_paragraphs` 这 2 类 kind 加 "查看" 按钮.

```tsx
// 新增 import
import { useRouter } from "@/i18n/navigation";
import { Eye } from "lucide-react";

// 组件内
const router = useRouter();

// 改 actions 列
const VIEWABLE_KINDS = ["chapter_structure", "flagged_paragraphs"] as const;
type ViewableKind = (typeof VIEWABLE_KINDS)[number];

const isViewableKind = (
  kind: PreAnalysisOutputFile["kind"],
): kind is ViewableKind =>
  (VIEWABLE_KINDS as readonly PreAnalysisOutputFile["kind"][]).includes(kind);

const viewHrefForKind = (kind: ViewableKind, taskId: string): string =>
  kind === "chapter_structure"
    ? `/admin/pre-analysis/${taskId}/chapters`
    : `/admin/pre-analysis/${taskId}/flagged`;

// 在 columns actions cell 内
cell: (ctx) => {
  const file = ctx.row.original;
  const viewable = isViewableKind(file.kind) ? viewHrefForKind(file.kind, params.task_id) : null;
  return (
    <div className="flex gap-2">
      {viewable ? (
        <Button
          data-testid={`view-file-${file.filename}`}
          onClick={() => router.push(viewable)}
          size="sm"
          variant="outline"
        >
          <Eye className="mr-1 h-4 w-4" />
          {translate("查看")}
        </Button>
      ) : null}
      <Button
        data-testid={`download-file-${file.filename}`}
        onClick={() => void handleDownloadFile(file.filename)}
        size="sm"
        variant="outline"
      >
        <Download className="mr-1 h-4 w-4" />
        {translate("下载")}
      </Button>
    </div>
  );
};
```

table / index 两条不显示 "查看" 按钮 (它们没有 viewer 页). 详细在 DataTable 不变,
只有 actions 列 cell 函数体改大.

## 7. 错误处理

| 失败 case | UI 表现 | 触发条件 |
|---|---|---|
| fetch 抛错 (网络断 / CORS) | `<ErrorBanner variant="destructive">{translate("网络异常,请稍后重试")}</ErrorBanner>` | `error.name === "TypeError"` |
| 404 (任务没那个文件, 未到该 stage) | `<ErrorBanner variant="warning">{translate("该任务暂无此产物,请等待 pre-analysis 完成后查看")}</ErrorBanner>` | `resp.status === 404` |
| 5xx (后端 bug) | `<ErrorBanner variant="destructive">后端错误: {status}</ErrorBanner>` | `resp.status >= 500` |
| JSON.parse 失败 (章节结构损坏) | `<ErrorBanner variant="destructive">章节结构文件格式错误</ErrorBanner>` | try/catch in helper |
| chapter payload `chapters: []` (empty tree) | `<DataEmpty title="PDF 自动识别失败,toc_source=empty">` | `flattened.length === 0` |
| CSV 空文件 (0 行数据) | `<DataEmpty title={translate("无标记段落")} />` | `data?.length === 0` |
| 任务状态 pending/running 时访问子页 | 不阻止, DataTable 自带 loading 状态, fetch 拿不到文件则上面 404 警告 | any |

实现:

- helper 抛错被 React Query 捕获, 暴露在 `error` 字段
- ErrorBanner 在 error 渲染
- 不使用 Toast/Sonner (一次只一个错误, 多弹窗噪音)
- 客户端不去 try/catch fetch 错误, 让 React Query 拿原始 error, 模板里直接 stringify

## 8. 测试

### 8.1 helper 单测 (lib/api/pre-analysis.test.ts)

**`getPreAnalysisChapterStructure`**:
1. ✅ mock fetch 返 `Response('{"chapters":[{"id":"ch_1",...}],"max_level":3,...}')`, 断言返 typed object
2. ✅ mock fetch 返 `Response('not found', {status: 404})`, 断言 throw 含 "fetch failed"
3. ✅ mock fetch 返 `Response('{not valid json')`, 断言 throw
4. ✅ mock fetch 返 `Response('{}')` (chapters 缺), 断言 throw 含 "'chapters' field is not an array"

**`getPreAnalysisFlaggedParagraphs`**:
1. ✅ mock fetch 返 14 列 + 3 数据行 CSV 字符串, 断言返 3 个 typed row (字段类型对)
2. ✅ mock CSV 文本含引号转义 `text="hello, ""world"""`, 断言 text 字段解析无逗号
3. ✅ mock CSV 仅表头 (无数据行), 断言返 `[]`
4. ✅ mock fetch 返 404, 断言 throw
5. ✅ is_dense 列 `True/False` 转 boolean (不是字符串)

### 8.2 章节页客户端单测 (admin-pre-analysis-chapters-client.test.tsx)

1. ✅ mock query 3 层节点 (3 个 L1 + 1 个 L2 ch_2 + 1 个 L3 ch_3), 断言默认全折叠后 DOM 仅 3 行
2. ✅ 点 ch_2 chevron, 断言 ch_3 节点从 DOM 出现 (因为 ch_2 现在展开)
3. ✅ 叶子节点渲染 `<span className="inline-block w-6" />` 占位 (无 chevron 按钮)
4. ✅ 缩进断言: mock ch_3.depth=3, 断言外层 `<div>` 的 `padding-left: "72px"` (3 × 24)
5. ✅ empty trees: mock `chapters: []`, 断言 `<DataEmpty>` 渲染
6. ✅ error: mock query 失败, 断言 `<ErrorBanner variant="destructive">` 渲染

### 8.3 段落页客户端单测 (admin-pre-analysis-flagged-client.test.tsx)

1. ✅ mock 4 row data, 断言 14 列渲染 (列名 + 值)
2. ✅ is_dense=true 行有 `<Badge variant="warning">` + AlertTriangle icon
3. ✅ text 列有 AppTooltip, hover 显示完整段落
4. ✅ 空 data 渲染 `<DataEmpty>`

### 8.4 详情页回归 (admin-pre-analysis-detail-client.test.tsx)

- 不改 test, 但跑现有 test 看 4 产物行还能渲染. 新增断言:
  - chapter_structure 行有 `[data-testid="view-file-chapter_structure.json"]` 按钮
  - flagged_paragraphs 行有 `[data-testid="view-file-flagged_paragraphs.csv"]` 按钮
  - table / index 行**无** view 按钮 (只有 download)

### 8.5 E2E

本期不做. 跟后续 BFF + admin 全模组 E2E 一起补.

### 8.6 测试运行约束

`packages/web/CLAUDE.md` §测试效率: 开发循环跑单文件, 不跑全量.

```bash
# 单文件
bun run test -- lib/api/pre-analysis.test.ts
bun run test -- app/.../admin-pre-analysis-chapters-client.test.tsx
bun run test -- app/.../admin-pre-analysis-flagged-client.test.tsx
bun run test -- app/.../admin-pre-analysis-detail-client.test.tsx

# 完整跑 (commit 前)
bun run test
```

## 9. i18n

新加 16 个 key, zh.json identity (`value = key`), en.json 翻译:

```jsonc
// zh.json
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
"语言": "语言",
"Token": "Token",
"条标记段落": "条标记段落",
"无章节数据": "无章节数据",
"无标记段落": "无标记段落",
"网络异常,请稍后重试": "网络异常,请稍后重试",
"该任务暂无此产物,请等待 pre-analysis 完成后查看": "该任务暂无此产物,请等待 pre-analysis 完成后查看",
"章节结构文件格式错误": "章节结构文件格式错误",
"PDF 自动识别失败,toc_source=empty": "PDF 自动识别失败,toc_source=empty",

// en.json
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
"语言": "Language",
"Token": "Token",
"条标记段落": "flagged paragraphs",
"无章节数据": "No chapter data",
"无标记段落": "No flagged paragraphs",
"网络异常,请稍后重试": "Network error, please retry",
"该任务暂无此产物,请等待 pre-analysis 完成后查看": "Artifact not yet available, please wait until pre-analysis completes",
"章节结构文件格式错误": "Chapter structure file format error",
"PDF 自动识别失败,toc_source=empty": "PDF outline detection failed (toc_source=empty)"
```

校验脚本 (zh identity, en 翻译存在):

```bash
node -e "
const zh = JSON.parse(require('fs').readFileSync('messages/zh.json'));
const en = JSON.parse(require('fs').readFileSync('messages/en.json'));
const KEYS = ['章节目录', '段落提取', /* ... 全部 23 个 ... */];
for (const k of KEYS) {
  if (zh[k] !== k) console.error('zh identity broken:', k);
  if (!en[k]) console.error('en missing:', k);
}
"
```

## 10. 交付阶段 (3 个 phase, 各跑 lint + typecheck + 单测)

| Phase | 文件 | 验收 |
|---|---|---|
| 1 — helper | `lib/api/pre-analysis.ts` 加 3 type + 2 helper | §8.1 单测绿 |
| 2 — 章节页 | `chapters/page.tsx` + `chapters/_components/admin-pre-analysis-chapters-client.tsx` + 测试 | §8.2 绿 |
| 3 — 段落页 + 详情页改 | `flagged/page.tsx` + `flagged/_components/admin-pre-analysis-flagged-client.tsx` + `admin-pre-analysis-detail-client.tsx` actions 列改 + 测试 + i18n | §8.3 + §8.4 绿 + i18n 全 key 存在 |

每个 phase:

1. `bun run format` (oxfmt --write)
2. `bun run lint:fix` (oxlint)
3. `bun run typecheck` (tsc --noEmit)
4. `bun run test -- <改动的 test 文件>` 单文件跑
5. 最终 phase 3 commit 前跑 `bun run test` 全量 (~ 1 分钟)

中间 phase 不跑全量, 跟 `packages/web/CLAUDE.md §测试效率` 一致.

## 11. 风险与回滚

| 风险 | 概率 | 影响 | 回滚 |
|---|---|---|---|
| papaparse parse 有边界 case 漏 (引号 / 多行字段) | 低 | 该 row 数据缺失或错位 | 收紧 `parse` options (`quoteChar: '"'` + `escapeChar: '"'`); 或回归测试覆盖 |
| 章节树嵌套很深 (> 10 层) 拖慢 React | 低 | 前端卡 | 加 `chapter_max_level_for_display` 截断 (后端 2026-07-09 已加, 默认 3); 或 useMemo 化 `flattenChapters` |
| 后端 schema 改 (e.g. 加列) helper 没及时改 | 中 | 字段 undefined / Number 兜底返 0 | helper 内 String/Number 兜底, 单测覆盖新 schema |
| 详情页 actions 列改影响现有 4 产物行回归 | 低 | 按钮错位 / 测试 fail | actions 列只 cell 函数体改大, 不动 columns 数组结构; 跑现有 admin-pre-analysis-detail-client.test.tsx 验证 |
| 默认全折叠让用户觉得 "看不到东西" | 中 | 用户进页只看 L1 | 后续在 PageHero 加 "全部展开" 按钮 (本期不做, 留作后续 plan) |
| `params: { task_id: string }` 同步 vs Promise 不一致 | 已知 | 类型警告但 runtime 正常 | 跟现有详情页一致 (同步); 后续统一 |

## 12. 文档同步

- `packages/web/CLAUDE.md` 不改 (本期只是新增 2 个 viewer 页, 不引入新封装模式)
- `packages/web/app/[locale]/admin/pre-analysis/` 目录 (与 page.tsx 平行) 不写 README, 业务代码自解释
- 本 spec 是设计文档唯一来源
- 实施完成后在 `docs/superpowers/specs/` 同名 spec 末尾追加 "实施记录" 段
  (实施完成的日期 / commit hash / 测试结果), 沉淀后续 plan 链接
