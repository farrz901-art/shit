"use client";
// pre-analysis stages 弹框 (2026-07-03) — 行点击触发, 显示 5 个 detail stage 进度

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, CircleDashed, Loader2, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { formatDurationMs } from "@/lib/date";
import {
  listPreAnalysisStages,
  type PreAnalysisDetailStage,
  type PreAnalysisStageItem,
  type PreAnalysisStageStatus,
} from "@/lib/api/pre-analysis";

/** 详情 stage 对应的中文标签映射 */
const STAGE_LABEL: Record<PreAnalysisDetailStage, string> = {
  prepare_input: "加载配置",
  extract_chapters: "章节提取",
  extract_tables: "表格提取",
  extract_flagged: "段落标记",
  write_outputs: "写产物",
};

/** 消息最大显示长度 */
const MAX_MESSAGE_LENGTH = 200;
/** 切片起始位置 */
const SLICE_START = 0;
/** 空消息占位符 */
const EMPTY_MESSAGE_PLACEHOLDER = "—";
/** (2026-07-08) "表格数" 之前是单列, 现在直接拼到 message 单元格, 避免表格内容撑成 5 列太挤. */
/** 后端 extract_tables message 模板 "{N} 表 / {M} 跨页候选" 的"表数"regex (2026-07-07) */
const TABLE_COUNT_PATTERN = /^(?<count>\d+)\s*表/;
/** (2026-07-07) 表格提取阶段未拉到 message 时的"无表格"展示常量 */
const ZERO_TABLES_HINT = "0";
/** (2026-07-08) "表格数: 消息正文" 之间的分隔符 */
const TABLE_COUNT_SEPARATOR = " · ";

/**
 * 根据状态渲染对应的状态图标
 * @param status - 预分析阶段状态
 * @returns 对应的图标 React 节点
 */
const renderStatusIcon = (status: PreAnalysisStageStatus): React.ReactNode => {
  if (status === "started") {
    return <Loader2 className="h-4 w-4 animate-spin text-status-success" />;
  }
  if (status === "completed") {
    return <CheckCircle2 className="h-4 w-4 text-status-success" />;
  }
  if (status === "failed") {
    return <XCircle className="h-4 w-4 text-status-error" />;
  }
  if (status === "pending") {
    return <Circle className="h-4 w-4 text-muted-foreground" />;
  }
  return <CircleDashed className="h-4 w-4 text-muted-foreground" />;
};

/** 预分析阶段详情弹框属性 */
export interface PreAnalysisStagesDialogProps {
  /** 弹框打开状态 */
  open: boolean;
  /** 弹框打开状态变更回调 */
  onOpenChange: (open: boolean) => void;
  /** 预分析任务 ID */
  taskId: string;
}

/**
 * 预分析阶段详情弹框组件 — 行点击触发, 显示 5 个 detail stage 进度
 * @param props - 组件属性
 * @param props.open - 弹框打开状态
 * @param props.onOpenChange - 弹框打开状态变更回调
 * @param props.taskId - 预分析任务 ID
 * @returns 预分析阶段详情弹框
 * @client-bff
 */
export const PreAnalysisStagesDialog = ({
  open,
  onOpenChange,
  taskId,
}: PreAnalysisStagesDialogProps) => {
  const translate = useTranslations();

  const { data, isLoading } = useQuery({
    queryKey: ["pre-analysis-stages", taskId],
    queryFn: () => listPreAnalysisStages(taskId),
    enabled: open,
  });

  const stagesMap = new Map<string, PreAnalysisStageItem>(
    (data?.stages ?? []).map((stage) => [stage.stage, stage]),
  );

  // 加载中 → loading 动画; 数据到 → 5 行 (未拉到的 stage pending = 未开始)
  const allStages: PreAnalysisStageItem[] = isLoading
    ? []
    : (Object.keys(STAGE_LABEL) as PreAnalysisDetailStage[]).map((stage) => {
        const fromDb = stagesMap.get(stage);
        if (fromDb) {
          return fromDb;
        }
        return {
          stage,
          status: "pending" as PreAnalysisStageStatus,
          progress: 0,
          started_at: "",
          finished_at: null,
          message: null,
        };
      });

  const statusLabels: Record<PreAnalysisStageStatus, string> = {
    pending: translate("未开始"),
    started: translate("进行中"),
    completed: translate("已完成"),
    failed: translate("失败"),
    skipped: translate("已跳过"),
  };

  const renderStatusCell = (stage: PreAnalysisStageItem): React.ReactNode => (
    <div className="flex items-center gap-2">
      {renderStatusIcon(stage.status)}
      <span>{statusLabels[stage.status]}</span>
    </div>
  );

  /**
   * (2026-07-08) 把 "已提取 N 个表格" 拼到消息列 — 不再独立成列.
   * 表格数信息从 message 文本 "{N} 表 / {M} 跨页候选" 抽.
   * 状态 started 时高亮 running 状态色.
   * @param stage 阶段详情
   * @returns React 节点 (拼好的 "已提取 N 个表格 · 原 message" 或仅原 message)
   */
  const renderMessageCell = (stage: PreAnalysisStageItem): React.ReactNode => {
    const rawMessage = (stage.message ?? "").slice(SLICE_START, MAX_MESSAGE_LENGTH);
    if (stage.stage !== "extract_tables") {
      return rawMessage || EMPTY_MESSAGE_PLACEHOLDER;
    }
    const match = TABLE_COUNT_PATTERN.exec(stage.message ?? "");
    const count = match?.groups?.count ?? ZERO_TABLES_HINT;
    const countClass = stage.status === "started" ? "text-status-running" : "text-foreground";
    return (
      <span data-testid={`table-count-${stage.stage}`}>
        <span className={`font-medium ${countClass}`}>
          {translate("已提取 {N} 个表格", { N: count })}
        </span>
        {rawMessage ? (
          <span className="text-muted-foreground">{TABLE_COUNT_SEPARATOR + rawMessage}</span>
        ) : null}
      </span>
    );
  };

  const columns: ColumnDef<PreAnalysisStageItem>[] = [
    {
      accessorKey: "stage",
      cell: (ctx) => STAGE_LABEL[ctx.row.original.stage],
      header: () => translate("阶段"),
    },
    {
      accessorKey: "status",
      cell: (ctx) => renderStatusCell(ctx.row.original),
      header: () => translate("状态"),
    },
    {
      accessorKey: "duration",
      cell: (ctx) => formatDurationMs(ctx.row.original.started_at, ctx.row.original.finished_at),
      header: () => translate("耗时"),
    },
    {
      accessorKey: "message",
      cell: (ctx) => renderMessageCell(ctx.row.original),
      header: () => translate("消息"),
    },
  ];

  return (
    <AppDialog
      className="w-[800px] max-w-[800px]"
      dataTestid="pre-analysis-stages-dialog"
      footer={
        <Button onClick={() => onOpenChange(false)} variant="outline">
          {translate("关闭")}
        </Button>
      }
      maxWidth="xl"
      onOpenChange={onOpenChange}
      open={open}
      title={`${translate("总体阶段")}: ${taskId}`}
    >
      <div data-testid="pre-analysis-stages-table">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <DataTable columns={columns} dataSource={allStages} rowKey="stage" />
        )}
      </div>
    </AppDialog>
  );
};
