// EvaluateApi 测试只覆盖**行为**, 不重复测 apiFetch 内部 (URL/headers/Content-Type 等)
import { HTTP_OK, HTTP_UNAUTHORIZED } from "@/const";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import { cancelRun, createRun, runCancelUrl, runDetailUrl, runsUrl, templateUrl } from "./evaluate";

const okResponse = (data: unknown, status = HTTP_OK): Response =>
  ({
    ok: true,
    status,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const errResponse = (status: number, statusText: string): Response =>
  ({ ok: false, status, statusText, text: async () => "" }) as unknown as Response;

describe("evaluate API functions", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });
  afterEach(() => vi.unstubAllGlobals());

  // URL 工厂返回**路径** (相对路径), apiFetch 内部拼 API_BASE
  it("URL 工厂返相对路径 (不含 base)", () => {
    expect(runsUrl()).toBe("/api/evaluate/runs");
    // oxlint-disable-next-line no-magic-numbers -- 测试数据: 42 是模拟的 run ID
    expect(runDetailUrl(42)).toBe("/api/evaluate/runs/42");
    // oxlint-disable-next-line no-magic-numbers -- 测试数据: 42 是模拟的 run ID
    expect(runCancelUrl(42)).toBe("/api/evaluate/runs/42/cancel");
    expect(templateUrl()).toBe("/api/evaluate/template");
  });

  it("createRun 返 { id, status }", async () => {
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse({ id: 1, status: "pending" })));
    const file = new File(["q,a\n"], "eval.csv", { type: "text/csv" });
    // oxlint-disable-next-line no-magic-numbers -- 测试数据: 最大运行数
    const out = await createRun(file, 5);
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(out.id).toBe(1);
    expect(out.status).toBe("pending");
  });

  it("createRun 4xx 抛 ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(errResponse(HTTP_UNAUTHORIZED, "Unauthorized")),
    );
    const file = new File(["x"], "x.csv", { type: "text/csv" });
    // oxlint-disable-next-line no-magic-numbers -- 测试数据: 1 个文件
    await expect(createRun(file, 1)).rejects.toBeInstanceOf(ApiError);
  });

  it("cancelRun 返 { cancelled: true }", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse({ cancelled: true })));
    // oxlint-disable-next-line no-magic-numbers -- 测试数据: 42 是模拟的 run ID
    const out = await cancelRun(42);
    expect(out.cancelled).toBe(true);
  });
});
