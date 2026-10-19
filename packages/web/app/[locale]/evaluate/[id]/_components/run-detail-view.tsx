"use client";
// 单次评估详情 client 子组件 (2026-06-12, Task 19).
// 父 page 改 RSC 后, 数据从 server fetch 灌进来, 客户端管 running 状态轮询 (router.refresh) + cancel/delete 按钮.
// 跟 Task 18 DatasetDocumentsTable 模板同型.
// (2026-06-14) shadcn: confirm() → useConfirm/AppConfirm, alert() → toast.error,
//   Button → shadcn Button.
// (2026-06-14) react-use: useInterval 替 setInterval + useEffect + clearInterval 模板
import type { EvaluationRun, EvaluationStatus } from "@/lib/evaluate/types";
import { Reveal } from "@/components/motion/animated";
import { PageHeader } from "@/components/common/navigation/app-page-header";
import { AppConfirm } from "@/components/common";
import { Loader2 } from "lucide-react";
import { MetricBar } from "./metric-bar";
import { SampleTable } from "./sample-table";
import { StatCard } from "@/components/common/display/app-stat-card";
import { deleteRun } from "@/app/[locale]/_actions/evaluate";
import { toast } from "sonner";
import { usePolling } from "@/lib/hooks";
import { DELAY } from "@/lib/motion";
import { useRouter } from "@/i18n/navigation";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { buildMetricDefs, mapSamplesForTable } from "./metric-defs";
import { RunActions } from "./run-actions";

/** 终态列表 @shared */
const TERMINAL: EvaluationStatus[] = ["completed", "failed", "cancelled"];
/** 轮询间隔 (ms) @shared */
const POLL_INTERVAL_MS = 2000;
/** 指标默认值 (无数据时) @shared */
const ZERO_METRIC = 0;

/** RunningBanner - 运行中提示条
 * @param successful - 成功数
 * @param failed - 失败数
 * @param total - 总数
 * @param trans - i18n 翻译函数
 * @returns 运行中提示 JSX
 * @client-bff
 */
const RunningBanner = ({
  successful,
  failed,
  total,
  trans,
}: {
  successful: number;
  failed: number;
  total: number;
  trans: ReturnType<typeof useTranslations>;
}) => (
  <Reveal delay={DELAY.secondary}>
    <div className="rounded-lg border border-status-running/30 bg-status-running/10 p-4 text-sm text-status-running">
      <Loader2 className="mr-2 inline-block h-4 w-4 animate-spin" aria-hidden="true" />
      {trans("评估进行中, 每 2 秒自动刷新…")}{" "}
      {trans("{n1} / {n2} 已完成", { n1: successful + failed, n2: total })}
    </div>
  </Reveal>
);

/** FailedBanner - 失败提示条
 * @param errorMessage - 错误信息
 * @param trans - i18n 翻译函数
 * @returns 失败提示 JSX
 * @client-bff
 */
const FailedBanner = ({
  errorMessage,
  trans,
}: {
  errorMessage: string;
  trans: ReturnType<typeof useTranslations>;
}) => (
  <div className="rounded-lg border border-clay/30 bg-clay/5 p-4 text-sm text-clay">
    {trans("错误:")} {errorMessage}
  </div>
);

/** 时长小数位数 @shared */
const DURATION_DIGITS = 1;
/** 空计数默认值 @shared */
const EMPTY_COUNT = 0;

/** MetricsSection - 指标/样本展示区域
 * @param run - 评估运行数据
 * @param trans - i18n 翻译函数
 * @returns 指标区域 JSX
 * @client-bff
 */
