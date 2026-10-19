"use client";
// PermissionsTable — 树形权限矩阵 (2026-07-02 nav spec §5)
// 旧版用 Table, 现改用 TreeCheckbox. 仍复用 usePermissionsTable hook 的数据流.
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTranslations } from "next-intl";
import {
  usePermissionsTable,
  SUPER_ADMIN_ROLE,
  computeChecked,
  computeIndeterminate,
  pagesToPageMeta,
  type MatrixPage,
  type MatrixRole,
  type MatrixUpdate,
  type RoleListItem,
} from "../_hooks/use-permissions-table";
import { TreeCheckbox, type TreeCheckboxNode } from "@/components/common/display/tree-checkbox";
import { buildNavTree } from "@/lib/nav/build-nav-tree";

export {
  type MatrixPage,
  type MatrixRole,
  type MatrixUpdate,
  type RoleListItem,
} from "../_hooks/use-permissions-table";

/** 权限矩阵表格属性 */
export interface PermissionsTableProps {
  /** 角色列表 (MatrixRole 格式) */
  roles: MatrixRole[];
  /** 预留 role list 行展示, 当前仅渲染权限矩阵 */
  roleList?: RoleListItem[];
  /** 可用页面权限列表 */
  pages: MatrixPage[];
  /** 初始权限矩阵数据 */
  matrix: Record<string, Record<string, boolean>>;
  /** 当前选中的角色 name */
  selectedRole: string | null;
  /** 选中角色回调 */
  onSelectRole: (name: string | null) => void;
  /** 保存变更回调 */
  onSave: (updates: MatrixUpdate[]) => Promise<void>;
  /** 预留编辑角色入口 (PR6 仅做矩阵树, edit/delete 走 RoleDetailCard) */
  onEditRole?: (name: string) => void;
  /** 预留删除角色入口 */
  onDeleteRole?: (name: string) => void;
  /** 创建角色回调 */
  onCreateRole: () => void;
}

/** 数字零常量 */
const ZERO = 0;
/** 空 Set 常量 */
const EMPTY_SET = new Set<string>();

/**
 * 树形权限矩阵组件
 *
 * 旧版用 Table, 现改用 TreeCheckbox. 仍复用 usePermissionsTable hook 的数据流.
 *
 * @param props - 组件属性
 * @param props.roles - 角色列表
 * @param props.pages - 可用页面权限列表
 * @param props.matrix - 初始权限矩阵数据
 * @param props.selectedRole - 当前选中的角色 name
 * @param props.onSelectRole - 选中角色回调
 * @param props.onSave - 保存变更回调
 * @param props.onCreateRole - 创建角色回调
 * @client-bff
 */
export const PermissionsTable = ({
  roles,
  pages,
  matrix,
  selectedRole,
  onSelectRole,
  onSave,
  onCreateRole,
}: PermissionsTableProps) => {
  const translate = useTranslations();
  const { isEditMode, search, filteredRoles, dirtyCount, getCellValue, toggle, handlers } =
    usePermissionsTable(roles, matrix, onSave);

  // (2026-07-02) 一次性建树, 跨 role 复用
  const navTree = buildNavTree(pagesToPageMeta(pages));
  const treeNodes: TreeCheckboxNode[] = navTree.roots.map((root) => ({
    key: root.key,
    label: translate(root.label_zh),
    children: root.children.map((child) => ({
      key: child.key,
      label: translate(child.label_zh),
    })),
  }));

  // super_admin 一次性算全选集合
  const allKeys = (() => {
    const result = new Set<string>();
    for (const root of navTree.roots) {
      result.add(root.key);
      for (const child of root.children) {
        result.add(child.key);
      }
    }
    return result;
  })();

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Input
          placeholder={translate("搜索角色…")}
          value={search}
          onChange={handlers.searchChange}
          className="max-w-xs"
          data-testid="permissions-search"
        />
        <div className="flex items-center gap-2">
          {isEditMode && (
            <>
              <span className="text-xs text-status-warning">
                {translate("未保存")} ({dirtyCount})
              </span>
              <Button variant="ghost" onClick={handlers.cancel}>
                {translate("取消")}
              </Button>
            </>
          )}
          <Button
            variant={isEditMode ? "default" : "outline"}
            onClick={handlers.editToggle}
            data-testid="permissions-edit-toggle"
          >
            {isEditMode ? translate("退出编辑") : translate("编辑")}
          </Button>
          <Button onClick={onCreateRole} data-testid="permissions-create-role">
            <Plus className="mr-1 h-4 w-4" />
            {translate("新建角色")}
          </Button>
        </div>
      </div>

      {/* Edit mode banner */}
      {isEditMode && (
        <div className="flex items-center justify-between rounded-lg border border-status-warning/30 bg-status-warning/5 px-4 py-2 text-sm">
          <span className="font-medium text-status-warning">
            {translate("编辑模式")} · {translate("修改不会立即生效, 点击保存后提交")}
          </span>
          <Button
            onClick={handlers.save}
            disabled={dirtyCount === ZERO}
            data-testid="permissions-save"
          >
            {translate("保存更改")}
          </Button>
        </div>
      )}

      {/* (2026-07-02) 角色列表 + 树形 matrix 组合 */}
      <div className="space-y-4">
        {filteredRoles.map((role) => {
          const checked = computeChecked(navTree, role.name, getCellValue);
          const indeterminate = computeIndeterminate(navTree, role.name, getCellValue);
          const isSuperAdmin = role.name === SUPER_ADMIN_ROLE;
          return (
            <div
              key={role.name}
              data-testid={`permission-role-${role.name}`}
              className={`cursor-pointer rounded-lg border p-4 ${
                selectedRole === role.name
                  ? "border-status-info/40 bg-status-info/5"
                  : "border-border/60 bg-card/40"
              } ${isSuperAdmin ? "opacity-80" : ""}`}
              onClick={() => onSelectRole(role.name)}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-base font-semibold">{translate(role.label_zh)}</span>
                {isSuperAdmin && (
                  <span className="text-xs text-status-info">
                    {translate("超级管理员 (所有权限)")}
                  </span>
                )}
              </div>
              <TreeCheckbox
                nodes={treeNodes}
                checked={isSuperAdmin ? allKeys : checked}
                indeterminate={isSuperAdmin ? EMPTY_SET : indeterminate}
                onToggle={(key) => {
                  if (!isEditMode) {
                    return;
                  }
                  toggle(role.name, key);
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};
