"use client";
// 用户管理表过滤器 (2026-06-22) — 搜索输入框 + kind 下拉过滤 + 刷新按钮
// (2026-06-26) RBAC wire: 加 role 下拉过滤
import { AppSelect } from "@/components/common/input/app-select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTranslations } from "next-intl";
import { type RoleListItem } from "@/lib/api/permissions";

/** "全部" 选项值 */
const KIND_ALL = "all";

/** 用户类型筛选项列表 */
const kindOptions = [
  { label: "全部", value: KIND_ALL },
  { label: "账号", value: "account" },
  { label: "anon", value: "anon" },
];

/** 用户筛选器属性 */
interface UserFiltersProps {
  /** 当前类型筛选值 */
  kind: string;
  /** 类型筛选变更回调 */
  onKindChange: (value: string) => void;
  /** 刷新回调 */
  onReload: () => void;
  /** 角色筛选变更回调 */
  onRoleFilterChange: (value: string) => void;
  /** 搜索文本变更回调 */
  onSearchChange: (value: string) => void;
  /** 当前角色筛选值 */
  roleFilter: string;
  /** 角色列表 */
  roles: RoleListItem[];
  /** 当前搜索文本 */
  search: string;
}

/**
 * 用户管理表过滤器组件 — 搜索输入框 + kind 下拉过滤 + 刷新按钮
 * @param props - 组件属性
 * @returns 用户筛选器
 * @client-bff
 */
export const UserFilters = ({
  kind,
  onKindChange,
  onReload,
  onRoleFilterChange,
  onSearchChange,
  roleFilter,
  roles,
  search,
}: UserFiltersProps) => {
  const translate = useTranslations();
  const roleOptions = [
    { label: translate("所有角色"), value: KIND_ALL },
    ...roles.map((role) => ({ label: role.label_zh, value: role.name })),
  ];

  /**
   * 搜索框键盘事件: Enter 触发刷新
   * @param event - 键盘事件
   */
  const handleSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      onReload();
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        type="text"
        placeholder={"搜索 email / 显示名"}
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        onKeyDown={handleSearchKeyDown}
        data-testid="search-input"
        className="w-64"
      />
      <AppSelect
        options={kindOptions}
        value={kind}
        onChange={(value) => onKindChange(value)}
        placeholder="类型"
        dataTestid="kind-filter"
        className="w-32"
      />
      <AppSelect
        options={roleOptions}
        value={roleFilter}
        onChange={(value) => onRoleFilterChange(value)}
        placeholder="角色"
        dataTestid="role-filter"
        className="w-40"
      />
      <Button size="sm" variant="outline" onClick={onReload} data-testid="reload">
        {translate("刷新")}
      </Button>
    </div>
  );
};
