// admin/pre-analysis/page.tsx - 列表页 (2026-07-02 PR5) — RSC entry
//
// client 子组件走 GuardPage (Server Component 不能被 client 引用为 import 后立即使用,
// 但作为 JSX child 是允许的 — React 会把 GuardPage 当作 children 渲染).

import { GuardPage } from "@/components/auth/guard-page";
import { AdminPreAnalysisClient } from "./_components/admin-pre-analysis-client";

/**
 * admin/pre-analysis 列表页 — 上传 PDF + 列出历史预分析任务
 * @returns 预分析列表页面
 * @client-bff
 */
export default function AdminPreAnalysisPage() {
  return (
    <GuardPage pageKey="admin">
      <AdminPreAnalysisClient />
    </GuardPage>
  );
}
