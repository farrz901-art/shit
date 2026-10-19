"use client";
/**
 * 长期记忆管理 Dialog — 列表 + 客户端搜索 + 编辑 + 单删 + 清空全部
 * 入口: ChatShell 头部 Brain 图标点击
 * @param props.open 弹框展开状态
 * @param props.onOpenChange 展开状态回调
 * @returns JSX 元素
 * @client-bff
 */
// 入口: ChatShell 头部 Brain 图标点击.
// 功能: 列表 + 客户端搜索 + 编辑 + 单删 + 清空全部 (AppConfirm 二次确认).
// 安全: 所有 mutating 操作走后端 _assert_owned, 前端不需做隔离.
import { Brain, Pencil, Trash2 } from "lucide-react";
import { type MemoryHit, list, update, deleteMemory, deleteAll } from "@/lib/api/memory";
import { useEffect, useState } from "react";
import { useBoolean } from "react-use";
import { AppConfirm } from "@/components/common/confirm/app-confirm";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ZERO } from "@/const";
import { useTranslations } from "next-intl";

/**
 * 记忆管理弹框属性接口
 * @client-bff
 */
interface MemoryManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** 列表最小高度 @shared */
const MIN_LIST_HEIGHT = "min-h-[200px]";
/** 加载中占位文字 @shared */
const LOADING_TEXT = "...";
/** 取消按钮文字 @shared */
const CANCEL_TEXT = "✕";

// (2026-06-29) 抽自 useMemoryFilter — 模块级纯函数, 消除 IIFE
/**
 * 客户端按文本过滤记忆列表
 * @param memories 原始记忆列表
 * @param query 搜索关键词
 * @returns 过滤后的记忆列表 (不区分大小写)
 * @shared
 */
const filterMemories = (memories: MemoryHit[], query: string): MemoryHit[] => {
  if (!query) {
    return memories;
  }
  const lower = query.toLowerCase();
  return memories.filter((memory) => memory.text.toLowerCase().includes(lower));
};

// --- 状态 hook (数据加载) ---

/**
 * 数据加载 hook — 弹框打开时自动加载记忆列表
 * @param open 弹框是否展开
 * @returns 记忆列表 / 加载中状态 / 重新加载函数 / 设置记忆函数
 * @client-bff
 */
const useMemoryApi = (open: boolean) => {
  const [memories, setMemories] = useState<MemoryHit[]>([]);
  const [loading, setLoading] = useBoolean(false);
  const load = async () => {
    setLoading(true);
    try {
      const { memories: fetched } = await list();
      setMemories(fetched);
    } catch {
      setMemories([]); // 降级: 失败 → 空
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    if (open) {
      load();
    }
  }, [open]);
  return { load, loading, memories, setMemories };
};

// --- 状态 hook (客户端过滤) ---

/**
 * 客户端过滤 hook — 按搜索词过滤记忆列表
 * @param memories 原始记忆列表
 * @returns 过滤词 / 过滤后列表 / 设置过滤词函数
 * @client-bff
 */
const useMemoryFilter = (memories: MemoryHit[]) => {
  const [filter, setFilter] = useState("");
  const filtered = filterMemories(memories, filter);
  return { filter, filtered, setFilter };
};

// --- 状态 hook (编辑) ---

/**
 * 编辑状态 hook — 追踪当前编辑的记忆 id 和文本
 * @returns 编辑 id / 编辑文本 / 设置 id / 设置文本
 * @client-bff
 */
const useMemoryEdit = () => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingText, setEditingText] = useState("");
  return { editingId, editingText, setEditingId, setEditingText };
};

// --- 子组件: 清空按钮 ---

/**
 * 弹框底部清空按钮
 * @param props.memories 当前记忆列表 (用于判断按钮是否可用)
 * @param props.translation i18n 翻译函数
 * @param props.setClearAllOpen 打开清空确认弹框
 * @returns JSX 元素
 * @client-bff
 */
const MemoryDialogFooter = ({
  memories,
  translation,
  setClearAllOpen,
}: {
  memories: MemoryHit[];
  translation: (key: string) => string;
  setClearAllOpen: (value: boolean) => void;
}) => (
  <Button
    variant="destructive"
    onClick={() => setClearAllOpen(true)}
    disabled={memories.length === ZERO}
  >
    <Trash2 className="h-4 w-4 mr-2" />
    {translation("清空所有记忆")}
  </Button>
);

// --- 子组件: 列表行 ---

/**
 * 单条记忆行 — 编辑态 (Input + 保存/取消) / 展示态 (文本 + 编辑/删除按钮)
 * @param props.memory 记忆数据
 * @param props.editingId 当前正在编辑的记忆 id
 * @param props.editingText 编辑中的文本
 * @param props.setEditingId 设置编辑 id
 * @param props.setEditingText 设置编辑文本
 * @param props.saveEdit 保存编辑回调
 * @param props.handleDelete 删除回调
 * @param props.translation i18n 翻译函数
 * @returns JSX 元素
 * @client-bff
 */
