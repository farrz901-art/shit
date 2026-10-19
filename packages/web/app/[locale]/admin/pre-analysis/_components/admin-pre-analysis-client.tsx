"use client";
// admin/pre-analysis client 组件 (2026-07-02 PR5) — RSC entry
// (2026-07-03) 上传改成 Button + PreAnalysisUploadDialog 弹框 (替 FileDropzone)
// (2026-07-03) 新增总体阶段列 + 点总体阶段弹 stages 弹框 + 重试按钮 + 手动刷新按钮 (不轮询)

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, UploadCloud } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { AppTooltip } from "@/components/common/overlay/app-tooltip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { formatDateTime, formatDurationMs } from "@/lib/date";
import { useRouter } from "@/i18n/navigation";
import {
  listPreAnalysisTasks,
  retryPreAnalysisTask,
  type PreAnalysisOverallStage,
  type PreAnalysisTaskItem,
  type PreAnalysisTaskState,
} from "@/lib/api/pre-analysis";
import { PreAnalysisStagesDialog } from "./pre-analysis-stages-dialog";
import { PreAnalysisUploadDialog } from "./pre-analysis-upload-dialog";

/**
 * 格式化 ISO 时间为本地字符串 (浏览器默认 locale).
 * @param iso - ISO 时间字符串
 * @returns 本地化时间字符串
 * @shared
 */
const formatTime = (iso: string): string => formatDateTime(iso, "zh-CN");

/**
 * (2026-07-07) 渲染 summary 计数列; undefined → "—" (旧数据 / 字段缺失防御).
 * Pydantic 强类型下 5 字段都是 number, 但前端消费历史脏数据时降级.
 * @param val 计数值
 * @returns 数字字符串 / "—"
 * @shared
 */
const formatSummaryCount = (val: number | undefined): string => {
  if (val === undefined || Number.isNaN(val)) {
    return PLACEHOLDER_DASH;
  }
  return String(val);
};

/** State 到 Badge variant 映射 */
const STATE_VARIANT: Record<
  PreAnalysisTaskState,
  "secondary" | "default" | "destructive" | "running"
> = {
  pending: "secondary",
  // (2026-07-09) running 用 running variant (绿), 跟 completed (default/蓝) 区分开
  running: "running",
  completed: "default",
  failed: "destructive",
};

/** 总体阶段标签映射 */
const OVERALL_STAGE_LABEL: Record<PreAnalysisOverallStage, string> = {
  prepare_input: "加载配置",
  extract_chapters: "章节提取",
  extract_tables: "表格提取",
  extract_flagged: "段落标记",
  write_outputs: "写产物",
  done: "已完成",
};

/** 列表查询上限 */
const TASKS_LIMIT = 50;
/** 失败状态常量 */
const TASK_STATE_FAILED = "failed";
/** 占位横线 */
const PLACEHOLDER_DASH = "—";
/** 空阶段标签 */
const EMPTY_LABEL_FOR_STAGE = "—";

/**
 * admin/pre-analysis 列表客户端组件
 *
 * 上传按钮 + 历史预分析任务列表 (按 started_at DESC).
 * 行点开 stages 弹框 + 重试 + 手动刷新.
 *
 * @returns 页面 React 元素
 * @client-bff
 */
