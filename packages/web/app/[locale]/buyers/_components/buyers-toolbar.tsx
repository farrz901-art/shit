// BuyersToolbar (2026-06-29 refactor)
// 抽自 buyers/page.tsx 的工具栏: 搜索 + 状态筛选 (全部 / 激活 / 已归档)

"use client";

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** 全部状态筛选值 */
const STATUS_ALL = "";
/** 激活状态筛选值 */
const STATUS_ACTIVE = "active";
/** 已归档状态筛选值 */
const STATUS_ARCHIVED = "archived";

/**
 * 买家列表工具栏组件 — 搜索 + 状态筛选 (全部 / 激活 / 已归档)
 * @param props.searchText - 当前搜索文本
 * @param props.onSearchChange - 搜索文本变更回调
 * @param props.statusFilter - 当前状态筛选值
 * @param props.onStatusChange - 状态筛选变更回调
 * @returns 买家列表工具栏
 * @client-bff
 */
export const BuyersToolbar = ({
  searchText,
  onSearchChange,
  statusFilter,
  onStatusChange,
}: {
  searchText: string;
  onSearchChange: (text: string) => void;
  statusFilter: string;
  onStatusChange: (status: string) => void;
}) => {
  const translate = useTranslations();
  return (
    <div className="flex items-center gap-3">
      <div className="relative w-64">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          className="pl-8"
          onChange={(ev) => onSearchChange(ev.target.value)}
          placeholder={translate("搜索")}
          value={searchText}
        />
      </div>
      <div className="flex items-center gap-1">
        <Button
          onClick={() => onStatusChange(STATUS_ALL)}
          size="sm"
          variant={statusFilter === STATUS_ALL ? "default" : "outline"}
        >
          {translate("全部")}
        </Button>
        <Button
          onClick={() => onStatusChange(STATUS_ACTIVE)}
          size="sm"
          variant={statusFilter === STATUS_ACTIVE ? "default" : "outline"}
        >
          {translate("激活")}
        </Button>
        <Button
          onClick={() => onStatusChange(STATUS_ARCHIVED)}
          size="sm"
          variant={statusFilter === STATUS_ARCHIVED ? "default" : "outline"}
        >
          {translate("已归档")}
        </Button>
      </div>
    </div>
  );
};
