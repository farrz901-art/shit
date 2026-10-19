"use client";
// 字典审计日志抽屉 (2026-06-19 lookup module Task 9)
// 侧拉抽屉展示 audit_logs 里 action='dictionary.item.*' 且 dict_code + 可选 key 匹配的条目.
// 时间倒序, 显示 ts / actor_id / action / before → after diff / ip.
// 用 AppDrawer (项目封装, shadcn Sheet 包装).
import { type LookupAuditLogEntry, fetchAdminAuditLog } from "@/lib/api/lookups";
import { useEffect, useState } from "react";
import { useBoolean } from "react-use";
import { ApiError } from "@/lib/api/errors";
import { AppDrawer } from "@/components/common/drawer/app-drawer";
import { Badge } from "@/components/ui/badge";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { TWO, ZERO } from "@/const";
import { formatDateTime } from "@/lib/date";
import { ScrollText } from "lucide-react";
import { useTranslations } from "next-intl";

/** 字典审计日志抽屉属性 */
export interface DictAuditLogProps {
  /** 抽屉打开状态 */
  open: boolean;
  /** 打开状态变更回调 */
  onOpenChange: (open: boolean) => void;
  // 当前 dict_code (必填, 抽屉从父组件接住)
  dictCode: string;
  // 可选过滤: 打开时只显示某个 item 的历史 (DictList onAudit 传入)
  itemKey?: string | null;
}

/**
 * 渲染抽屉内容 (加载 / 空态 / 列表)
 * @param loading - 是否加载中
 * @param entries - 审计日志条目列表
 * @param translate - i18n 翻译函数
 * @returns React 节点
 */
const renderDrawerContent = (
  loading: boolean,
  entries: LookupAuditLogEntry[],
  translate: ReturnType<typeof useTranslations>,
): React.ReactNode => {
  if (loading) {
    return <p className="text-sm text-muted-foreground">{translate("加载中…")}</p>;
  }
  if (entries.length === ZERO) {
    return (
      <DataEmpty
        icon={ScrollText}
        title={translate("暂无历史")}
        description={translate("还没有任何审计记录")}
      />
    );
  }
  return (
    <ul className="space-y-3" data-testid="audit-entries">
      {entries.map((entry) => (
        <li
          key={entry.id}
          className="space-y-1.5 rounded-md border border-border/40 bg-muted/10 p-3"
          data-testid={`audit-entry-${entry.id}`}
        >
          <div className="flex items-center justify-between">
            <Badge variant="secondary">{entry.action}</Badge>
            <span className="num text-xs text-muted-foreground">
              {formatDateTime(entry.ts, "zh-CN")}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            {translate("操作人")}: user#{entry.actor_id}
            {entry.ip && ` · ${entry.ip}`}
          </div>
          {entry.before && (
            <details className="text-xs">
              <summary className="cursor-pointer text-muted-foreground">before</summary>
              <pre className="mt-1 overflow-x-auto rounded bg-muted/30 p-2 font-mono">
                {JSON.stringify(entry.before, null, TWO)}
              </pre>
            </details>
          )}
          {entry.after && (
            <details className="text-xs">
              <summary className="cursor-pointer text-muted-foreground">after</summary>
              <pre className="mt-1 overflow-x-auto rounded bg-muted/30 p-2 font-mono">
                {JSON.stringify(entry.after, null, TWO)}
              </pre>
            </details>
          )}
        </li>
      ))}
    </ul>
  );
};

/**
 * 字典审计日志抽屉组件
 *
 * 侧拉抽屉展示 audit_logs 里 action='dictionary.item.*' 且 dict_code + 可选 key 匹配的条目.
 * 时间倒序, 显示 ts / actor_id / action / before → after diff / ip.
 *
 * @param props - 组件属性
 * @param props.open - 抽屉打开状态
 * @param props.onOpenChange - 打开状态变更回调
 * @param props.dictCode - 当前字典编码 (必填)
 * @param props.itemKey - 可选过滤, 只显示某个 item 的历史
 * @client-bff
 */
export const DictAuditLog = ({ open, onOpenChange, dictCode, itemKey }: DictAuditLogProps) => {
  const translate = useTranslations();
  const [entries, setEntries] = useState<LookupAuditLogEntry[]>([]);
  const [loading, setLoading] = useBoolean(false);
  const [err, setErr] = useState<string | null>(null);

  // 打开时拉一次 (后端已按时间倒序返).
  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErr(null);
    fetchAdminAuditLog(dictCode, itemKey ?? undefined)
      .then((data) => {
        if (!cancelled) {
          setEntries(data);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setErr(error instanceof ApiError ? error.message : translate("加载历史失败"));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, dictCode, itemKey, translate]);

  const drawerTitle = itemKey
    ? `${dictCode} / ${itemKey} - ${translate("审计历史")}`
    : `${dictCode} - ${translate("审计历史")}`;

  const drawerContent = renderDrawerContent(loading, entries, translate);

  return (
    <AppDrawer
      open={open}
      onOpenChange={onOpenChange}
      title={drawerTitle}
      description="所有 dictionary.item.* 操作, 时间倒序"
      maxWidth="640px"
    >
      {err && <ErrorBanner variant="destructive" description={err} />}
      {drawerContent}
    </AppDrawer>
  );
};
