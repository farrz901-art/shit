"use client";
// /output 任务列表卡片组件 (Task 24, 2026-06-12 redesign)
// 职责: 单个 IngestTask 的状态展示 / 进度渲染 / 操作按钮 / 卡片封装

import type { IngestTask } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { LocalizedLink } from "@/components/i18n";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/** 基础常量 */
const MULTI_FILE_OFFSET = 1;
const PERCENTAGE_BASE = 100;
const COUNT_NONE = 0;

/** 翻译函数类型 */
type TranslateFn = (key: string, values?: Record<string, string | number | Date>) => string;

/**
 * StateBadge - 状态徽章组件
 * @param props.state - 任务状态
 * @param props.progress - 进度百分比
 * @client-bff
 */
export const StateBadge = ({
  state,
  progress,
}: {
  state: IngestTask["state"];
  progress: number;
}) => {
  const map = {
    completed: "bg-moss/10 text-moss",
    failed: "bg-destructive/10 text-destructive",
    queued: "bg-muted text-muted-foreground",
    running: "bg-clay/10 text-clay",
  } as const;
  let label: string = state;
  if (state === "running") {
    label = `${progress}%`;
  }
  return <span className={cn("rounded-full px-2 py-0.5 text-xs", map[state])}>{label}</span>;
};

/**
 * progressOf - 计算进度百分比
 * @param task - 任务数据
 * @returns 进度百分比
 * @client-bff
 */
export const progressOf = (task: IngestTask): number => {
  if (task.total_files) {
    return Math.round((task.processed / task.total_files) * PERCENTAGE_BASE);
  }
  return COUNT_NONE;
};

/**
 * summaryText - 任务进度摘要文本
 * @param task - 任务数据
 * @param translate - 翻译函数
 * @returns 摘要文本
 */
export const summaryText = (task: IngestTask, translate: TranslateFn): string => {
  switch (task.state) {
    case "completed": {
      if (task.failed) {
        return `${task.processed} ${translate("成功")} · ${task.failed} ${translate("失败")}`;
      }
      return `${task.processed} ${translate("成功")}`;
    }
    case "running": {
      return `${translate("处理中…")} ${task.processed}/${task.total_files}`;
    }
    case "queued": {
      return translate("排队中…");
    }
    case "failed": {
      return task.error || translate("未知错误");
    }
    default: {
      return "";
    }
  }
};

/**
 * formatRowName - 格式化文件名 (首个文件 +N 后缀)
 * @param row - 任务行
 * @returns 显示名称对象
 */
export const formatRowName = (row: IngestTask) => {
  const [firstFile] = row.input_files ?? [];
  const name = firstFile?.name;
  const fileCount = row.input_files?.length ?? COUNT_NONE;
  let more = "";
  if (fileCount > MULTI_FILE_OFFSET) {
    more = ` +${fileCount - MULTI_FILE_OFFSET}`;
  }
  if (name) {
    return { displayName: `${name}${more}` };
  }
  return { displayName: row.id };
};

/** 下载状态类型 */
interface DownloadState {
  downloading: Set<string>;
  onDownload: (id: string) => void;
}

/**
 * renderProgressCell - 渲染进度列
 * @param row - 任务行
 * @param translate - 翻译函数
 * @returns JSX
 */
export const renderProgressCell = (row: IngestTask, translate: TranslateFn): ReactNode => {
  const showTotal = row.total_files && (row.state === "completed" || row.state === "failed");
  return (
    <div className="text-sm text-muted-foreground">
      <span>{summaryText(row, translate)}</span>
      {showTotal && (
        <span className="ml-2 text-xs">
          / {row.total_files} {translate("总数")}
        </span>
      )}
    </div>
  );
};

/**
 * renderActionsCell - 渲染操作列 (查看产物 / 下载全部)
 * @param row - 任务行
 * @param downloadState - 下载状态
 * @param translate - 翻译函数
 * @returns JSX
 * @client-bff
 */
export const renderActionsCell = (
  row: IngestTask,
  downloadState: DownloadState,
  translate: TranslateFn,
): ReactNode => {
  const isDone = row.state === "completed" || row.state === "failed";
  if (!isDone) {
    return null;
  }
  const isDownloading = downloadState.downloading.has(row.id);
  let buttonText = "";
  if (isDownloading) {
    buttonText = translate("下载中…");
  } else {
    buttonText = translate("下载全部");
  }
  return (
    <div className="flex justify-end gap-2">
      <LocalizedLink
        href={`/output/${encodeURIComponent(row.id)}`}
        className="rounded-md border border-border bg-card px-3 py-1 text-sm text-muted-foreground transition-colors hover:border-ink/40 hover:text-foreground"
      >
        {translate("查看产物")}
      </LocalizedLink>
      <Button
        type="button"
        onClick={() => downloadState.onDownload(row.id)}
        disabled={isDownloading}
        data-testid="download-zip"
        className="rounded-md bg-clay px-3 py-1 text-sm text-primary-foreground transition-colors hover:bg-clay/90 disabled:opacity-50"
      >
        {buttonText}
      </Button>
    </div>
  );
};

/**
 * OutputCardProps - OutputCard 组件属性
 * @property task - 任务数据
 * @property downloading - 下载中的任务 ID 集合
 * @property onDownload - 下载回调
 * @property translate - 翻译函数
 */
export interface OutputCardProps {
  task: IngestTask;
  downloading: Set<string>;
  onDownload: (id: string) => void;
  translate: TranslateFn;
}

/**
 * OutputCard - 单个任务卡片
 * @param props - 组件属性
 * @client-bff
 */
export const OutputCard = ({ task, downloading, onDownload, translate }: OutputCardProps) => {
  const { displayName } = formatRowName(task);
  return (
    <div className="flex items-center gap-4 py-2">
      <span className="num block max-w-xs truncate font-medium text-foreground" title={task.id}>
        {displayName}
      </span>
      <StateBadge state={task.state} progress={progressOf(task)} />
      {renderProgressCell(task, translate)}
      {renderActionsCell(task, { downloading, onDownload }, translate)}
    </div>
  );
};
