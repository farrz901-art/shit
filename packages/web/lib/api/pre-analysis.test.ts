// pre-analysis API wrapper 测试 (mode 1 mock fetch)

import { afterEach, describe, expect, it, vi, type MockInstance } from "vitest";
import {
  getPreAnalysisChapterStructure,
  getPreAnalysisFlaggedParagraphs,
  getPreAnalysisTablePage,
  getPreAnalysisTablePages,
  parseTableFilename,
  preAnalysisUpload,
  listPreAnalysisTasks,
  getPreAnalysisTask,
  downloadPreAnalysisZip,
  type ChapterStructurePayload,
  type ChapterTreeNode,
  type FlaggedParagraphRow,
  type PreAnalysisTaskDetail,
  type PreAnalysisUploadResponse,
  type PreAnalysisListResponse,
  type TablePageResponse,
  type TablePagesResponse,
} from "./pre-analysis";

afterEach(() => {
  vi.restoreAllMocks();
});

/** 装 mock fetch + 返强类型 MockInstance (vi.fn 默认推断成 () => Promise, 拿不到 calls). */
const installMockFetch = (resp: Response): MockInstance => {
  const m = vi.fn(async () => resp);
  globalThis.fetch = m as unknown as typeof fetch;
  return m as unknown as MockInstance;
};

describe("preAnalysisUpload", () => {
  it("POST /api/pre-analysis/upload with FormData", async () => {
    const mockResp: PreAnalysisUploadResponse = {
      task_id: "pa-abc",
      state: "pending",
      pdf_filename: "D81.pdf",
    };
    installMockFetch(Response.json(mockResp, { status: 200 }));

    const file = new File(["x"], "D81.pdf", { type: "application/pdf" });
    const result = await preAnalysisUpload(file);
    expect(result.task_id).toBe("pa-abc");
    expect(result.state).toBe("pending");
  });

  it("throws on 403", async () => {
    installMockFetch(Response.json({ detail: "权限不足" }, { status: 403 }));

    const file = new File(["x"], "D81.pdf", { type: "application/pdf" });
    await expect(preAnalysisUpload(file)).rejects.toThrow();
  });

  // (2026-07-09 PDF 章节树状化+LLM增强) chapter_config_json form 字段
  it("chapter_config_json FormData 字段在 chapterConfig 缺省时发 '{}'", async () => {
    const mockResp: PreAnalysisUploadResponse = {
      task_id: "pa-abc",
      state: "pending",
      pdf_filename: "D81.pdf",
    };
    const fetchMock = installMockFetch(Response.json(mockResp, { status: 200 }));

    const file = new File(["x"], "D81.pdf", { type: "application/pdf" });
    await preAnalysisUpload(file);

    const init = fetchMock.mock.calls[0]?.[1];
    const formData = init?.body as FormData;
    expect(formData).toBeInstanceOf(FormData);
    expect(formData.get("chapter_config_json")).toBe("{}");
  });

  it("chapter_config_json FormData 字段在 chapterConfig 提供时 JSON.stringify", async () => {
    const mockResp: PreAnalysisUploadResponse = {
      task_id: "pa-abc",
      state: "pending",
      pdf_filename: "D81.pdf",
    };
    const fetchMock = installMockFetch(Response.json(mockResp, { status: 200 }));

    const file = new File(["x"], "D81.pdf", { type: "application/pdf" });
    await preAnalysisUpload(
      file,
      { backend: "pymupdf", params: {} },
      {
        chapter_max_level_for_display: 4,
        enable_llm_refinement: true,
        llm_provider: "openai",
      },
    );

    const init = fetchMock.mock.calls[0]?.[1];
    const formData = init?.body as FormData;
    const parsed = JSON.parse(formData.get("chapter_config_json") as string);
    expect(parsed).toEqual({
      chapter_max_level_for_display: 4,
      enable_llm_refinement: true,
      llm_provider: "openai",
    });
  });
});

