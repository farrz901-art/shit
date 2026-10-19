// 端到端验证客户端方法 → fetch 调用 + JSON parse
import { THREE, ZERO } from "@/const";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const loadClient = async () => {
  // 动态 import + reset modules 让 client 重新读 process.env
  vi.resetModules();
  return await import("./dify-datasets");
};

describe("DifyDatasets", () => {
  let fetchMock: ReturnType<typeof vi.fn> = vi.fn();

  beforeEach(() => {
    process.env.DIFY_BASE_URL = "https://dify.test";
    process.env.DIFY_DATASET_API_KEY = "test-key";
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("listDatasets 走 GET /datasets, 返回 Dataset[] (提取 .data)", async () => {
    // Dify API 实际返回 { data: Dataset[], has_more, total, ... }, 不是裸数组
    const { DifyDatasets } = await loadClient();
    fetchMock.mockResolvedValueOnce({
      json: async () => ({
        data: [{ document_count: 3, id: "ds1", name: "FAQ" }],
        has_more: false,
        total: 1,
      }),
      ok: true,
    });
    const out = await DifyDatasets.listDatasets();
    expect(Array.isArray(out)).toBe(true);
    const [firstDataset] = out;
    expect(firstDataset.id).toBe("ds1");
    expect(firstDataset.document_count).toBe(THREE);
    const [firstCall] = fetchMock.mock.calls;
    const [url] = firstCall;
    expect(url).toBe("https://dify.test/datasets?limit=100");
  });

  it("createDocumentByText 走 POST 带 indexing_technique", async () => {
    const { DifyDatasets } = await loadClient();
    fetchMock.mockResolvedValueOnce({
      json: async () => ({ dataset_id: "ds1", id: "doc1", indexing_status: "queued", name: "Q1" }),
      ok: true,
    });
    const out = await DifyDatasets.createDocumentByText("ds1", "Q1", "Q? A!", "high_quality");
    expect(out.indexing_status).toBe("queued");
    const [, init] = fetchMock.mock.calls[ZERO];
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body);
    expect(body.indexing_technique).toBe("high_quality");
  });

  it("listDocuments 走 GET /datasets/{id}/documents", async () => {
    const { DifyDatasets } = await loadClient();
    fetchMock.mockResolvedValueOnce({
      json: async () => ({
        data: [{ dataset_id: "ds1", id: "doc1", indexing_status: "completed", name: "Q1" }],
      }),
      ok: true,
    });
    const out = await DifyDatasets.listDocuments("ds1");
    const [firstDoc] = out.data;
    expect(firstDoc.indexing_status).toBe("completed");
  });

  it("retrieve 走 POST /datasets/{id}/retrieve", async () => {
    const { DifyDatasets } = await loadClient();
    fetchMock.mockResolvedValueOnce({
      json: async () => ({
        records: [{ content: "hit", document_id: "doc1", document_name: "Q1", score: 0.9 }],
      }),
      ok: true,
    });
    const out = await DifyDatasets.retrieve("ds1", "1LE0001", THREE);
    const [firstRecord] = out.records;
    expect(firstRecord.content).toBe("hit");
    const [, secondCallInit] = fetchMock.mock.calls[ZERO];
    const parsedBody = JSON.parse(secondCallInit.body);
    expect(parsedBody.top_k).toBe(THREE);
  });

  it("非 2xx 抛 DifyApiError", async () => {
    const { DifyDatasets } = await loadClient();
    fetchMock.mockResolvedValueOnce({ ok: false, status: 401, text: async () => "unauth" });
    await expect(DifyDatasets.listDatasets()).rejects.toThrow(/unauth/);
  });

  it("healthCheck 成功返 true", async () => {
    const { DifyDatasets } = await loadClient();
    fetchMock.mockResolvedValueOnce({ json: async () => [], ok: true });
    expect(await DifyDatasets.healthCheck()).toBe(true);
  });

  it("healthCheck 失败返 false", async () => {
    const { DifyDatasets } = await loadClient();
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500, text: async () => "boom" });
    expect(await DifyDatasets.healthCheck()).toBe(false);
  });
});
