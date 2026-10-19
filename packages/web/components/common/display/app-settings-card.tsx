/**
 * SettingsCard — 统一设置页卡片组件
 * 入场动画 (Reveal) + hover 微浮 (hover:shadow-md) + 主题色边框
 * 不修改卡片长宽高, 不影响周边布局 (motion 只改 transform)
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Reveal } from "@/components/motion/animated";
import type { LucideIcon } from "lucide-react";

/** SettingsCard 属性接口 — 图标、标题、内容及 class 自定义
 * @shared
 * @property icon lucide-react 图标组件
 * @property title 卡片标题
 * @property children 卡片内容
 * @property className 自定义类名
 * @property iconClassName 图标自定义类名
 * @property titleClassName 标题自定义类名
 * @property "data-testid" 测试 ID
 */
export interface SettingsCardProps {
  icon: LucideIcon;
  title: string;
  children: React.ReactNode;
  className?: string;
  iconClassName?: string;
  titleClassName?: string;
  "data-testid"?: string;
}

/**
 * 设置卡片 — Reveal 入场 + hover 阴影 + 左侧 icon
 * @shared
 * @param props.icon lucide-react 图标组件, 自动 h-4 w-4 + text-muted-foreground
 * @returns 设置卡片 JSX
 */
export const SettingsCard = ({
  icon: Icon,
  title,
  children,
  className = "",
  iconClassName = "",
  titleClassName = "",
  ...rest
}: SettingsCardProps) => (
  <Reveal className="h-full">
    <Card
      className={`h-full border-border/60 bg-card/60 transition-all duration-200 hover:shadow-md ${className}`}
      {...rest}
    >
      <CardHeader>
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 text-muted-foreground ${iconClassName}`} strokeWidth={1.5} />
          <CardTitle className={titleClassName}>{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  </Reveal>
);
