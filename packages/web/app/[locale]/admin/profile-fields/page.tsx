"use client";
// 画像字段配置管理页 (2026-06-22 buyer-profile spec)
// DataTable 展示所有字段配置 + 新增 / 编辑 / 软删除

import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { AppConfirm } from "@/components/common/confirm/app-confirm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { useTranslations } from "next-intl";
import { useFieldConfigs } from "@/app/[locale]/buyers/_lib/buyer-profile/hooks";
import { useToggle } from "react-use";
import { FileText, ListTree, Plus, ToggleLeft } from "lucide-react";
import type { ProfileFieldConfig } from "@/app/[locale]/buyers/_lib/buyer-profile/types";
import { CreateFieldDialog } from "./_components/create-field-dialog";
import { EditFieldDialog } from "./_components/edit-field-dialog";
import { useProfileFieldsHandlers } from "./_hooks/use-profile-fields-handlers";

/** 字段类型列宽度 */
const FIELD_TYPE_COL_WIDTH = 100;
/** 状态列宽度 */
const STATUS_COL_WIDTH = 80;
/** 操作列宽度 */
const ACTIONS_COL_WIDTH = 120;

/** 空表单默认值 */
const EMPTY_FORM = { code: "", extraction_prompt: "", field_type: "text", label: "" };

/**
 * 根据字段类型返回对应的图标
 * @param fieldType - 字段类型
 * @returns 图标 React 节点
 */
const getTypeIcon = (fieldType: string) => {
  switch (fieldType) {
    case "select": {
      return <ListTree className="h-3 w-3" />;
    }
    case "boolean": {
      return <ToggleLeft className="h-3 w-3" />;
    }
    default: {
      return <FileText className="h-3 w-3" />;
    }
  }
};

/**
 * 构建字段配置列表列定义
 * @param translate - i18n 翻译函数
 * @param onEdit - 编辑回调
 * @param onToggleActive - 停用/激活回调
 * @returns DataTable 列定义数组
 */
const buildColumns = (
  translate: (key: string) => string,
  onEdit: (cfg: ProfileFieldConfig) => void,
  onToggleActive: (cfg: ProfileFieldConfig) => void,
): ColumnDef<ProfileFieldConfig>[] => [
  {
    accessorKey: "label",
    header: () => translate("标签"),
    id: "label",
    size: 120,
  },
  {
    accessorKey: "code",
    header: () => translate("编码"),
    id: "code",
    size: 120,
  },
  {
    accessorKey: "field_type",
    cell: (ctx) => (
      <div className="flex items-center gap-1">
        {getTypeIcon(ctx.row.original.field_type)}
        <span className="text-sm">{ctx.row.original.field_type}</span>
      </div>
    ),
    header: () => translate("类型"),
    id: "field_type",
    size: FIELD_TYPE_COL_WIDTH,
  },
  {
    accessorKey: "is_active",
    cell: (ctx) => (
      <Badge variant={ctx.row.original.is_active ? "default" : "secondary"}>
        {ctx.row.original.is_active ? translate("激活") : translate("停用")}
      </Badge>
    ),
    header: () => translate("状态"),
    id: "is_active",
    size: STATUS_COL_WIDTH,
  },
  {
    accessorKey: "sort_order",
    header: () => translate("排序"),
    id: "sort_order",
    size: 60,
  },
  {
    cell: (ctx) => (
      <div className="flex gap-1">
        <Button onClick={() => onEdit(ctx.row.original)} size="sm" variant="ghost">
          {translate("编辑")}
        </Button>
        <Button onClick={() => onToggleActive(ctx.row.original)} size="sm" variant="ghost">
          {ctx.row.original.is_active ? translate("停用") : translate("激活")}
        </Button>
      </div>
    ),
    header: () => translate("操作"),
    id: "actions",
    size: ACTIONS_COL_WIDTH,
  },
];

/**
 * 画像字段配置管理页面 — DataTable 展示所有字段配置 + 新增 / 编辑 / 软删除
 * @returns 字段配置管理页面
 * @client-bff
 */
const ProfileFieldsPage = () => {
  const translate = useTranslations();
  const { data: configs = [], error } = useFieldConfigs();

  const {
    createForm,
    createMutation,
    editForm,
    editTarget,
    errorMessage,
    handleCreate,
    handleEdit,
    handleEditSave,
    handleToggleActive,
    handleToggleConfirm,
    setCreateForm,
    setEditForm,
    setEditTarget,
    setToggleTarget,
    toggleTarget,
    updateMutation,
  } = useProfileFieldsHandlers();

  const [showCreateDialog, toggleShowCreateDialog] = useToggle(false);

  /** 取消新增, 关闭弹框 + 重置表单 */
  const handleCreateCancel = () => {
    toggleShowCreateDialog(false);
    setCreateForm(() => EMPTY_FORM);
  };

  /** 取消编辑, 清空编辑目标 */
  const handleEditCancel = () => {
    setEditTarget(null);
  };

  const columns = buildColumns(translate, handleEdit, handleToggleActive);

  return (
    <div className="space-y-6">
      <PageHero
        actions={
          <Button onClick={() => toggleShowCreateDialog(true)} size="sm">
            <Plus className="mr-1 h-4 w-4" />
            {translate("新增字段")}
          </Button>
        }
        eyebrow="Admin"
        title={translate("画像字段配置")}
      />

      {error && (
        <ErrorBanner
          description={error instanceof Error ? error.message : translate("出错了")}
          variant="destructive"
        />
      )}
      {errorMessage && <ErrorBanner description={errorMessage} variant="destructive" />}

      <DataTable<ProfileFieldConfig>
        columns={columns}
        dataSource={configs}
        emptyText={<DataEmpty icon={FileText} title={translate("暂无字段配置")} />}
        rowKey="code"
      />

      {/* 新增对话框 */}
      <CreateFieldDialog
        createForm={createForm}
        createMutation={createMutation}
        handleCreate={handleCreate}
        setCreateForm={setCreateForm}
        showCreateDialog={showCreateDialog}
        translate={translate}
        onCancel={handleCreateCancel}
      />

      {/* 编辑对话框 */}
      <EditFieldDialog
        editForm={editForm}
        handleEditSave={handleEditSave}
        setEditForm={setEditForm}
        showEditDialog={Boolean(editTarget)}
        translate={translate}
        updateMutation={updateMutation}
        onCancel={handleEditCancel}
      />

      {/* 停用/激活确认 */}
      <AppConfirm
        confirmText={toggleTarget?.is_active ? translate("停用") : translate("激活")}
        description={
          toggleTarget?.is_active
            ? translate("停用后该字段将不再被自动提取")
            : translate("激活后该字段将恢复自动提取")
        }
        onConfirm={handleToggleConfirm}
        onOpenChange={(open) => {
          if (!open) {
            setToggleTarget(null);
          }
        }}
        open={Boolean(toggleTarget)}
        title={toggleTarget?.is_active ? translate("确认停用?") : translate("确认激活?")}
        variant="destructive"
      />
    </div>
  );
};

export default ProfileFieldsPage;
