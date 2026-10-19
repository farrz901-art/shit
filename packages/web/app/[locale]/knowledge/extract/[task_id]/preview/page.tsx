"use client";
// 抽取预览 + 3 出口页 (2026-07-01 markdown extract KG PR4 v3)
// 实体/关系可编辑 DataTable + 勾选 + 3 个出口按钮 (写 Neo4j / 导出 JSONL / 导出 Cypher)
// 重构 (2026-07-01 深度): 抽 PreviewTable + useMapToggle + usePreviewState
//                       + usePreviewActions + usePreviewColumns + preview-content
//                       page 只做路由 + render 分支 (~50 行, ~14 statement)
/* oxlint-disable max-statements -- 预览页逻辑连贯, 拆分增加阅读成本 */
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { ZERO } from "@/const";
import { fetchExtractPreview } from "@/lib/api/knowledge";
import { usePreviewState } from "./_hooks/use-preview-state";
import { usePreviewActions } from "./_hooks/use-preview-actions";
import { usePreviewColumns } from "./_hooks/use-preview-columns";
import { ContentView, EmptyView, LoadingView } from "./_components/preview-content";

/**
 * 预览页路由参数
 * @property params - 路由参数 (含 task_id)
 */
interface PageProps {
  params: { task_id: string };
}

/**
 * PreviewPage - 抽取预览页 (实体/关系可编辑 DataTable + 勾选 + 出口按钮)
 * @param props - 组件属性
 * @client-bff
 */
const PreviewPage = ({ params }: PageProps) => {
  const tr = useTranslations();
  const searchParams = useSearchParams();
  const dataset = searchParams.get("dataset") ?? "motor";
  const taskId = params.task_id;
  const previewQuery = useQuery({
    queryKey: ["kg", "extract-preview", taskId, dataset],
    queryFn: () => fetchExtractPreview(taskId, dataset),
    enabled: Boolean(taskId),
  });
  const preview = usePreviewState({ previewQuery, taskId, dataset });
  const actions = usePreviewActions({
    taskId,
    dataset,
    saveEdits: preview.saveEdits,
    tr,
  });
  const { entityColumns, relationColumns } = usePreviewColumns();
  const canCommit = preview.totalSelected > ZERO && !actions.isPending;

  if (previewQuery.isLoading) {
    return <LoadingView />;
  }
  if (!preview.hasData) {
    return <EmptyView title={tr("预览实体与关系")} eyebrow={tr("知识图谱抽取")} />;
  }
  return (
    <ContentView
      taskId={taskId}
      dataset={dataset}
      totalSelected={preview.totalSelected}
      error={actions.error}
      entities={preview.entities}
      relations={preview.relations}
      selectedEntityCount={preview.selectedEntityCount}
      selectedRelationCount={preview.selectedRelationCount}
      entityColumns={entityColumns}
      relationColumns={relationColumns}
      entityState={preview.entityState}
      relationState={preview.relationState}
      isPending={actions.isPending}
      canCommit={canCommit}
      commitOpen={actions.commitOpen}
      onCommitOpenChange={actions.setCommitOpen}
      onSaveClick={actions.handleSaveClick}
      onCommitClick={() => actions.setCommitOpen(true)}
      onExportJsonl={() => void actions.handleExport("jsonl")}
      onExportCypher={() => void actions.handleExport("cypher")}
      onCommitConfirm={() => void actions.handleCommit()}
    />
  );
};

/** @client-bff */
export default PreviewPage;
