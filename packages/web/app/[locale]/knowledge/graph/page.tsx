// RSC: server 端 fetch /api/kg/stats?type=neo4j, prop 灌 GraphView client 子组件.
// 不再 "use client" — 真正的 server component (2026-06-12, 跟 datasets/documents 同模式).
// (2026-06-17) v2 RBAC: 套 PageGuard 做 4 层防护第 2 层
// (2026-06-23) 改用 GuardPage, 删 getMyPermissions
import { type GraphStats, GraphView } from "./_components/graph-view";
import { GuardPage } from "@/components/auth/guard-page";
import { fetchStats } from "@/lib/api/knowledge";

/**
 * 动态渲染模式: 走 cookie, 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic";

/**
 * GraphPage - 知识图谱入口 RSC 页面
 * @server-only
 */
export default async function GraphPage() {
  // /api/kg/stats?type=neo4j 直接返 { nodes, relations }, 见 service/src/kg/router.py
  let stats: GraphStats = { nodes: 0, relations: 0 };
  try {
    const fullStats = await fetchStats();
    stats = fullStats.neo4j;
  } catch {
    // 后端不可达时不阻塞整页，用空数据兜底
  }
  return (
    <GuardPage pageKey="knowledge">
      <GraphView stats={stats} />
    </GuardPage>
  );
}
