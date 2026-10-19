// CreateRoleDialog 组件测试 (2026-06-17) v2 RBAC
// 验证: 输入 name + label_zh + label_en + 选权限 → 提交 POST /api/roles → onCreated
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { CreateRoleDialog } from "./create-role-dialog";
import { NextIntlClientProvider } from "next-intl";
import { ZERO } from "@/const";
import zhMessages from "@/messages/zh.json";

const PAGES = [
  { key: "chat", label_en: "Chat", label_zh: "对话", path: "/chat" },
  { key: "output", label_en: "Output", label_zh: "文档结构化", path: "/output" },
  { key: "knowledge", label_en: "Knowledge", label_zh: "知识库", path: "/knowledge" },
];

const ONE = 1;
const FIRST_CALL = 0;
const HTTP_CONFLICT = 409;

const okResponse = (data: unknown): Response =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(data),
  }) as unknown as Response;

const errResponse = (status: number, detail?: string): Response =>
  ({
    ok: false,
    status,
    statusText: "Err",
    text: async () => {
      if (detail) {
        return JSON.stringify({ detail });
      }
      return "";
    },
  }) as unknown as Response;

const fetchMock = vi.fn();
globalThis.fetch = fetchMock as any;

const renderDialog = (
  props?: Partial<{ onCreated: () => void; onOpenChange: (isOpen: boolean) => void }>,
) => {
  const onCreated = props?.onCreated ?? vi.fn();
  const onOpenChange = props?.onOpenChange ?? vi.fn();
  render(
    <NextIntlClientProvider locale="zh" messages={zhMessages}>
      <CreateRoleDialog
        onCreated={onCreated}
        onOpenChange={onOpenChange}
        open={true}
        pages={PAGES}
      />
    </NextIntlClientProvider>,
  );
  return { onCreated, onOpenChange };
};

/**
 * 填表单字段 + 选权限 (可选) + submit form
 * 用于减少测试中的重复代码和语句数量
 *
 * 用 label/placeholder 找输入字段 (AppField 不暴露内层 Input 的 data-testid)
 */
const fillAndSubmitForm = (values: {
  name: string;
  labelZh: string;
  labelEn: string;
  selectPage?: string;
}) => {
  fireEvent.change(screen.getByPlaceholderText("operator"), { target: { value: values.name } });
  fireEvent.change(screen.getByPlaceholderText("运营"), {
    target: { value: values.labelZh },
  });
  fireEvent.change(screen.getByPlaceholderText("Operator"), {
    target: { value: values.labelEn },
  });
  if (values.selectPage) {
    fireEvent.click(screen.getByTestId(values.selectPage));
  }
  fireEvent.click(screen.getByTestId("role-submit"));
};

describe("CreateRoleDialog", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("渲染表单字段 (name + label_zh + label_en + 页面权限)", () => {
    renderDialog();
    expect(screen.getByPlaceholderText("operator")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("运营")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Operator")).toBeInTheDocument();
    expect(screen.getByTestId("role-page-chat")).toBeInTheDocument();
    expect(screen.getByTestId("role-page-output")).toBeInTheDocument();
  });

  it("填表 + 选权限 + 提交 → POST /api/roles, onCreated 调", async () => {
    fetchMock.mockResolvedValueOnce(okResponse({ name: "operator" }));
    const { onCreated, onOpenChange } = renderDialog();
    fillAndSubmitForm({
      labelEn: "Operator",
      labelZh: "运营",
      name: "operator",
      selectPage: "role-page-chat",
    });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(ONE));
    const call = fetchMock.mock.calls[FIRST_CALL] as [string, RequestInit];
    expect(call[ZERO]).toContain("/api/roles");
    expect(call[ONE]).toMatchObject({ method: "POST" });
    expect(JSON.parse(String(call[ONE].body))).toMatchObject({
      label_en: "Operator",
      label_zh: "运营",
      name: "operator",
      permissions: { chat: true },
    });
    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("提交失败 → 显示错误 + 不调 onCreated", async () => {
    fetchMock.mockResolvedValueOnce(errResponse(HTTP_CONFLICT, "name 已存在"));
    const { onCreated } = renderDialog();
    fillAndSubmitForm({ labelEn: "x", labelZh: "x", name: "x" });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(ONE));
    // 用 findByTestId 自动 retry (state 更新异步)
    expect(await screen.findByTestId("role-create-error")).toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });
});
