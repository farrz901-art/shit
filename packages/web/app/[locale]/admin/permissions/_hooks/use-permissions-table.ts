"use client";
// UsePermissionsTable — 管理权限表格的筛选 + 编辑状态
import { useState } from "react";
import { useToggle } from "react-use";
/* eslint-disable no-continue, no-magic-numbers, max-statements, curly -- pure tree helpers, 跟 build-nav-tree 一致 */
import type { NavTree } from "@/lib/nav/nav-types";
import type { PageMeta } from "@/lib/auth/permission-types";

// ── 域类型 ─────────────────────────────────────────────────────────────────
/** 权限矩阵中的角色 */
export interface MatrixRole {
  /** 角色英文标识 */
  name: string;
  /** 角色中文标签 */
  label_zh: string;
  /** 角色英文标签 */
  label_en: string;
  /** 是否为系统内置角色 */
  is_system: boolean;
}

/** 权限矩阵中的页面 */
export interface MatrixPage {
  /** 页面 key */
  key: string;
  /** 页面中文标签 */
  label_zh: string;
  /** 页面英文标签 */
  label_en: string;
  /** 页面路径 */
  path: string;
}

/** 权限更新单元 (单行单页的允许/禁止) */
export interface MatrixUpdate {
  /** 角色名 */
  role_name: string;
  /** 页面 key */
  page_key: string;
  /** 是否允许 */
  allowed: boolean;
}

/** 角色列表项 (含用户数/可删除标记) */
export interface RoleListItem extends MatrixRole {
  /** 是否可删除 */
  is_deletable: boolean;
  /** 使用此角色的人数 */
  user_count: number;
}

// ── 常量 ────────────────────────────────────────────────────────────────────
/** 超级管理员角色名 */
export const SUPER_ADMIN_ROLE = "super_admin";
/** cell key 分隔符 */
const CELL_SEPARATOR = "|";
/** 数字零常量 */
const ZERO = 0;

// ── usePermissionsTable 返回值 ──────────────────────────────────────────────
/** usePermissionsTable 返回值 */
export interface UsePermissionsTableReturn {
  /** 是否处于编辑模式 */
  isEditMode: boolean;
  /** 搜索关键词 */
  search: string;
  /** 过滤后的角色列表 */
  filteredRoles: MatrixRole[];
  /** 未保存变更数 */
  dirtyCount: number;
  /** 获取单元格权限值 */
  getCellValue: (role: string, page: string) => boolean;
  /** 判断单元格是否有未保存变更 */
  isDirty: (role: string, page: string) => boolean;
  /** 切换单元格权限 */
  toggle: (role: string, page: string) => void;
  /** 事件处理器集 */
  handlers: {
    /** 取消编辑 (清空 pending) */
    cancel: () => void;
    /** 切换编辑模式 */
    editToggle: () => void;
    /** 保存变更 */
    save: () => Promise<void>;
    /** 搜索输入变更 */
    searchChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  };
}

// ── 工具函数 ────────────────────────────────────────────────────────────────
/**
 * 按 name / label_zh / label_en 搜索过滤角色列表
 * @param roles - 完整角色列表
 * @param search - 搜索关键词
 * @returns 过滤后的角色列表
 * @shared
 */
const filterRolesByQuery = (roles: MatrixRole[], search: string): MatrixRole[] => {
  if (!search.trim()) {
    return roles;
  }
  const query = search.toLowerCase();
  return roles.filter(
    (role) =>
      role.name.toLowerCase().includes(query) ||
      role.label_zh.toLowerCase().includes(query) ||
      role.label_en.toLowerCase().includes(query),
  );
};

/**
 * 内部辅助 hook: 管理 cell 编辑状态 (pending 变更追踪)
 * @param matrix - 原始权限矩阵
 * @param isEditMode - 是否编辑模式
 * @returns cell 读取/修改工具集
 * @shared
 */
const usePermissionMatrix = (
  matrix: Record<string, Record<string, boolean>>,
  isEditMode: boolean,
) => {
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const cellKey = (role: string, page: string) => `${role}${CELL_SEPARATOR}${page}`;

  /**
   * 取当前值: pending > matrix > false; super_admin 恒 true
   * @param role - 角色名
   * @param page - 页面 key
   * @returns 是否有权限
   */
  const getCellValue = (role: string, page: string): boolean => {
    if (role === SUPER_ADMIN_ROLE) {
      return true;
    }
    const key = cellKey(role, page);
    if (key in pending) {
      return pending[key]!;
    }
    const roleMatrix = matrix[role];
    if (roleMatrix) {
      return roleMatrix[page] ?? false;
    }
    return false;
  };

  /**
   * 判断 cell 是否有未保存变更 (super_admin 恒不 dirty)
   * @param role - 角色名
   * @param page - 页面 key
   * @returns 是否有未保存变更
   */
  const isDirty = (role: string, page: string): boolean => {
    if (role === SUPER_ADMIN_ROLE) {
      return false;
    }
    return cellKey(role, page) in pending;
  };

  /**
   * 切换单 cell: 非编辑模式/super_admin 忽略
   * @param role - 角色名
   * @param page - 页面 key
   */
  const toggle = (role: string, page: string) => {
    if (!isEditMode || role === SUPER_ADMIN_ROLE) {
      return;
    }
    const key = cellKey(role, page);
    setPending((prev: Record<string, boolean>) => ({ ...prev, [key]: !getCellValue(role, page) }));
  };

  return { getCellValue, isDirty, toggle, pending, setPending };
};

