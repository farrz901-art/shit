"use client";
// 客户画像卡片 (2026-06-22 buyer-profile spec)
// 展示所有画像字段: 标签 + 值 + 置信度 badge
// 点击字段后弹出 AppDialog 编辑

import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useTranslations } from "next-intl";
import { Pencil } from "lucide-react";
import { useState } from "react";
import type {
  BuyerProfile,
  ProfileFieldConfig,
  ProfileFieldValue,
} from "@/app/[locale]/buyers/_lib/buyer-profile/types";

/** 空数组长度 */
const EMPTY_LENGTH = 0;

/**
 * 根据置信度返回 Badge variant
 * @param confidence - 置信度 (high / medium / low)
 * @returns Badge variant
 */
const confidenceColor = (
  confidence: string,
): "default" | "secondary" | "outline" | "destructive" => {
  switch (confidence) {
    case "high": {
      return "default";
    }
    case "medium": {
      return "secondary";
    }
    case "low": {
      return "outline";
    }
    default: {
      return "outline";
    }
  }
};

/** 客户画像卡片属性 */
interface ProfileCardProps {
  /** 字段配置列表 */
  configs: ProfileFieldConfig[];
  /** 字段更新回调 */
  onUpdate: (fieldCode: string, value: unknown) => void;
  /** 客户画像数据 */
  profile: BuyerProfile;
}

/**
 * 客户画像卡片组件 — 展示所有画像字段 + 点击字段弹出编辑
 * @param props.configs - 字段配置列表
 * @param props.onUpdate - 字段更新回调
 * @param props.profile - 客户画像数据
 * @returns 客户画像卡片
 * @client-bff
 */
export const ProfileCard = ({ configs, onUpdate, profile }: ProfileCardProps) => {
  const translate = useTranslations();
  const [editField, setEditField] = useState<{ code: string; value: string } | null>(null);
  const [editValue, setEditValue] = useState("");

  /**
   * 编辑字段, 预填当前值
   * @param code - 字段编码
   * @param currentValue - 当前值
   */
  const handleEdit = (code: string, currentValue: unknown) => {
    setEditField({ code, value: String(currentValue ?? "") });
    setEditValue(String(currentValue ?? ""));
  };

  /** 保存字段编辑结果, 调用 onUpdate 回调 */
  const handleSave = () => {
    if (editField) {
      onUpdate(editField.code, editValue);
      setEditField(null);
      setEditValue("");
    }
  };

  /** 取消编辑, 清空编辑状态 */
  const handleCancel = () => {
    setEditField(null);
    setEditValue("");
  };

  // Buyer_name 为空时用 buyer_key 作为标题 (跟后端 schema 一致, name 可为 null)
  const displayTitle = profile.buyer_name ?? profile.buyer_key;

  if (configs.length === EMPTY_LENGTH) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{displayTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">{translate("暂无字段配置")}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>{displayTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {configs.map((cfg) => {
              const fieldValue = profile.profile_data[cfg.code] as ProfileFieldValue | undefined;
              const displayValue = fieldValue?.value ?? "—";
              const confidence = fieldValue?.confidence ?? "medium";

              return (
                <div className="group relative rounded-lg border p-3" key={cfg.code}>
                  <div className="mb-1 flex items-center justify-between">
                    <Label className="text-muted-foreground text-xs">{cfg.label}</Label>
                    <Badge className="text-[10px]" variant={confidenceColor(confidence)}>
                      {confidence}
                    </Badge>
                  </div>
                  <div className="text-sm">{String(displayValue)}</div>
                  <Button
                    className="absolute right-1 top-1 h-6 w-6 opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={() => handleEdit(cfg.code, displayValue)}
                    size="icon"
                    variant="ghost"
                  >
                    <Pencil className="h-3 w-3" />
                  </Button>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <AppDialog
        footer={
          <>
            <Button onClick={handleCancel} variant="outline">
              {translate("取消")}
            </Button>
            <Button onClick={handleSave}>{translate("保存")}</Button>
          </>
        }
        onOpenChange={handleCancel}
        open={Boolean(editField)}
        title={translate("编辑字段")}
      >
        <div className="space-y-3 py-4">
          <Label>{editField?.code}</Label>
          <Input onChange={(ev) => setEditValue(ev.target.value)} value={editValue} />
        </div>
      </AppDialog>
    </>
  );
};
