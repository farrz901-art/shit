"use client";
// Antd 风格 RadioGroup 包装 (2026-07-07): 替 shadcn RadioGroup + RadioGroupItem 2 行模板
//   用法: <AppRadioGroup options={[{value,label}]} value={x} onChange={setX} />
//   跟 AppSelect / AppToggle 一致, 每项支持 renderLabel 复合 (带 Tooltip/描述/图标场景)
//   关联 [[feedback-no-shim-no-minimal-changes]]
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";

/**
 * AppRadioGroup 选项 — 值及展示文案
 * @client-bff
 */
export interface AppRadioOption {
  /** 选项值 */
  value: string;
  /** 选项展示文案 (renderLabel 缺省时使用) */
  label: string;
  /** 禁用单项 */
  disabled?: boolean;
}

/**
 * AppRadioGroup 属性接口 — 选项列表、受控值、变化回调、每项自定义渲染
 * @client-bff
 */
export interface AppRadioGroupProps<TOption extends AppRadioOption = AppRadioOption> {
  /** 选项列表 */
  options: TOption[];
  /** 受控值 */
  value?: string;
  /** 非受控初始值 */
  defaultValue?: string;
  /** 值变化回调 (传入新值) */
  onChange?: (value: string) => void;
  /** 自定义单选项渲染 — 默认只渲染 label 文本 */
  renderLabel?: (option: TOption) => React.ReactNode;
  /** 根容器 className (默认 flex flex-row gap-4 横向并排, 多选项时传 "flex-wrap") */
  className?: string;
  /** 根容器 testid — Item 级 testid 拼成 `${dataTestid}-${option.value}` */
  dataTestid?: string;
}

/**
 * 单选组 — antd 风格 RadioGroup 包装, 替 shadcn RadioGroup + RadioGroupItem 2 行模板
 * @param props.options 选项列表
 * @param props.value 受控值
 * @param props.onChange 值变化回调
 * @param props.renderLabel 自定义单选项渲染
 * @returns RadioGroup JSX
 */
export const AppRadioGroup = <TOption extends AppRadioOption = AppRadioOption>({
  options,
  value,
  defaultValue,
  onChange,
  renderLabel,
  className,
  dataTestid,
}: AppRadioGroupProps<TOption>) => (
  <RadioGroup
    value={value}
    defaultValue={defaultValue}
    onValueChange={onChange}
    className={cn("flex flex-row gap-4", className)}
    data-testid={dataTestid}
  >
    {options.map((opt) => {
      // 不传 dataTestid 时透传 undefined, 保持 RadioGroupItem 内部 data-testid 不被覆盖
      const testid = dataTestid ? `${dataTestid}-${opt.value}` : undefined;
      // Item id 用 testid 同字符串, 让 Label htmlFor 跟 data-testid 共享, 缺省时退化为 radio-<value>
      const itemId = testid ?? `radio-${opt.value}`;
      return (
        <div key={opt.value} className="flex items-center gap-2">
          <RadioGroupItem
            value={opt.value}
            disabled={opt.disabled}
            id={itemId}
            data-testid={testid}
          />
          <Label htmlFor={itemId} className="cursor-pointer font-normal">
            {renderLabel ? renderLabel(opt) : opt.label}
          </Label>
        </div>
      );
    })}
  </RadioGroup>
);
