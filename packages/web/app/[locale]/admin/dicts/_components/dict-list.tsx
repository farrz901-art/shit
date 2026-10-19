"use client";
// 字典项列表 (2026-06-19 lookup module Task 9)
// 展示 key / label_zh / label_en / sort / is_active, 行内 "编辑" 触发 DictItemEditor.
// "删除" / "历史" 只触发父组件回调 — 由 page 接住, 弹出 DictItemDeleteDialog / DictAuditLog.
// 用 DataTable + DataEmpty; 行 expandedRowRender 在编辑态展开 DictItemEditor.
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { type LookupItem, type LookupItemPatchInput } from "@/lib/api/lookups";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { Database } from "lucide-react";
import { DictItemEditor } from "./dict-item-editor";
import { useState } from "react";
import { useTranslations } from "next-intl";

/** 字典项列表组件属性 */
export interface DictListProps {
  /** 字典项列表 */
  items: LookupItem[];
  /** patch 回调: 内部会调 fetchAdminPatchItem 并刷新 query cache */
  onPatch: (key: string, payload: LookupItemPatchInput) => Promise<void>;
  /** "请求删除" 回调: page 接住后弹 DictItemDeleteDialog */
  onAskDelete: (item: LookupItem) => void;
  /** "查看历史" 回调: page 接住后开 DictAuditLog 抽屉 */
  onAskAudit: (item: LookupItem) => void;
  /** DICTIONARY_READONLY=true 时禁用所有写按钮 */
  readonly?: boolean;
}

/**
 * 字典项列表组件
 *
 * 展示 key / label_zh / label_en / sort / is_active, 行内 "编辑" 触发 DictItemEditor.
 * "删除" / "历史" 只触发父组件回调, 由 page 接住弹出 DictItemDeleteDialog / DictAuditLog.
 * 用 DataTable + DataEmpty; 行 expandedRowRender 在编辑态展开 DictItemEditor.
 *
 * @param props - 组件属性
 * @param props.items - 字典项列表
 * @param props.onPatch - patch 回调
 * @param props.onAskDelete - 请求删除回调
 * @param props.onAskAudit - 查看历史回调
 * @param props.readonly - 是否只读
 * @client-bff
 */
export const DictList = ({ items, onPatch, onAskDelete, onAskAudit, readonly }: DictListProps) => {
  const translate = useTranslations();
  const [editingKey, setEditingKey] = useState<string | null>(null);

  const columns: ColumnDef<LookupItem>[] = [
    {
      accessorKey: "key",
      cell: (ctx) => <span className="num font-mono">{ctx.row.original.key}</span>,
      header: () => "key",
      size: 140,
    },
    {
      accessorKey: "label_zh",
      cell: (ctx) => ctx.row.original.label_zh,
      header: () => translate("中文标签"),
      size: 160,
    },
    {
      accessorKey: "label_en",
      cell: (ctx) => ctx.row.original.label_en,
      header: () => translate("英文标签"),
      size: 160,
    },
    {
      accessorKey: "sort",
      cell: (ctx) => <span className="num">{ctx.row.original.sort}</span>,
      header: () => translate("排序"),
      size: 80,
    },
    {
      accessorKey: "is_active",
      cell: (ctx) =>
        ctx.row.original.is_active ? (
          <Badge variant="secondary">{translate("启用")}</Badge>
        ) : (
          <Badge variant="destructive">{translate("禁用")}</Badge>
        ),
      header: () => translate("状态"),
      size: 80,
    },
    {
      cell: (ctx) => (
        <div className="flex gap-1.5">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setEditingKey(ctx.row.original.key)}
            disabled={readonly || editingKey === ctx.row.original.key}
            data-testid={`edit-${ctx.row.original.key}`}
          >
            {translate("编辑")}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => onAskDelete(ctx.row.original)}
            disabled={readonly}
            data-testid={`delete-${ctx.row.original.key}`}
          >
            {translate("删除")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onAskAudit(ctx.row.original)}
            data-testid={`audit-${ctx.row.original.key}`}
          >
            {translate("历史")}
          </Button>
        </div>
      ),
      header: () => translate("操作"),
      id: "actions",
    },
  ];

  const editingItem = editingKey ? (items.find((it) => it.key === editingKey) ?? null) : null;

  return (
    <div className="space-y-3" data-testid="dict-list">
      <DataTable<LookupItem>
        columns={columns}
        dataSource={items}
        rowKey="key"
        emptyText={
          <DataEmpty
            icon={Database}
            title={translate("暂无字典项")}
            description={translate("点右上「新增项」开始添加")}
          />
        }
        expandedRowRender={(item) =>
          item.key === editingKey && editingItem ? (
            <DictItemEditor
              item={editingItem}
              onCancel={() => setEditingKey(null)}
              onPatch={async (key, payload) => {
                await onPatch(key, payload);
                setEditingKey(null);
              }}
            />
          ) : null
        }
        maxHeight="calc(100vh - 360px)"
      />
    </div>
  );
};