// oxlint-disable-next-line max-statements -- 列定义 + 3 个 handler 集中管理, 不拆函数
export const AdminPreAnalysisClient = (): React.ReactElement => {
  const translate = useTranslations();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [stagesDialogTaskId, setStagesDialogTaskId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const {
    data,
    error: fetchError,
    isLoading,
  } = useQuery({
    queryKey: ["pre-analysis-tasks"],
    queryFn: () => listPreAnalysisTasks({ limit: TASKS_LIMIT }),
  });

  const handleRefresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: ["pre-analysis-tasks"] });
  };

  const handleRetry = async (taskId: string): Promise<void> => {
    setRetryingId(taskId);
    try {
      await retryPreAnalysisTask(taskId);
      toast.success(translate("已重试"));
      void queryClient.invalidateQueries({ queryKey: ["pre-analysis-tasks"] });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    } finally {
      setRetryingId(null);
    }
  };

  const stateLabels: Record<PreAnalysisTaskState, string> = {
    pending: translate("等待中"),
    running: translate("运行中"),
    completed: translate("已完成"),
    failed: translate("失败"),
  };

  const renderStateBadge = (task: PreAnalysisTaskItem): React.ReactNode => {
    const badge = <Badge variant={STATE_VARIANT[task.state]}>{stateLabels[task.state]}</Badge>;
    if (task.state === TASK_STATE_FAILED && task.error) {
      return (
        <AppTooltip content={task.error} variant="error">
          {badge}
        </AppTooltip>
      );
    }
    return badge;
  };

  const columns: ColumnDef<PreAnalysisTaskItem>[] = [
    {
      accessorKey: "id",
      header: () => translate("任务编号"),
    },
    {
      accessorKey: "pdf_filename",
      header: () => translate("PDF 文件名"),
    },
    {
      accessorKey: "state",
      cell: (ctx) => renderStateBadge(ctx.row.original),
      header: () => translate("状态"),
    },
    {
      accessorKey: "current_stage",
      cell: (ctx) => (
        <Button
          onClick={(event) => {
            event.stopPropagation();
            setStagesDialogTaskId(ctx.row.original.id);
          }}
          size="sm"
          variant="link"
        >
          {ctx.row.original.current_stage
            ? OVERALL_STAGE_LABEL[ctx.row.original.current_stage]
            : EMPTY_LABEL_FOR_STAGE}
        </Button>
      ),
      header: () => translate("总体阶段"),
    },
    {
      accessorKey: "table_backend",
      cell: (ctx) => {
        const config = ctx.row.original.task_config_json;
        if (!config || !config.table_backend) {
          return PLACEHOLDER_DASH;
        }
        return String(config.table_backend);
      },
      header: () => translate("表格提取器"),
    },
    {
      accessorKey: "started_at",
      cell: (ctx) => formatTime(ctx.row.original.started_at),
      header: () => translate("上传时间"),
    },
    {
      accessorKey: "duration",
      cell: (ctx) => formatDurationMs(ctx.row.original.started_at, ctx.row.original.finished_at),
      header: () => translate("耗时"),
    },
    {
      accessorKey: "total_tables",
      cell: (ctx) => formatSummaryCount(ctx.row.original.summary.total_tables),
      header: () => translate("表格数"),
    },
    {
      accessorKey: "total_chapters",
      cell: (ctx) => formatSummaryCount(ctx.row.original.summary.total_chapters),
      header: () => translate("章节数"),
    },
    {
      accessorKey: "total_flagged_paragraphs",
      cell: (ctx) => formatSummaryCount(ctx.row.original.summary.total_flagged_paragraphs),
      header: () => translate("标记段落数"),
    },
    {
      accessorKey: "actions",
      cell: (ctx) => (
        <div className="flex gap-2">
          <Button
            onClick={() => router.push(`/admin/pre-analysis/${ctx.row.original.id}`)}
            size="sm"
            variant="link"
          >
            {translate("查看详情")}
          </Button>
          {ctx.row.original.state === TASK_STATE_FAILED ? (
            <Button
              data-testid={`retry-${ctx.row.original.id}`}
              disabled={retryingId === ctx.row.original.id}
              onClick={() => {
                void handleRetry(ctx.row.original.id);
              }}
              size="sm"
              variant="outline"
            >
              {retryingId === ctx.row.original.id ? translate("重试中…") : translate("重试")}
            </Button>
          ) : null}
        </div>
      ),
      header: () => translate("操作"),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHero eyebrow="admin" title={translate("PDF 预分析")} />
      <div className="flex justify-end gap-2">
        <Button data-testid="refresh-tasks" onClick={handleRefresh} size="sm" variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          {translate("刷新")}
        </Button>
        <Button
          data-testid="pre-analysis-upload-trigger"
          onClick={() => setIsDialogOpen(true)}
          size="lg"
          variant="default"
        >
          <UploadCloud className="mr-2 h-4 w-4" />
          {translate("上传 PDF")}
        </Button>
      </div>
      {fetchError ? (
        <ErrorBanner description={String(fetchError)} variant="destructive" />
      ) : (
        <DataTable
          columns={columns}
          dataSource={data?.tasks ?? []}
          emptyText={
            <DataEmpty
              description={translate("点击上传按钮开始")}
              title={translate("无预分析任务")}
            />
          }
          loading={isLoading}
          rowKey="id"
          maxHeight="400px"
        />
      )}
      <PreAnalysisUploadDialog
        onComplete={() => {
          void queryClient.invalidateQueries({ queryKey: ["pre-analysis-tasks"] });
        }}
        onOpenChange={setIsDialogOpen}
        open={isDialogOpen}
      />
      <PreAnalysisStagesDialog
        onOpenChange={(open) => {
          if (!open) {
            setStagesDialogTaskId(null);
          }
        }}
        open={stagesDialogTaskId !== null}
        taskId={stagesDialogTaskId ?? PLACEHOLDER_DASH}
      />
    </div>
  );
};
