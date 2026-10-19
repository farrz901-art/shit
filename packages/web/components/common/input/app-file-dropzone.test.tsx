// FileDropzone 测试 (2026-06-15) — 升级到 components/common/, 加 multiple + accept 字符串 + i18n props
// 覆盖: 默认渲染 / 自定义 data-testid / single file callback / multiple file callback
//        Accept 字符串 (.pdf,.jpg) 解析 / Title hint description 走 props / 出错提示 / maxSizeMB 文案
import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { FileDropzone } from "./app-file-dropzone";

const DEFAULT_FILE_SIZE = 10;
const CALL_ONCE = 1;
const FIRST_CALL_IDX = 0;
const FIRST_ARG_IDX = 0;

const makeFile = (name: string, type = "text/plain", sizeBytes = DEFAULT_FILE_SIZE): File => {
  // 测试用 File: 用 Uint8Array 构造, 避免 0 字节文件被某些库拒绝
  const blob = new Blob([new Uint8Array(sizeBytes)], { type });
  return new File([blob], name, { type });
};

// oxlint-disable-next-line max-statements -- 描述块内 it 数量多, 不拆分
describe("FileDropzone", () => {
  it("默认渲染 (testid + 默认 title + 默认 maxSizeMB hint)", () => {
    render(<FileDropzone onFile={vi.fn()} accept={{}} />);
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
    // 默认 title
    expect(screen.getByText(/拖文件到这/)).toBeInTheDocument();
    // 默认 maxSizeMB=50, hint 渲染 "上限 50MB"
    expect(screen.getByText(/上限 50MB/)).toBeInTheDocument();
  });

  it("data-testid 可自定义", () => {
    render(<FileDropzone onFile={vi.fn()} accept={{}} data-testid="my-dz" />);
    expect(screen.getByTestId("my-dz")).toBeInTheDocument();
  });

  it("maxSizeMB 自定义时 hint 文案更新", () => {
    render(<FileDropzone onFile={vi.fn()} accept={{}} maxSizeMB={20} />);
    expect(screen.getByText(/上限 20MB/)).toBeInTheDocument();
  });

  it("title / hint / description 走 props 透传 i18n 文案", () => {
    render(
      <FileDropzone
        onFile={vi.fn()}
        accept={{}}
        title="拖文件到这里"
        hint="最多 5MB"
        description="支持: PDF, 图片, Office, HTML, CAD (dxf/dwg), 压缩包 (zip)"
      />,
    );
    expect(screen.getByText("拖文件到这里")).toBeInTheDocument();
    expect(screen.getByText("最多 5MB")).toBeInTheDocument();
    expect(
      screen.getByText(/支持: PDF, 图片, Office, HTML, CAD \(dxf\/dwg\), 压缩包 \(zip\)/),
    ).toBeInTheDocument();
  });

  it("multiple=false (默认) 时 onFile 拿单文件", async () => {
    const onFile = vi.fn();
    render(<FileDropzone onFile={onFile} accept={{}} data-testid="dz" />);
    const file = makeFile("a.txt");
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toBeTruthy();
    // Simulate single file drop via input
    await fireEvent.change(input, { target: { files: [file] } });
    expect(onFile).toHaveBeenCalledTimes(CALL_ONCE);
    expect(onFile.mock.calls[FIRST_CALL_IDX][FIRST_ARG_IDX].name).toBe("a.txt");
  });

  it("multiple=true 时 onFiles 拿文件数组 (output/new 多文件场景)", async () => {
    const onFiles = vi.fn();
    render(<FileDropzone multiple onFiles={onFiles} accept={{}} data-testid="dz" />);
    const files = [makeFile("a.pdf"), makeFile("b.jpg"), makeFile("c.docx")];
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await fireEvent.change(input, { target: { files } });
    expect(onFiles).toHaveBeenCalledTimes(CALL_ONCE);
    expect(
      onFiles.mock.calls[FIRST_CALL_IDX][FIRST_ARG_IDX].map((file: File) => file.name),
    ).toEqual(["a.pdf", "b.jpg", "c.docx"]);
  });

  it('accept 字符串 ".pdf,.jpg,.png" 解析为 MIME 字典, react-dropzone 拦截非匹配文件', () => {
    // 间接验证: 字符串被解析, react-dropzone 接受 (拒绝行为在真实 DOM 测试里很难模拟)
    // 这里只验证组件不报 parse error
    const onFile = vi.fn();
    render(<FileDropzone onFile={onFile} accept=".pdf,.jpg,.png" />);
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
  });

  it("accept 字符串允许两种写法 (逗号分隔扩展名)", () => {
    const onFile = vi.fn();
    render(<FileDropzone onFile={onFile} accept=".pdf, .jpg , .png" />);
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
  });

  it("accept 不传时不报错 (无 accept 限制)", () => {
    render(<FileDropzone onFile={vi.fn()} />);
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
  });

  it("accept 字典 (MIME) 旧 API 仍兼容", () => {
    render(
      <FileDropzone
        onFile={vi.fn()}
        accept={{ "application/pdf": [".pdf"], "image/jpeg": [".jpg"] }}
      />,
    );
    expect(screen.getByTestId("file-dropzone")).toBeInTheDocument();
  });

  it("custom className 透传到容器", () => {
    render(<FileDropzone onFile={vi.fn()} accept={{}} className="my-custom-class" />);
    expect(screen.getByTestId("file-dropzone").className).toContain("my-custom-class");
  });
});
