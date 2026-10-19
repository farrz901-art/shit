"use client";
// SubmissionsTabs — 客户端组件, 切 mine / all, URL 同步
// Mine 跟 all 内容用子组件
// (2026-06-15) 改走 AppTabs 替 shadcn Tabs 三件套, tabs 配置 + i18n 收口在本组件
// 关联 [[feedback-no-shim-no-minimal-changes]]

import { AllApprovalsTable } from "./all-approvals-table";
import { AppTabs } from "@/components/common/input/app-tabs";
import type { Approval } from "@/lib/api/approvals";
import { MySubmissionsList } from "./my-submissions-list";
import { useRouter } from "@/i18n/navigation";

/** 提交审核标签页组件属性
 * @shared */
export interface SubmissionsTabsProps {
  activeTab: "mine" | "all";
  isAdmin: boolean;
  initialMine: Approval[];
  initialAll: Approval[] | null;
}

/**
 * SubmissionsTabs - 提交审核标签页
 * @param props.activeTab - 当前激活的 tab
 * @param props.isAdmin - 是否为管理员
 * @param props.initialMine - 预取的"我的"审批数据
 * @param props.initialAll - 预取的"全部"审批数据
 * @client-bff
 */
export const SubmissionsTabs = ({
  activeTab,
  isAdmin,
  initialMine,
  initialAll,
}: SubmissionsTabsProps) => {
  const router = useRouter();

  const handleTabChange = (key: string) => {
    router.push(`/submissions?tab=${key}`);
  };

  const Options = [
    {
      content: <MySubmissionsList initialData={initialMine} />,
      label: "我提交的",
      value: "mine",
    },
    ...(isAdmin
      ? [
          {
            content: <AllApprovalsTable initialData={initialAll ?? []} />,
            label: "全部待审",
            value: "all",
          },
        ]
      : []),
  ];

  return (
    <AppTabs options={Options} value={activeTab} onChange={handleTabChange} dataTestid="tab" />
  );
};
