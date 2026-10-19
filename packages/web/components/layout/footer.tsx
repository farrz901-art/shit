/**
 * 全站底部 Footer (Server Component) — 静态品牌信息 + RSC 直渲
 * 用 getTranslations() 服务端取 i18n, 避免 client bundle 多打一份 next-intl
 * 业务量小, 不需要 client 化 (无交互), 也不进 ThemeProvider/I18nProvider 嵌套
 */
import { getTranslations } from "next-intl/server";

export default async function Footer() {
  const translate = await getTranslations();

  return (
    <footer className="shrink-0 border-t border-border/40 p-4">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span className="eyebrow">{translate("RAG · 德源通泰 · 2026")}</span>
      </div>
    </footer>
  );
}
