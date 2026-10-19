import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";
import NewUpload from "./page";
import { upload, uploadViaPresign } from "@/lib/api/ingest";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/api/ingest", () => ({
  upload: vi.fn(),
  uploadViaPresign: vi.fn(),
}));

const push = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ push }),
}));

// (2026-06-23) GuardClient 读 zustand store; mock 不再需要 globalThis.fetch
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const renderNewUpload = () =>
  render(
    <IntlWrapper locale="zh">
      <NewUpload />
    </IntlWrapper>,
  );

describe("NewUpload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    usePermissionsStore.setState({
      accountId: null,
      allowed: ["output"],
      loaded: true,
      pages: [],
      role: "admin",
    });
  });

  it("渲染拖拽区 + 文件支持说明 (走 FileDropzone description)", () => {
    renderNewUpload();
    expect(screen.getByText(/拖文件到这里/)).toBeInTheDocument();
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
    expect(screen.getByText(/支持: PDF, 图片, Office, HTML, CAD/)).toBeInTheDocument();
  });

  it("选文件后显示文件列表", async () => {
    renderNewUpload();
    const file1 = new File(["x"], "a.pdf", { type: "application/pdf" });
    const file2 = new File(["y"], "b.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, [file1, file2]);
    expect(screen.getByText("a.pdf")).toBeInTheDocument();
    expect(screen.getByText("b.pdf")).toBeInTheDocument();
  });

  it("点开始转换 → 优先 uploadViaPresign + push 到 /output", async () => {
    (uploadViaPresign as any).mockResolvedValue({
      state: "queued",
      task_id: "t1",
      total_files: 1,
    });
    renderNewUpload();
    const file = new File(["x"], "a.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, [file]);
    const submitBtn = screen.getByText(/开始转换/);
    await userEvent.click(submitBtn);
    await waitFor(() => {
      expect(uploadViaPresign).toHaveBeenCalledWith([file]);
      expect(upload).not.toHaveBeenCalled();
      expect(push).toHaveBeenCalledWith("/output");
    });
  });

  it("uploadViaPresign 抛错 → fallback upload + push 到 /output", async () => {
    (uploadViaPresign as any).mockRejectedValue(new Error("presign 失败"));
    (upload as any).mockResolvedValue({
      state: "queued",
      task_id: "t1",
      total_files: 1,
    });
    renderNewUpload();
    const file = new File(["x"], "a.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, [file]);
    await userEvent.click(screen.getByText(/开始转换/));
    await waitFor(() => {
      expect(uploadViaPresign).toHaveBeenCalled();
      expect(upload).toHaveBeenCalledWith([file]);
      expect(push).toHaveBeenCalledWith("/output");
    });
  });

  it("upload 抛错 → 显示错误信息", async () => {
    (uploadViaPresign as any).mockRejectedValue(new Error("网络异常"));
    (upload as any).mockRejectedValue(new Error("网络异常"));
    renderNewUpload();
    const file = new File(["x"], "a.pdf", { type: "application/pdf" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, [file]);
    await userEvent.click(screen.getByText(/开始转换/));
    await waitFor(() => expect(screen.getByText(/网络异常/)).toBeInTheDocument());
  });
});
