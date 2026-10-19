// pre-analysis 端点 API wrapper (2026-07-02 PR4, 2026-07-03 加 stages/retry, 2026-07-09 加 viewer helpers)
//
// 类型定义跟后端 PreAnalysisTaskItem / PreAnalysisOutputFile 1:1 对齐.
// 后端返回 snake_case (跟 storage JSON 一致), 这里同样 snake_case.

import { parse } from "papaparse";

import { apiFetch } from "./config";

/**
 * 预分析总结 (章节/表格/标记段落/耗时/跨页候选数)
 * @shared
 */
export interface PreAnalysisSummary {
  total_chapters: number;
  total_tables: number;
  total_flagged_paragraphs: number;
  elapsed_ms: number;
  cross_page_candidates: number;
}

/**
 * 预分析输出产物元信息 (类型/文件名/URI/字节数)
 * @shared
 */
export interface PreAnalysisOutputFile {
  kind: "chapter_structure" | "flagged_paragraphs" | "table" | "index";
  filename: string;
  uri: string;
  size_bytes: number;
}

/**
 * 预分析任务状态枚举
 * @shared
 */
export type PreAnalysisTaskState = "pending" | "running" | "completed" | "failed";

// (2026-07-03) overall/detail stage — 弹框 5 阶段 + done 统一
/**
 * 预分析总体阶段枚举 (5 步 + done)
 * @shared
 */
export type PreAnalysisOverallStage =
  | "prepare_input"
  | "extract_chapters"
  | "extract_tables"
  | "extract_flagged"
  | "write_outputs"
  | "done";
/**
 * 预分析细节阶段枚举 (不含 done)
 * @shared
 */
export type PreAnalysisDetailStage = Exclude<PreAnalysisOverallStage, "done">;
/**
 * 预分析阶段状态枚举
 * @shared
 */
export type PreAnalysisStageStatus = "pending" | "started" | "completed" | "failed" | "skipped";

/**
 * 预分析单阶段详情 (阶段名 / 状态 / 进度 / 起止时间 / 消息)
 * @shared
 */
export interface PreAnalysisStageItem {
  stage: PreAnalysisDetailStage;
  status: PreAnalysisStageStatus;
  progress: number; // 0-100
  started_at: string;
  finished_at: string | null;
  message: string | null;
}

/**
 * 预分析阶段列表响应
 * @shared
 */
export interface PreAnalysisStagesResponse {
  stages: PreAnalysisStageItem[];
}

/**
 * 预分析重试响应 (task_id + state=pending)
 * @shared
 */
export interface PreAnalysisRetryResponse {
  task_id: string;
  state: "pending";
}

/**
 * 预分析任务列表项 (不含 output_files, 详情用 PreAnalysisTaskDetail)
 * @shared
 */
export interface PreAnalysisTaskItem {
  id: string;
  state: PreAnalysisTaskState;
  user_hash: string;
  pdf_filename: string;
  pdf_uri: string;
  started_at: string;
  finished_at: string | null;
  current_stage: PreAnalysisOverallStage | null; // (2026-07-03) 新增
  summary: PreAnalysisSummary;
  error: string | null;
  /** (2026-07-06) 执行快照 { table_backend, table_params, ... } */
  task_config_json: Record<string, unknown>;
}

/**
 * 预分析任务详情 (含产物清单, 详情页用)
 * @shared
 */
export interface PreAnalysisTaskDetail extends PreAnalysisTaskItem {
  output_files: PreAnalysisOutputFile[];
}

/**
 * 预分析上传响应 (task_id + state + pdf_filename)
 * @shared
 */
export interface PreAnalysisUploadResponse {
  task_id: string;
  state: "pending";
  pdf_filename: string;
}

/**
 * 预分析任务列表响应
 * @shared
 */
export interface PreAnalysisListResponse {
  tasks: PreAnalysisTaskItem[];
}

/**
 * 解析后端错误响应 → 抛 Error.
 *
 * @param resp fetch Response 对象 (非 2xx).
 * @returns never (抛 Error 终止).
 */
