/* eslint-disable max-statements -- dicts admin client with toast handlers */
"use client";
// 字典管理入口 (2026-06-19 lookup module Task 9 / spec §5.6)
// 顶部: ReadonlyBanner
// 中部: dict_code 下拉 + DictList + 右上 "新增项" / "查看字典历史" 按钮
// 弹层: DictItemCreateDialog (新增) / DictItemDeleteDialog (删除, 含二次确认 + token 申请) / DictAuditLog (抽屉)
// 数据流: useAllLookups() 拉字典概要 → 选 code → useLookup(code) 拉 items → DictList 触发回调
// (2026-06-19) ReadonlyBanner 的 readonly 状态本地 useState 默认 false, 真实状态后端 system-info 端点 (T6) 未实现, 留 hook 点.
import {
  type LookupItem,
  type LookupItemCreateInput,
  type LookupItemPatchInput,
  fetchAdminCreateItem,
  fetchAdminDeleteItem,
  fetchAdminPatchItem,
} from "@/lib/api/lookups";
import { useAllLookups, useLookup } from "@/lib/hooks/use-lookup";
import { usePermissionsStore } from "@/lib/hooks/use-permissions";
import { ApiError } from "@/lib/api/errors";
import { AppSelect } from "@/components/common/input/app-select";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { DictAuditLog } from "./dict-audit-log";
import { DictItemCreateDialog } from "./dict-item-create-dialog";
import { DictItemDeleteDialog } from "./dict-item-delete-dialog";
import { DictList } from "./dict-list";
import { DictPageActions } from "./dict-page-actions";
import { ErrorBanner } from "@/components/common/feedback/app-error-banner";
import { PageGuard } from "@/components/page-guard";
import { PageHero } from "@/components/common/navigation/app-page-hero";
import { ReadonlyBanner } from "./readonly-banner";
import { toast } from "sonner";
import { useState } from "react";
import { useTranslations } from "next-intl";
// === 常量 ===
/** 数组首个元素的索引 (0) */
const FIRST_INDEX = 0;
/** 默认计数 (用于 fallback 默认值) */
const DEFAULT_COUNT = 0;

// === 字典内容渲染: 列表 / 加载中 / 空态 ===

/** 字典内容区域: 根据 activeCode 和 items 渲染列表/加载中/空态
 * @param activeCode - 当前选中的字典代码, 空字符串时表示未选择
 * @param items - 字典项列表
 * @param readonly - 是否只读
 * @param translate - i18n 翻译函数
 * @param isLoading - 是否正在加载字典概要
 * @param onPatch - 编辑字典项回调
 * @param onAskDelete - 删除字典项回调
 * @param onAskAudit - 查看字典项审计日志回调
 * @returns 内容区域 JSX
 */
const DictPageContent = ({
  activeCode,
  items,
  readonly,
  translate,
  isLoading,
  onPatch,
  onAskDelete,
  onAskAudit,
}: {
  activeCode: string;
  items: LookupItem[];
  readonly: boolean;
  translate: (key: string, values?: Record<string, string | number | Date>) => string;
  isLoading: boolean;
  onPatch: (key: string, payload: LookupItemPatchInput) => Promise<void>;
  onAskDelete: (item: LookupItem | null) => void;
  onAskAudit: (item: LookupItem) => void;
}) => {
  if (activeCode) {
    return (
      <DictList
        items={items}
        readonly={readonly}
        onPatch={onPatch}
        onAskDelete={onAskDelete}
        onAskAudit={onAskAudit}
      />
    );
  }
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">{translate("加载中…")}</p>;
  }
  return <DataEmpty title={translate("暂无字典")} variant="page" />;
};

// === 操作处理函数 (模块级别, 避免组件内 max-statements 超标) ===

/** 操作处理函数的依赖注入
 * @property activeCode - 当前选中的字典代码
 * @property refresh - 刷新字典项列表
 * @property setError - 设置错误信息
 * @property translate - i18n 翻译函数
 */