describe("listPreAnalysisTasks", () => {
  it("GET /api/pre-analysis/tasks 返 task 数组", async () => {
    const EXPECTED_TASK_COUNT = 1;
    const FIRST_TASK_INDEX = 0;
    const mockResp: PreAnalysisListResponse = {
      tasks: [
        {
          id: "pa-1",
          state: "completed",
          user_hash: "hash",
          pdf_filename: "D81.pdf",
          pdf_uri: "local://x",
          started_at: "2026-07-02T10:00:00Z",
          finished_at: "2026-07-02T10:01:00Z",
          current_stage: "done",
          task_config_json: {},
          summary: {
            total_chapters: 6,
            total_tables: 12,
            total_flagged_paragraphs: 11,
            elapsed_ms: 28_421,
            cross_page_candidates: 1,
          },
          error: null,
        },
      ],
    };
    installMockFetch(Response.json(mockResp, { status: 200 }));

    const result = await listPreAnalysisTasks();
    expect(result.tasks).toHaveLength(EXPECTED_TASK_COUNT);
    expect(result.tasks[FIRST_TASK_INDEX]?.id).toBe("pa-1");
  });
});

describe("getPreAnalysisTask", () => {
  it("GET /api/pre-analysis/tasks/{id}", async () => {
    const mockTask: PreAnalysisTaskDetail = {
      id: "pa-1",
      state: "completed",
      user_hash: "hash",
      pdf_filename: "D81.pdf",
      pdf_uri: "local://x",
      started_at: "2026-07-02T10:00:00Z",
      finished_at: "2026-07-02T10:01:00Z",
      current_stage: "done",
      task_config_json: {},
      output_files: [
        {
          kind: "chapter_structure",
          filename: "chapter_structure.json",
          uri: "local://x",
          size_bytes: 3842,
        },
      ],
      summary: {
        total_chapters: 6,
        total_tables: 12,
        total_flagged_paragraphs: 11,
        elapsed_ms: 28_421,
        cross_page_candidates: 1,
      },
      error: null,
    };
    installMockFetch(Response.json(mockTask, { status: 200 }));

    const result = await getPreAnalysisTask("pa-1");
    expect(result.id).toBe("pa-1");
  });
});

// (2026-07-09) 章节树 + 标记段落 viewer helpers
describe("getPreAnalysisChapterStructure", () => {
  it("GET /api/pre-analysis/tasks/{id}/files/chapter_structure.json → 解析 chapters 数组", async () => {
    const mockPayload: ChapterStructurePayload = {
      max_level: 3,
      total_pages: 200,
      total_chapters: 6,
      extracted_at: "2026-07-09T10:00:00Z",
      toc_source: "pdf_outline",
      llm_summary_enabled: false,
      chapters: [
        {
          id: "ch-1",
          level: 1,
          title: "Introduction",
          page_start: 1,
          page_end: 10,
          children: [],
        },
      ],
    };
    installMockFetch(Response.json(mockPayload, { status: 200 }));

    const result = await getPreAnalysisChapterStructure("pa-1");
    expect(result.total_chapters).toBe(6);
    expect(result.chapters).toHaveLength(1);
    const [firstChapter] = result.chapters;
    expect(firstChapter).toBeDefined();
    if (!firstChapter) {
      return;
    }
    expect(firstChapter.title).toBe("Introduction");
  });

  it("chapters 缺/非数组时抛错", async () => {
    installMockFetch(Response.json({ max_level: 0 }, { status: 200 }));
    await expect(getPreAnalysisChapterStructure("pa-1")).rejects.toThrow(
      /chapter_structure\.json: 'chapters' field is not an array/,
    );
  });

  it("递归 children 嵌套结构 (L1 → L2 → L3) 原样返回", async () => {
    const mockGrandChild: ChapterTreeNode = {
      id: "ch-1-1-1",
      level: 3,
      title: "1.1.1 子节",
      page_start: 5,
      page_end: 7,
      children: [],
    };
    const mockChild: ChapterTreeNode = {
      id: "ch-1-1",
      level: 2,
      title: "1.1 父节",
      page_start: 4,
      page_end: 9,
      children: [mockGrandChild],
    };
    const mockRoot: ChapterTreeNode = {
      id: "ch-1",
      level: 1,
      title: "第 1 章",
      page_start: 1,
      page_end: 20,
      children: [mockChild],
    };
    const mockPayload: ChapterStructurePayload = {
      max_level: 3,
      total_pages: 200,
      total_chapters: 3,
      extracted_at: "2026-07-09T10:00:00Z",
      toc_source: "pdf_outline",
      llm_summary_enabled: false,
      chapters: [mockRoot],
    };
    installMockFetch(Response.json(mockPayload, { status: 200 }));

    const result = await getPreAnalysisChapterStructure("pa-1");
    const [firstChapter] = result.chapters;
    const grandChild = firstChapter?.children[0]?.children[0];
    expect(grandChild?.title).toBe("1.1.1 子节");
    expect(grandChild?.level).toBe(3);
  });

  it("后端 4xx/5xx 抛错 (handleError)", async () => {
    installMockFetch(Response.json({ detail: "文件未生成" }, { status: 404 }));
    await expect(getPreAnalysisChapterStructure("pa-1")).rejects.toThrow(/文件未生成/);
  });
});

