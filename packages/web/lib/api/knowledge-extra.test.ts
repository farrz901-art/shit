import { FIVE, ONE } from "@/const";
// Knowledge API 额外单测 (fetchNodes + fetchRelations + fetchSegments + createTriples)
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createTriples,
  fetchBatchStatus,
  fetchNodes,
  fetchRelations,
  fetchSegments,
} from "./knowledge";

describe("knowledgeApi extra", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("createTriples POST /api/kg/triples", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ rows: 5, success: 5, failed: 0, errors: [] }),
      } as Response),
    );
    const result = await createTriples({
      rows: [],
    });
    expect(result.success).toBe(FIVE);
  });

  it("fetchBatchStatus GET /api/knowledge/batch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            state: "running",
            total: 10,
            processed: 3,
            success: 2,
            failed: 1,
            errors: [],
          }),
      } as Response),
    );
    const result = await fetchBatchStatus("t1");
    expect(result.state).toBe("running");
  });

  it("fetchNodes GET /api/kg/nodes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify([{ id: "n1", name: "节点1", label: "Entity" }]),
      } as Response),
    );
    const result = await fetchNodes();
    expect(result).toHaveLength(ONE);
  });

  it("fetchRelations GET /api/kg/relations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify([{ id: "r1", src: "n1", type: "edge", dst: "n2", props: {} }]),
      } as Response),
    );
    const result = await fetchRelations();
    expect(result).toHaveLength(ONE);
  });

  it("fetchSegments GET /api/kg/segments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ items: [{ id: "s1", content: "段" }] }),
      } as Response),
    );
    const result = await fetchSegments();
    expect(result.items).toHaveLength(ONE);
  });
});
