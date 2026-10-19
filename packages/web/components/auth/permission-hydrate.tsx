"use client";
/**
 * RSC->Client 权限 hydrate 桥接 — 把 RSC layout 拿到的 PermissionData 写进 zustand store
 * @param props.permissions 权限数据
 * @returns null
 * @client-bff
 */
// (2026-06-23) RSC→Client 权限 hydrate 桥接
// 把 RSC layout 拿到的 PermissionData 写进 zustand store + auth-store
// 无条件同步 accountId (含 null), 清除 persist 残留
import { useEffect, useRef } from "react";
import { useAuthStore } from "@/lib/store/auth-store";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";
import type { PermissionData } from "@/lib/auth/permission-types";

/** permission-hydrate @client-bff */
export const PermissionHydrate = ({ permissions }: { permissions: PermissionData }) => {
  const hydrate = usePermissionsStore((state) => state.hydrate);
  const prevKey = useRef("");

  useEffect(() => {
    // 浅比较：只在 role/allowed 真正变化时 re-hydrate
    const key = `${permissions.role}|${permissions.allowed.join(",")}`;
    if (prevKey.current === key) {
      return;
    }
    prevKey.current = key;

    hydrate(permissions);
    // 无条件同步（含 null），清除 persist 残留
    useAuthStore.getState().setAccountId(permissions.accountId);
  }, [hydrate, permissions]);

  return null;
};
