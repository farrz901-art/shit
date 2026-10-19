"use client";
// 用户管理表 (2026-06-14) - 切 DataTable<T> + AppSelect + AppConfirm + ErrorBanner
//   替手写 table + 手写 <select> + 手写 globalThis.confirm()
//   AdminUserRow 删, 行内操作按钮内联到 actions column render
// (2026-06-22) 提取 hook + filter 组件: useUserTable + UserFilters
// (2026-06-14) React 19 use(promise) + useOptimistic: 接 Promise, toggle 乐观更新
import { type ColumnDef, DataTable } from "@/components/common/table/data-table";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { use, useState } from "react";
import { AppConfirm } from "@/components/common/confirm/app-confirm";
import { AppSelect } from "@/components/common/input/app-select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/date";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { ApiError } from "@/lib/api/errors";
import { resetPassword } from "@/lib/api/users";
import { toast } from "sonner";
import {
  type AdminUser,
  type AdminUsersResponse,
  FIRST_PAGE,
  useUserTable,
} from "../_hooks/use-user-table";
import { useRoles } from "../_hooks/use-roles";
import { type RoleListItem } from "@/lib/api/permissions";
import { UserFilters } from "./user-filters";

/** 邮箱列宽度 */
const COL_EMAIL_WIDTH = 240;
/** 类型列宽度 */
const COL_KIND_WIDTH = 80;
/** 角色列宽度 */
const COL_ROLE_WIDTH = 160;
/** 状态列宽度 */
const COL_STATUS_WIDTH = 80;
/** 创建时间列宽度 */
const COL_CREATED_WIDTH = 120;
/** 最近活动列宽度 */
const COL_LAST_SEEN_WIDTH = 120;

/** 禁用 super_admin 不可手动分配 */
const PROTECTED_ROLE = "super_admin";

/**
 * 构建角色下拉选项
 * @param roles - 角色列表
 * @returns 选项数组 (含 disabled 标记)
 */
const buildRoleOptions = (roles: RoleListItem[]) =>
  roles.map((role) => ({
    value: role.name,
    label: role.label_zh,
    disabled: role.name === PROTECTED_ROLE,
  }));

/**
 * 获取管理员操作标签 (提权/降权)
 * @param role - 当前角色
 * @returns 操作标签
 */
const getAdminActionLabel = (role: string): string => (role === "admin" ? "降权" : "提权");
/**
 * 获取启用/禁用操作标签
 * @param isActive - 是否启用
 * @returns 操作标签
 */
const getActiveActionLabel = (isActive: boolean): string => (isActive ? "禁用" : "启用");

/** renderRoleSelect 参数 */
interface RenderRoleCellParams {
  /** 变更角色回调 */
  changeRole: (user: AdminUser, newRole: string) => void;
  /** 当前登录用户 ID */
  currentUserId: number;
  /** 角色列表 */
  roles: RoleListItem[];
  /** 目标用户 */
  user: AdminUser;
}

/**
 * 渲染角色下拉选择器
 * @param params - 参数对象
 * @returns 角色选择组件
 */
const renderRoleSelect = ({ changeRole, currentUserId, roles, user }: RenderRoleCellParams) => (
  <AppSelect
    value={user.role}
    onChange={(val) => changeRole(user, val)}
    disabled={user.id === currentUserId}
    options={buildRoleOptions(roles)}
    dataTestid={`role-select-${user.id}`}
    className="w-36"
  />
);

/**
 * 渲染用户类型 Badge (账号 / anon)
 * @param user - 用户对象
 * @returns 类型 Badge 组件
 */
const renderKindBadge = (user: AdminUser) => {
  let badgeVariant: "default" | "secondary" = "default";
  if (user.kind !== "account") {
    badgeVariant = "secondary";
  }
  let label = "";
  if (user.kind === "account") {
    label = "账号";
  } else {
    label = "anon";
  }
  return <Badge variant={badgeVariant}>{label}</Badge>;
};

/**
 * 渲染启用状态 Badge (启用 / 禁用)
 * @param user - 用户对象
 * @returns 状态 Badge 组件
 */
const renderActiveBadge = (user: AdminUser) => {
  let badgeVariant: "secondary" | "destructive" = "secondary";
  if (!user.is_active) {
    badgeVariant = "destructive";
  }
  let label = "";
  if (user.is_active) {
    label = "启用";
  } else {
    label = "禁用";
  }
  return <Badge variant={badgeVariant}>{label}</Badge>;
};

