// Locale layout 404 页面 — RSC, 走 i18n
// (2026-06-14) React 19 not-found.tsx: 路由不匹配时自动显示
import { LocalizedLink } from "@/components/i18n/localized-link";
import { getTranslations } from "next-intl/server";

/**
 * LocaleNotFound - 404 页面
 * @server-only
 */
export default async function LocaleNotFound() {
  const translate = await getTranslations();
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="display text-6xl tracking-tight text-muted-foreground/40">404</h1>
      <h2 className="display text-2xl tracking-tight">{translate("页面不存在")}</h2>
      <p className="max-w-md text-base text-muted-foreground">
        {translate("你要找的页面可能已被移除或地址有误")}
      </p>
      <LocalizedLink
        href="/"
        className="mt-2 rounded-lg bg-ink px-5 py-2.5 text-sm font-medium text-paper transition-colors hover:bg-ink/90"
      >
        {translate("返回首页")}
      </LocalizedLink>
    </div>
  );
}
