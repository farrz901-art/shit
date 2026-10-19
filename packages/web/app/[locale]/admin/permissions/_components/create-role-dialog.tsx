"use client";
// 新建角色弹框 (2026-06-17) v2 RBAC
// 字段: name (英文标识) + label_zh + label_en + 7 页面权限
// 设计决策:
// - name 只能英文/数字/下划线 (后端 zod 验, 前端简单 minLength=1 提示)
// - 默认所有权限 false, 用户主动勾选要启用的 (避免误授权)
// - 提交失败 → 显示错误, 保留用户输入 (不 reset)
// - 成功后 onCreated + onOpenChange(false), 调用方决定刷新数据
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { AppForm, AppField, AppSubmit } from "@/components/common/form";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { MatrixPage } from "./permissions-table";
import { createRole } from "@/lib/api/permissions";
import { useState } from "react";
import { useBoolean } from "react-use";
import { useTranslations } from "next-intl";

/**
 * 新建角色弹框组件
 *
 * 字段: name (英文标识) + label_zh + label_en + 7 页面权限.
 * 默认所有权限 false, 用户主动勾选要启用的 (避免误授权).
 * 提交失败 -> 显示错误, 保留用户输入 (不 reset).
 *
 * @param props - 组件属性
 * @param props.open - 弹框打开状态
 * @param props.onOpenChange - 打开状态变更回调 (关闭时清空表单)
 * @param props.onCreated - 创建成功后回调 (刷新角色列表)
 * @param props.pages - 可用页面权限列表
 * @client-bff
 */
export const CreateRoleDialog = ({
  open,
  onOpenChange,
  onCreated,
  pages,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
  pages: MatrixPage[];
}) => {
  const translate = useTranslations();
  const [permissions, setPermissions] = useState<Record<string, boolean>>({});
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useBoolean(false);

  const handleClose = (nextOpen: boolean) => {
    if (!nextOpen) {
      setPermissions({});
      setDialogError(null);
    }
    onOpenChange(nextOpen);
  };

  const handleSubmit = async (values: Record<string, unknown>) => {
    setDialogError(null);
    setSubmitting(true);
    try {
      await createRole({
        name: values.name as string,
        label_zh: values.label_zh as string,
        label_en: values.label_en as string,
        permissions,
      });
      onCreated();
      handleClose(false);
    } catch (error) {
      setDialogError(error instanceof Error ? error.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppDialog
      open={open}
      onOpenChange={handleClose}
      title={translate("新建角色")}
      maxWidth="md"
      dataTestid="create-role-dialog"
      error={dialogError}
      errorTestid="role-create-error"
    >
      <AppForm defaultValues={{ name: "", label_zh: "", label_en: "" }} onFinish={handleSubmit}>
        <AppField name="name" label={translate("角色名")} required placeholder="operator" />
        <AppField name="label_zh" label={translate("中文标签")} required placeholder="运营" />
        <AppField name="label_en" label={translate("英文标签")} required placeholder="Operator" />

        {/* permissions 网格保持独立 — 非标准控件 */}
        <div className="space-y-2">
          <Label className="eyebrow block">{translate("页面权限")}</Label>
          <div className="grid grid-cols-2 gap-2">
            {pages.map((page) => (
              <Label
                key={page.key}
                className="flex cursor-pointer items-center gap-2 rounded border border-border/40 px-2 py-1.5 text-sm hover:bg-muted/30"
              >
                <Checkbox
                  checked={Boolean(permissions[page.key])}
                  onCheckedChange={(checked) =>
                    setPermissions((prev) => ({ ...prev, [page.key]: Boolean(checked) }))
                  }
                  data-testid={`role-page-${page.key}`}
                />
                {translate(page.label_zh)}
              </Label>
            ))}
          </div>
        </div>

        <div className="flex gap-2 pt-2">
          <AppSubmit data-testid="role-submit" className="flex-1">
            {submitting ? translate("创建中…") : translate("创建")}
          </AppSubmit>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleClose(false)}
            data-testid="role-cancel"
          >
            {translate("取消")}
          </Button>
        </div>
      </AppForm>
    </AppDialog>
  );
};
