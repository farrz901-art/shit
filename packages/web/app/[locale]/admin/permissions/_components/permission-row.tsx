"use client";
// PermissionRow — 单行角色权限矩阵 (角色信息 + 页面开关 + 操作菜单)
import { Check, MoreHorizontal, Pencil, Shield, Trash2, User, X } from "lucide-react";
import { TableCell, TableRow } from "@/components/ui/table";
import { AppDropdownMenu } from "@/components/common/input/app-dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useTranslations } from "next-intl";
import type { MatrixPage, MatrixRole, RoleListItem } from "../_hooks/use-permissions-table";

// ── 常量 ────────────────────────────────────────────────────────────────────
/** super_admin 角色标识 */
const SUPER_ADMIN_ROLE = "super_admin";
/** Lucide 图标基础 class */
const ICON_CLASSES = "h-4 w-4";
/** 通用图标 stroke 宽度 */
const ICON_STROKE = 1.5;
/** 勾选图标 stroke 宽度 */
const CHECK_STROKE = 3;
/** 叉号图标 stroke 宽度 */
const X_STROKE = 3;
/** 数字零常量 */
const ZERO = 0;

// ── Props ───────────────────────────────────────────────────────────────────
/** 权限行组件属性 */
export interface PermissionRowProps {
  /** 当前行角色对象 */
  role: MatrixRole;
  /** 角色列表 (含 user_count 等信息) */
  roleList: RoleListItem[];
  /** 可用页面权限列表 */
  pages: MatrixPage[];
  /** 当前选中的角色 name */
  selectedRole: string | null;
  /** 选中角色回调 */
  onSelectRole: (name: string | null) => void;
  /** 编辑角色回调 */
  onEditRole: (name: string) => void;
  /** 删除角色回调 */
  onDeleteRole: (name: string) => void;
  /** 获取单元格权限值 */
  getCellValue: (role: string, page: string) => boolean;
  /** 检查单元格是否有未保存变更 */
  isDirty: (role: string, page: string) => boolean;
  /** 切换单元格权限 */
  toggle: (role: string, page: string) => void;
  /** 是否处于编辑模式 */
  isEditMode: boolean;
}

// ── 子组件 ──────────────────────────────────────────────────────────────────
/** 角色图标: system -> Shield, 普通 -> User */
const RoleIcon = ({ name, isSystem }: { name: string; isSystem: boolean }) => {
  if (name === SUPER_ADMIN_ROLE || isSystem) {
    return <Shield className={`${ICON_CLASSES} text-status-warning`} strokeWidth={ICON_STROKE} />;
  }
  return <User className={`${ICON_CLASSES} text-muted-foreground`} strokeWidth={ICON_STROKE} />;
};

/**
 * 停止事件冒泡 (用于 dropdown 列, 防止行选中)
 * @param event - 鼠标事件对象
 * @shared
 */
const handleDropdownClick = (event: React.MouseEvent) => {
  event.stopPropagation();
};

/**
 * 行选中样式
 * @param selected - 是否选中
 * @returns Tailwind class 字符串, 选中时返回高亮背景
 * @shared
 */
const getRowClassName = (selected: boolean): string | undefined => {
  if (selected) {
    return "bg-muted/30";
  }
  return undefined;
};

/**
 * 单 cell 状态渲染: 编辑模式 -> Switch, 只读模式 -> Check / X
 *
 * @param props - 组件属性
 * @param props.isEditing - 是否编辑模式
 * @param props.isAllowed - 是否有权限
 * @param props.isDisabled - 是否禁用
 * @param props.roleName - 角色名
 * @param props.pageKey - 页面 key
 * @param props.toggle - 切换回调
 * @returns React 节点
 * @shared
 */
const CellContent = ({
  isEditing,
  isAllowed,
  isDisabled,
  roleName,
  pageKey,
  toggle,
}: {
  isEditing: boolean;
  isAllowed: boolean;
  isDisabled: boolean;
  roleName: string;
  pageKey: string;
  toggle: (role: string, page: string) => void;
}): React.ReactNode => {
  if (isEditing) {
    return (
      <Switch
        checked={isAllowed}
        onCheckedChange={() => toggle(roleName, pageKey)}
        disabled={isDisabled}
        data-testid={`matrix-${roleName}-${pageKey}`}
      />
    );
  }
  if (isAllowed) {
    return (
      <Check
        className="mx-auto h-4 w-4 text-status-success"
        strokeWidth={CHECK_STROKE}
        data-testid={`matrix-${roleName}-${pageKey}`}
      />
    );
  }
  return (
    <X
      className="mx-auto h-4 w-4 text-muted-foreground/30"
      strokeWidth={X_STROKE}
      data-testid={`matrix-${roleName}-${pageKey}`}
    />
  );
};

