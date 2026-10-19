// (2026-06-29) 评估指标定义 — 抽自 run-detail-view.tsx 的 4 个硬编 MetricBar
// 严重度 MEDIUM (A-10) — 消除 4 块硬编 label/value
import type { ComponentProps } from "react";
import type { EvaluationRun, ReportMetrics } from "@/lib/evaluate/types";
import type { SampleTable } from "./sample-table";

/** MetricDef - 评估指标定义 */
export interface MetricDef {
  key: keyof ReportMetrics;
  label: string;
}

/** 构建指标显示标签
 * @param translate - i18n 翻译函数
 * @param key - 指标键名
 * @returns 翻译后的标签
 * @shared
 */
const buildLabel = (translate: (key: string) => string, key: keyof ReportMetrics): string => {
  const labelMap: Record<keyof ReportMetrics, string> = {
    answer_relevancy: translate("答案相关性 (Answer Relevancy)"),
    context_precision: translate("上下文精度 (Context Precision)"),
    context_recall: translate("上下文召回 (Context Recall)"),
    faithfulness: translate("忠实度 (Faithfulness)"),
  };
  return labelMap[key];
};

/** 构建指标定义列表
 * @param translate - i18n 翻译函数
 * @returns 指标定义数组
 * @shared
 */
export const buildMetricDefs = (translate: (key: string) => string): MetricDef[] => {
  const keys: (keyof ReportMetrics)[] = [
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "faithfulness",
  ];
  return keys.map((key) => ({ key, label: buildLabel(translate, key) }));
};

/** 将评估运行的 samples 映射为 SampleTable 所需格式
 * @param samples - 评估运行样本
 * @returns SampleTable 兼容格式
 * @shared
 */
// (2026-06-29) 抽自 run-detail-view.tsx 的 samples.map 内联转换 (A-10)
export const mapSamplesForTable = (
  samples: EvaluationRun["samples"],
): ComponentProps<typeof SampleTable>["samples"] =>
  samples.map((sample) => ({
    answer: sample.answer ?? "",
    error: sample.error ?? undefined,
    ground_truth: sample.ground_truth ?? "",
    index: sample.index,
    metrics: sample.metrics,
    question: sample.question,
    sources: sample.sources ?? undefined,
  }));
