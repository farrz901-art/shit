// /submissions RSC (审核中心) — 鉴权 + 拉数据 + 渲染 Tabs
// 鉴权重定向: /me 失败 → /login?next=/submissions
// 服务端 conditional: admin 调两路 (mine + all), 普通用户只调 mine
// URL 同步: ?tab=all → 初始 active=admin tab (RSC 重跑预取)
// (2026-06-14) 改走 apiFetch(): 失败用 try/catch 转 fallback (空数组)
// (2026-06-16) 加 serverAuthHeaders: RSC 跨域到 FastAPI 需显式注 cookie token
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { ApiError } from "@/lib/api/errors";
import { type Approval, getMyApprovals, getPendingApprovals } from "@/lib/api/approvals";
import { GuardPage } from "@/components/auth/guard-page";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { SubmissionsTabs } from "./_components/submissions-tabs";
import { getProfile } from "@/lib/api/account";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { HTTP_FORBIDDEN, HTTP_UNAUTHORIZED } from "@/const";

/**
 * 动态渲染模式: 走 cookie, 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic";

/** Profile 响应类型 */
interface ProfileResponse {
  is_admin: boolean;
}

/**
 * fetchProfileOrRedirect - 获取用户信息或重定向到登录页
 * @param auth - 认证头
 * @returns ProfileResponse
 */
const fetchProfileOrRedirect = async (auth: Record<string, string>): Promise<ProfileResponse> => {
  try {
    return (await getProfile(auth)) as ProfileResponse;
  } catch (error) {
    if (
      error instanceof ApiError &&
      (error.status === HTTP_UNAUTHORIZED || error.status === HTTP_FORBIDDEN)
    ) {
      redirect("/login?next=/submissions");
    }
    throw error;
  }
};

/**
 * SubmissionsPage - 审核中心 RSC 页面
 * @param props.searchParams - URL 搜索参数
 * @server-only
 */
export default async function SubmissionsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  // 1. 鉴权: 拉 /me
  const auth = await serverAuthHeaders();
  const me = await fetchProfileOrRedirect(auth);

  const tr = await getTranslations();

  // 2. URL 同步: 读 ?tab= 决定初始 active
  const sp = await searchParams;
  const activeTab = (sp.tab === "all" ? "all" : "mine") as "mine" | "all";

  // 3. 预取两路数据 (admin 才有 all, 普通用户不调避免 403/404)
  const initialMine: Approval[] = await getMyApprovals(auth).catch(() => [] as Approval[]);

  const initialAll: Approval[] | null = me.is_admin
    ? await getPendingApprovals(auth).catch(() => [] as Approval[])
    : null;

  return (
    <GuardPage pageKey="submissions">
      <div className="flex h-full flex-col">
        <PageHero eyebrow="Submissions" title={tr("审核中心")} className="shrink-0 pb-6" />

        <div className="min-h-0 flex-1">
          <SubmissionsTabs
            activeTab={activeTab}
            isAdmin={me.is_admin}
            initialMine={initialMine}
            initialAll={initialAll}
          />
        </div>
      </div>
    </GuardPage>
  );
}
