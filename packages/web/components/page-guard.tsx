/**
 * RSC 守卫 — pageKey 不在 allowed 或 role 不是 super_admin 时 forbidden()
 * @param props.pageKey 权限标识
 * @param props.role 用户角色
 * @param props.allowed 允许的权限列表
 * @param props.permissions 旧版兼容权限对象
 * @param props.children 子节点
 * @returns JSX 元素 (子节点或 forbidden)
 * @shared
 */
import { forbidden } from "next/navigation";

/** PageGuard 组件的属性 */
export interface PageGuardProps {
  pageKey: string;
  role?: string;
  allowed?: string[];
  permissions?: { allowed: string[] };
  children: React.ReactNode;
}

/**
 * PageGuard — RSC 守卫, pageKey 不在 allowed 或 role 不是 super_admin 时 forbidden()
 * @param props.pageKey 权限标识
 * @param props.role 用户角色
 * @param props.allowed 允许的权限列表
 * @param props.permissions 旧版兼容权限对象
 * @param props.children 子节点
 * @returns JSX 元素 (子节点或 forbidden)
 * @shared
 */
export const PageGuard = ({ pageKey, role, allowed, permissions, children }: PageGuardProps) => {
  const effectiveRole = role ?? "user";
  const effectiveAllowed = allowed ?? permissions?.allowed ?? [];
  if (effectiveRole !== "super_admin" && !effectiveAllowed.includes(pageKey)) {
    forbidden();
  }
  return <>{children}</>;
};
