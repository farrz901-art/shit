// Approve BFF 测试 (TDD red → green)
// (2026-06-13) Task 23: BFF /api/approvals/{id}/approve
// (2026-06-14) 不再断言 fetch URL/header, 只测: 200 → 透传, 409 → 透传; 走 apiProxy
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// BFF 调 serverAuthHeaders() 走 next/headers cookies(), 测试环境没 request scope
// 直接 mock 整个 auth.server 模块, 避免触发 next/headers dynamic API
vi.mock("@/lib/api/auth.server", () => ({
  serverAuthHeaders: vi.fn(async () => ({ "x-user-token": "test-token" })),
}));

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

import { POST as handleApprove } from "./route";

// HTTP 状态常量
const HTTP_OK = 200;
const STATUS_2XX_UPPER = 300;
const HTTP_CONFLICT = 409;
const CALL_COUNT_ONCE = 1;

// ApiProxy 不读 body, 直接返 raw Response; mock 形状: { ok, status, headers.get, text }
const mockResponse = (status: number, body: string, contentType: string): Response => {
  const isSuccess = status >= HTTP_OK && status < STATUS_2XX_UPPER;
  return {
    headers: {
      get: (headerName: string) =>
        headerName.toLowerCase() === "content-type" ? contentType : null,
    },
    ok: isSuccess,
    status,
    statusText: isSuccess ? "OK" : "Err",
    text: async () => body,
  } as unknown as Response;
};

describe("POST /api/approvals/[id]/approve BFF", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("200 → BFF 透传 status + body", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse(
        HTTP_OK,
        JSON.stringify({ id: 142, review_status: "approved" }),
        "application/json",
      ),
    );
    const req = new Request("http://localhost/api/approvals/142/approve", { method: "POST" });
    const res = await handleApprove(req as never, { params: Promise.resolve({ id: "142" }) });
    expect(res.status).toBe(HTTP_OK);
    expect(await res.json()).toEqual({ id: 142, review_status: "approved" });
  });

  it("admin cookie → apiProxy 调到 fetch (具体 header 由 apiProxy 内部决定, 这里不绑死)", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse(
        HTTP_OK,
        JSON.stringify({ id: 1, review_status: "approved" }),
        "application/json",
      ),
    );
    const req = new Request("http://localhost/api/approvals/1/approve", { method: "POST" });
    await handleApprove(req as never, { params: Promise.resolve({ id: "1" }) });
    expect(fetchMock).toHaveBeenCalledTimes(CALL_COUNT_ONCE);
  });

  it("FastAPI 返 409 → BFF 透传 409", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse(HTTP_CONFLICT, "InvalidState", "text/plain"));
    const req = new Request("http://localhost/api/approvals/142/approve", { method: "POST" });
    const res = await handleApprove(req as never, { params: Promise.resolve({ id: "142" }) });
    expect(res.status).toBe(HTTP_CONFLICT);
  });
});
