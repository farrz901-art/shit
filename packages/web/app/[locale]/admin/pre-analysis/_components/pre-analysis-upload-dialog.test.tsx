"use client";

// pre-analysis 上传弹框 4 个独立测试 (mode 1 mock)
// mock sonner toast + preAnalysisUpload, 验证弹框渲染 / 选文件 / 上传成功 / 上传失败
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { ONE_MB } from "@/const";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { PreAnalysisUploadDialog } from "./pre-analysis-upload-dialog";

const CALL_ONCE = 1;
const CALL_FIRST = 0;
const DIALOG_CLOSE_DELAY_MS = 500;
const DIALOG_CLOSE_BUFFER_MS = 100;
const FAKE_FILE_SIZE_BYTES = ONE_MB;
const FAKE_PDF_BYTE1 = 1;
const FAKE_PDF_BYTE2 = 2;

const toastSuccessMock = vi.fn();
const preAnalysisUploadMock = vi.fn();

vi.mock("sonner", () => ({
  toast: { success: (...args: unknown[]) => toastSuccessMock(...args) },
}));

vi.mock("@/lib/api/pre-analysis", () => ({
  preAnalysisUpload: (...args: unknown[]) => preAnalysisUploadMock(...args),
}));

afterEach(() => {
  vi.restoreAllMocks();
  toastSuccessMock.mockReset();
  preAnalysisUploadMock.mockReset();
});

const renderDialog = (
  props: Partial<React.ComponentProps<typeof PreAnalysisUploadDialog>> = {},
): ReturnType<typeof render> => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlWrapper locale="zh">
        <PreAnalysisUploadDialog
          onComplete={vi.fn()}
          onOpenChange={vi.fn()}
          open={true}
          {...props}
        />
      </IntlWrapper>
    </QueryClientProvider>,
  );
};

const makeFakePdf = (name: string): File =>
  new File([new Uint8Array(FAKE_FILE_SIZE_BYTES)], name, { type: "application/pdf" });

/**
 * 父组件包装器 — 持有 open 状态, 关后立刻 setOpen(true) 模拟用户"再次点开"按钮.
 * 抽到 outer scope 避免每次 render 重建 (oxlint consistent-function-scoping).
 */
const HarnessWithReopen = (): React.ReactElement => {
  const [open, setOpen] = useState(true);
  return (
    <PreAnalysisUploadDialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        // 父组件立刻重开 (模拟用户"再次点开"按钮)
        if (!next) {
          queueMicrotask(() => setOpen(true));
        }
      }}
      onComplete={vi.fn()}
    />
  );
};

/** 通过 userEvent.upload 触发 react-dropzone 的 input change (穿透 Radix Portal). */
const pickFile = async (file: File): Promise<void> => {
  const user = userEvent.setup();
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(input, file);
};

