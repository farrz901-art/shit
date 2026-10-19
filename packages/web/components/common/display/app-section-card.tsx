/**
 * 通用 section 容器 — title + description + actions slot + children
 * 不带边框/卡片样式 (跟 SettingsCard 区别), 适合内嵌在 page 内的逻辑分组
 */
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

/**
 * Section 容器属性 — 标题、描述、子元素、操作区及 className
 * @shared
 * @property title section 标题
 * @property description section 描述 (可选)
 * @property children 子元素
 * @property actions 右上角操作区 (可选)
 * @property className 自定义类名
 */
interface SectionCardProps {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
}

/**
 * Section 容器 — title (左) + actions (右) + children
 * @shared
 * @param props.actions 右上角按钮组, 跟 title 同行右对齐
 * @returns Section 容器 JSX
 */
export const SectionCard = ({
  title,
  description,
  children,
  actions,
  className,
}: SectionCardProps) => (
  <div className={cn("rounded-lg border p-6", className)}>
    <div className="mb-4 flex items-start justify-between">
      <div>
        <h2 className="text-lg font-medium">{title}</h2>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
    {children}
  </div>
);
