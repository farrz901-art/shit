import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchDifyHealth, fetchSystem } from "./health";

const okResponse = <Data>(responseData: Data): Response =>
  ({
    ok: true,
    status: 200,
    text: async () => JSON.stringify(responseData),
  }) as unknown as Response;

describe("healthApi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("fetchDifyHealth GET /api/kg/health", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse({ ok: true })));
    const result = await fetchDifyHealth();
    expect(result.ok).toBe(true);
  });

  it("fetchSystem GET /api/health/system", async () => {
    const payload = {
      checked_at: "2026-06-01T00:00:00Z",
      python: { status: "ok", latency_ms: 10, error: null, extra: {} },
      dify: { status: "ok", latency_ms: 20, error: null, extra: {} },
      neo4j: { status: "ok", latency_ms: 30, error: null, extra: {} },
      pgvector: { status: "ok", latency_ms: 40, error: null, extra: {} },
      minio: { status: "ok", latency_ms: 50, error: null, extra: {} },
      redis: { status: "ok", latency_ms: 60, error: null, extra: {} },
      system: { status: "ok", latency_ms: 70, error: null, extra: {} },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse(payload)));
    const result = await fetchSystem();
    expect(result.python.status).toBe("ok");
    expect(result.dify.status).toBe("ok");
    expect(result.neo4j.status).toBe("ok");
  });
});
