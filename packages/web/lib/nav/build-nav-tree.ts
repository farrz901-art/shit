/**
 * buildNavTree: 把扁平 PageMeta[] 组装成 NavTree (2026-07-02 nav spec §3.1)
 *
 * 算法:
 * 1. 全转 NavNode (跳过 is_active=false)
 * 2. 建父子关系 (parent_id → children)
 * 3. 排序 (sort 字段)
 * 4. orphans 报警 (dev only)
 *
 * 决策 (来自 brainstorming 2026-07-02):
 * - 父级 is_group=true 不可点 (Header trigger 不跳页面)
 * - 子菜单可见性 = 父级 allowed OR 任一子项 allowed
 * - 叶子顶级: 自己 allowed 才显示
 */
/* eslint-disable max-statements, no-magic-numbers, no-continue -- pure function, multi-pass 逻辑清晰可读 */
import type { PageMeta } from "@/lib/auth/permission-types";
import type { NavNode, NavTree } from "./nav-types";

const DEFAULT_SORT = 0;

// 单字段排序, 提取到模块作用域避免 lint 警告
const sortBySort = (left: NavNode, right: NavNode) => left.sort - right.sort;

const indexNavNodes = (
  pages: PageMeta[],
): {
  byKey: Map<string, NavNode>;
  metaByKey: Map<string, PageMeta>;
} => {
  const byKey = new Map<string, NavNode>();
  const metaByKey = new Map<string, PageMeta>();

  for (const pg of pages) {
    if (pg.is_active === false) {
      continue;
    }
    const meta = pg.metadata ?? {};
    byKey.set(pg.key, {
      key: pg.key,
      label_zh: pg.label_zh,
      label_en: pg.label_en,
      path: meta.path ?? pg.path ?? null,
      icon: meta.icon,
      isGroup: meta.is_group === true,
      children: [],
      sort: pg.sort ?? DEFAULT_SORT,
    });
    metaByKey.set(pg.key, pg);
  }
  return { byKey, metaByKey };
};

const attachChildren = (
  byKey: Map<string, NavNode>,
  metaByKey: Map<string, PageMeta>,
): { roots: NavNode[]; orphans: NavNode[] } => {
  const roots: NavNode[] = [];
  const orphans: NavNode[] = [];

  for (const node of byKey.values()) {
    const parentId = metaByKey.get(node.key)?.metadata?.parent_id;
    if (!parentId) {
      roots.push(node);
    } else {
      const parent = byKey.get(parentId);
      if (parent) {
        parent.children.push(node);
      } else {
        orphans.push(node);
      }
    }
  }
  return { roots, orphans };
};

/** 扁平 PageMeta[] 组装成 NavTree (父子关系 + 排序 + orphan 报警).
 * @param pages 扁平页面元数据列表
 * @returns NavTree 树状结构
 * @shared */
export const buildNavTree = (pages: PageMeta[]): NavTree => {
  // 1st: 索引
  const { byKey, metaByKey } = indexNavNodes(pages);

  // 2nd: 父子
  const { roots, orphans } = attachChildren(byKey, metaByKey);

  // 3rd: 排序
  roots.sort(sortBySort);
  for (const root of roots) {
    root.children.sort(sortBySort);
  }

  // 4th: dev 报警
  if (orphans.length > 0 && process.env.NODE_ENV !== "production") {
    // dev 模式报警, 生产环境 (NODE_ENV=production) 不输出
    // (2026-07-08 lint-ignores.md §4.2)
    console.warn(
      "[buildNavTree] orphan nodes (parent_id 找不到):",
      orphans.map((orphan) => orphan.key),
    );
  }

  return { roots, orphans };
};

/**
 * filterNavByPermissions: 按用户权限过滤 NavTree.
 *
 * 规则:
 * - 父级 isGroup + 无 path (纯分组): 必须有 ≥1 子项 visible
 * - 父级 isGroup + 有 path (可点 + 子菜单): 自己 OR 子项 visible
 * - 叶子顶级 (无 is_group): 自己 visible
 *
 * @param tree NavTree 树状结构
 * @param allowed 用户允许的 pageKey 列表
 * @returns 过滤后的 NavTree
 * @shared
 */
export const filterNavByPermissions = (tree: NavTree, allowed: string[]): NavTree => {
  const visibleRoots: NavNode[] = [];
  for (const root of tree.roots) {
    const visibleChildren = root.children.filter((child) => allowed.includes(child.key));

    let isShown = false;
    if (root.isGroup && root.path === null) {
      // 纯分组: 仅子项可见时显示
      isShown = visibleChildren.length > 0;
    } else if (root.isGroup && root.path !== null) {
      // 父级可点 + 子菜单: 自己 OR 子项 visible
      isShown = allowed.includes(root.key) || visibleChildren.length > 0;
    } else {
      // 叶子顶级: 自己可见
      isShown = allowed.includes(root.key);
    }

    if (isShown) {
      visibleRoots.push(visibleChildren.length > 0 ? { ...root, children: visibleChildren } : root);
    }
  }
  return { roots: visibleRoots, orphans: [] };
};
