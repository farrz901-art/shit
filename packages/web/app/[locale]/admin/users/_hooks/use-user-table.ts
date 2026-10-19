"use client";
// 用户管理表 — 状态 + 操作 hook
// 提取自 AdminUsersTable (2026-06-22): useState + useOptimistic + useTransition + 操作函数
import { useOptimistic, useState, useTransition } from "react";
import { ApiError } from "@/lib/api/errors";
import { listUsers, patchUser } from "@/lib/api/users";
import { toast } from "sonner";

// --- 类型导出 ---

/** 用户管理中的用户数据 */
export interface AdminUser {
  /** 用户 ID */
  id: number;
  /** 邮箱 */
  email: string | null;
  /** 显示名 */
  display_name: string | null;
  /** 角色 */
  role: string;
  /** 是否启用 */
  is_active: boolean;
  /** 用户类型 (account / anon) */
  kind: "account" | "anon";
  /** 关联账号 ID */
  account_id: number | null;
  /** 创建时间 */
  created_at: string;
  /** 最近活动时间 */
  last_seen_at: string;
  /** 最后登录时间 */
  last_login_at: string | null;
}

/** 用户列表响应 */
export interface AdminUsersResponse {
  /** 用户数据数组 */
  items: AdminUser[];
  /** 总数 */
  total: number;
  /** 当前页码 */
  page: number;
  /** 每页条数 */
  page_size: number;
}

/** 首页页码 */
export const FIRST_PAGE = 1;

// --- 内部工具 ---

/**
 * 重新加载用户列表
 * @param params - URL 查询参数
 * @param setData - 设置数据回调
 * @param setError - 设置错误回调
 */
const reloadUsers = async (
  params: URLSearchParams,
  setData: (data: AdminUsersResponse) => void,
  setError: (msg: string | null) => void,
) => {
  try {
    const out = await listUsers<AdminUsersResponse>(params.toString());
    setData(out);
    setError(null);
  } catch (fetchError) {
    if (fetchError instanceof ApiError) {
      setError(fetchError.message);
    } else {
      setError("加载失败");
    }
    if (fetchError instanceof ApiError) {
      toast.error(fetchError.message);
    } else {
      toast.error("加载失败");
    }
  }
};

/**
 * 构建重载列表的 URL 查询参数
 * @param overrides - 覆盖参数
 * @param base - 基础参数
 * @returns URLSearchParams 对象
 */
const buildReloadParams = (
  overrides: { search?: string; kind?: string; page?: number; role?: string } | undefined,
  base: { search: string; kind: string; page: number; roleFilter: string },
): URLSearchParams => {
  const params = new URLSearchParams();
  if (overrides?.search ?? base.search) {
    params.set("search", overrides?.search ?? base.search);
  }
  if ((overrides?.kind ?? base.kind) !== "all") {
    params.set("kind", overrides?.kind ?? base.kind);
  }
  if (overrides?.role !== undefined && overrides?.role !== "all") {
    params.set("role", overrides?.role);
  } else if (base.roleFilter !== "all") {
    params.set("role", base.roleFilter);
  }
  params.set("page", String(overrides?.page ?? base.page));
  return params;
};

// --- 内部 hook: 操作函数 (拆分自 useUserTable, 满足 max-statements 10) ---

/** useUserTableActions 选项 */
interface UseUserTableActionsOptions {
  /** 当前类型筛选 */
  kind: string;
  /** 加载错误回调 */
  onLoadError: (msg: string | null) => void;
  /** 加载成功回调 */
  onLoadSuccess: (data: AdminUsersResponse) => void;
  /** 乐观更新回调 */
  onOptimisticUpdate: (action: AdminUser) => void;
  /** 当前页码 */
  page: number;
  /** 当前角色筛选 */
  roleFilter: string;
  /** 当前搜索文本 */
  search: string;
  /** useTransition startTransition */
  startTransition: React.TransitionStartFunction;
}

/**
 * 用户管理表操作函数 hook (拆分自 useUserTable, 满足 max-statements 10)
 * @param options - 选项
 * @returns 操作函数集合
 */
