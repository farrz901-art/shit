/**
 * JSON 行级 diff (RSC) — shiki 着色 + diff Lines + 高亮 add/remove
 *
 * 用法: <JsonDiff oldData={a} newData={b} /> — 对比两个对象, 渲染行级差异
 * 场景: 审计 / Dify 同步对比 / approval 记录 等"看改了啥"页面
 *
 * 跟 <JsonView> 区别:
 *   - JsonDiff: 两个对象对比, 高亮 add/remove 行 (status-success/error token)
 *   - JsonView: 单个对象展示, 不接受交互
 *   - 同样: RSC + shiki + safeStringify + 高度滚动
 *
 * 兜底:
 *   - old & new 都空 → "—"
 *   - 任一序列化失败 → "JSON 序列化失败" 错误态
 *   - 序列化结果完全相同 → "无差异" (避免白屏看不出差异)
 *   - 不同 → diffLines + codeToTokens → <DiffRow> 渲染表格
 *
 * 算法: diff 库 (jsdiff) 行级 diff → 每行 tokenize → <DiffRow> 渲染色块
 */
import { codeToTokens } from "shiki";
import { diffLines } from "diff";
import { cn } from "@/lib/utils";
import { DiffRow, type DiffRowLine, type DiffLineType } from "./diff-row";
import type { ShikiTheme } from "./types";
import { resolveCssDimension, safeStringify } from "./utils";

/**
 * JsonDiff 组件属性
 * @param props.oldData 旧 JSON 数据
 * @param props.newData 新 JSON 数据
 * @param props.theme shiki 主题
 * @param props.className 外层容器 className
 * @param props.maxHeight 容器最大高度
 * @shared
 */
export interface JsonDiffProps {
  /** 旧 JSON 数据 */
  oldData: unknown;
  /** 新 JSON 数据 */
  newData: unknown;
  /** shiki 主题, 默认 "github-dark" */
  theme?: ShikiTheme;
  /** 外层容器 className */
  className?: string;
  /** 容器最大高度, 超出滚动, 如 "500px" 或 400 */
  maxHeight?: string | number;
}

/** 空数据占位符 */
const EMPTY_PLACEHOLDER = "—";
/** 序列化错误文本 */
const SERIALIZE_ERROR_TEXT = "JSON 序列化失败";
/** 无差异提示文本 */
const NO_DIFF_TEXT = "无差异";

/** 解析 diffLines Change 类型为 DiffLineType */
/**
 * 解析 diffLines Change 类型为 DiffLineType
 * @param change diff 变更对象
 * @returns DiffLineType
 */
const resolveChangeType = (change: { added?: boolean; removed?: boolean }): DiffLineType => {
  if (change.added) {
    return "add";
  }
  if (change.removed) {
    return "remove";
  }
  return "none";
};

/** 将 diffLines Change[] 逐块 tokenize 为 DiffRowLine[] */
/**
 * 将 diffLines Change[] 逐块 tokenize 为 DiffRowLine[]
 * @param changes diffLines 变更数组
 * @param theme shiki 主题
 * @returns Promise<DiffRowLine[]>
 */
const buildDiffLines = async (
  changes: { added?: boolean; removed?: boolean; value: string }[],
  theme: ShikiTheme,
): Promise<DiffRowLine[]> => {
  const result: DiffRowLine[] = [];

  for (const change of changes) {
    const type = resolveChangeType(change);
    const { tokens } = await codeToTokens(change.value, {
      lang: "json",
      theme,
    });
    for (const tokenLine of tokens) {
      result.push({ type, tokens: tokenLine });
    }
  }

  return result;
};

/**
 * JsonDiff — JSON 行级 diff (RSC) 组件
 * shiki 着色 + diff Lines + 高亮 add/remove
 * 对比两个对象, 渲染行级差异
 * @param props.oldData - 旧 JSON 数据
 * @param props.newData - 新 JSON 数据
 * @param props.theme - shiki 主题, 默认 "github-dark"
 * @param props.className - 外层容器 className
 * @param props.maxHeight - 容器最大高度
 * @returns JSX 元素
 * @shared
 */
// eslint-disable-next-line max-statements -- RSC 组件含多个前置返回, 拆函数不降低成本
export const JsonDiff = async ({
  oldData,
  newData,
  theme = "github-dark" as ShikiTheme,
  className,
  maxHeight,
}: JsonDiffProps) => {
  // 全空兜底
  if (oldData == null && newData == null) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border p-8 text-muted-foreground",
          className,
        )}
      >
        {EMPTY_PLACEHOLDER}
      </div>
    );
  }

  // 序列化
  const oldStr = safeStringify(oldData);
  const newStr = safeStringify(newData);
  if (oldStr === null || newStr === null) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border p-8 text-destructive",
          className,
        )}
      >
        {SERIALIZE_ERROR_TEXT}
      </div>
    );
  }

  // 完全相同 → 提早返回
  if (oldStr === newStr) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border p-8 text-muted-foreground",
          className,
        )}
      >
        {NO_DIFF_TEXT}
      </div>
    );
  }

  // diff + tokenize
  const changes = diffLines(oldStr, newStr);
  const lines = await buildDiffLines(changes, theme);

  // 渲染
  const containerStyle =
    maxHeight != null ? { maxHeight: resolveCssDimension(maxHeight) } : undefined;

  return (
    <div
      className={cn("overflow-auto rounded-lg border font-mono text-sm leading-relaxed", className)}
      style={containerStyle}
    >
      <table className="w-full border-collapse">
        <tbody>
          {lines.map((line, idx) => (
            <DiffRow key={idx} line={line} />
          ))}
        </tbody>
      </table>
    </div>
  );
};
