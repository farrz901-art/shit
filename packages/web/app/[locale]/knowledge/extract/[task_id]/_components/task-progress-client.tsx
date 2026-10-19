"use client";
// 抽取进度页 client 组件 (2026-07-01 markdown extract KG PR4 v3)
// (2026-07-03) 拆 RSC entry 后, 改为接收 sync taskId prop (page.tsx RSC 已 await params).
// 轮询 GET /tasks/{id} 1s 间隔. dataset 从 URL ?dataset=motor 拿.
// 状态: queued → running → done/partial (可跳预览) / failed (显示错误).
/* oxlint-disable max-statements -- 进度页逻辑连贯, 拆分增加阅读成本 */
import { useEffect, useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { TaskStatusBadge } from "@/components/common/display/app-task-status-badge";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { HUNDRED, ONE, ZERO, ONE_MINUTE_MS } from "@/const";
import { usePolling } from "@/lib/hooks";
import { fetchExtractTask, type ExtractTaskState } from "@/lib/api/knowledge";

/**
 * 抽取任务进度页属性
 * @property taskId - 抽取任务 ID
 */
export interface TaskProgressClientProps {
  taskId: string;
}

/**
 * 抽取进度 client 组件, 1s 轮询任务状态, 完成后跳预览
 * @param props.taskId - 抽取任务 ID
 * @client-bff
 */
export const TaskProgressClient = ({ taskId }: TaskProgressClientProps) => {
  const tr = useTranslations();
  const router = useRouter();
  const searchParams = useSearchParams();
  const dataset = searchParams.get("dataset") ?? "motor";
  const [task, setTask] = useState<ExtractTaskState | null>(null);
  const shouldPoll = task === null || task.state === "queued" || task.state === "running";

  usePolling(
    () => {
      void fetchExtractTask(taskId)
        .then((next) => setTask(next))
        .catch(() => {
          // 轮询失败静默, 下次 1s 后重试
        });
    },
    shouldPoll ? ONE_MINUTE_MS : null,
  );

  useEffect(() => {
    void fetchExtractTask(taskId)
      .then((next) => setTask(next))
      .catch(() => {
        // 首次拉取失败, 留 task=null 让轮询接管
      });
  }, [taskId]);

  if (!task) {
    return (
      <div className="space-y-6">
        <PageHero eyebrow={tr("知识图谱抽取")} title={tr("抽取进度")} description={tr("加载中…")} />
      </div>
    );
  }

  const isDone = task.state === "done" || task.state === "partial";
  const progressValue =
    task.success > ZERO
      ? Math.min(
          HUNDRED,
          Math.round((task.success / Math.max(task.success + task.failed, ONE)) * HUNDRED),
        )
      : ZERO;

  const handlePreviewClick = () => {
    void router.push(
      `/knowledge/extract/${task.task_id}/preview?dataset=${encodeURIComponent(dataset)}`,
    );
  };

  return (
    <div className="space-y-6">
      <PageHero
        eyebrow={tr("知识图谱抽取")}
        title={tr("抽取进度")}
        description={`task_id: ${task.task_id} | dataset: ${dataset}`}
      />
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{tr("状态")}</CardTitle>
          <TaskStatusBadge state={task.state} />
        </CardHeader>
        <CardContent className="space-y-4">
          <Progress value={progressValue} />
          <div className="text-sm text-muted-foreground">
            success: {task.success} | failed: {task.failed}
          </div>
          {task.errors.length > ZERO ? (
            <ErrorBanner
              variant="destructive"
              title={tr("错误")}
              description={task.errors.join("\n")}
            />
          ) : null}
          {isDone ? <Button onClick={handlePreviewClick}>{tr("预览实体与关系")}</Button> : null}
          {task.state === "failed" ? (
            <ErrorBanner
              variant="destructive"
              title={tr("抽取失败")}
              description="请检查后端日志"
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
};
