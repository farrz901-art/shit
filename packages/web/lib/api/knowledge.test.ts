// KnowledgeApi 测试只覆盖**行为**(输入→输出 + 错误归一),
// 不重复测 apiFetch 内部实现 (URL 拼装 / 鉴权头注入 / Content-Type 等在 config.test.ts 覆盖)
import { HTTP_NOT_FOUND, HTTP_OK } from "@/const";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import {
  createTriples,
  fetchBatchStatus,
  fetchDatasets,
  fetchExtractDatasets,
  fetchExtractors,
  fetchSplitters,
  fetchExtractTask,
  fetchExtractTasks,
  fetchExtractPreview,
  fetchHealth,
  fetchNodes,
  fetchRelations,
  fetchSchema,
  fetchSchemas,
  fetchStats,
  patchExtractItems,
  commitExtract,
  retrieveQA,
  startBatch,
  startExtract,
  uploadDocument,
  uploadExtractFile,
} from "./knowledge";

// 最小 Response mock: apiFetch 调用 res.text() 解析, 不再依赖 res.json()
const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: HTTP_OK,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const errResponse = (status: number, statusText: string, detail?: string): Response => {
  const body = detail ? JSON.stringify({ detail }) : "";
  return {
    ok: false,
    status,
    statusText,
    text: async () => body,
  } as unknown as Response;
};

