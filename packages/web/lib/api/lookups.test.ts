// Lookups API 单测
import { ONE, ZERO } from "@/const";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  fetchAdminConfirmToken,
  fetchAdminCreateItem,
  fetchAdminDeleteItem,
  fetchAdminPatchItem,
  fetchAllLookups,
  fetchLookup,
} from "./lookups";

const okResponse = <Data>(responseData: Data): Response =>
  ({
    ok: true,
    status: 200,
    text: async () => JSON.stringify(responseData),
  }) as unknown as Response;

describe("fetchLookup", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("默认 lang=both, only_active=true", async () => {
    const dict = {
      code: "status",
      items: [{ key: "a", label_zh: "A", label_en: "B", sort: 1, is_active: true }],
      label_zh: "状态",
      label_en: "Status",
      version: 1,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse(dict)));
    const result = await fetchLookup("status");
    expect(result.code).toBe("status");
    expect(result.items).toHaveLength(ONE);
  });

  it("传 lang+onlyActive 拼到 query", async () => {
    let capturedUrl = "";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => {
        capturedUrl = url;
        return okResponse({ code: "x", items: [], label_zh: "X", label_en: "X", version: 1 });
      }),
    );
    await fetchLookup("status", { lang: "zh", onlyActive: false });
    expect(capturedUrl).toContain("lang=zh");
    expect(capturedUrl).toContain("only_active=false");
  });
});

describe("fetchAllLookups", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("返 summaries 数组", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({
          dictionaries: [
            { code: "status", label_zh: "状态", label_en: "Status", version: 1, is_active: true },
          ],
        }),
      ),
    );
    const result = await fetchAllLookups();
    expect(result).toHaveLength(ONE);
    expect(result[ZERO].code).toBe("status");
  });
});

describe("Admin APIs", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("fetchAdminCreateItem POST", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          okResponse({ key: "new", label_zh: "新", label_en: "New", sort: 1, is_active: true }),
        ),
    );
    const result = await fetchAdminCreateItem("status", {
      key: "new",
      label_zh: "新",
      label_en: "New",
      sort: 1,
      is_active: true,
    });
    expect(result.key).toBe("new");
  });

  it("fetchAdminPatchItem PATCH", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          okResponse({ key: "a", label_zh: "改", label_en: "A", sort: 1, is_active: true }),
        ),
    );
    const result = await fetchAdminPatchItem("status", "a", { label_zh: "改" });
    expect(result.label_zh).toBe("改");
  });

  it("fetchAdminDeleteItem DELETE 带 X-Confirm-Token", async () => {
    let capturedHeaders: Record<string, string> = {};
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (_url: string, init: RequestInit) => {
        capturedHeaders = (init.headers as Record<string, string>) ?? {};
        return okResponse(undefined);
      }),
    );
    await fetchAdminDeleteItem("status", "a", "tok123");
    expect(capturedHeaders["X-Confirm-Token"]).toBe("tok123");
  });

  it("fetchAdminConfirmToken POST", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ token: "abc", valid_until: "2026-07-01T00:00:00Z" })),
    );
    const result = await fetchAdminConfirmToken();
    expect(result.token).toBe("abc");
  });

  it("fetchAdminSystemInfo GET", async () => {
    const EXPECTED_DICTS_COUNT = 5;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ readonly: false, dicts_count: EXPECTED_DICTS_COUNT })),
    );
    const { fetchAdminSystemInfo } = await import("./lookups");
    const result = await fetchAdminSystemInfo();
    expect(result.readonly).toBe(false);
    expect(result.dicts_count).toBe(EXPECTED_DICTS_COUNT);
  });

  it("fetchAdminAuditLog 返 entries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({
          entries: [
            {
              id: 1,
              ts: "2026-06-01T00:00:00Z",
              actor_id: 1,
              action: "create",
              before: null,
              after: {},
              ip: null,
              target_id: "status:a",
            },
          ],
        }),
      ),
    );
    const { fetchAdminAuditLog } = await import("./lookups");
    const result = await fetchAdminAuditLog("status");
    expect(result).toHaveLength(ONE);
    expect(result[ZERO].action).toBe("create");
  });

  it("fetchAdminAuditLog 按 key 过滤", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({
          entries: [
            {
              id: 1,
              ts: "t1",
              actor_id: 1,
              action: "create",
              before: null,
              after: {},
              ip: null,
              target_id: "status:a",
            },
            {
              id: 2,
              ts: "t2",
              actor_id: 1,
              action: "update",
              before: null,
              after: {},
              ip: null,
              target_id: "status:b",
            },
          ],
        }),
      ),
    );
    const { fetchAdminAuditLog } = await import("./lookups");
    const result = await fetchAdminAuditLog("status", "a");
    expect(result).toHaveLength(ONE);
    expect(result[ZERO].action).toBe("create");
  });
});
