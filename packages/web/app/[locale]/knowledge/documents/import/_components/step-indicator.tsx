/**
 * StepIndicator (2026-06-29)
 * 抽自 documents-import-form.tsx 的步骤指示器 (3 步骤: 上传 / 校验 / 提交)
 * 步骤圆圈用 CSS_EASE_STR.outExpo transition, 跟原文件保持一致
 */
"use client";
import { CSS_EASE_STR } from "@/lib/motion";
import { ONE } from "@/const";
import { cn } from "@/lib/utils";

/**
 * ImportStep - 导入步骤定义
 * @property stepNum - 步骤编号
 * @property label - 步骤标签
 * @property description - 步骤描述
 */
export interface ImportStep {
  stepNum: number;
  label: string;
  description: string;
}

/**
 * StepIndicatorProps - 步骤指示器属性
 * @property steps - 步骤列表
 * @property isStepDone - 判断步骤是否完成的函数
 */
export interface StepIndicatorProps {
  steps: ImportStep[];
  /** 返回该步骤是否已完成 (由父组件传入, 因为依赖 parseResult 业务状态) */
  isStepDone: (stepNum: number) => boolean;
}

/** StepIndicator - 步骤指示器组件 */
export const StepIndicator = ({ steps, isStepDone }: StepIndicatorProps) => (
  <div className="flex items-center gap-3 rounded-xl border border-border/60 bg-card px-5 py-3">
    {steps.map((step, idx) => {
      const stepDone = isStepDone(step.stepNum);
      const circleClass = stepDone
        ? "bg-ink text-paper"
        : "border border-border bg-card text-muted-foreground";
      const circleContent = stepDone ? "✓" : step.stepNum;
      return (
        <div key={step.stepNum} className="flex items-center gap-3">
          <div className="flex items-center gap-2.5">
            <span
              className={cn(
                "num flex h-7 w-7 items-center justify-center rounded-full text-sm font-medium transition-all duration-500",
                circleClass,
              )}
              style={{ transitionTimingFunction: CSS_EASE_STR.outExpo }}
            >
              {circleContent}
            </span>
            <div className="leading-tight">
              <div className="text-base font-medium text-foreground">{step.label}</div>
              <div className="text-sm text-muted-foreground">{step.description}</div>
            </div>
          </div>
          {idx + ONE < steps.length && <span className="mx-2 h-px w-12 bg-border" />}
        </div>
      );
    })}
  </div>
);
