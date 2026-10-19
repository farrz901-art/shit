// admin/pre-analysis/[task_id]/flagged/page.tsx — RSC entry (2026-07-09)
// 调 AdminPreAnalysisFlaggedClient 渲染标记段落实体表.
// 跟 chapters/page.tsx 同 shape.

import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisFlaggedClient } from "./_components/admin-pre-analysis-flagged-client";

/**
 * admin/pre-analysis 段落提取页 (RSC)
 *
 * 渲染标记段落实体表. 路由参数 task_id 透传给 client 子组件.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数 Promise
 * @param props.params.task_id - 预分析任务 ID
 * @server-only
 */
export default async function AdminPreAnalysisFlaggedPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisFlaggedClient params={{ task_id }} />
    </GuardPage>
  );
}
