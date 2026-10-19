/**
 * 会话侧栏 — 展示对话列表 + 新建/删除操作
 * @param props.conversations 会话列表
 * @param props.currentId 当前会话 id
 * @param props.onSelect 选中回调
 * @param props.onCreate 新建回调
 * @param props.onDelete 删除回调
 * @returns JSX 元素
 * @shared
 */
// (2026-06-14) shadcn: 删除 <button> → <Button variant="ghost" size="icon"> + barrel
import { ZERO } from "@/const";
import { Button } from "@/components/ui/button";
import { type Conversation } from "@/lib/chat";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatRelativeTime } from "@/lib/date";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * 会话列表组件属性接口
 * @shared
 */
interface Props {
  conversations: Conversation[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

/** 新建对话按钮文案 @shared */
const NEW_CONV_LABEL = "+ 新对话";
/** 空列表提示文案 @shared */
const EMPTY_HINT = "开始一段新对话";

/**
 * 会话侧栏组件 — 展示对话列表 + 新建/删除操作
 * @param props.conversations 会话列表
 * @param props.currentId 当前会话 id
 * @param props.onSelect 选中回调
 * @param props.onCreate 新建回调
 * @param props.onDelete 删除回调
 * @returns JSX 元素
 * @shared
 */
export const ConversationList = ({
  conversations,
  currentId,
  onSelect,
  onCreate,
  onDelete,
}: Props) => {
  const sorted = [...conversations].toSorted((convA, convB) => convB.updatedAt - convA.updatedAt);

  /**
   * 渲染空列表提示
   * @client-bff
   */
  const renderEmpty = () => (
    <p data-testid="empty-conv" className="px-2 py-6 text-center text-sm text-muted-foreground">
      {EMPTY_HINT}
    </p>
  );

  /**
   * 渲染会话列表
   * @client-bff
   */
  const renderList = () => (
    <ul className="space-y-1">
      {sorted.map((conv) => {
        const isCurrent = conv.id === currentId;
        const onClickSelect = () => onSelect(conv.id);
        const onClickDelete = (event: React.MouseEvent) => {
          event.stopPropagation();
          onDelete(conv.id);
        };
        return (
          <li key={conv.id}>
            <div
              data-testid={`conv-${conv.id}`}
              onClick={onClickSelect}
              className={cn(
                "group flex cursor-pointer items-baseline gap-2 rounded-md border border-transparent px-2.5 py-2 transition-colors hover:bg-muted/40",
                isCurrent && "border-clay/40 bg-clay/5",
              )}
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{conv.title}</div>
                <div className="num mt-0.5 text-xs text-muted-foreground/60">
                  {formatRelativeTime(conv.updatedAt)} · {conv.messageCount} 条
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClickDelete}
                className="h-6 w-6 shrink-0 text-xs text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                aria-label="删除会话"
                data-testid={`delete-${conv.id}`}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );

  const list = sorted.length === ZERO ? renderEmpty() : renderList();

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-border/60 bg-card/30">
      <div className="px-3 py-2">
        <Button data-testid="new-conv" onClick={onCreate} variant="outline" className="w-full">
          {NEW_CONV_LABEL}
        </Button>
      </div>

      <ScrollArea className="flex-1 px-2">{list}</ScrollArea>
    </aside>
  );
};
