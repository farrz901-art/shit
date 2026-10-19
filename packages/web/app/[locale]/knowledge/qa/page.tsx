// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage (内部调 getPermissions, 0 额外 fetch)
import { GuardPage } from "@/components/auth/guard-page";
import { QASubmitForm } from "./_components/qa-submit-form";

/**
 * 动态渲染模式: 走 cookie, 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic";

/**
 * QAPage - QA 录入页 RSC 入口
 * @server-only
 */
export default async function QAPage() {
  return (
    <GuardPage pageKey="knowledge">
      <QASubmitForm />
    </GuardPage>
  );
}
