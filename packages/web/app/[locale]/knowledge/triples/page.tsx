// RSC: 三元组录入 (2026-06-12 redesign) — server 端预取 schema, 灌 TriplesForm client 子组件.
// 提交走 createTriples server action (Task 12 建的), form action pattern 跟 documents/import 一致.
// 不再 "use client" — 真正的 server component (跟 graph/nodes/relations 同模式).
// (2026-06-14) 改走 apiFetch()
// (2026-06-17) v2 RBAC: 套 PageGuard 做 4 层防护第 2 层
// (2026-06-23) 改用 GuardPage
import { GuardPage } from "@/components/auth/guard-page";
import { TriplesForm } from "./_components/triples-form";
import { fetchSchema } from "@/lib/api/knowledge";

/**
 * 动态渲染模式: 走 cookie, 每次请求取最新
 * @client-bff
 */
export const dynamic = "force-dynamic";

/**
 * DEFAULT_DOMAIN - 默认 domain, 跟 zustand store 里的初始值保持一致; 切换 domain 由客户端 store 触发 router.refresh()
 * @shared
 */
const DEFAULT_DOMAIN = "motor";

/**
 * TriplesPage - 三元组录入 RSC 页面
 * @client-bff
 */
export default async function TriplesPage() {
  const schema = await fetchSchema(DEFAULT_DOMAIN);
  return (
    <GuardPage pageKey="knowledge">
      <TriplesForm schema={schema} />
    </GuardPage>
  );
}
