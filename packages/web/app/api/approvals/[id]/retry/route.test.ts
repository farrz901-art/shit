// Retry BFF 测试 (TDD red → green)
// (2026-06-13) Task 23: BFF /api/approvals/{id}/retry
// (2026-06-14) 不再断言 fetch URL/header, 只测: 200 → 透传, 409 → 透传
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// BFF 调 serverAuthHeaders() 走 next/headers cookies(), 测试环境没 request scope
// 直接 mock 整个 auth.server 模块, 避免触发 next/headers dynamic API
vi.mock("@/lib/api/auth.server", () => ({
  serverAuthHeaders: vi.fn(async () => ({ "x-user-token": "test-token" })),
}));

import { POST as post } from "./route";

const HTTP_OK = 200;
const HTTP_2XX_CEILING = 300;
const HTTP_CONFLICT = 409;

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

const mockResponse = (status: number, body: string, contentType: string): Response => {
  let statusTextValue = "";
  if (status >= HTTP_OK && status < HTTP_2XX_CEILING) {
    statusTextValue = "OK";
  } else {
    statusTextValue = "Err";
  }
  return {
    headers: {
      get: (header: string) => {
        if (header.toLowerCase() === "content-type") {
          return contentType;
        }
        return null;
      },
    },
    ok: status >= HTTP_OK && status < HTTP_2XX_CEILING,
    status,
    statusText: statusTextValue,
    text: async () => body,
  } as unknown as Response;
};

describe("POST /api/approvals/[id]/retry BFF", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("200 → BFF 透传 status + body", async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse(HTTP_OK, JSON.stringify({ apply_status: "none", id: 142 }), "application/json"),
    );
    const req = new Request("http://localhost/api/approvals/142/retry", { method: "POST" });
    const res = await post(req as never, { params: Promise.resolve({ id: "142" }) });
    expect(res.status).toBe(HTTP_OK);
    expect(await res.json()).toEqual({ apply_status: "none", id: 142 });
  });

  it("FastAPI 返 409 → BFF 透传 409", async () => {
    fetchMock.mockResolvedValueOnce(mockResponse(HTTP_CONFLICT, "InvalidState", "text/plain"));
    const req = new Request("http://localhost/api/approvals/142/retry", { method: "POST" });
    const res = await post(req as never, { params: Promise.resolve({ id: "142" }) });
    expect(res.status).toBe(HTTP_CONFLICT);
  });
});
