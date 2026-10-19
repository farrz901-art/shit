"use client";
// AppField 测试 — TDD 红绿循环 (2026-06-25)
import { AppField } from "./app-field";
import { AppForm } from "./app-form";
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

describe("AppField", () => {
  it("默认 Input 渲染正确的 type 属性", () => {
    render(
      <AppForm defaultValues={{ email: "" }} onFinish={vi.fn()}>
        <AppField name="email" type="email" />
      </AppForm>,
    );
    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("type", "email");
  });

  it("label + required 显示标签和必填标记", () => {
    render(
      <AppForm defaultValues={{ name: "" }} onFinish={vi.fn()}>
        <AppField name="name" label="姓名" required />
      </AppForm>,
    );
    // label 存在
    const label = screen.getByText("姓名");
    expect(label).toBeInTheDocument();
    // required 标记: after content 星号 (aria-required 或 label 的 after 伪元素)
    // shadcn Label 的 required 用 after:content-['*'] 实现, 但 jsdom 不渲染伪元素
    // 改用 data 属性或 aria-required 标记
    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("required");
  });

  it("无错误时显示 help 文本", () => {
    render(
      <AppForm defaultValues={{ name: "" }} onFinish={vi.fn()}>
        <AppField name="name" label="姓名" help="请输入姓名" />
      </AppForm>,
    );
    expect(screen.getByText("请输入姓名")).toBeInTheDocument();
  });

  it("自定义 children 通过用户输入绑定 value/onChange", async () => {
    const user = await setupUser();
    render(
      <AppForm defaultValues={{ name: "张三" }} onFinish={vi.fn()}>
        <AppField name="name" label="姓名">
          <Input />
        </AppField>
      </AppForm>,
    );
    const input = screen.getByDisplayValue("张三") as HTMLInputElement;
    expect(input.value).toBe("张三");
    await user.clear(input);
    await user.type(input, "李四");
    expect(input.value).toBe("李四");
  });

  it("嵌套路径 name='user.email' 读写正确", async () => {
    const user = await setupUser();
    const onFinish = vi.fn();
    render(
      <AppForm defaultValues={{ user: { email: "a@b.com" } }} onFinish={onFinish}>
        <AppField name="user.email" label="邮箱">
          <Input />
        </AppField>
        <button type="submit" data-testid="submit-btn">
          提交
        </button>
      </AppForm>,
    );
    const input = screen.getByDisplayValue("a@b.com") as HTMLInputElement;
    expect(input.value).toBe("a@b.com");
    await user.clear(input);
    await user.type(input, "x@y.com");
    await user.click(screen.getByTestId("submit-btn"));
    expect(onFinish).toHaveBeenCalledWith({ user: { email: "x@y.com" } });
  });

  it("Zod 校验错误信息显示", async () => {
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
    // 先输入一个无效值触发 onChange 校验
    const input = screen.getByRole("textbox");
    await user.type(input, "A");
    // field.state.meta.errors 应在 value="A" (length=1 < 2) 时包含错误
    // 提交触发 onSubmit 校验, 确保错误出现
    await user.click(screen.getByTestId("submit-btn"));
    // TanStack Form 的 onChange 校验会在值变化后运行 Zod schema
    // 当 value.length < 2, Zod 返回 "至少 2 字"
    const errorEl = await screen.findByText("至少 2 字");
    expect(errorEl).toBeInTheDocument();
    expect(errorEl.className).toContain("destructive");
  });
});
