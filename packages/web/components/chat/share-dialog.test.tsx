// ShareDialog 单测 (2026-06-16) — 创建 + 复制 + 撤销 share
/* oxlint-disable no-magic-numbers, max-statements -- 测试数据/数组索引是测试用例, 命名反而失真 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";

vi.mock("lucide-react", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    Copy: () => <span data-testid="icon-copy" />,
    Share2: () => <span data-testid="icon-share" />,
    Trash2: () => <span data-testid="icon-trash" />,
    // eslint-disable-next-line id-length
    X: () => <span data-testid="icon-x" />,
  };
});

vi.mock("@/lib/api/chat-share", () => ({
  createShare: vi.fn(),
  getShare: vi.fn(),
  listShares: vi.fn(),
  revokeShare: vi.fn(),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock react-use 的 useCopyToClipboard (其底层 CJS require 绕过 vitest 的 vi.mock 拦截)
// 其它 react-use hook (useBoolean) 不在本测试关注范围内, 透传原模块
const { mockCopy } = vi.hoisted(() => ({ mockCopy: vi.fn(() => true) }));
vi.mock("react-use", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return {
    ...actual,
    useCopyToClipboard: () => [
      { value: undefined, error: undefined, noUserInteraction: false },
      mockCopy,
    ],
  };
});

import { createShare, listShares, revokeShare } from "@/lib/api/chat-share";
import { ShareDialog } from "./share-dialog";

const mockedCreate = vi.mocked(createShare);
const mockedList = vi.mocked(listShares);
const mockedRevoke = vi.mocked(revokeShare);
const mockedCopyToClipboard = vi.mocked(mockCopy);

describe("ShareDialog", () => {
  // (2026-06-30) mount 时 useEffect 调 listShares, 默认返空数组避免老测试因 mock=undefined 炸 TypeError.
  //   beforeEach 保证**第一个**测试也有默认值 (afterEach 不会跑在第一个测试之前).
  beforeEach(() => {
    mockedList.mockResolvedValue([]);
    mockCopy.mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
    mockedCreate.mockClear();
    mockedList.mockClear();
    mockedRevoke.mockClear();
    mockCopy.mockClear();
  });

  it("打开 → 显示创建按钮", () => {
    render(<ShareDialog open={true} onOpenChange={() => {}} convId="c1" />);
    expect(screen.getByTestId("share-dialog-create")).toBeInTheDocument();
  });

  it("点创建 → 调 chatShareApi.create → 显示 URL", async () => {
    mockedCreate.mockResolvedValue({
      created_at: "2026-06-16T00:00:00Z",
      expires_at: null,
      share_id: "abc123456789",
      title: "t",
      url: "http://localhost:3000/zh/chat/s/abc123456789",
    });
    render(
      <ShareDialog
        open={true}
        onOpenChange={() => {}}
        convId="c1"
        messages={[{ role: "user", content: "hi", createdAt: Date.now() }]}
      />,
    );
    fireEvent.click(screen.getByTestId("share-dialog-create"));

    await waitFor(() =>
      expect(mockedCreate).toHaveBeenCalledWith(expect.objectContaining({ convId: "c1" })),
    );
    expect(
      screen.getByDisplayValue("http://localhost:3000/zh/chat/s/abc123456789"),
    ).toBeInTheDocument();
  });

  it("点复制按钮 → 调 copy-to-clipboard", async () => {
    mockedCreate.mockResolvedValue({
      created_at: "",
      expires_at: null,
      share_id: "abc",
      title: "t",
      url: "http://x/y/abc",
    });
    render(
      <ShareDialog
        open={true}
        onOpenChange={() => {}}
        convId="c1"
        messages={[{ role: "user", content: "hi", createdAt: Date.now() }]}
      />,
    );
    fireEvent.click(screen.getByTestId("share-dialog-create"));
    await waitFor(() => expect(screen.getByDisplayValue("http://x/y/abc")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("share-dialog-copy"));

    await waitFor(() => expect(mockedCopyToClipboard).toHaveBeenCalledWith("http://x/y/abc"));
  });

  it("撤销已有 share → 调 chatShareApi.revoke", async () => {
    mockedCreate.mockResolvedValue({
      created_at: "",
      expires_at: null,
      share_id: "s1",
      title: "t",
      url: "http://x/s1",
    });
    mockedRevoke.mockResolvedValue(undefined);
    render(
      <ShareDialog
        open={true}
        onOpenChange={() => {}}
        convId="c1"
        messages={[{ role: "user", content: "hi", createdAt: Date.now() }]}
      />,
    );
    fireEvent.click(screen.getByTestId("share-dialog-create"));
    await waitFor(() => expect(screen.getByDisplayValue("http://x/s1")).toBeInTheDocument());
    // 触发撤销 → 弹 AppConfirm → 点确认 → 调 revoke
    fireEvent.click(screen.getByTestId("share-dialog-revoke"));
    const confirmBtns = await screen.findAllByRole("button", { name: /撤销分享/i });
    // 取最后一个 (AppConfirm 内的确认按钮, 列表行按钮在前)
    const LAST_INDEX = 1;
    fireEvent.click(confirmBtns[confirmBtns.length - LAST_INDEX]);
    await waitFor(() => expect(mockedRevoke).toHaveBeenCalledWith("s1"));
  });

  it("mount 时调 listShares 拉已分享列表", async () => {
    mockedList.mockResolvedValue([
      {
        share_id: "abc",
        url: "http://x/abc",
        title: "t",
        expires_at: null,
        created_at: "2026-06-30T00:00:00Z",
      },
    ]);
    render(<ShareDialog open={true} onOpenChange={() => {}} convId="c1" />);
    await waitFor(() => {
      expect(mockedList).toHaveBeenCalledWith("c1");
      expect(screen.getByTestId("share-row-abc")).toBeInTheDocument();
    });
  });

  it("点创建时调 createShare 携带当前 messages", async () => {
    mockedCreate.mockResolvedValue({
      created_at: "2026-06-30T00:00:00Z",
      expires_at: null,
      share_id: "new",
      title: "",
      url: "http://x/new",
    });
    const now = Date.now();
    render(
      <ShareDialog
        open={true}
        onOpenChange={() => {}}
        convId="c1"
        messages={[
          { role: "user", content: "hi", createdAt: now },
          { role: "assistant", content: "hello", createdAt: now },
        ]}
      />,
    );
    fireEvent.click(screen.getByTestId("share-dialog-create"));
    await waitFor(() => {
      expect(mockedCreate).toHaveBeenCalledTimes(1);
    });
    const callArg = mockedCreate.mock.calls[0]?.[0];
    expect(callArg?.convId).toBe("c1");
    expect(callArg?.messages).toHaveLength(2);
    expect(callArg?.messages[0]).toMatchObject({ role: "user", content: "hi" });
    expect(callArg?.messages[0]?.timestamp).toEqual(expect.any(String));
    expect(callArg?.messages[1]).toMatchObject({ role: "assistant", content: "hello" });
    expect(callArg?.messages[1]?.timestamp).toEqual(expect.any(String));
  });
});
