"use client";
// Invite 列表 + 撤销 (2026-06-14) - 切 DataTable<T> + AppConfirm
//   替手写 table + globalThis.confirm()
// (2026-06-14) React 19 use(promise): 接 RSC 传的 Promise, Suspense 边界控制 loading
// (2026-06-14) React 19 useOptimistic: 撤销时立刻移除行, 失败自动回滚
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { use, useOptimistic, useState, useTransition } from "react";
import { getErrorMessage } from "@/lib/api/errors";
import { AppConfirm } from "@/components/common/confirm/app-confirm";
import { formatDate } from "@/lib/date";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { deleteInvite } from "@/lib/api/users";
import { toast } from "sonner";
import { useTranslations } from "next-intl";

const EMAIL_COLUMN_WIDTH = 240;
const STATUS_COLUMN_WIDTH = 100;
const DATE_COLUMN_WIDTH = 120;

const renderStatusBadge = (inv: InviteItem) => {
  if (inv.redeemed_at) {
    return <Badge variant="secondary">已用</Badge>;
  }
  return <Badge variant="default">待用</Badge>;
};

const renderDate = (value: string) => formatDate(value, "zh-CN");

/** Invite 邀请数据项 */
export interface InviteItem {
  created_at: string;
  email: string;
  expires_at: string;
  id: number;
  redeemed_at: string | null;
  token: string;
}

interface BuildColumnsParams {
  onDelete: (token: string) => void;
  pending: boolean;
  translate: (key: string) => string;
}

const buildColumns = ({
  onDelete,
  pending,
  translate,
}: BuildColumnsParams): ColumnDef<InviteItem>[] => [
  {
    accessorKey: "email",
    header: () => "Email",
    size: EMAIL_COLUMN_WIDTH,
  },
  {
    accessorKey: "redeemed_at",
    cell: (ctx) => renderStatusBadge(ctx.row.original),
    header: () => "状态",
    size: STATUS_COLUMN_WIDTH,
  },
  {
    accessorKey: "expires_at",
    cell: (ctx) => renderDate(ctx.row.original.expires_at),
    header: () => "过期",
    size: DATE_COLUMN_WIDTH,
  },
  {
    accessorKey: "created_at",
    cell: (ctx) => renderDate(ctx.row.original.created_at),
    header: () => "创建",
    size: DATE_COLUMN_WIDTH,
  },
  {
    accessorKey: "actions",
    cell: (ctx) => (
      <Button
        data-testid={`delete-${ctx.row.original.token}`}
        disabled={pending || ctx.row.original.redeemed_at !== null}
        onClick={() => onDelete(ctx.row.original.token)}
        size="sm"
        variant="destructive"
      >
        {translate("撤销")}
      </Button>
    ),
    header: () => "操作",
  },
];

/** AdminInvitesTable
 * @param props
 * @client-bff
 */
// eslint-disable-next-line max-statements -- admin 列表组件内聚 5 hooks + 3 handlers 缺一不可
export const AdminInvitesTable = ({
  invitesPromise,
}: {
  invitesPromise: Promise<{ items: InviteItem[] }>;
}) => {
  const translate = useTranslations();
  const initialItems = use(invitesPromise);
  const [items, setItems] = useState(initialItems.items);
  const [optimisticItems, removeOptimistic] = useOptimistic(items, (state, token: string) =>
    state.filter((current) => current.token !== token),
  );
  const [pending, startTransition] = useTransition();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [confirmToken, setConfirmToken] = useState<string | null>(null);

  const handleConfirm = () => {
    if (confirmToken) {
      handleDelete(confirmToken);
      setConfirmToken(null);
    }
  };

  const handleDialogOpenChange = (open: boolean) => {
    if (!open) {
      setConfirmToken(null);
    }
  };

  // eslint-disable-next-line max-statements -- startTransition 内聚 4 调用 (optimistic / fetch / setItems / toast)
  const handleDelete = (token: string) => {
    startTransition(async () => {
      removeOptimistic(token);
      try {
        await deleteInvite(token);
        setItems((prev) => prev.filter((current) => current.token !== token));
        toast.success("已撤销");
      } catch (error) {
        // UseOptimistic 自动回滚到 items 原值
        const message = getErrorMessage(error);
        setErrorMessage(message);
        toast.error(message);
      }
    });
  };

  const columns = buildColumns({
    onDelete: (token: string) => {
      setConfirmToken(token);
    },
    pending,
    translate,
  });

  return (
    <div className="space-y-4">
      {errorMessage && <ErrorBanner description={errorMessage} variant="destructive" />}

      <DataTable<InviteItem>
        columns={columns}
        dataSource={optimisticItems}
        emptyText={<DataEmpty title="暂无 invite" />}
        rowKey="token"
      />

      <AppConfirm
        confirmText="确认撤销"
        description="此 invite 将立即失效"
        onConfirm={handleConfirm}
        onOpenChange={handleDialogOpenChange}
        open={Boolean(confirmToken)}
        title="撤销 invite?"
        variant="destructive"
      />
    </div>
  );
};
