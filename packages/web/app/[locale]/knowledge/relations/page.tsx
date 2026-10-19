// RSC: server 端 fetch /api/kg/relationships, 传 Promise 给 RelationsTable (use(promise) 模式).
// (2026-06-14) 改: 去 async/await, 传 Promise + Suspense fallback
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { DataTableSkeleton } from "@/components/common/table/data-table-skeleton";
import { GuardPage } from "@/components/auth/guard-page";
import { fetchRelations } from "@/lib/api/knowledge";
import { RelationsTable } from "./_components/relations-table";
import { Suspense } from "react";

/**
 * 动态渲染模式
 * @server-only
 */
export const dynamic = "force-dynamic";

/**
 * RelationsPage - 关系列表页 RSC 入口
 * @server-only
 */
export default async function RelationsPage() {
  const relationsPromise = fetchRelations();
  return (
    <GuardPage pageKey="knowledge">
      <Suspense fallback={<DataTableSkeleton columns={3} rows={10} />}>
        <RelationsTable relationsPromise={relationsPromise} />
      </Suspense>
    </GuardPage>
  );
}
