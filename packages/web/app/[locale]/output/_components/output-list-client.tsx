"use client";
// /output 任务列表 client 子组件 (Task 24, 2026-06-12 redesign)
// 模式: RSC 预取 + HydrationBoundary, 客户端 useQuery 接管 5s 轮询.
// QueryKey 跟 RSC 端 qKeys.output.list() 一致, staleTime: Infinity 让首屏不重拉.
// (2026-06-10 redesign; 2026-06-11 改用 DataTable) UI 跟 SWR 版完全一致:
//   - DataTable 4 列: 文件名 / 状态 / 进度 / 操作
//   - completed 任务显示「查看产物」+「下载全部」(走 taskDownload)
//   - 「下载全部」失败用 ErrorBanner 反馈 (跟 spec 一致, 持续可见不阻塞)
import type { IngestTask } from "@/lib/api";
import { AnimateUp, Reveal } from "@/components/motion/animated";
import { type ColumnDef, DataTable, ErrorBanner } from "@/components/common";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { LocalizedLink } from "@/components/i18n";
import { PageHero } from "@/components/common/navigation/app-page-hero";

import { useOutputList, type TranslateFn } from "../_hooks/use-output-list";
import {
  formatRowName,
  progressOf,
  renderProgressCell,
  renderActionsCell,
  StateBadge,
} from "./output-card";

/**
 * renderMainContent - 渲染主内容区 (错误 / 空态 / 表格)
 * @param displayError - 展示的错误信息
 * @param list - 任务列表
 * @param options - 配置选项
 * @returns JSX
 */
const renderMainContent = (
  displayError: string | null,
  list: IngestTask[],
  options: {
    columns: ColumnDef<IngestTask>[];
    setDownloadError: (msg: string | null) => void;
    translate: TranslateFn;
  },
): ReactNode => {
  if (displayError) {
    return (
      <ErrorBanner
        variant="destructive"
        description={displayError}
        action={
          <Button variant="ghost" size="sm" onClick={() => options.setDownloadError(null)}>
            {options.translate("重试")}
          </Button>
        }
      />
    );
  }
  if (!list.length) {
    return (
      <AnimateUp show={!list.length} lift={0}>
        <div
          key="empty"
          className="rounded-2xl border border-dashed border-border/80 bg-card/40 px-8 py-16 text-center"
        >
          <div className="display mb-3 text-2xl text-muted-foreground/60">
            {options.translate("还没有任务")}
          </div>
          <p className="text-base text-muted-foreground">
            {options.translate("点右上")}{" "}
            <span className="text-clay">{options.translate("+ 新转换")}</span>{" "}
            {options.translate("上传文件。")}
          </p>
        </div>
      </AnimateUp>
    );
  }
  return (
    <Reveal>
      <DataTable<IngestTask>
        dataSource={list}
        columns={options.columns}
        rowKey="id"
        rowClassName={(rowData) => {
          if (rowData.state === "failed") {
            return "bg-destructive/5";
          }
          return "";
        }}
      />
    </Reveal>
  );
};

/**
 * OutputListClient - /output 任务列表 client 组件
 * @client-bff
 */
export const OutputListClient = () => {
  const {
    downloadError,
    downloading,
    isLoading,
    list,
    onDownload,
    queryError,
    setDownloadError,
    translate,
  } = useOutputList();

  const taskColumns: ColumnDef<IngestTask>[] = [
    {
      // (2026-06-11) 首列: 任务 id → 首个上传文件的 name (input_files, 用户上传时的原名)
      // Running/queued 时 input_files 一定存在 (上传时记录的), 所以基本不会 fallback 到 id
      accessorKey: "filename",
      cell: (ctx) => {
        const { displayName } = formatRowName(ctx.row.original);
        return (
          <span
            className="num block max-w-xs truncate font-medium text-foreground"
            title={ctx.row.original.id}
          >
            {displayName}
          </span>
        );
      },
      header: () => translate("文件名"),
    },
    {
      accessorKey: "state",
      cell: (ctx) => (
        <StateBadge state={ctx.row.original.state} progress={progressOf(ctx.row.original)} />
      ),
      header: () => translate("状态"),
      size: 120,
    },
    {
      accessorKey: "progress",
      cell: (ctx) => renderProgressCell(ctx.row.original, translate),
      header: () => translate("进度"),
    },
    {
      meta: { align: "right" },
      accessorKey: "actions",
      cell: (ctx) => renderActionsCell(ctx.row.original, { downloading, onDownload }, translate),
      header: () => translate("操作"),
      size: 220,
    },
  ];

  if (isLoading) {
    return <div className="text-base text-muted-foreground">{translate("加载中…")}</div>;
  }

  // 错误展示: 优先下载错误
  const displayError = downloadError ?? queryError;

  return (
    <div className="h-full overflow-y-auto">
      <PageHero
        className="mb-8"
        eyebrow="Document Structuring"
        title={translate("文档结构化")}
        description={translate("把 PDF/Office/CAD 拖进来, 后台跑, 跑完来看。")}
        actions={
          <LocalizedLink
            href="/output/new"
            className="rounded-lg bg-clay px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-clay/90"
          >
            {translate("+ 新转换")}
          </LocalizedLink>
        }
      />

      {renderMainContent(displayError, list, {
        columns: taskColumns,
        setDownloadError,
        translate,
      })}
    </div>
  );
};
