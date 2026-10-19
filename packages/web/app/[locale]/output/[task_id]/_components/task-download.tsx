"use client";
// 下载产物按钮组件 — 仅 completed 状态显示, 走 taskDownload API (2026-06-23 从 task-detail-client 提取)
import { Button } from "@/components/ui/button";
import type { IngestTask } from "@/lib/api";
import { useTranslations } from "next-intl";

/**
 * TaskDownload 组件属性
 * @property downloading - 是否下载中
 * @property onDownload - 下载回调
 * @property task - 任务数据
 */
interface Props {
  downloading: boolean;
  onDownload: () => void;
  task: IngestTask;
}

/**
 * TaskDownload - 下载产物按钮组件
 * @param props.downloading - 是否下载中
 * @param props.onDownload - 下载回调
 * @param props.task - 任务数据
 * @client-bff
 */
export const TaskDownload = ({ downloading, onDownload, task }: Props) => {
  const translate = useTranslations();

  if (task.state !== "completed") {
    return null;
  }

  return (
    <Button
      type="button"
      onClick={onDownload}
      disabled={downloading}
      data-testid="download-zip"
      className="rounded-lg bg-clay px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-clay/90 disabled:opacity-50"
    >
      {downloading ? translate("下载中…") : translate("↓ 下载全部产物 zip")}
    </Button>
  );
};
