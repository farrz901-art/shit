# A3 TS Hook/Util Oversize-Files Audit (2026-07-10)

扫描日期: 2026-07-10
扫描范围: packages/web/ 4 个 .ts 文件 (总 1868 行)
输出格式: 每文件 7 段 (拆分点 / 纯函数化 / 库替代 / 对象替 if / 数组迭代 / 预计减少 / 骨架伪代码)
库替代基线: package.json:62 (es-toolkit) / :72 (react-use) / :80 (zod) / :78 (tailwind-merge) / :60 (dexie) / :76 (sonner)
未装确认: 项目无 ahooks / dayjs / nuqs / lodash / moment 依赖 (package.json:30-82)

---

### `lib/api/pre-analysis.ts` (585 行)

**1. 拆分点**:
- L10-136 13 个 interface (Summary/OutputFile/TaskState/OverallStage/DetailStage/StageStatus/StageItem/StagesResponse/RetryResponse/TaskItem/TaskDetail/UploadResponse/ListResponse) -> `pre-analysis-types.ts` (~127 行)
- L138-146 `handleError` 内部 helper -> 已经在 lib/api/config.ts 里有, 复用 `handleFetchError` (lib/api/errors.ts) -> 删本地实现
- L148-176 `TableExtractionConfig` + `ChapterExtractionConfig` 2 config interface -> `pre-analysis-config.ts` (~30 行)
- L178-315 上传/列表/详情/下载/stages/retry 6 个 fetch wrapper (含 FormData / apiFetch) -> `pre-analysis-tasks.ts` (~138 行)
- L317-321 章节树常量 (CHAPTER_JSON_FILENAME / FLAG_CSV_FILENAME / ZERO / EMPTY_STRING / ROW_INDEX_BASE) -> 留 pre-analysis-types.ts 或 const/
- L322-327 数字/字符串兜底常量 (ZERO / EMPTY_STRING / ROW_INDEX_BASE) -> 用 const/index.ts 的 ZERO / 提取本地 const
- L329-403 `ChapterTreeNode` / `ChapterStructurePayload` / `FlaggedParagraphRow` 3 个 viewer interface -> `pre-analysis-viewer-types.ts` (~75 行)
- L405-480 `fetchPreAnalysisFile` + `getPreAnalysisChapterStructure` + `getPreAnalysisFlaggedParagraphs` 3 个 chapter/flag 解析 -> `pre-analysis-viewer.ts` (~75 行)
- L482-585 `TablePagesResponse` / `TablePageItem` / `TablePageResponse` 3 个 table interface + `parseTableFilename` + `getPreAnalysisTablePages` + `getPreAnalysisTablePage` -> `pre-analysis-tables.ts` (~104 行)

**2. 纯函数/hook 化**: 可拆
- `parseTableFilename` 已是 pure func (regex exec + 数值转换), 无副作用
- `getPreAnalysisFlaggedParagraphs` 内 `parsed.data.map(...)` 行转换可拆 `mapFlaggedRow(raw: Record<string, string>, idx: number): FlaggedParagraphRow` pure func, 13 个 `?? EMPTY_STRING` / `Number() ?? ZERO` 字段映射清晰
- `getPreAnalysisChapterStructure` 内 `if (!Array.isArray(parsed.chapters)) throw` 可拆 `assertChaptersArray(parsed: unknown): asserts parsed is ChapterStructurePayload`
- `handleError` 删本地, 复用 lib/api/errors.ts

**3. 库替代**: ✅
- es-toolkit `pick` 已装 (package.json:62) — 不适用本文件 (无字段 pick 场景)
- es-toolkit `omit` — 不适用
- react-use 已装 (package.json:72) — 不适用 (无 useAsyncFn / useMount 等 hook 需求)
- zod 已装 (package.json:80) — 可替手写 `if (!Array.isArray(parsed.chapters))` 类型守卫, 但本文件只 1 处断言, 引入 zod 收益低, 不强推
- 无 dayjs / moment — 本文件不用日期格式化

**4. 对象替 if**: 无
- L439-444 `if (!Array.isArray(parsed.chapters)) throw` — 单点断言, 不构成 if/else 链, 不可替 Map 查找
- L463-479 `parsed.data.map(...)` 内 13 字段全用 `?? EMPTY_STRING` / `Number(...) ?? ZERO` 默认值, 风格统一无 if/else 嵌套
- L540-547 `parseTableFilename` 内 `if (!match) throw` — 同上单点

