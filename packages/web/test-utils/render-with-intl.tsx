/**
 * 测试用 render wrapper: 自动注入 NextIntlClientProvider context
 * 解决 41 个 vitest fail 的 useTranslations context 缺失
 * (2026-07-08 test-failures.md §P0.1)
 */
import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import { I18nProvider } from "@/i18n/provider";
import zhMessages from "@/messages/zh.json";

const DEFAULT_LOCALE = "zh";
const DEFAULT_TIME_ZONE = "Asia/Shanghai";

interface RenderWithIntlOptions extends Omit<RenderOptions, "wrapper"> {
  locale?: string;
  messages?: Record<string, unknown>;
  timeZone?: string;
}

export const renderWithIntl = (
  ui: React.ReactElement,
  options: RenderWithIntlOptions = {},
): RenderResult => {
  const {
    locale = DEFAULT_LOCALE,
    messages = zhMessages,
    timeZone = DEFAULT_TIME_ZONE,
    ...rest
  } = options;
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <I18nProvider locale={locale} messages={messages} timeZone={timeZone}>
      {children}
    </I18nProvider>
  );
  return render(ui, { wrapper: Wrapper, ...rest });
};

// re-export @testing-library/react 其它工具, 避免 import 散落
export { screen, waitFor, act, fireEvent } from "@testing-library/react";