interface AdminDeps {
  activeCode: string;
  refresh: () => Promise<unknown>;
  setError: (msg: string | null) => void;
  translate: (key: string, values?: Record<string, string | number | Date>) => string;
}

/** 从异常中提取错误消息, 非 ApiError 使用 fallback
 * @param cause - 捕获的异常
 * @param fallback - 默认错误消息
 * @returns 错误消息字符串
 */
const extractErrorMsg = (cause: unknown, fallback: string): string =>
  cause instanceof ApiError ? cause.message : fallback;

/** 执行操作并显示成功/失败 toast
 * @param action - 要执行的操作 (异步)
 * @param messages - 成功和 fallback 消息配置
 * @param onError - 错误时的回调
 * @returns 操作是否成功
 */
const callWithToast = async <TResult,>(
  action: () => Promise<TResult>,
  messages: { success: string; fallback: string },
  onError: (msg: string) => void,
): Promise<boolean> => {
  try {
    await action();
    toast.success(messages.success);
    return true;
  } catch (error) {
    const msg = extractErrorMsg(error, messages.fallback);
    onError(msg);
    toast.error(msg);
    return false;
  }
};

/** 编辑字典项: 调用 patch API 并刷新列表
 * @param deps - 操作依赖注入
 * @param key - 字典项 key
 * @param payload - 编辑 payload
 */
const doPatch = async (
  deps: AdminDeps,
  key: string,
  payload: LookupItemPatchInput,
): Promise<void> => {
  const { activeCode, refresh, setError, translate } = deps;
  setError(null);
  const ok = await callWithToast(
    () => fetchAdminPatchItem(activeCode, key, payload),
    { fallback: translate("保存失败"), success: translate("已保存") },
    setError,
  );
  if (ok) {
    await refresh();
    // (2026-07-02 nav spec §6) 改 page_key 后清权限 store 强制 RSC 重 hydrate
    if (activeCode === "page_key") {
      usePermissionsStore.getState().reset();
    }
  }
};

/** 删除字典项: 调用 delete API 并刷新列表
 * @param deps - 操作依赖注入 (含 deletingItem / setDeletingItem)
 * @param token - 删除确认 token
 */
const doDelete = async (
  deps: AdminDeps & {
    deletingItem: LookupItem | null;
    setDeletingItem: (item: LookupItem | null) => void;
  },
  token: string,
): Promise<void> => {
  const { activeCode, refresh, setError, translate, deletingItem, setDeletingItem } = deps;
  if (!deletingItem) {
    return;
  }
  setError(null);
  const ok = await callWithToast(
    () => fetchAdminDeleteItem(activeCode, deletingItem.key, token),
    { fallback: translate("删除失败"), success: translate("已删除") },
    setError,
  );
  if (ok) {
    setDeletingItem(null);
    await refresh();
  }
};

/** 新增字典项: 调用 create API 并刷新列表, 出错时抛异常让调用方处理
 * @param deps - 操作依赖注入
 * @param payload - 创建 payload
 * @param onError - 错误回调
 */
const doCreate = async (
  deps: AdminDeps,
  payload: LookupItemCreateInput,
  onError: (msg: string) => void,
): Promise<void> => {
  const { activeCode, refresh, setError, translate } = deps;
  setError(null);
  try {
    await fetchAdminCreateItem(activeCode, payload);
    toast.success(translate("已新增"));
    await refresh();
    // (2026-07-02) 新增 page_key 后清权限 store
    if (activeCode === "page_key") {
      usePermissionsStore.getState().reset();
    }
  } catch (error) {
    const msg = extractErrorMsg(error, translate("新增失败"));
    setError(msg);
    onError(msg);
    throw error;
  }
};

// === 页面组件 ===

/** 字典管理页面客户端组件: 字典选择/列表/新增/编辑/删除/审计日志
 * @param role - 当前用户角色
 * @param allowed - 用户被授权的 page_key 列表
 * @returns 字典管理页面 JSX
 * @client-bff
 */