const useUserTableActions = ({
  kind,
  onLoadError,
  onLoadSuccess,
  onOptimisticUpdate,
  page,
  roleFilter,
  search,
  startTransition,
}: UseUserTableActionsOptions) => {
  const reload = (overrides?: { search?: string; kind?: string; page?: number; role?: string }) => {
    const params = buildReloadParams(overrides, { search, kind, page, roleFilter });
    startTransition(async () => {
      await reloadUsers(params, onLoadSuccess, onLoadError);
    });
  };

  const toggleActive = (user: AdminUser) => {
    const updated: AdminUser = { ...user, is_active: !user.is_active };
    startTransition(async () => {
      onOptimisticUpdate(updated);
      try {
        await patchUser(user.id, { is_active: !user.is_active });
        if (user.is_active) {
          toast.success("已禁用");
        } else {
          toast.success("已启用");
        }
        reload();
      } catch (toggleError) {
        // UseOptimistic 自动回滚
        if (toggleError instanceof ApiError) {
          toast.error(toggleError.message);
        } else {
          toast.error("操作失败");
        }
      }
    });
  };

  const toggleAdmin = (user: AdminUser) => {
    const newRole = user.role === "admin" ? "user" : "admin";
    const updated: AdminUser = { ...user, role: newRole };
    startTransition(async () => {
      onOptimisticUpdate(updated);
      try {
        await patchUser(user.id, { role: newRole });
        if (newRole === "admin") {
          toast.success("已提权");
        } else {
          toast.success("已降权");
        }
        reload();
      } catch (toggleError) {
        if (toggleError instanceof ApiError) {
          toast.error(toggleError.message);
        } else {
          toast.error("操作失败");
        }
      }
    });
  };

  return { reload, toggleActive, toggleAdmin };
};

// --- Hook ---

/**
 * 创建 changeRole 函数 (闭包封装乐观更新 + 刷新)
 * @param startTransition - useTransition startTransition
 * @param updateOptimistic - 乐观更新回调
 * @param reloadFn - 刷新列表函数
 * @returns changeRole 函数
 */
const makeChangeRole = (
  startTransition: React.TransitionStartFunction,
  updateOptimistic: (user: AdminUser) => void,
  reloadFn: ReturnType<typeof useUserTableActions>["reload"],
) => {
  const changeRole = (user: AdminUser, newRole: string) => {
    startTransition(async () => {
      const updated: AdminUser = { ...user, role: newRole };
      updateOptimistic(updated);
      try {
        await patchUser(user.id, { role: newRole });
        toast.success("已改角色");
        reloadFn();
      } catch (changeError) {
        if (changeError instanceof ApiError) {
          toast.error(changeError.message);
        } else {
          toast.error("操作失败");
        }
      }
    });
  };
  return changeRole;
};

/** 用户管理表状态 + 操作 hook
 * @param initialData - 初始数据
 * @param onError - 错误回调
 * @returns 状态 + 操作函数
 * @client-bff
 */
export const useUserTable = (
  initialData: AdminUsersResponse,
  onError?: (msg: string | null) => void,
) => {
  const [data, setData] = useState<AdminUsersResponse>(initialData);
  const [optimisticData, updateOptimistic] = useOptimistic(
    data,
    (state, updatedUser: AdminUser) => ({
      ...state,
      items: state.items.map((user) => {
        if (user.id === updatedUser.id) {
          return updatedUser;
        }
        return user;
      }),
    }),
  );
  const [search, setSearch] = useState("");
  // (2026-06-17) 默认 kind=account, 过滤掉游客 (anon) — admin 通常想看账号用户
  const [kind, setKind] = useState<"all" | "account" | "anon">("account");
  const [page, setPage] = useState(FIRST_PAGE);
  const [pending, startTransition] = useTransition();
  const [roleFilter, setRoleFilter] = useState("all");

  const onLoadError = onError ?? (() => {});

  const { reload, toggleActive, toggleAdmin } = useUserTableActions({
    kind,
    onLoadError,
    onLoadSuccess: setData,
    onOptimisticUpdate: updateOptimistic,
    page,
    roleFilter,
    search,
    startTransition,
  });

  return {
    changeRole: makeChangeRole(startTransition, updateOptimistic, reload),
    data: optimisticData,
    kind,
    optimisticUsers: optimisticData.items,
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
  };
};
