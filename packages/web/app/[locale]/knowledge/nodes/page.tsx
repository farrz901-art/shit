// RSC: server 端 fetch /api/kg/nodes, 传 Promise 给 NodesTable (use(promise) 模式).
// (2026-06-14) 改: 去 async/await, 传 Promise + Suspense fallback
// (2026-06-17) v2 RBAC: 套 PageGuard 做 4 层防护第 2 层
// (2026-06-23) 改用 GuardPage
import { DataTableSkeleton } from "@/components/common/table/data-table-skeleton";
import { fetchNodes } from "@/lib/api/knowledge";
import { NodesTable } from "./_components/nodes-table";
import { GuardPage } from "@/components/auth/guard-page";
import { Suspense } from "react";

/**
 * 动态渲染模式
 * @server-only
 */
export const dynamic = "force-dynamic";

/**
 * NodesPage - 节点列表页 RSC 入口
 * @server-only
 */
export default async function NodesPage() {
  const nodesPromise = fetchNodes();
  return (
    <GuardPage pageKey="knowledge">
      <Suspense fallback={<DataTableSkeleton columns={4} rows={10} />}>
        <NodesTable nodesPromise={nodesPromise} />
      </Suspense>
    </GuardPage>
  );
}
