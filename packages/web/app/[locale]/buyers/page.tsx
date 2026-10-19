"use client";
// 买家列表页 (2026-06-22 buyer-profile spec, 2026-06-25 动态画像列)
// (2026-06-29 refactor) 拆 useBuyersColumns hook + BuyersToolbar, 主组件只管 DataTable + PageHero
// TanStack Query 客户端获取 + DataTable 展示 + 状态筛选
// 动态列: useFieldConfigs() 激活字段按 sort_order 升序生成列, 按 field_type 差异化渲染

import { useRouter } from "@/i18n/navigation";
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { LoadingSkeleton } from "@/components/common/button/app-loading-skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BuyersToolbar } from "@/app/[locale]/buyers/_components/buyers-toolbar";
import { useBuyersColumns } from "@/app/[locale]/buyers/_hooks/use-buyers-columns";
import { ONE, TWO } from "@/const/index";
import { useBuyerProfiles, useFieldConfigs } from "@/app/[locale]/buyers/_lib/buyer-profile/hooks";
import { Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { BuyerProfile } from "@/app/[locale]/buyers/_lib/buyer-profile/types";

/** 空状态筛选值 (全部) @shared */
const STATUS_ALL = "";
/** 序号列宽度 @shared */
const INDEX_COL_WIDTH = 56;
/** 买家名列宽度 @shared */
const NAME_COL_WIDTH = 240;
/** 状态列宽度 @shared */
const STATUS_COL_WIDTH = 100;
/** 日期列宽度 @shared */
const DATE_COL_WIDTH = 160;
/** 操作列宽度 @shared */
const ACTIONS_COL_WIDTH = 100;

/** 按搜索文本筛选画像列表
 * @param items - 画像列表
 * @param searchText - 搜索文本
 * @returns 筛选后的画像列表
 * @shared
 */
const filterProfiles = (items: BuyerProfile[], searchText: string): BuyerProfile[] => {
  if (!searchText) {
    return items;
  }
  const query = searchText.toLowerCase();
  return items.filter(
    (profile) =>
      profile.buyer_name?.toLowerCase().includes(query) ||
      profile.buyer_key.toLowerCase().includes(query),
  );
};

import { formatDateTime } from "@/lib/date";

/** 格式化 ISO 日期为 zh-CN 短格式
 * @param iso - ISO 日期字符串
 * @returns 格式化后日期字符串
 * @shared
 */
const formatDate = (iso: string | null): string => {
  if (!iso) {
    return "—";
  }
  return formatDateTime(iso, "zh-CN");
};

/** 状态对应的 Badge variant
 * @param status - 状态值
 * @returns Badge variant 值
 * @shared
 */
const getStatusVariant = (status: string): "default" | "secondary" | "outline" | "destructive" => {
  switch (status) {
    case "active": {
      return "default";
    }
    case "archived": {
      return "secondary";
    }
    default: {
      return "outline";
    }
  }
};

/** 买家列表页数据 hook (状态筛选 + 搜索 + 字段配置 + 列定义)
 * @returns 页面所需全部状态与数据
 * @client-bff
 */
const useBuyersPageData = () => {
  const translate = useTranslations();
  const [statusFilter, setStatusFilter] = useState(STATUS_ALL);
  const [searchText, setSearchText] = useState("");

  const {
    data,
    isLoading: isLoadingProfiles,
    error: profilesError,
  } = useBuyerProfiles(statusFilter ? { status: statusFilter } : undefined);
  const { data: configs = [], isLoading: isLoadingFields, error: fieldsError } = useFieldConfigs();
  const profileColumns = useBuyersColumns(configs, translate);

  return {
    statusFilter,
    setStatusFilter,
    searchText,
    setSearchText,
    data,
    isLoading: isLoadingProfiles || isLoadingFields,
    profilesError,
    fieldsError,
    columns: buildBaseColumns(translate, profileColumns),
  };
};

/** 买家列表行点击跳转 hook
 * @returns 行点击处理函数
 * @client-bff
 */
const useBuyersRowClick = () => {
  const router = useRouter();
  return (row: BuyerProfile) => {
    router.push(`/buyers/${row.id}`);
  };
};

/** 构建 DataTable 基础列配置
 * @param translate - i18n 翻译函数
 * @param profileColumns - 动态画像列
 * @returns 完整列定义数组
 * @shared
 */
const buildBaseColumns = (
  translate: (key: string) => string,
  profileColumns: ColumnDef<BuyerProfile>[],
): ColumnDef<BuyerProfile>[] => [
  {
    accessorKey: "index",
    cell: (ctx) => (
      <span className="num text-sm text-muted-foreground">
        {String(ctx.row.index + ONE).padStart(TWO, "0")}
      </span>
    ),
    header: () => "#",
    size: INDEX_COL_WIDTH,
  },
  {
    accessorKey: "buyer_name",
    cell: (ctx) => (
      <span className="truncate text-sm font-medium">{ctx.row.original.buyer_name ?? "—"}</span>
    ),
    header: () => translate("买家"),
    size: NAME_COL_WIDTH,
  },
  ...profileColumns,
  {
    accessorKey: "status",
    cell: (ctx) => (
      <Badge variant={getStatusVariant(ctx.row.original.status)}>{ctx.row.original.status}</Badge>
    ),
    header: () => translate("状态"),
    size: STATUS_COL_WIDTH,
  },
  {
    accessorKey: "last_contact_at",
    cell: (ctx) => (
      <span className="num text-sm text-muted-foreground">
        {formatDate(ctx.row.original.last_contact_at)}
      </span>
    ),
    header: () => translate("最近联系"),
    size: DATE_COL_WIDTH,
  },
  {
    accessorKey: "actions",
    cell: () => (
      <Button size="sm" variant="ghost">
        {translate("查看")}
      </Button>
    ),
    header: () => translate("操作"),
    size: ACTIONS_COL_WIDTH,
  },
];

/** 买家列表页面组件
 * @returns 页面 JSX
 * @client-bff
 */
const BuyersPage = () => {
  const translate = useTranslations();
  const {
    statusFilter,
    setStatusFilter,
    searchText,
    setSearchText,
    data,
    isLoading,
    profilesError,
    fieldsError,
    columns,
  } = useBuyersPageData();
  const handleRowClick = useBuyersRowClick();

  const filteredItems = filterProfiles(data?.items ?? [], searchText);

  if (isLoading) {
    return <LoadingSkeleton rows={5} />;
  }

  const profilesErrorMessage = profilesError instanceof Error ? profilesError.message : null;
  const fieldsErrorMessage = fieldsError instanceof Error ? fieldsError.message : null;

  return (
    <div className="space-y-6">
      <PageHero eyebrow="Buyers" title={translate("客户画像")} />

      <BuyersToolbar
        searchText={searchText}
        onSearchChange={setSearchText}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
      />

      {profilesErrorMessage && (
        <ErrorBanner
          description={profilesErrorMessage ?? translate("出错了")}
          variant="destructive"
        />
      )}
      {fieldsErrorMessage && (
        <ErrorBanner
          description={fieldsErrorMessage ?? translate("出错了")}
          variant="destructive"
        />
      )}

      <DataTable<BuyerProfile>
        columns={columns}
        dataSource={filteredItems}
        emptyText={<DataEmpty icon={Users} title={translate("暂无买家")} />}
        onRowClick={handleRowClick}
        rowKey="id"
      />
    </div>
  );
};

export default BuyersPage;
