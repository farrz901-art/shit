"use server";
// 评估 server actions: createRun / deleteRun.
// 跟 lib/api/evaluate.ts (客户端 + BFF multipart) 并存: 客户端表单仍走 BFF multipart;
// Server action 用于 RSC 表单/链接, JSON 体直接透传 FastAPI.
//
// (2026-06-27) deleteRun 改走 lib/server/evaluate.ts 直连后端,
// 不再绕 BFF (避免额外 hop + cookie-vs-header 鉴权混乱).
// (2026-06-14) createRun 改走 apiFetch(); auth + Content-Type + 错误归一都在 wrapper 里
// (2026-06-16) 加 serverAuthHeaders
import { actionError } from "@/lib/actions-utils";
import { createRunJson } from "@/lib/api/evaluate";
import { deleteRunById } from "@/lib/server/evaluate";
import { revalidatePath } from "next/cache";
import { serverAuthHeaders } from "@/lib/api/auth.server";

/** 统一返回包装 — 永不抛, 错误走 error 字段. */
export type ActionResult<TData> = { ok: true; data: TData } | { ok: false; error: string };

/** 创建评估批的入参
 * @property name - 评估批名称
 */
interface CreateRunInput {
  name: string;
}

/** 创建评估批的返回结果
 * @property id - 评估批 ID
 * @property status - 评估批状态
 */
interface CreateRunResult {
  id: number;
  status: string;
}

/** 创建评估批 — JSON 版 (客户端 multipart 仍走 BFF: lib/api/evaluate.ts)
 * @param input - 创建入参 (name)
 * @returns 创建结果包装
 * @server-only
 */
export const createRun = async (input: CreateRunInput): Promise<ActionResult<CreateRunResult>> => {
  try {
    const data = await createRunJson<CreateRunResult>(input, await serverAuthHeaders());
    revalidatePath("/[locale]/evaluate");
    return { data, ok: true };
  } catch (error) {
    return actionError(error);
  }
};

/** 删除评估批 — DELETE /api/evaluate/runs/{id}.
 *  (2026-06-27) 直连后端, 不绕 BFF.
 * @param id 评估批 ID
 * @returns ActionResult<...>
 * @throws ApiError / NetworkError
 * @server-only
 */
export const deleteRun = async (id: string): Promise<ActionResult<unknown>> => {
  try {
    const data = await deleteRunById(id);
    revalidatePath("/[locale]/evaluate");
    revalidatePath(`/[locale]/evaluate/${id}`);
    return { data, ok: true };
  } catch (error) {
    return actionError(error);
  }
};
