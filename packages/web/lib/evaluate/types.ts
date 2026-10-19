// RAGAS 评估类型定义 (2026-06-09)
// 跟 src/rag/eval/router.py 响应结构 1:1 对齐

/** 评估状态枚举 (pending/running/completed/failed/cancelled).
 * @shared */
export const EvaluationStatus = {
  Cancelled: "cancelled",
  Completed: "completed",
  Failed: "failed",
  Pending: "pending",
  Running: "running",
} as const;
/** EvaluationStatus 的类型.
 * @shared */
export type EvaluationStatus = (typeof EvaluationStatus)[keyof typeof EvaluationStatus];

/** RAGAS 聚合指标, 含 faithfulness/answer_relevancy/context_precision/context_recall.
 * @shared */
export interface ReportMetrics {
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_precision: number | null;
  context_recall: number | null;
}

/** 单样本评估结果, 含问题/答案/指标/错误.
 * @shared */
export interface SampleResult {
  index: number;
  question: string;
  ground_truth: string;
  answer: string;
  contexts_count?: number;
  metrics: ReportMetrics | null;
  error?: string;
  // (2026-06-11 Task C) 召回到的文件列表: 旧评估可能没这个字段 (undefined → 显「—」)
  sources?: Source[];
}

// (2026-06-11 Task C) 单个召回文件: 跟后端 dify_client.achat 返的 sources 元素 1:1 对齐
/** 单个召回文件, 跟后端 dify_client.achat 返的 sources 对齐.
 * @shared */
export interface Source {
  name: string;
  position: number | null;
  score: number | null;
  snippet: string;
}

/** 完整评估报告, 含数据集信息/聚合指标/逐样本结果.
 * @shared */
export interface EvalReport {
  dataset_path: string;
  total_samples: number;
  successful: number;
  failed: number;
  concurrency: number;
  duration_seconds: number;
  avg_metrics: ReportMetrics;
  per_sample: SampleResult[];
}

// ---- 新增: 异步评估批 ----
/** 异步评估单条样本, 含问题/答案/上下文/指标/耗时.
 * @shared */
export interface EvaluationSample {
  id: number;
  index: number;
  question: string;
  ground_truth: string | null;
  answer: string | null;
  contexts: string[] | null;
  // (2026-06-11 Task C) 召回到文件: 跟后端 dify_client.achat 返的 sources 对齐
  // 旧评估数据可能没这个字段 (undefined), 跟 SampleResult.sources 一样可选
  sources?: Source[];
  metrics: ReportMetrics | null;
  error: string | null;
  duration_ms: number | null;
}

/** 评估批运行记录, 含状态/指标/样本列表.
 * @shared */
export interface EvaluationRun {
  id: number;
  user_id: number;
  dataset_name: string;
  dataset_path: string | null;
  status: EvaluationStatus;
  total_samples: number;
  successful: number;
  failed: number;
  concurrency: number;
  avg_metrics: ReportMetrics | null;
  duration_seconds: number | null;
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
  samples: EvaluationSample[];
}

// 列表行简版 (不嵌 samples, 减 payload)
/** 评估批列表行 (不含 samples, 减 payload).
 * @shared */
export type EvaluationRunSummary = Omit<EvaluationRun, "samples">;
