"use client";
/**
 * 分享对话 Dialog — 创建 share + 显示 URL + 复制 + 列出已创建 share + 撤销
 * 入口: ChatShell 头部 Share 图标点击
 * @param props.open 弹框展开状态
 * @param props.onOpenChange 展开状态回调
 * @param props.convId 当前会话 id
 * @param props.messages 当前会话消息列表
 * @returns JSX 元素
 * @client-bff
 */
// 入口: ChatShell 头部 Share 图标点击.
// 功能: 创建 share + 显示 URL + 复制 + 列出已创建 share + 撤销.
// 样式: 跟 MemoryManagementDialog 一致, 用 common/dialog/AppDialog + common/confirm/AppConfirm.
// (2026-06-30) 创建时序列化 messages 传给后端; mount 时 + convId 切换时拉已分享列表.
import { Copy, Share2, Trash2 } from "lucide-react";
import { type ShareResponse, createShare, listShares, revokeShare } from "@/lib/api/chat-share";
import { AppConfirm } from "@/components/common/confirm/app-confirm";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ZERO } from "@/const";
import { toInstant } from "@/lib/date";
import { toast } from "sonner";
import { useEffect, useState } from "react";
import { useBoolean, useCopyToClipboard } from "react-use";
import { useTranslations } from "next-intl";

/**
 * 分享弹框属性接口
 * @client-bff
 */
interface ShareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  convId: string | null;
  // (2026-06-30) 业务侧注入当前会话 messages, 创建 share 时序列化传给后端.
  messages?: { role: "user" | "assistant"; content: string; createdAt: number }[];
}

/** 创建中占位文字 @shared */
const CREATING_TEXT = "...";

/** 分享创建/复制/撤销逻辑 — 抽出自定义 hook 降 max-statements
 * @returns 分享操作相关状态和回调
 * @client-bff */
const useShareActions = ({
  convId,
  messages,
  setShares,
  translation,
}: {
  convId: string | null;
  messages: ShareDialogProps["messages"];
  setShares: React.Dispatch<React.SetStateAction<ShareResponse[]>>;
  translation: ReturnType<typeof useTranslations>;
}) => {
  const [creating, setCreating] = useBoolean(false);
  const [pendingRevoke, setPendingRevoke] = useState<ShareResponse | null>(null);
  const [, copyToClipboard] = useCopyToClipboard();

  /**
   * 创建分享 — 校验 + 调 API + 更新列表
   * @client-bff
   */
  // oxlint-disable-next-line max-statements -- 序列化的 createShare 调用需要 statements 数, 不拆函数
  const handleCreate = async () => {
    if (!convId) {
      return;
    }
    if (!messages || messages.length === ZERO) {
      // (2026-06-30) 跟后端 schema min_length=1 对齐: 空 messages 不发请求, 弹 toast.
      toast.error(translation("当前会话没有消息, 无法分享"));
      return;
    }
    setCreating(true);
    try {
      const res = await createShare({
        convId,
        messages: messages.map((message) => ({
          role: message.role,
          content: message.content,
          timestamp: toInstant(message.createdAt).toString(),
        })),
      });
      setShares((prev) => [res, ...prev]);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setCreating(false);
    }
  };

  /**
   * 复制分享链接到剪贴板
   * @param url 分享 URL
   * @client-bff
   */
  const handleCopy = (url: string) => {
    copyToClipboard(url);
    toast.success(translation("已复制"));
  };

  /**
   * 确认撤销分享
   * @client-bff
   */
  const confirmRevoke = async () => {
    if (!pendingRevoke) {
      return;
    }
    const target = pendingRevoke;
    setPendingRevoke(null);
    try {
      await revokeShare(target.share_id);
      setShares((prev) => prev.filter((share) => share.share_id !== target.share_id));
    } catch (error) {
      toast.error((error as Error).message);
    }
  };

  return { confirmRevoke, creating, handleCopy, handleCreate, pendingRevoke, setPendingRevoke };
};

/**
 * 分享对话 Dialog 主组件 — 创建/列表/复制/撤销分享
 * @param props.open 弹框展开状态
 * @param props.onOpenChange 展开状态回调
 * @param props.convId 当前会话 id
 * @param props.messages 当前会话消息
 * @returns JSX 元素
 * @client-bff
 */
export const ShareDialog = ({ open, onOpenChange, convId, messages = [] }: ShareDialogProps) => {
  const translation = useTranslations();
  const [shares, setShares] = useState<ShareResponse[]>([]);

  // (2026-06-30) mount 时 + convId 切换时拉该 conv 已创建的 share 列表.
  useEffect(() => {
    if (!open || !convId) {
      return;
    }
    listShares(convId)
      .then(setShares)
      .catch((error) => {
        toast.error((error as Error).message);
      });
  }, [open, convId]);

  const { confirmRevoke, creating, handleCopy, handleCreate, pendingRevoke, setPendingRevoke } =
    useShareActions({ convId, messages, setShares, translation });

  /**
   * 渲染创建分享按钮
   * @client-bff
   */
  const renderCreateButton = () => {
    let createLabel = "";
    if (creating) {
      createLabel = CREATING_TEXT;
    } else {
      createLabel = translation("分享");
    }
    return (
      <Button
        onClick={handleCreate}
        disabled={!convId || messages.length === ZERO || creating}
        data-testid="share-dialog-create"
      >
        <Share2 className="mr-2 h-4 w-4" />
        {createLabel}
      </Button>
    );
  };

  /**
   * 渲染空列表提示
   * @client-bff
   */
  const renderEmpty = () => {
    let hint = "";
    if (!convId) {
      hint = "—";
    } else if (messages.length === ZERO) {
      hint = translation("当前会话没有消息, 无法分享");
    } else {
      hint = translation("我的分享");
    }
    return <div className="py-8 text-center text-sm text-muted-foreground">{hint}</div>;
  };

  /**
   * 渲染单条分享行 (URL 输入框 + 复制 + 撤销)
   * @param share 分享数据
   * @returns JSX 元素
   * @client-bff
   */
  const renderShareRow = (share: ShareResponse) => {
    const onClickCopy = () => handleCopy(share.url);
    const onClickRevoke = () => setPendingRevoke(share);
    return (
      <div
        key={share.share_id}
        className="flex items-center gap-2 rounded-md border p-3"
        data-testid={`share-row-${share.share_id}`}
      >
        <Input value={share.url} readOnly className="flex-1 font-mono text-xs" />
        <Button
          size="icon"
          variant="ghost"
          onClick={onClickCopy}
          data-testid="share-dialog-copy"
          aria-label={translation("复制链接")}
        >
          <Copy className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          onClick={onClickRevoke}
          data-testid="share-dialog-revoke"
          aria-label={translation("撤销分享")}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    );
  };

  return (
    <>
      <AppDialog
        open={open}
        onOpenChange={onOpenChange}
        title={translation("分享对话")}
        description={translation("我的分享")}
        maxWidth="lg"
        icon={<Share2 className="h-5 w-5" />}
        footer={renderCreateButton()}
      >
        <div className="flex flex-col gap-3">
          {shares.length === ZERO && renderEmpty()}
          {shares.map(renderShareRow)}
        </div>
      </AppDialog>

      <AppConfirm
        open={pendingRevoke !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) {
            setPendingRevoke(null);
          }
        }}
        title={translation("撤销分享")}
        description={translation("我的分享")}
        confirmText={translation("撤销分享")}
        cancelText={translation("取消")}
        variant="destructive"
        onConfirm={confirmRevoke}
      />
    </>
  );
};
