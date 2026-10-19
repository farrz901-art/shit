// 章节目录客户端组件测试 (mode 1 mock fetch)

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { AdminPreAnalysisChaptersClient } from "./admin-pre-analysis-chapters-client";
import type { ChapterStructurePayload } from "@/lib/api/pre-analysis";

vi.mock("server-only", () => ({}));

afterEach(() => {
  vi.restoreAllMocks();
});

/** (2026-07-09) 3 层节点 fixture — 3 L1, ch_2 含 L2, ch_2_1 含 L3, 用于测折叠 + 缩进 */
const TREE_PAYLOAD: ChapterStructurePayload = {
  max_level: 3,
  total_pages: 100,
  total_chapters: 5,
  extracted_at: "2026-07-09T10:00:00Z",
  toc_source: "pdf_outline",
  llm_summary_enabled: false,
  chapters: [
    {
      id: "ch_1",
      level: 1,
      title: "Introduction",
      page_start: 1,
      page_end: 10,
      children: [],
    },
    {
      id: "ch_2",
      level: 1,
      title: "Background",
      page_start: 11,
      page_end: 50,
      children: [
        {
          id: "ch_2_1",
          level: 2,
          title: "Prior work",
          page_start: 12,
          page_end: 20,
          children: [
            {
              id: "ch_2_1_1",
              level: 3,
              title: "Methods (2020)",
              page_start: 13,
              page_end: 15,
              children: [],
            },
          ],
        },
      ],
    },
    {
      id: "ch_3",
      level: 1,
      title: "Conclusion",
      page_start: 51,
      page_end: 60,
      children: [],
    },
  ],
};

/**
 * 包装 QueryClientProvider + IntlWrapper. retry=false 避免 fetch fail 重试拖慢.
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

const installMockFetch = (resp: Response): void => {
  globalThis.fetch = vi.fn(async () => resp) as unknown as typeof fetch;
};

describe("AdminPreAnalysisChaptersClient", () => {
  it("默认全部折叠, 只渲染 L1 节点 (3 行)", async () => {
    installMockFetch(Response.json(TREE_PAYLOAD, { status: 200 }));
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("Introduction")).toBeTruthy();
      expect(screen.getByText("Background")).toBeTruthy();
      expect(screen.getByText("Conclusion")).toBeTruthy();
    });

    // L2/L3 节点默认不渲染
    expect(screen.queryByText("Prior work")).toBeNull();
    expect(screen.queryByText("Methods (2020)")).toBeNull();
  });

  it("点 ch_2 chevron 展开后, 子节点出现", async () => {
    installMockFetch(Response.json(TREE_PAYLOAD, { status: 200 }));
    const user = userEvent.setup();
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("Background")).toBeTruthy();
    });
    await user.click(screen.getByTestId("chapter-toggle-ch_2"));

    expect(screen.getByText("Prior work")).toBeTruthy();
  });

  it("再点一次 ch_2 chevron 折叠, 子节点消失", async () => {
    installMockFetch(Response.json(TREE_PAYLOAD, { status: 200 }));
    const user = userEvent.setup();
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("Background")).toBeTruthy();
    });
    await user.click(screen.getByTestId("chapter-toggle-ch_2"));
    expect(screen.getByText("Prior work")).toBeTruthy();
    await user.click(screen.getByTestId("chapter-toggle-ch_2"));
    expect(screen.queryByText("Prior work")).toBeNull();
  });

  it("叶子节点渲染 <span> 占位 (无 chevron button)", async () => {
    installMockFetch(Response.json(TREE_PAYLOAD, { status: 200 }));
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("Introduction")).toBeTruthy();
    });

    // ch_1 是叶子, 不应该有 toggle button
    expect(screen.queryByTestId("chapter-toggle-ch_1")).toBeNull();
    // ch_2 有子节点, 应该有 toggle button
    expect(screen.getByTestId("chapter-toggle-ch_2")).toBeTruthy();
  });

  it("空树 (chapters: []) 渲染 <DataEmpty>", async () => {
    installMockFetch(Response.json({ ...TREE_PAYLOAD, chapters: [] }, { status: 200 }));
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("无章节数据")).toBeTruthy();
    });
  });

  it("fetch 失败时渲染 ErrorBanner", async () => {
    installMockFetch(Response.json({ detail: "网络异常,请稍后重试" }, { status: 500 }));
    renderWithProviders(<AdminPreAnalysisChaptersClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      // Error 对象 toString() 会带 "Error: " 前缀, 所以匹配前半段
      expect(screen.getByText(/网络异常,请稍后重试/)).toBeTruthy();
    });
  });
});