describe("getPreAnalysisFlaggedParagraphs", () => {
  it("GET /api/pre-analysis/tasks/{id}/files/flagged_paragraphs.csv → 解析为 FlaggedParagraphRow[]", async () => {
    const CSV_HEADER =
      "row_index,page,section,text,rule_categories,density,is_dense,language,token_count";
    const CSV_BODY = `1,3,2.1,Some flagged text,density,0.85,True,en,42
2,5,2.2,Another flagged text,density,0.72,False,en,38`;
    const csv = `${CSV_HEADER}\n${CSV_BODY}\n`;
    installMockFetch(new Response(csv, { status: 200 }));

    const result = await getPreAnalysisFlaggedParagraphs("pa-1");
    expect(result).toHaveLength(2);
    const [firstRow] = result;
    expect(firstRow).toBeDefined();
    if (!firstRow) {
      return;
    }
    expect(firstRow.page).toBe(3);
    expect(firstRow.section).toBe("2.1");
    expect(firstRow.is_dense).toBe(true);
    expect(firstRow.density).toBeCloseTo(0.85, 5);
    expect(firstRow.row_index).toBe(1);
  });

  it("空 CSV (仅 header) 返空数组", async () => {
    const CSV_HEADER =
      "row_index,page,section,text,rule_categories,density,is_dense,language,token_count";
    installMockFetch(new Response(`${CSV_HEADER}\n`, { status: 200 }));

    const result = await getPreAnalysisFlaggedParagraphs("pa-1");
    expect(result).toEqual([]);
  });

  it("is_dense 字符串 'false' / '' 都归 false (不抛)", async () => {
    const CSV_HEADER =
      "row_index,page,section,text,rule_categories,density,is_dense,language,token_count";
    const CSV_BODY = `1,3,2.1,text A,density,0.1,False,en,5
2,4,2.2,text B,density,0.2,,en,6`;
    const csv = `${CSV_HEADER}\n${CSV_BODY}\n`;
    installMockFetch(new Response(csv, { status: 200 }));

    const result = await getPreAnalysisFlaggedParagraphs("pa-1");
    expect(result).toHaveLength(2);
    const [firstRow, secondRow] = result;
    if (!firstRow || !secondRow) {
      return;
    }
    expect(firstRow.is_dense).toBe(false);
    expect(secondRow.is_dense).toBe(false);
  });

  it("后端 4xx/5xx 抛错 (handleError)", async () => {
    installMockFetch(Response.json({ detail: "文件未生成" }, { status: 404 }));
    await expect(getPreAnalysisFlaggedParagraphs("pa-1")).rejects.toThrow(/文件未生成/);
  });

  it("row_index 按返回顺序重排 (1, 2, 3...) 不信 CSV 字符串", async () => {
    const CSV_HEADER =
      "row_index,page,section,text,rule_categories,density,is_dense,language,token_count";
    const CSV_BODY = `99,3,2.1,text A,density,0.1,False,en,5
77,4,2.2,text B,density,0.2,False,en,6`;
    const csv = `${CSV_HEADER}\n${CSV_BODY}\n`;
    installMockFetch(new Response(csv, { status: 200 }));

    const result = await getPreAnalysisFlaggedParagraphs("pa-1");
    const indices = result.map((row: FlaggedParagraphRow) => row.row_index);
    expect(indices).toEqual([1, 2]);
  });
});

