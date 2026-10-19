// 单次评估详情 (2026-06-09) - 改造自原 /evaluate/page.tsx
// (2026-06-11) i18n: useTranslations + translate() + LocalizedLink
// (2026-06-12) RSC 化: server fetch + 灌 RunDetailView client 子组件 (Task 19).
// Next 16: params 是 Promise, 必须 await.
// (2026-06-23) 迁移: PageGuard + getMyPermissions → GuardPage
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import type { EvaluationRun } from "@/lib/evaluate/types";
import { GuardPage } from "@/components/auth/guard-page";
import { RunDetailView } from "./_components/run-detail-view";
import { getTranslations } from "next-intl/server";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { getEvaluationRun } from "@/lib/api/evaluate";

/** 每次请求动态渲染 (走 cookie 鉴权) @shared */
export const dynamic = "force-dynamic";

/** 单次评估详情页 (RSC)
 * @param params - 路由参数 (含 id)
 * @returns 评估详情 JSX
 * @server-only
 */
export default async function EvaluationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let run: EvaluationRun | null = null;
  try {
    run = await getEvaluationRun(id, await serverAuthHeaders());
  } catch {
    // 后端不可达时不阻塞整页，下方 ErrorBanner 兜底
  }

  const translate = await getTranslations();
  return (
    <GuardPage pageKey="evaluate">
      {run ? (
        <RunDetailView run={run} id={id} />
      ) : (
        <ErrorBanner
          variant="destructive"
          description={translate("后端服务不可达, 请检查 main_py 是否在 8000 端口运行")}
        />
      )}
    </GuardPage>
  );
}
