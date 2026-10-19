"use client";
// Antd 风格 Select 包装 (2026-06-14): 替 shadcn Select 6 子件 (Root/Trigger/Value/Content/Item/Icon) 模板
//   用法: <AppSelect options={[{value,label}]} value={x} onChange={setX} />
//   关联 [[feedback-no-shim-no-minimal-changes]] (shadcn 原始模板啰嗦, antd 风格 1 行)
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * AppSelect 选项 — 值、展示文案及禁用状态
 * @client-bff
 */
export interface AppSelectOption {
  /** 选项值 */
  value: string;
  /** 选项展示文案 */
  label: string;
  disabled?: boolean;
}

/**
 * AppSelect 属性接口 — 选项列表、受控值/默认值、变化回调及占位文案
 * @client-bff
 */
export interface AppSelectProps {
  options: AppSelectOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  dataTestid?: string;
}

/**
 * 下拉选择器 — antd 风格 Select 包装, 替 shadcn Select 6 子件模板
 * @param props.options 选项列表
 * @param props.value 受控值
 * @param props.onChange 值变化回调
 * @param props.placeholder 占位文案
 * @returns Select JSX
 */
export const AppSelect = ({
  options,
  value,
  defaultValue,
  onChange,
  placeholder,
  disabled,
  className,
  dataTestid,
}: AppSelectProps) => (
  <Select value={value} defaultValue={defaultValue} onValueChange={onChange} disabled={disabled}>
    <SelectTrigger className={className} data-testid={dataTestid}>
      <SelectValue placeholder={placeholder} />
    </SelectTrigger>
    <SelectContent>
      {options.map((opt) => (
        <SelectItem key={opt.value} value={opt.value} disabled={opt.disabled}>
          {opt.label}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);
