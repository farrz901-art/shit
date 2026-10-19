"use client";
/**
 * AnimatePresence mode="wait" 包装 — 3 处 mode="wait" 调用统一 API
 * @param props.children 子节点
 * @param props.mode AnimatePresence 模式, 默认 wait
 * @returns JSX 元素 (AnimatePresence 包装)
 * @client-bff
 */
import { type ReactNode } from "react";
import { AnimatePresence } from "motion/react";

/**
 * FadePresence 可用的 AnimatePresence mode 值
 * @property "wait" 等待当前子节点退出后再渲染新子节点
 * @property "sync" 同时退出和进入
 * @property "popLayout" 退出时布局弹出
 * @client-bff
 */
export type FadePresenceMode = "wait" | "sync" | "popLayout";

/** FadePresence 组件的属性 */
export interface FadePresenceProps {
  children: ReactNode;
  mode?: FadePresenceMode;
}

/**
 * FadePresence — AnimatePresence mode="wait" 包装
 * @param props.children 子节点
 * @param props.mode AnimatePresence 模式
 * @returns JSX 元素
 * @client-bff
 */
export const FadePresence = ({ children, mode = "wait" }: FadePresenceProps) => (
  <AnimatePresence mode={mode}>{children}</AnimatePresence>
);
