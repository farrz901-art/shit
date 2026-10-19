import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock server-only: knowledge.ts 间接 import auth.server.ts 它顶部 import "server-only"
vi.mock("server-only", () => ({}));

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (key: string) => (key === "rag_user_token" ? { value: "test-tok" } : undefined),
  })),
}));

vi.mock("next/cache", () => ({
  revalidatePath: vi.fn(),
}));

// (2026-06-13) Task 10: createQA 改走审核, 不再直调 DifyDatasets.
// Mock approvalsApi.submit 走审核; mock DifyDatasets.createDocumentByText 用于断言 NOT called (防回归).
const { approvalsSubmitMock, difyCreateDocMock } = vi.hoisted(() => ({
  approvalsSubmitMock: vi.fn(),
  difyCreateDocMock: vi.fn(),
}));

vi.mock("@/lib/api/approvals", () => ({
  submit: approvalsSubmitMock,
}));

vi.mock("@/lib/api/dify-datasets", () => ({
  DifyApiError: class DifyApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = "DifyApiError";
      this.status = status;
    }
  },
  DifyDatasets: {
    createDocumentByText: difyCreateDocMock,
  },
}));

import { commitDocuments, createQA, createTriples, optimizeAnswer } from "./knowledge";
import { revalidatePath } from "next/cache";

beforeEach(() => {
  approvalsSubmitMock.mockReset();
  difyCreateDocMock.mockReset();
  vi.mocked(revalidatePath).mockClear();
  // 默认 fetch 200, 给 createTriples 测试用 (commitDocuments/createQA 都不再直调 fetch)
  globalThis.fetch = vi.fn(async () =>
    Response.json(
      { ok: true },
      {
        headers: { "Content-Type": "application/json" },
        status: 200,
      },
    ),
  ) as never;
});

afterEach(() => vi.restoreAllMocks());

describe("createQA 走审核 (不直调 Dify)", () => {
  it("调 approvalsApi.submit(kind=qa, payload=input), 返 {approval_id, review_status, apply_status}", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 142,
      kind: "qa",
      review_status: "pending",
    });

    const result = await createQA({
      answer: "a",
      dataset_id: "ds1",
      question: "q",
      tags: ["W21"],
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({
        apply_status: "none",
        approval_id: 142,
        review_status: "pending",
      });
    }
    expect(approvalsSubmitMock).toHaveBeenCalledWith("qa", {
      answer: "a",
      dataset_id: "ds1",
      question: "q",
      sync_to_neo4j: undefined,
      tags: ["W21"],
    });
    // 关键防回归: 不能调 Dify 直写
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });

  it("同步 sync_to_neo4j=true 时也透传给 approval payload", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 200,
      kind: "qa",
      review_status: "pending",
    });

    await createQA({
      answer: "a",
      dataset_id: "ds1",
      question: "q",
      sync_to_neo4j: true,
      tags: ["1LE0001"],
    });

    expect(approvalsSubmitMock).toHaveBeenCalledWith("qa", {
      answer: "a",
      dataset_id: "ds1",
      question: "q",
      sync_to_neo4j: true,
      tags: ["1LE0001"],
    });
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });

  it("成功后调 revalidatePath /submissions", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 1,
      kind: "qa",
      review_status: "pending",
    });

    await createQA({ answer: "a", dataset_id: "ds1", question: "q" });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/submissions");
  });

  it("approvals 抛错时返 ActionResult { ok: false, error }, 不抛异常", async () => {
    approvalsSubmitMock.mockRejectedValueOnce(new Error("HTTP 500: upstream down"));

    const result = await createQA({ answer: "a", dataset_id: "ds1", question: "q" });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/HTTP 500/);
    }
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });

  it("必填字段缺失返 ok: false, 不发请求", async () => {
    const r1 = await createQA({ answer: "", dataset_id: "x", question: "q" });
    expect(r1.ok).toBe(false);
    const r2 = await createQA({ answer: "a", dataset_id: "", question: "q" });
    expect(r2.ok).toBe(false);
    const r3 = await createQA({ answer: "a", dataset_id: "x", question: "" });
    expect(r3.ok).toBe(false);
    expect(approvalsSubmitMock).not.toHaveBeenCalled();
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });
});

