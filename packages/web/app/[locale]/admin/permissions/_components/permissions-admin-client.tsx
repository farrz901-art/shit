"use client";
// PermissionsAdminClient — 整合 wrapper, 共享 selectedRole 状态
// PermissionsTable (matrix + 工具栏) + RoleDetailCard (选中角色详情) + CreateRoleDialog

import {
  type MatrixPage,
  type MatrixRole,
  type MatrixUpdate,
  PermissionsTable,
  type RoleListItem,
} from "./permissions-table";
import { useState, useTransition } from "react";
import { useToggle } from "react-use";
import { CreateRoleDialog } from "./create-role-dialog";
import { RoleDetailCard } from "./role-detail-card";
import { ZERO } from "@/const";
import { log } from "@/lib/log";
import { patchPermissions } from "@/lib/api/permissions";
import { useRouter } from "@/i18n/navigation";

/** 权限管理客户端组件的属性 */
export interface PermissionsAdminClientProps {
  /** 角色列表 (MatrixRole 格式) */
  roles: MatrixRole[];
  /** 可用页面权限列表 */
  pages: MatrixPage[];
  /** 初始权限矩阵数据 */
  matrix: Record<string, Record<string, boolean>>;
  /** 角色列表 (含 user_count 等详情) */
  roleList: RoleListItem[];
}

/**
 * 编辑角色 (TODO Phase 5: 实现 EditRoleDialog 重命名)
 * @param name - 角色名
 * @shared
 */
const handleEdit = (name: string) => {
  // TODO (Phase 5): EditRoleDialog 重命名
  log.info(`[permissions] edit role ${name} (TODO Phase 5)`);
};

/**
 * 删除角色 (TODO Phase 5: AppConfirm -> DELETE /api/roles/:name)
 * @param name - 角色名
 * @shared
 */
const handleDelete = (name: string) => {
  // TODO (Phase 5): AppConfirm → DELETE /api/roles/:name
  // 当前 RoleList 阻断 UI 不让点 system, 不调 API
  log.info(`[permissions] delete role ${name} (TODO Phase 5)`);
};

/**
 * 权限管理客户端组件 (矩阵 + 详情 + 创建)
 *
 * 整合 wrapper, 共享 selectedRole 状态.
 * PermissionsTable (matrix + 工具栏) + RoleDetailCard (选中角色详情) + CreateRoleDialog.
 *
 * @param props - 组件属性
 * @param props.roles - 角色列表
 * @param props.pages - 可用页面权限列表
 * @param props.matrix - 初始权限矩阵数据
 * @param props.roleList - 角色列表 (含详情)
 * @client-bff
 */
export const PermissionsAdminClient = ({
  roles,
  pages,
  matrix,
  roleList,
}: PermissionsAdminClientProps) => {
  const router = useRouter();
  const [createOpen, togglecreateOpen] = useToggle(false);
  const [selectedRole, setSelectedRole] = useState<string | null>(roles[ZERO]?.name ?? null);
  const [, startTransition] = useTransition();

  const selectedRoleData = roleList.find((role) => role.name === selectedRole) ?? null;

  return (
    <div className="space-y-6">
      <PermissionsTable
        roles={roles}
        roleList={roleList}
        pages={pages}
        matrix={matrix}
        selectedRole={selectedRole}
        onSelectRole={setSelectedRole}
        onSave={async (updates: MatrixUpdate[]) => {
          await patchPermissions(updates);
          // 矩阵变化可能影响我的 allowed → 刷路由让 server 组件重跑
          startTransition(() => router.refresh());
        }}
        onEditRole={handleEdit}
        onDeleteRole={handleDelete}
        onCreateRole={togglecreateOpen}
      />
      {selectedRoleData && (
        <RoleDetailCard role={selectedRoleData} onEdit={handleEdit} onDelete={handleDelete} />
      )}
      <CreateRoleDialog
        onCreated={() => startTransition(() => router.refresh())}
        onOpenChange={togglecreateOpen}
        open={createOpen}
        pages={pages}
      />
    </div>
  );
};
