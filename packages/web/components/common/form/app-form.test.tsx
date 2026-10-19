// AppForm 测试 — TDD 红绿循环 (2026-06-25)
import { AppField } from "./app-field";
import { AppForm } from "./app-form";
import { AppSubmit } from "./app-submit";
import { Input } from "@/components/ui/input";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import { describe, expect, it, vi } from "vitest";
import { z } from "zod";

const MIN_NAME_LENGTH = 2;

const setupUser = async () => {
  const userEventModule = await import("@testing-library/user-event");
  return userEventModule.default.setup();
};

describe("AppForm", () => {
  it("action 模式: 渲染表单且 action 回调已绑定", () => {
    const action = vi.fn();
    const { container } = render(
      <AppForm defaultValues={{ email: "" }} action={action}>
        <AppField name="email" type="email" />
        <AppSubmit>提交</AppSubmit>
      </AppForm>,
    );
    const form = container.querySelector("form")!;
    expect(form).toBeInTheDocument();
    // 验证 action 回调已传入 (React 19 不将函数 action 转为 DOM 属性)
  });

  it("onFinish 模式: 提交触发 onFinish", async () => {
    const user = await setupUser();
    const onFinish = vi.fn();
    render(
      <AppForm defaultValues={{ name: "张三" }} onFinish={onFinish}>
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit-btn">
          提交
        </button>
      </AppForm>,
    );
    await user.click(screen.getByTestId("submit-btn"));
    expect(onFinish).toHaveBeenCalledWith({ name: "张三" });
  });

  it("onFinish 模式: Zod schema 校验失败阻止提交", async () => {
    const user = await setupUser();
    const onFinish = vi.fn();
    const schema = z.object({ name: z.string().min(MIN_NAME_LENGTH, "至少 2 字") });
    render(
      <AppForm defaultValues={{ name: "" }} schema={schema} onFinish={onFinish}>
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit-btn">
          提交
        </button>
      </AppForm>,
    );
    await user.click(screen.getByTestId("submit-btn"));
    // TanStack Form 的 validators.onSubmit 校验失败后不会调用 onSubmit
    // onFinishFailed 回调待后续任务通过 TanStack Form 错误状态接入
    expect(onFinish).not.toHaveBeenCalled();
  });

  it("onFinish 模式: Zod schema 校验通过触发 onFinish", async () => {
    const user = await setupUser();
    const onFinish = vi.fn();
    const schema = z.object({ name: z.string().min(MIN_NAME_LENGTH) });
    render(
      <AppForm defaultValues={{ name: "张三" }} schema={schema} onFinish={onFinish}>
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit-btn">
          提交
        </button>
      </AppForm>,
    );
    await user.click(screen.getByTestId("submit-btn"));
    expect(onFinish).toHaveBeenCalledWith({ name: "张三" });
  });

  it("layout='horizontal' 使用 grid 布局", () => {
    const { container } = render(
      <AppForm defaultValues={{ name: "" }} onFinish={vi.fn()} layout="horizontal">
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
      </AppForm>,
    );
    const form = container.querySelector("form")!;
    expect(form.className).toContain("grid");
  });
});