const MemoryListItem = ({
  memory,
  editingId,
  editingText,
  setEditingId,
  setEditingText,
  saveEdit,
  handleDelete,
  translation,
}: {
  memory: MemoryHit;
  editingId: string | null;
  editingText: string;
  setEditingId: (id: string | null) => void;
  setEditingText: (text: string) => void;
  saveEdit: () => void;
  handleDelete: (id: string) => void;
  translation: (key: string) => string;
}) => {
  const isEditing = editingId === memory.id;
  if (isEditing) {
    const onClickCancel = () => setEditingId(null);
    return (
      <div
        key={memory.id}
        className="flex items-center gap-2 p-3 border rounded-md"
        data-testid={`memory-${memory.id}`}
      >
        <Input
          value={editingText}
          onChange={(event) => setEditingText(event.target.value)}
          className="flex-1"
          autoFocus
        />
        <Button size="sm" onClick={saveEdit}>
          {translation("保存")}
        </Button>
        <Button size="sm" variant="ghost" onClick={onClickCancel}>
          {CANCEL_TEXT}
        </Button>
      </div>
    );
  }
  const onClickEdit = () => {
    setEditingId(memory.id);
    setEditingText(memory.text);
  };
  const onClickDelete = () => handleDelete(memory.id);
  return (
    <div
      key={memory.id}
      className="flex items-center gap-2 p-3 border rounded-md"
      data-testid={`memory-${memory.id}`}
    >
      <span className="flex-1 text-sm">{memory.text}</span>
      <Button size="icon" variant="ghost" onClick={onClickEdit}>
        <Pencil className="h-4 w-4" />
        <span className="sr-only">{translation("编辑")}</span>
      </Button>
      <Button size="icon" variant="ghost" onClick={onClickDelete}>
        <Trash2 className="h-4 w-4" />
        <span className="sr-only">{translation("删除")}</span>
      </Button>
    </div>
  );
};

// --- 子组件: 列表容器 (加载/空态/列表) ---

/**
 * 记忆列表容器 — 加载态 / 空态 / 列表渲染
 * @param props.loading 是否加载中
 * @param props.filtered 过滤后的记忆列表
 * @param props.translation i18n 翻译函数
 * @param props.editingId 当前编辑 id
 * @param props.editingText 当前编辑文本
 * @param props.setEditingId 设置编辑 id
 * @param props.setEditingText 设置编辑文本
 * @param props.saveEdit 保存编辑回调
 * @param props.handleDelete 删除回调
 * @returns JSX 元素
 * @client-bff
 */
const MemoryListContent = ({
  loading,
  filtered,
  translation,
  editingId,
  editingText,
  setEditingId,
  setEditingText,
  saveEdit,
  handleDelete,
}: {
  loading: boolean;
  filtered: MemoryHit[];
  translation: (key: string) => string;
  editingId: string | null;
  editingText: string;
  setEditingId: (id: string | null) => void;
  setEditingText: (text: string) => void;
  saveEdit: () => void;
  handleDelete: (id: string) => void;
}) => {
  if (loading) {
    return <div className="text-muted-foreground text-sm">{LOADING_TEXT}</div>;
  }
  if (filtered.length === ZERO) {
    return (
      <div className="text-muted-foreground text-sm py-8 text-center">
        {translation("还没有记忆。开始聊天, AI 会自动记下你说的事实。")}
      </div>
    );
  }
  return filtered.map((memory) => (
    <MemoryListItem
      key={memory.id}
      memory={memory}
      editingId={editingId}
      editingText={editingText}
      setEditingId={setEditingId}
      setEditingText={setEditingText}
      saveEdit={saveEdit}
      handleDelete={handleDelete}
      translation={translation}
    />
  ));
};

// --- 主组件 ---

/**
 * 长期记忆管理 Dialog 主组件 — 列表/搜索/编辑/删除/清空
 * @param props.open 弹框展开状态
 * @param props.onOpenChange 展开状态回调
 * @returns JSX 元素
 * @client-bff
 */
export const MemoryManagementDialog = ({ open, onOpenChange }: MemoryManagementDialogProps) => {
  const translation = useTranslations();
  const [clearAllOpen, setClearAllOpen] = useState(false);
  const { memories, loading, load } = useMemoryApi(open);
  const { filter, setFilter, filtered } = useMemoryFilter(memories);
  const { editingId, setEditingId, editingText, setEditingText } = useMemoryEdit();

  // 编辑保存
  const saveEdit = async () => {
    if (!editingId || !editingText.trim()) {
      return;
    }
    await update(editingId, editingText);
    setEditingId(null);
    setEditingText("");
    await load();
  };

  // 单删
  const handleDelete = async (id: string) => {
    await deleteMemory(id);
    await load();
  };

  // 清空
  const handleClearAll = async () => {
    await deleteAll();
    setClearAllOpen(false);
    await load();
  };

  return (
    <>
      <AppDialog
        open={open}
        onOpenChange={onOpenChange}
        title={`${translation("我的记忆")} (${memories.length})`}
        description={translation("记忆管理")}
        maxWidth="2xl"
        icon={<Brain className="h-5 w-5" />}
        footer={
          <MemoryDialogFooter
            memories={memories}
            translation={translation}
            setClearAllOpen={setClearAllOpen}
          />
        }
      >
        <div className={`flex flex-col gap-2 ${MIN_LIST_HEIGHT}`}>
          <Input
            placeholder={translation("搜索记忆")}
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />

          <div className={`flex-1 overflow-y-auto space-y-2 ${MIN_LIST_HEIGHT}`}>
            <MemoryListContent
              loading={loading}
              filtered={filtered}
              translation={translation}
              editingId={editingId}
              editingText={editingText}
              setEditingId={setEditingId}
              setEditingText={setEditingText}
              saveEdit={saveEdit}
              handleDelete={handleDelete}
            />
          </div>
        </div>
      </AppDialog>

      <AppConfirm
        open={clearAllOpen}
        onOpenChange={setClearAllOpen}
        title={translation("确定清空所有记忆?")}
        description={translation("此操作不可撤销。你的所有记忆将被永久删除。")}
        confirmText={translation("确认清空")}
        cancelText={CANCEL_TEXT}
        variant="destructive"
        onConfirm={handleClearAll}
      />
    </>
  );
};
