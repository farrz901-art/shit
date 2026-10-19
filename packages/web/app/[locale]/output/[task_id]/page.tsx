import { HydrationBoundary, dehydrate } from "@tanstack/react-query";
import { getRscQueryClient, prefetchQuery } from "@/lib/api/rsc-queries";
import { API_BASE } from "@/lib/api/config";
import type { IngestTask } from "@/lib/api/ingest";
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { GuardPage } from "@/components/auth/guard-page";
import { TaskDetailClient } from "./_components/task-detail-client";
import { qKeys } from "@/lib/api/query-keys";

/**
 * 动态渲染模式
 * @server-only
 */
export const dynamic = "force-dynamic";

/**
 * TaskDetailPage - 任务详情页 RSC 入口
 * @param props.params - 路由参数 Promise
 * @server-only
 */
export default async function TaskDetailPage({ params }: { params: Promise<{ task_id: string }> }) {
  const { task_id } = await params;
  const qc = await getRscQueryClient();
  // 预取: require_page("output") 守卫, user 角色可访问
  await prefetchQuery<IngestTask>(
    qc,
    qKeys.output.detail(task_id),
    `${API_BASE}/api/ingest/tasks/${encodeURIComponent(task_id)}`,
  );

  return (
    <GuardPage pageKey="output">
      <HydrationBoundary state={dehydrate(qc)}>
        <TaskDetailClient taskId={task_id} />
      </HydrationBoundary>
    </GuardPage>
  );
}
