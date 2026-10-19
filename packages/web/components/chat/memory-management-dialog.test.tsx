import { ONE, TWO } from "@/const";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

// (2026-06-16) lucide-react 用 stub 替真图标, 加快测试 + 避免 hydrate 警告
// (2026-06-25) 必须 importOriginal 否则 AppErrorBanner 用 AlertCircle/Info/Loader2 等 import 时报缺
vi.mock("lucide-react", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    Brain: () => <span data-testid="icon-brain" />,
    Pencil: () => <span data-testid="icon-pencil" />,
    Trash2: () => <span data-testid="icon-trash" />,
    // eslint-disable-next-line id-length
    X: () => <span data-testid="icon-x" />,
  };
});

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/api/memory", () => ({
  deleteAll: vi.fn(),
  deleteMemory: vi.fn(),
  list: vi.fn(),
  update: vi.fn(),
}));

import { type MemoryHit, deleteAll, deleteMemory, list, update } from "@/lib/api/memory";
import { MemoryManagementDialog } from "./memory-management-dialog";

const mockedList = vi.mocked(list);
const mockedUpdate = vi.mocked(update);
const mockedDelete = vi.mocked(deleteMemory);
const mockedDeleteAll = vi.mocked(deleteAll);

const sampleMemories: MemoryHit[] = [
  { id: "m1", text: "用户叫张三" },
  { id: "m2", text: "用户住北京" },
];

describe("MemoryManagementDialog", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("打开时立即 list 一次", async () => {
    mockedList.mockResolvedValue({ memories: [] });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(ONE));
  });

  it("列 2 条记忆 (text 渲染)", async () => {
    mockedList.mockResolvedValue({ memories: sampleMemories });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    expect(await screen.findByText("用户叫张三")).toBeInTheDocument();
    expect(screen.getByText("用户住北京")).toBeInTheDocument();
  });

  it("memories 为空 → 显示 empty 文案", async () => {
    mockedList.mockResolvedValue({ memories: [] });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    expect(
      await screen.findByText("还没有记忆。开始聊天, AI 会自动记下你说的事实。"),
    ).toBeInTheDocument();
  });

  it("搜索 '北京' → 只显示匹配项", async () => {
    mockedList.mockResolvedValue({ memories: sampleMemories });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await screen.findByText("用户叫张三");
    fireEvent.change(screen.getByPlaceholderText("搜索记忆"), {
      target: { value: "北京" },
    });
    expect(screen.queryByText("用户叫张三")).not.toBeInTheDocument();
    expect(screen.getByText("用户住北京")).toBeInTheDocument();
  });

  it("点编辑 → 弹输入框 + 调 update(id, newText)", async () => {
    mockedList.mockResolvedValue({ memories: [{ id: "m1", text: "用户叫张三" }] });
    mockedUpdate.mockResolvedValue(undefined);
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await screen.findByText("用户叫张三");
    // 找到对应行内的编辑按钮 (sr-only label 包裹 icon, 点 icon 父 Button)
    const editBtn = screen.getByRole("button", { name: /编辑/i });
    fireEvent.click(editBtn);
    const input = screen.getByDisplayValue("用户叫张三") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "用户叫李四" } });
    fireEvent.click(screen.getByText("保存"));
    await waitFor(() => expect(mockedUpdate).toHaveBeenCalledWith("m1", "用户叫李四"));
  });

  it("点删除 → 调 delete(id) + 重新拉 list", async () => {
    mockedList.mockResolvedValue({ memories: [{ id: "m1", text: "用户叫张三" }] });
    mockedDelete.mockResolvedValue(undefined);
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await screen.findByText("用户叫张三");
    const deleteBtn = screen.getByRole("button", { name: /删除/i });
    fireEvent.click(deleteBtn);
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith("m1"));
    // 初次 + 删后 refetch
    expect(mockedList).toHaveBeenCalledTimes(TWO);
  });

  it("点清空所有 → 弹 AlertDialog + 确认后调 deleteAll", async () => {
    mockedList.mockResolvedValue({ memories: [{ id: "m1", text: "x" }] });
    mockedDeleteAll.mockResolvedValue({ deleted_count: 0 });
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    await screen.findByText("x");
    fireEvent.click(screen.getByText("清空所有记忆"));
    expect(await screen.findByText("确定清空所有记忆?")).toBeInTheDocument();
    fireEvent.click(screen.getByText("确认清空"));
    await waitFor(() => expect(mockedDeleteAll).toHaveBeenCalled());
  });

  it("list 失败 → 静默显示空 (不弹错)", async () => {
    mockedList.mockRejectedValue(new Error("网络挂了"));
    render(<MemoryManagementDialog open={true} onOpenChange={() => {}} />);
    expect(
      await screen.findByText("还没有记忆。开始聊天, AI 会自动记下你说的事实。"),
    ).toBeInTheDocument();
  });
});
