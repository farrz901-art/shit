/**
 * 全站顶部 Header (2026-07-02 redesign) — RSC 友好, 仅交互部分 (SettingsDialog) 用 client
 * 3 段:
 *   1. 品牌区: RAG · 德源通泰 (LocalizedLink "/")
 *   2. 导航: buildNavTree + filterNavByPermissions 树形渲染
 *      - ≥ sm: 顶级无子项 → NavLink, 顶级有子项 → NavDropdown
 *      - < sm: 汉堡按钮 → MobileNavDrawer
 *   3. 状态 cluster: EnvBadge + ThemeToggle + UserMenu
 */
"use client";
import { UserMenu, type UserMenuUser } from "@/components/user-menu";
import { useEffect, useState } from "react";
import { EnvBadge } from "@/components/common/display/app-env-badge";
import { LocalizedLink } from "@/components/i18n/localized-link";
import type { PermissionData } from "@/lib/auth/permission-types";
import { SettingsDialog } from "@/components/settings/settings-dialog";
import { ThemeToggle } from "@/components/settings/theme-toggle";
import { useTranslations } from "next-intl";
import { buildNavTree, filterNavByPermissions } from "@/lib/nav/build-nav-tree";
import { NavDropdown } from "@/components/layout/nav-dropdown";
import { MobileNavDrawer, MobileMenuIcon } from "@/components/layout/mobile-nav-drawer";
import { usePathname } from "@/i18n/navigation";

/** 空子节点判断常量, 用于 NavTree 根节点有无子项 */
const EMPTY_CHILDREN = 0;
/** 导航 fallback href, 当 NavNode.path 为 undefined 时兜底 */
const FALLBACK_HREF = "#";

/**
 * Header — 全站顶部 Header (RSC 友好)
 * @param props.user - 用户信息
 * @param props.permissions - 权限数据
 * @returns JSX 元素
 */
export const Header = ({
  user,
  permissions,
}: {
  user?: UserMenuUser | null;
  permissions: PermissionData;
}) => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const translate = useTranslations();
  const pathname = usePathname();
  // (2026-07-02) 走 NavTree 渲染, 取代旧的 flat filter
  const tree = buildNavTree(permissions.pages);
  const visible = filterNavByPermissions(tree, permissions.allowed);

  // 路由切换自动关闭移动端 drawer
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  return (
    <>
      <header className="shrink-0 border-b border-border/60 bg-paper/80 backdrop-blur-sm">
        <div className="mx-auto flex items-center gap-8 px-6 py-4">
          <LocalizedLink
            href="/"
            className="display text-xl tracking-tight transition-opacity hover:opacity-70"
          >
            RAG<span className="text-clay"> · </span>
            {translate("德源通泰")}
          </LocalizedLink>
          {/* 桌面端 nav: ≥ sm 显示, 移动端隐藏 */}
          <nav className="ml-auto hidden items-center gap-1 text-base sm:flex">
            {visible.roots.map((node) =>
              node.children.length > EMPTY_CHILDREN ? (
                <NavDropdown key={node.key} node={node} />
              ) : (
                <NavLink key={node.key} href={node.path ?? FALLBACK_HREF}>
                  {translate(node.label_zh)}
                </NavLink>
              ),
            )}
          </nav>
          {/* 移动端 hamburger: < sm 显示, 桌面隐藏 */}
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label={translate("打开导航菜单")}
            data-testid="mobile-hamburger"
            className="ml-auto rounded-md p-2 text-muted-foreground hover:text-foreground sm:hidden"
          >
            <MobileMenuIcon className="h-5 w-5" />
          </button>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="eyebrow">v0.1</span>
            <EnvBadge />
            <ThemeToggle onOpen={() => setSettingsOpen(true)} />
          </div>
          <UserMenu user={user ?? null} />
        </div>
      </header>
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
      <MobileNavDrawer tree={visible} open={mobileOpen} onOpenChange={setMobileOpen} />
    </>
  );
};

/**
 * NavLink — 顶部导航单个链接项
 * @param props.href 链接地址
 * @param props.children 标签文本
 * @returns JSX 元素 (LocalizedLink)
 * @client-bff
 */
const NavLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
  <LocalizedLink
    href={href}
    data-testid="nav-link"
    className="group relative rounded-md px-3 py-1.5 text-muted-foreground transition-colors duration-300 hover:text-foreground"
    style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
  >
    <span className="relative z-10">{children}</span>
    <span
      className="absolute bottom-0.5 left-3 right-3 h-px origin-left scale-x-0 bg-foreground/40 transition-transform duration-300 group-hover:scale-x-100"
      style={{ transitionTimingFunction: "var(--ease-out-expo)" }}
    />
  </LocalizedLink>
);
