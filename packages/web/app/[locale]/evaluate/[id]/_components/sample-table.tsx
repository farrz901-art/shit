// 逐条 QA 评估表格 (2026-06-11) — DataTable 封装
//   失败行用 expandedRowRender 始终展开错误原因 (原点击展开改为默认展开, 简化 UX)
"use client";
import { ChevronDown, FileText } from "lucide-react";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { Badge } from "@/components/ui/badge";
import type { SampleResult } from "@/lib/evaluate/types";
import { cn } from "@/lib/utils";
import { stripThink } from "./strip-think";

// ──────────── 局部常量 ────────────
/** 高分阈值 @shared */
const SOURCE_HIGH = 0.7;
/** 中分阈值 @shared */
const SOURCE_MEDIUM = 0.4;
/** sources 列最多显示条数 @shared */
const MAX_SOURCES_SHOWN = 3;
/** 数值小数位数 @shared */
const DECIMAL_PLACES = 3;
/** F1 权重因子 @shared */
const F1_WEIGHT = 2;

/** 根据分数返回颜色类名
 * @param val - 分数值
 * @returns Tailwind 颜色类名
 * @shared
 */
const scoreColor = (val: number | null): string => {
  if (val == null) {
    return "text-muted-foreground";
  }
  if (val >= SOURCE_HIGH) {
    return "text-moss";
  }
  if (val >= SOURCE_MEDIUM) {
    return "text-status-warning";
  }
  return "text-destructive";
};

/** 计算 F1: 2 * (P * R) / (P + R), P/R 为空时返回 null */
const calcF1 = (precision: number | null, recall: number | null): number | null => {
  if (precision == null || recall == null) {
    return null;
  }
  const sum = precision + recall;
  // eslint-disable-next-line no-magic-numbers -- 数学公式: sum 为 0 时返回 0
  if (sum === 0) {
    // eslint-disable-next-line no-magic-numbers -- 数学公式: F1 = 0
    return 0;
  }
  return (F1_WEIGHT * precision * recall) / sum;
};

/** 渲染错误状态图标
 * @param sample - 样本结果
 * @returns 图标节点或 null
 * @shared
 */
const renderStatusIcon = (sample: SampleResult) => {
  if (sample.error) {
    return <ChevronDown className="h-4 w-4 text-muted-foreground" />;
  }
  return null;
};

/** 计算并渲染 F1 分数
 * @param sample - 样本结果
 * @returns F1 分数节点
 * @shared
 */
const renderF1 = (sample: SampleResult) => {
  let f1Val: number | null = null;
  if (sample.metrics != null) {
    f1Val = calcF1(sample.metrics.context_precision, sample.metrics.context_recall);
  }
  return <MetricCell val={f1Val} />;
};

/** 根据样本状态返回行类名
 * @param sample - 样本结果
 * @returns Tailwind 行类名
 * @shared
 */
const getRowClassName = (sample: SampleResult): string => {
  if (sample.error) {
    return "bg-destructive/5";
  }
  return "";
};

/** 展开行渲染 (错误原因展示)
 * @param sample - 样本结果
 * @returns 展开行 JSX 或 null
 * @shared
 */
const renderExpandedRow = (sample: SampleResult): React.ReactNode => {
  if (!sample.error) {
    return null;
  }
  return (
    <div className="border-l-2 border-destructive/40 px-4 py-3 text-sm">
      <div className="mb-1 text-xs font-medium text-destructive">失败原因</div>
      <pre className="whitespace-pre-wrap break-all text-xs text-destructive/90">
        {sample.error}
      </pre>
    </div>
  );
};