**5. 数组迭代替循环**: 无
- L463-479 `parsed.data.map((raw, idx) => ({...}))` 已用 map, 不需换
- 无 for / forEach / while 显式循环

**6. 预计减少**: 585 -> ~150 (主文件, 仅留 facade re-export), 拆分后单文件最大 ~138 行 (-74%)

**7. 骨架伪代码**:

- `pre-analysis-types.ts`:
```ts
// imports: 只列需要的 import
export interface PreAnalysisSummary;
export interface PreAnalysisOutputFile;
export type PreAnalysisTaskState;
export type PreAnalysisOverallStage;
export type PreAnalysisDetailStage;
export type PreAnalysisStageStatus;
export interface PreAnalysisStageItem;
export interface PreAnalysisStagesResponse;
export interface PreAnalysisRetryResponse;
export interface PreAnalysisTaskItem;
export interface PreAnalysisTaskDetail;
export interface PreAnalysisUploadResponse;
export interface PreAnalysisListResponse;
```

- `pre-analysis-config.ts`:
```ts
export interface TableExtractionConfig;
export interface ChapterExtractionConfig;
```

- `pre-analysis-tasks.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";
import { handleFetchError } from "@/lib/api/errors";
import type { PreAnalysisTaskDetail, PreAnalysisTaskItem, ... } from "./pre-analysis-types";
import type { TableExtractionConfig, ChapterExtractionConfig } from "./pre-analysis-config";

export const preAnalysisUpload: (file: File, config?: TableExtractionConfig, chapterConfig?: ChapterExtractionConfig) => Promise<PreAnalysisUploadResponse>;
export const listPreAnalysisTasks: (params?: { limit?: number; offset?: number }) => Promise<PreAnalysisListResponse>;
export const getPreAnalysisTask: (id: string) => Promise<PreAnalysisTaskDetail>;
export const downloadPreAnalysisZip: (id: string) => Promise<Blob>;
export const downloadPreAnalysisFile: (taskId: string, filename: string) => Promise<Blob>;
export const listPreAnalysisStages: (id: string) => Promise<PreAnalysisStagesResponse>;
export const retryPreAnalysisTask: (id: string) => Promise<PreAnalysisRetryResponse>;
```

- `pre-analysis-viewer-types.ts`:
```ts
export interface ChapterTreeNode;
export interface ChapterStructurePayload;
export interface FlaggedParagraphRow;
```

- `pre-analysis-viewer.ts`:
```ts
// imports: 只列需要的 import
import { parse } from "papaparse";
import { ROW_INDEX_BASE, ZERO, EMPTY_STRING } from "@/const";
import type { FlaggedParagraphRow, ChapterStructurePayload } from "./pre-analysis-viewer-types";

const mapFlaggedRow: (raw: Record<string, string>, idx: number) => FlaggedParagraphRow;
const assertChaptersArray: (parsed: unknown) => asserts parsed is ChapterStructurePayload;
const fetchPreAnalysisFile: (taskId: string, filename: string) => Promise<string>;
export const getPreAnalysisChapterStructure: (taskId: string) => Promise<ChapterStructurePayload>;
export const getPreAnalysisFlaggedParagraphs: (taskId: string) => Promise<FlaggedParagraphRow[]>;
```

- `pre-analysis-tables.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";
import type { TablePageItem, TablePageResponse, TablePagesResponse } from "./pre-analysis-viewer-types";

const TABLE_FILENAME_PATTERN: RegExp;
export const parseTableFilename: (filename: string) => { pageNumber: number; tableIndex: number };
export const getPreAnalysisTablePages: (taskId: string) => Promise<TablePagesResponse>;
export const getPreAnalysisTablePage: (taskId: string, pageNum: number) => Promise<TablePageResponse>;
```

---

### `lib/api/knowledge.ts` (502 行)

