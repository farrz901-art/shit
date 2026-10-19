// useRoles (2026-06-26) RBAC wire
//   走 TanStack Query, initialData 透传 RSC 拉的列表, mount 强制 refetch 1 次
//   (拿权限页 /admin/permissions 新建 role 后的最新列表, 见 spec §4.3)
"use client";
import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { listRoles, type RoleListItem } from "@/lib/api/permissions";

/** 角色列表缓存过期时间 (毫秒) */
const ROLES_STALE_MS = 60_000;

/** 角色列表 hook (TanStack Query + initialData)
 * @param initial - RSC 预拉的角色列表
 * @returns 角色列表
 * @client-bff
 */
export const useRoles = (initial: RoleListItem[]): RoleListItem[] => {
  const hasRefetched = useRef(false);
  const query = useQuery({
    initialData: { roles: initial },
    queryFn: () => listRoles(),
    queryKey: ["roles"],
    staleTime: ROLES_STALE_MS,
  });
  // mount 强制 refetch 1 次, 拿权限页最新 role 列表
  // 用 useRef 防重复, 不用 dataUpdatedAt (initialData 下它为当前时间 ms, 不是 0)
  useEffect(() => {
    if (!hasRefetched.current) {
      hasRefetched.current = true;
      void query.refetch();
    }
  }, []);
  return query.data?.roles ?? initial;
};
