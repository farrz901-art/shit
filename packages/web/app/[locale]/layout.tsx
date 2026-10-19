import "../globals.css";
import { Geist as geist, JetBrains_Mono as jetbrainsMonoFont } from "next/font/google";
import { getMessages, setRequestLocale } from "next-intl/server";
// (2026-06-19 chat spec §3) ChatApiProvider: TanStack Query client 注入, 跟
// ThemeProvider / I18nProvider 嵌套一致, 让 lib/chat/api 的 useConversations 等 hook
// 在 ChatShell 等 client 组件里能 useQuery
import { AuthBootstrap } from "@/components/auth/auth-bootstrap";
import { ChatApiProvider } from "@/components/chat/chat-api-provider";
import { Header } from "@/components/layout/header";
import Footer from "@/components/layout/footer";
import { I18nProvider } from "@/i18n/provider";
// T4.3: 全局 RestoreDeletionBanner — pending_deletion 时挂, 任何 layout 都显示
import { RestoreDeletionBanner } from "./account/settings/_components/restore-deletion-banner";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
// (2026-06-23) 客户端 zustand 权限 hydrate 桥接
import { PermissionHydrate } from "@/components/auth/permission-hydrate";
import type { UserMenuUser } from "@/components/user-menu";
import { getProfile } from "@/lib/api/account";
// (2026-06-23) 改用 RSC cached getPermissions() 替代 raw API getMyPermissions
//   避免每次 layout 渲染重复调 /api/permissions/me
import { getPermissions } from "@/lib/auth/permission";
import type { PermissionData } from "@/lib/auth/permission-types";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { serverAuthHeaders } from "@/lib/api/auth.server";
import { themes } from "@/lib/theme";
// (2026-06-28 motion-a11y-refactor §1.2) MotionConfig 全局 reducedMotion="user":
// 用户系统级开启 reduce-motion 时, motion 库自动把所有 transform 动画降级为瞬时切换,
// 我们的原子组件再各自用 useReducedMotionSafe 做进一步分支 (Reveal/Stagger 跳过 hidden).
import { MotionConfig } from "motion/react";
// Layout 用的 /me 字段: 包含 UserMenuUser + deletion 2 字段 (T4.3 banner 需要)

/**
 * LayoutMe - layout 用户数据类型
 * @property deletion_expires_at - 删除过期时间
 * @property is_pending_deletion - 是否 pending 删除
 */
interface LayoutMe extends UserMenuUser {
  deletion_expires_at: string | null;
  is_pending_deletion: boolean;
}

/** UI 字体 (Geist Sans) */
const geistSans = geist({
  display: "swap",
  subsets: ["latin"],
  variable: "--font-geist-sans",
});

/** 数字/代码字体 (JetBrains Mono) */
const jetbrainsMono = jetbrainsMonoFont({
  display: "swap",
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
});

/**
 * 站点元数据
 * @server-only
 */
export const metadata = {
  description: "产品订货号解析 + 知识库管理 + 知识图谱",
  title: "RAG 德源通泰",
};

/**
 * 获取 layout 用户数据 (带 try/catch 兜底)
 * @returns LayoutMe 或 null
 */
const fetchLayoutUser = async (): Promise<LayoutMe | null> => {
  try {
    return (await getProfile(await serverAuthHeaders())) as LayoutMe;
  } catch {
    return null;
  }
};

/**
 * 生成静态参数 (next-intl locale 列表)
 * @returns 静态参数数组
 * @server-only
 */
export const generateStaticParams = () => routing.locales.map((locale) => ({ locale }));

/**
 * LocaleLayout - 多语言根布局
 * @param props.children - 子页面内容
 * @param props.params - 路由参数 (含 locale)
 * @server-only
 */
export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  // 非法 locale 直接 404
  if (!routing.locales.includes(locale as "zh" | "en")) {
    notFound();
  }
  // 必须在任何 client 组件渲染前调用, 让 next-intl 把 locale 写入 server context
  setRequestLocale(locale);
  const messages = await getMessages();

  // 跟 /me 同 try/catch 模式: anon 失败时返默认 ({ allowed: ["chat"] }),
  // 不阻塞整页, 后续 GuardPage 会兜底
  const user = await fetchLayoutUser();
  const perm = await getPermissions();
  // 剥离 server-only 字段 (can/headers), 只传可序列化的 PermissionData 给 client
  const permData: PermissionData = {
    role: perm.role,
    accountId: perm.accountId,
    allowed: perm.allowed,
    pages: perm.pages,
  };

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={`${geistSans.variable} ${jetbrainsMono.variable}`}
      data-scroll-behavior="smooth"
    >
      {/* Body 锁视口 + 防横滚; flex 链必须靠 min-h-0 让子级滚容器拿到正确高度上限 */}
      <body className="bg-paper flex h-screen flex-col overflow-x-hidden overflow-y-hidden text-foreground antialiased">
        {/* ThemeProvider 必须在外层: 它直接改 <html class> 实现深色模式, 必须在 I18nProvider 之前存在 */}
        {/* (2026-06-19) ChatApiProvider 跟 ThemeProvider / I18nProvider 平行嵌套,
            让 lib/chat/api 的 useQuery hook 在 client 组件里能注入 QueryClient */}
        {/* (2026-06-28) MotionConfig 在最外层 — 让所有下层 motion 组件继承 reducedMotion="user" 全局默认 */}
        <MotionConfig reducedMotion="user">
          <ChatApiProvider>
            <ThemeProvider
              attribute="class"
              themes={themes.map((theme) => theme.name)}
              defaultTheme="system"
              enableSystem
            >
              <I18nProvider locale={locale} messages={messages} timeZone="Asia/Shanghai">
                {/* AuthBootstrap: 首次访问触发鉴权 bootstrap (旧 localStorage token 换 cookie, 或匿名 token 兜底) */}
                <AuthBootstrap serverSession={user?.is_account} />
                {/* T4.3: pending_deletion 时挂全局横幅, 显示倒计时 + 撤销表单 (任何 layout 都可见) */}
                {user?.is_pending_deletion && user.deletion_expires_at && (
                  <RestoreDeletionBanner expiresAt={user.deletion_expires_at} />
                )}
                <Header user={user} permissions={permData} />
                {/* (2026-06-23) hydrate RSC 权限到 client zustand store, 0 额外 fetch */}
                <PermissionHydrate permissions={permData} />
                {/* Min-h-0 是关键: flex 子项默认 min-height: auto, 子级 h-full 拿不到正确上限, 滚不动 */}
                <main className="w-full flex-1 min-h-0 overflow-hidden px-12 py-8">{children}</main>
                <Footer />
                {/* Sonner toast 全局 mount: RQ onError + 各处 toast.error 都会显示在这里 */}
                <Toaster richColors closeButton position="top-right" />
              </I18nProvider>
            </ThemeProvider>
          </ChatApiProvider>
        </MotionConfig>
      </body>
    </html>
  );
}
