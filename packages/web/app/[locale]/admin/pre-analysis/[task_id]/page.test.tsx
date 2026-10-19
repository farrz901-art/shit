// pre-analysis 详情页测试

/* oxlint-disable unicorn/numeric-separators-style, no-magic-numbers */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { AdminPreAnalysisDetailClient } from "./_components/admin-pre-analysis-detail-client";

vi.mock("server-only", () => ({}));
// (2026-06-23) GuardPage 是 RSC async 组件, jsdom + RTL 不能渲染 server component.
//   Mock 成 sync passthrough 透传 children — 渲染层只测页面结构, 权限逻辑由 guard-page.test.tsx 覆盖.
vi.mock("@/components/auth/guard-page", () => ({
  GuardPage: ({ children }: { children: React.ReactNode }) => children,
}));

afterEach(() => {
  vi.restoreAllMocks();
});

const FAKE_ELAPSED_MS = 28_421;
const ONE_CROSS_PAGE = 1;

const mockTask = {
  id: "pa-1",
  state: "completed" as const,
  user_hash: "hash",
  pdf_filename: "D81.pdf",
  pdf_uri: "local://x",
  started_at: "2026-07-02T10:00:00Z",
  finished_at: "2026-07-02T10:01:00Z",
  output_files: [
    {
      kind: "chapter_structure" as const,
      filename: "chapter_structure.json",
      uri: "local://x",
      size_bytes: 3842,
    },
    {
      kind: "flagged_paragraphs" as const,
      filename: "flagged_paragraphs.csv",
      uri: "local://x",
      size_bytes: 2156,
    },
    {
      kind: "table" as const,
      filename: "tables/page-3-table-1.csv",
      uri: "local://x",
      size_bytes: 512,
    },
  ],
  summary: {
    total_chapters: 6,
    total_tables: 0,
    total_flagged_paragraphs: 11,
    elapsed_ms: FAKE_ELAPSED_MS,
    cross_page_candidates: ONE_CROSS_PAGE,
  },
  error: null,
};

/**
 * 包装 QueryClientProvider 让 useQuery 不报 "No QueryClient set".
 * 详情页需要 route 参数 — 模拟传 task_id.
 */
const renderWithProviders = (ui: React.ReactElement): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">{ui}</IntlWrapper>
    </QueryClientProvider>,
  );
};

describe("admin pre-analysis detail page", () => {
  it("renders task filename", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json(mockTask, { status: 200 }),
    ) as unknown as typeof fetch;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      // text is split by spans in PageHero, use regex match
      expect(screen.getByText(/D81\.pdf/)).toBeTruthy();
    });
  });

  it("shows cross-page warning when candidates > 0", async () => {
    globalThis.fetch = vi.fn(async () =>
      Response.json(mockTask, { status: 200 }),
    ) as unknown as typeof fetch;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      expect(screen.getByText(/跨页候选表/)).toBeTruthy();
    });
  });

  it("渲染 3 个 StatCard: 表格数/章节数/标记段落数 跟 summary 字段一致, hint ICU 不抛错", async () => {
    // (2026-07-08) 回归测试: hint "跨页候选: {N}" 之前 .replace() 写错, 应走 ICU translate.
    // 修后: 3 个 StatCard 全部渲染, hint "跨页候选: 1" 正常出 (不再 FORMATTING_ERROR).
    globalThis.fetch = vi.fn(async () =>
      Response.json(mockTask, { status: 200 }),
    ) as unknown as typeof fetch;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      // 3 个 StatCard 全部存在 (没被错误边界吞掉)
      const stats = screen.getByTestId("pre-analysis-summary-stats");
      expect(stats).toBeTruthy();
      // 表格数 / 章节数 / 标记段落数 三个标签都在
      expect(screen.getByText("表格数")).toBeTruthy();
      expect(screen.getByText("章节数")).toBeTruthy();
      expect(screen.getByText("标记段落数")).toBeTruthy();
      // hint 渲染: "跨页候选: 1" 走 ICU 替换 (跟 summary.cross_page_candidates=1 一致)
      expect(screen.getByText(/跨页候选: 1/)).toBeTruthy();
    });
  });

  it("renders download zip button", async () => {
    // PKZIP signature: 0x50 0x4B, 后面任意 2 字节
    const PK_BYTE_1 = 0x50;
    const PK_BYTE_2 = 0x4b;
    const ZIP_HEADER_LEN = 2;
    const fakeZip = new Uint8Array(ZIP_HEADER_LEN);
    fakeZip[0] = PK_BYTE_1;
    fakeZip[1] = PK_BYTE_2;
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/download")) {
        return new Response(fakeZip, { status: 200 });
      }
      return Response.json(mockTask, { status: 200 });
    }) as unknown as typeof fetch;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      expect(screen.getByText(/下载全部/)).toBeTruthy();
    });
  });

  it("chapter_structure / flagged_paragraphs / table 行都渲染 '查看' 按钮 (3 个 viewer 路由)", async () => {
    globalThis.fetch = vi.fn(async () => Response.json(mockTask, { status: 200 })) as never;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      // chapter_structure 行的查看按钮
      expect(screen.getByTestId("view-file-chapter_structure.json")).toBeTruthy();
      // flagged_paragraphs 行的查看按钮
      expect(screen.getByTestId("view-file-flagged_paragraphs.csv")).toBeTruthy();
      // (2026-07-09 tables viewer) table 行也有查看按钮, 跳 tables 子路由 + ?page=N#table-M
      expect(screen.getByTestId("view-file-tables/page-3-table-1.csv")).toBeTruthy();
    });
  });

  it("章节数 / 标记段落数 卡片可点击 (cursor-pointer + role=button), 表格数卡片不可点击", async () => {
    globalThis.fetch = vi.fn(async () => Response.json(mockTask, { status: 200 })) as never;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      // mockTask.summary.total_chapters = 6 → 章节数卡片 clickable
      const chapterCard = screen.getByTestId("stat-card-chapters");
      expect(chapterCard.getAttribute("role")).toBe("button");
      expect(chapterCard.getAttribute("tabindex")).not.toBeNull();
      // total_flagged_paragraphs = 11 → 标记段落数卡片 clickable
      const flaggedCard = screen.getByTestId("stat-card-flagged");
      expect(flaggedCard.getAttribute("role")).toBe("button");
      // 表格数卡片 total_tables=0 → 不可点击 (无产物可跳转)
      const tableCard = screen.getByTestId("stat-card-tables");
      expect(tableCard.getAttribute("role")).toBeNull();
    });
  });

  it("章节数 0 时卡片不挂 onClick (无对应产物不可跳转)", async () => {
    const zeroChapterTask = {
      ...mockTask,
      summary: { ...mockTask.summary, total_chapters: 0, total_flagged_paragraphs: 5 },
    };
    globalThis.fetch = vi.fn(async () => Response.json(zeroChapterTask, { status: 200 })) as never;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      // total_chapters = 0 → 章节数卡片不可点击
      const chapterCard = screen.getByTestId("stat-card-chapters");
      expect(chapterCard.getAttribute("role")).toBeNull();
    });
  });
});

