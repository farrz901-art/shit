"use client";
// AccountSettingsClient — 4 Section, 一面展示不滚动
// Profile(左) + Email/Password(右上) + Deletion(右下)
// 每张卡片内置 StaggerItem (self-trigger) 入场动画, 不需要父 Stagger
import { DeletionSection } from "./deletion-section";
import { EmailSection } from "./email-section";
import { PasswordSection } from "./password-section";
import { ProfileSection } from "./profile-section";

/** 当前账号基本信息
 * @property id - 用户 ID
 * @property email - 邮箱
 * @property display_name - 显示名称
 * @property avatar_url - 头像 URL
 * @property is_pending_deletion - 是否处于待注销状态
 * @property deletion_expires_at - 注销截止时间
 */
export interface AccountMe {
  id: number;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  is_pending_deletion: boolean;
  deletion_expires_at: string | null;
}

/** 账号设置主布局: 4 个 Section 卡片以 3 列网格排列
 * @param me - 当前账号信息
 * @returns 设置页面 JSX
 * @client-bff
 */
export const AccountSettingsClient = ({ me }: { me: AccountMe }) => (
  <div className="grid grid-cols-3 gap-4">
    <div className="col-span-2">
      <ProfileSection
        me={{
          avatar_url: me.avatar_url,
          display_name: me.display_name,
        }}
      />
    </div>
    <div className="col-span-1 flex flex-col gap-4">
      <EmailSection email={me.email} />
      <PasswordSection />
      <div className="flex-1">
        <DeletionSection isPending={me.is_pending_deletion} expiresAt={me.deletion_expires_at} />
      </div>
    </div>
  </div>
);
