// 权限管理页 (RSC) — super_admin 专属 (2026-06-17) v2 RBAC
// 4 层防护: 第 1 层 /admin/* layout (未实现), 第 2 层 GuardPage (pageKey="admin"),
// 第 3 层后端 /api/permissions 端点 (需 super_admin), 第 4 层 UI 隐藏
// 注: GuardPage 的 pageKey="admin" 范围覆盖 /admin/users + /admin/invites + /admin/permissions;
// Super_admin 专属的 /admin/permissions 需在 GuardPage 基础上额外判 role.
// (2026-06-18) 改 notFound() → forbidden(): 之前非 super_admin 进这里显示"404 / 页面不存在",
//   但实际是权限拒绝. 用 Next.js 15+ experimental forbidden() + app/[locale]/forbidden.tsx
//   显式说"权限不足 / 请联系 super_admin" (HTTP 403 而不是 404).
// (2026-06-23) 迁移: PageGuard → GuardPage
import {
  type MatrixPage,
  type MatrixRole,
  type RoleListItem,
} from "./_components/permissions-table";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { GuardPage } from "@/components/auth/guard-page";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { PermissionsAdminClient } from "./_components/permissions-admin-client";
import { getAllPermissions } from "@/lib/api/permissions";
import { forbidden } from "next/navigation";
import { getPermissions } from "@/lib/auth/permission";
import { getTranslations } from "next-intl/server";

/** getAllPermissions API 响应结构 */
interface PermissionsData {
  /** 角色列表 (MatrixRole 格式) */
  roles: MatrixRole[];
  /** 角色列表 (含 user_count + is_deletable), 跟 matrix 复用 roles 数组但字段增强 */
  role_list?: RoleListItem[];
  /** 权限矩阵数据 */
  matrix: Record<string, Record<string, boolean>>;
  /** 可用页面权限列表 */
  pages: MatrixPage[];
}

/**
 * 权限管理页面元数据 (标题)
 * @returns Metadata 对象
 * @server-only
 */
export const generateMetadata = async () => {
  const tr = await getTranslations();
  return { title: `${tr("权限管理")} - RAG` };
};

/**
 * 权限管理页面 (RSC, super_admin 专属)
 *
 * 4 层防护: GuardPage (pageKey="admin") + super_admin 守卫 + 后端 /api/permissions 端点 + UI 隐藏.
 * 非 super_admin 进这里显示 HTTP 403 而不是 404.
 *
 * @server-only
 */
export default async function PermissionsPage() {
  const perm = await getPermissions();
  if (!perm.isSuperAdmin) {
    forbidden();
  }

  const tr = await getTranslations();

  let data: PermissionsData | null = null;
  try {
    data = await getAllPermissions<PermissionsData>(perm.headers);
  } catch {
    // 后端不可达时不阻塞整页，下方 ErrorBanner 兜底
  }

  return (
    <GuardPage pageKey="admin">
      <div className="space-y-6">
        <PageHero eyebrow="rbac" title={tr("权限管理")} />
        {data ? (
          <>
            <p className="text-sm text-muted-foreground">{tr("管理角色权限矩阵")}</p>
            <PermissionsAdminClient
              matrix={data.matrix}
              pages={data.pages}
              roleList={
                data.role_list ??
                data.roles.map((role) => ({
                  is_deletable: !role.is_system,
                  is_system: role.is_system,
                  label_en: role.label_en,
                  label_zh: role.label_zh,
                  name: role.name,
                  user_count: 0,
                }))
              }
              roles={data.roles}
            />
          </>
        ) : (
          <ErrorBanner
            variant="destructive"
            description={tr("后端服务不可达, 请检查 main_py 是否在 8000 端口运行")}
          />
        )}
      </div>
    </GuardPage>
  );
}
