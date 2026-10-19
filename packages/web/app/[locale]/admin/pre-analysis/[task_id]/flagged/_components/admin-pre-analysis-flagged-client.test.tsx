// 段落提取客户端组件测试 (mode 1 mock fetch)

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { AdminPreAnalysisFlaggedClient } from "./admin-pre-analysis-flagged-client";
import type { FlaggedParagraphRow } from "@/lib/api/pre-analysis";

vi.mock("server-only", () => ({}));

afterEach(() => {
  vi.restoreAllMocks();
});

/** (2026-07-09) 4 row fixture — 2 dense (True) + 2 normal (False).
 * (2026-07-10) rule_categories 改为真实后端拼接格式 "neg=N,obl=N" (extractor.py:129),
 *   测试 parseRuleCategories 拆 4 类 badge 的渲染. */
const FIXTURE_ROWS: FlaggedParagraphRow[] = [
  {
    row_index: 1,
    matched_keywords: "foo|bar",
    page: 12,
    section: "2.1",
    text: "Lorem ipsum dolor sit amet.",
    rule_categories: "neg=2,obl=1",
    density: 0.9,
    is_dense: true,
    raw_density: 0.9,
    weighted_density: 1.2,
    safe_hits: 3,
    rec_hits: 5,
    lemmas: "[1,2]",
    token_count: 12_000,
    language: "zh",
  },
  {
    row_index: 2,
    matched_keywords: "baz",
    page: 15,
    section: "2.2",
    text: "Sed do eiusmod tempor.",
    rule_categories: "cond=3",
    density: 0.72,
    is_dense: false,
    raw_density: 0.8,
    weighted_density: 1,
    safe_hits: 2,
    rec_hits: 3,
    lemmas: "[3]",
    token_count: 35,
    language: "zh",
  },
  {
    row_index: 3,
    matched_keywords: "qux",
    page: 20,
    section: "3.1",
    text: "Ut labore et dolore magna.",
    rule_categories: "neg=1,obl=2,perm=1",
    density: 0.95,
    is_dense: true,
    raw_density: 0.95,
    weighted_density: 1.5,
    safe_hits: 5,
    rec_hits: 8,
    lemmas: "[4,5]",
    token_count: 60,
    language: "zh",
  },
  {
    row_index: 4,
    matched_keywords: "x",
    page: 25,
    section: "3.2",
    text: "Excepteur sint occaecat.",
    rule_categories: "",
    density: 0.3,
    is_dense: false,
    raw_density: 0.3,
    weighted_density: 0.3,
    safe_hits: 0,
    rec_hits: 0,
    lemmas: "[6]",
    token_count: 20,
    language: "zh",
  },
];

/** 模拟 fetch 返 CSV 文本 (让 helper 内 papaparse 解析). */
const installMockFetchCsv = (csvText: string): void => {
  globalThis.fetch = vi.fn(
    async () => new Response(csvText, { status: 200 }),
  ) as unknown as typeof fetch;
};

const installMockFetch = (resp: Response): void => {
  globalThis.fetch = vi.fn(async () => resp) as unknown as typeof fetch;
};

/** 序列化行成 CSV (字段含 , 或 " 需 quote). */
const toCsv = (rows: FlaggedParagraphRow[]): string => {
  const header =
    "matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language";
  const body = rows.map((r) => {
    const isDense = r.is_dense ? "True" : "False";
    return `"${r.matched_keywords}",${r.page},"${r.section}","${r.text}","${r.rule_categories}",${r.density},${isDense},${r.raw_density},${r.weighted_density},${r.safe_hits},${r.rec_hits},"${r.lemmas}",${r.token_count},${r.language}`;
  });
  return [header, ...body].join("\n");
};

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

describe("AdminPreAnalysisFlaggedClient", () => {
  it("渲染 14 列 4 行 (匹配关键词 / 词形还原 / 原始密度 / 加权密度 / 安全命中 / 推荐命中 全展示)", async () => {
    installMockFetchCsv(toCsv(FIXTURE_ROWS));
    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      // 4 行 text 全部命中
      expect(screen.getByText(/Lorem ipsum dolor sit amet\./)).toBeTruthy();
      expect(screen.getByText(/Sed do eiusmod tempor\./)).toBeTruthy();
      expect(screen.getByText(/Ut labore et dolore magna\./)).toBeTruthy();
      expect(screen.getByText(/Excepteur sint occaecat\./)).toBeTruthy();
      // 新加 6 字段的列头存在
      expect(screen.getByText("匹配关键词")).toBeTruthy();
      expect(screen.getByText("词形还原")).toBeTruthy();
      expect(screen.getByText("原始密度")).toBeTruthy();
      expect(screen.getByText("加权密度")).toBeTruthy();
      expect(screen.getByText("安全命中")).toBeTruthy();
      expect(screen.getByText("推荐命中")).toBeTruthy();
      // 数据点 — token_count 千分位 + safe_hits 数
      expect(screen.getByText("12,000")).toBeTruthy();
      // matched_keywords "foo|bar" 在行内展示
      expect(screen.getByText("foo|bar")).toBeTruthy();
    });
  });

  it("is_dense=true 行渲染 Badge (高密度)", async () => {
    installMockFetchCsv(toCsv(FIXTURE_ROWS));
    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      // 高密度 Badge 至少出现 2 次 (is_dense=true 的 2 行)
      expect(screen.getAllByText("高密度").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("rule_categories 拆 4 类 deontic badge (neg/obl/cond/perm) + count 内嵌", async () => {
    installMockFetchCsv(toCsv(FIXTURE_ROWS));
    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      // 行 1: neg=2,obl=1 → 2 个 badge (data-testid=rule-badge-{key})
      const negBadgesRow1 = screen.getAllByTestId("rule-badge-neg");
      const oblBadgesRow1 = screen.getAllByTestId("rule-badge-obl");
      expect(negBadgesRow1.length).toBeGreaterThanOrEqual(2); // row1 neg=2 + row3 neg=1
      expect(oblBadgesRow1.length).toBeGreaterThanOrEqual(2); // row1 obl=1 + row3 obl=2
      // 行 2: cond=3
      expect(screen.getAllByTestId("rule-badge-cond").length).toBeGreaterThanOrEqual(1);
      // 行 3: 包含 perm=1
      expect(screen.getAllByTestId("rule-badge-perm").length).toBeGreaterThanOrEqual(1);
      // count 内嵌到 badge 文案 (中文 label 后接数字)
      expect(screen.getByText("否定 2")).toBeTruthy();
      expect(screen.getByText("义务 1")).toBeTruthy();
    });
  });

  it("空 rule_categories 行渲染 placeholder — (无类别命中)", async () => {
    installMockFetchCsv(toCsv(FIXTURE_ROWS));
    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      // 行 4 rule_categories="" → 渲染 "—" (em-dash placeholder)
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("空 CSV (仅 header) 渲染 <DataEmpty>", async () => {
    const headerOnly =
      "matched_keywords,page,section,text,rule_categories,density,is_dense,raw_density,weighted_density,safe_hits,rec_hits,lemmas,token_count,language";
    installMockFetch(new Response(`${headerOnly}\n`, { status: 200 }));

    renderWithProviders(<AdminPreAnalysisFlaggedClient params={{ task_id: "pa-1" }} />);

    await waitFor(() => {
      expect(screen.getByText("无标记段落")).toBeTruthy();
    });
  });
});
