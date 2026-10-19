/**
 * RSC 页面权限守卫 — 内部调 getPermissions(), 无权则 forbidden()
 * 取代 PageGuard + getMyPermissions() 的页面层样板
 * @param props.pageKey 权限标识
 * @param props.children 子节点
 * @returns JSX 元素 (子节点或 forbidden)
 * @shared
 */
import { type ReactNode } from "react";
import { getPermissions } from "@/lib/auth/permission";
import { forbidden } from "next/navigation";

/**
 * 页面权限守卫 — 内部调 getPermissions(), 无权则 forbidden()
 * @param props.pageKey 权限标识
 * @param props.children 子节点
 * @returns JSX 元素 (子节点或 forbidden)
 * @shared
 */
export const GuardPage = async ({
  pageKey,
  children,
}: {
  pageKey: string;
  children: ReactNode;
}) => {
  const perm = await getPermissions();
  if (!perm.can(pageKey)) {
    forbidden();
  }
  return <>{children}</>;
};
