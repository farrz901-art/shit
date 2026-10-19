// (2026-06-29) DictPageActions 子组件 — 抽自 admin-dicts-client.tsx 的 PageHero actions 内联
// 严重度 LOW (预防性) — admin-dicts-client 临界 290 行, 拆 actions 减 25 行
"use client";

import { History, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

/** 字典页面操作按钮组件属性 */
interface DictPageActionsProps {
  /** 打开字典审计历史回调 */
  onOpenAudit: () => void;
  /** 打开新增字典项弹框回调 */
  onOpenCreate: () => void;
  /** i18n 翻译函数 */
  translate: (key: string) => string;
}

/**
 * 字典页面操作按钮组件
 *
 * 抽自 admin-dicts-client.tsx 的 PageHero actions 内联,
 * 拆出来减少 PageHero 复杂度.
 *
 * @param props - 组件属性
 * @param props.onOpenAudit - 打开字典审计历史回调
 * @param props.onOpenCreate - 打开新增字典项弹框回调
 * @param props.translate - i18n 翻译函数
 * @client-bff
 */
export const DictPageActions = ({ onOpenAudit, onOpenCreate, translate }: DictPageActionsProps) => (
  <div className="flex gap-2">
    <Button data-testid="open-audit-dict" onClick={onOpenAudit} size="sm" variant="outline">
      <History className="mr-1 h-4 w-4" />
      {translate("查看字典历史")}
    </Button>
    <Button data-testid="create-item-btn" onClick={onOpenCreate} size="sm">
      <Plus className="mr-1 h-4 w-4" />
      {translate("新增项")}
    </Button>
  </div>
);
