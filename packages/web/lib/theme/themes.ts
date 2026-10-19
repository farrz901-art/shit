/**
 * 主题色定义 (2026-06-14) — light/dark 两套 CSS variable token
 * ThemeColors: 27 个颜色变量 (paper/ink/card/primary/.../status-*)
 * getThemeConfig(name): 根据 name 找 Theme, 不存在 throw
 * 跟 Tailwind 4 + shadcn CSS variable 对齐, 改色只动这个文件
 */
export interface ThemeColors {
  paper: string;
  background: string;
  foreground: string;
  ink: string;
  card: string;
  "card-foreground": string;
  popover: string;
  "popover-foreground": string;
  border: string;
  input: string;
  ring: string;
  muted: string;
  "muted-foreground": string;
  secondary: string;
  "secondary-foreground": string;
  accent: string;
  "accent-foreground": string;
  primary: string;
  "primary-foreground": string;
  clay: string;
  "clay-foreground": string;
  moss: string;
  destructive: string;
  "destructive-foreground": string;
  "status-success": string;
  "status-warning": string;
  "status-error": string;
  "status-running": string;
}

/** 主题定义, 含名称/标签/图标/色值.
 * @shared */
export interface Theme {
  name: "light" | "dark" | string;
  label: string;
  icon: "sun" | "moon" | "eye";
  colors: Partial<ThemeColors>;
}

/** 内置主题列表 (light / dark).
 * @shared */
export const themes: Theme[] = [
  {
    colors: {
      // 跟 globals.css :root 一致, 这里只作 type 文档, 实际色值在 CSS
      background: "0 0% 98%",
      foreground: "222 47% 11%",
      primary: "217 91% 60%",
      "status-error": "0 84% 60%",
      "status-running": "199 89% 48%",
      "status-success": "160 84% 39%",
      "status-warning": "38 92% 50%",
    },
    icon: "sun",
    label: "明亮",
    name: "light",
  },
  {
    colors: {
      background: "222 47% 7%",
      foreground: "210 20% 92%",
      primary: "217 91% 60%",
      "status-error": "0 62.8% 30.6%",
      "status-running": "199 89% 48%",
      "status-success": "160 84% 39%",
      "status-warning": "38 92% 50%",
    },
    icon: "moon",
    label: "暗色",
    name: "dark",
  },
];

/** 根据名称查找主题配置, 不存在则抛错.
 * @param name 主题名 (light / dark)
 * @returns Theme 对象
 * @shared */
export const getThemeConfig = (name: string): Theme => {
  const found = themes.find((entry) => entry.name === name);
  if (!found) {
    throw new Error(`主题 "${name}" 不存在`);
  }
  return found;
};
