// RSC: server 端 fetch /api/kg/stats?type=dify, prop 灌 DocumentsEntry client 子组件.
// 不再 "use client" — 真正的 server component (2026-06-12, 跟 datasets 试点同模式).
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { DocumentsEntry, type DocumentsStats } from "./_components/documents-entry";
import { GuardPage } from "@/components/auth/guard-page";
import { fetchStats } from "@/lib/api/knowledge";

/**
 * 动态渲染模式: 走 cookie, 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic";

/**
 * DocumentsPage - 文档库列表页 RSC 入口
 * @server-only
 */
export default async function DocumentsPage() {
  // /api/kg/stats?type=dify 直接返 { datasets, documents }, 见 service/src/kg/router.py:99-100
  let stats: DocumentsStats = { datasets: 0, documents: 0 };
  try {
    const fullStats = await fetchStats();
    stats = fullStats.dify;
  } catch {
    // 后端不可达时不阻塞整页，用空数据兜底
  }
  return (
    <GuardPage pageKey="knowledge">
      <DocumentsEntry stats={stats} />
    </GuardPage>
  );
}
