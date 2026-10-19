// EditFieldDialog (2026-06-29 refactor)
// 抽自 profile-fields/page.tsx 的编辑字段 AppDialog, 表单字段跟原内联 JSX 完全一致

"use client";

import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { UseMutationResult } from "@tanstack/react-query";
import type { ProfileFieldsFormState } from "../_hooks/use-profile-fields-handlers";
import { FieldTypeSelect } from "./field-type-select";

/** 更新字段的 mutation 类型 */
type UpdateMutation = UseMutationResult<
  unknown,
  Error,
  { code: string } & Record<string, unknown>,
  unknown
>;

/**
 * 编辑字段弹框组件 — 表单字段跟原内联 JSX 完全一致
 * @param props.editForm - 编辑表单状态
 * @param props.handleEditSave - 保存编辑回调
 * @param props.onCancel - 取消关闭回调
 * @param props.setEditForm - 更新编辑表单状态
 * @param props.showEditDialog - 弹框显示状态
 * @param props.translate - i18n 翻译函数
 * @param props.updateMutation - 更新字段 mutation
 * @returns 编辑字段弹框
 * @client-bff
 */
export const EditFieldDialog = ({
  editForm,
  handleEditSave,
  onCancel,
  setEditForm,
  showEditDialog,
  translate,
  updateMutation,
}: {
  editForm: ProfileFieldsFormState;
  handleEditSave: () => void;
  onCancel: () => void;
  setEditForm: (updater: (prev: ProfileFieldsFormState) => ProfileFieldsFormState) => void;
  showEditDialog: boolean;
  translate: (key: string) => string;
  updateMutation: UpdateMutation;
}) => (
  <AppDialog
    footer={
      <>
        <Button onClick={onCancel} variant="outline">
          {translate("取消")}
        </Button>
        <Button disabled={updateMutation.isPending} onClick={handleEditSave}>
          {translate("保存")}
        </Button>
      </>
    }
    onOpenChange={(open) => {
      if (!open) {
        onCancel();
      }
    }}
    open={showEditDialog}
    title={translate("编辑字段")}
  >
    <div className="space-y-4 py-4">
      <div className="space-y-2">
        <Label>{translate("标签")}</Label>
        <Input
          onChange={(_event) =>
            setEditForm((prev: ProfileFieldsFormState) => ({ ...prev, label: _event.target.value }))
          }
          value={editForm.label}
        />
      </div>
      <div className="space-y-2">
        <Label>{translate("类型")}</Label>
        <FieldTypeSelect
          onChange={(val) =>
            setEditForm((prev: ProfileFieldsFormState) => ({
              ...prev,
              field_type: val,
            }))
          }
          value={editForm.field_type}
        />
      </div>
      <div className="space-y-2">
        <Label>{translate("提取提示词")}</Label>
        <Input
          onChange={(_ev) =>
            setEditForm((prev: ProfileFieldsFormState) => ({
              ...prev,
              extraction_prompt: _ev.target.value,
            }))
          }
          value={editForm.extraction_prompt}
        />
      </div>
    </div>
  </AppDialog>
);
