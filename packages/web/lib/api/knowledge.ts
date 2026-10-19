// 知识库业务客户端 (2026-06-10)
// 直连 FastAPI (统计/列表/CRUD) 或 走 BFF (multipart / Dify 调用 / 任务管理)
// (2026-06-12) 删 createQA / commitDocuments / fetchQADocuments / qaListUrl / QAListResponse:
//   这些 wrapper 对应的 BFF /api/knowledge/qa, /api/knowledge/documents/commit 已删,
//   改走 server action / RSC 直调 DifyDatasets. 客户端不再 fetch.
// (2026-06-14) 全部 fetch 改走 ./config.apiFetch() 统一封装, 不再手写 API_BASE / authHeaders / try/catch
//
// ============================================================
// 调用边界 (calling-boundary, 2026-06-19 audit)
// ============================================================
// 标注约定 (跟 lib/api/ 全局对齐):
//   - `@client-bff`    浏览器端调用, 必须从 'use client' 组件用;
//                       走 Next.js BFF (专用 /api/knowledge/* route), cookie 自动带.
//   - `@server-only`   仅 RSC / server action / route.ts 可用, 必须显式传 `headers` (auth token).
//                       直连 FastAPI, 绕过 BFF.
//   - `@shared`        浏览器或 server 都可用. 浏览器走 BFF catch-all, server 直连 FastAPI.
// 关键点: 本文件多数函数走 /api/kg/* (无专用 BFF, 走 [...path] catch-all).
//   在浏览器 = catch-all 代理; 在 server = 直连 FastAPI. 所以标 `@shared`.
// /api/knowledge/* (batch / documents/upload / qa/retrieve) 走专用 BFF, 标 `@client-bff`.
import type { KnowledgeSchema } from "@/lib/schema-types";
import { THREE } from "@/const";
import { apiFetch } from "./config";

/**
 * 统计响应 (Neo4j 节点/关系数 + Dify 数据集/文档数)
 * @shared
 */
export interface StatsResponse {
  neo4j: { nodes: number; relations: number };
  dify: { datasets: number; documents: number };
}

/**
 * Dify 数据集行
 * @shared
 */
export interface DatasetRow {
  id: string;
  name: string;
  description?: string;
  document_count?: number;
  word_count?: number;
}

// (2026-06-12) QAListResponse 仍 export — RSC page.tsx / DatasetDocumentsTable 还要用.
// 但 createQA / commitDocuments / fetchQADocuments / qaListUrl 的 client HTTP wrapper 删了
// (改成 server action / RSC 直调 DifyDatasets).
/**
 * QA 列表响应 (RSC page.tsx / DatasetDocumentsTable 用)
 * @shared
 */
export interface QAListResponse {
  items: {
    id: string;
    question: string;
    answer: string;
    name: string;
    indexing_status: string;
  }[];
}

/**
 * 检索结果单条记录
 * @shared
 */
export interface RetrieveRecord {
  content: string;
  score: number;
  document_name: string;
}

/**
 * 检索结果响应
 * @shared
 */
export interface RetrieveResult {
  records: RetrieveRecord[];
}

/**
 * 文档上传响应
 * @shared
 */
export interface UploadResult {
  document_id: string;
}

/**
 * Neo4j 节点行
 * @shared
 */
export interface NodeRow {
  id: string;
  business_id: string;
  name: string;
  label: string;
  props: Record<string, unknown>;
}

/**
 * Neo4j 关系行
 * @shared
 */
export interface RelationRow {
  src: string;
  src_label: string;
  src_name: string;
  src_business_id: string;
  type: string;
  dst: string;
  dst_label: string;
  dst_name: string;
  dst_business_id: string;
  props: Record<string, unknown>;
}

/**
 * 三元组单行输入
 * @shared
 */
export interface TripleRowInput {
  from_label: string;
  from_key: string;
  from_value: string;
  rel_type: string;
  to_label: string;
  to_key: string;
  to_value: string;
  properties: Record<string, unknown>;
}

/**
 * 三元组批量输入
 * @shared
 */
export interface TriplesInput {
  rows: TripleRowInput[];
}

/**
 * 三元组批量提交响应 (成功/失败计数 + 错误列表)
 * @shared
 */
