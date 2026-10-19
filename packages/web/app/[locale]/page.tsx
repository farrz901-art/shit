// RSC: Landing — Editorial 杂志封面 (一屏展示完, BOLD 但不夸张)
// 跟 Sprint 1 草根版 (3 个 emoji 卡片) 彻底不同:
//   - 一屏可见: 顶部 metadata + hero + 入口列表 全部在视口高度内
//   - 标题字重: text-3xl/4xl, 不再 8xl/10rem (听用户反馈: 大的离谱)
//   - 编号入口 (01 02 03) + Lucide 图标 (替 emoji)
//   - RSC (替 client component, 不需要交互)
//
// (2026-06-29) 未登录态 (isAccount=false) → redirect /chat, 不让 anon 看到知识库 / 评估入口.
//   走 @/i18n/navigation 的 redirect (next-intl 4.x API: { href, locale }), 强制 locale 前缀,
//   不会被 intlMiddleware 307 多一跳. 跟 chat/page.tsx 一致: 调 /api/account/me, 401 catch 兜底.
import { ArrowUpRight, BarChart3, BookOpen, MessageSquare } from "lucide-react";
import { LocalizedLink } from "@/components/i18n/localized-link";
import { getProfile } from "@/lib/api/account";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { redirect } from "@/i18n/navigation";
import { getLocale, getTranslations } from "next-intl/server";
import { ONE, TWO } from "@/const";

/** 用户信息响应类型 */
interface MeResponse {
  is_account: boolean;
}

/**
 * ENTRIES — 首页入口配置
 * @shared
 */
const ENTRIES = [
  {
    desc: "跟产品智能体聊",
    href: "/chat",
    icon: MessageSquare,
    title: "对话",
  },
  {
    desc: "录 QA / 文档 / 三元组",
    href: "/knowledge",
    icon: BookOpen,
    title: "知识库",
  },
  {
    desc: "RAG 评估报告",
    href: "/evaluate",
    icon: BarChart3,
    title: "评估",
  },
] as const;

/**
 * Landing - 首页 (Editorial 杂志封面, 一屏展示)
 * @server-only
 */
export default async function Landing() {
  // (2026-06-29) 未登录态 (isAccount=false) → redirect /chat, anon 看不到知识库 / 评估入口
  // 鉴权失败 → 视作 anon, 跟 chat/page.tsx:25-33 一致模式
  let isAccount = false;
  try {
    const me = (await getProfile(await serverAuthHeaders())) as MeResponse;
    isAccount = me.is_account;
  } catch {
    isAccount = false;
  }
  if (!isAccount) {
    // redirect() 抛 NEXT_REDIRECT, 后续 JSX 不会渲染 (TypeScript 用 throw 满足类型)
    redirect({ href: "/chat", locale: await getLocale() });
  }

  const translation = await getTranslations();

  return (
    <div className="relative flex min-h-full items-center">
      {/* 极淡蓝图纸网格背景 (跟 health 统一 Mission Control 主题) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.02]"
        style={{
          WebkitMaskImage:
            "radial-gradient(ellipse 60% 50% at 50% 40%, black 30%, transparent 80%)",
          backgroundImage:
            "linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          maskImage: "radial-gradient(ellipse 60% 50% at 50% 40%, black 30%, transparent 80%)",
        }}
      />

      <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-8 px-8 py-8 lg:gap-10 lg:px-12 lg:py-10">
        {/* HERO: 中等字重, 不夸张, 一屏可见 */}
        <section className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between lg:gap-10">
          <h1 className="display text-3xl font-light leading-tight tracking-[-0.03em] md:text-4xl lg:text-5xl">
            RAG <span className="text-clay">·</span>{" "}
            <span className="text-balance text-foreground/85">{translation("德源通泰")}</span>
          </h1>
          <p className="display max-w-md text-base leading-relaxed text-muted-foreground md:text-lg lg:max-w-sm lg:text-right">
            知识库 <span className="text-clay">+</span> 对话 <span className="text-clay">+</span>{" "}
            评估。
            <br className="hidden lg:block" />
            选个方向 <span className="text-clay">↓</span>
          </p>
        </section>

        {/* 3 入口: 编号 + 图标 + 标题 + 描述 + arrow (横向排版, 一行) */}
        <nav aria-label="primary" className="border-t border-ink/10">
          {ENTRIES.map((entry, index) => {
            const num = String(index + ONE).padStart(TWO, "0");
            return (
              <LocalizedLink
                key={entry.href}
                href={entry.href}
                className="group flex items-center gap-4 border-b border-ink/10 py-4 transition-colors duration-500 hover:bg-paper/40 lg:gap-6 lg:py-5"
              >
                {/* 编号: monospace, 中等大小, 灰底 */}
                <div className="num shrink-0 text-2xl font-light tabular-nums text-muted-foreground/40 transition-colors duration-500 group-hover:text-clay lg:text-3xl">
                  {num}
                </div>

                {/* Icon 圆形 border */}
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-ink/15 transition-all duration-500 group-hover:border-clay group-hover:bg-clay/5 lg:h-12 lg:w-12">
                  <entry.icon
                    className="h-4 w-4 text-ink/70 transition-colors duration-500 group-hover:text-clay lg:h-5 lg:w-5"
                    strokeWidth={1.25}
                  />
                </div>

                {/* 标题 + 描述 */}
                <div className="flex-1 min-w-0">
                  <h2 className="display text-lg font-light tracking-tight md:text-xl">
                    {entry.title}
                  </h2>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground md:text-sm">
                    {entry.desc}
                  </p>
                </div>

                {/* 右侧 arrow: hover 时滑出 + 变 clay */}
                <ArrowUpRight
                  className="h-4 w-4 shrink-0 text-ink/30 transition-all duration-500 group-hover:translate-x-1 group-hover:-translate-y-1 group-hover:text-clay lg:h-5 lg:w-5"
                  strokeWidth={1.25}
                />
              </LocalizedLink>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
