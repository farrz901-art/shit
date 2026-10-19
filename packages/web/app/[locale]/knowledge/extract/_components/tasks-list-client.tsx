"use client";
// KG 任务列表容器 (2026-07-03): PageHero + AppToggle (抽取/批量) + DataTable + 弹框状态 + 刷新
/* oxlint-disable max-statements -- 容器含 query + tab + 弹框 + 刷新 4 个状态, 拆分增加参数传递 */
import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Plus, RefreshCw } from "lucide-react";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { AppToggle } from "@/components/common/input/app-toggle";
import { Button } from "@/components/ui/button";
import { fetchExtractTasks, type ExtractTaskRow } from "@/lib/api/knowledge";
import { DEFAULT_PAGE_SIZE, ZERO } from "@/const";
import ExtractTasksTable from "./extract-tasks-table";
import BatchTasksTable from "./batch-tasks-table";
import ExtractCreateDialog from "./extract-create-dialog";

/** 任务类型 (抽取 / 批量) */
type TaskKind = "kg_extract" | "kg_batch";

/**
 * TasksListClient - KG 任务列表容器
 * @client-bff
 */
const TasksListClient = () => {
  const tr = useTranslations();
  const [activeTab, setActiveTab] = useState<TaskKind>("kg_extract");
  const [page, setPage] = useState(ZERO);
  const [dialogOpen, setDialogOpen] = useState(false);

  const tasksQuery = useQuery({
    queryFn: () =>
      fetchExtractTasks({
        kind: activeTab,
        limit: DEFAULT_PAGE_SIZE,
        offset: page * DEFAULT_PAGE_SIZE,
      }),
    queryKey: ["kg", "tasks", activeTab, page],
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  const handleTabChange = (value: string) => {
    setActiveTab(value as TaskKind);
    setPage(ZERO);
  };

  const handleRefresh = () => {
    void tasksQuery.refetch();
  };

  const handleDialogChange = (open: boolean) => {
    setDialogOpen(open);
    if (!open) {
      void tasksQuery.refetch();
    }
  };

  const rows: ExtractTaskRow[] = tasksQuery.data?.items ?? [];
  const total = tasksQuery.data?.total ?? ZERO;
  const totalSuccess = tasksQuery.data?.total_success ?? ZERO;
  const totalFailed = tasksQuery.data?.total_failed ?? ZERO;
  const error = tasksQuery.error instanceof Error ? tasksQuery.error.message : null;
  const isLoading = tasksQuery.isLoading || tasksQuery.isFetching;

  return (
    <div className="space-y-6">
      <PageHero
        eyebrow={tr("知识图谱")}
        title={tr("任务列表")}
        description={tr("查看所有 KG 抽取与批量任务")}
        actions={
          <>
            {activeTab === "kg_extract" ? (
              <Button onClick={() => setDialogOpen(true)} data-testid="new-extract-btn">
                <Plus className="mr-1 h-4 w-4" />
                {tr("新建提取")}
              </Button>
            ) : null}
            <Button variant="outline" onClick={handleRefresh} data-testid="refresh-btn">
              <RefreshCw className="mr-1 h-4 w-4" />
              {tr("刷新")}
            </Button>
          </>
        }
      />

      <AppToggle
        options={[
          { value: "kg_extract", label: tr("抽取") },
          { value: "kg_batch", label: tr("批量") },
        ]}
        value={activeTab}
        onChange={handleTabChange}
        dataTestid="tasks-tab"
      />

      {activeTab === "kg_extract" ? (
        <ExtractTasksTable
          error={error}
          loading={isLoading}
          onPageChange={setPage}
          onRetry={handleRefresh}
          page={page}
          pageSize={DEFAULT_PAGE_SIZE}
          rows={rows}
          total={total}
          totalFailed={totalFailed}
          totalSuccess={totalSuccess}
        />
      ) : (
        <BatchTasksTable
          error={error}
          loading={isLoading}
          onPageChange={setPage}
          onRetry={handleRefresh}
          page={page}
          pageSize={DEFAULT_PAGE_SIZE}
          rows={rows}
          total={total}
          totalFailed={totalFailed}
          totalSuccess={totalSuccess}
        />
      )}

      <ExtractCreateDialog open={dialogOpen} onOpenChange={handleDialogChange} />
    </div>
  );
};

/** @client-bff */
export default TasksListClient;
