"use client";
// 批量导入 (2026-06-09 redesign) — hero + 进度条 + 实时任务面板
// (2026-06-11) motion.button 替换为 shadcn Button
// (2026-06-11) i18n: useTranslations + t() 包裹中文文案
// (2026-06-17) v2 RBAC: 套 GuardClient 做 4 层防护第 2 层
import { AnimateUp, Reveal } from "@/components/motion/animated";
import { type BatchState, fetchBatchStatus, startBatch } from "@/lib/api/knowledge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { FIFTY, HUNDRED, THOUSAND, ZERO } from "@/const/index";
import { useState, useTransition } from "react";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Button } from "@/components/ui/button";
import { GuardClient } from "@/components/auth/guard-client";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { TaskStatusBadge } from "@/components/common/display/app-task-status-badge";
import { cn } from "@/lib/utils";
import { parseJsonText } from "@/lib/parse/parse-json";
import { useAppStore } from "@/lib/store/app-store";
import { usePolling } from "@/lib/hooks";
import { DELAY } from "@/lib/motion";
import { useTranslations } from "next-intl";

// BatchTaskPolling: 后台任务轮询子组件, 抽离 usePolling 闭包, 让 BatchPageInner 不超 10-statement 上限
/** BatchTaskPolling - 后台任务轮询子组件
 * @shared
 */
const BatchTaskPolling = ({
  activeTask,
  setActiveTask,
}: {
  activeTask: BatchState | null;
  setActiveTask: (val: BatchState | null) => void;
}) => {
  const shouldPoll =
    activeTask !== null && (activeTask.state === "queued" || activeTask.state === "running");
  usePolling(
    () => {
      if (!activeTask) {
        return;
      }
      void fetchBatchStatus(activeTask.task_id)
        .then((tk) => {
          setActiveTask(tk);
        })
        .catch(() => {
          // 静默: 一次 poll 失败不影响下一次
        });
    },
    shouldPoll ? THOUSAND : null,
  );
  return null;
};

// 计算提交按钮文案、进度值、失败样式
/** BatchDerivedState - 批量导入状态推导类型 */
interface BatchDerivedState {
  /** 提交按钮文案 */
  submitLabel: string;
  /** 进度条当前值 */
  progressValue: number;
  /** 失败文案样式类名 */
  failedClassName: string;
}

/** useBatchDerivedState - 从任务状态推导 UI 状态 (按钮文案、进度值、失败样式)
 * @param tr i18n 翻译函数
 * @param isPending 是否提交中
 * @param activeTask 当前活跃任务 (可为 null)
 * @returns 推导后的 UI 状态
 * @client-bff
 */
const useBatchDerivedState = (
  tr: ReturnType<typeof useTranslations>,
  isPending: boolean,
  activeTask: BatchState | null,
): BatchDerivedState => {
  let submitLabel = tr("提交为后台任务");
  if (isPending) {
    submitLabel = tr("提交中…");
  }

  let progressValue = ZERO;
  if (activeTask && activeTask.total) {
    progressValue = (activeTask.processed / activeTask.total) * HUNDRED;
  }

  let failedClassName = "text-foreground";
  if (activeTask && activeTask.failed > ZERO) {
    failedClassName = "text-destructive";
  }

  return { failedClassName, progressValue, submitLabel };
};

/** BatchPage - 批量导入页面根组件, 包裹 GuardClient 鉴权
 * @client-bff
 */
export default function BatchPage() {
  return (
    <GuardClient pageKey="knowledge">
      <BatchPageInner />
    </GuardClient>
  );
}

/** BatchPageInner - 批量导入页面内部组件 (含文件选择、解析、提交和任务轮询逻辑)
 * @client-bff
 */