// oxlint-disable-next-line max-statements -- 4 个 test 描述块, 不拆分
describe("PreAnalysisUploadDialog", () => {
  it("open=true 渲染 title + FileDropzone + 取消/开始按钮 (开始 disabled)", () => {
    renderDialog();
    // AppDialog title
    expect(screen.getByText("上传 PDF")).toBeInTheDocument();
    // FileDropzone 用了我们传的 title (覆盖默认 "拖文件到这 或 点击选择")
    expect(screen.getByText("点击上传按钮开始")).toBeInTheDocument();
    // footer 按钮
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
    const startBtn = screen.getByRole("button", { name: "开始上传" });
    expect(startBtn).toBeInTheDocument();
    expect(startBtn).toBeDisabled();
  });

  it("选文件 → 文件信息 + fmtSize 渲染 + 清空按钮 + 开始上传 enabled", async () => {
    const user = userEvent.setup();
    renderDialog();
    await pickFile(makeFakePdf("test.pdf"));
    // 文件名 + fmtSize (1.0 MB)
    expect(screen.getByText("test.pdf")).toBeInTheDocument();
    expect(screen.getByText("1.0 MB")).toBeInTheDocument();
    // 清空按钮
    expect(screen.getByRole("button", { name: "清空" })).toBeInTheDocument();
    // 开始上传 enabled
    const startBtn = screen.getByRole("button", { name: "开始上传" });
    expect(startBtn).not.toBeDisabled();
    // 引用 user 让 lint 不报 unused
    void user;
  });

  // oxlint-disable-next-line max-statements -- 多个 waitFor 串联, 不拆 helper
  it("点开始上传 → preAnalysisUpload 调 + toast.success + 500ms 后 onComplete + onOpenChange(false)", async () => {
    const onOpenChange = vi.fn();
    const onComplete = vi.fn();
    preAnalysisUploadMock.mockResolvedValue({
      task_id: "pa-new-1",
      state: "pending",
      pdf_filename: "test.pdf",
    });
    renderDialog({ onComplete, onOpenChange });
    await pickFile(makeFakePdf("test.pdf"));
    screen.getByRole("button", { name: "开始上传" }).click();
    // preAnalysisUpload + toast.success 立即触发
    await waitFor(() => {
      expect(preAnalysisUploadMock).toHaveBeenCalledTimes(CALL_ONCE);
      expect(toastSuccessMock).toHaveBeenCalledWith("上传成功");
    });
    // 500ms 还没到, 回调不触发
    expect(onComplete).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalled();
    // 等真实 600ms (覆盖 500ms 弹框关闭延迟)
    await new Promise((resolve) =>
      setTimeout(resolve, DIALOG_CLOSE_DELAY_MS + DIALOG_CLOSE_BUFFER_MS),
    );
    expect(onComplete).toHaveBeenCalledTimes(CALL_ONCE);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("preAnalysisUpload 抛错 → uploadError 设置 + 弹框不关 + error slot 展示", async () => {
    const onOpenChange = vi.fn();
    preAnalysisUploadMock.mockRejectedValue(new Error("PDF > 100MB"));
    renderDialog({ onOpenChange });
    await pickFile(makeFakePdf("test.pdf"));
    screen.getByRole("button", { name: "开始上传" }).click();
    await waitFor(() => {
      expect(screen.getByText("PDF > 100MB")).toBeInTheDocument();
    });
    // 弹框不关
    expect(onOpenChange).not.toHaveBeenCalled();
    // toast 不调
    expect(toastSuccessMock).not.toHaveBeenCalled();
  });

  // === (2026-07-09) 高级选项区不再折叠, 直接展示 backend + 章节配置 ===
  it("默认状态下看到 backend 选择器 + 默认 camelot (Camelot 置首, 默认选中)", () => {
    renderDialog();
    // 表格提取器 label 可见 (高级选项区不再折叠, 直接展示)
    expect(screen.getByText("表格提取器")).toBeInTheDocument();
    // AppRadioGroup 默认显示 Camelot (Item 级 testid)
    expect(screen.getByTestId("backend-radio-camelot")).toBeInTheDocument();
    // 章节配置 label 可见
    expect(screen.getByText("章节配置")).toBeInTheDocument();
  });

  // (2026-07-09) regression: 表格参数配置 UI 隐藏 (params 数据仍传给后端).
  // 选 camelot → 不渲染 flavor / line_scale / line_tol 等输入控件.
  it("默认 camelot → 表格参数配置区 UI 隐藏 (params 数据仍传给后端)", async () => {
    const user = userEvent.setup();
    preAnalysisUploadMock.mockResolvedValue({
      task_id: "p",
      state: "pending",
      pdf_filename: "x.pdf",
    });
    renderDialog();
    // 选 camelot (已经是默认, 显式点一次保证状态稳定)
    await user.click(screen.getByTestId("backend-radio-camelot"));
    // UI 上没有参数输入控件: 不应该有 param-flavor / param-line_scale / param-line_tol
    expect(screen.queryByTestId("param-flavor")).not.toBeInTheDocument();
    expect(screen.queryByTestId("param-line_scale")).not.toBeInTheDocument();
    expect(screen.queryByTestId("param-line_tol")).not.toBeInTheDocument();
    // 但 camelot 默认提示文案可见 (告诉用户走的什么策略)
    expect(screen.getByText(/Camelot lattice 解析器/)).toBeInTheDocument();
    // 选文件 → 上传, 验证 params 数据 (默认值) 仍然传给后端
    await pickFile(
      new File([new Uint8Array([FAKE_PDF_BYTE1, FAKE_PDF_BYTE2])], "x.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: "开始上传" }));
    await waitFor(() => expect(preAnalysisUploadMock).toHaveBeenCalledTimes(CALL_ONCE));
    const [, passedConfig] = preAnalysisUploadMock.mock.calls[CALL_FIRST] as [File, object];
    // params 走 BACKEND_DEFAULT_PARAMS.camelot 默认值 (UI 隐藏但数据照传)
    expect(passedConfig).toEqual({
      backend: "camelot",
      params: { flavor: "lattice", line_scale: 15, line_tol: 2 },
    });
  });

  // (2026-07-09) regression: 切到 pdfplumber 也不渲染参数 UI.
  it("切到 pdfplumber → 表格参数配置区 UI 隐藏 (params 数据仍传给后端)", async () => {
    const user = userEvent.setup();
    preAnalysisUploadMock.mockResolvedValue({
      task_id: "p",
      state: "pending",
      pdf_filename: "x.pdf",
    });
    renderDialog();
    // 切到 pdfplumber
    await user.click(screen.getByTestId("backend-radio-pdfplumber"));
    // UI 上没有参数输入控件
    expect(screen.queryByTestId("param-vertical_strategy")).not.toBeInTheDocument();
    expect(screen.queryByTestId("param-snap_tolerance")).not.toBeInTheDocument();
    // pdfplumber 默认提示文案可见
    expect(screen.getByText(/pdfplumber 策略/)).toBeInTheDocument();
    // 选文件 → 上传
    await pickFile(
      new File([new Uint8Array([FAKE_PDF_BYTE1, FAKE_PDF_BYTE2])], "x.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: "开始上传" }));
    await waitFor(() => expect(preAnalysisUploadMock).toHaveBeenCalledTimes(CALL_ONCE));
    const [, passedConfig] = preAnalysisUploadMock.mock.calls[CALL_FIRST] as [File, object];
    // params 走 BACKEND_DEFAULT_PARAMS.pdfplumber 默认值
    expect(passedConfig).toEqual({
      backend: "pdfplumber",
      params: {
        vertical_strategy: "lines",
        horizontal_strategy: "lines",
        snap_tolerance: 3,
        join_tolerance: 3,
      },
    });
  });

  // === (2026-07-09 PDF 章节树状化) 章节配置 3 个新测试 ===
  it("默认看到章节配置区 + 章节层级默认 1-3 级", () => {
    renderDialog();
    // 章节配置 label
    expect(screen.getByText("章节配置")).toBeInTheDocument();
    // AppSelect 默认值 = "3" (1-3 级)
    const levelSelect = screen.getByTestId("chapter-max-level");
    expect(levelSelect).toBeInTheDocument();
    // 启用 LLM 增强 Switch
    const llmSwitch = screen.getByTestId("enable-llm-refinement");
    expect(llmSwitch).toBeInTheDocument();
    expect(llmSwitch).toHaveAttribute("aria-checked", "false");
  });

  it("开启 LLM 增强 Switch → aria-checked=true + 上传发送 enable_llm_refinement=true", async () => {
    const user = userEvent.setup();
    preAnalysisUploadMock.mockResolvedValue({
      task_id: "p",
      state: "pending",
      pdf_filename: "x.pdf",
    });
    renderDialog();
    const llmSwitch = screen.getByTestId("enable-llm-refinement");
    await user.click(llmSwitch);
    expect(llmSwitch).toHaveAttribute("aria-checked", "true");
    // 选文件 → 上传
    await pickFile(
      new File([new Uint8Array([FAKE_PDF_BYTE1, FAKE_PDF_BYTE2])], "x.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: "开始上传" }));
    await waitFor(() => expect(preAnalysisUploadMock).toHaveBeenCalledTimes(CALL_ONCE));
    const args = preAnalysisUploadMock.mock.calls[CALL_FIRST] as [File, object, object];
    expect(args[2]).toMatchObject({
      chapter_max_level_for_display: 3,
      enable_llm_refinement: true,
      llm_provider: "openai",
    });
  });

  it("上传默认不开启 LLM → chapterConfig 字段含 max_level 但 enable_llm_refinement=false", async () => {
    const user = userEvent.setup();
    preAnalysisUploadMock.mockResolvedValue({
      task_id: "p",
      state: "pending",
      pdf_filename: "x.pdf",
    });
    renderDialog();
    await pickFile(
      new File([new Uint8Array([FAKE_PDF_BYTE1, FAKE_PDF_BYTE2])], "x.pdf", {
        type: "application/pdf",
      }),
    );
    await user.click(screen.getByRole("button", { name: "开始上传" }));
    await waitFor(() => expect(preAnalysisUploadMock).toHaveBeenCalledTimes(CALL_ONCE));
    const args = preAnalysisUploadMock.mock.calls[CALL_FIRST] as [File, object, object];
    // 默认 LLM off, max_level=3, provider=openai
    expect(args[2]).toEqual({
      chapter_max_level_for_display: 3,
      enable_llm_refinement: false,
      llm_provider: "openai",
    });
  });

  // (2026-07-09) regression: 上传成功 500ms 自动关弹框后, 父组件重开弹框应该是空状态
  // (无文件名, 走 FileDropzone). 原 bug: executeUpload setTimeout 调 props.onOpenChange(false)
  // 绕过 handleOpenChange, state 全残留 → 重开还是上次表单.
  it("上传成功关弹框后父组件重开 → 弹框是空 (FileDropzone, 无文件名)", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    preAnalysisUploadMock.mockResolvedValue({
      task_id: "pa-after-success",
      state: "pending",
      pdf_filename: "x.pdf",
    });
    render(
      <QueryClientProvider client={queryClient}>
        <IntlWrapper locale="zh">
          <HarnessWithReopen />
        </IntlWrapper>
      </QueryClientProvider>,
    );
    // 选文件 → 弹框显示文件信息
    await pickFile(makeFakePdf("ghost.pdf"));
    expect(screen.getByText("ghost.pdf")).toBeInTheDocument();
    // 点上传
    screen.getByRole("button", { name: "开始上传" }).click();
    // 等 500ms + buffer 走完自动关 + 重开
    await new Promise((resolve) =>
      setTimeout(resolve, DIALOG_CLOSE_DELAY_MS + DIALOG_CLOSE_BUFFER_MS),
    );
    // 重开后弹框应该是空: 文件名不再出现, FileDropzone title 出现
    expect(screen.queryByText("ghost.pdf")).not.toBeInTheDocument();
    expect(screen.getByText("点击上传按钮开始")).toBeInTheDocument();
  });
});
