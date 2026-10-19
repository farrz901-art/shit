/**
 * next-intl 服务端配置: 加载 locale 对应的消息文件
 *
 * @param requestLocale - 请求 locale (来自中间件)
 * @returns 包含 locale / messages / timeZone 的配置对象
 * @shared
 */
import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;
  if (!locale || !routing.locales.includes(locale as "zh" | "en")) {
    locale = routing.defaultLocale;
  }
  const messagesModule = await import(`../messages/${locale}.json`);
  return {
    locale,
    messages: messagesModule.default,
    // 必填: next-intl 4.x SSR 要求, 防 SSR/CSR markup mismatch
    // 文档: https://next-intl.dev/docs/configuration#time-zone
    timeZone: "Asia/Shanghai",
  };
});
