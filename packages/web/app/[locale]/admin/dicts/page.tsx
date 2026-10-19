// 字典管理页 (RSC) — super_admin 专属 (2026-06-19 lookup module Task 9 / spec §5.6)
// 4 层防护: GuardPage (pageKey="admin") + super_admin 守卫 + 后端 admin router (super_admin 权限) + UI 隐藏.
// 内容组装走 AdminDictsClient (client) — TanStack Query hooks 在 client 内调用.
// (2026-06-23) 迁移: PageGuard → GuardPage (保留 super_admin 守卫 + perm.role/allowed 传子组件)
import { AdminDictsClient } from "./_components/admin-dicts-client";
import { GuardPage } from "@/components/auth/guard-page";
import { forbidden } from "next/navigation";
import { getPermissions } from "@/lib/auth/permission";
import { getTranslations } from "next-intl/server";

/**
 * 字典管理页面元数据 (标题)
 * @returns Metadata 对象
 * @server-only
 */
export const generateMetadata = async () => {
  const translate = await getTranslations();
  return { title: `${translate("字典管理")} - RAG` };
};

/**
 * 字典管理页面 (RSC, super_admin 专属)
 *
 * 4 层防护: GuardPage (pageKey="admin") + super_admin 守卫 + 后端 admin router (super_admin 权限) + UI 隐藏.
 * 内容组装走 AdminDictsClient (client).
 *
 * @server-only
 */
export default async function AdminDictsPage() {
  const perm = await getPermissions();
  // (2026-06-19) 字典管理是 super_admin 专属 (改 enum 的能力, v3 RBAC).
  if (!perm.isSuperAdmin) {
    forbidden();
  }

  return (
    <GuardPage pageKey="admin">
      <AdminDictsClient role={perm.role} allowed={perm.allowed} />
    </GuardPage>
  );
}
