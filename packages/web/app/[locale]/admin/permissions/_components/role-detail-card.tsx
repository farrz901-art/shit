"use client";
// RoleDetailCard — 选中 role 后下方显示元信息 + 操作
// Linear/Stripe 风格: 信息按列横排, 操作放右上角 dropdown
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MoreHorizontal, Pencil, Shield, Trash2, User } from "lucide-react";
import { AppDropdownMenu } from "@/components/common/input/app-dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { RoleListItem } from "./permissions-table";
import { useTranslations } from "next-intl";

/** 角色详情卡片属性 */
export interface RoleDetailCardProps {
  /** 角色详情数据 (含 user_count, is_deletable 等) */
  role: RoleListItem;
  /** 编辑角色回调 */
  onEdit: (name: string) => void;
  /** 删除角色回调 */
  onDelete: (name: string) => void;
}

/**
 * 角色详情卡片组件
 *
 * Linear/Stripe 风格: 信息按列横排, 操作放右上角 dropdown.
 * 选中 role 后下方显示元信息 + 操作.
 *
 * @param props - 组件属性
 * @param props.role - 角色详情数据
 * @param props.onEdit - 编辑角色回调
 * @param props.onDelete - 删除角色回调
 * @client-bff
 */
export const RoleDetailCard = ({ role, onEdit, onDelete }: RoleDetailCardProps) => {
  const tr = useTranslations();
  const isSuper = role.name === "super_admin";
  const RoleIcon = isSuper ? Shield : User;

  /** 渲染可删除状态徽章 */
  const renderDeletableBadge = () => {
    if (isSuper) {
      return <Badge variant="secondary">{tr("不可")}</Badge>;
    }
    if (role.is_deletable) {
      return (
        <Badge variant="outline" className="text-status-success border-status-success/40">
          {tr("可")}
        </Badge>
      );
    }
    return <Badge variant="secondary">{tr("不可")}</Badge>;
  };

  return (
    <Card className="border-border/60 bg-card/40" data-testid={`role-detail-${role.name}`}>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
              <RoleIcon className="h-5 w-5" strokeWidth={1.5} />
            </div>
            <div>
              <CardTitle>{tr(role.label_zh)}</CardTitle>
              <p className="text-sm text-muted-foreground">{role.name}</p>
            </div>
          </div>
          <AppDropdownMenu
            trigger={
              <Button variant="outline" size="sm" data-testid={`role-detail-actions-${role.name}`}>
                <MoreHorizontal className="mr-1 h-4 w-4" />
                {tr("操作")}
              </Button>
            }
            items={[
              {
                key: "rename",
                label: tr("重命名"),
                icon: <Pencil className="h-4 w-4" />,
                onClick: () => onEdit(role.name),
              },
              {
                key: "delete",
                label: tr("删除"),
                icon: <Trash2 className="h-4 w-4" />,
                onClick: () => onDelete(role.name),
                variant: "destructive" as const,
                hidden: isSuper || !role.is_deletable,
              },
            ]}
          />
        </div>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm md:grid-cols-4">
          <div>
            <dt className="text-muted-foreground">{tr("英文标签")}</dt>
            <dd className="font-medium">{role.label_en}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{tr("类型")}</dt>
            <dd>
              {role.is_system ? (
                <Badge variant="secondary">{tr("系统角色")}</Badge>
              ) : (
                <Badge variant="outline">{tr("自定义")}</Badge>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{tr("使用人数")}</dt>
            <dd className="font-medium num">
              {role.user_count} {tr("人")}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{tr("可删除")}</dt>
            <dd>{renderDeletableBadge()}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
};
