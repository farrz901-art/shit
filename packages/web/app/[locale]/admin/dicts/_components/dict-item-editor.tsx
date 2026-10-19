"use client";
// 字典项行内编辑表单 (2026-06-19 lookup module Task 9)
// DictList 行内 "编辑" 按钮触发, 受控表单改 label_zh/label_en/sort/is_active,
// 保存调 onPatch (DictList 接 onPatch → fetchAdminPatchItem); 取消还原.
import { type LookupItem, type LookupItemPatchInput } from "@/lib/api/lookups";
import { ApiError } from "@/lib/api/errors";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { useBoolean } from "react-use";
import { useTranslations } from "next-intl";

/** 字典项行内编辑表单属性 */
export interface DictItemEditorProps {
  /** 正在编辑的字典项 (从 DictList 传入) */
  item: LookupItem;
  /** 保存回调: DictList 接住后调 fetchAdminPatchItem */
  onPatch: (key: string, payload: LookupItemPatchInput) => Promise<void>;
  /** 取消回调: DictList 清掉 editingKey state */
  onCancel: () => void;
}

/**
 * 编辑表单初始值: 用 item 当前值, 改完调 onPatch 时只把 changed 字段带上.
 * @param item - 字典项
 * @returns 初始表单值
 * @shared
 */
const initialValues = (item: LookupItem) => ({
  is_active: item.is_active,
  label_en: item.label_en,
  label_zh: item.label_zh,
  sort: item.sort,
});

/**
 * 计算 changed 字段: 跟 item 当前值对比, 只送改过的 (减少后端无意义写入).
 * @param values - 当前表单值
 * @param item - 原始字典项
 * @returns 只包含变更字段的 patch payload
 * @shared
 */
const buildPatchPayload = (
  values: ReturnType<typeof initialValues>,
  item: LookupItem,
): LookupItemPatchInput => {
  const payload: LookupItemPatchInput = {};
  if (values.label_zh !== item.label_zh) {
    payload.label_zh = values.label_zh;
  }
  if (values.label_en !== item.label_en) {
    payload.label_en = values.label_en;
  }
  if (values.sort !== item.sort) {
    payload.sort = values.sort;
  }
  if (values.is_active !== item.is_active) {
    payload.is_active = values.is_active;
  }
  return payload;
};

/**
 * 字典项行内编辑表单组件
 *
 * DictList 行内 "编辑" 按钮触发, 受控表单改 label_zh/label_en/sort/is_active,
 * 保存调 onPatch (DictList 接 onPatch -> fetchAdminPatchItem); 取消还原.
 *
 * @param props - 组件属性
 * @param props.item - 正在编辑的字典项
 * @param props.onPatch - 保存回调
 * @param props.onCancel - 取消回调
 * @param props.submitting - 提交中状态
 * @client-bff
 */
export const DictItemEditor = ({ item, onPatch, onCancel }: DictItemEditorProps) => {
  const translate = useTranslations();
  const [values, setValues] = useState(() => initialValues(item));
  const [submitting, setSubmitting] = useBoolean(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      const payload = buildPatchPayload(values, item);
      await onPatch(item.key, payload);
    } catch (error) {
      setSubmitError(error instanceof ApiError ? error.message : translate("保存失败"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-center gap-3 rounded border border-border/40 bg-muted/20 p-3"
      data-testid={`item-editor-${item.key}`}
    >
      <span className="num font-mono text-sm text-muted-foreground">{item.key}</span>

      <div className="flex items-center gap-1.5">
        <Label className="text-xs text-muted-foreground">{translate("中文")}</Label>
        <Input
          value={values.label_zh}
          onChange={(evt) => setValues({ ...values, label_zh: evt.target.value })}
          required
          data-testid="editor-label-zh"
          className="h-8 w-32"
        />
      </div>

      <div className="flex items-center gap-1.5">
        <Label className="text-xs text-muted-foreground">{translate("英文")}</Label>
        <Input
          value={values.label_en}
          onChange={(evt) => setValues({ ...values, label_en: evt.target.value })}
          required
          data-testid="editor-label-en"
          className="h-8 w-32"
        />
      </div>

      <div className="flex items-center gap-1.5">
        <Label className="text-xs text-muted-foreground">{translate("排序")}</Label>
        <Input
          type="number"
          value={values.sort}
          onChange={(evt) => setValues({ ...values, sort: Number(evt.target.value) })}
          data-testid="editor-sort"
          className="h-8 w-16"
        />
      </div>

      <Label className="flex items-center gap-1.5 text-xs">
        <Checkbox
          checked={values.is_active}
          onCheckedChange={(checked) => setValues({ ...values, is_active: Boolean(checked) })}
          data-testid="editor-is-active"
        />
        {translate("启用")}
      </Label>

      {submitError && (
        <span className="text-xs text-destructive" data-testid="editor-error">
          {submitError}
        </span>
      )}

      <div className="ml-auto flex gap-1.5">
        <Button type="submit" size="sm" disabled={submitting} data-testid="editor-save">
          {submitting ? translate("保存中…") : translate("保存")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onCancel}
          disabled={submitting}
          data-testid="editor-cancel"
        >
          {translate("取消")}
        </Button>
      </div>
    </form>
  );
};