/** renderActionButtons 参数 */
interface RenderActionButtonsParams {
  /** 当前登录用户 ID */
  currentUserId: number;
  /** 启用/禁用回调 */
  onToggleActive: (user: AdminUser) => void;
  /** 提权/降权回调 */
  onToggleAdmin: (user: AdminUser) => void;
  /** 重设密码回调 */
  onResetPassword: (user: AdminUser) => void;
  /** 操作是否 pending */
  pending: boolean;
  /** 目标用户 */
  user: AdminUser;
}

/**
 * 渲染行操作按钮
 * @param params - 参数对象
 * @returns 操作按钮组
 */
const renderActionButtons = ({
  currentUserId,
  onToggleActive,
  onToggleAdmin,
  onResetPassword,
  pending,
  user,
}: RenderActionButtonsParams) => (
  <div className="flex gap-1.5">
    <Button
      size="sm"
      variant="outline"
      disabled={pending || user.id === currentUserId}
      onClick={() => onToggleAdmin(user)}
      data-testid={`toggle-admin-${user.id}`}
    >
      {getAdminActionLabel(user.role)}
    </Button>
    <Button
      size="sm"
      variant="outline"
      disabled={pending || user.id === currentUserId}
      onClick={() => onToggleActive(user)}
      data-testid={`toggle-active-${user.id}`}
    >
      {getActiveActionLabel(user.is_active)}
    </Button>
    <Button
      size="sm"
      variant="destructive"
      disabled={pending}
      onClick={() => onResetPassword(user)}
      data-testid={`reset-pwd-${user.id}`}
    >
      重设密码
    </Button>
  </div>
);

/**
 * 获取重设密码确认描述文本
 * @param confirmUser - 待确认用户
 * @returns 描述文本
 */
const getResetDescription = (confirmUser: AdminUser | null): string => {
  if (confirmUser) {
    return `将生成临时密码给 ${confirmUser.email ?? "此用户"}`;
  }
  return "";
};

/** buildColumns 参数 */
interface BuildColumnsParams {
  /** 变更角色回调 */
  changeRole: (user: AdminUser, newRole: string) => void;
  /** 当前登录用户 ID */
  currentUserId: number;
  /** 操作是否 pending */
  pending: boolean;
  /** 角色列表 */
  roles: RoleListItem[];
  /** 设置确认重设密码的用户 */
  setConfirmUser: (user: AdminUser | null) => void;
  /** 启用/禁用回调 */
  toggleActive: (user: AdminUser) => void;
  /** 提权/降权回调 */
  toggleAdmin: (user: AdminUser) => void;
}

/**
 * 构建用户管理表格列定义
 * @param params - 参数对象
 * @returns DataTable 列定义数组
 */
const buildColumns = ({
  changeRole,
  currentUserId,
  pending,
  roles,
  setConfirmUser,
  toggleActive,
  toggleAdmin,
}: BuildColumnsParams): ColumnDef<AdminUser>[] => [
  {
    accessorKey: "email",
    cell: (ctx) => <span className="font-medium">{ctx.row.original.email ?? "—"}</span>,
    header: () => "邮箱",
    size: COL_EMAIL_WIDTH,
  },
  {
    accessorKey: "kind",
    cell: (ctx) => renderKindBadge(ctx.row.original),
    header: () => "类型",
    size: COL_KIND_WIDTH,
  },
  {
    accessorKey: "role",
    cell: (ctx) =>
      renderRoleSelect({
        changeRole,
        currentUserId,
        roles,
        user: ctx.row.original,
      }),
    header: () => "角色",
    size: COL_ROLE_WIDTH,
  },
  {
    accessorKey: "is_active",
    cell: (ctx) => renderActiveBadge(ctx.row.original),
    header: () => "状态",
    size: COL_STATUS_WIDTH,
  },
  {
    accessorKey: "created_at",
    cell: (ctx) => formatDate(ctx.row.original.created_at, "zh-CN"),
    header: () => "创建",
    size: COL_CREATED_WIDTH,
  },
  {
    accessorKey: "last_seen_at",
    cell: (ctx) => formatDate(ctx.row.original.last_seen_at, "zh-CN"),
    header: () => "最近活动",
    size: COL_LAST_SEEN_WIDTH,
  },
  {
    accessorKey: "actions",
    cell: (ctx) =>
      renderActionButtons({
        currentUserId,
        onResetPassword: setConfirmUser,
        onToggleActive: toggleActive,
        onToggleAdmin: toggleAdmin,
        pending,
        user: ctx.row.original,
      }),
    header: () => "操作",
  },
];