describe("downloadPreAnalysisZip", () => {
  it("GET /api/pre-analysis/tasks/{id}/download 返 Blob", async () => {
    // PK\x03\x04 是 zip 文件头 (PKZIP signature)
    const PK_BYTE_1 = 0x50;
    const PK_BYTE_2 = 0x4b;
    const PK_BYTE_3 = 0x03;
    const PK_BYTE_4 = 0x04;
    const PK_SIGNATURE = [PK_BYTE_1, PK_BYTE_2, PK_BYTE_3, PK_BYTE_4] as const;
    const fakeZip = new Uint8Array(PK_SIGNATURE);
    installMockFetch(
      new Response(fakeZip, {
        status: 200,
        headers: { "content-type": "application/zip" },
      }),
    );

    const blob = await downloadPreAnalysisZip("pa-1");
    // jsdom Blob 跟 Node 20 Blob 不是同一 class, instanceof 不稳
    // 验 size + type 即可
    expect(blob.size).toBe(4);
    expect(blob.type).toBe("application/zip");
  });
});

// (2026-07-09) 表格 viewer helpers
describe("parseTableFilename", () => {
  it("extract page 9 table 1", () => {
    expect(parseTableFilename("tables/page-9-table-1.csv")).toEqual({
      pageNumber: 9,
      tableIndex: 1,
    });
  });

  it("support multi-digit page and table index", () => {
    expect(parseTableFilename("tables/page-123-table-45.csv")).toEqual({
      pageNumber: 123,
      tableIndex: 45,
    });
  });

  it("throw on invalid format", () => {
    expect(() => parseTableFilename("chapters.json")).toThrow(/Invalid table filename/);
    expect(() => parseTableFilename("tables/page-9.csv")).toThrow(/Invalid table filename/);
    expect(() => parseTableFilename("tables/page-x-table-1.csv")).toThrow(/Invalid table filename/);
  });
});

describe("getPreAnalysisTablePages", () => {
  it("GET pages endpoint → return {pages, total}", async () => {
    const mock: TablePagesResponse = { pages: [3, 9, 12, 21], total: 5 };
    installMockFetch(Response.json(mock, { status: 200 }));

    const result = await getPreAnalysisTablePages("pa-1");
    expect(result).toEqual({ pages: [3, 9, 12, 21], total: 5 });
  });

  it("empty pages list", async () => {
    installMockFetch(Response.json({ pages: [], total: 0 }, { status: 200 }));
    const result = await getPreAnalysisTablePages("pa-1");
    expect(result).toEqual({ pages: [], total: 0 });
  });

  it("404 throws", async () => {
    installMockFetch(Response.json({ detail: "任务不存在" }, { status: 404 }));
    await expect(getPreAnalysisTablePages("missing")).rejects.toThrow(/任务不存在/);
  });
});

describe("getPreAnalysisTablePage", () => {
  it("GET page endpoint → return {page, tables}", async () => {
    const mock: TablePageResponse = {
      page: 9,
      tables: [
        {
          table_index: 1,
          filename: "tables/page-9-table-1.csv",
          size_bytes: 100,
          columns: ["col_a", "col_b"],
          rows: [{ col_a: "v1", col_b: "v2" }],
        },
      ],
    };
    installMockFetch(Response.json(mock, { status: 200 }));

    const result = await getPreAnalysisTablePage("pa-1", 9);
    expect(result.page).toBe(9);
    expect(result.tables).toHaveLength(1);
    expect(result.tables[0]?.filename).toBe("tables/page-9-table-1.csv");
    expect(result.tables[0]?.rows[0]).toEqual({ col_a: "v1", col_b: "v2" });
  });

  it("page not found → 404 throws", async () => {
    installMockFetch(Response.json({ detail: "页 999 无表格" }, { status: 404 }));
    await expect(getPreAnalysisTablePage("pa-1", 999)).rejects.toThrow(/页 999 无表格/);
  });
});
