"use client";
// 已导入系列弹框 — 展示 systemApi.listSeries() 结果
//   Trigger 按钮由调用方 (page.tsx) 渲染, 本组件只负责弹框内容
import { useEffect, useState } from "react";
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { Badge } from "@/components/ui/badge";
import { ZERO } from "@/const";
import { listSeries } from "@/lib/api/system";

/** 产品系列信息
 * @property series - 系列编码
 * @property manufacturer - 制造商
 * @property name - 系列名称
 * @property prefix - 前缀
 * @shared
 */
interface Series {
  series: string;
  manufacturer: string;
  name: string;
  prefix: string;
}

/** SeriesDialogProps - 已导入系列弹框属性 */
export interface SeriesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** SeriesDialog - 已导入系列弹框组件 */
export const SeriesDialog = ({ open, onOpenChange }: SeriesDialogProps) => {
  const [series, setSeries] = useState<Series[]>([]);

  useEffect(() => {
    if (!open || series.length > ZERO) {
      return;
    }
    listSeries()
      .then(setSeries)
      .catch(() => {});
  }, [open, series.length]);

  return (
    <AppDialog open={open} onOpenChange={onOpenChange} title="已导入系列." maxWidth="2xl">
      {series.length > ZERO ? (
        <div className="max-h-[60vh] overflow-auto">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {series.map((ser) => (
              <div
                key={ser.series}
                className="flex items-baseline gap-3 rounded-lg border border-border/40 bg-card px-3 py-2.5"
              >
                <span className="num shrink-0 text-base font-medium text-foreground">
                  {ser.series}
                </span>
                <Badge variant="outline" className="shrink-0 text-xs">
                  {ser.manufacturer}
                </Badge>
                <span className="truncate text-sm text-muted-foreground">{ser.name}</span>
                <span className="num ml-auto shrink-0 text-xs text-muted-foreground/60">
                  {ser.prefix}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">加载中…</p>
      )}
    </AppDialog>
  );
};
