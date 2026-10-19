// Locale layout 403 页面 — RSC, 走 i18n
// (2026-06-18) 新增: 之前 RSC 调 notFound() 显示 "404 / 页面不存在", 但实际场景是权限拒绝
//   (例 admin 进 /admin/permissions). 用 Next.js 15+ 实验 forbidden() + forbidden.tsx 文件约定,
//   文案明确说"权限不足 / 请联系 super_admin". 启用需 next.config.ts experimental.authInterrupts = true.
import { LocalizedLink } from "@/components/i18n/localized-link";
import { getTranslations } from "next-intl/server";

/** LocaleForbidden - 403 权限拒绝页面, 使用 i18n 显示提示文案和返回首页链接
 * @server-only
 */
export default async function LocaleForbidden() {
  const translate = await getTranslations();
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="display text-6xl tracking-tight text-muted-foreground/40">403</h1>
      <h2 className="display text-2xl tracking-tight">{translate("权限不足")}</h2>
      <p className="max-w-md text-base text-muted-foreground">
        {translate("请联系 super_admin 申请访问权限")}
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