const MetricsSection = ({
  run,
  trans,
}: {
  run: EvaluationRun;
  trans: ReturnType<typeof useTranslations>;
}) => {
  let durationDisplay = "—";
  if (run.duration_seconds) {
    durationDisplay = `${run.duration_seconds.toFixed(DURATION_DIGITS)}s`;
  }
  const hasSamples = run.samples.length > EMPTY_COUNT;

  return (
    <>
      <Reveal delay={DELAY.heroStep2}>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[640px_1fr]">
          <div className="rounded-lg border border-border/40 bg-card p-5 space-y-4">
            <h3 className="text-sm font-medium text-muted-foreground">{trans("平均指标")}</h3>
            {run.avg_metrics ? (
              <>
                {buildMetricDefs(trans).map((metric) => (
                  <MetricBar
                    key={metric.key}
                    label={metric.label}
                    value={run.avg_metrics?.[metric.key] ?? ZERO_METRIC}
                  />
                ))}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">{trans("暂无评估指标")}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4 content-start">
            <StatCard label={trans("总样本")} value={run.total_samples} accent="indigo" index={0} />
            <StatCard label={trans("总耗时")} value={durationDisplay} accent="ink" index={1} />
            <StatCard label={trans("成功")} value={run.successful} accent="moss" index={2} />
            <StatCard label={trans("失败")} value={run.failed} accent="clay" index={3} />
          </div>
        </div>
      </Reveal>

      {hasSamples && (
        <Reveal delay={DELAY.detail}>
          <div>
            <h3 className="mb-3 text-sm font-medium text-muted-foreground">
              {trans("逐条结果 ({n_} 条)", { n_: run.samples.length })}
            </h3>
            <SampleTable samples={mapSamplesForTable(run.samples)} />
          </div>
        </Reveal>
      )}
    </>
  );
};

/** 确认对话框状态 hook (取消/删除)
 * @param run - 评估运行数据
 * @param trans - i18n 翻译函数
 * @param router - next-intl router
 * @returns 确认对话框状态及回调
 * @client-bff
 */
const useConfirmHandlers = (
  run: EvaluationRun,
  trans: ReturnType<typeof useTranslations>,
  router: ReturnType<typeof useRouter>,
) => {
  const [confirmOpen, setConfirmOpen] = useState<{ description: string; title: string } | null>(
    null,
  );
  const [pendingAction, setPendingAction] = useState<"cancel" | "delete" | null>(null);

  const onCancel = () => {
    setPendingAction("cancel");
    setConfirmOpen({
      description: trans("确认取消这次评估? 已跑的题会保留"),
      title: trans("取消评估"),
    });
  };

  const onDelete = () => {
    setPendingAction("delete");
    setConfirmOpen({
      description: trans("确认删除这次评估?"),
      title: trans("删除评估"),
    });
  };

  const handleConfirm = async () => {
    setConfirmOpen(null);
    if (pendingAction === "cancel") {
      // 取消仍走 BFF multipart client API (lib/api/evaluate.ts cancelRun)
      const { cancelRun } = await import("@/lib/api/evaluate");
      await cancelRun(run.id);
      router.refresh();
    } else if (pendingAction === "delete") {
      const result = await deleteRun(String(run.id));
      if (result.ok) {
        router.push("/evaluate");
      } else {
        // (2026-06-14) shadcn: alert() → toast.error
        toast.error(result.error);
      }
    }
    setPendingAction(null);
  };

  const clearConfirm = () => {
    setConfirmOpen(null);
    setPendingAction(null);
  };

  return { clearConfirm, confirmOpen, handleConfirm, onCancel, onDelete };
};

/** RunDetailView - 单次评估详情 client 子组件
 * @param run - 评估运行数据
 * @param id - 评估 ID
 * @returns 评估详情 JSX
 * @client-bff
 */
export const RunDetailView = ({ run, id }: { run: EvaluationRun; id: string }) => {
  const trans = useTranslations();
  const router = useRouter();
  // (2026-06-14) react-use: useInterval 替 setInterval + useEffect + clearInterval 模板.
  // Delay=null 时 useInterval 内部 clearInterval, 跟之前运行中注册/停止效果一致.
  const shouldPoll = !TERMINAL.includes(run.status);
  usePolling(() => router.refresh(), shouldPoll ? POLL_INTERVAL_MS : null);

  const { clearConfirm, confirmOpen, handleConfirm, onCancel, onDelete } = useConfirmHandlers(
    run,
    trans,
    router,
  );

  const hasMetrics = run.avg_metrics !== null;

  return (
    <div className="h-full overflow-y-auto space-y-8">
      <PageHeader
        backHref="/evaluate"
        title={trans("评估详情")}
        actions={
          <RunActions
            isPending={confirmOpen !== null}
            onCancel={onCancel}
            onDelete={onDelete}
            status={run.status}
            translate={trans}
          />
        }
      />
      <h1 className="display text-3xl tracking-tight md:text-4xl">
        {run.dataset_name ?? trans("评估 #{n_}", { n_: id })}
      </h1>

      {run.status !== "completed" && run.status !== "failed" && run.status !== "cancelled" && (
        <RunningBanner
          successful={run.successful}
          failed={run.failed}
          total={run.total_samples}
          trans={trans}
        />
      )}

      {run.status === "failed" && run.error_message && (
        <FailedBanner errorMessage={run.error_message} trans={trans} />
      )}

      {hasMetrics && <MetricsSection run={run} trans={trans} />}
      {/* (2026-06-14) shadcn: confirm() 替 AppConfirm controlled (项目 AppConfirm 是 controlled) */}
      <AppConfirm
        open={confirmOpen !== null}
        onOpenChange={(open) => {
          if (!open) {
            clearConfirm();
          }
        }}
        title={confirmOpen?.title ?? ""}
        description={confirmOpen?.description}
        variant="destructive"
        onConfirm={handleConfirm}
      />
    </div>
  );
};
