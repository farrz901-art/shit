"use client";
// 客户画像变更时间线 (2026-06-22 buyer-profile spec)
// 垂直时间线展示 profile_change_logs: 字段, 旧值 -> 新值, 时间, 来源

import { formatDateTime as formatDateTimeZh } from "@/lib/date";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Clock, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ChangeLog } from "@/app/[locale]/buyers/_lib/buyer-profile/types";

/** 空数组长度 */
const EMPTY_LENGTH = 0;

/**
 * 格式化 ISO 时间为中文短格式
 * @param iso - ISO 时间字符串
 * @returns 格式化后的时间字符串
 */
const formatDateTime = (iso: string | null): string => {
  if (!iso) {
    return "—";
  }
  return formatDateTimeZh(iso, "zh-CN");
};

/**
 * 根据来源返回 Badge variant
 * @param source - 来源标识 (auto / manual)
 * @returns Badge variant
 */
const getSourceVariant = (source: string): "default" | "secondary" | "outline" => {
  switch (source) {
    case "auto": {
      return "secondary";
    }
    case "manual": {
      return "default";
    }
    default: {
      return "outline";
    }
  }
};

/** 客户画像变更时间线属性 */
interface ChangeTimelineProps {
  /** 变更日志数组 */
  changes: ChangeLog[];
  /** 是否加载中 */
  loading?: boolean;
}

/**
 * 客户画像变更时间线组件 — 垂直时间线展示 profile_change_logs
 * @param props.changes - 变更日志数组
 * @param props.loading - 是否加载中
 * @returns 变更时间线卡片
 * @client-bff
 */
export const ChangeTimeline = ({ changes, loading }: ChangeTimelineProps) => {
  const translate = useTranslations();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <RefreshCw className="h-4 w-4" />
          {translate("变更历史")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading && (
          <div className="text-muted-foreground py-4 text-center text-sm">
            {translate("加载中…")}
          </div>
        )}
        {!loading && changes.length === EMPTY_LENGTH && (
          <div className="text-muted-foreground py-4 text-center text-sm">
            <Clock className="mx-auto mb-2 h-6 w-6" />
            {translate("暂无变更记录")}
          </div>
        )}
        {!loading && changes.length > EMPTY_LENGTH && (
          <div className="space-y-0">
            {changes.map((change, idx) => (
              <div className="relative flex gap-4 pb-6 pl-6 last:pb-0" key={change.id ?? idx}>
                {/* 时间线竖线 */}
                <div className="absolute left-2 top-1 h-full w-px bg-border last:h-0" />
                {/* 时间线圆点 */}
                <div className="border-primary absolute left-0 top-1.5 h-4 w-4 rounded-full border-2 bg-background" />

                <div className="flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="text-sm font-medium">{change.field_code}</span>
                    <Badge className="text-[10px]" variant={getSourceVariant(change.source)}>
                      {change.source}
                    </Badge>
                  </div>
                  <div className="mb-1 text-sm">
                    <span className="text-muted-foreground line-through">
                      {String(change.old_value ?? "—")}
                    </span>
                    <span className="mx-2 text-muted-foreground">&rarr;</span>
                    <span className="font-medium">{String(change.new_value ?? "—")}</span>
                  </div>
                  <div className="text-muted-foreground text-xs">
                    {formatDateTime(change.created_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