const handleError = async (resp: Response): Promise<never> => {
  const body = await resp.json().catch(() => ({ detail: "未知错误" }));
  throw new Error(body.detail ?? `${resp.status} ${resp.statusText}`);
};

/**
 * 表格提取配置 (2026-07-06 新增, 后端 3 种 backend 可选)
 * @shared
 */
export interface TableExtractionConfig {
  /** 后端名: pymupdf (默认) | camelot | pdfplumber */
  backend: "pymupdf" | "camelot" | "pdfplumber";
  /** backend-specific 参数 (e.g. camelot: { flavor, edge_tol, row_tol }) */
  params: Record<string, unknown>;
}

/**
 * (2026-07-09 PDF 章节树状化+LLM增强) 章节提取配置.
 *
 * 字段对齐后端 `ChapterExtractionConfig` (Pydantic):
 * - chapter_max_level_for_display: 显示的最大章节层级 (1-6)
 * - enable_llm_refinement: 是否启用 LLM 增强 (章节识别 + 摘要)
 * - llm_provider: LLM provider (openai | ollama)
 *
 * @shared
 */
export interface ChapterExtractionConfig {
  /** 显示的最大章节层级 (1-6, 默认 3 = 显示 1.x / 1.x.x 两级) */
  chapter_max_level_for_display?: number;
  /** 是否启用 LLM 增强 (false = 纯 OCR/字体聚类识别) */
  enable_llm_refinement?: boolean;
  /** LLM provider: openai (默认) | ollama */
  llm_provider?: "openai" | "ollama";
}

/**
 * 上传 PDF 文件, 触发后台预分析.
 *
 * @param file PDF 文件.
 * @param config 表格后端配置 (默认 pymupdf + 空 params).
 * @param chapterConfig (2026-07-09) 章节配置 (章节层级 + LLM 开关), 默认走后端 default.
 * @returns {task_id, state=pending, pdf_filename}.
 * @throws Error 4xx/5xx 时 handleError 抛.
 */
export const preAnalysisUpload = async (
  file: File,
  config: TableExtractionConfig = { backend: "pymupdf", params: {} },
  chapterConfig?: ChapterExtractionConfig,
): Promise<PreAnalysisUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("table_backend", config.backend);
  formData.append("table_params", JSON.stringify(config.params ?? {}));
  // (2026-07-09) 章节配置 JSON 字段, 后端 ChapterExtractionConfig.from_form 解析.
  formData.append("chapter_config_json", JSON.stringify(chapterConfig ?? {}));
  const resp = await fetch("/api/pre-analysis/upload", {
    method: "POST",
    body: formData,
    credentials: "include",
  });
  if (!resp.ok) {
    await handleError(resp);
  }
  return (await resp.json()) as PreAnalysisUploadResponse;
};

/**
 * 列 super_admin 当前用户的预分析 task 列表 (按 started_at DESC).
 *
 * @param params 可选 limit/offset 分页.
 * @returns {tasks: PreAnalysisTaskItem[]}.
 * @throws Error 鉴权失败 / 服务异常.
 */
