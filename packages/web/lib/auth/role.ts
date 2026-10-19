// 角色 helper: 替代原 is_admin bool (v2 RBAC)
// V1: accounts.is_admin (单一 bool)
// V2: accounts.role (string, "user" | "admin" | "super_admin" | 自定义)

interface UserLike {
  role: string;
}

/**
 * 判断用户是否为管理级别 (非 user 角色)
 * @param user  用户对象或 null/undefined
 * @returns     是否为管理级别角色
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
export const isAdminLevel = (user: UserLike | null | undefined): boolean =>
  // 非 user 角色都视为 "管理级别" (admin / super_admin / 自定义如 operator)
  user != null && user.role !== "user";

/**
 * 判断用户是否为超级管理员
 * @param user  用户对象或 null/undefined
 * @returns     是否为 super_admin
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
export const isSuperAdmin = (user: UserLike | null | undefined): boolean =>
  user?.role === "super_admin";
