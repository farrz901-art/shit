// useProfileFieldsHandlers (2026-06-29 refactor)
// 抽自 profile-fields/page.tsx 的 5 个 handler + form state, 主组件只管 UI state

"use client";

import { useState } from "react";
import {
  useCreateFieldConfig,
  useUpdateFieldConfig,
} from "@/app/[locale]/buyers/_lib/buyer-profile/hooks";
import type { ProfileFieldConfig } from "@/app/[locale]/buyers/_lib/buyer-profile/types";

/** 默认排序值 */
const DEFAULT_SORT_ORDER = 0;

/** 字段表单状态 */
export interface ProfileFieldsFormState {
  /** 字段编码 */
  code: string;
  /** 提取提示词 */
  extraction_prompt: string;
  /** 字段类型 */
  field_type: string;
  /** 字段标签 */
  label: string;
}

/** 创建空表单状态 */
const emptyForm = (): ProfileFieldsFormState => ({
  code: "",
  extraction_prompt: "",
  field_type: "text",
  label: "",
});

// oxlint-disable-next-line max-statements -- handlers 集中管理, 暂不拆分
/** 字段管理 handler hook
 * @returns 表单状态 + 各类操作 handler
 * @client-bff
 */
export const useProfileFieldsHandlers = () => {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 新增对话框
  const [createForm, setCreateForm] = useState<ProfileFieldsFormState>(emptyForm);

  // 编辑对话框
  const [editTarget, setEditTarget] = useState<ProfileFieldConfig | null>(null);
  const [editForm, setEditForm] = useState<ProfileFieldsFormState>(emptyForm);

  // 停用/激活确认
  const [toggleTarget, setToggleTarget] = useState<ProfileFieldConfig | null>(null);

  const createMutation = useCreateFieldConfig();
  const updateMutation = useUpdateFieldConfig();

  /** 执行创建字段, 成功后重置表单 */
  const handleCreate = () => {
    createMutation.mutate(
      {
        code: createForm.code,
        extraction_prompt: createForm.extraction_prompt || undefined,
        field_type: createForm.field_type,
        label: createForm.label,
        sort_order: DEFAULT_SORT_ORDER,
      },
      {
        onError: (err) => {
          setErrorMessage(err instanceof Error ? err.message : "出错了");
        },
        onSuccess: () => {
          setCreateForm(emptyForm());
        },
      },
    );
  };

  /**
   * 设置编辑目标并预填编辑表单
   * @param cfg - 要编辑的字段配置
   */
  const handleEdit = (cfg: ProfileFieldConfig) => {
    setEditTarget(cfg);
    setEditForm({
      code: cfg.code,
      extraction_prompt: cfg.extraction_prompt ?? "",
      field_type: cfg.field_type,
      label: cfg.label,
    });
  };

  /** 执行编辑保存, 成功后清空编辑目标 */
  const handleEditSave = () => {
    if (!editTarget) {
      return;
    }
    updateMutation.mutate(
      {
        code: editTarget.code,
        label: editForm.label || undefined,
        field_type: editForm.field_type || undefined,
        extraction_prompt: editForm.extraction_prompt || undefined,
      },
      {
        onError: (err) => {
          setErrorMessage(err instanceof Error ? err.message : "出错了");
        },
        onSuccess: () => {
          setEditTarget(null);
        },
      },
    );
  };

  /**
   * 设置停用/激活确认目标
   * @param cfg - 要切换激活状态的字段配置
   */
  const handleToggleActive = (cfg: ProfileFieldConfig) => {
    setToggleTarget(cfg);
  };

  /** 执行停用/激活确认, 成功后清空确认目标 */
  const handleToggleConfirm = () => {
    if (!toggleTarget) {
      return;
    }
    updateMutation.mutate(
      { code: toggleTarget.code, is_active: !toggleTarget.is_active },
      {
        onError: (err) => {
          setErrorMessage(err instanceof Error ? err.message : "出错了");
        },
        onSuccess: () => {
          setToggleTarget(null);
        },
      },
    );
  };

  return {
    createForm,
    createMutation,
    editForm,
    editTarget,
    errorMessage,
    handleCreate,
    handleEdit,
    handleEditSave,
    handleToggleActive,
    handleToggleConfirm,
    setCreateForm,
    setEditForm,
    setErrorMessage,
    setEditTarget,
    setToggleTarget,
    toggleTarget,
    updateMutation,
  };
};
