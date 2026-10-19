/**
 * next-intl 路由配置: 定义支持的语言列表和行为
 *
 * @defaultLocale zh - 默认中文
 * @localePrefix always - URL 始终带 locale 前缀
 * @shared
 */
import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  defaultLocale: "zh",
  localePrefix: "always",
  locales: ["zh", "en"],
});