/**
 * 单行角色权限矩阵组件 (角色信息 + 页面开关 + 操作菜单)
 *
 * @param props - 组件属性
 * @param props.role - 当前行角色对象
 * @param props.roleList - 角色列表
 * @param props.pages - 可用页面权限列表
 * @param props.selectedRole - 当前选中的角色 name
 * @param props.onSelectRole - 选中角色回调
 * @param props.onEditRole - 编辑角色回调
 * @param props.onDeleteRole - 删除角色回调
 * @param props.getCellValue - 获取单元格权限值
 * @param props.isDirty - 检查单元格是否有未保存变更
 * @param props.toggle - 切换单元格权限
 * @param props.isEditMode - 是否处于编辑模式
 * @client-bff
 */
// ── 主组件 ──────────────────────────────────────────────────────────────────
export const PermissionRow = ({
  role,
  roleList,
  pages,
  selectedRole,
  onSelectRole,
  onEditRole,
  onDeleteRole,
  getCellValue,
  isDirty,
  toggle,
  isEditMode,
}: PermissionRowProps) => {
  const translate = useTranslations();
  const roleListItem = roleList.find((item) => item.name === role.name);
  const isSelected = selectedRole === role.name;
  const isSuper = role.name === SUPER_ADMIN_ROLE;
  const disabled = isSuper || !isEditMode;

  return (
    <TableRow
      data-testid={`matrix-row-${role.name}`}
      className={getRowClassName(isSelected)}
      onClick={() => onSelectRole(role.name)}
    >
      {/* 角色信息列 */}
      <TableCell>
        <div className="flex items-center gap-2">
          <RoleIcon name={role.name} isSystem={role.is_system} />
          <div className="flex flex-col">
            <span className="font-medium leading-none">{translate(role.label_zh)}</span>
            <span className="text-xs text-muted-foreground">{role.name}</span>
          </div>
          {roleListItem && roleListItem.user_count > ZERO && (
            <Badge variant="outline" className="text-xs">
              {roleListItem.user_count} {translate("人")}
            </Badge>
          )}
          {role.is_system && (
            <Badge variant="secondary" className="text-xs">
              {translate("系统")}
            </Badge>
          )}
        </div>
      </TableCell>

      {/* 页面权限列 */}
      {pages.map((page) => {
        const allowed = getCellValue(role.name, page.key);
        const dirty = isDirty(role.name, page.key);
        return (
          <TableCell
            key={page.key}
            className="text-center"
            onClick={() => toggle(role.name, page.key)}
          >
            <div className="flex flex-col items-center gap-0.5">
              <CellContent
                isAllowed={allowed}
                isDisabled={disabled}
                isEditing={isEditMode}
                pageKey={page.key}
                roleName={role.name}
                toggle={toggle}
              />
              {dirty && <span className="h-1 w-1 rounded-full bg-status-warning" />}
            </div>
          </TableCell>
        );
      })}

      {/* 操作菜单列 */}
      <TableCell onClick={handleDropdownClick}>
        <AppDropdownMenu
          trigger={
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              data-testid={`matrix-actions-${role.name}`}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          }
          items={[
            {
              key: "rename",
              label: translate("重命名"),
              icon: <Pencil className="h-4 w-4" />,
              onClick: () => onEditRole(role.name),
              testid: `matrix-edit-${role.name}`,
            },
            {
              key: "delete",
              label: translate("删除"),
              icon: <Trash2 className="h-4 w-4" />,
              onClick: () => onDeleteRole(role.name),
              variant: "destructive" as const,
              testid: `matrix-delete-${role.name}`,
              hidden: isSuper || !roleListItem?.is_deletable,
            },
          ]}
        />
      </TableCell>
    </TableRow>
  );
};
