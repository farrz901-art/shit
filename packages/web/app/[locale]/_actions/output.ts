"use server";
// Output 相关 server actions (Task 25, 2026-06-12): cancelTask.
// 简单数据 POST 用, 不用 BFF. 跟 _actions/evaluate.ts / _actions/knowledge.ts 同模式:
//   - 成功 → revalidatePath 让 RSC 重新预取
//   - 失败 → 不 revalidate, 错误走 ActionResult.error 字段
// (2026-06-14) 改走 apiFetch()
// (2026-06-16) 加 serverAuthHeaders
import { actionError } from "@/lib/actions-utils";
import type { ActionResult } from "./evaluate";
import { cancelTask as cancelIngestTask } from "@/lib/api/ingest";
import { revalidatePath } from "next/cache";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** 取消一个 ingest 任务 — POST /api/ingest/tasks/{id}/cancel.
 *
 * 成功后 revalidatePath 让 RSC 重新预取, 客户端 RQ 用同 queryKey (qKeys.output.detail(id)) 接管.
 * 失败时返 { ok: false, error }, 不 revalidate, 避免污染下一轮预取.
 * @param taskId 任务 ID
 * @returns ActionResult<...>
 * @throws ApiError / NetworkError
 * @server-only
 */
export const cancelTask = async (taskId: string): Promise<ActionResult<{ ok: true }>> => {
  try {
    await cancelIngestTask(taskId, await serverAuthHeaders());
    revalidatePath(`/[locale]/output/${taskId}`);
    return { data: { ok: true }, ok: true };
  } catch (error) {
    return actionError(error);
  }
};
