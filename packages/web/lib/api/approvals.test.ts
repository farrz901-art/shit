// ApprovalsApi 测试只覆盖**行为** (输入→输出 + 错误归一),
// 不重复测 apiFetch 内部实现 (URL 拼装 / 鉴权头注入 / Content-Type 等)
import { HTTP_CREATED, HTTP_FORBIDDEN, HTTP_NOT_FOUND, HTTP_OK } from "@/const";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import { approve, getDetail, reject, retry, submit } from "./approvals";

const okResponse = (data: unknown, status = HTTP_OK): Response =>
  ({
    ok: true,
    status,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const errResponse = (status: number, statusText: string, detail?: string): Response => {
  const textContent = detail ? JSON.stringify({ detail }) : "";
  return {
    ok: false,
    status,
    statusText,
    text: async () => textContent,
  } as unknown as Response;
};

const sampleApproval = {
  applied_at: null,
  apply_status: "none" as const,
  created_at: "2026-06-13T00:00:00Z",
  error_msg: null,
  id: 142,
  kind: "qa" as const,
  rejection_note: null,
  rejection_reason: null,
  review_status: "pending" as const,
  reviewed_at: null,
  reviewer_id: null,
  submitter_id: 1,
};

describe("approvalsApi", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("submit 返完整 Approval", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse(sampleApproval, HTTP_CREATED)));
    const out = await submit("qa", { answer: "a", dataset_id: "ds1", question: "q" });
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(out.id).toBe(142);
    expect(out.review_status).toBe("pending");
  });

  it("getDetail 返 approval 含 payload", async () => {
    vi.stubGlobal(
      "fetch",
      // oxlint-disable-next-line no-magic-numbers -- 测试数据
      vi.fn().mockResolvedValue(okResponse({ ...sampleApproval, id: 7, payload: { val: 1 } })),
    );
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    const out = await getDetail(7);
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(out.id).toBe(7);
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(out.payload).toEqual({ val: 1 });
  });

  it("approve 走 BFF, 返 approval", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ ...sampleApproval, review_status: "approved" })),
    );
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    const out = await approve(142);
    expect(out.review_status).toBe("approved");
  });

  it("reject 带 reason + note, 返 approval", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({
          ...sampleApproval,
          rejection_reason: "low_quality",
          review_status: "rejected",
        }),
      ),
    );
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    const out = await reject(142, "low_quality", "测试备注");
    expect(out.review_status).toBe("rejected");
    expect(out.rejection_reason).toBe("low_quality");
  });

  it("retry 返 approval (apply_status 重置)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ ...sampleApproval, apply_status: "none" })),
    );
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    const out = await retry(142);
    expect(out.apply_status).toBe("none");
  });

  it("submit 4xx 抛 ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(errResponse(HTTP_NOT_FOUND, "Not Found", "not found")),
    );
    await expect(submit("qa", {})).rejects.toBeInstanceOf(ApiError);
  });

  it("approve 4xx 抛 ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(errResponse(HTTP_FORBIDDEN, "Forbidden")));
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    await expect(approve(142)).rejects.toBeInstanceOf(ApiError);
  });
});