/**
 * 用户管理表格组件 (2026-06-14) — 含角色选择/提权降权/启用禁用/重设密码
 * @param props.usersPromise - 用户列表 Promise (RSC use)
 * @param props.currentUserId - 当前登录用户 ID
 * @param props.initialRoles - 初始角色列表
 * @returns 用户管理表格
 * @client-bff
 */
export const AdminUsersTable = ({
  usersPromise,
  currentUserId,
  initialRoles,
}: {
  usersPromise: Promise<AdminUsersResponse>;
  currentUserId: number;
  initialRoles: RoleListItem[];
}) => {
  const initialData = use(usersPromise);
  const [error, setError] = useState<string | null>(null);
  const [confirmUser, setConfirmUser] = useState<AdminUser | null>(null);
  const {
    changeRole,
    data,
    kind,
    page,
    pending,
    reload,
    roleFilter,
    search,
    setKind,
    setPage,
    setRoleFilter,
    setSearch,
    startTransition,
    toggleActive,
    toggleAdmin,
  } = useUserTable(initialData, setError);
  const roles = useRoles(initialRoles);

  /**
   * 类型筛选变更, 重新加载列表
   * @param value - 选中值
   */
  const handleKindChange = (value: string) => {
    setKind(value as typeof kind);
    reload({ kind: value, page: FIRST_PAGE });
  };

  /**
   * 角色筛选变更, 重新加载列表
   * @param value - 选中值
   */
  const handleRoleFilterChange = (value: string) => {
    setRoleFilter(value);
    reload({ role: value, page: FIRST_PAGE });
  };

  /**
   * 确认弹框开关变更回调
   * @param open - 是否打开
   */
  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setConfirmUser(null);
    }
  };

  /** 执行重设密码, 成功 toast 显示临时密码 */
  const handleConfirmReset = () => {
    if (!confirmUser) {
      return;
    }
    const user = confirmUser;
    setConfirmUser(null);
    startTransition(async () => {
      try {
        const result = await resetPassword(user.id);
        toast.success(`临时密码: ${result.temp_password}`);
      } catch (resetError) {
        if (resetError instanceof ApiError) {
          toast.error(resetError.message);
        } else {
          toast.error("重设失败");
        }
      }
    });
  };

  return (
    <div className="space-y-4">
      {error && <ErrorBanner variant="destructive" description={error} dataTestid="users-error" />}

      <UserFilters
        search={search}
        onSearchChange={setSearch}
        kind={kind}
        onKindChange={handleKindChange}
        roleFilter={roleFilter}
        onRoleFilterChange={handleRoleFilterChange}
        roles={roles}
        onReload={() => reload({ page: FIRST_PAGE })}
      />

      <DataTable<AdminUser>
        columns={buildColumns({
          changeRole,
          currentUserId,
          pending,
          roles,
          setConfirmUser,
          toggleActive,
          toggleAdmin,
        })}
        dataSource={data.items}
        rowKey="id"
        emptyText={<DataEmpty title="暂无用户" />}
        pagination={{
          current: page,
          onChange: (newPage) => {
            setPage(newPage);
            reload({ page: newPage });
          },
          pageSize: data.page_size,
          total: data.total,
        }}
        // (2026-06-17) 限制表格高度, 避免 admin 49+ 用户时撑爆页面下方被遮.
        // 200px 留给: p-6 (48px) + h1+button (40px) + space-y-6 (24px) + filter bar (40px) + space-y-4 (16px) + 缓冲
        maxHeight="calc(100vh - 200px)"
      />

      <AppConfirm
        open={Boolean(confirmUser)}
        onOpenChange={handleOpenChange}
        title="重设密码"
        description={getResetDescription(confirmUser)}
        confirmText="确认重设"
        variant="destructive"
        onConfirm={handleConfirmReset}
      />
    </div>
  );
};