**1. 拆分点**:
- L20-22 3 个 import (KnowledgeSchema type / THREE / apiFetch) — 拆后多文件需分别 import
- L24-171 11 个 knowledge 域 interface (StatsResponse / DatasetRow / QAListResponse / RetrieveRecord / RetrieveResult / UploadResult / NodeRow / RelationRow / TripleRowInput / TriplesInput / TriplesResponse / BatchInput / BatchState) -> `knowledge-types.ts` (~140 行)
- L173-272 16 个 CRUD wrapper (createTriples / fetchBatchStatus / fetchDatasets / fetchHealth / fetchNodes / fetchRelations / fetchSchema / fetchSchemas / fetchSegments / fetchStats / retrieveQA / startBatch / uploadDocument) -> `knowledge-crud.ts` (~100 行)
- L273-454 (2026-07-01 markdown extract KG spec) 12 个 type + 6 个 wrapper + 2 helper (buildExportUrl / triggerBlobDownload) + triggerExportDownload -> `knowledge-extract.ts` (~180 行)
- L456-502 (2026-07-03) ExtractTaskRow / ExtractTaskList + fetchExtractTasks -> `knowledge-tasks.ts` (~46 行)

**2. 纯函数/hook 化**: 可拆
- L429-432 `buildExportUrl(args)` 已是 pure func (URL 拼接), 可独立单测
- L435-442 `triggerBlobDownload(blob, filename)` 已是 pure side-effect func (DOM 节点创建 + click), 可独立单测 + mock document
- L175-179 `createTriples` 已是 one-liner wrapper, 无业务逻辑可拆
- L239-244 `fetchStats` 内 `params.toString()` + `queryString = ""; if (qs) queryString = "?${qs}";` 三元表达改成 `?${qs}` 一行 (oxlint 禁嵌套三元, 现状已是 if/else 写法, 但变量 queryString 冗余)
- L494-501 `fetchExtractTasks` 内 URLSearchParams 构造已是标准 pattern, 无需拆

**3. 库替代**: ✅
- es-toolkit 已装 (package.json:62) — 不适用本文件 (无 pick/omit/chunk/groupBy 场景)
- react-use 已装 (package.json:72) — `useAsync` / `useMount` 不适用 (本文件全是一过式 fetch wrapper, 非 React hook)
- zod 已装 (package.json:80) — 本文件 type 字段都从后端响应来, 解析校验是 server action 责任, 不在前端重复
- 无 URLSearchParams 替代库 — es-toolkit 1.49 不带 URL util, 保留原生

**4. 对象替 if**: 无
- L239-244 `fetchStats` 内 `if (qs) { queryString = "?${qs}"; }` 三元表达式 (oxlint 禁嵌套三元, 现状 if/else 写法符合规范), 不构成 if/else 链, 不需替
- 无 `if (kind === "kg_extract") ... else if (...)` 这种 dispatch, 不需 Map

**5. 数组迭代替循环**: 无
- 全文件无 for / forEach / while
- L494-501 URLSearchParams set/get 是 builder pattern, 不算数组迭代

**6. 预计减少**: 502 -> ~100 (主文件, 仅 facade re-export), 拆分后单文件最大 ~180 行 (-80%)

**7. 骨架伪代码**:

- `knowledge-types.ts`:
```ts
// imports: 只列需要的 import
import type { KnowledgeSchema } from "@/lib/schema-types";

export interface StatsResponse;
export interface DatasetRow;
export interface QAListResponse;
export interface RetrieveRecord;
export interface RetrieveResult;
export interface UploadResult;
export interface NodeRow;
export interface RelationRow;
export interface TripleRowInput;
export interface TriplesInput;
export interface TriplesResponse;
export interface BatchInput;
export interface BatchState;
```

- `knowledge-crud.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";
import { THREE } from "@/const";
import type { KnowledgeSchema } from "@/lib/schema-types";
import type { ... } from "./knowledge-types";

export const createTriples: (input: TriplesInput, headers?: Record<string, string>) => Promise<TriplesResponse>;
export const fetchBatchStatus: (taskId: string) => Promise<BatchState>;
export const fetchDatasets: () => Promise<DatasetRow[]>;
export const fetchHealth: () => Promise<{ ok: boolean }>;
export const fetchNodes: (limit?: number) => Promise<NodeRow[]>;
export const fetchRelations: (limit?: number) => Promise<RelationRow[]>;
export const fetchSchema: (domain: string) => Promise<KnowledgeSchema>;
export const fetchSchemas: () => Promise<{ schemas: { name: string }[] }>;
export const fetchSegments: () => Promise<{ items: { id: string; content: string }[] }>;
export const fetchStats: (type?: string, domain?: string) => Promise<StatsResponse>;
export const retrieveQA: (question: string, datasetId: string, topK?: number) => Promise<RetrieveResult>;
export const startBatch: (input: BatchInput) => Promise<{ task_id: string }>;
export const uploadDocument: (file: File, datasetId: string) => Promise<UploadResult>;
```

