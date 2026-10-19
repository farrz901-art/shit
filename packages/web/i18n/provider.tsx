"use client";
/**
 * i18n Provider 组件: 包装 NextIntlClientProvider, 注入 locale / messages / timeZone
 *
 * @param locale - 当前语言 (zh / en)
 * @param messages - 扁平 key=value 消息对象
 * @param timeZone - 时区, 与 i18n/request.ts server 端保持一致
 * @param children - 子组件
 * @returns JSX 元素
 * @shared
 */
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";

interface Props {
  locale: string;
  messages: Record<string, unknown>;
  // 必填: 跟 i18n/request.ts server 端 timeZone 保持一致, 防 client useTranslations() 报 ENVIRONMENT_FALLBACK
  timeZone: string;
  children: ReactNode;
}

export const I18nProvider = ({ locale, messages, timeZone, children }: Props) => (
  <NextIntlClientProvider locale={locale} messages={messages} timeZone={timeZone}>
    {children}
  </NextIntlClientProvider>
);
