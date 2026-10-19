// CreateFieldDialog (2026-06-29 refactor)
// 抽自 profile-fields/page.tsx 的新增字段 AppDialog, 表单字段跟原内联 JSX 完全一致

"use client";

import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { UseMutationResult } from "@tanstack/react-query";
import type { ProfileFieldsFormState } from "../_hooks/use-profile-fields-handlers";
import { FieldTypeSelect } from "./field-type-select";

/** 创建字段的 mutation 类型 */
type CreateMutation = UseMutationResult<unknown, Error, Record<string, unknown>, unknown>;

/**
 * 新增字段弹框组件 — 表单字段跟原内联 JSX 完全一致
 * @param props.createForm - 创建表单状态
 * @param props.createMutation - 创建字段 mutation
 * @param props.handleCreate - 创建提交回调
 * @param props.onCancel - 取消关闭回调
 * @param props.setCreateForm - 更新创建表单状态
 * @param props.showCreateDialog - 弹框显示状态
 * @param props.translate - i18n 翻译函数
 * @returns 新增字段弹框
 * @client-bff
 */
export const CreateFieldDialog = ({
  createForm,
  createMutation,
  handleCreate,
  onCancel,
  setCreateForm,
  showCreateDialog,
  translate,
}: {
  createForm: ProfileFieldsFormState;
  createMutation: CreateMutation;
  handleCreate: () => void;
  onCancel: () => void;
  setCreateForm: (updater: (prev: ProfileFieldsFormState) => ProfileFieldsFormState) => void;
  showCreateDialog: boolean;
  translate: (key: string) => string;
}) => (
  <AppDialog
    footer={
      <>
        <Button onClick={onCancel} variant="outline">
          {translate("取消")}
        </Button>
        <Button disabled={createMutation.isPending} onClick={handleCreate}>
          {translate("创建")}
        </Button>
      </>
    }
    onOpenChange={(open) => {
      if (!open) {
        onCancel();
      }
    }}
    open={showCreateDialog}
    title={translate("新增字段")}
  >
    <div className="space-y-4 py-4">
      <div className="space-y-2">
        <Label>{translate("编码")}</Label>
        <Input
          onChange={(_event) =>
            setCreateForm((prev: ProfileFieldsFormState) => ({
              ...prev,
              code: _event.target.value,
            }))
          }
          placeholder="field_code"
          value={createForm.code}
        />
      </div>
      <div className="space-y-2">
        <Label>{translate("标签")}</Label>
        <Input
          onChange={(_event) =>
            setCreateForm((prev: ProfileFieldsFormState) => ({
              ...prev,
              label: _event.target.value,
            }))
          }
          value={createForm.label}
        />
      </div>
      <div className="space-y-2">
        <Label>{translate("类型")}</Label>
        <FieldTypeSelect
          onChange={(val) =>
            setCreateForm((prev: ProfileFieldsFormState) => ({
              ...prev,
              field_type: val,
            }))
          }
          value={createForm.field_type}
        />
      </div>
      <div className="space-y-2">
        <Label>{translate("提取提示词")}</Label>
        <Input
          onChange={(_ev) =>
            setCreateForm((prev: ProfileFieldsFormState) => ({
              ...prev,
              extraction_prompt: _ev.target.value,
            }))
          }
          value={createForm.extraction_prompt}
        />
      </div>
    </div>
  </AppDialog>
);
