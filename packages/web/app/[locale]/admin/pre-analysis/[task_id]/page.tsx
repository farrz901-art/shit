// admin/pre-analysis/[task_id]/page.tsx — RSC entry (2026-07-02 PR6)
// (2026-07-03) Next 16: params 是 Promise, 必须 await, 否则 client 拿 undefined → fetch /tasks/undefined.

import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisDetailClient } from "./_components/admin-pre-analysis-detail-client";

/**
 * admin/pre-analysis 详情页 (RSC)
 *
 * 显示 task 详情 + 产物清单 + 下载 zip 按钮.
 * 从路由参数获取 task_id, 传给 AdminPreAnalysisDetailClient.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数 Promise
 * @param props.params.task_id - 预分析任务 ID
 * @server-only
 */
export default async function AdminPreAnalysisDetailPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisDetailClient params={{ task_id }} />
    </GuardPage>
  );
}