export interface TriplesResponse {
  success: number;
  failed: number;
  errors: string[];
}

/**
 * 后台批量任务输入
 * @shared
 */
export interface BatchInput {
  dataset_id: string;
  items: { target: "dify" | "neo4j"; type: string; payload: Record<string, unknown> }[];
}

/**
 * 后台批量任务状态
 * @shared
 */
export interface BatchState {
  task_id: string;
  state: string;
  total: number;
  processed: number;
  success: number;
  failed: number;
  errors: string[];
}

/** 批量提交三元组到 Neo4j — 直连 FastAPI */
/** @shared */
export const createTriples = (
  input: TriplesInput,
  headers?: Record<string, string>,
): Promise<TriplesResponse> =>
  apiFetch<TriplesResponse>("/api/kg/triples", { body: input, headers, method: "POST" });

/** 查询后台批量任务进度 — 走 BFF (in-memory task map) */
/** @client-bff */
export const fetchBatchStatus = (taskId: string): Promise<BatchState> =>
  apiFetch<BatchState>(`/api/knowledge/batch?task_id=${encodeURIComponent(taskId)}`);

/**
 * 数据集列表 (Dify datasets) — 后端透传 Dify 包装 { data, has_more, total, limit, page }.
 * (2026-06-15) 改: 内部 .then(r => r.data) 拆包装, 调用方拿裸数组, 跟 DifyDatasets.listDatasets 一致.
 * 这样消除 DatasetSwitcher 那个 (data as { data?: Dataset[] } | undefined)?.data ?? [] shim.
 */
/** @shared */
export const fetchDatasets = async (): Promise<DatasetRow[]> => {
  const res = await apiFetch<{ data?: DatasetRow[] }>("/api/kg/datasets");
  return res.data ?? [];
};

/** Dify 监控检查 */
/** @shared */
export const fetchHealth = (): Promise<{ ok: boolean }> =>
  apiFetch<{ ok: boolean }>("/api/kg/health");

/** 节点列表 (Neo4j) */
/** @shared */
// oxlint-disable-next-line no-magic-numbers -- 默认查询条数限制
export const fetchNodes = (limit = 1000): Promise<NodeRow[]> =>
  apiFetch<NodeRow[]>(`/api/kg/nodes?limit=${limit}`);

/** 关系列表 (Neo4j) */
/** @shared */
// oxlint-disable-next-line no-magic-numbers -- 默认查询条数限制
export const fetchRelations = (limit = 1000): Promise<RelationRow[]> =>
  apiFetch<RelationRow[]>(`/api/kg/relationships?limit=${limit}`);

/** 知识图谱 schema */
/** @shared */
export const fetchSchema = (domain: string): Promise<KnowledgeSchema> =>
  apiFetch<KnowledgeSchema>(`/api/kg/schema?domain=${encodeURIComponent(domain)}`);

/** 列出可用 schema domain */
/** @shared */
export const fetchSchemas = (): Promise<{ schemas: { name: string }[] }> =>
  apiFetch<{ schemas: { name: string }[] }>("/api/kg/schemas");

/** 列出 dataset 下的 segments */
/** @shared */
export const fetchSegments = (): Promise<{ items: { id: string; content: string }[] }> =>
  apiFetch<{ items: { id: string; content: string }[] }>("/api/kg/segments");

/** 统计 */
/** @shared */
export const fetchStats = (type?: string, domain?: string): Promise<StatsResponse> => {
  const params = new URLSearchParams();
  if (type) {
    params.set("type", type);
  }
  if (domain) {
    params.set("domain", domain);
  }
  const qs = params.toString();
  let queryString = "";
  if (qs) {
    queryString = `?${qs}`;
  }
  return apiFetch<StatsResponse>(`/api/kg/stats${queryString}`);
};

/** Retriever 自测 — 走 BFF (Dify 调用) */
/** @client-bff */
export const retrieveQA = (
  question: string,
  datasetId: string,
  topK = THREE,
): Promise<RetrieveResult> =>
  apiFetch<RetrieveResult>("/api/knowledge/qa/retrieve", {
    body: { dataset_id: datasetId, question, top_k: topK },
    method: "POST",
  });

