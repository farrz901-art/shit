// Dify Datasets API TS 客户端 (2026-06-08)
// 服务端调用 (BFF route handler 里), 凭据在 server env 不进 bundle
// (2026-06-14) 改走 apiProxy() (base=DIFY_BASE_URL 走外部服务, 跳过本项目 auth)
import { FIVE } from "@/const";
import { apiProxy } from "@/lib/api/config";

const BASE = process.env.DIFY_BASE_URL ?? "http://localhost/v1";
const API_KEY = process.env.DIFY_DATASET_API_KEY ?? "";

/**
 * Dify 数据集索引模式
 * @shared
 */
export type IndexingMode = "high_quality" | "economy";

/**
 * Dify 数据集元信息
 * @shared
 */
export interface Dataset {
  id: string;
  name: string;
  description?: string;
  document_count?: number;
  word_count?: number;
}

/**
 * Dify 数据集文档元信息
 * @shared
 */
export interface Document {
  id: string;
  dataset_id: string;
  name: string;
  indexing_status: "queued" | "indexing" | "completed" | "error";
  error?: string;
}

/**
 * Dify 检索命中的结果片段
 * @shared
 */
export interface RetrievalHit {
  content: string;
  score: number;
  document_id: string;
  document_name: string;
}

/**
 * Dify API 调用错误
 * @server-only
 */
class DifyApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "DifyApiError";
    this.status = status;
  }
}

const call = async <TResult>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<TResult> => {
  const res = await apiProxy(path, {
    base: BASE,
    body: init.body,
    headers: { Authorization: `Bearer ${API_KEY}` },
    method: init.method as "GET" | "POST" | undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new DifyApiError(res.status, text);
  }
  return (await res.json()) as TResult;
};

/**
 * Dify Datasets API 客户端方法集合
 * @server-only
 */
export const DifyDatasets = {
  /**
   * 按文本创建文档
   * @param datasetId        数据集 ID
   * @param name             文档名称
   * @param text             文档文本内容
   * @param indexingMode     索引模式 (默认 high_quality)
   * @returns                创建的文档信息
   */
  // eslint-disable-next-line max-params -- Dify API 要求的 4 个参数
  createDocumentByText: (
    datasetId: string,
    name: string,
    text: string,
    indexingMode: IndexingMode = "high_quality",
  ): Promise<Document> =>
    call<Document>(`/datasets/${datasetId}/document/create_by_text`, {
      body: {
        doc_form: "text_model",
        indexing_technique: indexingMode, // Dify API 要求字段名是 indexing_technique, 不是 indexing_mode
        name,
        process_rule: { mode: "automatic" }, // Dify v2+ 必填
        text,
      },
      method: "POST",
    }),

  /**
   * 创建文档片段
   * @param datasetId    数据集 ID
   * @param documentId   文档 ID
   * @param content      片段内容
   * @param keywords     关键词列表 (默认空数组)
   * @returns            创建的片段信息
   */
  // eslint-disable-next-line max-params -- Dify API 要求的 4 个参数
  createSegment: (
    datasetId: string,
    documentId: string,
    content: string,
    keywords: string[] = [],
  ): Promise<{ data: { id: string; position: number; content: string } }> =>
    call<{ data: { id: string; position: number; content: string } }>(
      `/datasets/${datasetId}/documents/${documentId}/segments`,
      {
        body: { segments: [{ content, keywords }] },
        method: "POST",
      },
    ),

  /**
   * 健康检查 (GET /datasets?limit=1 是否通)
   * @returns true 可连通 Dify
   */
  healthCheck: async (): Promise<boolean> => {
    try {
      await call("/datasets?limit=1");
      return true;
    } catch {
      return false;
    }
  },

  /**
   * 获取全部数据集列表
   * @returns 数据集列表 (不含分页元信息)
   */
  listDatasets: async (): Promise<Dataset[]> => {
    // Dify API 返回 { data: Dataset[], has_more, total, ... }, 提取 .data
    const res = await call<{ data: Dataset[] }>("/datasets?limit=100");
    return res.data;
  },

  /**
   * 获取数据集下的文档列表
   * @param datasetId  数据集 ID
   * @returns          文档列表 (含分页元信息)
   */
  listDocuments: (datasetId: string): Promise<{ data: Document[] }> =>
    call<{ data: Document[] }>(`/datasets/${datasetId}/documents?limit=100`),

  /**
   * 获取文档的片段列表
   * @param datasetId    数据集 ID
   * @param documentId   文档 ID
   * @returns            片段列表 (含 content / position)
   */
  // 获取文档的 segments
  listSegments: (
    datasetId: string,
    documentId: string,
  ): Promise<{ data: { id: string; content: string; position: number }[] }> =>
    call<{ data: { id: string; content: string; position: number }[] }>(
      `/datasets/${datasetId}/documents/${documentId}/segments?limit=10`,
    ),

  /**
   * 检索命中文档片段
   * @param datasetId  数据集 ID
   * @param query      检索查询文本
   * @param topK       返回 topK 条 (默认 FIVE)
   * @returns          检索结果 (含 content / score 等)
   */
  retrieve: (datasetId: string, query: string, topK = FIVE): Promise<{ records: RetrievalHit[] }> =>
    call<{ records: RetrievalHit[] }>(`/datasets/${datasetId}/retrieve`, {
      body: { query, retrieval_mode: "hybrid_search", top_k: topK },
      method: "POST",
    }),
};

export { DifyApiError };
