// /account/restore — 撤销注销页 (anon OK, token 验证)
// (2026-06-18) T4.3 实现: 用户从邮件点链接进入, 输入密码撤销
// 简化版本: 必须登录且 is_pending_deletion=true 才能进, 输密码撤销
// 实际 token 验证需要查询 DeletionRestore 表 (T5.1 完成 purge 时一起做)
import { Card } from "@/components/ui/card";
import { RestoreForm } from "./restore-form";
import { getProfile } from "@/lib/api/account";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** 当前用户信息 (用于鉴权判断)
 * @property is_account - 是否为真账号用户
 * @property is_pending_deletion - 是否处于待注销状态
 * @property deletion_expires_at - 注销生效截止时间
 */
interface MeResponse {
  is_account: boolean;
  is_pending_deletion: boolean;
  deletion_expires_at: string | null;
}

/** 生成页面 title
 * @returns Metadata 对象, title 为 "撤销注销 - RAG"
 */
export const generateMetadata = async () => {
  const translate = await getTranslations();
  return { title: `${translate("撤销注销")} - RAG` };
};

/** 撤销注销页面: 校验用户登录状态及是否 pending_deletion, 条件满足时展示 RestoreForm
 * @returns 页面 JSX
 * @server-only
 */
export default async function RestoreAccountPage() {
  let me: MeResponse | null = null;
  try {
    me = (await getProfile(await serverAuthHeaders())) as MeResponse;
  } catch {
    redirect("/login?next=/account/restore");
  }
  // Anon → 跳登录
  if (!me.is_account) {
    redirect("/login?next=/account/restore");
  }
  // 非 pending → 跳首页 (没有注销可撤销)
  if (!me.is_pending_deletion) {
    redirect("/");
  }
  const translate = await getTranslations();
  return (
    <div className="mx-auto max-w-md p-6">
      <Card className="p-6">
        <h1 className="display mb-4 text-2xl">{translate("撤销注销")}</h1>
        <p className="mb-4 text-sm text-muted-foreground">{translate("注销账号说明")}</p>
        <RestoreForm />
      </Card>
    </div>
  );
}
