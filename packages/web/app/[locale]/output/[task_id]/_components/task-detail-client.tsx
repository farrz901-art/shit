"use client";
// /output/[task_id] 任务详情 client 子组件 (Task 25, 2026-06-12 redesign)
// 模式: RSC 预取 + HydrationBoundary, 客户端 useQuery 接管 2s 轮询.
// QueryKey 跟 RSC 端 qKeys.output.detail(task_id) 一致, staleTime: Infinity 让首屏不重拉.
// (2026-06-10 redesign; 2026-06-11 产物列表改用 DataTable) UI 跟 SWR 版一致:
//   - 产物表 + 「查看」链接 (只 md 文件)
//   - 「下载全部产物 zip」按钮 (走 taskDownload)
//   - 「取消任务」按钮 → cancelTask server action (Task 25 新增)
// (2026-06-14) shadcn: 取消/下载 button → <Button>; globalThis.alert → ErrorBanner
// (2026-06-14) barrel: 走 "@/lib/api" "@/components/common" "@/components/i18n" "@/lib/dom"
// (2026-06-23) 提取 TaskInfo / TaskFiles / TaskDownload 子组件 → ./task-info.tsx 等
import { TaskDownload } from "./task-download";
import { TaskFiles } from "./task-files";
import { TaskInfo } from "./task-info";
import { cancelTask } from "@/app/[locale]/_actions/output";
import { BackLink } from "@/components/common/navigation/app-back-link";
import { ErrorBanner } from "@/components/common";
import { FadePresence, Reveal } from "@/components/motion/animated";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, type IngestTask, NetworkError, fetchTask, qKeys, taskDownload } from "@/lib/api";
import { triggerBrowserDownload } from "@/lib/dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

// 常量定义
const POLL_INTERVAL = 2000;

/**
 * 从下载错误中提取消息字符串
 * @param downloadError - 下载错误 (unknown 类型)
 * @returns 错误消息字符串
 */
const extractErrorMessage = (downloadError: unknown): string => {
  if (downloadError instanceof ApiError || downloadError instanceof NetworkError) {
    return downloadError.message;
  }
  return String(downloadError);
};

/**
 * 从查询错误中解析可显示的消息
 * @param error - 查询错误 (unknown 类型)
 * @returns 可显示的错误消息; 无错误则返回 null
 */
const resolveError = (error: unknown): string | null => {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  return null;
};

/**
 * TaskDetailClient 组件属性
 * @property taskId - 任务 ID
 */
interface Props {
  taskId: string;
}

/**
 * 下载按钮 hook — 走 taskDownload (带 x-user-token) → blob → 浏览器保存
 * (2026-06-14) React 19 useTransition 替 useState(downloading) + finally 块:
 * startTransition 结束 isPending 自动 false
 * (2026-06-14) globalThis.alert → setDownloadError + ErrorBanner (页内反馈)
 * @param taskId - 任务 ID
 * @param translate - i18n 翻译函数
 * @param setDownloadError - 设置下载错误状态
 * @returns 下载状态和回调
 */
const useTaskDownload = (
  taskId: string,
  translate: ReturnType<typeof useTranslations>,
  setDownloadError: (msg: string | null) => void,
) => {
  const [isPending, startTransition] = useTransition();
  const onDownload = () => {
    if (isPending) {
      return;
    }
    startTransition(async () => {
      try {
        const { blob, filename } = await taskDownload(taskId);
        triggerBrowserDownload(blob, filename);
        setDownloadError(null);
      } catch (downloadError) {
        const msg = extractErrorMessage(downloadError);
        setDownloadError(translate("下载失败: {msg}", { msg }));
      }
    });
  };
  return { downloading: isPending, onDownload };
};

/**
 * 取消任务 hook — form action 模式 + startCancelTransition 标记 isPending
 * 走 _actions/output.ts: cancelTask POST 后端, 成功 revalidatePath 让 RSC 重新预取
 * @param taskId - 任务 ID
 * @param translate - i18n 翻译函数
 * @param setCancelError - 设置取消失败错误状态
 * @returns 取消状态和回调
 */
const useTaskCancel = (
  taskId: string,
  translate: ReturnType<typeof useTranslations>,
  setCancelError: (msg: string | null) => void,
) => {
  const [cancelPending, startCancelTransition] = useTransition();
  const [cancelling, setCancelling] = useState(false);
  const onCancelSubmit = () => {
    if (cancelling) {
      return;
    }
    setCancelling(true);
    startCancelTransition(async () => {
      const result = await cancelTask(taskId);
      setCancelling(false);
      if (!result.ok) {
        setCancelError(translate("取消失败: {msg}", { msg: result.error }));
      }
    });
  };
  return { cancelPending, cancelling, onCancelSubmit };
};

/**
 * TaskDetailClient — 任务详情 client 子组件
 * RSC 预取 + HydrationBoundary, 客户端 useQuery 接管 2s 轮询
 * @param props.taskId - 任务 ID
 * @returns JSX 元素
 */
