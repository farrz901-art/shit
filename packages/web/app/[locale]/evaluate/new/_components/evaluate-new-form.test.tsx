// EvaluateNewForm 单元测试 (2026-06-12) — Task 20 抽 client form
// 行为: 选择 CSV 文件 → Papa Parse 解析 → 显示预览前 5 行 → 提交 createRun
// 提交成功后 router.push("/evaluate/${id}")
// Mock createRun (BFF multipart) + papaparse (同步返回 5 行), 用 IntlWrapper 包 i18n
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { createRun } from "@/lib/api/evaluate";

const pushMock = vi.fn();
// (2026-06-24 FE-001) source 改用 @/i18n/navigation, mock target 也跟着换
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ back: vi.fn(), push: pushMock, refresh: vi.fn() }),
}));

const createRunMock = vi.fn(async (_file: File, _concurrency: number) => ({
  id: 42,
  status: "pending",
}));
vi.mock("@/lib/api/evaluate", () => ({
  createRun: (file: File, concurrency: number) => createRunMock(file, concurrency),
  templateUrl: () => "/api/evaluate/template",
}));

vi.mock("papaparse", () => ({
  default: {
    parse: (
      _file: unknown,
      cfg: { complete?: (result: unknown) => void; error?: (err: unknown) => void },
    ) => {
      // 模拟异步 microtask, 跟真实 papaparse 行为接近
      queueMicrotask(() => {
        cfg.complete?.({
          data: [
            { ground_truth: "A1", question: "Q1" },
            { ground_truth: "A2", question: "Q2" },
            { ground_truth: "A3", question: "Q3" },
            { ground_truth: "A4", question: "Q4" },
            { ground_truth: "A5", question: "Q5" },
          ],
          meta: { fields: ["question", "ground_truth"] },
        });
      });
    },
  },
}));

import { EvaluateNewForm } from "./evaluate-new-form";

// 测试常量 (避免 magic number lint)
const ROW_COUNT = 5;
const ONCE = 1;
const FIRST_CALL = 0;
const ARG_FILE = 0;
const ARG_CONCURRENCY = 1;
const DEFAULT_CONCURRENCY = 1;
const KILOBYTE = 1024;
const MEGABYTE = KILOBYTE * KILOBYTE;
const MAX_SIZE_MB = 5;
const OVERHEAD = 1;
const BIG_FILE_SIZE = MAX_SIZE_MB * MEGABYTE + OVERHEAD;

const renderForm = () =>
  render(
    <IntlWrapper locale="zh">
      <EvaluateNewForm />
    </IntlWrapper>,
  );

describe("EvaluateNewForm (Task 20 client form)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("渲染文件选择区 + FileDropzone", () => {
    const { container } = renderForm();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toBeTruthy();
    // FileDropzone 内部文案
    expect(screen.getByText(/拖文件到这/)).toBeInTheDocument();
  });

  it("选择 5 行 CSV 后, 预览表格渲染全部 5 行 (DataTable)", async () => {
    const { container } = renderForm();
    const file = new File(
      ["question,ground_truth\nQ1,A1\nQ2,A2\nQ3,A3\nQ4,A4\nQ5,A5"],
      "eval.csv",
      { type: "text/csv" },
    );
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    await waitFor(() => {
      expect(screen.getByText("Q1")).toBeInTheDocument();
      expect(screen.getByText("Q5")).toBeInTheDocument();
    });

    // DataTable data-testid="data-table-row"
    const rows = screen.getAllByTestId("data-table-row");
    expect(rows).toHaveLength(ROW_COUNT);
    // 顶部提示行数 = 5
    expect(screen.getByText(/\(5 行\)/)).toBeInTheDocument();
  });

  it("提交表单 → createRun 被调 (含 file + concurrency) + router.push(/evaluate/42)", async () => {
    const { container } = renderForm();
    const file = new File(["question,ground_truth\nQ1,A1\nQ2,A2"], "eval.csv", {
      type: "text/csv",
    });
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    // 等待预览渲染 (说明 parse 完成)
    await waitFor(() => {
      expect(screen.getByText("Q1")).toBeInTheDocument();
    });

    // Concurrency 默认 1 (Form initialValues), 点提交
    const submit = screen.getByTestId("eval-start");
    await act(async () => {
      fireEvent.click(submit);
    });

    await waitFor(() => {
      // 关键断言: createRun 收到 file + concurrency
      expect(createRunMock).toHaveBeenCalledTimes(ONCE);
      const call = createRunMock.mock.calls[FIRST_CALL];
      expect(call?.[ARG_FILE]).toBe(file);
      expect(call?.[ARG_CONCURRENCY]).toBe(DEFAULT_CONCURRENCY);
      // Router.push 跳到详情页
      expect(pushMock).toHaveBeenCalledWith("/evaluate/42");
    });
  });

  it("createRun 抛错时, 显示错误信息 (不 navigate)", async () => {
    createRunMock.mockRejectedValueOnce(new Error("网络挂了"));
    const { container } = renderForm();
    const file = new File(["question,ground_truth\nQ1,A1"], "eval.csv", {
      type: "text/csv",
    });
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await waitFor(() => {
      expect(screen.getByText("Q1")).toBeInTheDocument();
    });
    const submit = screen.getByTestId("eval-start");
    await act(async () => {
      fireEvent.click(submit);
    });
    await waitFor(() => {
      expect(screen.getByText("网络挂了")).toBeInTheDocument();
    });
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("文件超过 5MB 给出错误 (FileDropzone 内部 dropzone-error), 不进入预览态", async () => {
    const { container } = renderForm();
    // 构造 5MB+1 字节
    const big = new File([new Uint8Array(BIG_FILE_SIZE)], "big.csv", {
      type: "text/csv",
    });
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [big] } });
    });
    await waitFor(() => {
      // FileDropzone 内部 data-testid="dropzone-error"
      expect(screen.getByTestId("dropzone-error")).toBeInTheDocument();
    });
    // 表格不该出现
    expect(screen.queryByTestId("data-table-row")).toBeNull();
  });
});

// 防止 lint 报未使用 import
void createRun;