// oxlint-disable-next-line max-statements -- describe 块包含 16 个 it, 每个 it 是独立测试
describe("knowledgeApi", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  afterEach(() => vi.unstubAllGlobals());

  it("fetchStats 返解析后的对象", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          okResponse({ dify: { datasets: 3, documents: 4 }, neo4j: { nodes: 1, relations: 2 } }),
        ),
    );
    const out = await fetchStats();
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(out.neo4j.nodes).toBe(1);
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(out.dify.documents).toBe(4);
  });

  it("fetchStats 带 type+domain 时透传 query string", async () => {
    const mock = vi.fn().mockResolvedValue(
      /* oxlint-disable no-magic-numbers -- 测试数据: 空状态值 */
      okResponse({ dify: { datasets: 0, documents: 0 }, neo4j: { nodes: 0, relations: 0 } }),
      /* oxlint-enable no-magic-numbers */
    );
    vi.stubGlobal("fetch", mock);
    await fetchStats("neo4j", "电机");
    // oxlint-disable-next-line no-magic-numbers -- 数组索引
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("type=neo4j");
    expect(url).toContain("domain=");
  });

  it("fetchNodes 4xx 抛 ApiError", async () => {
    // oxlint-disable-next-line no-magic-numbers -- 测试使用的 HTTP 状态码, 但 const 中没有 HTTP_BAD_GATEWAY
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(errResponse(502, "Bad Gateway")));
    await expect(fetchNodes()).rejects.toBeInstanceOf(ApiError);
  });

  it("fetchBatchStatus 4xx 抛 ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(errResponse(HTTP_NOT_FOUND, "Not Found")));
    await expect(fetchBatchStatus("nope")).rejects.toBeInstanceOf(ApiError);
  });

  it("createTriples POST 返 success 计数", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ errors: [], failed: 0, success: 1 })),
    );
    const result = await createTriples({
      rows: [
        {
          from_key: "model",
          from_label: "Product",
          from_value: "1LE0001",
          properties: {},
          rel_type: "BELONGS_TO",
          to_key: "name",
          to_label: "Series",
          to_value: "1LE",
        },
      ],
    });
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(result.success).toBe(1);
  });

  it("uploadDocument 走 BFF, body 是 FormData", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse({ document_id: "doc_1" })));
    const file = new File(["x"], "test.csv", { type: "text/csv" });
    const result = await uploadDocument(file, "ds_1");
    expect(result.document_id).toBe("doc_1");
  });

  it("fetchDatasets 返 data 数组", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ data: [{ id: "ds1", name: "测试数据集" }] })),
    );
    const result = await fetchDatasets();
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(result).toHaveLength(1);
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(result[0].name).toBe("测试数据集");
  });

  it("fetchDatasets data 为 undefined 时返 []", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse({})));
    const result = await fetchDatasets();
    expect(result).toEqual([]);
  });

  it("fetchHealth 返 ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse({ ok: true })));
    const result = await fetchHealth();
    expect(result.ok).toBe(true);
  });

  it("fetchRelations 返关系数组", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse([
          {
            src: "n1",
            src_label: "Node",
            src_name: "A",
            src_business_id: "b1",
            type: "RELATES_TO",
            dst: "n2",
            dst_label: "Node",
            dst_name: "B",
            dst_business_id: "b2",
            props: {},
          },
        ]),
      ),
    );
    const result = await fetchRelations();
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(result).toHaveLength(1);
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(result[0].type).toBe("RELATES_TO");
  });

  it("fetchSchema 拼 domain 到 query", async () => {
    const mock = vi.fn().mockResolvedValue(okResponse({ nodes: [], relations: [] }));
    vi.stubGlobal("fetch", mock);
    await fetchSchema("motor");
    // oxlint-disable-next-line no-magic-numbers -- 数组索引
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("domain=motor");
  });

  it("fetchSchemas 返 schemas 列表", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ schemas: [{ name: "motor" }, { name: "pump" }] })),
    );
    const result = await fetchSchemas();
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(result.schemas).toHaveLength(2);
  });

  it("retrieveQA POST 返 records", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          okResponse({ records: [{ content: "答案", score: 0.95, document_name: "doc1" }] }),
        ),
    );
    const result = await retrieveQA("问题", "ds1");
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(result.records).toHaveLength(1);
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(result.records[0].content).toBe("答案");
  });

  it("startBatch POST 返 task_id", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okResponse({ task_id: "t1" })));
    const result = await startBatch({
      dataset_id: "ds1",
      items: [{ target: "neo4j", type: "create_node", payload: {} }],
    });
    expect(result.task_id).toBe("t1");
  });

  // ===== (2026-07-01 markdown extract KG PR4 v3) 9 个新 wrapper 测试 =====
  // 测试数据 + 索引都用 magic number, 整段禁用 no-magic-numbers 规则
  /* oxlint-disable no-magic-numbers */

  it("fetchExtractDatasets 返 dataset 白名单数组", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(okResponse([{ label: "motor" }, { label: "plc" }, { label: "sensor" }])),
    );
    const out = await fetchExtractDatasets();
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(out).toHaveLength(3);
    expect(out[0].label).toBe("motor");
  });

  it("fetchExtractors 返抽取器白名单", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse([
          { id: "spacy_rule", available: true },
          { id: "llm_pydantic", available: true },
        ]),
      ),
    );
    const out = await fetchExtractors();
    // oxlint-disable-next-line no-magic-numbers -- 测试数据
    expect(out).toHaveLength(2);
    expect(out[1].id).toBe("llm_pydantic");
  });

  it("fetchSplitters 返切片器白名单 + chunk_size_range", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse([{ id: "heading", chunk_size_range: [100, 5000] }])),
    );
    const out = await fetchSplitters();
    // oxlint-disable-next-line no-magic-numbers -- 数组索引
    expect(out[0].id).toBe("heading");
    expect(out[0].chunk_size_range[1]).toBe(5000);
  });

  it("uploadExtractFile FormData + dataset query 透传", async () => {
    const mock = vi.fn().mockResolvedValue(
      okResponse({
        uri: "s3://rag-extract/inputs/abc/source.md",
        file_id: "abc",
        dataset: "motor",
      }),
    );
    vi.stubGlobal("fetch", mock);
    const file = new File(["# H1"], "test.md", { type: "text/markdown" });
    const out = await uploadExtractFile(file, "motor");
    expect(out.file_id).toBe("abc");
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("dataset=motor");
  });

  it("startExtract POST 返 task_id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(okResponse({ task_id: "tk_1", state: "queued" })),
    );
    const out = await startExtract({
      uri: "s3://rag-extract/inputs/abc/source.md",
      dataset: "motor",
      extractor: "llm_pydantic",
      splitter: "heading",
    });
    expect(out.task_id).toBe("tk_1");
    expect(out.state).toBe("queued");
  });

  it("fetchExtractTask 拼 task_id 到 path", async () => {
    const mock = vi
      .fn()
      .mockResolvedValue(
        okResponse({ task_id: "tk_1", state: "done", success: 5, failed: 0, errors: [] }),
      );
    vi.stubGlobal("fetch", mock);
    const out = await fetchExtractTask("tk_1");
    expect(out.state).toBe("done");
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("/api/kg/extract/tasks/tk_1");
  });

  it("fetchExtractPreview 拼 dataset query + 返 entities/relations", async () => {
    const mock = vi.fn().mockResolvedValue(
      okResponse({
        entities: [
          {
            id: 1,
            text: "W21",
            label: "Spec",
            selected: true,
            char_span: [0, 3],
            confidence: 0.9,
            chunk_id: "c1",
          },
        ],
        relations: [],
      }),
    );
    vi.stubGlobal("fetch", mock);
    const out = await fetchExtractPreview("tk_1", "motor");
    expect(out.entities[0].label).toBe("Spec");
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("dataset=motor");
  });

  it("patchExtractItems PATCH + 透传 items + dataset query", async () => {
    const mock = vi.fn().mockResolvedValue(okResponse({ updated: 2 }));
    vi.stubGlobal("fetch", mock);
    const out = await patchExtractItems("tk_1", "motor", [
      { id: 1, selected: true, corrected_payload: null },
      { id: 2, selected: false, corrected_payload: { text: "改" } },
    ]);
    expect(out.updated).toBe(2);
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("dataset=motor");
  });

  it("commitExtract POST + dataset query 透传", async () => {
    const mock = vi.fn().mockResolvedValue(okResponse({ success: 5, failed: 0, errors: [] }));
    vi.stubGlobal("fetch", mock);
    const out = await commitExtract("tk_1", "motor");
    expect(out.success).toBe(5);
    const url = mock.mock.calls[0][0] as string;
    expect(url).toContain("dataset=motor");
  });

  it("fetchExtractTasks 返 {items, total, total_success, total_failed}", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        okResponse({
          items: [
            {
              task_id: "t1",
              kind: "kg_extract",
              state: "done",
              success: 5,
              failed: 0,
              created_at: 0,
              started_at: 0,
              finished_at: 0,
            },
          ],
          total: 1,
          total_success: 5,
          total_failed: 0,
          limit: 20,
          offset: 0,
        }),
      ),
    );
    const out = await fetchExtractTasks({ kind: "kg_extract" });
    expect(out.total).toBe(1);
    expect(out.items[0].task_id).toBe("t1");
  });

  it("fetchExtractTasks 拼 query string kind/limit/offset", async () => {
    const mock = vi.fn().mockResolvedValue(
      okResponse({
        items: [],
        total: 0,
        total_success: 0,
        total_failed: 0,
        limit: 5,
        offset: 10,
      }),
    );
    vi.stubGlobal("fetch", mock);
    await fetchExtractTasks({ kind: "kg_batch", limit: 5, offset: 10 });
    const url = String(mock.mock.calls[0][0]);
    expect(url).toContain("kind=kg_batch");
    expect(url).toContain("limit=5");
    expect(url).toContain("offset=10");
  });

  it("fetchExtractTasks 422 抛 ApiError 带 detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          errResponse(422, "Unprocessable", "kind 必须在 [kg_extract, kg_batch, all]"),
        ),
    );
    await expect(fetchExtractTasks({ kind: "kg_extract" })).rejects.toThrow("kind 必须在");
  });
});
