// RSC: /health 监控状态页 (Task 26, 2026-06-12 redesign) — server 预取 + HydrationBoundary.
// B 档 (Task 23): health/layout.tsx 包了 QueryClientProvider,
// RSC 预取后 dehydrate 传过 boundary, 客户端 useQuery (HealthClient) 接管 10s 轮询.
// QueryKey 跟 HealthClient 内部 qKeys.health.system() 一致.
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { HydrationBoundary, dehydrate } from "@tanstack/react-query";
import { getRscQueryClient, prefetchQuery } from "@/lib/api/rsc-queries";
import { API_BASE } from "@/lib/api/config";
import { HealthClient } from "./_components/health-client";
import type { HealthPayload } from "@/lib/api/health";
import { GuardPage } from "@/components/auth/guard-page";
import { qKeys } from "@/lib/api/query-keys";

/** dynamic - 强制 dynamic 渲染, 走 cookie (admin), 每次请求取最新
 * @server-only
 */
export const dynamic = "force-dynamic"; // 走 cookie (admin), 每次请求取最新

/**
 * HealthPage — 监控状态页 RSC 入口, 服务端预取健康数据 + HydrationBoundary 传给 HealthClient
 * @returns JSX 元素
 * @server-only
 */
export default async function HealthPage() {
  const qc = await getRscQueryClient();
  // 预取: prefetchQuery 内部走 authHeaders (server-only cookie) + fetch.
  // 失败抛错让 Next error.tsx 兜住.
  await prefetchQuery<HealthPayload>(qc, qKeys.health.system(), `${API_BASE}/api/health/system`);

  return (
    <GuardPage pageKey="health">
      <HydrationBoundary state={dehydrate(qc)}>
        <HealthClient />
      </HydrationBoundary>
    </GuardPage>
  );
}
