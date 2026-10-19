import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import DecodePage from "./page";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { ZERO } from "@/const";
import { decode } from "@/lib/api/system";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";

vi.mock("@/lib/api/system", () => ({
  decode: vi.fn(),
}));

vi.mock("@/lib/api/errors", () => ({
  ApiError: class extends Error {
    status!: number;
    constructor(status: number, msg: string) {
      super(msg);
    }
  },
  NetworkError: class extends Error {},
}));

// (2026-06-23) GuardClient 读 zustand store
const setAllowed = () => {
  usePermissionsStore.setState({
    accountId: null,
    allowed: ["decode"],
    loaded: true,
    pages: [],
    role: "admin",
  });
};

const renderPage = () => {
  setAllowed();
  return render(
    <IntlWrapper locale="zh">
      <DecodePage />
    </IntlWrapper>,
  );
};

describe("DecodePage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("输入型号 + 提交 → 渲染结果 (字段网格)", async () => {
    (decode as any).mockResolvedValue({ raw_input: "1LE0001", series: "siemens_1le0" });
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("1LE0001-1AA42-1AA4"), {
      target: { value: "1LE0001" },
    });
    fireEvent.click(screen.getByText("解码"));
    // 新 UI: DecodeField 渲染 "series" 标签 + "siemens_1le0" 值
    await waitFor(() => expect(screen.getAllByText("siemens_1le0")[ZERO]).toBeInTheDocument());
  });

  it("decode 抛错 → 渲染错误信息", async () => {
    (decode as any).mockRejectedValue(new Error("挂了"));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("1LE0001-1AA42-1AA4"), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByText("解码"));
    expect(await screen.findByText("Error: 挂了")).toBeInTheDocument();
  });
});

describe("DecodePage 视图切换 (llm_view)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  // 通用渲染: 模拟带 llm_view 的返回, 让结果区域出现
  const submitWithLlmView = async (llmView: string[]) => {
    (decode as any).mockResolvedValue({
      llm_view: llmView,
      raw_input: "1LE0001",
      series: "siemens_1le0",
    });
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("1LE0001-1AA42-1AA4"), {
      target: { value: "1LE0001" },
    });
    fireEvent.click(screen.getByText("解码"));
    await waitFor(() => expect(screen.getAllByText("siemens_1le0")[ZERO]).toBeInTheDocument());
  };

  it("切换到 LLM 视图 → 渲染 <pre data-testid='llm-view'> 含 join 文本", async () => {
    await submitWithLlmView(["a", "b"]);
    // 切到 LLM 视图
    fireEvent.click(screen.getByTestId("view-llm"));
    const pre = await screen.findByTestId("llm-view");
    expect(pre.textContent).toBe("a\nb");
  });

  it("切换到 LLM 视图 → 写 localStorage 'decode.view' = 'llm'", async () => {
    await submitWithLlmView(["a", "b"]);
    fireEvent.click(screen.getByTestId("view-llm"));
    // (2026-06-14) react-use useLocalStorage 用 JSON.stringify 存值, "llm" 存成 '"llm"'
    expect(JSON.parse(localStorage.getItem("decode.view")!)).toBe("llm");
  });

  it(String.raw`LLM 模式下点复制 → 剪贴板收到 llm_view.join('\n')`, async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: writeTextMock },
      writable: true,
    });
    await submitWithLlmView(["hello", "world"]);
    fireEvent.click(screen.getByTestId("view-llm"));
    // 复制按钮 — 在 LLM 模式下文本会变, 用 findByText 等待
    const copyBtn = await screen.findByText("复制 LLM 文本");
    fireEvent.click(copyBtn);
    await waitFor(() => expect(writeTextMock).toHaveBeenCalledWith("hello\nworld"));
  });

  it("复制按钮文案随视图切换: cards='复制 JSON' / llm='复制 LLM 文本'", async () => {
    await submitWithLlmView(["a", "b"]);
    // 默认 cards 模式
    expect(screen.getByText("复制 JSON")).toBeInTheDocument();
    // 切到 llm
    fireEvent.click(screen.getByTestId("view-llm"));
    expect(await screen.findByText("复制 LLM 文本")).toBeInTheDocument();
  });
});
