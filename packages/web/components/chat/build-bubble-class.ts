/**
 * 气泡基础样式 (2026-06-29 message-bubble 拆分)
 * 原 message-bubble.tsx IIFE 提取 — 模块级纯函数
 * isUser → 实色 (ink/paper); assistant → 边框 + bg-card
 */
const MAX_WIDTH_CLASS = "max-w-[80%]";
const BUBBLE_PADDING = "px-4 py-2.5";
const USER_BUBBLE_CLASS = `${MAX_WIDTH_CLASS} rounded-2xl bg-ink ${BUBBLE_PADDING} text-paper`;
const ASSISTANT_BUBBLE_CLASS = `${MAX_WIDTH_CLASS} rounded-2xl border border-border/60 bg-card ${BUBBLE_PADDING}`;

/**
 * 根据消息角色构建气泡 CSS 类名
 * @param isUser 是否为用户消息
 * @returns 完整的气泡样式类名
 * @shared
 */
export const buildBubbleClass = (isUser: boolean): string =>
  isUser ? USER_BUBBLE_CLASS : ASSISTANT_BUBBLE_CLASS;