- `knowledge-extract.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";
import type { ... } from "./knowledge-types";

export type DatasetEntry;
export type ExtractorInfo;
export type SplitterInfo;
export type ExtractTaskState;
export type ExtractPreviewEntity;
export type ExtractPreviewRelation;
export type ExtractPreview;
export type PatchItemInput;
export type ExtractUploadResult;
export const fetchExtractDatasets: () => Promise<DatasetEntry[]>;
export const fetchExtractors: () => Promise<ExtractorInfo[]>;
export const fetchSplitters: () => Promise<SplitterInfo[]>;
export const uploadExtractFile: (file: File, dataset: string) => Promise<ExtractUploadResult>;
export const startExtract: (req: {...}) => Promise<{ task_id: string; state: string }>;
export const fetchExtractTask: (taskId: string) => Promise<ExtractTaskState>;
export const fetchExtractPreview: (taskId: string, dataset: string) => Promise<ExtractPreview>;
export const patchExtractItems: (taskId: string, dataset: string, items: PatchItemInput[]) => Promise<{ updated: number }>;
export const commitExtract: (taskId: string, dataset: string) => Promise<{ success: number; failed: number; errors: string[] }>;
export type ExportArgs;
const buildExportUrl: (args: ExportArgs) => string;
const triggerBlobDownload: (blob: Blob, filename: string) => void;
export const triggerExportDownload: (args: ExportArgs) => Promise<void>;
```

- `knowledge-tasks.ts`:
```ts
// imports: 只列需要的 import
import { apiFetch } from "@/lib/api/config";

export type ExtractTaskRow;
export type ExtractTaskList;
export const fetchExtractTasks: (params: { kind: "kg_extract" | "kg_batch"; limit?: number; offset?: number }) => Promise<ExtractTaskList>;
```

---

### `lib/date.ts` (450 行)

**1. 拆分点**:
- L1-13 imports + L19 HOURS_PER_DAY 常量 (项目 const/index.ts:36 已有 HOURS_PER_DAY = 24) -> 删本地 HOURS_PER_DAY, 复用 const/
- L15-65 `DateInput` type + `toInstant` 输入归一化 + `InstantUnit` internal type -> `date-instant.ts` (~55 行)
- L66-90 `nowInstant` / `nowMs` / `nowIso` 3 个当前时间 -> `date-now.ts` (~30 行)
- L92-159 5 个 differenceIn (Milliseconds / Seconds / Minutes / Hours / Days) + `durationOf` internal -> `date-difference.ts` (~70 行)
- L161-227 5 个 add (Days / Hours / Minutes / Seconds / Milliseconds) + `shift` internal -> `date-add.ts` (~70 行)
- L229-270 3 个比较 (isAfter / isBefore / isEqual) + `instantOf` internal -> `date-compare.ts` (~45 行)
- L272-304 2 个格式化 (formatDate / formatDateTime) -> `date-format.ts` (~35 行)
- L306-356 2 个相对时间 (fmtRelativeTime / formatRelativeTime) -> `date-relative.ts` (~55 行)
- L358-450 4 个耗时格式化 (`MILLIS_PER_HOUR` / `MILLIS_PER_MINUTE` / `DURATION_DASH` / `tryParseMs` / `formatElapsedMs` / `formatDurationMs` / `formatRange`) -> `date-duration.ts` (~95 行)
- 主文件 `date.ts` 仅留 facade barrel re-export (~30 行)

**2. 纯函数/hook 化**: 可拆
- 所有 export 函数已是 pure (Temporal.Instant 输入 → 数值/字符串输出), 无 hook
- `toInstant` / `durationOf` / `shift` / `instantOf` / `tryParseMs` / `formatRange` 都是 internal helper, 已标注 @internal
- `nowInstant` / `nowMs` / `nowIso` 是当前时间 getter, 测试可注入 `Temporal.Now` mock (现 date.test.ts 用 Temporal.Now.instant() 真实值)