export const AdminDictsClient = ({ role, allowed }: { role: string; allowed: string[] }) => {
  const translate = useTranslations();
  const summaries = useAllLookups();
  const [dictCode, setDictCode] = useState<string>("");
  const activeCode = dictCode || (summaries.data?.[FIRST_INDEX]?.code ?? "");
  const [dialogOpen, setDialogOpen] = useState({
    audit: false,
    auditKey: null as string | null,
    create: false,
  });
  const [deletingItem, setDeletingItem] = useState<LookupItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { items, refresh } = useLookup(activeCode, { onlyActive: false });

  const handlers = {
    create: (payload: LookupItemCreateInput) =>
      doCreate({ activeCode, refresh, setError, translate }, payload, (msg) => setError(msg)),
    deleteWithToken: (token: string) =>
      doDelete({ activeCode, deletingItem, refresh, setDeletingItem, setError, translate }, token),
    patch: (key: string, payload: LookupItemPatchInput) =>
      doPatch({ activeCode, refresh, setError, translate }, key, payload),
  };

  return (
    <PageGuard pageKey="admin" role={role} allowed={allowed}>
      <div className="space-y-6" data-testid="admin-dicts-page">
        <PageHero
          eyebrow="rbac"
          title={translate("字典管理")}
          actions={
            <DictPageActions
              onOpenAudit={() => {
                setDialogOpen((prev) => ({ ...prev, audit: true }));
              }}
              onOpenCreate={() => setDialogOpen((prev) => ({ ...prev, create: true }))}
              translate={translate}
            />
          }
        />

        <ReadonlyBanner
          readonly={false}
          dictsCount={summaries.data?.length ?? DEFAULT_COUNT}
          readonlyText={translate("DICTIONARY_READONLY 已开启")}
          writableText={translate("字典可正常编辑")}
        />

        {error && <ErrorBanner variant="destructive" description={error} dataTestid="dict-error" />}

        <div className="flex flex-wrap items-center gap-3">
          <span className="eyebrow text-sm">{translate("选择字典")}</span>
          <AppSelect
            options={(summaries.data ?? []).map((summary) => ({
              label: `${summary.label_zh} / ${summary.label_en} (${summary.code})`,
              value: summary.code,
            }))}
            value={activeCode}
            onChange={setDictCode}
            placeholder={translate("选择字典")}
            dataTestid="dict-code-select"
            className="w-72"
            disabled={summaries.isLoading}
          />
          {activeCode && (
            <span className="num text-xs text-muted-foreground">
              {translate("共 {val} 项", { val: items.length })}
            </span>
          )}
        </div>

        <DictPageContent
          activeCode={activeCode}
          items={items}
          readonly={false}
          translate={translate}
          isLoading={summaries.isLoading}
          onPatch={handlers.patch}
          onAskDelete={setDeletingItem}
          onAskAudit={(item: LookupItem) => {
            setDialogOpen((prev) => ({ ...prev, audit: true, auditKey: item.key }));
          }}
        />

        <DictItemCreateDialog
          open={dialogOpen.create}
          onOpenChange={(open) => setDialogOpen((prev) => ({ ...prev, create: open }))}
          onCreated={() => {
            void refresh();
          }}
          onSubmit={handlers.create}
        />

        <DictItemDeleteDialog
          open={Boolean(deletingItem)}
          onOpenChange={(open) => !open && setDeletingItem(null)}
          dictCode={activeCode}
          itemKey={deletingItem?.key ?? null}
          itemLabel={deletingItem?.label_zh ?? null}
          onConfirm={handlers.deleteWithToken}
        />

        <DictAuditLog
          open={dialogOpen.audit}
          onOpenChange={(open) => setDialogOpen((prev) => ({ ...prev, audit: open }))}
          dictCode={activeCode}
          itemKey={dialogOpen.auditKey}
        />
      </div>
    </PageGuard>
  );
};
