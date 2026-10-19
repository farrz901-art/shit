/**
 * 设置入口按钮 (Header 右上角齿轮图标)
 * 点击 → onOpen (Header 控制 SettingsDialog open 状态)
 * 注意: 只负责触发, 真正的设置面板 (主题/语言/...) 在 SettingsDialog 内
 *   - Header 内 useState(settingsOpen) 管 dialog 显隐
 *   - 设置项真值变化 → SettingsDialog 通过 onChange 回调 (或 zustand 持久化) 上抛
 */
"use client";
import { Button } from "@/components/ui/button";
import { Settings } from "lucide-react";

interface Props {
  onOpen: () => void;
}

/**
 * ThemeToggle — 设置入口按钮, Header 右上角齿轮图标, 点击触发 SettingsDialog 打开
 * @param props.onOpen 打开弹框回调
 * @returns JSX 元素
 * @client-bff
 */
export const ThemeToggle = ({ onOpen }: Props) => (
  <Button variant="ghost" size="icon" onClick={onOpen} aria-label="设置" data-testid="theme-toggle">
    <Settings className="h-4 w-4" />
  </Button>
);