const BatchPageInner = () => {
  const tr = useTranslations();
  const datasetId = useAppStore((store) => store.datasetId);
  const [file, setFile] = useState<File | null>(null);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  // (2026-06-14) React 19 useTransition 替 useState(submitting) — 整段 (file.text → parse → startBatch) 包进 transition
  const [isPending, startTransition] = useTransition();
  const [activeTask, setActiveTask] = useState<BatchState | null>(null);

  // (2026-06-14) react-use: useInterval 替 setInterval + useEffect + clearInterval + useRef 模板.
  // 任务 queued/running 时 1s 轮询; 完成/失败/取消时传 null 停止 (内部 clearInterval).
  // 抽离轮询闭包到 BatchTaskPolling 子组件, 避免 BatchPageInner 触发 max-statements (≤10) 限制

  const { failedClassName, progressValue, submitLabel } = useBatchDerivedState(
    tr,
    isPending,
    activeTask,
  );

  const handleSubmit = () => {
    if (!file || !datasetId) {
      return;
    }
    setParseErrors([]);
    // (2026-06-14) useTransition 包整段: 按钮立刻 disabled 防双击, transition 结束 (含 parse 错误早退) isPending 自然 false
    startTransition(async () => {
      const text = await file.text();
      const parsed = parseJsonText(text);
      if (parsed.errors.length) {
        setParseErrors(parsed.errors);
        return;
      }
      try {
        const { task_id } = await startBatch({
          dataset_id: datasetId,
          items: parsed.items,
        });
        setActiveTask({
          errors: [],
          failed: ZERO,
          processed: ZERO,
          state: "queued",
          success: ZERO,
          task_id,
          total: parsed.items.length,
        });
      } catch {
        // 静默: 启动失败不弹错
      }
    });
  };

  return (
    <div className="h-full overflow-y-auto space-y-8">
      <BatchTaskPolling activeTask={activeTask} setActiveTask={setActiveTask} />
      <PageHero
        eyebrow={tr("知识图谱 · 批量导入")}
        title={tr("批量导入")}
        meta={tr("1s 轮询")}
        description={tr("大批量 → 后台任务 → 实时轮询进度。")}
        backHref="/knowledge/graph"
        backLabel={tr("返回知识图谱")}
      />

      <Reveal delay={DELAY.heroStep2}>
        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-lg">{tr("操作")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <Input
                type="file"
                accept=".json"
                onChange={(evt) => setFile((evt.target as HTMLInputElement).files?.[ZERO] ?? null)}
                data-testid="batch-file"
                className="num text-base file:mr-3 file:rounded-md file:border-0 file:bg-ink file:px-3 file:py-1.5 file:text-base file:font-medium file:text-paper file:transition-shadow hover:file:shadow-[0_4px_12px_hsl(0_0%_0%/0.10)]"
              />
              <Button
                onClick={handleSubmit}
                disabled={!file || isPending}
                className="h-10 gap-2 rounded-full bg-ink px-5 text-base text-paper hover:bg-ink/90 hover:shadow-[0_4px_12px_hsl(0_0%_0%/0.10),0_2px_4px_hsl(0_0%_0%/0.06)]"
                data-testid="batch-submit"
              >
                {submitLabel}
              </Button>
              <Button asChild variant="outline">
                <a href="/templates/knowledge-import.json" download>
                  {tr("下载模板")}
                </a>
              </Button>
            </div>
            <AnimateUp show={parseErrors.length > ZERO} enterFromTop className="rounded-lg">
              <ErrorBanner
                variant="destructive"
                descriptionNode={
                  <ul className="list-disc space-y-1 pl-5 text-sm">
                    {parseErrors.map((err, idx) => (
                      <li key={idx}>{err}</li>
                    ))}
                  </ul>
                }
                description=""
                dataTestid="batch-parse-errors"
              />
            </AnimateUp>
          </CardContent>
        </Card>
      </Reveal>

      {activeTask && (
        <AnimateUp show={Boolean(activeTask)}>
          <Card className="border-border/60">
            <CardHeader>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <CardTitle className="text-lg">{tr("活跃任务")}</CardTitle>
                <span className="num text-sm text-muted-foreground">{activeTask.task_id}</span>
              </div>
            </CardHeader>
            <CardContent>
              <div className="mb-3 flex items-center gap-3">
                <TaskStatusBadge state={activeTask.state} />
                <span
                  className="num text-base text-muted-foreground"
                  data-testid="batch-progress-text"
                >
                  {activeTask.processed} / {activeTask.total}
                </span>
              </div>
              <Progress value={progressValue} className="h-1.5" />
              <div className="mt-4 flex items-baseline gap-6 text-base">
                <span className="num">
                  <span className="eyebrow mr-1">{tr("成功")}</span>
                  <span className="text-moss">{activeTask.success}</span>
                </span>
                <span className="num">
                  <span className="eyebrow mr-1">{tr("失败")}</span>
                  <span className={cn(failedClassName)}>{activeTask.failed}</span>
                </span>
              </div>
              {activeTask.errors.length > ZERO && (
                <details className="mt-3">
                  <summary className="num cursor-pointer text-sm text-destructive transition-colors hover:text-destructive/80">
                    {tr("查看错误 ({count})", { count: activeTask.errors.length })}
                  </summary>
                  <ul className="mt-2 max-h-48 list-disc space-y-0.5 overflow-auto pl-5 text-sm text-muted-foreground">
                    {activeTask.errors.slice(ZERO, FIFTY).map((err, idx) => (
                      <li key={idx}>{err}</li>
                    ))}
                  </ul>
                </details>
              )}
            </CardContent>
          </Card>
        </AnimateUp>
      )}
    </div>
  );
};
