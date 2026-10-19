/**
 * 简化版页面 Header — 返回按钮 + 标题 + 右侧 actions slot
 * 跟 app-page-hero.tsx 区别: PageHeader 简单列表/详情页用 (无 description, 无 Reveal 动画);
 *                                      PageHero 业务页/落地页用 (多 slot + eyebrow + 动画)
 * 选用规则: 列表/详情 → PageHeader; 业务页 → PageHero
 */
"use client";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/navigation";
import type { ReactNode } from "react";

/**
 * PageHeader 属性接口 — 返回目标 URL、页面标题及右上角操作区
 * @client-bff
 * @property backHref 返回目标 URL
 * @property title 页面标题
 * @property actions 右上角操作区
 */
interface PageHeaderProps {
  backHref: string;
  title: string;
  actions?: ReactNode;
}

/**
 * 简化版页面 Header — 返回按钮 + 标题 + 右侧 actions slot
 * 跟 PageHero 区别: PageHeader 简单列表/详情页用, PageHero 业务页/落地页用 (多 slot + 动画)
 * @param props.backHref 返回目标 URL
 * @param props.title 页面标题
 * @param props.actions 右上角操作区
 * @returns 页面 Header JSX
 */
export const PageHeader = ({ backHref, title, actions }: PageHeaderProps) => {
  const router = useRouter();
  return (
    <div className="mb-6 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <Button onClick={() => router.push(backHref)} size="sm" variant="ghost">
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回
        </Button>
        <h1 className="text-xl font-semibold">{title}</h1>
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
};
