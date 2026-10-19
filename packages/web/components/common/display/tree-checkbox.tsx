/**
 * TreeCheckbox: 通用树形 checkbox 组件 (2026-07-02 nav spec §5.3)
 *
 * 通用, 不耦合业务. 业务用法:
 * - 权限矩阵: checked = cell value, indeterminate = 子项部分勾
 * - 未来: 角色组 / 功能开关 / 标签
 *
 * 视觉规格 (spec §5.3):
 * - 缩进 24px/级
 * - 行高 32px
 * - 父级 label 加粗
 * - hover 整行高亮 bg-muted/40
 */
/* eslint-disable max-statements, id-length, no-magic-numbers -- generic component */
"use client";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

/**
 * TreeCheckboxNode — 树形节点: 唯一 key、显示文案、子节点及附加业务数据
 * @client-bff
 */
export interface TreeCheckboxNode<T = unknown> {
  /** 节点唯一 key */
  key: string;
  /** 节点显示文案 */
  label: string;
  /** 子节点列表 */
  children?: TreeCheckboxNode<T>[];
  /** 附加业务数据 */
  data?: T;
}

/**
 * TreeCheckbox 属性接口 — 节点列表、勾选集合、toggle 回调及自定义渲染
 * @client-bff
 */
export interface TreeCheckboxProps<T = unknown> {
  nodes: TreeCheckboxNode<T>[];
  /** 已勾选的 key 集合 */
  checked: Set<string>;
  /** indeterminate 状态的 key 集合 (父级部分勾) */
  indeterminate: Set<string>;
  /** toggle 一个 key (一般是叶子, 父级 disabled) */
  onToggle: (key: string) => void;
  /** 自定义 label 渲染 (e.g. 加 icon / 翻译) */
  renderLabel?: (node: TreeCheckboxNode<T>) => React.ReactNode;
  /** 默认是否全部展开 (default true) */
  defaultExpanded?: boolean;
}

/** 每级缩进像素数 */
const INDENT_PX_PER_LEVEL = 24;
/** 行高像素数 */
const ROW_HEIGHT_PX = 32;

/**
 * 在 Set 中 toggle 一个 key — 存在则删, 不存在则加
 * @param set 原集合
 * @param key 要切换的 key
 * @returns 新集合
 */
const toggleSet = (set: Set<string>, key: string): Set<string> => {
  const next = new Set(set);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  return next;
};

/**
 * 通用树形 checkbox — 缩进 24px/级, 行高 32px, 父级加粗
 * @param props.nodes 树节点列表
 * @param props.checked 已勾选 key 集合
 * @param props.indeterminate 部分勾选 key 集合
 * @param props.onToggle 勾选回调
 * @param props.renderLabel 自定义 label 渲染
 * @param props.defaultExpanded 默认全部展开
 * @returns 树形 checkbox JSX
 */
export const TreeCheckbox = <T,>({
  nodes,
  checked,
  indeterminate,
  onToggle,
  renderLabel,
  defaultExpanded = true,
}: TreeCheckboxProps<T>) => {
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    if (!defaultExpanded) {
      return new Set();
    }
    return new Set(nodes.map((node) => node.key));
  });

  const onToggleExpand = (key: string) => {
    setExpanded((prev) => toggleSet(prev, key));
  };

  return (
    <div role="tree" className="flex flex-col">
      {nodes.map((node) => (
        <TreeRow
          key={node.key}
          node={node}
          level={0}
          checked={checked}
          indeterminate={indeterminate}
          onToggle={onToggle}
          renderLabel={renderLabel}
          expanded={expanded}
          onToggleExpand={onToggleExpand}
        />
      ))}
    </div>
  );
};

/**
 * TreeRow 属性接口 — 节点、层级、勾选及展开状态
 * @client-bff
 */
interface TreeRowProps<T> {
  node: TreeCheckboxNode<T>;
  level: number;
  checked: Set<string>;
  indeterminate: Set<string>;
  onToggle: (key: string) => void;
  renderLabel?: (node: TreeCheckboxNode<T>) => React.ReactNode;
  expanded: Set<string>;
  onToggleExpand: (key: string) => void;
}

/**
 * 树形行渲染 — 递归渲染节点及子节点
 * @param props.node 树节点
 * @param props.level 当前层级
 * @param props.checked 已勾选 key 集合
 * @param props.indeterminate 部分勾选 key 集合
 * @param props.onToggle 勾选回调
 * @param props.renderLabel 自定义 label 渲染
 * @param props.expanded 展开 key 集合
 * @param props.onToggleExpand 展开/折叠回调
 * @returns 树形行 JSX
 */
const TreeRow = <T,>({
  node,
  level,
  checked,
  indeterminate,
  onToggle,
  renderLabel,
  expanded,
  onToggleExpand,
}: TreeRowProps<T>) => {
  const hasChildren = (node.children?.length ?? 0) > 0;
  const isExpanded = expanded.has(node.key);
  const isChecked = checked.has(node.key);
  const isIndeterminate = indeterminate.has(node.key);
  const isDisabled = hasChildren;

  return (
    <div role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
      <div
        className="flex items-center gap-2 rounded-md px-2 hover:bg-muted/40"
        style={{
          paddingLeft: `${level * INDENT_PX_PER_LEVEL + 8}px`,
          minHeight: `${ROW_HEIGHT_PX}px`,
        }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => onToggleExpand(node.key)}
            data-testid={`tree-chevron-${node.key}`}
            aria-label={isExpanded ? "折叠" : "展开"}
            className="flex h-5 w-5 items-center justify-center"
          >
            <ChevronDown
              className={cn("h-3 w-3 transition-transform", isExpanded ? "rotate-0" : "-rotate-90")}
            />
          </button>
        ) : (
          <span className="inline-block h-5 w-5" />
        )}
        <Checkbox
          checked={isIndeterminate ? "indeterminate" : isChecked}
          disabled={isDisabled}
          onCheckedChange={() => onToggle(node.key)}
          aria-label={node.label}
        />
        <span className={cn(hasChildren && "font-semibold")}>
          {renderLabel ? renderLabel(node) : node.label}
        </span>
      </div>
      {hasChildren && isExpanded && (
        <div role="group">
          {node.children!.map((child) => (
            <TreeRow
              key={child.key}
              node={child}
              level={level + 1}
              checked={checked}
              indeterminate={indeterminate}
              onToggle={onToggle}
              renderLabel={renderLabel}
              expanded={expanded}
              onToggleExpand={onToggleExpand}
            />
          ))}
        </div>
      )}
    </div>
  );
};
