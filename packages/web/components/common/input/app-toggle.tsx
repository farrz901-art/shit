"use client";
// Shadcn ToggleGroup type="single" 包装 (2026-06-14): 替手写 button 按钮组
//   用法: <AppToggle options={[{value,label}]} value={x} onChange={setX} />
//   跟 AppSelect 一致, 业务当前只有 decode view 切换 1 处用
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

/**
 * AppToggle 选项 — 值及展示文案
 * @client-bff
 */
export interface AppToggleOption {
  /** 选项值 */
  value: string;
  /** 选项展示文案 */
  label: string;
}

/**
 * AppToggle 属性接口 — 选项列表、受控值/默认值、切换回调及 testid
 * @client-bff
 */
export interface AppToggleProps {
  options: AppToggleOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  className?: string;
  dataTestid?: string;
}

/**
 * 按钮组切换 — shadcn ToggleGroup type="single" 包装, 替手写 button 按钮组
 * @param props.options 选项列表
 * @param props.value 受控值
 * @param props.onChange 切换回调
 * @returns ToggleGroup JSX
 */
export const AppToggle = ({
  options,
  value,
  defaultValue,
  onChange,
  className,
  dataTestid,
}: AppToggleProps) => (
  <ToggleGroup
    type="single"
    value={value}
    defaultValue={defaultValue}
    onValueChange={onChange}
    className={className}
  >
    {options.map((opt) => {
      // 不传 dataTestid 时透传 undefined, 保持 ToggleGroupItem 内部 data-testid 不被覆盖
      const testid = dataTestid ? `${dataTestid}-${opt.value}` : undefined;
      return (
        <ToggleGroupItem key={opt.value} value={opt.value} data-testid={testid}>
          {opt.label}
        </ToggleGroupItem>
      );
    })}
  </ToggleGroup>
);
