"use client";
// 任务基本信息展示组件 — 标题 / 进度徽章 / 状态文案 (2026-06-23 从 task-detail-client 提取)
import type { IngestTask } from "@/lib/api";
import { Reveal } from "@/components/motion/animated";
import { useTranslations } from "next-intl";

/** 基础常量 */
const ZERO_VALUE = 0;
const PERCENTAGE_MAX = 100;
const EMPTY_STRING = "";

/**
 * calcProgress - 计算任务进度百分比
 * @param task - 任务数据
 * @returns 进度百分比
 */
const calcProgress = (task: IngestTask): number => {
  if (task.total_files > ZERO_VALUE) {
    return Math.round((task.processed / task.total_files) * PERCENTAGE_MAX);
  }
  return ZERO_VALUE;
};

/**
 * TaskInfo 组件属性
 * @property taskId - 任务 ID
 * @property task - 任务数据 (可选)
 */
interface Props {
  taskId: string;
  task: IngestTask | undefined;
}

/**
 * getProgressBadge - 渲染进度徽章 (仅 running 状态)
 * @param task - 任务数据
 * @returns JSX 徽章或 null
 */
const getProgressBadge = (task: IngestTask | undefined): React.ReactNode => {
  if (task?.state !== "running") {
    return null;
  }
  const percent = calcProgress(task);
  return <span className="rounded-full bg-clay/10 px-2 py-0.5 text-xs text-clay">{percent}%</span>;
};

/**
 * 状态文案构建器类型
 */
type StatusTextBuilder = (
  task: IngestTask,
  translate: ReturnType<typeof useTranslations>,
) => string;

/** 状态文案构建器 Record */
const STATUS_TEXT_BUILDERS: Record<IngestTask["state"], StatusTextBuilder> = {
  completed: (task, translate) => `${task.processed} ${translate("成功")}`,
  failed: (task, translate) => `${translate("失败:")} ${task.error || translate("未知错误")}`,
  queued: (_task, translate) => translate("排队中…"),
  running: (task, translate) => `${translate("处理中…")} ${task.processed}/${task.total_files}`,
};

/**
 * getStatusText - 获取状态文案
 * @param task - 任务数据
 * @param translate - i18n 翻译函数
 * @returns 状态文本
 */
const getStatusText = (
  task: IngestTask | undefined,
  translate: ReturnType<typeof useTranslations>,
): string => {
  if (!task) {
    return EMPTY_STRING;
  }
  return STATUS_TEXT_BUILDERS[task.state](task, translate);
};

/**
 * TaskInfo - 任务基本信息展示组件
 * @param props.taskId - 任务 ID
 * @param props.task - 任务数据 (可选)
 * @client-bff
 */
export const TaskInfo = ({ taskId, task }: Props) => {
  const translate = useTranslations();
  const progressBadge = getProgressBadge(task);
  const statusText = getStatusText(task, translate);

  return (
    <Reveal className="mb-6 space-y-2">
      <div className="flex items-center gap-3">
        <h1 className="display text-3xl tracking-tight md:text-4xl">
          {translate("任务 {id}", { id: taskId })}
        </h1>
        {progressBadge}
      </div>
      {task && <p className="text-base text-muted-foreground">{statusText}</p>}
    </Reveal>
  );
};