// ── Hook ────────────────────────────────────────────────────────────────────
/**
 * UsePermissionsTable — 管理权限矩阵的筛选、编辑模式、pending 变更
 *
 * @param roles - 完整角色列表
 * @param matrix - 原始权限矩阵 { role -> { page -> boolean } }
 * @param onSave - 保存 pending 变更的回调
 * @returns 表格状态与操作工具集
 * @client-bff
 */
export const usePermissionsTable = (
  roles: MatrixRole[],
  matrix: Record<string, Record<string, boolean>>,
  onSave: (updates: MatrixUpdate[]) => Promise<void>,
): UsePermissionsTableReturn => {
  const [isEditMode, toggleIsEditMode] = useToggle(false);
  const [search, setSearch] = useState("");
  const { getCellValue, isDirty, toggle, pending, setPending } = usePermissionMatrix(
    matrix,
    isEditMode,
  );

  const filteredRoles = filterRolesByQuery(roles, search);
  const dirtyCount = Object.keys(pending).length;

  const handlers = {
    cancel: () => {
      setPending({});
      toggleIsEditMode(false);
    },
    editToggle: () => toggleIsEditMode(),
    save: async () => {
      if (dirtyCount === ZERO) {
        return;
      }
      const updates: MatrixUpdate[] = Object.entries(pending).map(([key, allowed]) => {
        const [roleName, pageKey] = key.split(CELL_SEPARATOR);
        return { allowed: allowed as boolean, page_key: pageKey!, role_name: roleName! };
      });
      await onSave(updates);
      setPending({});
      toggleIsEditMode(false);
    },
    searchChange: (event: React.ChangeEvent<HTMLInputElement>) => setSearch(event.target.value),
  };

  return { isEditMode, search, filteredRoles, dirtyCount, getCellValue, isDirty, toggle, handlers };
};

// ── (2026-07-02 nav spec §5.4) Tree helpers ────────────────────────────────

/**
 * MatrixPage[] 转换为 PageMeta[], 兼容 metadata 字段
 * @param pages - 权限页配置列表
 * @returns 导航树所需的页面元数据列表
 * @shared
 */
export const pagesToPageMeta = (pages: MatrixPage[]): PageMeta[] =>
  pages.map((page) => {
    const meta = (page as MatrixPage & { metadata?: PageMeta["metadata"] }).metadata;
    return {
      key: page.key,
      label_zh: page.label_zh,
      label_en: page.label_en,
      path: page.path,
      metadata: meta,
    };
  });

/**
 * 计算角色的半选集合 (父级部分子项被勾选)
 * @param navTree - 导航树
 * @param role - 角色名
 * @param getCellValue - 权限值查询函数
 * @returns 半选状态的父级 key 集合
 * @shared
 */
export const computeIndeterminate = (
  navTree: NavTree,
  role: string,
  getCellValue: (role: string, page: string) => boolean,
): Set<string> => {
  const result = new Set<string>();
  for (const root of navTree.roots) {
    if (root.children.length === 0) continue;
    const checkedCount = root.children.filter((child: { key: string }) =>
      getCellValue(role, child.key),
    ).length;
    if (checkedCount > 0 && checkedCount < root.children.length) {
      result.add(root.key);
    }
  }
  return result;
};

/**
 * 计算角色的全选集合 (含继承的父级)
 * @param navTree - 导航树
 * @param role - 角色名
 * @param getCellValue - 权限值查询函数
 * @returns 勾选状态的 key 集合
 * @shared
 */
export const computeChecked = (
  navTree: NavTree,
  role: string,
  getCellValue: (role: string, page: string) => boolean,
): Set<string> => {
  const result = new Set<string>();
  for (const root of navTree.roots) {
    if (root.children.length === ZERO) {
      if (getCellValue(role, root.key)) result.add(root.key);
      continue;
    }
    if (getCellValue(role, root.key)) {
      result.add(root.key);
      for (const child of root.children) result.add(child.key);
    } else {
      for (const child of root.children) {
        if (getCellValue(role, child.key)) result.add(child.key);
      }
    }
  }
  return result;
};