**3. 库替代**: ✅
- @js-temporal/polyfill 已装 (package.json:32) — 本文件核心依赖, 保留
- es-toolkit 已装 (package.json:62) — 不适用 (无 pick/omit 场景)
- date-fns — 项目无依赖 (CLAUDE.md 规定用 lib/date), 不引
- dayjs — 项目无依赖 (CLAUDE.md 禁止 moment, 同源不引 dayjs)
- react-use 已装 (package.json:72) — 不适用 (本文件全 pure func)
- zod 已装 (package.json:80) — 不适用 (无 input schema 校验)

**4. 对象替 if**: 部分可替
- L322-333 `fmtRelativeTime` 内 4 个 if-else 链 (`if (diff < SECONDS_PER_MINUTE) ... else if (diff < SECONDS_PER_HOUR) ... else if (diff < SECONDS_PER_DAY) ...`) — 经典档位查找, 可替 `const RELATIVE_THRESHOLDS: Array<{ max: number; unit: number; suffix: string }> = [...]` 然后 `find()`
- L345-355 `formatRelativeTime` 内 4 个 if-else 链 (同上), 同上可替
- L425-430 `formatDurationMs` 内 `if (end === null) { liveMs < MILLIS_PER_MINUTE ? ... : ... } else { formatRange(...) }` — 二分支 (end 是否 null) 不可替 Map
- L436-450 `formatRange` 内 4 个 if-else 链 (同上 ms 档位查找), 可替 `const DURATION_RANGES: Array<{ max: number; format: (ms: number) => string }> = [...]`

**5. 数组迭代替循环**: 无
- 全文件无 for / forEach / while
- `if-else` 链可用 `find` 替, 不算数组迭代

**6. 预计减少**: 450 -> ~120 (单文件 facade), 拆分后单文件最大 ~95 行 (-73%)

**7. 骨架伪代码**:

- `date.ts` (facade barrel):
```ts
// imports: 只列需要的 import
export type { DateInput } from "./date-instant";
export { toInstant } from "./date-instant";
export { nowInstant, nowMs, nowIso } from "./date-now";
export {
  differenceInMilliseconds,
  differenceInSeconds,
  differenceInMinutes,
  differenceInHours,
  differenceInDays,
} from "./date-difference";
export { addDays, addHours, addMinutes, addSeconds, addMilliseconds } from "./date-add";
export { isAfter, isBefore, isEqual } from "./date-compare";
export { formatDate, formatDateTime } from "./date-format";
export { fmtRelativeTime, formatRelativeTime } from "./date-relative";
export { formatElapsedMs, formatDurationMs } from "./date-duration";
```

- `date-instant.ts`:
```ts
// imports: 只列需要的 import
import { Temporal } from "@js-temporal/polyfill";
export type DateInput = string | number | Date | Temporal.Instant;
type InstantUnit = ...;
export const toInstant: (input: DateInput) => Temporal.Instant;
```

- `date-difference.ts`:
```ts
import { toInstant } from "./date-instant";
import { HOURS_PER_DAY } from "@/const";
const durationOf: (later: DateInput, earlier: DateInput, largestUnit: InstantUnit) => Temporal.Duration;
export const differenceInMilliseconds: (later: DateInput, earlier: DateInput) => number;
export const differenceInSeconds: (later: DateInput, earlier: DateInput) => number;
export const differenceInMinutes: (later: DateInput, earlier: DateInput) => number;
export const differenceInHours: (later: DateInput, earlier: DateInput) => number;
export const differenceInDays: (later: DateInput, earlier: DateInput) => number;
```

- `date-relative.ts`:
```ts
import { nowMs } from "./date-now";
import { MS_PER_SECOND, SECONDS_PER_MINUTE, SECONDS_PER_HOUR, SECONDS_PER_DAY, HOURS_PER_DAY, ZERO } from "@/const";
const RELATIVE_THRESHOLDS: Array<{ max: number; divisor: number; suffix: string }>;
export const fmtRelativeTime: (epoch: number, now?: number) => string;
export const formatRelativeTime: (timestamp: number) => string;
```

- `date-duration.ts`:
```ts
import { nowMs } from "./date-now";
import { MS_PER_SECOND, SECONDS_PER_MINUTE, SECONDS_PER_HOUR, ZERO } from "@/const";
const MILLIS_PER_HOUR: number;
const MILLIS_PER_MINUTE: number;
const DURATION_DASH: string;
const tryParseMs: (iso: string) => number;
const DURATION_RANGES: Array<{ max: number; format: (ms: number) => string }>;
const formatRange: (ms: number) => string;
export const formatElapsedMs: (ms: number) => string;
export const formatDurationMs: (start: string, end: string | null) => string;
```

