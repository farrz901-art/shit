"use client";
// preview-content — 预览页的 3 个渲染分支 (loading / empty / content)
// preview page 接 use-preview-state + 调 3 个 action, 然后把数据透传给本组件
import { useTranslations } from "next-intl";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Button } from "@/components/ui/button";
import { AppConfirm } from "@/components/common/confirm";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { PreviewTable, type AnyColumn } from "./preview-table";
import type { ExtractPreviewEntity, ExtractPreviewRelation } from "@/lib/api/knowledge";
import type { useMapToggle } from "../_hooks/use-map-toggle";

type EntityState = ReturnType<typeof useMapToggle<ExtractPreviewEntity>>;
type RelationState = ReturnType<typeof useMapToggle<ExtractPreviewRelation>>;

/**
 * 预览页内容视图属性
 * @property taskId - 任务 ID
 * @property dataset - 数据集名称
 * @property totalSelected - 总选中数
 * @property error - 错误信息
 * @property entities - 实体列表
 * @property relations - 关系列表
 * @property selectedEntityCount - 已选实体数
 * @property selectedRelationCount - 已选关系数
 * @property entityColumns - 实体列定义
 * @property relationColumns - 关系列定义
 * @property entityState - 实体状态管理
 * @property relationState - 关系状态管理
 * @property isPending - 操作是否 pending
 * @property canCommit - 是否可提交
 * @property commitOpen - 提交确认弹框是否打开
 * @property onCommitOpenChange - 提交弹框开关回调
 * @property onSaveClick - 保存点击回调
 * @property onCommitClick - 提交点击回调
 * @property onExportJsonl - 导出 JSONL 回调
 * @property onExportCypher - 导出 Cypher 回调
 * @property onCommitConfirm - 确认提交回调
 */
interface ContentViewProps {
  taskId: string;
  dataset: string;
  totalSelected: number;
  error: string | null;
  entities: ExtractPreviewEntity[];
  relations: ExtractPreviewRelation[];
  selectedEntityCount: number;
  selectedRelationCount: number;
  entityColumns: AnyColumn<ExtractPreviewEntity>[];
  relationColumns: AnyColumn<ExtractPreviewRelation>[];
  entityState: EntityState;
  relationState: RelationState;
  isPending: boolean;
  canCommit: boolean;
  commitOpen: boolean;
  onCommitOpenChange: (open: boolean) => void;
  onSaveClick: () => void;
  onCommitClick: () => void;
  onExportJsonl: () => void;
  onExportCypher: () => void;
  onCommitConfirm: () => void;
}

/**
 * 预览页主内容视图, 包含实体表/关系表/操作按钮/确认弹框
 * @param props - 组件属性
 * @client-bff
 */
export const ContentView = (props: ContentViewProps) => {
  const {
    taskId,
    dataset,
    totalSelected,
    error,
    entities,
    relations,
    selectedEntityCount,
    selectedRelationCount,
    entityColumns,
    relationColumns,
    entityState,
    relationState,
    isPending,
    canCommit,
    commitOpen,
    onCommitOpenChange,
    onSaveClick,
    onCommitClick,
    onExportJsonl,
    onExportCypher,
    onCommitConfirm,
  } = props;
  const tr = useTranslations();
  return (
    <div className="space-y-6">
      <PageHero
        eyebrow={tr("知识图谱抽取")}
        title={tr("预览实体与关系")}
        description={`task_id: ${taskId} | dataset: ${dataset} | 已选 ${totalSelected} 项`}
      />

      {error ? (
        <ErrorBanner variant="destructive" title={tr("导入失败")} description={error} />
      ) : null}

      <PreviewTable
        title={tr("实体")}
        dataSource={entities}
        rowKey="id"
        columns={entityColumns}
        actions={entityState.actions}
        allSelected={entityState.allSelected}
        selectedCount={selectedEntityCount}
        emptyText={<div className="text-sm text-muted-foreground">{tr("暂无实体")}</div>}
      />

      <PreviewTable
        title={tr("关系")}
        dataSource={relations}
        rowKey="id"
        columns={relationColumns}
        actions={relationState.actions}
        allSelected={relationState.allSelected}
        selectedCount={selectedRelationCount}
        emptyText={<div className="text-sm text-muted-foreground">{tr("暂无关系")}</div>}
      />

      <div className="flex flex-wrap gap-3">
        <Button onClick={onSaveClick} variant="outline" disabled={isPending}>
          {tr("保存编辑")}
        </Button>
        <Button onClick={onCommitClick} disabled={!canCommit}>
          {tr("写 Neo4j")}
        </Button>
        <Button onClick={onExportJsonl} variant="outline" disabled={!canCommit}>
          {tr("导出 JSONL")}
        </Button>
        <Button onClick={onExportCypher} variant="outline" disabled={!canCommit}>
          {tr("导出 Cypher")}
        </Button>
      </div>

      <AppConfirm
        open={commitOpen}
        onOpenChange={onCommitOpenChange}
        title={tr("确认写 Neo4j")}
        description={tr(`写 ${dataset} dataset 操作不可撤销,选中的实体/关系会被合并到知识图谱.`)}
        onConfirm={onCommitConfirm}
        confirmText={tr("写 Neo4j")}
        variant="destructive"
      />
    </div>
  );
};

/**
 * LoadingView - 预览页骨架屏加载态
 * @client-bff
 */
export const LoadingView = () => (
  <div className="space-y-6 animate-pulse">
    <div className="h-8 w-48 bg-muted rounded" />
    <div className="h-4 w-96 bg-muted rounded" />
    <div className="h-32 bg-muted rounded" />
    <div className="h-32 bg-muted rounded" />
  </div>
);

/**
 * 空态视图属性
 * @property title - 页面标题
 * @property eyebrow - 页面副标题
 */
interface EmptyViewProps {
  title: string;
  eyebrow: string;
}

/**
 * 空态视图, 仅显示 PageHero
 * @param props.title - 页面标题
 * @param props.eyebrow - 页面副标题
 * @client-bff
 */
export const EmptyView = ({ title, eyebrow }: EmptyViewProps) => (
  <div className="space-y-6">
    <PageHero eyebrow={eyebrow} title={title} description="" />
  </div>
);
