// (2026-06-11) SampleTable 测试 — 长答案换行 + 召回到文件列 + 指标 0/None 区分
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { SampleTable } from "./sample-table";
import { TWO } from "@/const";
import type { SampleResult } from "@/lib/evaluate/types";

const sample = (overrides: Partial<SampleResult> = {}): SampleResult => ({
  answer: "短答案",
  error: undefined,
  ground_truth: "GT",
  index: 1,
  metrics: null,
  question: "Q?",
  ...overrides,
});

describe("SampleTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("长答案换行 (2026-06-11 Task A)", () => {
    it("长答案 → 渲染的 cell 不带 truncate (允许换行)", () => {
      const longAnswer =
        "第一行\n第二行\n第三行非常非常长的内容, 应该正常换行显示而不是被 truncate 截掉";
      render(<SampleTable samples={[sample({ answer: longAnswer })]} />);
      const cell = screen.getByText(/第一行/);
      // (2026-06-11) 之前 max-w-sm truncate → 改 whitespace-pre-wrap + max-h-32 overflow-y-auto
      expect(cell.className).not.toMatch(/\btruncate\b/);
      expect(cell.className).toMatch(/whitespace-pre-wrap/);
    });

    it("空 answer → 显 — 占位符 (不崩)", () => {
      const { container } = render(<SampleTable samples={[sample({ answer: "" })]} />);
      // 直接查 DOM 文本节点, 避免 jsdom 对 em-dash 字符的精确匹配差异
      const cells = container.querySelectorAll("td");
      const hasDash = [...cells].some((cell) => cell.textContent?.trim() === "—");
      expect(hasDash).toBe(true);
    });

    it("answer 含 <think>...</think> → 表格展示时 strip (历史评估兜底)", () => {
      // (2026-06-11 bug fix) 之前后端 DifyClient._strip_think 加之前的评估, answer 在 DB 里还是原文
      // 前端表格展示时再 strip 一次, 无论新/旧数据都干净
      const dirty = "<think>\n我们分析用户的问题...\n</think>真正的答案";
      render(<SampleTable samples={[sample({ answer: dirty })]} />);
      // 真正的答案应该在 DOM 里
      expect(screen.getByText("真正的答案")).toBeInTheDocument();
      // 推理过程不应该在 DOM 里
      expect(screen.queryByText(/我们分析用户/)).not.toBeInTheDocument();
    });
  });

  describe("召回到文件列 (2026-06-11 Task C)", () => {
    it("sources 非空 → 渲染文件名 + 位置", () => {
      render(
        <SampleTable
          samples={[
            sample({
              sources: [
                {
                  name: "1LE 电机手册.pdf",
                  position: 3,
                  score: 0.85,
                  snippet: "1LE 系列是西门子电机...",
                },
                { name: "产品选型指南.docx", position: 1, score: 0.72, snippet: "适用场景" },
              ],
            }),
          ]}
        />,
      );
      expect(screen.getByText("1LE 电机手册.pdf")).toBeInTheDocument();
      expect(screen.getByText("产品选型指南.docx")).toBeInTheDocument();
      // 位置信息 (position=3 → "p.3")
      expect(screen.getByText(/p\.3/)).toBeInTheDocument();
    });

    it("sources 为空数组 → 显 — 占位符", () => {
      const { container } = render(<SampleTable samples={[sample({ sources: [] })]} />);
      const cells = container.querySelectorAll("td");
      // Sources 列显 — (跟空 answer 共用 em-dash)
      const dashCount = [...cells].filter((cell) => cell.textContent?.trim() === "—").length;
      // eslint-disable-next-line no-magic-numbers -- 测试断言: 至少 answer 列 + sources 列
      expect(dashCount).toBeGreaterThanOrEqual(TWO);
    });

    it("sources 未定义 (旧评估数据) → 表格不崩", () => {
      const { container } = render(<SampleTable samples={[sample()]} />);
      // 不传 sources 字段, 表格不应崩
      expect(container.querySelector("table")).toBeTruthy();
    });
  });
});
