// DictList 单元测试 (2026-06-19 lookup module Task 9 smoke test)
// 验证:
//   1. 渲染 items (DataTable data-table-row)
//   2. 显示 key / label_zh / label_en
//   3. 点击 "编辑" 按钮 → 展开 DictItemEditor 表单 (含 editor-label-zh input)
//   4. readonly=true → 编辑/删除按钮 disabled
//   5. 点击 "删除" 按钮 → 触发 onAskDelete 回调 (把 item 传给父组件)
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { DictList } from "./dict-list";
import { type LookupItem } from "@/lib/api/lookups";
import { TWO } from "@/const";
import { NextIntlClientProvider } from "next-intl";
import zhMessages from "@/messages/zh.json";

const SAMPLE: LookupItem[] = [
  {
    is_active: true,
    key: "pending",
    label_en: "Pending",
    label_zh: "待审核",
    sort: 1,
  },
  {
    is_active: false,
    key: "approved",
    label_en: "Approved",
    label_zh: "已批准",
    sort: 2,
  },
];

const renderList = (props: Partial<React.ComponentProps<typeof DictList>> = {}) => {
  const onPatch = vi.fn();
  const onAskDelete = vi.fn();
  const onAskAudit = vi.fn();
  const view = render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <DictList
        items={SAMPLE}
        onPatch={onPatch}
        onAskDelete={onAskDelete}
        onAskAudit={onAskAudit}
        {...props}
      />
    </NextIntlClientProvider>,
  );
  return { ...view, onAskAudit, onAskDelete, onPatch };
};

describe("DictList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("渲染 2 行 + 显示 key / label_zh / label_en", async () => {
    renderList();
    await waitFor(() => {
      expect(screen.getAllByTestId("data-table-row")).toHaveLength(TWO);
    });
    // (2026-06-19) 数据通过 DataTable column render 渲染
    expect(screen.getByText("待审核")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("approved")).toBeInTheDocument();
  });

  it("点击「编辑」展开 DictItemEditor 表单 (含 input 编辑器)", async () => {
    renderList();
    fireEvent.click(screen.getByTestId("edit-pending"));
    // DictItemEditor 内部: key (text) + label_zh input + label_en input + sort + is_active + 保存/取消
    const editor = await screen.findByTestId("item-editor-pending");
    expect(editor).toBeInTheDocument();
    expect(screen.getByTestId("editor-label-zh")).toBeInTheDocument();
    expect(screen.getByTestId("editor-label-en")).toBeInTheDocument();
    expect(screen.getByTestId("editor-sort")).toBeInTheDocument();
  });

  it("点击「删除」触发 onAskDelete (传整 item 回去)", () => {
    const { onAskDelete } = renderList();
    fireEvent.click(screen.getByTestId("delete-pending"));
    expect(onAskDelete).toHaveBeenCalledWith(
      expect.objectContaining({ key: "pending", label_zh: "待审核" }),
    );
  });

  it("点击「历史」触发 onAskAudit (传整 item 回去)", () => {
    const { onAskAudit } = renderList();
    fireEvent.click(screen.getByTestId("audit-pending"));
    expect(onAskAudit).toHaveBeenCalledWith(expect.objectContaining({ key: "pending" }));
  });

  it("readonly=true 时编辑/删除按钮 disabled", () => {
    renderList({ readonly: true });
    expect(screen.getByTestId("edit-pending")).toBeDisabled();
    expect(screen.getByTestId("delete-pending")).toBeDisabled();
  });
});