/** 启动后台批量任务 — 走 BFF (in-memory task map) */
/** @client-bff */
export const startBatch = (input: BatchInput): Promise<{ task_id: string }> =>
  apiFetch<{ task_id: string }>("/api/knowledge/batch", { body: input, method: "POST" });

/** 上传文档 — 走 BFF (multipart, 服务端中转) */
/** @client-bff */
export const uploadDocument = (file: File, datasetId: string): Promise<UploadResult> => {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("dataset_id", datasetId);
  return apiFetch<UploadResult>("/api/knowledge/documents/upload", { body: fd, method: "POST" });
};

// ============================================================
// (2026-07-01 markdown extract KG spec PR4 v3)
// 上传 Markdown → 后台抽取 → 预览 → 3 出口 (Neo4j / JSONL / Cypher)
// 全部走 /api/kg/extract/* (catch-all BFF 自动透传 cookie + query + body)
// ============================================================

/** Neo4j dataset 白名单 entry (PR4 v3: 新形状, 跟 Dify fetchDatasets 区分)
 * @shared */
export type DatasetEntry = { label: string };

/** 抽取器白名单 entry
 * @shared */
export type ExtractorInfo = { id: string; available: boolean };

/** 切片器白名单 entry (chunk_size_range 是 [min, max])
 * @shared */
export type SplitterInfo = { id: string; chunk_size_range: [number, number] };

/** 抽取任务状态 (后端 /api/kg/extract/tasks/{id} 响应)
 * @shared */
export type ExtractTaskState = {
  task_id: string;
  state: "queued" | "running" | "done" | "failed" | "partial";
  success: number;
  failed: number;
  errors: string[];
};

/** 预览实体 (后端 /preview 返)
 * @shared */
export type ExtractPreviewEntity = {
  id: number;
  text: string;
  label: string;
  selected: boolean;
  char_span: [number, number];
  confidence: number;
  chunk_id: string;
};

/** 预览关系 (后端 /preview 返)
 * @shared */
export type ExtractPreviewRelation = {
  id: number;
  head: string;
  rel_type: string;
  tail: string;
  selected: boolean;
  rule_type: string;
  confidence: number;
  chunk_id: string;
};

/** 预览响应 (entities + relations)
 * @shared */
export type ExtractPreview = {
  entities: ExtractPreviewEntity[];
  relations: ExtractPreviewRelation[];
};

/** PATCH items 输入 (id + selected + corrected_payload)
 * @shared */
export type PatchItemInput = {
  id: number;
  selected: boolean;
  corrected_payload: object | null;
};

/** 上传文件响应 (uri + file_id + dataset)
 * @shared */
export type ExtractUploadResult = { uri: string; file_id: string; dataset: string };

/** Neo4j dataset 白名单 (后端新增 /api/kg/extract/datasets 返 ["motor", "plc", "sensor"]) */
/** @shared */
export const fetchExtractDatasets = async (): Promise<DatasetEntry[]> =>
  apiFetch<DatasetEntry[]>("/api/kg/extract/datasets");

/** 抽取器白名单 */
/** @shared */
export const fetchExtractors = async (): Promise<ExtractorInfo[]> =>
  apiFetch<ExtractorInfo[]>("/api/kg/extract/extractors");

/** 切片器白名单 */
/** @shared */
export const fetchSplitters = async (): Promise<SplitterInfo[]> =>
  apiFetch<SplitterInfo[]>("/api/kg/extract/splitters");

/** 上传 Markdown 文件 → ObjectStore (dataset 透传 query param) */
/** @shared */
export const uploadExtractFile = (file: File, dataset: string): Promise<ExtractUploadResult> => {
  const fd = new FormData();
  fd.append("file", file);
  return apiFetch<ExtractUploadResult>(
    `/api/kg/extract/upload?dataset=${encodeURIComponent(dataset)}`,
    { body: fd, method: "POST" },
  );
};

/** 启动后台抽取任务 (BackgroundTasks 异步) */
/** @shared */
export const startExtract = (req: {
  uri: string;
  dataset: string;
  extractor: string;
  splitter: string;
}): Promise<{ task_id: string; state: string }> =>
  apiFetch<{ task_id: string; state: string }>("/api/kg/extract/start", {
    body: req,
    method: "POST",
  });

