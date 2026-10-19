/**
 * JsonDiff 单行渲染 — 3 type: add/remove/none, 走 status-* 主题 token
 * 每行: 左侧 gutter (+/- 符号) + token 序列 (可选着色)
 * 父组件 (JsonDiff) 拼多行, 配套 shiki 着色
 */
import { ZERO } from "@/const";
import { cn } from "@/lib/utils";

/** diff 行类型: add(新增)/remove(删除)/none(不变) */
export type DiffLineType = "add" | "remove" | "none";

/** diff 行 token — 着色片段 */
export interface DiffRowToken {
  content: string;
  color?: string;
}

/** diff 行 — 类型 + token 序列 */
export interface DiffRowLine {
  type: DiffLineType;
  tokens: DiffRowToken[];
}

/** DiffRow 组件属性 */
interface DiffRowProps {
  line: DiffRowLine;
}

// (2026-06-28 P2 refactor) 硬编码 green/red Tailwind 色阶 → status-* 项目主题 token
//   响应 light/dark 主题切换, 跟项目规约一致
/** diff 行背景色映射 */
const BG_MAP: Record<DiffLineType, string> = {
  add: "bg-status-success/20 dark:bg-status-success/40",
  remove: "bg-status-error/20 dark:bg-status-error/40",
  none: "",
};

/** gutter 符号颜色映射 */
const GUTTER_COLOR_MAP: Record<DiffLineType, string> = {
  add: "text-status-success",
  remove: "text-status-error",
  none: "text-muted-foreground",
};

/** gutter 符号映射 */
const GUTTER_SIGN_MAP: Record<DiffLineType, string> = {
  add: "+",
  remove: "-",
  none: " ",
};

/**
 * json-diff 单行渲染 — 左侧 gutter (+/-) + 着色 token
 * @param props.line diff 行数据
 * @returns JSX 元素 (tr)
 * @shared
 */
export const DiffRow = ({ line }: DiffRowProps) => (
  <tr className={BG_MAP[line.type]}>
    <td className={cn("w-8 select-none text-right", GUTTER_COLOR_MAP[line.type])}>
      {GUTTER_SIGN_MAP[line.type]}
    </td>
    <td className="whitespace-pre px-2">
      {line.tokens.length > ZERO ? (
        line.tokens.map((token, idx) => (
          <span key={idx} style={{ color: token.color }}>
            {token.content}
          </span>
        ))
      ) : (
        <span>&nbsp;</span>
      )}
    </td>
  </tr>
);