---

### `lib/chat/use-chat-state.ts` (331 行)

**1. 拆分点**:
- L1-29 imports + 3 个本地常量 (DRAFT_KEY / ZERO_LEN / FIRST_INDEX) -> 顶部 imports 不拆, DRAFT_KEY 移到 const/
- L30-78 `ChatShellUiState` interface + `useChatShellUiState` hook (5 个 useState + useLocalStorage) -> `use-chat-shell-ui-state.ts` (~60 行)
- L80-136 `ServerDataParams` / `ServerData` interface + `serverConvToClient` helper + `useServerData` hook (5 个 TanStack Query) -> `use-server-data.ts` (~75 行)
- L138-250 `ChatShellChatParams` / `ChatShellChat` interface + `buildInitialMessages` helper + `useChatShellChat` hook (useConversation + useChatWithPersistence + UIMessage → flat Message 转换) -> `use-chat-shell-chat.ts` (~130 行)
- L252-266 兼容旧 API (`useChatShellState` deprecated + `removeConvLocal`) -> 留主文件或 `use-chat-state-compat.ts` (~30 行)
- L268-331 4 个 helper + `deleteConversationLocal` (`createLocalConv` / `pickNextConvId` / `CreateConvResult` interface / `doCreateServerConv` / `deleteConversationLocal`) -> `use-chat-state-helpers.ts` (~75 行)

**2. 纯函数/hook 化**: 可拆
- L103-109 `serverConvToClient` 已是 pure func (字段 mapping + toInstant), 可独立单测
- L166-191 `buildInitialMessages` 已是 pure func (3 个 if 分支), 可独立单测, 无副作用
- L275-285 `createLocalConv` 不是 pure (写 IDB via upsertConversation), 标 client-bff
- L312-323 `doCreateServerConv` 不是 pure (try/catch + mutateAsync), 标 client-bff
- L329-331 `deleteConversationLocal` 不是 pure (调 storageDelete 写 IDB), 标 client-bff

**3. 库替代**: ✅
- react-use 已装 (package.json:72) — L60 已用 `useLocalStorage` (项目既定), 保留
- zustand 已装 (package.json:81) — 不适用 (本文件无全局 store)
- zod 已装 (package.json:80) — 不适用 (无 input schema)
- es-toolkit 已装 (package.json:62) — `pick` 可替 `serverConvToClient` 内 `{ id, title, message_count, created_at, updated_at }` 字段 pick, 但只 5 字段, 显式 mapping 可读性更好, 不强推
- @tanstack/react-query 已装 (package.json:53) — 已用 (L116 `useConversations` 等)

**4. 对象替 if**: 部分可替
- L176-190 `buildInitialMessages` 内 `if (!isAccount || !currentDetail?.messages) return initialMessages; if (initialMessages.length > ZERO_LEN) return initialMessages; return ...map(...)` — 3 分支 (guard return + guard return + map), 前 2 个 guard return 不可替 (短路逻辑), 不构成 dispatch
- L181-183 `if (msg.role !== "system") { ({ role } = msg); }` — 1 行 if-else (三元违规), 简化为 `const role = msg.role === "system" ? "user" : msg.role;` 1 行

**5. 数组迭代替循环**: 部分可拆
- L224-237 `flatMessages = messages.map((uimsg) => {...})` 已用 map, 内部 `parts.filter(...).map(...).join("")` 已链式, 无显式循环
- L179-190 `currentDetail.messages.map((msg) => {...})` 已用 map
- 无 for / forEach / while

**6. 预计减少**: 331 -> ~75 (单文件 facade + 兼容), 拆分后单文件最大 ~130 行 (-77%)

**7. 骨架伪代码**:

- `use-chat-shell-ui-state.ts`:
```ts
// imports: 只列需要的 import
import { useState } from "react";
import { useLocalStorage } from "react-use";
import { DRAFT_KEY } from "@/const";

export interface ChatShellUiState;
export const useChatShellUiState: () => ChatShellUiState;
```

