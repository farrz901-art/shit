/**
 * 测试用 i18n wrapper — 包 NextIntlClientProvider + 注入 zh/en messages
 * 用法: render(<IntlWrapper locale="zh"><MyComponent /></IntlWrapper>)
 */
"use client";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";

import enMessages from "@/messages/en.json";
import zhMessages from "@/messages/zh.json";

const messagesMap = {
  en: enMessages,
  zh: zhMessages,
} as const;

interface Props {
  locale: "zh" | "en";
  children: ReactNode;
}

/** 共享 i18n 测试 wrapper, 给 page/component 测试用, 包 NextIntlClientProvider + 传入对应 messages */
export const IntlWrapper = ({ locale, children }: Props) => (
  <NextIntlClientProvider locale={locale} messages={messagesMap[locale] as never}>
    {children}
  </NextIntlClientProvider>
);
