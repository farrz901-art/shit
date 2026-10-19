/**
 * Assistant 消息主体 (2026-06-30 streamdown 迁移)
 * 原 message-bubble.tsx 内联 IIFE bodyContent (assistant 分支) 提取
 * 关键: parseThinkTag 拆 thinking / answer → ThinkBlock 折叠 + MarkdownStream 渲染 answer
 *       markdown img 点击 → onPreview 回调给父组件弹 ImagePreview
 */
import { MarkdownStream } from "@/components/markdown/markdown-stream";
import { ThinkBlock } from "@/components/markdown/think-block";
import { type ReactNode } from "react";

/** think 标签匹配正则 (含 named capture group) */
const THINK_TAG_PATTERN = /<think>(?<thinkingContent>[\s\S]*?)<\/think>/;
/** think 标签移除正则 (剔除整个标签) */
const THINK_REMOVE_PATTERN = /<think>[\s\S]*?<\/think>/;
/** 空 thinking 占位符 */
const EMPTY_THINKING = "";

/**
 * parseThinkTag - 从 content 中提取 think 标签
 * @param content - 消息文本
 * @returns 拆分后的 thinking 和 answer
 */
const parseThinkTag = (content: string): { thinking: string; answer: string } => {
  const match = content.match(THINK_TAG_PATTERN);
  if (!match) {
    return { answer: content, thinking: EMPTY_THINKING };
  }
  return {
    answer: content.replace(THINK_REMOVE_PATTERN, "").trim(),
    thinking: match.groups?.thinkingContent?.trim() ?? "",
  };
};

/**
 * AssistantBodyProps - Assistant 消息主体属性
 * @property content - 消息内容
 * @property onPreview - 图片预览回调
 */
interface AssistantBodyProps {
  content: string;
  onPreview: (src: string) => void;
}

/**
 * AssistantBody — Assistant 消息主体组件 (2026-06-30 streamdown 迁移)
 * 原 message-bubble.tsx 内联 IIFE bodyContent (assistant 分支) 提取
 * 关键: parseThinkTag 拆 thinking / answer → ThinkBlock 折叠 + MarkdownStream 渲染 answer
 *       markdown img 点击 → onPreview 回调给父组件弹 ImagePreview
 * @param props.content - 消息内容
 * @param props.onPreview - 图片预览回调
 * @returns ReactNode 元素
 */
export const AssistantBody = ({ content, onPreview }: AssistantBodyProps): ReactNode => {
  const { thinking, answer } = parseThinkTag(content);
  return (
    <>
      {thinking && (
        <ThinkBlock defaultOpen testId="think-toggle">
          {thinking}
        </ThinkBlock>
      )}
      <MarkdownStream onPreview={onPreview}>{answer}</MarkdownStream>
    </>
  );
};
