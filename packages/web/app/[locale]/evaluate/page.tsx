// 评估历史列表 (2026-06-09; 2026-06-11 改用 DataTable)
// (2026-06-11) i18n: useTranslations + t() 包裹中文文案 + Locale-aware fmtDate
// (2026-06-12) RSC 化: server fetch + 灌 EvaluateListView client 子组件 (Task 19).
// (2026-06-14) Sprint 1.6 改: 跟 nodes/datasets 同步用 Promise + Suspense + use(promise) 模式.
// 失败走 error.tsx 兜 (避免 fetch 抛错整页 500, 见 [[feedback-rsc-throw-must-not-crash-page]])
// (2026-06-23) 迁移: PageGuard → GuardPage, 改用 getPermissions + perm.can() 控数据拉取
import { DataTableSkeleton } from "@/components/common/table/data-table-skeleton";
import { EvaluateListView } from "./_components/evaluate-list-view";
import type { EvaluationRunSummary } from "@/lib/evaluate/types";
import { GuardPage } from "@/components/auth/guard-page";
import { Suspense } from "react";
import { getPermissions } from "@/lib/auth/permission";
import { rscGet } from "@/lib/api/rsc-queries";
import { runsUrl } from "@/lib/api/evaluate";

/** dynamic - 强制 dynamic 渲染, 走 cookie 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic"; // 走 cookie, 每次请求取最新

/** fetchEvaluations - 服务端获取评估运行列表
 * @returns 评估运行摘要数组 Promise
 * @server-only
 */
const fetchEvaluations = (): Promise<EvaluationRunSummary[]> =>
  rscGet<EvaluationRunSummary[]>(runsUrl());

/** EvaluateListPage - 评估历史列表 RSC 页面, 含鉴权数据拉取 + Suspense 兜底
 * @server-only
 */
export default async function EvaluateListPage() {
  // (2026-06-23) GuardPage 仅负责鉴权, 此处再调 getPermissions() 拿 perm 判断数据拉取 (cache hit)
  const perm = await getPermissions();
  // 无权用户不 fetch, 避免 unhandledRejection (2026-06-22 修正)
  // (2026-06-23) runsPromise 必须保持 Promise.resolve([]) 而非 undefined: 客户端 use(promise) 抛错
  const runsPromise: Promise<EvaluationRunSummary[]> = perm.can("evaluate")
    ? fetchEvaluations()
    : Promise.resolve([]);
  return (
    <GuardPage pageKey="evaluate">
      <Suspense fallback={<DataTableSkeleton columns={6} rows={8} />}>
        <EvaluateListView runsPromise={runsPromise} />
      </Suspense>
    </GuardPage>
  );
}
