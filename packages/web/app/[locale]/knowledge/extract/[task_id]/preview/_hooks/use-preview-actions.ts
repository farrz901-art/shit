// use-preview-actions — preview page 的 3 个 action handler (save / commit / export)
// 抽到独立 hook, 跟 usePreviewState 配套
"use client";
import { useState, useTransition } from "react";
import type { useTranslations } from "next-intl";
import { toast } from "sonner";
import { ZERO } from "@/const";
import { commitExtract, triggerExportDownload } from "@/lib/api/knowledge";

/**
 * UsePreviewActionsArgs - usePreviewActions 参数
 * @property taskId - 任务 ID
 * @property dataset - 数据集名称
 * @property saveEdits - 保存编辑回调
 * @property tr - useTranslations 返回值
 */
export interface UsePreviewActionsArgs {
  taskId: string;
  dataset: string;
  saveEdits: () => Promise<void>;
  tr: ReturnType<typeof useTranslations>;
}

/**
 * UsePreviewActionsResult - usePreviewActions 返回值
 * @property isPending - 操作是否 pending
 * @property commitOpen - 提交确认弹框是否打开
 * @property setCommitOpen - 设置提交弹框开关
 * @property error - 错误信息
 * @property setError - 设置错误信息
 * @property handleCommit - 提交处理函数
 * @property handleExport - 导出处理函数
 * @property handleSaveClick - 保存点击处理函数
 */
export interface UsePreviewActionsResult {
  isPending: boolean;
  commitOpen: boolean;
  setCommitOpen: (open: boolean) => void;
  error: string | null;
  setError: (message: string | null) => void;
  handleCommit: () => Promise<void>;
  handleExport: (format: "jsonl" | "cypher") => Promise<void>;
  handleSaveClick: () => void;
}
/**
 * Preview 页面 action hook, 封装保存/提交/导出操作与状态
 * @param args - hook 参数
 * @returns UsePreviewActionsResult
 * @client-bff
 */
export const usePreviewActions = ({
  taskId,
  dataset,
  saveEdits,
  tr,
}: UsePreviewActionsArgs): UsePreviewActionsResult => {
  const [isPending, startTransition] = useTransition();
  const [commitOpen, setCommitOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCommit = async (): Promise<void> => {
    setCommitOpen(false);
    startTransition(async () => {
      try {
        await saveEdits();
        const result = await commitExtract(taskId, dataset);
        if (result.failed > ZERO) {
          setError(`写入失败: ${result.errors.join(", ")}`);
          toast.error(tr("写 Neo4j 失败"));
        } else {
          toast.success(tr("已成功写入 Neo4j"));
        }
      } catch (commitError) {
        const message = commitError instanceof Error ? commitError.message : tr("写 Neo4j 失败");
        setError(message);
        toast.error(message);
      }
    });
  };

  const handleExport = async (format: "jsonl" | "cypher"): Promise<void> => {
    startTransition(async () => {
      try {
        await saveEdits();
        await triggerExportDownload({
          taskId,
          dataset,
          format,
          filename: `kg-${dataset}-${taskId}.${format}`,
        });
        toast.success(tr("导出成功"));
      } catch (exportError) {
        const message = exportError instanceof Error ? exportError.message : tr("导出失败");
        setError(message);
        toast.error(message);
      }
    });
  };

  const handleSaveClick = (): void => {
    startTransition(() => {
      void saveEdits().then(() => toast.success(tr("保存编辑")));
    });
  };

  return {
    isPending,
    commitOpen,
    setCommitOpen,
    error,
    setError,
    handleCommit,
    handleExport,
    handleSaveClick,
  };
};
