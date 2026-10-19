// 账号设置页 (RSC) — 鉴权 + 拉 /me + Suspense
// (2026-06-18) 不套 PageGuard: 用户设置页是个人页面, 不是功能模块,
//               PageGuard 的 pageKey 体系不适配 (dashboard 不存在于
//               ALL_PAGE_KEYS). 已有 is_account 检查拦截游客, 够了.
import { AccountSettingsClient } from "./_components/account-settings-client";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Skeleton } from "@/components/ui/skeleton";
import { Suspense } from "react";
import { getProfile } from "@/lib/api/account";
import { getPermissions } from "@/lib/auth/permission";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

/** 服务端 Me 响应 (含 is_account 鉴权字段)
 * @property id - 用户 ID
 * @property email - 邮箱
 * @property display_name - 显示名称
 * @property avatar_url - 头像 URL
 * @property is_pending_deletion - 是否处于待注销状态
 * @property deletion_expires_at - 注销截止时间
 * @property is_account - 是否为真账号 (游客为 false)
 */
interface MeResponse {
  id: number;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_pending_deletion: boolean;
  deletion_expires_at: string | null;
  is_account: boolean;
}

/** 生成页面 title
 * @returns Metadata 对象, title 为 "账号设置 - RAG"
 */
export const generateMetadata = async () => {
  const translate = await getTranslations();
  return { title: `${translate("账号设置")} - RAG` };
};

/** 账号设置页: 鉴权后拉取 /me 并传递给 AccountSettingsClient
 * @returns 页面 JSX
 * @server-only
 */
export default async function AccountSettingsPage() {
  const perm = await getPermissions();
  let me: MeResponse | null = null;
  try {
    me = (await getProfile(perm.headers)) as MeResponse;
  } catch {
    redirect("/login?next=/account/settings");
  }
  // Anon 账号 (is_account=false) 不让进
  if (!me.is_account) {
    redirect("/login?next=/account/settings");
  }
  const translate = await getTranslations();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHero eyebrow={translate("账号")} title={translate("账号设置")} />
      <Suspense fallback={<Skeleton className="h-96" />}>
        <AccountSettingsClient me={me} />
      </Suspense>
    </div>
  );
}
