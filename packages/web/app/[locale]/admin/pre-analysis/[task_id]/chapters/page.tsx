// admin/pre-analysis/[task_id]/chapters/page.tsx — RSC entry (2026-07-09)
// 调 AdminPreAnalysisChaptersClient 渲染章节树查看页.
// 跟 [task_id]/page.tsx 模式一致 (params 是 Promise, await 后传 sync value).

import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisChaptersClient } from "./_components/admin-pre-analysis-chapters-client";

/**
 * admin/pre-analysis 章节目录页 (RSC)
 *
 * 渲染章节树查看页. 路由参数 task_id 透传给 client 子组件.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数 Promise
 * @param props.params.task_id - 预分析任务 ID
 * @server-only
 */
export default async function AdminPreAnalysisChaptersPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisChaptersClient params={{ task_id }} />
    </GuardPage>
  );
}