/** DataTable 列配置 @shared */
const columns: ColumnDef<SampleResult>[] = [
  {
    accessorKey: "status_icon",
    cell: (ctx) => renderStatusIcon(ctx.row.original),
    header: () => "",
    size: 32,
  },
  {
    accessorKey: "index",
    cell: (ctx) => <span className="num text-muted-foreground">{ctx.row.original.index}</span>,
    header: () => "#",
    size: 48,
  },
  {
    accessorKey: "question",
    cell: (ctx) => (
      <span className="max-w-xs truncate text-sm block" title={ctx.row.original.question}>
        {ctx.row.original.question}
      </span>
    ),
    header: () => "问题",
  },
  {
    accessorKey: "answer",
    cell: (ctx) => {
      // (2026-06-11 Task A) 之前 max-w-sm truncate 单行截断, 改 whitespace-pre-wrap + max-h-32 overflow-y-auto
      // 长答案: 保留换行符 + 限制最大高度 + 内部滚动, 短答案正常显示
      // (2026-06-11 bug fix) 显示前 strip <think>...</think>, 历史评估入库时未 strip, 这里兜底
      const cleaned = stripThink(ctx.row.original.answer);
      return (
        <div
          className="max-w-sm max-h-32 overflow-y-auto whitespace-pre-wrap break-words text-sm text-muted-foreground rounded border border-border/30 bg-background/50 p-2"
          title={cleaned}
        >
          {cleaned || "—"}
        </div>
      );
    },
    header: () => "大模型回答",
  },
  {
    // (2026-06-11 Task C) 召回到的文件列表
    // 旧评估数据可能没 sources 字段 (undefined), 显 —
    // 新数据: [{name, position, score, snippet}, ...] 显示文件名+位置
    accessorKey: "sources",
    cell: (ctx) => {
      // eslint-disable-next-line no-magic-numbers -- 检查数组是否为空
      if (!ctx.row.original.sources || ctx.row.original.sources.length === 0) {
        return <span className="text-sm text-muted-foreground">—</span>;
      }
      // eslint-disable-next-line no-magic-numbers -- slice 起始索引为 0
      const sourceSlices = ctx.row.original.sources.slice(0, MAX_SOURCES_SHOWN);
      return (
        <div className="flex flex-col gap-1 text-xs">
          {sourceSlices.map((src, idx) => (
            <div key={idx} className="flex items-center gap-1" title={src.snippet}>
              <FileText className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
              <span className="truncate font-mono text-foreground/80">{src.name}</span>
              {src.position != null && (
                <span className="num text-muted-foreground">p.{src.position}</span>
              )}
            </div>
          ))}
          {ctx.row.original.sources.length > MAX_SOURCES_SHOWN && (
            <span className="text-muted-foreground">
              +{ctx.row.original.sources.length - MAX_SOURCES_SHOWN} 更多
            </span>
          )}
        </div>
      );
    },
    header: () => "召回到",
    size: 200,
  },
  {
    accessorKey: "faithfulness",
    cell: (ctx) => <MetricCell val={ctx.row.original.metrics?.faithfulness ?? null} />,
    header: () => "忠实度",
    size: 80,
  },
  {
    accessorKey: "answer_relevancy",
    cell: (ctx) => <MetricCell val={ctx.row.original.metrics?.answer_relevancy ?? null} />,
    header: () => "答案相关",
    size: 96,
  },
  {
    accessorKey: "context_precision",
    cell: (ctx) => <MetricCell val={ctx.row.original.metrics?.context_precision ?? null} />,
    header: () => "上下文精度",
    size: 96,
  },
  {
    accessorKey: "context_recall",
    cell: (ctx) => <MetricCell val={ctx.row.original.metrics?.context_recall ?? null} />,
    header: () => "上下文召回",
    size: 96,
  },
  {
    accessorKey: "f1",
    cell: (ctx) => renderF1(ctx.row.original),
    header: () => "F1",
    size: 64,
  },
  {
    accessorKey: "status",
    cell: (ctx) => {
      if (ctx.row.original.error) {
        return (
          <Badge variant="destructive" className="text-xs">
            失败
          </Badge>
        );
      }
      return (
        <Badge variant="outline" className="border-moss/40 text-moss text-xs">
          通过
        </Badge>
      );
    },
    header: () => "状态",
    size: 64,
  },
];

/** MetricCell - 单指标值单元格渲染
 * @param val - 指标值
 * @returns 指标值 JSX
 * @shared
 */
const MetricCell = ({ val }: { val: number | null }) => {
  if (val == null) {
    return <span className="text-sm text-destructive">—</span>;
  }
  return <span className={cn("num text-sm", scoreColor(val))}>{val.toFixed(DECIMAL_PLACES)}</span>;
};

/** SampleTable - 逐条 QA 评估表格组件
 * @param samples - 样本结果数组
 * @returns DataTable JSX
 * @client-bff
 */
export const SampleTable = ({ samples }: { samples: SampleResult[] }) => (
  <DataTable
    dataSource={samples}
    columns={columns}
    rowKey="index"
    maxHeight="600px"
    rowClassName={getRowClassName}
    expandedRowRender={renderExpandedRow}
  />
);
