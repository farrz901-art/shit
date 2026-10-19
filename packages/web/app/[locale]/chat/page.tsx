// 智能体聊天主页 (2026-06-09)
// (2026-06-17) v2 RBAC: anon (isAccount=false) → 隐藏记忆按钮
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage (保留 serverAuthHeaders 用于 /me 鉴权)
import { ChatShell } from "@/components/chat/chat-shell";
import { GuardPage } from "@/components/auth/guard-page";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { Reveal } from "@/components/motion/animated";
import { getProfile } from "@/lib/api/account";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { DELAY } from "@/lib/motion";
import { getTranslations } from "next-intl/server";

/** generateMetadata
 * @server-only
 */
export const generateMetadata = async () => {
  const translate = await getTranslations();
  return { title: `${translate("智能体聊天")} - RAG` };
};

/** /me 接口响应
 * @property is_account - 是否为完整账户
 * @shared
 */
interface MeResponse {
  is_account: boolean;
}

/** chat 页面
 * @param props
 * @server-only
 */
export default async function ChatPage() {
  // (2026-06-17) v2 RBAC: anon 不显示记忆按钮 (/api/memory/* 返 403)
  // 鉴权失败 → 视作 anon, 跟 Header / UserMenu 行为一致
  let isAccount = false;
  try {
    const me = (await getProfile(await serverAuthHeaders())) as MeResponse;
    isAccount = me.is_account;
  } catch {
    isAccount = false;
  }
  return (
    <GuardPage pageKey="chat">
      <div className="flex h-full flex-col">
        <PageHero eyebrow="chat" title="跟产品智能体聊聊" className="shrink-0 pb-6" />

        <Reveal delay={DELAY.primary} className="flex min-h-0 flex-1 flex-col">
          <ChatShell isAccount={isAccount} />
        </Reveal>
      </div>
    </GuardPage>
  );
}
