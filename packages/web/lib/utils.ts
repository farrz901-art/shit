// Shadcn 要求的 cn() 工具: 合并 className
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * 合并 className, 支持条件类名和 Tailwind 类名冲突处理
 * @param inputs  类名值, 支持字符串/对象/数组
 * @returns       合并后的 className 字符串
 *
 * 调用边界:
 *   @shared  前后端通用 (纯函数)
 */
export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
