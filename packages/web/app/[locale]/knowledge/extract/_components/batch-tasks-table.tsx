"use client";
// kg_batch 任务列表 (2026-07-03): 跟 kg_extract 类似, 但无"重跑" + 行 click 不响应 (无详情页)
/* oxlint-disable id-length, max-statements -- TanStack cell 参数 row 短, 表格列定义连贯 */
import { useTranslations } from "next-intl";
import { FileText } from "lucide-react";
import { type ColumnDef, DataTable } from "@/components/common/table";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { TaskStatusBadge } from "@/components/common/display/app-task-status-badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { CopyButton } from "@/components/common/button/app-copy-button";
import { type ExtractTaskRow } from "@/lib/api/knowledge";
import { fmtRelativeTime } from "@/lib/date";
import { Button } from "@/components/ui/button";
import { ONE, ZERO } from "@/const";

const TASK_ID_PREVIEW_LENGTH = 8;

/**
 * BatchTasksTableProps - Batch 任务表格属性
 * @property rows - 任务行数据
 * @property total - 总任务数
 * @property totalSuccess - 成功数
 * @property totalFailed - 失败数
 * @property page - 当前页
 * @property pageSize - 每页大小
 * @property loading - 是否加载中
 * @property error - 错误信息
 * @property onPageChange - 翻页回调
 * @property onRetry - 重试回调
 */
export interface BatchTasksTableProps {
  rows: ExtractTaskRow[];
  total: number;
  totalSuccess: number;
  totalFailed: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  onPageChange: (page: number) => void;
  onRetry: () => void;
}

/**
 * kg_batch 任务列表表格 (无重跑 + 行 click 无响应)
 * @param props
 * @client-bff
 */
const BatchTasksTable = ({
  rows,
  loading,
  error,
  page,
  pageSize,
  total,
  onPageChange,
  onRetry,
}: BatchTasksTableProps) => {
  const tr = useTranslations();

  const columns: ColumnDef<ExtractTaskRow>[] = [
    {
      id: "task_id",
      header: tr("任务 ID"),
      cell: ({ row }) => {
        const taskId = row.original.task_id;
        return (
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{taskId.slice(ZERO, TASK_ID_PREVIEW_LENGTH)}…</span>
            <CopyButton
              text={taskId}
              label={tr("复制")}
              successLabel="✓"
              size="sm"
              variant="ghost"
            />
          </div>
        );
      },
    },
    {
      id: "kind",
      header: tr("类型"),
      cell: () => <span className="text-xs text-muted-foreground">kg_batch</span>,
    },
    {
      id: "state",
      header: tr("状态"),
      cell: ({ row }) => <TaskStatusBadge state={row.original.state} />,
    },
    {
      id: "progress",
      header: tr("进度"),
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {row.original.success}/{row.original.success + row.original.failed}
        </span>
      ),
    },
    {
      id: "created_at",
      header: tr("创建时间"),
      cell: ({ row }) => (
        <span className="text-xs text-muted-foreground">
          {fmtRelativeTime(row.original.created_at)}
        </span>
      ),
    },
  ];

  return (
    <>
      <DataTable<ExtractTaskRow>
        dataSource={rows}
        columns={columns}
        rowKey="task_id"
        loading={loading}
        emptyText={
          <DataEmpty icon={FileText} title={tr("暂无任务")} description={tr("暂无任务描述")} />
        }
        pagination={
          total > ZERO
            ? {
                current: page + ONE,
                pageSize,
                total,
                onChange: (pageNum) => onPageChange(pageNum - ONE),
              }
            : undefined
        }
      />
      {error ? (
        <div className="mt-4">
          <ErrorBanner
            variant="destructive"
            title={tr("加载任务失败")}
            description={error}
            action={
              <Button variant="outline" size="sm" onClick={onRetry}>
                {tr("刷新")}
              </Button>
            }
          />
        </div>
      ) : null}
    </>
  );
};

/**
 * @client-bff
 */
export default BatchTasksTable;