export const TaskDetailClient = ({ taskId }: Props) => {
  const translate = useTranslations();
  // 2s 轮询: 任务进行中 (running/queued) 时拉, completed 后停止.
  // RefetchInterval 接受函数 (RQ v5 API), 返 false 停止轮询.
  const { data: task, error } = useQuery<IngestTask>({
    queryFn: () => fetchTask(taskId),
    queryKey: qKeys.output.detail(taskId),
    refetchInterval: (query) => {
      if (query.state.data?.state === "completed") {
        return false;
      }
      return POLL_INTERVAL;
    },
  });
  const errorMessage = resolveError(error);
  // (2026-06-14) ErrorBanner state: 下载/取消失败反馈, 替 globalThis.alert
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const { downloading, onDownload } = useTaskDownload(taskId, translate, setDownloadError);
  const { cancelPending, cancelling, onCancelSubmit } = useTaskCancel(
    taskId,
    translate,
    setCancelError,
  );
  const displayError = downloadError ?? cancelError ?? errorMessage;

  return (
    <div className="h-full overflow-y-auto">
      <Reveal className="mb-6">
        <BackLink href="/output" label={translate("返回 Output")} />
      </Reveal>

      <TaskInfo taskId={taskId} task={task} />

      <FadePresence mode="wait">
        <BodyContentSwitch
          cancelPending={cancelPending}
          cancelling={cancelling}
          displayError={displayError}
          downloading={downloading}
          onCancelSubmit={onCancelSubmit}
          onDownload={onDownload}
          setCancelError={setCancelError}
          setDownloadError={setDownloadError}
          task={task}
          translate={translate}
        />
      </FadePresence>
    </div>
  );
};

/**
 * BodyContentSwitch — 根据 displayError / task 状态渲染主内容区
 * @param props.cancelPending - 取消请求 pending 状态
 * @param props.cancelling - 取消中状态
 * @param props.displayError - 显示错误消息
 * @param props.downloading - 下载中状态
 * @param props.onCancelSubmit - 取消提交回调
 * @param props.onDownload - 下载回调
 * @param props.setCancelError - 设置取消错误状态
 * @param props.setDownloadError - 设置下载错误状态
 * @param props.task - 任务数据
 * @param props.translate - i18n 翻译函数
 * @returns JSX 元素
 */
const BodyContentSwitch = ({
  cancelPending,
  cancelling,
  displayError,
  downloading,
  onCancelSubmit,
  onDownload,
  setCancelError,
  setDownloadError,
  task,
  translate,
}: {
  cancelPending: boolean;
  cancelling: boolean;
  displayError: string | null;
  downloading: boolean;
  onCancelSubmit: () => void;
  onDownload: () => void;
  setCancelError: (msg: string | null) => void;
  setDownloadError: (msg: string | null) => void;
  task: IngestTask | undefined;
  translate: ReturnType<typeof useTranslations>;
}) => {
  if (displayError) {
    return (
      <ErrorBanner
        variant="destructive"
        description={displayError}
        action={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setDownloadError(null);
              setCancelError(null);
            }}
          >
            {translate("重试")}
          </Button>
        }
      />
    );
  }
  if (!task) {
    return <div className="text-base text-muted-foreground">{translate("加载中…")}</div>;
  }
  return (
    <OutputPanel
      cancelPending={cancelPending}
      cancelling={cancelling}
      downloading={downloading}
      onCancelSubmit={onCancelSubmit}
      onDownload={onDownload}
      task={task}
    />
  );
};

/**
 * OutputPanel — 产物表 + 操作按钮 (取消任务 / 下载 zip)
 * @param props.task - 任务数据
 * @param props.downloading - 下载中状态
 * @param props.cancelPending - 取消请求 pending 状态
 * @param props.cancelling - 取消中状态
 * @param props.onDownload - 下载回调
 * @param props.onCancelSubmit - 取消提交回调
 * @returns JSX 元素
 */
const OutputPanel = ({
  task,
  downloading,
  cancelPending,
  cancelling,
  onDownload,
  onCancelSubmit,
}: {
  task: IngestTask;
  downloading: boolean;
  cancelPending: boolean;
  cancelling: boolean;
  onDownload: () => void;
  onCancelSubmit: () => void;
}) => {
  const translate = useTranslations();

  return (
    <Card className="overflow-hidden border-border/60">
      <CardContent className="p-6">
        <TaskFiles task={task} />
        <div className="mt-6 flex justify-end gap-2">
          <form action={onCancelSubmit}>
            <Button
              type="submit"
              variant="outline"
              disabled={cancelPending || cancelling}
              className="rounded-lg border border-border bg-card px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-ink/40 hover:text-foreground disabled:opacity-50"
            >
              {cancelPending || cancelling ? translate("取消中…") : translate("取消任务")}
            </Button>
          </form>
          <TaskDownload downloading={downloading} onDownload={onDownload} task={task} />
        </div>
      </CardContent>
    </Card>
  );
};
