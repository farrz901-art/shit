"use client";
/**
 * 设置弹框 — 主题切换 / 语言切换
 * @param props.open 弹框展开状态
 * @param props.onOpenChange 展开状态回调
 * @returns JSX 元素
 * @client-bff
 */
//   主题切换 (活) / 语言切换 (活) / 监控 (链) / 账号 (占位)
import { useLocale } from "next-intl";
import { useTransition } from "react";

import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppSelect } from "@/components/common/input/app-select";
import { usePathname, useRouter } from "@/i18n/navigation";
import { themes, useTheme } from "@/lib/theme";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const LOCALE_LABELS: Record<string, string> = {
  en: "English",
  zh: "中文",
};

/**
 * SettingsDialog — 设置弹框, 主题切换 / 语言切换
 * @param props.open 弹框展开状态
 * @param props.onOpenChange 展开状态回调
 * @returns JSX 元素
 * @client-bff
 */
export const SettingsDialog = ({ open, onOpenChange }: Props) => {
  const { theme, setTheme } = useTheme();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [isPending, startTransition] = useTransition();

  const handleLocaleChange = (newLocale: string) => {
    // Cookie 持久化 (next-intl 自动读 NEXT_LOCALE)
    document.cookie = `NEXT_LOCALE=${newLocale}; path=/; max-age=31536000; SameSite=Lax`;
    startTransition(() => {
      // 用 next-intl 原生 locale 切换: 当前路径 + 新 locale
      // usePathname 来自 @/i18n/navigation, 已不含 locale 前缀
      router.push(pathname, { locale: newLocale });
      router.refresh();
    });
  };

  return (
    <AppDialog open={open} onOpenChange={onOpenChange} title="设置" maxWidth="sm">
      <div className="divide-y divide-border/40">
        {/* 行 1: 主题 (活) */}
        <div className="flex items-center justify-between px-6 py-4">
          <span className="text-sm font-medium">主题</span>
          <AppSelect
            options={[
              ...themes.map((entry) => ({ label: entry.label, value: entry.name })),
              { label: "跟随系统", value: "system" },
            ]}
            value={theme}
            onChange={(val) => setTheme(val as typeof theme)}
            className="w-32"
          />
        </div>

        {/* 行 2: 语言 (活) */}
        <div className="flex items-center justify-between px-6 py-4">
          <span className="text-sm font-medium">语言</span>
          <AppSelect
            options={(["zh", "en"] as const).map((loc) => ({
              label: LOCALE_LABELS[loc] ?? loc,
              value: loc,
            }))}
            value={locale}
            onChange={handleLocaleChange}
            disabled={isPending}
            className="w-32"
          />
        </div>
      </div>
    </AppDialog>
  );
};