describe("createTriples 走审核 (不直调 KgClient)", () => {
  beforeEach(() => {
    approvalsSubmitMock.mockReset();
    difyCreateDocMock.mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("调 approvalsApi.submit(kind=triple, payload=rows), 返 {approval_id, review_status, apply_status}", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 200,
      kind: "triple",
      review_status: "pending",
    });

    const result = await createTriples({
      rows: [
        {
          from_key: "k",
          from_label: "A",
          from_value: "v",
          properties: {},
          rel_type: "R",
          to_key: "k",
          to_label: "B",
          to_value: "v",
        },
      ],
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({
        apply_status: "none",
        approval_id: 200,
        review_status: "pending",
      });
    }
    expect(approvalsSubmitMock).toHaveBeenCalledWith("triple", {
      rows: [
        {
          from_key: "k",
          from_label: "A",
          from_value: "v",
          properties: {},
          rel_type: "R",
          to_key: "k",
          to_label: "B",
          to_value: "v",
        },
      ],
    });
    // 关键防回归: 不能调 Dify 直写
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });

  it("成功后 revalidatePath /submissions", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 1,
      kind: "triple",
      review_status: "pending",
    });

    await createTriples({ rows: [] });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/submissions");
  });

  it("approvals 抛错时返 ActionResult { ok: false, error }, 不抛异常", async () => {
    approvalsSubmitMock.mockRejectedValueOnce(new Error("HTTP 500: upstream down"));

    const result = await createTriples({ rows: [] });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/HTTP 500/);
    }
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });
});

describe("commitDocuments 走审核 (不循环调 Dify)", () => {
  beforeEach(() => {
    approvalsSubmitMock.mockReset();
    difyCreateDocMock.mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("调 approvalsApi.submit(kind=batch, payload={dataset_id, rows}), 返 {approval_id, ...}", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 300,
      kind: "batch",
      review_status: "pending",
    });

    const result = await commitDocuments({
      dataset_id: "ds1",
      rows: [
        { answer: "a1", question: "q1" },
        { answer: "a2", question: "q2" },
      ],
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({
        apply_status: "none",
        approval_id: 300,
        review_status: "pending",
      });
    }
    expect(approvalsSubmitMock).toHaveBeenCalledWith("batch", {
      dataset_id: "ds1",
      rows: [
        { answer: "a1", question: "q1" },
        { answer: "a2", question: "q2" },
      ],
    });
    // 关键防回归: 不能调 DifyDatasets 循环直写
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });

  it("成功后 revalidatePath /submissions", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 1,
      kind: "batch",
      review_status: "pending",
    });

    await commitDocuments({ dataset_id: "x", rows: [] });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/submissions");
  });

  it("必填字段缺失返 ok: false, 不发请求", async () => {
    const r1 = await commitDocuments({ dataset_id: "", rows: [] });
    expect(r1.ok).toBe(false);
    const r2 = await commitDocuments({ dataset_id: "x", rows: null as never });
    expect(r2.ok).toBe(false);
    expect(approvalsSubmitMock).not.toHaveBeenCalled();
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });
});

describe("optimizeAnswer 走审核 (新增 server action)", () => {
  beforeEach(() => {
    approvalsSubmitMock.mockReset();
    difyCreateDocMock.mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("调 approvalsApi.submit(kind=optimize, payload={...}), 返 {approval_id, ...}", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 400,
      kind: "optimize",
      review_status: "pending",
    });

    const result = await optimizeAnswer({
      dataset_id: "ds1",
      improved_answer: "改进后",
      original_answer: "原回答",
      question: "原问题",
      reason: "改了什么",
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({
        apply_status: "none",
        approval_id: 400,
        review_status: "pending",
      });
    }
    expect(approvalsSubmitMock).toHaveBeenCalledWith("optimize", {
      dataset_id: "ds1",
      improved_answer: "改进后",
      original_answer: "原回答",
      question: "原问题",
      reason: "改了什么",
    });
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });

  it("成功后 revalidatePath /submissions", async () => {
    approvalsSubmitMock.mockResolvedValueOnce({
      apply_status: "none",
      id: 1,
      kind: "optimize",
      review_status: "pending",
    });

    await optimizeAnswer({
      dataset_id: "ds1",
      improved_answer: "new",
      original_answer: "old",
      question: "q",
      reason: "r",
    });
    expect(revalidatePath).toHaveBeenCalledWith("/[locale]/submissions");
  });

  it("必填字段缺失返 ok: false, 不发请求", async () => {
    const r1 = await optimizeAnswer({
      dataset_id: "",
      improved_answer: "new",
      original_answer: "old",
      question: "q",
      reason: "r",
    });
    expect(r1.ok).toBe(false);
    const r2 = await optimizeAnswer({
      dataset_id: "x",
      improved_answer: "",
      original_answer: "old",
      question: "q",
      reason: "r",
    });
    expect(r2.ok).toBe(false);
    const r3 = await optimizeAnswer({
      dataset_id: "x",
      improved_answer: "new",
      original_answer: "old",
      question: "",
      reason: "r",
    });
    expect(r3.ok).toBe(false);
    expect(approvalsSubmitMock).not.toHaveBeenCalled();
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });

  it("approvals 抛错时返 ActionResult { ok: false, error }, 不抛异常", async () => {
    approvalsSubmitMock.mockRejectedValueOnce(new Error("HTTP 502: bad gateway"));

    const result = await optimizeAnswer({
      dataset_id: "ds1",
      improved_answer: "new",
      original_answer: "old",
      question: "q",
      reason: "r",
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/HTTP 502/);
    }
    expect(difyCreateDocMock).not.toHaveBeenCalled();
  });
});
