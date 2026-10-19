"use client";
/**
 * 顶部右上角用户菜单 — anon 显示登录按钮, 账号显示 display_name 下拉菜单
 * @param props.user 用户信息, null 时为匿名态
 * @returns JSX 元素
 * @client-bff
 */
// (2026-06-14) shadcn: <details>/<summary> → <DropdownMenu>, <Link> anon → <Button>
// (2026-06-16) 登出: 不用 <form action> (Radix DropdownMenuItem 会拦截 onSelect 关菜单,
//                       DOM 节点提前移除, form 来不及提交). 改 onClick + useTransition
//                       直接调 logoutAction.
// (2026-06-17) v2 RBAC: 加 role 字段, 用 isAdminLevel / isSuperAdmin 替 is_admin bool,
//            Super_admin 多 权限管理 链接
import { AppDropdownMenu } from "@/components/common/input/app-dropdown-menu";
import { isAdminLevel, isSuperAdmin } from "@/lib/auth/role";
import { Button } from "@/components/ui/button";
import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { logoutAction } from "@/app/[locale]/_actions/account";
import { LS_KEY_WAS_LOGGED_IN } from "@/const";
import { useTransition } from "react";
import { useTranslations } from "next-intl";

/** UserMenu 组件的 user 属性类型 */
export interface UserMenuUser {
  is_account: boolean;
  is_admin: boolean;
  role?: string;
  email: string | null;
  display_name: string | null;
}

interface BuildMenuItemsCtx {
  isPending: boolean;
  onLogout: () => void;
  roleUser: { role: string };
  tr: (key: string) => string;
}

// (2026-06-29) 抽自 JSX 内联 — 模块级函数, 消除 7 元素内联数组
const buildMenuItems = ({ isPending, onLogout, roleUser, tr }: BuildMenuItemsCtx) => [
  {
    key: "admin-users",
    href: "/admin/users",
    label: tr("用户管理"),
    testid: "menu-admin-users",
    hidden: !isAdminLevel(roleUser),
  },
  {
    key: "admin-profile-fields",
    href: "/admin/profile-fields",
    label: tr("画像字段配置"),
    testid: "menu-profile-fields",
    hidden: !isAdminLevel(roleUser),
  },
  {
    key: "admin-permissions",
    href: "/admin/permissions",
    label: tr("权限管理"),
    testid: "menu-permissions",
    hidden: !isSuperAdmin(roleUser),
  },
  {
    key: "admin-dicts",
    href: "/admin/dicts",
    label: tr("字典管理"),
    testid: "menu-dicts",
    hidden: !isSuperAdmin(roleUser),
  },
  {
    key: "admin-pre-analysis",
    href: "/admin/pre-analysis",
    label: tr("PDF 预分析"),
    testid: "menu-pre-analysis",
    hidden: !isAdminLevel(roleUser),
  },
  {
    key: "account-settings",
    href: "/account/settings",
    label: tr("账号设置"),
    testid: "menu-account-settings",
  },
  { key: "logout-sep", separator: true, label: "" },
  {
    key: "logout",
    label: tr("登出"),
    onClick: onLogout,
    testid: "menu-logout",
    disabled: isPending,
  },
];

/**
 * UserMenu — 顶部右上角用户菜单, anon 显示登录按钮, 账号显示 display_name 下拉菜单
 * @param props.user 用户信息, null 时为匿名态
 * @returns JSX 元素
 * @client-bff
 */
export const UserMenu = ({ user }: { user: UserMenuUser | null }) => {
  const tr = useTranslations();
  const [isPending, startTransition] = useTransition();

  const handleLogout = () => {
    startTransition(async () => {
      await logoutAction();
      // 2026-06-18: AuthBootstrap 用 localStorage 标记防止 anon 覆盖真账号
      try {
        localStorage.removeItem(LS_KEY_WAS_LOGGED_IN);
      } catch {
        // LocalStorage 不可用时静默
      }
      // 跳到首页刷新登录态
      globalThis.location.href = "/";
    });
  };

  // 1. anon → 登录按钮
  if (!user || !user.is_account) {
    return (
      <Button
        asChild
        variant="outline"
        size="sm"
        data-testid="user-menu-login"
        className="border-border bg-card hover:border-ink/40"
      >
        <Link href="/login">{tr("登录")}</Link>
      </Button>
    );
  }

  // 2. 账号 → display_name 下拉 (shadcn DropdownMenu)
  // V2 RBAC: 用 role 字段判断. 兼容老 user 对象 (无 role) → 走 is_admin bool 兜底
  const roleUser =
    user.role !== undefined ? { role: user.role } : { role: user.is_admin ? "admin" : "user" };

  return (
    <div className="flex items-center gap-3">
      <AppDropdownMenu
        trigger={
          <Button
            variant="outline"
            size="sm"
            data-testid="user-menu"
            className="border-border bg-card"
          >
            {user.display_name ?? user.email}
            <ChevronDown className="ml-1 h-3 w-3" />
          </Button>
        }
        contentClassName="w-48"
        items={buildMenuItems({ isPending, onLogout: handleLogout, roleUser, tr })}
      />
    </div>
  );
};
