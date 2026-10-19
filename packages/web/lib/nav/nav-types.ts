/**
 * NavTree 渲染模型 (2026-07-02 nav spec §2.4)
 * Header / 移动端 / 权限矩阵 3 处复用.
 */
export interface NavNode {
  key: string;
  label_zh: string;
  label_en: string;
  path: string | null;
  icon?: string;
  isGroup: boolean; // 父级 = true, 叶子 = false
  children: NavNode[]; // 空数组 = 没子项 (自己就是页面)
  sort: number;
}

/** 导航树, 按 sort 排序的顶级节点 + 孤儿节点.
 * @shared */
export interface NavTree {
  roots: NavNode[]; // 顶级节点 (按 sort 排)
  orphans: NavNode[]; // 找不到 parent_id 的孤儿节点
}