- `use-server-data.ts`:
```ts
// imports: 只列需要的 import
import { useConversations, useCreateConversation, useDeleteConversation, useRenameConversation, useAppendMessage } from "@/lib/chat/api";
import { computeEffectiveConversations } from "@/lib/chat/chat-utils";
import { toInstant } from "@/lib/date";
import type { Conversation } from "@/lib/chat/types";

export interface ServerDataParams;
export interface ServerData;
const serverConvToClient: (server: ServerConversation) => Conversation;
export const useServerData: (params: ServerDataParams) => ServerData;
```

- `use-chat-shell-chat.ts`:
```ts
// imports: 只列需要的 import
import { useConversation } from "@/lib/chat/api";
import { useChatWithPersistence } from "@/lib/chat/use-chat-with-persistence";
import { nowMs, toInstant } from "@/lib/date";
import type { ChatFile, Conversation, Message } from "@/lib/chat/types";
import type { ServerConversationDetail } from "@/lib/chat/api";

export interface ChatShellChatParams;
export interface ChatShellChat;
const buildInitialMessages: (isAccount: boolean, currentDetail: ServerConversationDetail | undefined, initialMessages: Message[]) => Message[];
export const useChatShellChat: (params: ChatShellChatParams) => ChatShellChat;
```

- `use-chat-state-helpers.ts`:
```ts
// imports: 只列需要的 import
import { useCreateConversation } from "@/lib/chat/api";
import { deleteConversation as storageDelete, upsertConversation } from "@/lib/chat/storage";
import { getNextConversationId, newId } from "@/lib/chat/chat-utils";
import { log } from "@/lib/log";
import { nowMs } from "@/lib/date";
import type { Conversation } from "@/lib/chat/types";
import type { ChatShellUiState } from "./use-chat-shell-ui-state";

const TITLE_LEN: number;
const FIRST_INDEX: number;
export const createLocalConv: (text: string) => Conversation;
export const pickNextConvId: (effectiveConversations: Conversation[], deletedId: string) => string | null;
export interface CreateConvResult;
export const doCreateServerConv: (args: {...}) => Promise<CreateConvResult>;
export const deleteConversationLocal: (targetId: string) => void;
```

---

## 汇总

| 文件 | 当前行数 | 拆分目标 | 拆分后最大单文件 | 减幅 |
|------|----------|----------|------------------|------|
| lib/api/pre-analysis.ts | 585 | 5 文件 | ~138 行 | -74% |
| lib/api/knowledge.ts | 502 | 4 文件 | ~180 行 | -80% |
| lib/date.ts | 450 | 8 文件 + 1 facade | ~95 行 | -73% |
| lib/chat/use-chat-state.ts | 331 | 4 文件 + 1 compat | ~130 行 | -77% |
| **总计** | **1868** | **~22 文件** | **~180 行 (最大)** | **平均 -76%** |

### 通用约束遵守

- 所有拆分都保持 `export const` 箭头函数, 无 function 声明
- 所有 import 按字母排序 (oxlint sort-imports)
- 所有魔法数字提 const (DRAFT_KEY / ZERO / EMPTY_STRING / ROW_INDEX_BASE / TITLE_LEN / FIRST_INDEX / HOURS_PER_DAY 复用 const/index.ts)
- 所有文案不动 i18n (本 4 文件无 t() 调用)
- 无 emoji, 无 lodash / moment / dayjs / ahooks / nuqs (项目零依赖, package.json 验证)

### 库替代实施注意

- date.ts L19 `HOURS_PER_DAY` 与 const/index.ts:36 重复, 拆 date-difference.ts 时直接 import const/index.ts 的
- date.ts L361-364 `MILLIS_PER_HOUR` / `MILLIS_PER_MINUTE` 是 const/index.ts `ONE_HOUR_MS` / `ONE_MINUTE_MS` 的等价值, 拆 date-duration.ts 时复用 const/index.ts
- pre-analysis.ts `handleError` 复用 lib/api/errors.ts 的 `handleFetchError`, 删本地实现
- date.ts 4 个 if-else 链 (fmtRelativeTime / formatRelativeTime / formatRange / formatDurationMs end==null 分支) 用 `RELATIVE_THRESHOLDS` / `DURATION_RANGES` 数组 find 替, 但 end==null 是 2 分支不可替 Map

### 兼容旧 API 注意

- use-chat-state.ts L258 `useChatShellState` deprecated 标保留, T7 后由 ChatShell 内部 handler 替代, 拆后留 compat 文件
- use-chat-state.ts L264 `removeConvLocal` deprecated 同上