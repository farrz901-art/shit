/**
 * PermissionsTable 树形 UI 测试 (2026-07-02 nav spec §5.4)
 * 5 个用例覆盖树形渲染 / 父级 disabled / indeterminate / super_admin 豁免.
 */
/* eslint-disable id-length, no-magic-numbers, max-statements -- test fixture */
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PermissionsTable } from "./permissions-table";
import type { MatrixPage, MatrixRole, RoleListItem } from "../_hooks/use-permissions-table";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  NextIntlClientProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const mkRole = (name: string): MatrixRole => ({
  name,
  label_zh: name,
  label_en: name,
  is_system: name !== "custom",
});

const mkPage = (
  overrides: Partial<MatrixPage & { metadata?: { parent_id?: string; is_group?: boolean } }>,
): MatrixPage & { metadata?: { parent_id?: string; is_group?: boolean } } => ({
  key: "x",
  label_zh: "X",
  label_en: "X",
  path: "/x",
  ...overrides,
});

const mkRoleList = (roles: MatrixRole[]): RoleListItem[] =>
  roles.map((role) => ({ ...role, is_deletable: !role.is_system, user_count: 0 }));

describe("PermissionsTable 树形", () => {
  it("树形渲染: 父级 + 子项都显示", () => {
    const roles = [mkRole("user")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
      mkPage({ key: "chat", label_zh: "对话" }),
    ];
    const matrix = { user: { admin: false, admin_users: true, chat: true } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={async () => {}}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    expect(screen.getByText("管理中心")).toBeInTheDocument();
    expect(screen.getByText("用户管理")).toBeInTheDocument();
    expect(screen.getByText("对话")).toBeInTheDocument();
  });

  it("父级 checkbox disabled", () => {
    const roles = [mkRole("user")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
    ];
    const matrix = { user: { admin: false, admin_users: true } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={async () => {}}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    const adminCheckbox = screen.getByRole("checkbox", { name: /管理中心/ });
    expect(adminCheckbox).toBeDisabled();
  });

  it("叶子 toggle 调 onSave 提交 updates", async () => {
    const onSave = vi.fn(async () => {});
    const user = userEvent.setup();
    const roles = [mkRole("user")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
    ];
    const matrix = { user: { admin: false, admin_users: false } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={onSave}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    await user.click(screen.getByTestId("permissions-edit-toggle"));
    await user.click(screen.getByRole("checkbox", { name: /用户管理/ }));
    await user.click(screen.getByTestId("permissions-save"));
    expect(onSave).toHaveBeenCalled();
    const updates = (
      onSave.mock.calls[0] as unknown as [{ role_name: string; page_key: string; allowed: boolean }]
    )?.[0];
    expect(updates).toContainEqual(
      expect.objectContaining({ role_name: "user", page_key: "admin_users", allowed: true }),
    );
  });

  it("super_admin 行所有 checkbox 永远 checked (parent disabled, leaf always-checked)", () => {
    const roles = [mkRole("user"), mkRole("super_admin")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
    ];
    const matrix = { user: {}, super_admin: { admin: true, admin_users: true } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={async () => {}}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    // super_admin 行的 leaf admin_users 永远 checked (via checked set trick in PermissionsTable)
    const superAdminRow = screen.getByTestId("permission-role-super_admin");
    const checkboxes = superAdminRow.querySelectorAll("[role='checkbox']");
    const superAdminLeafCheckbox = checkboxes[1] as HTMLElement;
    expect(superAdminLeafCheckbox).toHaveAttribute("aria-checked", "true");
    // parent admin 在 super_admin 行内 disabled (TreeCheckbox 父级禁用规则)
    const superAdminParentCheckbox = checkboxes[0] as HTMLElement;
    expect(superAdminParentCheckbox).toBeDisabled();
  });

  it("indeterminate: 部分子项勾选时父级显示 mixed", () => {
    const roles = [mkRole("user")];
    const pages = [
      mkPage({ key: "admin", label_zh: "管理中心", metadata: { is_group: true } }),
      mkPage({ key: "admin_users", label_zh: "用户管理", metadata: { parent_id: "admin" } }),
      mkPage({ key: "admin_dicts", label_zh: "字典管理", metadata: { parent_id: "admin" } }),
    ];
    const matrix = { user: { admin: false, admin_users: true, admin_dicts: false } };
    render(
      <PermissionsTable
        roles={roles}
        roleList={mkRoleList(roles)}
        pages={pages}
        matrix={matrix}
        selectedRole={null}
        onSelectRole={() => {}}
        onSave={async () => {}}
        onEditRole={() => {}}
        onDeleteRole={() => {}}
        onCreateRole={() => {}}
      />,
    );
    const adminCheckbox = screen.getByRole("checkbox", { name: /管理中心/ });
    expect(adminCheckbox).toHaveAttribute("aria-checked", "mixed");
  });
});
