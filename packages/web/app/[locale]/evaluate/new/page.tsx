// RSC: 新建评估页 (2026-06-12) — Task 20 RSC 化
//   Page 只做 server wrapper, 把交互态/Papa Parse/multipart 上传都搬到 client 子组件
//   Client 子组件 (EvaluateNewForm) 走 BFF multipart: evaluateApi.createRun
//   没用 _actions/evaluate.ts createRun — 那是 JSON variant, 跟 multipart 不兼容
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { EvaluateNewForm } from "./_components/evaluate-new-form";
import { GuardPage } from "@/components/auth/guard-page";

/** dynamic - 强制 dynamic 渲染, 走 cookie 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic";

/** NewEvalPage - 新建评估 RSC 页面, 只做 server wrapper 并包裹 GuardPage 鉴权
 * @server-only
 */
export default async function NewEvalPage() {
  return (
    <GuardPage pageKey="evaluate">
      <EvaluateNewForm />
    </GuardPage>
  );
}
