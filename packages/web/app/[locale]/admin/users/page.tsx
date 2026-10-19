// 用户管理页 (RSC) — 鉴权 + 传 Promise 给 AdminUsersTable (use(promise) 模式)
// (2026-06-14) 改: 去 await data, 传 Promise + Suspense fallback
// (2026-06-18) v3 RBAC: 改用 getPermissions(), 替换 /api/account/me 鉴权 + getMyPermissions()
// (2026-06-23) 迁移: PageGuard → GuardPage (内部 cache hit, 0 额外 fetch)
import { Suspense } from "react";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

/** generateMetadata
 * @server-only
 */
export const generateMetadata = async () => {
  const tr = await getTranslations();
  return { title: `${tr("用户管理")} - RAG` };
};
import { getProfile } from "@/lib/api/account";
import { listUsers } from "@/lib/api/users";
import { listRoles, type RoleListItem } from "@/lib/api/permissions";
import { AdminUsersTable } from "./_components/admin-users-table";
import { type AdminUsersResponse } from "./_hooks/use-user-table";
import { CreateInviteButton } from "./_components/create-invite-button";
import { GuardPage } from "@/components/auth/guard-page";
import { getPermissions } from "@/lib/auth/permission";

/** 当前用户 ID 响应 */
interface MeIdResponse {
  /** 用户 ID */
  id: number;
}

/**
 * 获取角色列表，用于 AdminUsersTable 的 AppSelect 选项
 */
const fetchRoles = async (headers: Record<string, string>): Promise<RoleListItem[]> => {
  const rolesResponse = await listRoles(headers);
  return rolesResponse.roles;
};

/** 获取当前用户 ID，取不到就重定向到登录 */
const getCurrentUserId = async (headers: Record<string, string>): Promise<number> => {
  try {
    const me = await getProfile(headers);
    return (me as MeIdResponse).id;
  } catch {
    redirect("/login?next=/admin/users");
  }
};

/**
 * admin / users 页面 — 鉴权 + 传 Promise 给 AdminUsersTable (use(promise) 模式)
 * @returns 用户管理页面
 * @server-only
 */
export default async function AdminUsersPage() {
  const perm = await getPermissions();
  if (!perm.isAdminLevel) {
    redirect("/");
  }

  // 只取当前用户 ID, 用于 table 内按钮 disabled (不能对自己操作)
  const currentUserId = await getCurrentUserId(perm.headers);

  // 鉴权通过后才启动数据 fetch — 不 await, Suspense 边界控制 loading
  // (2026-06-17) 默认 kind=account, 跟 table 默认一致, 首屏不渲染游客
  const usersPromise = listUsers<AdminUsersResponse>(
    "page=1&page_size=20&kind=account",
    perm.headers,
  );

  // (2026-06-26) RSC 同步拉 roles 透传给 client
  const tr = await getTranslations();
  const initialRoles = await fetchRoles(perm.headers);

  return (
    <GuardPage pageKey="admin">
      <div className="space-y-6">
        <div className="flex items-end justify-between">
          <h1 className="display text-3xl">{tr("用户管理")}</h1>
          <CreateInviteButton />
        </div>
        <Suspense fallback={<div className="text-muted-foreground">{tr("加载中…")}</div>}>
          <AdminUsersTable
            usersPromise={usersPromise}
            currentUserId={currentUserId}
            initialRoles={initialRoles}
          />
        </Suspense>
      </div>
    </GuardPage>
  );
}
