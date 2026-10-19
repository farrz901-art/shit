/**
 * (2026-06-23) Client 页面权限守卫: 读 zustand store, 无权 → router.replace("/404")
 * 取代 ClientPageGuard (自己 fetch API 的旧版)
 * 跟 GuardPage 双层防御: GuardPage 是 server-side 抛 forbidden, GuardClient 是 client-side 跳 404
 * (z守卫 只在 client mount 后生效, 避免 SSR 阶段阻塞)
 */
"use client";
import { type ReactNode, useEffect } from "react";
import { usePermissions } from "@/lib/hooks/use-permissions";
import { useRouter } from "@/i18n/navigation";

/**
 * Client 权限守卫 — 子组件挂载后检查 pageKey 权限, 无权则跳 /404
 * @param props.pageKey 权限标识 (例 "admin.users" / "knowledge.write"), 跟 GuardPage 共享
 * @param props.children 被守卫的子节点, 有权时直接渲染
 */
export const GuardClient = ({ pageKey, children }: { pageKey: string; children: ReactNode }) => {
  const { can, loaded } = usePermissions();
  const router = useRouter();

  useEffect(() => {
    if (loaded && !can(pageKey)) {
      router.replace("/404");
    }
  }, [pageKey, can, loaded, router]);

  return <>{children}</>;
};
