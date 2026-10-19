// RSC: server 端 fetch datasets, 传 Promise 给 client 子组件 (use(promise) 模式).
// (2026-06-14) 改: 去 async/await, 传 Promise + Suspense fallback
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { DataTableSkeleton } from "@/components/common/table/data-table-skeleton";
import { fetchDatasets } from "@/lib/api/knowledge";
import { DatasetsTable } from "./_components/datasets-table";
import { GuardPage } from "@/components/auth/guard-page";
import { Suspense } from "react";

/** dynamic - 强制 dynamic 渲染, 走 cookie, 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic"; // 走 cookie, 每次请求取最新

/** DatasetsPage - 数据集列表 RSC 页面, server fetch 后传 Promise 给 DatasetsTable
 * @server-only
 */
export default async function DatasetsPage() {
  const datasetsPromise = fetchDatasets();
  return (
    <GuardPage pageKey="knowledge">
      <Suspense fallback={<DataTableSkeleton columns={4} rows={8} />}>
        <DatasetsTable datasetsPromise={datasetsPromise} />
      </Suspense>
    </GuardPage>
  );
}
