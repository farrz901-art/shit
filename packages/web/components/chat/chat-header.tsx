"use client";
/**
 * 聊天头部工具栏 — 分享 + 记忆管理入口按钮
 * anon 模式下不显示分享按钮
 * @param props.isAccount 是否为登录账号
 * @param props.onShareOpen 分享弹框展开回调
 * @param props.onMemoryOpen 记忆管理弹框展开回调
 * @returns JSX 元素
 * @client-bff
 */
import { Brain, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * ChatHeader 组件属性
 * @property isAccount - 是否为登录账号
 * @property onShareOpen - 分享弹框展开回调
 * @property onMemoryOpen - 记忆管理弹框展开回调
 */
interface ChatHeaderProps {
  isAccount: boolean;
  onShareOpen: () => void;
  onMemoryOpen: () => void;
}

/** chat-header @client-bff */
export const ChatHeader = ({ isAccount, onShareOpen, onMemoryOpen }: ChatHeaderProps) => (
  <div className="flex items-center justify-end gap-1 border-b px-3 py-1.5">
    {/* (2026-06-30) Share 按钮 anon 不显示 — anon 本地 conv (crypto.randomUUID) 不在
        后端 conversations 表, create_share 会 FK miss. 等未来 anon 也支持再开. */}
    {isAccount && (
      <Button
        size="icon"
        variant="ghost"
        onClick={onShareOpen}
        aria-label="分享对话"
        data-testid="share-button"
      >
        <Share2 className="h-5 w-5" />
      </Button>
    )}
    {isAccount && (
      <Button
        size="icon"
        variant="ghost"
        onClick={onMemoryOpen}
        aria-label="记忆管理"
        data-testid="memory-management-button"
      >
        <Brain className="h-5 w-5" />
      </Button>
    )}
  </div>
);
