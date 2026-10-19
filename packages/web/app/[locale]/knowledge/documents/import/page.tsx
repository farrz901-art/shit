// RSC: 文档导入子页 (2026-06-12) — 简单 server wrapper, 3 步流程搬到 client 子组件.
// 提交按钮在子组件里改 form action + commitDocuments server action (Task 12).
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { DocumentsImportForm } from "./_components/documents-import-form";
import { GuardPage } from "@/components/auth/guard-page";

/**
 * 动态渲染模式: DatasetId 走 zustand (client), 跟父级 tab 同步
 * @server-only
 */
export const dynamic = "force-dynamic"; // DatasetId 走 zustand (client), 跟父级 tab 同步

/**
 * ImportPage - 文档导入 RSC 入口
 * @server-only
 */
export default async function ImportPage() {
  return (
    <GuardPage pageKey="knowledge">
      <DocumentsImportForm />
    </GuardPage>
  );
}