/** 轮询任务状态 */
/** @shared */
export const fetchExtractTask = (taskId: string): Promise<ExtractTaskState> =>
  apiFetch<ExtractTaskState>(`/api/kg/extract/tasks/${taskId}`);

/** 拉预览 (entities + relations) */
/** @shared */
export const fetchExtractPreview = (taskId: string, dataset: string): Promise<ExtractPreview> =>
  apiFetch<ExtractPreview>(
    `/api/kg/extract/tasks/${taskId}/preview?dataset=${encodeURIComponent(dataset)}`,
  );

/** 保存编辑 (勾选 / corrected_payload) */
/** @shared */
export const patchExtractItems = (
  taskId: string,
  dataset: string,
  items: PatchItemInput[],
): Promise<{ updated: number }> =>
  apiFetch<{ updated: number }>(
    `/api/kg/extract/tasks/${taskId}/items?dataset=${encodeURIComponent(dataset)}`,
    { body: { items }, method: "PATCH" },
  );

/** 写 Neo4j (commit 选中的实体/关系) */
/** @shared */
export const commitExtract = (
  taskId: string,
  dataset: string,
): Promise<{ success: number; failed: number; errors: string[] }> =>
  apiFetch<{ success: number; failed: number; errors: string[] }>(
    `/api/kg/extract/tasks/${taskId}/commit?dataset=${encodeURIComponent(dataset)}`,
    { method: "POST" },
  );

/** 导出参数 (避免 4 个位置参数触发 max-params)
 * @shared */
export type ExportArgs = {
  taskId: string;
  dataset: string;
  format: "jsonl" | "cypher";
  filename: string;
};

/** 拼导出 URL (query: dataset + format) */
const buildExportUrl = (args: ExportArgs): string =>
  `/api/kg/extract/tasks/${args.taskId}/export?dataset=${encodeURIComponent(
    args.dataset,
  )}&format=${args.format}`;

/** 浏览器端触发 blob 下载 (a 标签 + createObjectURL) */
const triggerBlobDownload = (blob: Blob, filename: string): void => {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
};

/** 导出 JSONL / Cypher (走 fetch blob + createObjectURL 触发下载) */
/** @shared */
export const triggerExportDownload = async (args: ExportArgs): Promise<void> => {
  // 走 raw fetch (不能用 apiFetch<T> 因为它返 JSON, 这里是下载)
  const res = await fetch(buildExportUrl(args));
  if (!res.ok) {
    throw new Error(`export 失败: ${res.status}`);
  }
  const blob = await res.blob();
  triggerBlobDownload(blob, args.filename);
};

// ============================================================
// (2026-07-03) KG 任务列表页: 后端 GET /api/kg/extract/tasks
// ============================================================

/** 抽取任务行 (kg_extract / kg_batch 共用形状, kg_extract 多 4 个 payload 字段)
 * @shared */
export type ExtractTaskRow = {
  task_id: string;
  kind: "kg_extract" | "kg_batch";
  state: "queued" | "running" | "done" | "partial" | "failed" | "cancelled";
  dataset?: string;
  extractor?: string;
  splitter?: string;
  uri?: string; // 前端不展示, 仅重跑用
  success: number;
  failed: number;
  created_at: number; // epoch float (秒)
  started_at: number | null;
  finished_at: number | null;
};

/** 任务列表响应 (含分页 + 聚合) */
export type ExtractTaskList = {
  items: ExtractTaskRow[];
  total: number;
  total_success: number;
  total_failed: number;
  limit: number;
  offset: number;
};

/** 列任务 (kind 必传, limit/offset 可选) */
/** @shared */
export const fetchExtractTasks = async (params: {
  kind: "kg_extract" | "kg_batch";
  limit?: number;
  offset?: number;
}): Promise<ExtractTaskList> => {
  const qs = new URLSearchParams({ kind: params.kind });
  if (params.limit !== undefined) {
    qs.set("limit", String(params.limit));
  }
  if (params.offset !== undefined) {
    qs.set("offset", String(params.offset));
  }
  return apiFetch<ExtractTaskList>(`/api/kg/extract/tasks?${qs.toString()}`);
};
