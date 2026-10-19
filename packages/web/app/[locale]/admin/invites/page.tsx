// Invite 管理页 (RSC) — 鉴权 + 传 Promise 给 AdminInvitesTable (use(promise) 模式)
// (2026-06-14) 改: 去 await data, 传 Promise + Suspense fallback
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage (仍保留 /api/account/me 鉴权重定向)
// (2026-06-30) 业务 API 走 wrapper: getProfile / listInvites (不再直接 apiFetch)
import { AdminInvitesTable, type InviteItem } from "./_components/admin-invites-table";
import { GuardPage } from "@/components/auth/guard-page";
import { Suspense } from "react";
import { getProfile } from "@/lib/api/account";
import { listInvites } from "@/lib/api/users";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

/** /api/account/me 响应结构 */
interface MeResponse {
  /** 是否管理员 */
  is_admin: boolean;
}

/** listInvites API 响应结构 */
interface InvitesResponse {
  /** 邀请列表 */
  items: InviteItem[];
}

/**
 * Invite 管理页面元数据 (标题)
 * @returns Metadata 对象
 * @server-only
 */
export const generateMetadata = async () => {
  const translate = await getTranslations();
  return { title: `${translate("Invite 管理")} - RAG` };
};

/**
 * Invite 管理页面 (RSC)
 *
 * 鉴权 + 传 Promise 给 AdminInvitesTable (use(promise) 模式).
 * 不 await data, 传 Promise + Suspense fallback.
 *
 * @server-only
 */
export default async function AdminInvitesPage() {
  let account: MeResponse | null = null;
  try {
    account = (await getProfile()) as MeResponse;
  } catch {
    redirect("/login?next=/admin/invites");
  }
  if (!account?.is_admin) {
    redirect("/");
  }

  // 鉴权通过后才启动数据 fetch — 不 await, Suspense 边界控制 loading
  const invitesPromise = listInvites<InvitesResponse>();

  const translate = await getTranslations();

  return (
    <GuardPage pageKey="admin">
      <div className="space-y-6">
        <h1 className="display text-3xl">{translate("Invite 管理")}</h1>
        <Suspense fallback={<div className="text-muted-foreground">{translate("加载中…")}</div>}>
          <AdminInvitesTable invitesPromise={invitesPromise} />
        </Suspense>
      </div>
    </GuardPage>
  );
}
