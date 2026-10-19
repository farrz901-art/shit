import { HydrationBoundary, dehydrate } from "@tanstack/react-query";
import { getRscQueryClient, prefetchQuery } from "@/lib/api/rsc-queries";
import type { IngestTask } from "@/lib/api/ingest";
import { OutputListClient } from "./_components/output-list-client";
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { GuardPage } from "@/components/auth/guard-page";
import { getTranslations } from "next-intl/server";
import { qKeys } from "@/lib/api/query-keys";

/**
 * 动态渲染模式
 * @server-only
 */
export const dynamic = "force-dynamic";

/**
 * generateMetadata - 生成页面元数据
 * @returns 页面标题
 * @server-only
 */
export const generateMetadata = async () => {
  const tr = await getTranslations();
  return { title: `${tr("Output")} - RAG` };
};

/**
 * OutputPage - 文档结构化列表页 RSC 入口
 * @server-only
 */
export default async function OutputPage() {
  const queryClient = await getRscQueryClient();
  // 预取: require_page("output") 守卫, user 角色可访问 (需 migration 设 knowledge/output 权限)
  await prefetchQuery<IngestTask[]>(queryClient, qKeys.output.list(), `/api/ingest/tasks`);

  return (
    <GuardPage pageKey="output">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <OutputListClient />
      </HydrationBoundary>
    </GuardPage>
  );
}
