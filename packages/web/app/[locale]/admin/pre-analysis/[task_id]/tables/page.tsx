// admin/pre-analysis/[task_id]/tables/page.tsx — RSC entry (2026-07-09)
// 调 AdminPreAnalysisTablesClient 渲染表格 viewer 页.
// 跟 chapters/page.tsx + flagged/page.tsx 同 shape (params 是 Promise, await 后传 sync value).

import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisTablesClient } from "./_components/admin-pre-analysis-tables-client";

/**
 * admin/pre-analysis 表格查看页 (RSC).
 *
 * 渲染表格 viewer. 路由参数 task_id 透传给 client 子组件.
 *
 * @param props - 组件属性
 * @param props.params - 路由参数 Promise
 * @param props.params.task_id - 预分析任务 ID
 * @server-only
 */
export default async function AdminPreAnalysisTablesPage({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisTablesClient params={{ task_id }} />
    </GuardPage>
  );
}
