"use client";
// Antd 风格 Tabs 包装 (2026-06-15): 替 shadcn Tabs 三件套 (Tabs + TabsList + TabsTrigger [+ TabsContent])
//   用法 1 (纯 trigger, 替 MySubmissionsList 内的 filter 切):
//     <AppTabs options={[{value, label}]} value={x} onChange={setX} />
//   用法 2 (带 content, 替 SubmissionsTabs 整体):
//     <AppTabs options={[{value, label, content}]} value={x} onChange={setX} />
//   Content 字段任意 option 有值就自动包 TabsContent; 都没就只渲染 TabsList
//   关联 [[feedback-no-shim-no-minimal-changes]] (shadcn 原始模板啰嗦, antd 风格 1 行)
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/**
 * AppTab 选项 — 值、文案、禁用状态及可选内容
 * @client-bff
 */
export interface AppTabOption {
  /** Tab 值 */
  value: string;
  /** Tab 文案 */
  label: string;
  disabled?: boolean;
  // 任一 option 有 content 即触发 TabsContent 渲染 (替 SubmissionsTabs 那种"tab 带内容"用法)
  content?: React.ReactNode;
}

/**
 * AppTabs 属性接口 — 选项列表、受控值/默认值、切换回调及 testid
 * @client-bff
 */
export interface AppTabsProps {
  options: AppTabOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  className?: string;
  // Trigger testid 前缀, 最终 testid = `${dataTestid}-${value}` (跟 AppToggle 一致)
  dataTestid?: string;
}

/**
 * Tab 切换 — antd 风格 Tabs 包装, 替 shadcn Tabs 三件套模板
 * 支持纯 trigger 模式 (filter 切换) 和带 content 模式 (tab 内容切换)
 * @param props.options 选项列表 (含可选 content)
 * @param props.value 受控值
 * @param props.onChange 切换回调
 * @returns Tabs JSX
 */
export const AppTabs = ({
  options,
  value,
  defaultValue,
  onChange,
  className,
  dataTestid,
}: AppTabsProps) => {
  const hasContent = options.some((opt) => opt.content !== undefined);

  return (
    <Tabs value={value} defaultValue={defaultValue} onValueChange={onChange} className={className}>
      <TabsList>
        {options.map((opt) => {
          // 不传 dataTestid 时透传 undefined, 保持 TabsTrigger 内部 data-testid 不被覆盖
          const testid = dataTestid ? `${dataTestid}-${opt.value}` : undefined;
          return (
            <TabsTrigger
              disabled={opt.disabled}
              key={opt.value}
              value={opt.value}
              data-testid={testid}
            >
              {opt.label}
            </TabsTrigger>
          );
        })}
      </TabsList>
      {hasContent &&
        options.map((opt) => {
          if (opt.content === undefined) {
            return null;
          }
          return (
            <TabsContent key={opt.value} value={opt.value}>
              {opt.content}
            </TabsContent>
          );
        })}
    </Tabs>
  );
};
