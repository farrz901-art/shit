"use client";
// 新增字典项弹框 (2026-06-19 lookup module Task 9)
// 字段: key / label_zh / label_en / sort / is_active / description / metadata_json.
// 提交调 fetchAdminCreateItem, 成功后由父组件 onCreated() 决定刷新数据 (关 dialog + 刷新 items).
// (2026-06-25) 迁移到 AppForm, 用 form.Field 管理 is_active 和 metadata_json (Task 6)
import { AppField, AppForm, AppSubmit, useFormCtx } from "@/components/common/form";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { getErrorMessage as normalizeErrorMessage } from "@/lib/api/errors";
import { type LookupItemCreateInput } from "@/lib/api/lookups";
import { useTranslations } from "next-intl";
import { useState } from "react";

/** 新增字典项弹框属性 */
export interface DictItemCreateDialogProps {
  /** 弹框打开状态 */
  open: boolean;
  /** 打开状态变更回调 */
  onOpenChange: (open: boolean) => void;
  /** 创建成功后回调 (刷新列表) */
  onCreated: () => void;
  /** 提交函数: 父组件接住后调 fetchAdminCreateItem 并刷新 query cache */
  onSubmit: (payload: LookupItemCreateInput) => Promise<void>;
}

/**
 * 默认 AppForm 初始值
 * @shared
 */
const EMPTY_VALUES: Record<string, unknown> = {
  description: "",
  is_active: true,
  key: "",
  label_en: "",
  label_zh: "",
  metadata_json: "",
  sort: 0,
};

/**
 * 业务错误归一: ApiError/NetworkError/Error 走公共 getErrorMessage, 其余 (罕见) 用 i18n 兜底
 * @param err - 原始错误对象
 * @param translate - i18n 翻译函数
 * @returns 归一后的错误信息字符串
 * @shared
 */
const getErrorMessage = (err: unknown, translate: (key: string) => string): string => {
  if (err instanceof Error) {
    return normalizeErrorMessage(err);
  }
  return translate("新增失败");
};

/**
 * 解析 metadata_json: 空字符串当作 null, 否则要求合法 JSON
 * @param raw - 原始值
 * @returns 解析后的 Record, 空串时返回 null
 * @shared
 */
const parseMetadata = (raw: unknown): Record<string, unknown> | null => {
  if (typeof raw !== "string" || raw.trim() === "") {
    return null;
  }
  return JSON.parse(raw) as Record<string, unknown>;
};

/**
 * 从 AppForm values 构造提交 payload. metadata_json 非法时返 null 并报错
 * @param values - 表单原始值
 * @param translate - i18n 翻译函数
 * @param onError - 报错回调
 * @returns 构造后的 payload, 非法时返回 null
 * @shared
 */
const tryBuildPayload = (
  values: Record<string, unknown>,
  translate: (key: string) => string,
  onError: (msg: string) => void,
): LookupItemCreateInput | null => {
  try {
    return {
      key: (values.key as string).trim(),
      label_zh: (values.label_zh as string).trim(),
      label_en: (values.label_en as string).trim(),
      sort: values.sort as number,
      description: (values.description as string)?.trim() || null,
      is_active: values.is_active as boolean,
      metadata_json: parseMetadata(values.metadata_json),
    };
  } catch {
    onError(translate("metadata_json 不是合法 JSON"));
    return null;
  }
};

/**
 * metadata_json textarea 用 form.Field 原生（非标准控件）
 * @client-bff
 */
const MetadataField = () => {
  const { form } = useFormCtx();
  const { Field } = form;
  return (
    <Field name="metadata_json" mode="value">
      {(field: { handleChange: (value: string) => void; state: { value: unknown } }) => (
        <div className="space-y-1.5">
          <Label className="eyebrow block" htmlFor="create-metadata">
            metadata_json
          </Label>
          <textarea
            id="create-metadata"
            value={(field.state.value as string) ?? ""}
            onChange={(ev: React.ChangeEvent<HTMLTextAreaElement>) =>
              field.handleChange(ev.target.value)
            }
            placeholder='{"color": "blue"}'
            data-testid="create-metadata-input"
            className="border-input bg-transparent w-full rounded-md border px-3 py-2 font-mono text-xs"
            rows={3}
          />
        </div>
      )}
    </Field>
  );
};

/**
 * is_active Checkbox 用 form.Field 原生（非标准控件）
 * @client-bff
 */
const ActiveField = () => {
  const translate = useTranslations();
  const { form } = useFormCtx();
  const { Field } = form;
  return (
    <Label className="flex cursor-pointer items-center gap-2 text-sm">
      <Field name="is_active" mode="value">
        {(field: { handleChange: (value: boolean) => void; state: { value: unknown } }) => (
          <Checkbox
            checked={Boolean(field.state.value)}
            onCheckedChange={(checked) => field.handleChange(checked === true)}
            data-testid="create-is-active-input"
          />
        )}
      </Field>
      {translate("启用")}
    </Label>
  );
};

/**
 * 新增字典项弹框组件
 *
 * 字段: key / label_zh / label_en / sort / is_active / description / metadata_json.
 * 提交调 fetchAdminCreateItem, 成功后由父组件 onCreated() 决定刷新数据.
 *
 * @param props - 组件属性
 * @param props.open - 弹框打开状态
 * @param props.onOpenChange - 打开状态变更回调
 * @param props.onCreated - 创建成功后刷新列表回调
 * @param props.onSubmit - 提交流程 (调 fetchAdminCreateItem)
 * @client-bff
 */
export const DictItemCreateDialog = ({
  open,
  onOpenChange,
  onCreated,
  onSubmit,
}: DictItemCreateDialogProps) => {
  const translate = useTranslations();
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleClose = (next: boolean) => {
    if (!next) {
      setSubmitError(null);
    }
    onOpenChange(next);
  };

  const handleSubmit = async (values: Record<string, unknown>) => {
    setSubmitError(null);
    const payload = tryBuildPayload(values, translate, setSubmitError);
    if (!payload) {
      return;
    }
    try {
      await onSubmit(payload);
      onCreated();
      handleClose(false);
    } catch (error) {
      setSubmitError(getErrorMessage(error, translate));
    }
  };

  return (
    <AppDialog
      open={open}
      onOpenChange={handleClose}
      title={translate("新增字典项")}
      maxWidth="md"
      dataTestid="dict-item-create-dialog"
      error={submitError}
      errorTestid="dict-item-create-error"
    >
      <AppForm defaultValues={EMPTY_VALUES} onFinish={handleSubmit}>
        <AppField name="key" label="key" required placeholder="pending" />
        <AppField name="label_zh" label={translate("中文标签")} required placeholder="待审核" />
        <AppField name="label_en" label={translate("英文标签")} required placeholder="Pending" />
        <AppField name="sort" label={translate("排序")} type="number" />
        <AppField
          name="description"
          label={translate("描述")}
          placeholder={translate("可选, 说明这个字典项用途")}
        />

        <MetadataField />
        <ActiveField />

        <div className="flex gap-2 pt-2">
          <AppSubmit data-testid="dict-item-create-submit" className="flex-1">
            {translate("新增")}
          </AppSubmit>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleClose(false)}
            data-testid="dict-item-create-cancel"
          >
            {translate("取消")}
          </Button>
        </div>
      </AppForm>
    </AppDialog>
  );
};