describe("tables viewer 集成", () => {
  // 表行 "查看" 按钮: kind="table" 行渲染, table/index 不渲染 (跟 chapters/flagged 一致)
  it("kind=table 行渲染 '查看' 按钮, 跳 URL 含 ?page=N#table-M, index 行不渲染", async () => {
    const taskWithTables = {
      ...mockTask,
      output_files: [
        {
          kind: "table" as const,
          filename: "tables/page-9-table-1.csv",
          uri: "local://x",
          size_bytes: 100,
        },
        {
          kind: "table" as const,
          filename: "tables/page-12-table-1.csv",
          uri: "local://x",
          size_bytes: 200,
        },
        {
          kind: "index" as const,
          filename: "index.json",
          uri: "local://x",
          size_bytes: 50,
        },
      ],
      summary: {
        ...mockTask.summary,
        total_tables: 5,
        total_chapters: 0,
        total_flagged_paragraphs: 0,
        cross_page_candidates: 0,
      },
    };
    globalThis.fetch = vi.fn(async () => Response.json(taskWithTables, { status: 200 })) as never;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => {
      // 2 个 table 行 各有 "查看" 按钮
      expect(screen.getByTestId("view-file-tables/page-9-table-1.csv")).toBeTruthy();
      expect(screen.getByTestId("view-file-tables/page-12-table-1.csv")).toBeTruthy();
    });
    // index 行无 "查看" 按钮
    expect(screen.queryByTestId("view-file-index.json")).toBeNull();
  });

  it("表格数 StatCard 可点击 (total_tables > 0 时 role=button)", async () => {
    const taskWithTables = {
      ...mockTask,
      summary: {
        ...mockTask.summary,
        total_tables: 5,
        total_chapters: 0,
        total_flagged_paragraphs: 0,
        cross_page_candidates: 0,
      },
    };
    globalThis.fetch = vi.fn(async () => Response.json(taskWithTables, { status: 200 })) as never;

    renderWithProviders(<AdminPreAnalysisDetailClient params={{ task_id: "pa-1" }} />);
    await waitFor(() => screen.getByTestId("stat-card-tables"));

    const card = screen.getByTestId("stat-card-tables");
    expect(card.getAttribute("role")).toBe("button");
  });
});

describe("AdminPreAnalysisDetailPage (RSC)", () => {
  // (2026-07-03) 守门测试: RSC entry 必须 await params, 把 string task_id 透传给 client 子组件.
  // 若 page.tsx 没 await,会把 Promise<{task_id}> 原样透传 → client 拿 undefined → fetch /api/pre-analysis/tasks/undefined.
  beforeEach(() => {
    globalThis.fetch = vi.fn(async () => Response.json(mockTask, { status: 200 })) as never;
  });

  it("把 URL 上的 task_id 透传给 client 子组件, 触发正确的 fetch URL", async () => {
    const mod = await import("./page");
    const page = mod.default;
    const element = await page({
      params: Promise.resolve({ task_id: "pa-c2a193fa00a9" }),
    });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <NextIntlClientProvider locale="zh" messages={zhMessages}>
        <QueryClientProvider client={qc}>{element}</QueryClientProvider>
      </NextIntlClientProvider>,
    );
    await waitFor(() => {
      const { calls: fetchedCalls } = (globalThis.fetch as ReturnType<typeof vi.fn>).mock;
      const fetchedUrls = fetchedCalls.map((call) => String(call[0]));
      expect(
        fetchedUrls.some((url) => url.includes("/api/pre-analysis/tasks/pa-c2a193fa00a9")),
      ).toBe(true);
      expect(fetchedUrls.some((url) => url.includes("/undefined"))).toBe(false);
    });
  });
});