export const listPreAnalysisTasks = async (params?: {
  limit?: number;
  offset?: number;
}): Promise<PreAnalysisListResponse> => {
  const search = new URLSearchParams();
  if (params?.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  if (params?.offset !== undefined) {
    search.set("offset", String(params.offset));
  }
  const qs = search.toString();
  const resp = await apiFetch<PreAnalysisListResponse>(
    `/api/pre-analysis/tasks${qs ? `?${qs}` : ""}`,
    { credentials: "include" },
  );
  return resp;
};

/**
 * 查单条预分析 task 详情 (元数据 + 产物清单).
 *
 * @param id task_id (后端生成, 前端跳转用).
 * @returns PreAnalysisTaskDetail.
 * @throws Error 任务不存在 → 404.
 */
export const getPreAnalysisTask = async (id: string): Promise<PreAnalysisTaskDetail> => {
  const resp = await apiFetch<PreAnalysisTaskDetail>(`/api/pre-analysis/tasks/${id}`, {
    credentials: "include",
  });
  return resp;
};

/**
 * 下载预分析产物 zip 包.
 *
 * @param id task_id.
 * @returns Blob (application/zip). 调用方负责触发浏览器下载 (createObjectURL + <a download>).
 * @throws Error 任务未 completed 或不存在.
 */
export const downloadPreAnalysisZip = async (id: string): Promise<Blob> => {
  // 不能用 apiFetch (它会读 body 解析 JSON); 直接 fetch + blob()
  const resp = await fetch(`/api/pre-analysis/tasks/${id}/download`, {
    credentials: "include",
  });
  if (!resp.ok) {
    await handleError(resp);
  }
  return await resp.blob();
};

/**
 * (2026-07-06) 下载单个预分析产物文件 — fetch BFF → blob → 触发浏览器下载.
 *
 * @param taskId 预分析任务 ID
 * @param filename 产物文件名 (e.g. "chapters.json")
 * @returns Blob
 * @throws Error 404 或服务异常
 */
export const downloadPreAnalysisFile = async (taskId: string, filename: string): Promise<Blob> => {
  const resp = await fetch(
    `/api/pre-analysis/tasks/${taskId}/files/${encodeURIComponent(filename)}`,
    {
      credentials: "include",
    },
  );
  if (!resp.ok) {
    await handleError(resp);
  }
  return await resp.blob();
};

/**
 * (2026-07-03) 查 task 的所有 detail stage (5 个: prepare_input / extract_chapters / extract_tables / extract_flagged / write_outputs).
 *
 * @param id task_id
 * @returns {stages: PreAnalysisStageItem[]}
 * @throws Error 任务不存在 → 404
 */
export const listPreAnalysisStages = async (id: string): Promise<PreAnalysisStagesResponse> => {
  const resp = await apiFetch<PreAnalysisStagesResponse>(`/api/pre-analysis/tasks/${id}/stages`, {
    credentials: "include",
  });
  return resp;
};

/**
 * (2026-07-03) 重试失败 task → state 转 pending + 后台重新跑 pre-analysis.
 *
 * @param id task_id
 * @returns {task_id, state: "pending"}
 * @throws Error 任务不存在 → 404 / 任务非 failed → 409
 */
export const retryPreAnalysisTask = async (id: string): Promise<PreAnalysisRetryResponse> => {
  const resp = await apiFetch<PreAnalysisRetryResponse>(`/api/pre-analysis/tasks/${id}/retry`, {
    method: "POST",
    credentials: "include",
  });
  return resp;
};

// ===== (2026-07-09) 章节树 + 标记段落 viewer helpers =====

const CHAPTER_JSON_FILENAME = "chapter_structure.json";
const FLAG_CSV_FILENAME = "flagged_paragraphs.csv";

/** CSV 字段缺失/空值时的数字兜底 */
const ZERO = 0;
/** 字段缺失/空值时的字符串兜底 */
const EMPTY_STRING = "";
/** row_index 起始值 (1-based) */
const ROW_INDEX_BASE = 1;

/**
 * (2026-07-09) 单章节节点 — 树状结构, 字段对齐后端 chapter_structure.json.
 *
 * @property id 章节 ID (后端生成, e.g. "ch-1-2")
 * @property level 层级 (1 = 章, 2 = 节, 3 = 小节, ...)
 * @property title 标题
 * @property page_start 起始页
 * @property page_end 结束页
 * @property children 子章节
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
 * (2026-07-09) chapter_structure.json 顶层结构.
 *
 * @property max_level 最大章节层级 (1-6)
 * @property total_pages PDF 总页数
 * @property total_chapters 章节数 (含子章节)
 * @property extracted_at 提取时间 (ISO 8601)
 * @property toc_source TOC 来源 (pdf_outline / toc_pages / llm_refined / empty)
 * @property llm_summary_enabled 是否启用 LLM 摘要
 * @property chapters L1 章节列表
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
 * (2026-07-09) flagged_paragraphs.csv 单行 — 强类型版本 (Number/Boolean 转换).
 *
 * @property row_index 重排后的行号 (1-based, 按 CSV 顺序)
 * @property page 所在页码
 * @property section 所在章节 (e.g. "2.1")
 * @property text 段落原文
 * @property rule_categories 命中的规则类别 (逗号分隔)
 * @property density 密度分数
 * @property is_dense 是否密集
 * @property raw_density 原始密度
 * @property weighted_density 加权密度
 * @property safe_hits 安全命中数
 * @property rec_hits 推荐命中数
 * @property lemmas 词形还原结果 (分号分隔)
 * @property token_count token 数
 * @property language 语言
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
 * (2026-07-09) 拉取预分析产物文件原文 (text 形式, 跟 downloadPreAnalysisFile 的 blob 形式互补).
 *
 * 后端 flagged_paragraphs.csv 接口 Content-Type 误为 application/json (已知后端 bug),
 * 这里直接用 resp.text() 不依赖 Content-Type 解析, 避免 papaparse 拿到 JSON wrapper 报错.
 *
 * @param taskId 预分析任务 ID
 * @param filename 产物文件名
 * @returns 原始文本
 * @throws Error 4xx/5xx 时 handleError 抛
 */
const fetchPreAnalysisFile = async (taskId: string, filename: string): Promise<string> => {
  const resp = await fetch(
    `/api/pre-analysis/tasks/${taskId}/files/${encodeURIComponent(filename)}`,
    {
      credentials: "include",
    },
  );
  if (!resp.ok) {
    await handleError(resp);
  }
  return await resp.text();
};

/**
 * (2026-07-09) 拉取 chapter_structure.json → 解析成强类型结构.
 *
 * @param taskId 预分析任务 ID
 * @returns ChapterStructurePayload (含递归 children)
 * @throws Error chapters 字段缺失/非数组时抛 "chapter_structure.json: 'chapters' field is not an array"
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
 * (2026-07-09) 拉取 flagged_paragraphs.csv → 解析成强类型行数组.
 *
 * 使用 papaparse 的 header mode + skipEmptyLines, 数值字段 Number() 强转, is_dense
 * 接受 "True"/"true" (其他都归 false, 含空字符串).
 * row_index 按返回顺序重排 (1, 2, 3, ...), 不信 CSV 自带字段 (CSV 导出 index 不可靠).
 *
 * @param taskId 预分析任务 ID
 * @returns FlaggedParagraphRow[] (按 CSV 顺序)
 * @throws Error 4xx/5xx 时 handleError 抛
 */
export const getPreAnalysisFlaggedParagraphs = async (
  taskId: string,
): Promise<FlaggedParagraphRow[]> => {
  const text = await fetchPreAnalysisFile(taskId, FLAG_CSV_FILENAME);
  const parsed = parse<Record<string, string>>(text, { header: true, skipEmptyLines: true });
  return parsed.data.map((raw, idx) => ({
    row_index: idx + ROW_INDEX_BASE,
    matched_keywords: raw["matched_keywords"] ?? EMPTY_STRING,
    page: Number(raw["page"] ?? ZERO),
    section: raw["section"] ?? EMPTY_STRING,
    text: raw["text"] ?? EMPTY_STRING,
    rule_categories: raw["rule_categories"] ?? EMPTY_STRING,
    density: Number(raw["density"] ?? ZERO),
    is_dense: raw["is_dense"] === "True" || raw["is_dense"] === "true",
    raw_density: Number(raw["raw_density"] ?? ZERO),
    weighted_density: Number(raw["weighted_density"] ?? ZERO),
    safe_hits: Number(raw["safe_hits"] ?? ZERO),
    rec_hits: Number(raw["rec_hits"] ?? ZERO),
    lemmas: raw["lemmas"] ?? EMPTY_STRING,
    token_count: Number(raw["token_count"] ?? ZERO),
    language: raw["language"] ?? EMPTY_STRING,
  }));
};

// ===== (2026-07-09) 表格 viewer types + helpers =====

/**
 * 表格页列表响应.
 * @property pages 有表格的 PDF 页号数组 (升序)
 * @property total 表格文件总数 (含同页多张)
 */
export interface TablePagesResponse {
  pages: number[];
  total: number;
}

/**
 * 单张表格的解析数据 (来自后端 csv.DictReader).
 * @property table_index 该页内的表索引 (从 1 开始)
 * @property filename 产物文件名 (e.g. "tables/page-9-table-1.csv")
 * @property size_bytes CSV 字节数
 * @property columns 表头列名 (从 CSV 第一行读)
 * @property rows 数据行 (Record<column_name, value>)
 */
export interface TablePageItem {
  table_index: number;
  filename: string;
  size_bytes: number;
  columns: string[];
  rows: Record<string, string>[];
}

/**
 * 指定页的表格数据响应.
 * @property page PDF 页号
 * @property tables 该页所有表格 (按 table_index 升序)
 */
export interface TablePageResponse {
  page: number;
  tables: TablePageItem[];
}

/** 正则匹配 tables/page-{N}-table-{M}.csv 文件名. */
const TABLE_FILENAME_PATTERN = /^tables\/page-(?<page>\d+)-table-(?<tableIndex>\d+)\.csv$/;

/** 正则 match 的 capture group 名索引 (用于 named groups). */
const PAGE_CAPTURE_INDEX = 1;
const TABLE_INDEX_CAPTURE_INDEX = 2;

/**
 * 从表格 CSV 文件名提取页号和表索引.
 * 跟后端 `parse_table_filename` 严格对齐 (router.py table_view.py).
 *
 * @param filename 产物文件名 (e.g. "tables/page-9-table-1.csv")
 * @returns `{ pageNumber, tableIndex }`
 * @throws 文件名不符格式时抛错
 * @shared
 */
export const parseTableFilename = (
  filename: string,
): { pageNumber: number; tableIndex: number } => {
  const match = TABLE_FILENAME_PATTERN.exec(filename);
  if (!match) {
    throw new Error(`Invalid table filename: ${filename} (expected tables/page-{N}-table-{M}.csv)`);
  }
  return {
    pageNumber: Number(match[PAGE_CAPTURE_INDEX]),
    tableIndex: Number(match[TABLE_INDEX_CAPTURE_INDEX]),
  };
};

/**
 * 查询任务的有表格页号列表 (用于前端 pagination).
 * BFF: GET /api/pre-analysis/tasks/{taskId}/tables/pages.
 *
 * @param taskId 预分析任务 ID
 * @returns `{ pages, total }`
 * @throws 4xx/5xx 时 handleError 抛
 * @client-bff
 */
export const getPreAnalysisTablePages = async (taskId: string): Promise<TablePagesResponse> => {
  const resp = await apiFetch<TablePagesResponse>(
    `/api/pre-analysis/tasks/${encodeURIComponent(taskId)}/tables/pages`,
    { credentials: "include" },
  );
  return resp;
};

/**
 * 查询指定 PDF 页的表格数据 (含 columns + rows JSON, 后端已 parse).
 * BFF: GET /api/pre-analysis/tasks/{taskId}/tables/page/{pageNum}.
 *
 * @param taskId 预分析任务 ID
 * @param pageNum PDF 页号 (1-based)
 * @returns `{ page, tables: TablePageItem[] }`
 * @throws 4xx/5xx 时 handleError 抛 (404 表示该页无表格)
 * @client-bff
 */
export const getPreAnalysisTablePage = async (
  taskId: string,
  pageNum: number,
): Promise<TablePageResponse> => {
  const resp = await apiFetch<TablePageResponse>(
    `/api/pre-analysis/tasks/${encodeURIComponent(taskId)}/tables/page/${pageNum}`,
    { credentials: "include" },
  );
  return resp;
};
